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


class RawDoc(BaseModel):
    """Export 산출물 — raw/<page_id>__<slug>.md 의 frontmatter + 본문 (기획서 §4.1)."""

    source_page_id: str
    source_url: str = ""
    title: str = ""
    author: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    original_labels: list[str] = Field(default_factory=list)
    attachments: list[str] = Field(default_factory=list)
    path: list[str] = Field(default_factory=list)  # 기존 메뉴 경로(ancestors 제목)
    body_markdown: str = ""
    body_storage: str = ""  # 원본 Confluence storage(XHTML) — 업로드 시 재사용


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
    # 메뉴 개선: 사전 기반 메타데이터(자유 생성 금지) — docs/메뉴구조개선방안.md
    domain: str | None = None  # Infrastructure/Cloud/Database/Platform/Security/Network
    technology: str | None = None  # VMware/OpenShift/Kubernetes/Linux/Oracle/Storage/Backup
    menu_type: str | None = None  # Guide/Runbook/Architecture/Reference …
    lifecycle: str | None = None  # Planning/Build/Operation/Migration/Retire
    menu_path: list[str] = Field(default_factory=list)  # 추천 메뉴 경로(온톨로지+메타+Path)


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


class BuildPage(BaseModel):
    """Build 산출물 페이지 메타 — build/<page_id>.md 에 대응."""

    source_page_id: str
    title: str
    business: str
    year: int | None = None
    role: str = "canonical"  # canonical | duplicate | related
    labels: list[str] = Field(default_factory=list)
    properties: PageProperties
    summary: str = ""
    body_markdown: str = ""  # 원문(Markdown) — fallback
    body_storage: str = ""  # 원문(Confluence storage XHTML) — 업로드 본문


class YearGroup(BaseModel):
    year: int | None = None
    page_ids: list[str] = Field(default_factory=list)


class BusinessGroup(BaseModel):
    """업무 → {개요, 작업실적 → 연도 → 문서} 3단계 IA."""

    business: str
    business_page_id: str  # 업무 루트 (biz-<업무>)
    overview_page_id: str  # 개요 (overview-<업무>)
    worklog_page_id: str  # 작업실적 (worklog-<업무>)
    overview_storage: str = ""  # 개요 페이지 본문(storage)
    years: list[YearGroup] = Field(default_factory=list)  # 작업실적 하위 연도


class BuildTree(BaseModel):
    """업무 중심 Page Tree — build/tree.json."""

    businesses: list[BusinessGroup] = Field(default_factory=list)


class UploadResult(BaseModel):
    """Upload 결과 — upload.log (성공/실패 + 멱등 키 매핑)."""

    source_page_id: str
    status: str  # created | updated | failed | skipped
    target_page_id: str | None = None
    error: str | None = None


class ReviewQueueItem(BaseModel):
    """검수 큐 항목 — review_queue.json (저신뢰·중복 우선)."""

    source_page_id: str
    title: str
    business: str | None = None
    year: int | None = None
    labels: list[str] = Field(default_factory=list)
    min_confidence: float = 1.0
    role: str = "canonical"
    duplicate_of: str | None = None
