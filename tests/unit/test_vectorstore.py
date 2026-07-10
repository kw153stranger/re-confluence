"""FileVectorStore 검색 검증 — 코사인 근접 + 메타 필터."""

from reconf.markdown import dump_raw
from reconf.models import AnalysisResult, EmbeddingRecord, RawDoc
from reconf.store import Store
from reconf.vectorstore import FileVectorStore


def _seed(store, pid, business, year, title, vector):
    store.ensure_dirs()
    store.write_raw(pid, "s" + pid, dump_raw(RawDoc(source_page_id=pid, title=title)))
    store.write_json(
        store.analysis_path(pid),
        AnalysisResult(source_page_id=pid, title_normalized=title, business=business, year=year),
    )
    store.write_json(
        store.embedding_path(pid),
        EmbeddingRecord(source_page_id=pid, model="m", dim=len(vector),
                        content_hash="h", vector=vector),
    )


def test_search_ranks_by_cosine(tmp_path):
    store = Store(tmp_path / "vault")
    _seed(store, "1", "구매관리", 2024, "정산", [1.0, 0.0, 0.0])
    _seed(store, "2", "배포관리", 2024, "배포", [0.0, 1.0, 0.0])
    vs = FileVectorStore(store)
    hits = vs.search([0.9, 0.1, 0.0], top_k=2)
    assert hits[0].source_page_id == "1"
    assert hits[0].score > hits[1].score


def test_search_filters_by_business_and_year(tmp_path):
    store = Store(tmp_path / "vault")
    _seed(store, "1", "구매관리", 2024, "a", [1.0, 0.0])
    _seed(store, "2", "구매관리", 2023, "b", [1.0, 0.0])
    _seed(store, "3", "배포관리", 2024, "c", [1.0, 0.0])
    vs = FileVectorStore(store)
    hits = vs.search([1.0, 0.0], business="구매관리", year=2024)
    assert [h.source_page_id for h in hits] == ["1"]
