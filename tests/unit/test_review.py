"""Review 검증 — 큐 우선순위·결정 반영·라벨 후보 승인."""

from pydantic import RootModel

from reconf import review
from reconf.config import Config
from reconf.markdown import dump_raw
from reconf.models import (
    AnalysisResult,
    Cluster,
    ClusterMember,
    Confidence,
    LabelEntry,
    LabelRegistry,
    RawDoc,
    ReviewDecision,
)
from reconf.store import Store


def _seed(store, pid, conf, title="t", business="구매관리"):
    store.ensure_dirs()
    store.write_raw(pid, "s" + pid, dump_raw(RawDoc(source_page_id=pid, title=title)))
    a = AnalysisResult(
        source_page_id=pid, title_normalized=title, business=business,
        confidence=Confidence(business=conf, project=conf, system=conf, year=conf),
    )
    store.write_json(store.analysis_path(pid), a)


def test_export_queue_orders_lowconf_and_dupes_first(tmp_path):
    store = Store(tmp_path / "vault")
    _seed(store, "1", 0.95)  # 고신뢰 정본
    _seed(store, "2", 0.99)  # 고신뢰지만 중복
    _seed(store, "3", 0.40)  # 저신뢰 정본
    store.clusters_path.write_text(
        RootModel[list[Cluster]]([
            Cluster(business="구매관리", year=2024, members=[
                ClusterMember(source_page_id="1", role="canonical"),
                ClusterMember(source_page_id="2", role="duplicate", similarity=0.95),
            ]),
            Cluster(business="구매관리", year=2023, members=[
                ClusterMember(source_page_id="3", role="canonical"),
            ]),
        ]).model_dump_json(), encoding="utf-8"
    )

    review.run(Config(), store, export_queue=True)
    queue_path = store.root / "review_queue.json"
    assert queue_path.exists()
    from reconf.models import ReviewQueueItem

    items = RootModel[list[ReviewQueueItem]].model_validate_json(
        queue_path.read_text("utf-8")
    ).root
    # 중복(2)이 먼저, 그 다음 저신뢰(3), 마지막 고신뢰 정본(1)
    assert items[0].source_page_id == "2"
    assert items[1].source_page_id == "3"
    assert items[2].source_page_id == "1"


def test_apply_writes_review_and_approves_labels(tmp_path):
    store = Store(tmp_path / "vault")
    store.ensure_dirs()
    # 후보 라벨이 있는 레지스트리
    entry = LabelEntry(namespace="업무", canonical="구매관리", status="candidate")
    store.write_json(store.labels_path, LabelRegistry(entries=[entry]))
    decisions = [ReviewDecision(source_page_id="1", status="approved", reviewer="qa")]
    apply_file = tmp_path / "decisions.json"
    apply_file.write_text(
        RootModel[list[ReviewDecision]](decisions).model_dump_json(), encoding="utf-8"
    )

    review.run(Config(), store, apply=str(apply_file))
    assert store.review_path.exists()
    from reconf.labels import load_registry

    reg = load_registry(store)
    assert reg.entries[0].status == "approved"  # 후보 → 승인
