"""HTML→MD 변환·slug·frontmatter 직렬화 검증."""

from reconf.markdown import dump_raw, html_to_markdown, parse_raw, slugify
from reconf.models import RawDoc


def test_html_to_markdown_headings_and_list():
    md = html_to_markdown("<h1>제목</h1><p>본문</p><ul><li>a</li><li>b</li></ul>")
    assert "제목" in md
    assert "본문" in md
    assert "a" in md and "b" in md


def test_slugify_keeps_korean_strips_symbols():
    assert slugify("2024년 상반기 구매/정산!") == "2024년-상반기-구매-정산"
    assert slugify("") == "untitled"


def test_dump_parse_roundtrip():
    doc = RawDoc(
        source_page_id="123",
        title="구매 정산 절차",
        author="홍길동",
        updated_at="2024-06-02",
        original_labels=["구매", "정산"],
        body_markdown="# 제목\n\n본문 내용",
    )
    text = dump_raw(doc)
    assert text.startswith("---")
    back = parse_raw(text)
    assert back.source_page_id == "123"
    assert back.title == "구매 정산 절차"
    assert back.original_labels == ["구매", "정산"]
    assert "본문 내용" in back.body_markdown
