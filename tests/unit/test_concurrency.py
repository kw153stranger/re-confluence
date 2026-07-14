"""단계 내부 동시성 검증 — Export/Analyze 병렬 처리·오류 격리·순서 보존."""

import json

from reconf import analyze, export
from reconf.concurrency import run_concurrent
from reconf.config import Config
from reconf.markdown import dump_raw, parse_raw
from reconf.models import RawDoc
from reconf.store import Store


def test_run_concurrent_preserves_order():
    assert run_concurrent(lambda x: x * 2, [1, 2, 3, 4], workers=4) == [2, 4, 6, 8]


def test_run_concurrent_sequential_when_single_worker():
    assert run_concurrent(lambda x: x + 1, [1, 2, 3], workers=1) == [2, 3, 4]


# --- Export 병렬 ---
def _page(pid):
    return {
        "id": pid, "title": f"문서{pid}", "body": {"storage": {"value": f"<p>{pid}</p>"}},
        "version": {"when": f"2024-06-{int(pid):02d}", "by": {"displayName": "u"}},
        "history": {"createdDate": "2024-01-01"},
        "metadata": {"labels": {"results": []}}, "_links": {"webui": f"/p/{pid}"},
    }


class FakeConf:
    """스레드세이프(불변 dict 조회)."""
    base_url = "https://cf"

    def __init__(self, n, fail_ids=()):
        self.p = {str(i): _page(str(i)) for i in range(1, n + 1)}
        self.fail = set(fail_ids)

    def list_pages(self, space):
        return [{"id": k} for k in self.p]

    def get_page(self, pid):
        if pid in self.fail:
            raise RuntimeError("boom")
        return self.p[pid]

    def get_attachments(self, pid):
        return []

    def download_attachment(self, a):
        return b""


def test_export_concurrent_saves_all(tmp_path):
    store = Store(tmp_path / "vault")
    cfg = Config()
    cfg.concurrency.export = 4
    saved = export.run(cfg, store, client=FakeConf(20))
    assert len(saved) == 20
    assert len(store.list_raw()) == 20


def test_export_concurrent_isolates_failure(tmp_path):
    store = Store(tmp_path / "vault")
    cfg = Config()
    cfg.concurrency.export = 4
    saved = export.run(cfg, store, client=FakeConf(10, fail_ids={"3", "7"}))
    assert len(saved) == 8  # 2건 실패 격리, 나머지 저장
    assert len(store.list_raw()) == 8


# --- Analyze 병렬 ---
class StatelessLLM:
    """입력 page_id 기반 응답(스레드세이프)."""

    def chat(self, system, user):
        line = next(x for x in user.splitlines() if x.startswith("source_page_id"))
        pid = line.split()[-1]
        return json.dumps(
            {"source_page_id": pid, "title_normalized": "t", "business": "업무A",
             "system": "S", "year": 2024, "labels": [], "summary": "y",
             "confidence": {"business": 0.9, "project": 0.9, "system": 0.9, "year": 0.9}},
            ensure_ascii=False,
        )


def test_analyze_concurrent_matches_all(tmp_path):
    store = Store(tmp_path / "vault")
    store.ensure_dirs()
    for i in range(1, 16):
        store.write_raw(str(i), f"s{i}", dump_raw(RawDoc(source_page_id=str(i), title=f"T{i}")))
    cfg = Config()
    cfg.concurrency.analyze = 4
    results = analyze.run(cfg, store, client=StatelessLLM())
    assert len(results) == 15
    assert len(store.list_analysis()) == 15
    # 각 결과의 source_page_id가 원본과 일치(뒤섞임 없음)
    ids = {parse_raw(p.read_text("utf-8")).source_page_id for p in store.list_raw()}
    got = {store.read_json(p, type(results[0])).source_page_id for p in store.list_analysis()}
    assert got == ids
