"""[Cluster] 동일 업무 병합·연도 그룹핑·중복 탐지 (구현설계 §6.3).

- 임베딩은 embed.ensure로 문서별 캐시를 재사용/생성.
- 중복 탐지: 제목 유사도(rapidfuzz) + 본문 임베딩 코사인 유사도.
- 정본(canonical) 선정 후 중복 후보를 표시(자동 삭제 없음).
"""

from __future__ import annotations

import numpy as np
from rapidfuzz import fuzz

from . import embed
from .config import Config
from .embed import Embedder
from .logging_setup import get_logger, progress
from .markdown import parse_raw
from .models import AnalysisResult, Cluster, ClusterMember, RawDoc
from .store import Store

log = get_logger("cluster")


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def normalize_task(business: str | None) -> str:
    """업무(task) 키 정규화 — 공백 축약·트림으로 표기 흔들림 병합 (예: 'SSL  적용'→'SSL 적용')."""
    if not business:
        return "미분류"
    return " ".join(business.split())


def group_key(a: AnalysisResult) -> tuple[str, int | None]:
    """업무(+연도) 그룹 키. business가 없으면 '미분류'."""
    return (normalize_task(a.business), a.year)


def pick_canonical(members: list[AnalysisResult], raws: dict[str, RawDoc]) -> str:
    """정본 선정: 최신 수정일 → 최장 본문 순."""
    def sort_key(a: AnalysisResult):
        raw = raws.get(a.source_page_id)
        updated = (raw.updated_at or "") if raw else ""
        length = len(raw.body_markdown) if raw else 0
        return (updated, length)

    return max(members, key=sort_key).source_page_id


def detect_duplicates(
    members: list[AnalysisResult],
    raws: dict[str, RawDoc],
    vectors: dict[str, np.ndarray],
    *,
    sim_threshold: float,
    fuzzy_threshold: int = 85,
) -> dict[str, tuple[str, float]]:
    """중복 후보 매핑: dup_id -> (canonical_id, similarity)."""
    canonical = pick_canonical(members, raws)
    dups: dict[str, tuple[str, float]] = {}
    cvec = vectors.get(canonical)
    ctitle = raws[canonical].title if canonical in raws else ""
    for a in members:
        if a.source_page_id == canonical:
            continue
        title = raws[a.source_page_id].title if a.source_page_id in raws else ""
        title_sim = fuzz.token_set_ratio(ctitle, title)
        emb_sim = 0.0
        if cvec is not None and a.source_page_id in vectors:
            emb_sim = _cosine(cvec, vectors[a.source_page_id])
        if emb_sim >= sim_threshold or title_sim >= fuzzy_threshold:
            dups[a.source_page_id] = (canonical, max(emb_sim, title_sim / 100.0))
    return dups


def build_clusters(
    results: list[AnalysisResult],
    raws: dict[str, RawDoc],
    vectors: dict[str, np.ndarray],
    *,
    sim_threshold: float,
) -> list[Cluster]:
    groups: dict[tuple[str, int | None], list[AnalysisResult]] = {}
    for a in results:
        groups.setdefault(group_key(a), []).append(a)

    clusters: list[Cluster] = []
    for (business, year), members in sorted(groups.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):  # noqa: E501
        canonical = pick_canonical(members, raws)
        dups = detect_duplicates(members, raws, vectors, sim_threshold=sim_threshold)
        related = {a.source_page_id for a in members} - {canonical} - set(dups)
        cm: list[ClusterMember] = [ClusterMember(source_page_id=canonical, role="canonical")]
        for dup_id, (_, sim) in dups.items():
            cm.append(
                ClusterMember(source_page_id=dup_id, role="duplicate", similarity=round(sim, 3))
            )
        for rid in sorted(related):
            cm.append(ClusterMember(source_page_id=rid, role="related"))
        clusters.append(Cluster(business=business, year=year, members=cm))
    return clusters


def run(
    cfg: Config,
    store: Store,
    *,
    resume: bool = False,
    dry_run: bool = False,
    embedder: Embedder | None = None,
) -> list[Cluster]:
    store.ensure_dirs()
    if embedder is None:
        from .embed import TEIEmbedder

        embedder = TEIEmbedder(cfg.embeddings)

    # analysis + raw 로드
    results = [store.read_json(p, AnalysisResult) for p in store.list_analysis()]
    raws: dict[str, RawDoc] = {}
    for p in store.list_raw():
        d = parse_raw(p.read_text(encoding="utf-8"))
        raws[d.source_page_id] = d

    # 임베딩(캐시 재사용/생성)
    vectors: dict[str, np.ndarray] = {}
    total = len(results)
    for idx, a in enumerate(results, 1):
        progress(log, "Cluster", idx, total)
        raw = raws.get(a.source_page_id)
        text = raw.body_markdown if raw else a.summary
        rec = embed.ensure(store, cfg.embeddings, a.source_page_id, text, embedder)
        vectors[a.source_page_id] = np.array(rec.vector, dtype=float)

    clusters = build_clusters(results, raws, vectors, sim_threshold=cfg.cluster.sim_threshold)
    n_dup = sum(1 for c in clusters for m in c.members if m.role == "duplicate")
    log.info("[Cluster] 업무그룹 %d · 중복후보 %d", len(clusters), n_dup)

    if not dry_run:
        # list[Cluster] 저장을 위해 래퍼 모델 사용
        from pydantic import RootModel

        ClusterList = RootModel[list[Cluster]]
        store.clusters_path.write_text(
            ClusterList(clusters).model_dump_json(indent=2), encoding="utf-8"
        )
    return clusters
