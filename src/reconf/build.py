"""[Build] 업무 중심 IA·Page Properties·Labels 생성 (구현설계 §6.4).

라벨은 labels 마스터를 거쳐 canonical로 정규화한다.
M0: 스텁. 실제 구현은 M3.
"""

from __future__ import annotations

from .config import Config
from .logging_setup import get_logger
from .store import Store

log = get_logger("build")


def run(cfg: Config, store: Store, *, resume: bool = False, dry_run: bool = False) -> None:
    store.ensure_dirs()
    log.info("[Build] → %s (labels registry=%s)", store.build_dir, cfg.labels.registry)
    log.warning("[Build] 아직 구현되지 않았습니다 (M3 예정).")
