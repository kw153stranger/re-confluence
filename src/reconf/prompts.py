"""Analyze 프롬프트 (구현설계 §6.2·§8).

system=출력 스키마·규칙 강제, user=문서 메타+본문.
"""

from __future__ import annotations

from .dictionaries import DOMAIN, LABEL_WHITELIST, LIFECYCLE, MENU_TYPE, TECHNOLOGY
from .models import RawDoc

ANALYZE_SYSTEM = f"""당신은 사내 문서를 분류하는 도우미입니다.
아래 JSON 스키마에 정확히 맞는 **JSON 객체 1개만** 출력하세요. 설명·코드펜스 금지.

{{
  "source_page_id": "문자열(입력과 동일)",
  "title_normalized": "핵심만 남긴 제목",
  "business": "최상위 업무명 또는 null",
  "project": "프로젝트명 또는 null",
  "system": "관련 시스템 또는 null",
  "year": 정수 또는 null,
  "month": 정수 또는 null,
  "domain": "아래 Domain 목록에서 하나 또는 null",
  "technology": "아래 Technology 목록에서 하나 또는 null",
  "menu_type": "아래 MenuType 목록에서 하나 또는 null",
  "lifecycle": "아래 Lifecycle 목록에서 하나 또는 null",
  "labels": ["아래 Label 목록에서 선택"],
  "summary": "1~2문장 요약",
  "related_pages": [],
  "duplicate_of": null,
  "confidence": {{"business": 0~1, "project": 0~1, "system": 0~1, "year": 0~1}}
}}

사전(반드시 이 목록에서만 선택, 없으면 null):
- Domain: {", ".join(DOMAIN)}
- Technology: {", ".join(TECHNOLOGY)}
- MenuType: {", ".join(MENU_TYPE)}
- Lifecycle: {", ".join(LIFECYCLE)}
- Label: {", ".join(LABEL_WHITELIST)}

규칙:
- domain/technology/menu_type/lifecycle/labels 는 **위 사전 값만** 사용(자유 생성 금지).
- 근거가 부족한 필드는 null과 낮은 confidence(<0.5)로 표기.
- 기존 메뉴 경로(Current Path)가 있으면 운영자 의도로 존중해 분류를 판단.
- 반드시 유효한 JSON 하나만 출력."""


SUMMARIZE_SYSTEM = """다음 문서 조각을 사실 위주로 3~5문장으로 요약하세요.
숫자·고유명사·업무/시스템/연도 단서를 보존하고, 군더더기는 제거합니다."""


def build_summarize_user(chunk: str) -> str:
    return chunk


def build_analyze_user(doc: RawDoc, body_limit: int = 6000) -> str:
    body = doc.body_markdown[:body_limit]
    current_path = " > ".join(doc.path) if doc.path else "(없음)"
    return (
        f"source_page_id: {doc.source_page_id}\n"
        f"제목: {doc.title}\n"
        f"Current Path: {current_path}\n"  # 기존 메뉴 경로(운영자 의도)
        f"작성자: {doc.author or ''}\n"
        f"생성: {doc.created_at or ''} / 수정: {doc.updated_at or ''}\n"
        f"기존 라벨: {', '.join(doc.original_labels)}\n"
        f"---\n{body}"
    )
