"""[Review] 사람 검수 — 분류 확인·수정·승인 (구현설계 §6.5).

- `--export-queue`: 검수 큐(review_queue.json)를 저신뢰·중복 후보 우선으로 export.
- `--apply <file>`: 사람이 수정/승인한 결정(ReviewDecision 목록)을 review.json으로 반영.
  승인된 문서만 Upload 대상이 된다.
"""

from __future__ import annotations

from pydantic import RootModel

from .config import Config
from .labels import load_registry, save_registry
from .logging_setup import get_logger
from .markdown import parse_raw
from .models import (
    AnalysisResult,
    Cluster,
    ReviewDecision,
    ReviewQueueItem,
)
from .store import Store

log = get_logger("review")

_ClusterList = RootModel[list[Cluster]]
_QueueList = RootModel[list[ReviewQueueItem]]
_DecisionList = RootModel[list[ReviewDecision]]


def build_queue(
    analyses: dict[str, AnalysisResult],
    clusters: list[Cluster],
    titles: dict[str, str],
) -> list[ReviewQueueItem]:
    """저신뢰(confidence 최소값)·중복 후보를 상단에 오도록 정렬한 큐."""
    role: dict[str, str] = {}
    dup_of: dict[str, str] = {}
    for c in clusters:
        canon = next((m.source_page_id for m in c.members if m.role == "canonical"), None)
        for m in c.members:
            role[m.source_page_id] = m.role
            if m.role == "duplicate":
                dup_of[m.source_page_id] = canon

    items: list[ReviewQueueItem] = []
    for pid, a in analyses.items():
        conf = a.confidence
        items.append(
            ReviewQueueItem(
                source_page_id=pid,
                title=titles.get(pid, a.title_normalized),
                business=a.business,
                year=a.year,
                labels=a.labels,
                min_confidence=min(conf.business, conf.project, conf.system, conf.year),
                role=role.get(pid, "canonical"),
                duplicate_of=dup_of.get(pid),
            )
        )
    # 중복 후보 우선(True 먼저) → 신뢰도 낮은 순
    items.sort(key=lambda it: (it.role != "duplicate", it.min_confidence))
    return items


def apply_decisions(
    store: Store, decisions: list[ReviewDecision], approve_labels: bool = True
) -> None:
    """검수 결정을 review.json으로 저장하고, 라벨 후보를 승인 처리."""
    store.write_json(store.review_path, _DecisionList(decisions))
    if approve_labels:
        reg = load_registry(store)
        promoted = 0
        for e in reg.entries:
            if e.status == "candidate":
                e.status = "approved"
                promoted += 1
        save_registry(store, reg)
        if promoted:
            log.info("[Review] 라벨 후보 %d건 승인(approved)", promoted)


def load_queue(store: Store) -> list[ReviewQueueItem]:
    """store에서 검수 큐를 계산한다(웹 API·CLI 공용)."""
    analyses = {p.stem: store.read_json(p, AnalysisResult) for p in store.list_analysis()}
    clusters = []
    if store.exists(store.clusters_path):
        clusters = _ClusterList.model_validate_json(store.clusters_path.read_text("utf-8")).root
    titles = {}
    for p in store.list_raw():
        d = parse_raw(p.read_text(encoding="utf-8"))
        titles[d.source_page_id] = d.title
    return build_queue(analyses, clusters, titles)


def run(
    cfg: Config,
    store: Store,
    *,
    export_queue: bool = False,
    apply: str | None = None,
    resume: bool = False,
    dry_run: bool = False,
) -> None:
    store.ensure_dirs()

    if export_queue:
        queue = load_queue(store)
        if not dry_run:
            (store.root / "review_queue.json").write_text(
                _QueueList(queue).model_dump_json(indent=2), encoding="utf-8"
            )
        log.info("[Review] 검수 큐 %d건 export (저신뢰·중복 우선)", len(queue))
        return

    if apply:
        from pathlib import Path

        decisions = _DecisionList.model_validate_json(
            Path(apply).read_text(encoding="utf-8")
        ).root
        if not dry_run:
            apply_decisions(store, decisions)
        n_ok = sum(1 for d in decisions if d.status == "approved")
        log.info("[Review] 결정 %d건 반영(승인 %d)", len(decisions), n_ok)
        return

    log.warning("[Review] --export-queue 또는 --apply <file> 중 하나를 지정하세요.")
