"""[Upload] 신규 Space 생성·멱등 업로드 (구현설계 §6.6).

입력: build/pages.json, build/tree.json, review.json(승인 결정)
처리: 승인 문서만 신규 Space에 upsert(source_page_id 멱등 키). 업무 index를 부모로.
출력: upload.log (UploadResult 목록)
"""

from __future__ import annotations

from pydantic import RootModel

from .config import Config
from .confluence import ConfluenceWriter
from .logging_setup import get_logger, progress
from .models import BuildPage, BuildTree, BusinessGroup, ReviewDecision, UploadResult
from .storagefmt import render_page
from .store import Store

log = get_logger("upload")

_PageList = RootModel[list[BuildPage]]
_DecisionList = RootModel[list[UploadResult]]


def _approved_ids(store: Store) -> set[str] | None:
    """review.json에서 승인된 page_id 집합. 없으면 None(=전체 허용, 경고)."""
    if not store.exists(store.review_path):
        return None
    decisions = RootModel[list[ReviewDecision]].model_validate_json(
        store.review_path.read_text("utf-8")
    ).root
    return {d.source_page_id for d in decisions if d.status == "approved"}


def _page_body(page: BuildPage) -> str:
    """업로드 본문 = Page Properties 매크로 + 원문(storage) (§5.3·§6.6)."""
    return render_page(page)


def run(
    cfg: Config,
    store: Store,
    *,
    target_space: str | None = None,
    resume: bool = False,
    dry_run: bool = False,
    writer: ConfluenceWriter | None = None,
) -> list[UploadResult]:
    store.ensure_dirs()
    pages_path = store.build_dir / "pages.json"
    if not store.exists(pages_path):
        log.warning("[Upload] build/pages.json 이 없습니다. 먼저 build를 실행하세요.")
        return []

    pages = _PageList.model_validate_json(pages_path.read_text("utf-8")).root
    approved = _approved_ids(store)
    if approved is None:
        log.warning("[Upload] review.json 이 없어 전체를 업로드합니다(검수 생략).")

    # 트리(개요 본문·연도 구조)
    tree_path = store.build_dir / "tree.json"
    groups: dict[str, BusinessGroup] = {}
    if store.exists(tree_path):
        tree = BuildTree.model_validate_json(tree_path.read_text("utf-8"))
        groups = {g.business: g for g in tree.businesses}

    space = target_space or cfg.target.space
    if writer is None:
        from .confluence import ConfluenceRestWriter

        writer = ConfluenceRestWriter()
    if not dry_run:
        writer.ensure_space(space, "재구성 아카이브")

    # IA: 업무 → {개요, 작업실적 → 연도 → 문서}. 필요한 부모를 지연 생성한다.
    biz_pid: dict[str, str] = {}
    overview_done: set[str] = set()
    worklog_pid: dict[str, str] = {}
    year_pid: dict[tuple[str, int | None], str] = {}

    def _ensure_year_parent(business: str, year: int | None) -> str:
        """업무→개요/작업실적→연도 체인을 보장하고 연도 페이지 id 반환."""
        if business not in biz_pid:
            pid, _ = writer.upsert_page(
                space, f"biz-{business}", business, f"<h1>{business}</h1>", None, []
            )
            biz_pid[business] = pid
        if business not in overview_done:
            g = groups.get(business)
            body = g.overview_storage if g else f"<h1>{business} 개요</h1>"
            writer.upsert_page(space, f"overview-{business}", "개요", body, biz_pid[business], [])
            overview_done.add(business)
        if business not in worklog_pid:
            pid, _ = writer.upsert_page(
                space, f"worklog-{business}", "작업실적",
                "<p>연도별 작업실적</p>", biz_pid[business], [],
            )
            worklog_pid[business] = pid
        key = (business, year)
        if key not in year_pid:
            label = str(year) if year is not None else "연도미상"
            pid, _ = writer.upsert_page(
                space, f"year-{business}-{year}", label,
                f"<p>{label}년 작업실적</p>", worklog_pid[business], [],
            )
            year_pid[key] = pid
        return year_pid[key]

    results: list[UploadResult] = []
    total = len(pages)
    for idx, page in enumerate(pages, 1):
        progress(log, "Upload", idx, total)
        if approved is not None and page.source_page_id not in approved:
            results.append(UploadResult(source_page_id=page.source_page_id, status="skipped"))
            continue
        if dry_run:
            results.append(UploadResult(source_page_id=page.source_page_id, status="skipped"))
            continue
        try:
            parent = _ensure_year_parent(page.business, page.year)
            target_id, action = writer.upsert_page(
                space, page.source_page_id, page.title, _page_body(page), parent, page.labels
            )
            results.append(
                UploadResult(
                    source_page_id=page.source_page_id, status=action, target_page_id=target_id
                )
            )
        except Exception as e:  # noqa: BLE001 - 부분 실패 격리
            results.append(
                UploadResult(source_page_id=page.source_page_id, status="failed", error=str(e))
            )
            log.warning("[Upload] %s 실패: %s", page.source_page_id, e)

    if not dry_run:
        (store.root / "upload.log").write_text(
            _DecisionList(results).model_dump_json(indent=2), encoding="utf-8"
        )
    n_ok = sum(1 for r in results if r.status in ("created", "updated"))
    n_fail = sum(1 for r in results if r.status == "failed")
    log.info("[Upload] 업로드 %d · 실패 %d · 스킵 %d", n_ok, n_fail, len(results) - n_ok - n_fail)
    return results
