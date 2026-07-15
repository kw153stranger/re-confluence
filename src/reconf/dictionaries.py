"""메타데이터·라벨 사전 (docs/메뉴구조개선방안.md §2·§3).

LLM이 자유롭게 값을 생성하지 않고 **사전에서 선택**하도록 강제한다.
`snap`은 LLM 출력을 사전의 표준 값으로 스냅(대소문자·표기 흔들림 보정), 실패 시 None.
"""

from __future__ import annotations

from rapidfuzz import fuzz, process

# 분류 축 (docs 제안 §2)
DOMAIN = ["Infrastructure", "Cloud", "Database", "Platform", "Security", "Network"]
TECHNOLOGY = [
    "VMware", "OpenShift", "Kubernetes", "Linux", "Oracle", "Storage", "Backup",
    "NetApp", "ESXi", "Nginx",
]
MENU_TYPE = [
    "Guide", "Runbook", "Architecture", "Reference", "Template", "Operation",
    "Troubleshooting", "Meeting", "Project", "Standard", "Policy", "FAQ", "Release",
]
LIFECYCLE = ["Planning", "Build", "Operation", "Migration", "Retire"]

# 라벨 화이트리스트 (docs 제안 §3) — 소문자 표준
LABEL_WHITELIST = [
    "vmware", "openshift", "kubernetes", "linux", "oracle", "storage",
    "backup", "network", "nginx", "netapp", "esxi",
]


def snap(value: str | None, vocab: list[str], threshold: int = 80) -> str | None:
    """value를 vocab의 표준 값으로 스냅. 대소문자 무시·유사도 기반. 미달이면 None."""
    if not value:
        return None
    v = value.strip()
    # 정확(대소문자 무시) 매칭
    for term in vocab:
        if v.lower() == term.lower():
            return term
    # 유사 매칭(대소문자 무시)
    match = process.extractOne(v, vocab, scorer=fuzz.ratio, processor=str.lower)
    if match and match[1] >= threshold:
        return match[0]
    return None


def snap_label(value: str) -> str | None:
    """라벨을 화이트리스트 소문자 표준으로 스냅."""
    return snap(value, LABEL_WHITELIST, threshold=85)
