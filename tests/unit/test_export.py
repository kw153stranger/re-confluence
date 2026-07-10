"""Export 오케스트레이션 검증 — fake ConfluenceClient 사용."""

from reconf import export
from reconf.config import Config
from reconf.markdown import parse_raw
from reconf.store import Store


def _page(pid: str, title: str, updated: str, body: str) -> dict:
    return {
        "id": pid,
        "title": title,
        "body": {"storage": {"value": body}},
        "version": {"when": updated, "by": {"displayName": "홍길동"}},
        "history": {"createdDate": "2024-01-01"},
        "metadata": {"labels": {"results": [{"name": "구매"}]}},
        "_links": {"webui": f"/pages/{pid}"},
    }


class FakeConfluence:
    base_url = "https://confluence.example.com"

    def __init__(self, pages: dict[str, dict]):
        self._pages = pages

    def list_pages(self, space):
        return [{"id": pid} for pid in self._pages]

    def get_page(self, page_id):
        return self._pages[page_id]

    def get_attachments(self, page_id):
        return [{"title": "정산표.xlsx", "_links": {"download": f"/dl/{page_id}"}}]

    def download_attachment(self, attachment):
        return b"BINARY-DATA"


def test_export_writes_raw(tmp_path):
    store = Store(tmp_path / "vault")
    client = FakeConfluence({"1": _page("1", "구매 정산 절차", "2024-06-02", "<h1>정산</h1>")})
    saved = export.run(Config(), store, client=client)
    assert len(saved) == 1
    raw = store.find_raw("1")
    assert raw is not None
    doc = parse_raw(raw.read_text(encoding="utf-8"))
    assert doc.title == "구매 정산 절차"
    assert doc.source_url == "https://confluence.example.com/pages/1"
    assert doc.attachments == ["정산표.xlsx"]
    assert "정산" in doc.body_markdown
    # 첨부 바이너리 저장 확인
    att = store.raw_dir / "attachments" / "1" / "정산표.xlsx"
    assert att.exists() and att.read_bytes() == b"BINARY-DATA"


def test_export_idempotent_skip_when_unchanged(tmp_path):
    store = Store(tmp_path / "vault")
    pages = {"1": _page("1", "T", "2024-06-02", "<p>x</p>")}
    client = FakeConfluence(pages)
    assert len(export.run(Config(), store, client=client)) == 1
    # 두 번째 실행 — 수정일 동일 → 스킵
    assert len(export.run(Config(), store, client=client)) == 0
    # 수정일 변경 → 재저장
    pages["1"]["version"]["when"] = "2024-07-01"
    assert len(export.run(Config(), store, client=client)) == 1
