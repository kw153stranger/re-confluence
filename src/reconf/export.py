"""[Export] Confluence 수집 → Raw Markdown 저장 (구현설계 §6.1).

M0: 스텁. 실제 구현은 M2.
"""

from __future__ import annotations

from .config import Config
from .logging_setup import get_logger
from .store import Store

log = get_logger("export")


def run(cfg: Config, store: Store, *, resume: bool = False, dry_run: bool = False) -> None:
    store.ensure_dirs()
    log.info("[Export] space=%s → %s", cfg.source.space, store.raw_dir)
    log.info("[Export] resume=%s dry_run=%s", resume, dry_run)
    log.warning("[Export] 아직 구현되지 않았습니다 (M2 예정).")
