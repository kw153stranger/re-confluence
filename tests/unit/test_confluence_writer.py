"""ConfluenceRestWriter 멱등 upsert 검증 — 라벨 조회 + PUT version 처리."""

import json

import httpx

from reconf.confluence import ConfluenceRestWriter


def _writer(monkeypatch, handler):
    monkeypatch.setenv("CONFLUENCE_BASE_URL", "https://cf.example.com")
    monkeypatch.setenv("CONFLUENCE_PAT", "PAT")
    w = ConfluenceRestWriter()
    w._client = httpx.Client(
        base_url=w.base_url,
        headers={"Authorization": "Bearer PAT"},
        transport=httpx.MockTransport(handler),
    )
    return w


def test_create_posts_and_adds_src_label(monkeypatch):
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, req.url.path, req.content))
        if req.url.path == "/rest/api/content/search":
            return httpx.Response(200, json={"results": []})  # 없음 → create
        if req.method == "POST" and req.url.path == "/rest/api/content":
            return httpx.Response(200, json={"id": "1000"})
        if req.url.path == "/rest/api/content/1000/label":
            return httpx.Response(200, json={})
        return httpx.Response(404)

    w = _writer(monkeypatch, handler)
    pid, action = w.upsert_page("RE", "123456", "제목", "<p>본문</p>", None, ["업무/구매관리"])
    assert (pid, action) == ("1000", "created")
    # src-<id> 라벨 부착 확인
    label_call = next(c for c in calls if c[1] == "/rest/api/content/1000/label")
    names = [x["name"] for x in json.loads(label_call[2])]
    assert "src-123456" in names and "업무/구매관리" in names


def test_update_puts_with_incremented_version(monkeypatch):
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/rest/api/content/search":
            # 기존 페이지 존재, 현재 version=3
            return httpx.Response(
                200, json={"results": [{"id": "999", "version": {"number": 3}}]}
            )
        if req.method == "PUT" and req.url.path == "/rest/api/content/999":
            captured["body"] = json.loads(req.content)
            return httpx.Response(200, json={"id": "999"})
        return httpx.Response(404)

    w = _writer(monkeypatch, handler)
    pid, action = w.upsert_page("RE", "123456", "제목", "<p>본문</p>", None, [])
    assert (pid, action) == ("999", "updated")
    # PUT payload에 version.number = 현재+1
    assert captured["body"]["version"] == {"number": 4}
    assert captured["body"]["body"]["storage"]["representation"] == "storage"
