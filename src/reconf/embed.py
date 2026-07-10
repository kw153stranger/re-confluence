"""TEI 임베딩 클라이언트 + 임베딩 캐시 (구현설계 §6.3, §8).

embed.ensure(page_id, text)로 embeddings/<page_id>.json을 재사용/생성한다.
M0: 인터페이스 스텁. 실제 TEI 호출은 M2.
"""

from __future__ import annotations

from .config import EmbeddingsCfg
from .logging_setup import get_logger
from .models import EmbeddingRecord
from .store import Store, content_hash

log = get_logger("embed")


def ensure(store: Store, cfg: EmbeddingsCfg, page_id: str, text: str) -> EmbeddingRecord:
    """캐시가 유효하면 로드, 아니면 (M2에서) TEI로 생성 후 저장.

    M0: 캐시 조회·해시 검증 로직만. content_hash 불일치 시 NotImplementedError.
    """
    path = store.embedding_path(page_id)
    h = content_hash(text)
    if cfg.cache and store.exists(path):
        rec = store.read_json(path, EmbeddingRecord)
        if rec.content_hash == h:
            return rec  # 재사용 (재계산 생략)
    raise NotImplementedError("TEI 임베딩 생성은 M2에서 구현됩니다.")
