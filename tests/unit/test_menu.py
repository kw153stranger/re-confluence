"""메뉴 개선 로직 검증 — 사전 스냅 + 온톨로지/Path/메타 가중 스코어 추천."""

from reconf import menu
from reconf.dictionaries import DOMAIN, MENU_TYPE, TECHNOLOGY, snap, snap_label
from reconf.models import AnalysisResult


# --- Dictionary snap ---
def test_snap_case_insensitive_and_fuzzy():
    assert snap("vmware", TECHNOLOGY) == "VMware"
    assert snap("VMWARE", TECHNOLOGY) == "VMware"
    assert snap("infrastructure", DOMAIN) == "Infrastructure"
    assert snap("Guied", MENU_TYPE) == "Guide"  # 오타 보정
    assert snap("존재안함", DOMAIN) is None
    assert snap(None, DOMAIN) is None


def test_snap_label_whitelist():
    assert snap_label("VMWare") == "vmware"
    assert snap_label("VMware8") == "vmware"  # 유사
    assert snap_label("완전무관") is None


# --- Menu recommend ---
def _a(**kw):
    return AnalysisResult(source_page_id="1", title_normalized="t", **kw)


def test_recommend_from_metadata_ontology_path():
    a = _a(domain="Platform", technology="VMware", menu_type="Guide", lifecycle="Operation")
    assert menu.recommend(a, existing_path=["DC", "Platform"]) == [
        "Platform", "VMware", "Operation Guide",
    ]


def test_recommend_keeps_existing_path_when_metadata_weak():
    # 메타데이터가 거의 없으면 기존 경로(운영자 의도)를 유지
    a = _a()
    assert menu.recommend(a, existing_path=["DC", "Infrastructure", "Server"]) == [
        "DC", "Infrastructure", "Server",
    ]


def test_ontology_match_scoring():
    # Platform>VMware 는 온톨로지 일치(1.0), Platform>Oracle 은 불일치(0.6)
    assert menu.ontology_match(["Platform", "VMware"]) == 1.0
    assert menu.ontology_match(["Platform", "Oracle"]) == 0.6
    assert menu.ontology_match(["없는도메인"]) == 0.0


def test_score_weights_sum_to_one():
    assert abs(menu.W_ONTOLOGY + menu.W_PATH + menu.W_METADATA + menu.W_EMBEDDING - 1.0) < 1e-9


def test_embedding_only_refines_not_decides():
    # 임베딩은 후보 선택의 보조 신호(가중 0.20)일 뿐, 메뉴 자체를 만들지 않음
    a = _a(domain="Infrastructure", technology="Storage", menu_type="Runbook")
    path = ["Infra", "Storage"]
    low = menu.score(a, ["Infrastructure", "Storage", "Runbook"], path, embedding_sim=0.0)
    high = menu.score(a, ["Infrastructure", "Storage", "Runbook"], path, embedding_sim=1.0)
    assert high > low
    assert abs((high - low) - menu.W_EMBEDDING) < 1e-9
