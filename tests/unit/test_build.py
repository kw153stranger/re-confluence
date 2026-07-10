"""Build 검증 — IA 트리·Page Properties·라벨 canonical·pages.json."""

from pydantic import RootModel

from reconf import build
from reconf.config import Config
from reconf.markdown import dump_raw
from reconf.models import AnalysisResult, Cluster, ClusterMember, RawDoc
from reconf.store import Store


def _seed(store, pid, business, year, title, system="ERP"):
    store.ensure_dirs()
    doc = RawDoc(source_page_id=pid, title=title, body_markdown="본문", updated_at="2024-01-01",
                 source_url=f"https://cf/{pid}", author="홍길동")
    store.write_raw(pid, "s" + pid, dump_raw(doc))
    a = AnalysisResult(source_page_id=pid, title_normalized=title, business=business,
                       system=system, year=year, summary="요약", labels=[])
    store.write_json(store.analysis_path(pid), a)


def _write_clusters(store, clusters):
    store.clusters_path.write_text(
        RootModel[list[Cluster]](clusters).model_dump_json(), encoding="utf-8"
    )


def test_build_produces_pages_tree_and_labels(tmp_path):
    store = Store(tmp_path / "vault")
    _seed(store, "1", "구매관리", 2024, "구매 정산 절차")
    _seed(store, "2", "구매관리", 2024, "구매 정산 사본")
    _seed(store, "3", "배포관리", 2023, "배포 체크리스트")
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

    # pages.json / tree.json 생성
    assert (store.build_dir / "pages.json").exists()
    assert (store.build_dir / "tree.json").exists()
    assert (store.build_dir / "1.md").exists()
    assert store.labels_path.exists()

    by_id = {p.source_page_id: p for p in pages}
    # 정본/중복 상태 라벨
    assert "상태/정본" in by_id["1"].labels
    assert "상태/중복후보" in by_id["2"].labels
    assert "업무/구매관리" in by_id["1"].labels
    # Page Properties
    assert by_id["1"].properties.owner == "홍길동"
    assert by_id["1"].properties.source == "https://cf/1"

    # 페이지 md에 Page Properties 섹션 포함
    md = (store.build_dir / "1.md").read_text(encoding="utf-8")
    assert "Page Properties" in md and "구매관리" in md


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
