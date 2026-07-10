"""라벨 마스터(labels.json) 정규화·유사중복 병합 (구현설계 §6.4a).

resolve_label로 문서 라벨을 canonical 하나로 통일한다.
- 정규화 → 정확매칭(canonical/alias) → rapidfuzz 유사매칭(alias 흡수) → 미매칭 시 candidate 등록.
- 임베딩 기반 라벨 병합은 옵션(embed_sim 콜백)으로 주입 가능.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from rapidfuzz import fuzz

from .logging_setup import get_logger
from .models import LabelEntry, LabelRegistry
from .store import Store

log = get_logger("labels")


def normalize(namespace: str, raw: str) -> str:
    """공백·특수문자 정리 후 `네임스페이스/라벨` 형태로 정규화."""
    label = re.sub(r"\s+", "", raw.strip())
    return f"{namespace}/{label}"


def _bare(namespace: str, raw: str) -> str:
    return normalize(namespace, raw).split("/", 1)[1]


def resolve_label(
    registry: LabelRegistry,
    namespace: str,
    raw: str,
    *,
    fuzzy_threshold: int = 90,
    embed_sim: Callable[[str, str], float] | None = None,
    embed_threshold: float = 0.92,
) -> str:
    """라벨을 canonical로 통일. 미매칭이면 candidate로 등록.

    embed_sim(canonical, candidate)->0~1 을 주면 임베딩 유사도로도 병합 판단.
    """
    label = _bare(namespace, raw)
    ns_entries = [e for e in registry.entries if e.namespace == namespace]

    # 1) 정확 매칭
    for e in ns_entries:
        if label == e.canonical or label in e.aliases:
            e.count += 1
            return f"{namespace}/{e.canonical}"

    # 2) 유사 매칭 (rapidfuzz 표기 + 선택적 임베딩)
    for e in ns_entries:
        fuzzy = fuzz.token_set_ratio(label, e.canonical)
        emb = embed_sim(e.canonical, label) if embed_sim else 0.0
        if fuzzy >= fuzzy_threshold or emb >= embed_threshold:
            e.aliases.append(label)  # 유사중복 → alias 흡수
            e.count += 1
            log.info("[labels] '%s' → '%s' 병합(fuzzy=%d)", label, e.canonical, fuzzy)
            return f"{namespace}/{e.canonical}"

    # 3) 신규 후보
    registry.entries.append(
        LabelEntry(namespace=namespace, canonical=label, status="candidate", count=1)
    )
    return f"{namespace}/{label}"


def merge_alias(registry: LabelRegistry, namespace: str, canonical: str, alias: str) -> None:
    """검수에서 alias 병합을 확정(거버넌스)."""
    for e in registry.entries:
        if e.namespace == namespace and e.canonical == canonical:
            if alias not in e.aliases:
                e.aliases.append(alias)
    registry.entries = [
        e for e in registry.entries if not (e.namespace == namespace and e.canonical == alias)
    ]


def load_registry(store: Store) -> LabelRegistry:
    if store.exists(store.labels_path):
        return store.read_json(store.labels_path, LabelRegistry)
    return LabelRegistry()


def save_registry(store: Store, registry: LabelRegistry) -> None:
    store.write_json(store.labels_path, registry)
