"""HTML(storage)→Markdown 변환 · slug · frontmatter 직렬화 (구현설계 §6.1).

Export 산출물 raw/<page_id>__<slug>.md 는 YAML frontmatter + 본문 구조를 갖는다.
"""

from __future__ import annotations

import re

import yaml
from markdownify import markdownify

from .models import RawDoc

_SLUG_RE = re.compile(r"[^0-9A-Za-z가-힣]+")


def slugify(text: str, max_len: int = 60) -> str:
    """제목을 파일명 안전한 slug로 변환(한글 허용)."""
    s = _SLUG_RE.sub("-", text.strip()).strip("-")
    return (s[:max_len] or "untitled").lower()


def html_to_markdown(storage_html: str) -> str:
    """Confluence storage/HTML을 Markdown으로 변환."""
    if not storage_html:
        return ""
    return markdownify(storage_html, heading_style="ATX").strip()


# frontmatter 직렬화 대상 필드 (본문 제외)
_FM_FIELDS = (
    "source_page_id",
    "source_url",
    "title",
    "author",
    "created_at",
    "updated_at",
    "original_labels",
    "attachments",
)


def dump_raw(doc: RawDoc) -> str:
    """RawDoc → frontmatter+본문 문자열."""
    fm = {k: getattr(doc, k) for k in _FM_FIELDS}
    front = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{front}\n---\n\n{doc.body_markdown}\n"


def parse_raw(text: str) -> RawDoc:
    """frontmatter+본문 문자열 → RawDoc."""
    if text.startswith("---"):
        _, front, body = text.split("---", 2)
        meta = yaml.safe_load(front) or {}
        return RawDoc(**meta, body_markdown=body.strip())
    return RawDoc(source_page_id="", body_markdown=text.strip())
