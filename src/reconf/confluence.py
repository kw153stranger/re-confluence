"""Confluence 접근 클라이언트 (구현설계 §6.1).

`ConfluenceClient` 프로토콜을 두어 수집 로직(export.py)이 구현체에 의존하지 않게 한다.
- `ConfluenceRestClient`: httpx 기반 실 구현(Confluence REST). mcp-atlassian도 동일 REST를 감싼다.
- 테스트/오프라인은 동일 프로토콜을 만족하는 fake로 대체한다.
"""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

import httpx

from .logging_setup import get_logger

log = get_logger("confluence")


@runtime_checkable
class ConfluenceClient(Protocol):
    """수집에 필요한 최소 인터페이스."""

    def list_pages(self, space: str) -> list[dict]:
        """space의 페이지 메타 목록(id/title/version 등)을 반환."""
        ...

    def get_page(self, page_id: str) -> dict:
        """페이지 본문(storage)·메타를 반환."""
        ...

    def get_attachments(self, page_id: str) -> list[dict]:
        """첨부 메타(title/download url) 목록."""
        ...

    def download_attachment(self, attachment: dict) -> bytes:
        """첨부 바이너리를 내려받아 반환."""
        ...


class ConfluenceRestClient:
    """Confluence Cloud REST v1 기반 실 구현.

    인증 토큰은 환경변수로 주입한다(파일 저장 금지):
      CONFLUENCE_BASE_URL, CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN
    """

    def __init__(self, base_url: str | None = None, timeout: float = 30.0):
        self.base_url = (base_url or os.environ.get("CONFLUENCE_BASE_URL", "")).rstrip("/")
        email = os.environ.get("CONFLUENCE_EMAIL", "")
        token = os.environ.get("CONFLUENCE_API_TOKEN", "")
        if not (self.base_url and email and token):
            raise RuntimeError(
                "Confluence 접속 정보가 없습니다. "
                "CONFLUENCE_BASE_URL/EMAIL/API_TOKEN 환경변수를 설정하세요."
            )
        self._client = httpx.Client(base_url=self.base_url, auth=(email, token), timeout=timeout)

    def list_pages(self, space: str) -> list[dict]:
        pages: list[dict] = []
        start, limit = 0, 50
        while True:
            r = self._client.get(
                "/rest/api/content",
                params={"spaceKey": space, "type": "page", "start": start, "limit": limit},
            )
            r.raise_for_status()
            data = r.json()
            pages.extend(data.get("results", []))
            if start + limit >= data.get("size", 0) and not data.get("_links", {}).get("next"):
                break
            start += limit
        return pages

    def get_page(self, page_id: str) -> dict:
        r = self._client.get(
            f"/rest/api/content/{page_id}",
            params={"expand": "body.storage,version,history,metadata.labels,ancestors"},
        )
        r.raise_for_status()
        return r.json()

    def get_attachments(self, page_id: str) -> list[dict]:
        r = self._client.get(f"/rest/api/content/{page_id}/child/attachment")
        r.raise_for_status()
        return r.json().get("results", [])

    def download_attachment(self, attachment: dict) -> bytes:
        download = attachment.get("_links", {}).get("download", "")
        if not download:
            return b""
        r = self._client.get(download)
        r.raise_for_status()
        return r.content


@runtime_checkable
class ConfluenceWriter(Protocol):
    """신규 Space 업로드에 필요한 최소 쓰기 인터페이스 (구현설계 §6.6)."""

    def ensure_space(self, key: str, name: str) -> None:
        ...

    def upsert_page(
        self,
        space: str,
        source_page_id: str,
        title: str,
        body_storage: str,
        parent_id: str | None,
        labels: list[str],
    ) -> tuple[str, str]:
        """source_page_id를 멱등 키로 생성/갱신. body는 storage(XHTML).
        (target_page_id, 'created'|'updated') 반환."""
        ...


class ConfluenceRestWriter:
    """Confluence REST 쓰기 구현(개요). source_page_id는 페이지 property로 저장해 멱등.

    실 사용 시 CONFLUENCE_* 환경변수가 필요하다(원본과 분리된 신규 Space 대상).
    """

    PROP_KEY = "reconf_source_id"

    def __init__(self, base_url: str | None = None, timeout: float = 30.0):
        self.base_url = (base_url or os.environ.get("CONFLUENCE_BASE_URL", "")).rstrip("/")
        email = os.environ.get("CONFLUENCE_EMAIL", "")
        token = os.environ.get("CONFLUENCE_API_TOKEN", "")
        if not (self.base_url and email and token):
            raise RuntimeError(
                "Confluence 접속 정보가 없습니다. "
                "CONFLUENCE_BASE_URL/EMAIL/API_TOKEN 환경변수를 설정하세요."
            )
        self._client = httpx.Client(base_url=self.base_url, auth=(email, token), timeout=timeout)

    def ensure_space(self, key: str, name: str) -> None:
        r = self._client.get(f"/rest/api/space/{key}")
        if r.status_code == 200:
            return
        self._client.post("/rest/api/space", json={"key": key, "name": name}).raise_for_status()

    def _find_by_source(self, space: str, source_page_id: str) -> str | None:
        cql = f'space="{space}" and label="src-{source_page_id}"'
        r = self._client.get("/rest/api/content/search", params={"cql": cql})
        r.raise_for_status()
        results = r.json().get("results", [])
        return results[0]["id"] if results else None

    def upsert_page(
        self,
        space: str,
        source_page_id: str,
        title: str,
        body_storage: str,
        parent_id: str | None,
        labels: list[str],
    ) -> tuple[str, str]:
        existing = self._find_by_source(space, source_page_id)
        payload = {
            "type": "page",
            "title": title,
            "space": {"key": space},
            "body": {"storage": {"value": body_storage, "representation": "storage"}},
        }
        if parent_id:
            payload["ancestors"] = [{"id": parent_id}]
        if existing:
            self._client.put(f"/rest/api/content/{existing}", json=payload).raise_for_status()
            return existing, "updated"
        r = self._client.post("/rest/api/content", json=payload)
        r.raise_for_status()
        pid = r.json()["id"]
        # 멱등 추적용 라벨 + 표준 라벨
        all_labels = [f"src-{source_page_id}", *labels]
        self._client.post(
            f"/rest/api/content/{pid}/label",
            json=[{"prefix": "global", "name": label} for label in all_labels],
        )
        return pid, "created"
