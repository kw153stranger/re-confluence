"""[Build] 업무 중심 IA·Page Properties·Labels 생성 (구현설계 §6.4).

입력: clusters.json, analysis/*.json, raw/*.md, labels.json(레지스트리)
출력: build/<page_id>.md, build/tree.json, labels.json(갱신)
라벨은 labels 마스터를 거쳐 canonical로 정규화한다(§6.4a).
"""

from __future__ import annotations

from pydantic import RootModel

from .config import Config
from .labels import load_registry, resolve_label, save_registry
from .logging_setup import get_logger
from .markdown import parse_raw
from .models import (
    STATUS_CANONICAL,
    STATUS_DUPLICATE,
    AnalysisResult,
    BuildPage,
    BuildTree,
    BusinessGroup,
    Cluster,
    LabelRegistry,
    PageProperties,
    RawDoc,
    YearGroup,
)
from .store import Store

log = get_logger("build")

_ClusterList = RootModel[list[Cluster]]


def _make_labels(reg: LabelRegistry, a: AnalysisResult, role: str, cfg: Config) -> list[str]:
    """표준 라벨을 마스터 canonical로 정규화해 부여."""
    out: list[str] = []
    ft = cfg.labels.merge_fuzzy_threshold
    if a.business:
        out.append(resolve_label(reg, "업무", a.business, fuzzy_threshold=ft))
    if a.system:
        out.append(resolve_label(reg, "시스템", a.system, fuzzy_threshold=ft))
    if a.year:
        out.append(resolve_label(reg, "연도", str(a.year), fuzzy_threshold=ft))
    status = STATUS_DUPLICATE if role == "duplicate" else STATUS_CANONICAL
    out.append(resolve_label(reg, "상태", status, fuzzy_threshold=ft))
    return out


def _page_markdown(page: BuildPage, raw: RawDoc | None) -> str:
    p = page.properties
    props = [
        "| 필드 | 값 |",
        "| --- | --- |",
        f"| 업무명 | {p.business} |",
        f"| 담당 | {p.owner or ''} |",
        f"| 시스템 | {p.system or ''} |",
        f"| 연도 | {p.year or ''} |",
        f"| 상태 | {p.status} |",
        f"| 원본링크 | {p.source} |",
    ]
    body = raw.body_markdown if raw else ""
    return (
        f"# {page.title}\n\n"
        f"## Page Properties\n" + "\n".join(props) + "\n\n"
        f"## 요약\n{page.summary}\n\n"
        f"**라벨**: {', '.join(page.labels)}\n\n"
        f"---\n\n{body}\n"
    )


def build_ia(
    clusters: list[Cluster],
    analyses: dict[str, AnalysisResult],
    raws: dict[str, RawDoc],
    reg: LabelRegistry,
    cfg: Config,
    storages: dict[str, str] | None = None,
) -> tuple[list[BuildPage], BuildTree]:
    storages = storages or {}
    pages: list[BuildPage] = []
    biz_map: dict[str, dict[int | None, list[str]]] = {}

    for cluster in clusters:
        for m in cluster.members:
            a = analyses.get(m.source_page_id)
            if a is None:
                continue
            raw = raws.get(m.source_page_id)
            labels = _make_labels(reg, a, m.role, cfg)
            props = PageProperties(
                business=a.business or "미분류",
                owner=raw.author if raw else None,
                system=a.system,
                year=a.year,
                status=STATUS_DUPLICATE if m.role == "duplicate" else STATUS_CANONICAL,
                source=raw.source_url if raw else "",
            )
            pages.append(
                BuildPage(
                    source_page_id=a.source_page_id,
                    title=raw.title if raw else a.title_normalized,
                    business=cluster.business,
                    year=cluster.year,
                    role=m.role,
                    labels=labels,
                    properties=props,
                    summary=a.summary,
                    body_markdown=raw.body_markdown if raw else "",
                    body_storage=storages.get(m.source_page_id, ""),
                )
            )
            biz_map.setdefault(cluster.business, {}).setdefault(cluster.year, []).append(
                a.source_page_id
            )

    tree = BuildTree(
        businesses=[
            BusinessGroup(
                business=biz,
                index_page_id=f"index-{biz}",
                years=[
                    YearGroup(year=y, page_ids=ids)
                    for y, ids in sorted(years.items(), key=lambda kv: str(kv[0]))
                ],
            )
            for biz, years in sorted(biz_map.items())
        ]
    )
    return pages, tree


def run(
    cfg: Config, store: Store, *, resume: bool = False, dry_run: bool = False
) -> list[BuildPage]:
    store.ensure_dirs()
    if not store.exists(store.clusters_path):
        log.warning("[Build] clusters.json 이 없습니다. 먼저 cluster를 실행하세요.")
        return []

    clusters = _ClusterList.model_validate_json(store.clusters_path.read_text("utf-8")).root
    analyses = {p.stem: store.read_json(p, AnalysisResult) for p in store.list_analysis()}
    raws: dict[str, RawDoc] = {}
    storages: dict[str, str] = {}
    for p in store.list_raw():
        d = parse_raw(p.read_text(encoding="utf-8"))
        raws[d.source_page_id] = d
        storages[d.source_page_id] = store.read_storage(d.source_page_id)

    reg = load_registry(store)
    pages, tree = build_ia(clusters, analyses, raws, reg, cfg, storages)

    if not dry_run:
        for page in pages:
            md = _page_markdown(page, raws.get(page.source_page_id))
            (store.build_dir / f"{page.source_page_id}.md").write_text(md, encoding="utf-8")
        (store.build_dir / "tree.json").write_text(tree.model_dump_json(indent=2), encoding="utf-8")
        _PageList = RootModel[list[BuildPage]]
        (store.build_dir / "pages.json").write_text(
            _PageList(pages).model_dump_json(indent=2), encoding="utf-8"
        )
        save_registry(store, reg)

    n_cand = sum(1 for e in reg.entries if e.status == "candidate")
    log.info("[Build] 페이지 %d · 업무 %d · 라벨후보 %d", len(pages), len(tree.businesses), n_cand)
    return pages
