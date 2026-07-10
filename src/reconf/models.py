"""pydantic 데이터 모델 — vault 중간 산출물의 직렬화 계약.

구현설계 §4 / 기획서 §4.2 Analyze JSON 스키마를 그대로 고정한다.
`store.py`는 이 모델로만 직렬화/역직렬화한다.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# 라벨 네임스페이스 (기획서 §5.2)
LABEL_NAMESPACES: tuple[str, ...] = ("업무", "시스템", "연도", "상태")

# 문서 상태값 (기획서 §5.3 / §6)
STATUS_CANONICAL = "정본"
STATUS_DUPLICATE = "중복후보"


class Confidence(BaseModel):
    """필드별 분류 신뢰도 (0~1). 0.7 미만은 검수 우선 대상."""

    business: float = 0.0
    project: float = 0.0
    system: float = 0.0
    year: float = 0.0


class AnalysisResult(BaseModel):
    """Analyze 산출물 — analysis/<page_id>.json"""

    source_page_id: str
    title_normalized: str
    business: str | None = None
    project: str | None = None
    system: str | None = None
    year: int | None = None
    month: int | None = None
    labels: list[str] = Field(default_factory=list)  # 예: "업무/구매관리"
    summary: str = ""
    related_pages: list[str] = Field(default_factory=list)
    duplicate_of: str | None = None
    confidence: Confidence = Field(default_factory=Confidence)


class ClusterMember(BaseModel):
    source_page_id: str
    role: str  # "canonical" | "duplicate" | "related"
    similarity: float | None = None  # duplicate일 때 0~1


class Cluster(BaseModel):
    business: str
    year: int | None = None
    members: list[ClusterMember] = Field(default_factory=list)


class ReviewDecision(BaseModel):
    source_page_id: str
    status: str = "pending"  # "approved" | "rejected" | "pending"
    overrides: dict = Field(default_factory=dict)  # 사람이 수정한 필드
    reviewer: str | None = None


class PageProperties(BaseModel):
    """기획서 §5.3 표준 필드."""

    business: str
    owner: str | None = None
    system: str | None = None
    year: int | None = None
    status: str = STATUS_CANONICAL
    source: str = ""


class EmbeddingRecord(BaseModel):
    """embeddings/<page_id>.json — 재사용 캐시 (구현설계 §6.3)."""

    source_page_id: str
    model: str
    dim: int
    content_hash: str  # raw 본문 해시 → 변경 시에만 재계산
    vector: list[float] = Field(default_factory=list)


class LabelEntry(BaseModel):
    """labels.json 항목 (구현설계 §6.4a)."""

    namespace: str  # "업무" | "시스템" | "연도" | "상태"
    canonical: str  # 대표 라벨 (예: "구매관리")
    aliases: list[str] = Field(default_factory=list)  # 유사중복 → canonical 매핑
    status: str = "approved"  # "approved" | "candidate"
    count: int = 0  # 사용 문서 수


class LabelRegistry(BaseModel):
    """전역 라벨 마스터."""

    entries: list[LabelEntry] = Field(default_factory=list)
