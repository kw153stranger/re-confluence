"""단계 내부 동시성 헬퍼 (구현설계 §6.1·§6.2·§9).

workers<=1 이면 순차, 아니면 ThreadPoolExecutor로 처리한다. 입력 순서를 보존한다.
I/O 바운드(Export 수집·Analyze LLM·Cluster 임베딩)에 사용.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")


def run_concurrent(fn: Callable[[T], R], items: list[T], workers: int) -> list[R]:
    if workers <= 1 or len(items) <= 1:
        return [fn(x) for x in items]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(fn, items))
