"""Confluence storage 렌더링 검증 — Page Properties 매크로 + 원문."""

from reconf.models import BuildPage, PageProperties
from reconf.storagefmt import details_macro, render_page


def _props():
    return PageProperties(
        business="구매관리", owner="홍길동", system="ERP", year=2024,
        status="정본", source="https://cf/1",
    )


def test_details_macro_contains_standard_fields():
    xml = details_macro(_props())
    assert 'ac:structured-macro ac:name="details"' in xml
    for field in ("업무명", "담당", "시스템", "연도", "상태", "원본링크"):
        assert field in xml
    assert "구매관리" in xml and "ERP" in xml
    assert '<a href="https://cf/1">' in xml  # 원본링크는 링크로


def test_render_page_uses_original_storage():
    page = BuildPage(
        source_page_id="1", title="t", business="구매관리",
        properties=_props(), body_storage="<h2>제목</h2><p>원본</p>", body_markdown="무시됨",
    )
    out = render_page(page)
    assert "<h2>제목</h2><p>원본</p>" in out          # 원문 그대로
    assert 'ac:name="details"' in out                 # 프로퍼티 매크로
    assert "원본 문서 열기" in out                     # back-link


def test_render_page_falls_back_to_markdown():
    page = BuildPage(
        source_page_id="1", title="t", business="구매관리",
        properties=PageProperties(business="구매관리"), body_markdown="라인1\n라인2",
    )
    out = render_page(page)
    assert "<p>라인1</p>" in out and "<p>라인2</p>" in out
