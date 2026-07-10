"""라벨 마스터(labels.json) 정규화·유사중복 병합 (구현설계 §6.4a).

resolve_label로 문서 라벨을 canonical 하나로 통일한다.
M0: 정규화·정확매칭까지. 유사매칭(rapidfuzz/임베딩)은 M3.
"""

from __future__ import annotations

import re

from .logging_setup import get_logger
from .models import LabelEntry, LabelRegistry

log = get_logger("labels")


def normalize(namespace: str, raw: str) -> str:
    """공백·특수문자 정리 후 `네임스페이스/라벨` 형태로 정규화."""
    label = re.sub(r"\s+", "", raw.strip())
    return f"{namespace}/{label}"


def resolve_label(registry: LabelRegistry, namespace: str, raw: str) -> str:
    """정규화 → 정확매칭(canonical/aliases). 미매칭이면 candidate로 등록.

    유사매칭(rapidfuzz + 임베딩)은 M3에서 추가한다.
    """
    norm = normalize(namespace, raw)
    canonical_only = norm.split("/", 1)[1]
    for e in registry.entries:
        if e.namespace != namespace:
            continue
        if canonical_only == e.canonical or canonical_only in e.aliases:
            e.count += 1
            return f"{namespace}/{e.canonical}"
    # 미매칭 → 후보 등록
    registry.entries.append(
        LabelEntry(namespace=namespace, canonical=canonical_only, status="candidate", count=1)
    )
    return norm
