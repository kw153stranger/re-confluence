"""진행률 로그 헬퍼 검증."""

import logging

from reconf.logging_setup import progress


def _count(caplog, total, step_pct=5):
    caplog.clear()
    log = logging.getLogger("reconf.test")
    with caplog.at_level(logging.INFO, logger="reconf.test"):
        for i in range(1, total + 1):
            progress(log, "Stage", i, total, step_pct=step_pct)
    return [r.getMessage() for r in caplog.records]


def test_progress_throttles_and_reports_fraction(caplog):
    msgs = _count(caplog, 100, step_pct=5)
    # 5% 간격(=5건마다) + 1건째 + 마지막 → 첫/끝 포함
    assert any("1/100 (1%)" in m for m in msgs)
    assert any("100/100 (100%)" in m for m in msgs)
    assert any("50/100 (50%)" in m for m in msgs)
    # 너무 자주 찍지 않음 (전체보다 훨씬 적게)
    assert len(msgs) < 30


def test_progress_small_total_logs_each(caplog):
    msgs = _count(caplog, 3)
    assert any("1/3" in m for m in msgs)
    assert any("3/3 (100%)" in m for m in msgs)


def test_progress_zero_total_no_log(caplog):
    log = logging.getLogger("reconf.test")
    with caplog.at_level(logging.INFO, logger="reconf.test"):
        progress(log, "Stage", 0, 0)
    assert caplog.records == []
