"""라벨 정규화·정확/유사 매칭·후보 등록·거버넌스 검증."""

from reconf.labels import merge_alias, normalize, resolve_label
from reconf.models import LabelEntry, LabelRegistry


def test_normalize_strips_spaces_and_prefixes_namespace():
    assert normalize("업무", " 구매 관리 ") == "업무/구매관리"


def test_resolve_exact_match_increments_count():
    reg = LabelRegistry(entries=[LabelEntry(namespace="업무", canonical="구매관리")])
    assert resolve_label(reg, "업무", "구매관리") == "업무/구매관리"
    assert reg.entries[0].count == 1


def test_resolve_alias_match():
    reg = LabelRegistry(
        entries=[LabelEntry(namespace="업무", canonical="구매관리", aliases=["구매팀"])]
    )
    assert resolve_label(reg, "업무", "구매팀") == "업무/구매관리"


def test_resolve_fuzzy_absorbs_near_duplicate():
    reg = LabelRegistry(entries=[LabelEntry(namespace="업무", canonical="구매관리")])
    # '구매 관리' → 정규화 '구매관리' 와 동일 → 정확매칭(공백만 차이)
    assert resolve_label(reg, "업무", "구매 관리") == "업무/구매관리"
    # 표기 유사(부분집합)로 흡수
    out = resolve_label(reg, "업무", "구매관리팀", fuzzy_threshold=80)
    assert out == "업무/구매관리"
    assert "구매관리팀" in reg.entries[0].aliases


def test_resolve_unmatched_registers_candidate():
    reg = LabelRegistry()
    assert resolve_label(reg, "시스템", "ERP") == "시스템/ERP"
    assert reg.entries[0].status == "candidate"


def test_merge_alias_removes_entry():
    reg = LabelRegistry(
        entries=[
            LabelEntry(namespace="업무", canonical="구매관리"),
            LabelEntry(namespace="업무", canonical="구매", status="candidate"),
        ]
    )
    merge_alias(reg, "업무", "구매관리", "구매")
    canons = [e.canonical for e in reg.entries]
    assert canons == ["구매관리"]
    assert "구매" in reg.entries[0].aliases
