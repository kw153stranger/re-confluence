"""TEI 임베딩 클라이언트 + 임베딩 캐시 (구현설계 §6.3, §8).

embed.ensure(store, cfg, page_id, text, embedder)로
embeddings/<page_id>.json 을 재사용(content_hash 일치)하거나 생성/저장한다.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import httpx

from .config import EmbeddingsCfg
from .logging_setup import get_logger
from .models import EmbeddingRecord
from .store import Store, content_hash

log = get_logger("embed")


@runtime_checkable
class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        """문장 리스트 → 임베딩 벡터 리스트."""
        ...


def _l2_normalize(vec: list[float]) -> list[float]:
    import math

    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm else vec


class OpenAIEmbedder:
    """OpenAI 호환 임베딩 클라이언트 (POST /embeddings).

    TEI를 OpenAI 호환 모드로 띄우거나 vLLM 등 OpenAI 호환 임베딩 서버를 사용한다.
    엔드포인트는 base(예: http://localhost:8080/v1), 경로는 /embeddings.
    """

    def __init__(self, cfg: EmbeddingsCfg):
        self.cfg = cfg
        headers = {"Authorization": f"Bearer {cfg.api_key}"} if cfg.api_key else {}
        self._client = httpx.Client(
            base_url=cfg.endpoint.rstrip("/"), headers=headers, timeout=cfg.timeout_s
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        bs = self.cfg.batch_size
        for i in range(0, len(texts), bs):
            batch = texts[i : i + bs]
            r = self._client.post("/embeddings", json={"model": self.cfg.model, "input": batch})
            r.raise_for_status()
            data = sorted(r.json()["data"], key=lambda d: d.get("index", 0))
            vecs = [d["embedding"] for d in data]
            if self.cfg.normalize:
                vecs = [_l2_normalize(v) for v in vecs]
            out.extend(vecs)
        return out


# 하위 호환 별칭 (TEI를 OpenAI 호환 모드로 사용)
TEIEmbedder = OpenAIEmbedder


def ensure(
    store: Store,
    cfg: EmbeddingsCfg,
    page_id: str,
    text: str,
    embedder: Embedder,
) -> EmbeddingRecord:
    """캐시가 유효하면 로드, 아니면 임베딩 생성 후 저장 (재계산 최소화)."""
    path = store.embedding_path(page_id)
    h = content_hash(text)
    if cfg.cache and store.exists(path):
        rec = store.read_json(path, EmbeddingRecord)
        if rec.content_hash == h:
            return rec  # 재사용
    vector = embedder.embed([text])[0]
    rec = EmbeddingRecord(
        source_page_id=page_id, model=cfg.model, dim=len(vector), content_hash=h, vector=vector
    )
    store.write_json(path, rec)
    return rec
