"""Cluster 검증 — fake Embedder + 중복 탐지·정본 선정·그룹핑."""

from reconf import cluster
from reconf.config import Config
from reconf.markdown import dump_raw
from reconf.models import AnalysisResult, RawDoc
from reconf.store import Store


class FakeEmbedder:
    """page_id별 고정 벡터를 반환하도록 텍스트→벡터 매핑을 흉내."""

    def __init__(self, mapping):
        self._mapping = mapping  # text -> vector

    def embed(self, texts):
        return [self._mapping[t] for t in texts]


def _seed(store: Store, pid: str, business, year, title, body):
    store.ensure_dirs()
    doc = RawDoc(source_page_id=pid, title=title, body_markdown=body, updated_at="2024-01-0" + pid)
    store.write_raw(pid, "s" + pid, dump_raw(doc))
    a = AnalysisResult(
        source_page_id=pid, title_normalized=title, business=business, year=year, summary=body
    )
    store.write_json(store.analysis_path(pid), a)


def test_duplicate_detected_and_canonical_latest(tmp_path):
    store = Store(tmp_path / "vault")
    # 두 문서: 거의 동일(높은 코사인) → 중복. pid=2 가 수정일 늦음 → 정본.
    _seed(store, "1", "구매관리", 2024, "구매 정산 절차", "정산 본문 A")
    _seed(store, "2", "구매관리", 2024, "구매 정산 절차 (사본)", "정산 본문 B")
    _seed(store, "3", "배포관리", 2024, "배포 체크리스트", "배포 본문")

    vecs = {
        "정산 본문 A": [1.0, 0.0, 0.0],
        "정산 본문 B": [0.99, 0.01, 0.0],  # 1과 매우 유사
        "배포 본문": [0.0, 1.0, 0.0],
    }
    clusters = cluster.run(Config(), store, embedder=FakeEmbedder(vecs))

    by_biz = {c.business: c for c in clusters}
    assert set(by_biz) == {"구매관리", "배포관리"}

    gm = by_biz["구매관리"].members
    roles = {m.source_page_id: m.role for m in gm}
    assert roles["2"] == "canonical"  # 수정일 최신
    assert roles["1"] == "duplicate"
    dup = next(m for m in gm if m.role == "duplicate")
    assert dup.similarity is not None and dup.similarity >= 0.9

    assert store.clusters_path.exists()


def test_normalize_task_merges_spacing_variants():
    from reconf.cluster import normalize_task

    assert normalize_task("SSL  적용") == "SSL 적용"
    assert normalize_task(" SSL 적용 ") == "SSL 적용"
    assert normalize_task(None) == "미분류"


def test_no_duplicate_when_dissimilar(tmp_path):
    store = Store(tmp_path / "vault")
    _seed(store, "1", "구매관리", 2024, "발주 가이드", "발주 내용")
    _seed(store, "2", "구매관리", 2024, "재고 실사 절차", "완전히 다른 내용")
    vecs = {"발주 내용": [1.0, 0.0], "완전히 다른 내용": [0.0, 1.0]}
    clusters = cluster.run(Config(), store, embedder=FakeEmbedder(vecs))
    members = clusters[0].members
    assert sum(1 for m in members if m.role == "duplicate") == 0
