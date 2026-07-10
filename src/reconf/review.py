"""[Review] 사람 검수 — 분류 확인·수정·승인 (구현설계 §6.5).

검수 큐 export / 결과 apply 및 라벨 후보 승인/병합을 담당한다.
M0: 스텁. 실제 구현은 M3.
"""

from __future__ import annotations

from .config import Config
from .logging_setup import get_logger
from .store import Store

log = get_logger("review")


def run(
    cfg: Config,
    store: Store,
    *,
    export_queue: bool = False,
    apply: str | None = None,
    resume: bool = False,
    dry_run: bool = False,
) -> None:
    store.ensure_dirs()
    log.info("[Review] export_queue=%s apply=%s", export_queue, apply)
    log.warning("[Review] 아직 구현되지 않았습니다 (M3 예정).")
