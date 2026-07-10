"""Upload 검증 — fake writer로 멱등 upsert·승인 필터·부분 실패."""

from pydantic import RootModel

from reconf import upload
from reconf.config import Config
from reconf.models import (
    BuildPage,
    PageProperties,
    ReviewDecision,
)
from reconf.store import Store


class FakeWriter:
    def __init__(self):
        self.pages: dict[str, str] = {}  # source_id -> target_id
        self.spaces: list[str] = []
        self._seq = 0

    def ensure_space(self, key, name):
        self.spaces.append(key)

    def upsert_page(self, space, source_page_id, title, body_md, parent_id, labels):
        if source_page_id in self.pages:
            return self.pages[source_page_id], "updated"
        self._seq += 1
        tid = f"t{self._seq}"
        self.pages[source_page_id] = tid
        return tid, "created"


def _seed_build(store, pages):
    store.ensure_dirs()
    (store.build_dir / "pages.json").write_text(
        RootModel[list[BuildPage]](pages).model_dump_json(), encoding="utf-8"
    )


def _page(pid, business="구매관리"):
    return BuildPage(
        source_page_id=pid, title=f"제목{pid}", business=business, year=2024, role="canonical",
        labels=["업무/구매관리", "연도/2024"],
        properties=PageProperties(business=business, source=f"https://cf/{pid}"),
        summary="요약",
    )


def _approve(store, ids):
    decisions = [ReviewDecision(source_page_id=i, status="approved") for i in ids]
    store.write_json(store.review_path, RootModel[list[ReviewDecision]](decisions))


def test_upload_only_approved_and_idempotent(tmp_path):
    store = Store(tmp_path / "vault")
    _seed_build(store, [_page("1"), _page("2")])
    _approve(store, ["1"])  # 1만 승인

    w = FakeWriter()
    results = upload.run(Config(), store, target_space="RE", writer=w)
    by_id = {r.source_page_id: r for r in results}
    assert by_id["1"].status == "created"
    assert by_id["2"].status == "skipped"  # 미승인
    assert store.review_path.exists()
    assert (store.root / "upload.log").exists()

    # 재실행 → 멱등: 중복 생성 없이 updated
    results2 = upload.run(Config(), store, target_space="RE", writer=w)
    assert {r.source_page_id: r.status for r in results2}["1"] == "updated"
    # 승인 1건에 대해 target 페이지는 1개(+업무 index)만 존재
    assert len([k for k in w.pages if not k.startswith("index-")]) == 1


def test_upload_partial_failure_isolated(tmp_path):
    store = Store(tmp_path / "vault")
    _seed_build(store, [_page("1"), _page("2")])
    _approve(store, ["1", "2"])

    class FlakyWriter(FakeWriter):
        def upsert_page(self, space, source_page_id, title, body_md, parent_id, labels):
            if source_page_id == "2":
                raise RuntimeError("boom")
            return super().upsert_page(space, source_page_id, title, body_md, parent_id, labels)

    results = upload.run(Config(), store, target_space="RE", writer=FlakyWriter())
    status = {r.source_page_id: r.status for r in results}
    assert status["1"] == "created"
    assert status["2"] == "failed"
