"""[Cluster] 동일 업무 병합·연도 그룹핑·중복 탐지 (구현설계 §6.3).

임베딩은 embed.ensure로 문서별 캐시를 재사용한다.
M0: 스텁. 실제 구현은 M2.
"""

from __future__ import annotations

from .config import Config
from .logging_setup import get_logger
from .store import Store

log = get_logger("cluster")


def run(cfg: Config, store: Store, *, resume: bool = False, dry_run: bool = False) -> None:
    store.ensure_dirs()
    log.info(
        "[Cluster] sim_threshold=%.2f embed=%s",
        cfg.cluster.sim_threshold,
        cfg.embeddings.model,
    )
    log.warning("[Cluster] 아직 구현되지 않았습니다 (M2 예정).")
