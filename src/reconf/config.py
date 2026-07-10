"""설정 로더 — config.yaml + 환경변수 병합 (구현설계 §7).

비밀값(Confluence 토큰 등)은 파일이 아닌 환경변수로만 주입한다.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class SourceCfg(BaseModel):
    space: str = "DOCS"
    filter: dict = Field(default_factory=dict)


class TargetCfg(BaseModel):
    space: str = "RE-ARCHIVE"


class LLMCfg(BaseModel):
    endpoint: str = "http://localhost:8000/v1"  # vLLM/Ollama OpenAI 호환
    model: str = "qwen3-30b-a3b"
    max_retries: int = 3
    chunk_chars: int = 8000  # 본문이 이보다 길면 청크 요약 후 통합


class EmbeddingsCfg(BaseModel):
    provider: str = "tei"  # HuggingFace Text Embeddings Inference
    endpoint: str = "http://localhost:8080"  # TEI 서버 (POST /embed)
    model: str = "BAAI/bge-m3"
    dim: int = 1024
    batch_size: int = 32
    normalize: bool = True
    timeout_s: int = 30
    cache: bool = True  # embeddings/<page_id>.json 재사용


class ClusterCfg(BaseModel):
    sim_threshold: float = 0.90


class LabelsCfg(BaseModel):
    namespaces: list[str] = Field(default_factory=lambda: ["업무", "시스템", "연도", "상태"])
    registry: str = "labels.json"
    merge_fuzzy_threshold: int = 90  # rapidfuzz 0~100
    merge_embed_threshold: float = 0.92


class DBCfg(BaseModel):
    """M6 저장/벡터 백엔드 (구현설계 §12.2, §12.6)."""

    backend: str = "file"  # "file" | "postgres"
    dsn: str = ""  # postgres 연결 문자열(비밀은 환경변수 권장)


class WebCfg(BaseModel):
    """M6 웹서비스 (구현설계 §12)."""

    host: str = "127.0.0.1"
    port: int = 8000


class Config(BaseModel):
    source: SourceCfg = Field(default_factory=SourceCfg)
    target: TargetCfg = Field(default_factory=TargetCfg)
    llm: LLMCfg = Field(default_factory=LLMCfg)
    embeddings: EmbeddingsCfg = Field(default_factory=EmbeddingsCfg)
    cluster: ClusterCfg = Field(default_factory=ClusterCfg)
    labels: LabelsCfg = Field(default_factory=LabelsCfg)
    db: DBCfg = Field(default_factory=DBCfg)
    web: WebCfg = Field(default_factory=WebCfg)
    vault: str = "./vault"

    @classmethod
    def load(cls, path: str | Path | None = None) -> Config:
        """config.yaml을 로드한다. 파일이 없으면 기본값으로 생성한다."""
        if path is None:
            return cls()
        p = Path(path)
        if not p.exists():
            return cls()
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        return cls.model_validate(data)
