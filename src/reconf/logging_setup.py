"""구조화 로깅 설정 (구현설계 §9).

단계·page_id 등 컨텍스트를 붙이기 쉬운 최소 구성. 표준 logging 기반.
"""

from __future__ import annotations

import logging
import threading

_CONFIGURED = False


def setup_logging(level: int = logging.INFO) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    root = logging.getLogger("reconf")
    root.setLevel(level)
    root.addHandler(handler)
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"reconf.{name}")


def progress(log: logging.Logger, stage: str, done: int, total: int, step_pct: int = 5) -> None:
    """단계 진행률 표시: '[Stage] 완료/전체 (pct%)'. step_pct 간격으로만 로그(throttle)."""
    if total <= 0:
        return
    every = max(1, total * step_pct // 100)
    if done == 1 or done == total or done % every == 0:
        log.info("[%s] 진행 %d/%d (%d%%)", stage, done, total, done * 100 // total)


class ProgressCounter:
    """동시성(스레드) 환경에서 안전하게 진행률을 집계·표시한다."""

    def __init__(self, log: logging.Logger, stage: str, total: int, step_pct: int = 5):
        self._log = log
        self._stage = stage
        self._total = total
        self._step_pct = step_pct
        self._done = 0
        self._lock = threading.Lock()

    def tick(self) -> None:
        with self._lock:
            self._done += 1
            done = self._done
        progress(self._log, self._stage, done, self._total, self._step_pct)
