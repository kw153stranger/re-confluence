"""Upload 검증 — fake writer로 멱등 upsert·승인 필터·부분 실패."""

from pydantic import RootModel

from reconf import build, upload
from reconf.config import Config
from reconf.markdown import dump_raw
from reconf.models import (
    AnalysisResult,
    BuildPage,
    Cluster,
    ClusterMember,
    PageProperties,
    RawDoc,
    ReviewDecision,
)
from reconf.store import Store

_STRUCT_PREFIXES = ("menu:",)


class FakeWriter:
    def __init__(self):
        self.pages: dict[str, str] = {}  # source_id -> target_id
        self.spaces: list[str] = []
        self.bodies: dict[str, str] = {}  # source_id -> uploaded body(storage)
        self.parents: dict[str, str | None] = {}  # source_id -> parent target id
        self._seq = 0

    def ensure_space(self, key, name):
        self.spaces.append(key)

    def upsert_page(self, space, source_page_id, title, body_storage, parent_id, labels):
        self.bodies[source_page_id] = body_storage
        self.parents[source_page_id] = parent_id
        if source_page_id in self.pages:
            return self.pages[source_page_id], "updated"
        self._seq += 1
        tid = f"t{self._seq}"
        self.pages[source_page_id] = tid
        return tid, "created"

    def doc_keys(self):
        return [k for k in self.pages if not k.startswith(_STRUCT_PREFIXES)]


def _seed_build(store, pages):
    store.ensure_dirs()
    (store.build_dir / "pages.json").write_text(
        RootModel[list[BuildPage]](pages).model_dump_json(), encoding="utf-8"
    )


def _page(pid, business="구매관리", body_storage="<p>원본 본문 내용</p>", menu_path=None):
    return BuildPage(
        source_page_id=pid, title=f"제목{pid}", business=business, year=2024, role="canonical",
        labels=["업무/구매관리", "연도/2024"],
        properties=PageProperties(business=business, system="ERP", year=2024,
                                  source=f"https://cf/{pid}"),
        summary="요약", body_storage=body_storage,
        menu_path=menu_path or ["구매관리"],
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
    # 승인 1건 → 문서 페이지는 1개만(구조 페이지 제외)
    assert w.doc_keys() == ["1"]


def test_upload_builds_menu_hierarchy(tmp_path):
    """온톨로지 메뉴 경로(menu_path) 기반 부모 관계 검증."""
    store = Store(tmp_path / "vault")
    store.ensure_dirs()
    doc = RawDoc(source_page_id="1", title="VMware 운영 가이드", updated_at="2024-01-01",
                 source_url="https://cf/1", author="홍길동")
    store.write_raw("1", "s1", dump_raw(doc))
    store.write_json(store.analysis_path("1"), AnalysisResult(
        source_page_id="1", title_normalized="VMware 운영 가이드", business="가상화",
        summary="운영", menu_path=["Platform", "VMware", "Operation Guide"]))
    store.clusters_path.write_text(RootModel[list[Cluster]]([
        Cluster(business="가상화", year=2024,
                members=[ClusterMember(source_page_id="1", role="canonical")]),
    ]).model_dump_json(), encoding="utf-8")
    build.run(Config(), store)
    _approve(store, ["1"])

    w = FakeWriter()
    upload.run(Config(), store, target_space="RE", writer=w)

    # 메뉴 노드 생성 확인
    for key in ("menu:Platform", "menu:Platform/VMware", "menu:Platform/VMware/Operation Guide"):
        assert key in w.pages
    # 부모 체인: 문서 → Operation Guide → VMware → Platform → (루트)
    assert w.parents["1"] == w.pages["menu:Platform/VMware/Operation Guide"]
    assert w.parents["menu:Platform/VMware/Operation Guide"] == w.pages["menu:Platform/VMware"]
    assert w.parents["menu:Platform/VMware"] == w.pages["menu:Platform"]
    assert w.parents["menu:Platform"] is None


def test_uploaded_body_includes_original_content_and_properties(tmp_path):
    store = Store(tmp_path / "vault")
    _seed_build(store, [_page("1", body_storage="<h2>절차</h2><p>원본 상세 내용</p>")])
    _approve(store, ["1"])
    w = FakeWriter()
    upload.run(Config(), store, target_space="RE", writer=w)
    body = w.bodies["1"]
    # 원문 동일 포함
    assert "<h2>절차</h2><p>원본 상세 내용</p>" in body
    # Page Properties 매크로 + 표준 필드
    assert 'ac:name="details"' in body
    assert "업무명" in body and "구매관리" in body
    assert "시스템" in body and "ERP" in body


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
