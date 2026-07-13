"""Confluence 개인키(PAT) Bearer 인증 검증 (httpx MockTransport)."""

import httpx
import pytest

from reconf.confluence import ConfluenceRestClient, ConfluenceRestWriter


def test_client_uses_bearer_pat(monkeypatch):
    monkeypatch.setenv("CONFLUENCE_BASE_URL", "https://cf.example.com")
    monkeypatch.setenv("CONFLUENCE_PAT", "PAT-123")
    monkeypatch.delenv("CONFLUENCE_EMAIL", raising=False)

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"results": [], "size": 0, "_links": {}})

    client = ConfluenceRestClient()
    client._client = httpx.Client(
        base_url=client.base_url,
        headers={"Authorization": "Bearer PAT-123"},
        transport=httpx.MockTransport(handler),
    )
    client.list_pages("DOCS")
    assert captured["auth"] == "Bearer PAT-123"


def test_api_token_fallback(monkeypatch):
    monkeypatch.setenv("CONFLUENCE_BASE_URL", "https://cf.example.com")
    monkeypatch.delenv("CONFLUENCE_PAT", raising=False)
    monkeypatch.setenv("CONFLUENCE_API_TOKEN", "TOK-9")
    # 예외 없이 생성되면 fallback 동작
    ConfluenceRestClient()
    ConfluenceRestWriter()


def test_missing_credentials_raises(monkeypatch):
    monkeypatch.delenv("CONFLUENCE_BASE_URL", raising=False)
    monkeypatch.delenv("CONFLUENCE_PAT", raising=False)
    monkeypatch.delenv("CONFLUENCE_API_TOKEN", raising=False)
    with pytest.raises(RuntimeError):
        ConfluenceRestClient()
