"""메뉴 추천 — Ontology + 기존 Path + Metadata + Embedding 보조.

docs/메뉴구조개선방안.md의 §4·§5·Scoring을 구현한다.
임베딩은 "어떤 메뉴인지"가 아니라 "같은 그룹 내 어디에 둘지"를 돕는 보조 신호로 쓴다.
가중 스코어로 후보 메뉴(메타데이터 기반 vs 기존 경로 유지) 중 최적을 고른다.
"""

from __future__ import annotations

from rapidfuzz import fuzz

from .models import AnalysisResult

# 메뉴 온톨로지: 도메인 → 하위 기술/영역 (docs 제안)
ONTOLOGY: dict[str, list[str]] = {
    "Infrastructure": ["Server", "Storage", "Network", "Backup", "NetApp", "Linux", "Oracle"],
    "Platform": ["VMware", "OpenShift", "Kubernetes", "ESXi"],
    "Database": ["Oracle"],
    "Cloud": ["OpenShift", "Kubernetes"],
    "Security": [],
    "Network": ["Nginx"],
}

# 스코어 가중치 (docs 제안)
W_ONTOLOGY = 0.35
W_PATH = 0.25
W_METADATA = 0.20
W_EMBEDDING = 0.20


def _menu_leaf(a: AnalysisResult) -> str | None:
    if a.menu_type and a.lifecycle:
        return f"{a.lifecycle} {a.menu_type}"
    return a.menu_type or None


def candidate_from_metadata(a: AnalysisResult) -> list[str]:
    """메타데이터 기반 후보 메뉴: Domain > Technology > (Lifecycle MenuType)."""
    parts = [a.domain, a.technology, _menu_leaf(a)]
    return [p for p in parts if p]


def candidate_from_path(existing_path: list[str]) -> list[str]:
    """기존 경로 유지 후보(운영자 의도 반영)."""
    return list(existing_path)


def ontology_match(candidate: list[str]) -> float:
    if len(candidate) >= 2 and candidate[0] in ONTOLOGY:
        return 1.0 if candidate[1] in ONTOLOGY[candidate[0]] else 0.6
    if candidate and candidate[0] in ONTOLOGY:
        return 0.6
    return 0.0


def path_similarity(candidate: list[str], existing_path: list[str]) -> float:
    if not candidate or not existing_path:
        return 0.0
    return fuzz.token_set_ratio(" > ".join(candidate), " > ".join(existing_path)) / 100.0


def metadata_match(a: AnalysisResult) -> float:
    fields = [a.domain, a.technology, a.menu_type, a.lifecycle]
    return sum(1 for f in fields if f) / len(fields)


def score(
    a: AnalysisResult, candidate: list[str], existing_path: list[str], embedding_sim: float = 0.0
) -> float:
    return (
        W_ONTOLOGY * ontology_match(candidate)
        + W_PATH * path_similarity(candidate, existing_path)
        + W_METADATA * metadata_match(a)
        + W_EMBEDDING * embedding_sim
    )


def recommend(
    a: AnalysisResult, existing_path: list[str] | None = None, embedding_sim: float = 0.0
) -> list[str]:
    """후보(메타데이터 기반·기존 경로 유지) 중 가중 스코어가 높은 메뉴 경로를 반환."""
    existing_path = existing_path or []
    candidates: list[list[str]] = []
    meta = candidate_from_metadata(a)
    if meta:
        candidates.append(meta)
    if existing_path:
        candidates.append(candidate_from_path(existing_path))
    if not candidates:
        return []
    return max(candidates, key=lambda c: score(a, c, existing_path, embedding_sim))
