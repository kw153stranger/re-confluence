"""[Export] Confluence 수집 → Raw Markdown 저장 (구현설계 §6.1).

수집 로직은 ConfluenceClient 프로토콜에 의존하고, 변환·저장은 여기서 담당한다.
멱등: 페이지 수정일(updated_at)이 그대로면 재저장하지 않는다.
"""

from __future__ import annotations

from .concurrency import run_concurrent
from .config import Config
from .confluence import ConfluenceClient
from .logging_setup import ProgressCounter, get_logger
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
    ancestors = page.get("ancestors", [])
    return RawDoc(
        source_page_id=str(page.get("id", "")),
        source_url=f"{base_url}{webui}" if webui else "",
        title=page.get("title", ""),
        author=(version.get("by") or {}).get("displayName"),
        created_at=history.get("createdDate"),
        updated_at=version.get("when"),
        original_labels=[label.get("name", "") for label in labels],
        attachments=[a.get("title", "") for a in attachments],
        path=[a.get("title", "") for a in ancestors if a.get("title")],  # 기존 메뉴 경로
        body_markdown=html_to_markdown(body_html),
        body_storage=body_html,  # 원본 storage 보존 → 업로드 원문 동일성
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
    counter = ProgressCounter(log, "Export", len(pages))

    def work(meta: dict) -> tuple[str, RawDoc | None]:
        counter.tick()
        page_id = str(meta.get("id", ""))
        try:
            full = client.get_page(page_id)
            new_updated = full.get("version", {}).get("when")
            if new_updated and _existing_updated_at(store, page_id) == new_updated:
                return ("skip", None)  # 멱등: 수정일 동일 → 재저장 생략
            attachments = client.get_attachments(page_id)
            doc = _page_to_rawdoc(full, attachments, base_url)
            if not dry_run:
                store.write_raw(doc.source_page_id, slugify(doc.title), dump_raw(doc))
                if doc.body_storage:
                    store.write_storage(doc.source_page_id, doc.body_storage)
                for att in attachments:
                    data = client.download_attachment(att)
                    if data:
                        store.write_attachment(page_id, att.get("title", "attachment"), data)
            return ("saved", doc)
        except Exception as e:  # noqa: BLE001 - 페이지 단위 오류 격리
            log.warning("[Export] %s 실패: %s", page_id, e)
            return ("error", None)

    rows = run_concurrent(work, pages, cfg.concurrency.export)
    saved = [d for status, d in rows if status == "saved" and d is not None]
    skipped = sum(1 for status, _ in rows if status == "skip")
    errors = sum(1 for status, _ in rows if status == "error")
    log.info(
        "[Export] 저장 %d · 스킵(변경없음) %d · 실패 %d (dry_run=%s)",
        len(saved), skipped, errors, dry_run,
    )
    return saved
