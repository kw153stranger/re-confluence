"""웹 API 검증 — FastAPI TestClient + fake embedder/vectorstore (M6, 설계 §12)."""

from pydantic import RootModel
from starlette.testclient import TestClient

from reconf.config import Config
from reconf.markdown import dump_raw
from reconf.models import (
    AnalysisResult,
    Cluster,
    ClusterMember,
    Confidence,
    EmbeddingRecord,
    LabelEntry,
    LabelRegistry,
    RawDoc,
)
from reconf.store import Store
from reconf.vectorstore import FileVectorStore
from reconf.web.app import create_app


def _seed_analysis(store, pid, conf, business="구매관리", role_dup=False):
    store.ensure_dirs()
    store.write_raw(pid, "s" + pid, dump_raw(RawDoc(source_page_id=pid, title=f"제목{pid}")))
    store.write_json(
        store.analysis_path(pid),
        AnalysisResult(
            source_page_id=pid, title_normalized=f"제목{pid}", business=business,
            confidence=Confidence(business=conf, project=conf, system=conf, year=conf),
        ),
    )


class FakeEmbedder:
    def embed(self, texts):
        return [[1.0, 0.0]] * len(texts)


def _client(store, **kw):
    return TestClient(create_app(store, Config(), **kw))


def test_health(tmp_path):
    store = Store(tmp_path / "vault")
    store.ensure_dirs()
    r = _client(store).get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_review_ui_served(tmp_path):
    store = Store(tmp_path / "vault")
    store.ensure_dirs()
    r = _client(store).get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "검수 승인" in r.text
    assert "/api/review/queue" in r.text  # 프런트가 API를 호출


def test_review_queue_endpoint(tmp_path):
    store = Store(tmp_path / "vault")
    _seed_analysis(store, "1", 0.9)
    _seed_analysis(store, "2", 0.3)
    store.clusters_path.write_text(
        RootModel[list[Cluster]]([
            Cluster(business="구매관리", year=2024, members=[
                ClusterMember(source_page_id="1", role="canonical"),
                ClusterMember(source_page_id="2", role="canonical"),
            ]),
        ]).model_dump_json(), encoding="utf-8"
    )
    r = _client(store).get("/api/review/queue")
    assert r.status_code == 200
    ids = [it["source_page_id"] for it in r.json()]
    assert ids[0] == "2"  # 저신뢰 우선


def test_decisions_and_labels_and_run(tmp_path):
    store = Store(tmp_path / "vault")
    _seed_analysis(store, "1", 0.9)
    store.write_json(
        store.labels_path,
        LabelRegistry(entries=[
            LabelEntry(namespace="업무", canonical="구매관리"),
            LabelEntry(namespace="업무", canonical="구매", status="candidate"),
        ]),
    )
    client = _client(store)

    # 결정 반영
    r = client.post("/api/review/decisions", json=[{"source_page_id": "1", "status": "approved"}])
    assert r.json()["approved"] == 1
    assert store.review_path.exists()

    # 라벨 병합
    r = client.post("/api/labels/resolve",
                    json={"namespace": "업무", "canonical": "구매관리", "alias": "구매"})
    assert r.status_code == 200

    # 미지원 단계 run → failed 상태로 표면화
    r = client.post("/api/runs", json={"stage": "export"})
    assert r.json()["status"] == "failed"

    # 404
    assert client.get("/api/runs/999").status_code == 404


def test_search_endpoint(tmp_path):
    store = Store(tmp_path / "vault")
    _seed_analysis(store, "1", 0.9)
    store.write_json(
        store.embedding_path("1"),
        EmbeddingRecord(source_page_id="1", model="m", dim=2, content_hash="h", vector=[1.0, 0.0]),
    )
    client = TestClient(
        create_app(store, Config(), embedder=FakeEmbedder(), vectorstore=FileVectorStore(store))
    )
    r = client.post("/api/search", json={"query": "정산", "top_k": 5})
    assert r.status_code == 200
    assert r.json()[0]["source_page_id"] == "1"
