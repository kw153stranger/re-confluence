"""[Analyze] 로컬 LLM(Qwen3) 분류·요약 → analysis JSON (구현설계 §6.2).

M0: 스텁. 실제 구현은 M2.
"""

from __future__ import annotations

from .config import Config
from .logging_setup import get_logger
from .store import Store

log = get_logger("analyze")


def run(cfg: Config, store: Store, *, resume: bool = False, dry_run: bool = False) -> None:
    store.ensure_dirs()
    log.info("[Analyze] model=%s endpoint=%s", cfg.llm.model, cfg.llm.endpoint)
    log.warning("[Analyze] 아직 구현되지 않았습니다 (M2 예정).")
