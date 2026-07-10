"""[Export] Confluence 수집 → Raw Markdown 저장 (구현설계 §6.1).

수집 로직은 ConfluenceClient 프로토콜에 의존하고, 변환·저장은 여기서 담당한다.
멱등: 페이지 수정일(updated_at)이 그대로면 재저장하지 않는다.
"""

from __future__ import annotations

from .config import Config
from .confluence import ConfluenceClient
from .logging_setup import get_logger
from .markdown import dump_raw, html_to_markdown, parse_raw, slugify
from .models import RawDoc
from .store import Store

log = get_logger("export")


def _page_to_rawdoc(page: dict, attachments: list[dict], base_url: str) -> RawDoc:
    """Confluence REST content 객체 → RawDoc."""
    body_html = page.get("body", {}).get("storage", {}).get("value", "")
    version = page.get("version", {})
    history = page.get("history", {})
    labels = page.get("metadata", {}).get("labels", {}).get("results", [])
    webui = page.get("_links", {}).get("webui", "")
    return RawDoc(
        source_page_id=str(page.get("id", "")),
        source_url=f"{base_url}{webui}" if webui else "",
        title=page.get("title", ""),
        author=(version.get("by") or {}).get("displayName"),
        created_at=history.get("createdDate"),
        updated_at=version.get("when"),
        original_labels=[label.get("name", "") for label in labels],
        attachments=[a.get("title", "") for a in attachments],
        body_markdown=html_to_markdown(body_html),
    )


def _existing_updated_at(store: Store, page_id: str) -> str | None:
    path = store.find_raw(page_id)
    if not path:
        return None
    return parse_raw(path.read_text(encoding="utf-8")).updated_at


def run(
    cfg: Config,
    store: Store,
    *,
    resume: bool = False,
    dry_run: bool = False,
    client: ConfluenceClient | None = None,
) -> list[RawDoc]:
    store.ensure_dirs()
    if client is None:  # 지연 생성 — 실 구현은 환경변수 필요
        from .confluence import ConfluenceRestClient

        client = ConfluenceRestClient()

    space = cfg.source.space
    pages = client.list_pages(space)
    log.info("[Export] space=%s pages=%d", space, len(pages))

    base_url = getattr(client, "base_url", "")
    saved: list[RawDoc] = []
    skipped = 0
    for meta in pages:
        page_id = str(meta.get("id", ""))
        full = client.get_page(page_id)
        new_updated = full.get("version", {}).get("when")
        if new_updated and _existing_updated_at(store, page_id) == new_updated:
            skipped += 1
            continue  # 멱등: 수정일 동일 → 재저장 생략
        attachments = client.get_attachments(page_id)
        doc = _page_to_rawdoc(full, attachments, base_url)
        saved.append(doc)
        if not dry_run:
            store.write_raw(doc.source_page_id, slugify(doc.title), dump_raw(doc))

    log.info("[Export] 저장 %d건, 스킵(변경없음) %d건 (dry_run=%s)", len(saved), skipped, dry_run)
    return saved
