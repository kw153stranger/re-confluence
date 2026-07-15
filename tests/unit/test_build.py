"""Build 검증 — IA 트리·Page Properties·라벨 canonical·pages.json."""

from pydantic import RootModel

from reconf import build
from reconf.config import Config
from reconf.markdown import dump_raw
from reconf.models import AnalysisResult, Cluster, ClusterMember, RawDoc
from reconf.store import Store


def _seed(store, pid, business, year, title, system="ERP", menu_path=None):
    store.ensure_dirs()
    doc = RawDoc(source_page_id=pid, title=title, body_markdown="본문", updated_at="2024-01-01",
                 source_url=f"https://cf/{pid}", author="홍길동")
    store.write_raw(pid, "s" + pid, dump_raw(doc))
    a = AnalysisResult(source_page_id=pid, title_normalized=title, business=business,
                       system=system, year=year, summary="요약", labels=[],
                       menu_path=menu_path or [])
    store.write_json(store.analysis_path(pid), a)


def _write_clusters(store, clusters):
    store.clusters_path.write_text(
        RootModel[list[Cluster]](clusters).model_dump_json(), encoding="utf-8"
    )


def test_build_produces_pages_tree_and_labels(tmp_path):
    store = Store(tmp_path / "vault")
    # 온톨로지 메뉴 경로 기반 배치
    _seed(store, "1", "구매관리", 2024, "구매 정산 절차",
          menu_path=["Platform", "VMware", "Operation Guide"])
    _seed(store, "2", "구매관리", 2024, "구매 정산 사본",
          menu_path=["Platform", "VMware", "Operation Guide"])
    _seed(store, "3", "배포관리", 2023, "배포 체크리스트",
          menu_path=["Infrastructure", "Storage"])
    _write_clusters(store, [
        Cluster(business="구매관리", year=2024, members=[
            ClusterMember(source_page_id="1", role="canonical"),
            ClusterMember(source_page_id="2", role="duplicate", similarity=0.95),
        ]),
        Cluster(business="배포관리", year=2023, members=[
            ClusterMember(source_page_id="3", role="canonical"),
        ]),
    ])

    pages = build.run(Config(), store)
    assert len(pages) == 3

    assert (store.build_dir / "pages.json").exists()
    assert (store.build_dir / "tree.json").exists()
    assert (store.build_dir / "1.md").exists()
    assert store.labels_path.exists()

    by_id = {p.source_page_id: p for p in pages}
    assert "상태/정본" in by_id["1"].labels
    assert "상태/중복후보" in by_id["2"].labels
    assert by_id["1"].menu_path == ["Platform", "VMware", "Operation Guide"]
    assert by_id["1"].properties.owner == "홍길동"

    md = (store.build_dir / "1.md").read_text(encoding="utf-8")
    assert "Page Properties" in md

    # 메뉴 트리: Platform>VMware>Operation Guide 아래 문서 1,2 / Infrastructure>Storage 아래 3
    from reconf.models import BuildTree

    tree = BuildTree.model_validate_json((store.build_dir / "tree.json").read_text("utf-8"))
    roots = {r.name: r for r in tree.roots}
    assert set(roots) == {"Platform", "Infrastructure"}
    vmware = roots["Platform"].children[0].children[0]
    assert vmware.name == "Operation Guide"
    assert set(vmware.page_ids) == {"1", "2"}
    assert vmware.node_key == "menu:Platform/VMware/Operation Guide"
    assert roots["Infrastructure"].children[0].page_ids == ["3"]


def test_build_labels_canonical_dedup(tmp_path):
    """표기가 흔들린 업무명이 canonical 하나로 통일된다."""
    store = Store(tmp_path / "vault")
    _seed(store, "1", "구매관리", 2024, "A")
    _seed(store, "2", "구매 관리", 2024, "B")  # 공백 차이
    _write_clusters(store, [
        Cluster(business="구매관리", year=2024, members=[
            ClusterMember(source_page_id="1", role="canonical"),
        ]),
        Cluster(business="구매 관리", year=2024, members=[
            ClusterMember(source_page_id="2", role="canonical"),
        ]),
    ])
    build.run(Config(), store)
    from reconf.labels import load_registry

    reg = load_registry(store)
    biz = [e for e in reg.entries if e.namespace == "업무"]
    assert len(biz) == 1  # '구매관리' 하나로 통일
