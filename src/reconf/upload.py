"""[Upload] 신규 Space 생성·멱등 업로드 (구현설계 §6.6).

각 페이지에 source_page_id를 저장해 재실행 시 생성 대신 갱신한다.
M0: 스텁. 실제 구현은 M4.
"""

from __future__ import annotations

from .config import Config
from .logging_setup import get_logger
from .store import Store

log = get_logger("upload")


def run(
    cfg: Config,
    store: Store,
    *,
    target_space: str | None = None,
    resume: bool = False,
    dry_run: bool = False,
) -> None:
    store.ensure_dirs()
    log.info("[Upload] target_space=%s", target_space or cfg.target.space)
    log.warning("[Upload] 아직 구현되지 않았습니다 (M4 예정).")
