"""Analyze 프롬프트 (구현설계 §6.2·§8).

system=출력 스키마·규칙 강제, user=문서 메타+본문.
"""

from __future__ import annotations

from .models import RawDoc

ANALYZE_SYSTEM = """당신은 사내 문서를 분류하는 도우미입니다.
아래 JSON 스키마에 정확히 맞는 **JSON 객체 1개만** 출력하세요. 설명·코드펜스 금지.

{
  "source_page_id": "문자열(입력과 동일)",
  "title_normalized": "핵심만 남긴 제목",
  "business": "최상위 업무명 또는 null",
  "project": "프로젝트명 또는 null",
  "system": "관련 시스템 또는 null",
  "year": 정수 또는 null,
  "month": 정수 또는 null,
  "labels": ["업무/<업무명>", "시스템/<시스템>", "연도/<연도>"],
  "summary": "1~2문장 요약",
  "related_pages": [],
  "duplicate_of": null,
  "confidence": {"business": 0~1, "project": 0~1, "system": 0~1, "year": 0~1}
}

규칙:
- 근거가 부족한 필드는 null과 낮은 confidence(<0.5)로 표기.
- labels는 최소 업무/*, 연도/*를 포함(해당 시 시스템/* 추가).
- 반드시 유효한 JSON 하나만 출력."""


def build_analyze_user(doc: RawDoc, body_limit: int = 6000) -> str:
    body = doc.body_markdown[:body_limit]
    return (
        f"source_page_id: {doc.source_page_id}\n"
        f"제목: {doc.title}\n"
        f"작성자: {doc.author or ''}\n"
        f"생성: {doc.created_at or ''} / 수정: {doc.updated_at or ''}\n"
        f"기존 라벨: {', '.join(doc.original_labels)}\n"
        f"---\n{body}"
    )
