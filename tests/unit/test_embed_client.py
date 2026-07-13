"""OpenAI 호환 임베딩 클라이언트 검증 (httpx MockTransport)."""

import httpx

from reconf.config import EmbeddingsCfg
from reconf.embed import OpenAIEmbedder, TEIEmbedder


def _mock_embedder(cfg: EmbeddingsCfg, captured: list):
    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content)
        captured.append((str(request.url), body, dict(request.headers)))
        # input 순서대로 index 뒤섞어 반환 → 정렬 검증
        vecs = [{"index": i, "embedding": [float(i), 1.0]} for i in range(len(body["input"]))]
        return httpx.Response(200, json={"data": list(reversed(vecs))})

    emb = OpenAIEmbedder(cfg)
    headers = {"Authorization": f"Bearer {cfg.api_key}"} if cfg.api_key else {}
    emb._client = httpx.Client(
        base_url=cfg.endpoint.rstrip("/"),
        transport=httpx.MockTransport(handler),
        headers=headers,
    )
    return emb


def test_posts_to_embeddings_with_model_and_input():
    cap = []
    cfg = EmbeddingsCfg(endpoint="http://tei/v1", model="BAAI/bge-m3", normalize=False)
    emb = _mock_embedder(cfg, cap)
    out = emb.embed(["a", "b"])
    url, body, _ = cap[0]
    assert url.endswith("/embeddings")
    assert body == {"model": "BAAI/bge-m3", "input": ["a", "b"]}
    # index 순 정렬 확인 (0→[0,1], 1→[1,1])
    assert out == [[0.0, 1.0], [1.0, 1.0]]


def test_bearer_header_when_api_key():
    cap = []
    cfg = EmbeddingsCfg(endpoint="http://tei/v1", api_key="SECRET", normalize=False)
    emb = _mock_embedder(cfg, cap)
    emb.embed(["x"])
    _, _, headers = cap[0]
    assert headers.get("authorization") == "Bearer SECRET"


def test_normalize_applies_l2():
    cfg = EmbeddingsCfg(endpoint="http://tei/v1", normalize=True)
    emb = _mock_embedder(cfg, [])
    out = emb.embed(["a"])[0]
    # [0,1] 정규화 → [0,1]; 크기 1 확인
    assert abs(sum(x * x for x in out) - 1.0) < 1e-9


def test_tei_alias_points_to_openai_embedder():
    assert TEIEmbedder is OpenAIEmbedder
