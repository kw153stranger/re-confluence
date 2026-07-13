"""Confluence storage format(XHTML) 렌더링 (구현설계 §5.3·§6.6).

업로드 페이지 본문 = Page Properties(details) 매크로 + 원문 내용.
- details 매크로는 Page Properties Report / Content by Label 자동 조회의 기반이 된다.
- 원문은 export에서 보존한 원본 storage(XHTML)를 그대로 재사용해 **동일 내용**을 보장한다.
"""

from __future__ import annotations

from html import escape

from .models import BuildPage, PageProperties

# Page Properties 매크로에 넣을 표준 필드 순서 (기획서 §5.3)
_FIELDS = ("업무명", "담당", "시스템", "연도", "상태", "원본링크")


def _prop_values(p: PageProperties) -> dict[str, str]:
    return {
        "업무명": p.business or "",
        "담당": p.owner or "",
        "시스템": p.system or "",
        "연도": str(p.year) if p.year else "",
        "상태": p.status or "",
        "원본링크": p.source or "",
    }


def details_macro(props: PageProperties) -> str:
    """Confluence 'Page Properties'(details) 매크로 XHTML."""
    vals = _prop_values(props)
    rows = []
    for f in _FIELDS:
        v = vals[f]
        if f == "원본링크" and v:
            cell = f'<a href="{escape(v)}">{escape(v)}</a>'
        else:
            cell = escape(v)
        rows.append(f"<tr><th>{f}</th><td>{cell}</td></tr>")
    table = f"<table><tbody>{''.join(rows)}</tbody></table>"
    return (
        '<ac:structured-macro ac:name="details">'
        f"<ac:rich-text-body>{table}</ac:rich-text-body>"
        "</ac:structured-macro>"
    )


def _markdown_fallback(md: str) -> str:
    """원본 storage가 없을 때의 최소 변환(문단 단위 이스케이프)."""
    parts = [f"<p>{escape(line)}</p>" for line in md.splitlines() if line.strip()]
    return "".join(parts)


def render_page(page: BuildPage) -> str:
    """업로드용 페이지 본문(storage XHTML): Page Properties 매크로 + 원문."""
    content = page.body_storage or _markdown_fallback(page.body_markdown or page.summary)
    backlink = ""
    if page.properties.source:
        src = escape(page.properties.source)
        backlink = f'<p><a href="{src}">원본 문서 열기 ↗</a></p>'
    return details_macro(page.properties) + content + backlink
