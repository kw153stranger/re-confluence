"""라벨 정규화·정확매칭·후보 등록 검증 (M0 범위)."""

from reconf.labels import normalize, resolve_label
from reconf.models import LabelEntry, LabelRegistry


def test_normalize_strips_spaces_and_prefixes_namespace():
    assert normalize("업무", " 구매 관리 ") == "업무/구매관리"


def test_resolve_exact_match_increments_count():
    reg = LabelRegistry(entries=[LabelEntry(namespace="업무", canonical="구매관리")])
    out = resolve_label(reg, "업무", "구매관리")
    assert out == "업무/구매관리"
    assert reg.entries[0].count == 1


def test_resolve_alias_match():
    reg = LabelRegistry(
        entries=[LabelEntry(namespace="업무", canonical="구매관리", aliases=["구매팀"])]
    )
    assert resolve_label(reg, "업무", "구매팀") == "업무/구매관리"


def test_resolve_unmatched_registers_candidate():
    reg = LabelRegistry()
    out = resolve_label(reg, "시스템", "ERP")
    assert out == "시스템/ERP"
    assert reg.entries[0].status == "candidate"
    assert reg.entries[0].canonical == "ERP"
