"""AnalysisResult 등 핵심 모델이 기획서 스키마와 일치하는지 검증."""

from reconf.models import (
    LABEL_NAMESPACES,
    AnalysisResult,
    Confidence,
    EmbeddingRecord,
    LabelRegistry,
)


def test_analysis_roundtrip():
    data = {
        "source_page_id": "123456",
        "title_normalized": "구매 정산 절차",
        "business": "구매관리",
        "project": "정산 자동화",
        "system": "ERP",
        "year": 2024,
        "month": 3,
        "labels": ["업무/구매관리", "시스템/ERP", "연도/2024"],
        "summary": "구매 정산 절차 정의.",
        "related_pages": ["123457"],
        "duplicate_of": None,
        "confidence": {"business": 0.92, "project": 0.71, "system": 0.88, "year": 0.99},
    }
    a = AnalysisResult.model_validate(data)
    assert a.source_page_id == "123456"
    assert a.confidence.business == 0.92
    # 직렬화 후 재파싱 동일성
    assert AnalysisResult.model_validate_json(a.model_dump_json()) == a


def test_analysis_allows_nulls_and_defaults():
    a = AnalysisResult(source_page_id="1", title_normalized="t")
    assert a.business is None
    assert a.labels == []
    assert isinstance(a.confidence, Confidence)


def test_label_namespaces():
    assert LABEL_NAMESPACES == ("업무", "시스템", "연도", "상태")


def test_embedding_record():
    e = EmbeddingRecord(source_page_id="1", model="BAAI/bge-m3", dim=1024, content_hash="abc")
    assert e.dim == 1024
    assert e.vector == []


def test_label_registry_default_empty():
    assert LabelRegistry().entries == []
