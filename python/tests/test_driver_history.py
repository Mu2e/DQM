"""An evaluator that needs history must not pass points it judged without it.

The trends evaluator says nothing about a point with too little history, which
is right early in a source's life and wrong when the history simply failed to
load: every point then counted as clean, the run exited 0 and the watermark
moved past steps and drifts that were never looked for.
"""

from __future__ import annotations

import logging

from evaluate_fakes import (IN, OUT, FakeReader, numbers_frame, run_driver,
                            warned, watermark)

TRENDS = {"algo": "trends", "lookback": 5,
          "pars": {"checks": ["step"], "min_history": 3}}


def _flat_then_step(n: int):
    """n points with one metric each: flat at IN, then a step to OUT at the end."""
    return [(200 + i, 2000 + i, IN if i < n - 1 else OUT, [1 + i]) for i in range(n)]


def test_trends_with_history_finds_the_step(tmp_path, fake_dqmtool):
    rows = numbers_frame(_flat_then_step(8))
    result = run_driver(tmp_path, FakeReader(rows), fake_dqmtool, **TRENDS)
    assert result.ok
    assert result.committed == 1
    assert watermark(tmp_path, "trends") == 8


def test_history_load_failure_fails_the_run_and_holds_the_watermark(
        tmp_path, fake_dqmtool, caplog):
    """The first numbers() read finds the new points; the second, for history,
    fails. Before the fix the step at the end went unreported, the run exited
    0 and the watermark moved to 8."""
    caplog.set_level(logging.DEBUG, logger="dqm")
    rows = numbers_frame(_flat_then_step(8))
    reader = FakeReader(rows, fail={"numbers#2"})
    result = run_driver(tmp_path, reader, fake_dqmtool, **TRENDS)

    assert not result.ok
    assert result.examined == 0
    assert watermark(tmp_path, "trends") == 0
    assert fake_dqmtool.calls() == []
    assert warned(caplog, "history")


def test_history_lookup_failure_for_one_point_stops_there(
        tmp_path, fake_dqmtool, monkeypatch):
    """History loaded, but finding the window for iid 204 raised. Before the
    fix 204 was judged with no history and passed, and the run went on and
    exited 0. Now the run stops at 204 and the watermark stays below it."""
    from dqm.evaluate.points import History

    real_before = History.before

    def before(self, point, count):
        if point.iid == 204:
            raise KeyError("broken index")
        return real_before(self, point, count)

    monkeypatch.setattr(History, "before", before)
    rows = numbers_frame(_flat_then_step(8))
    result = run_driver(tmp_path, FakeReader(rows), fake_dqmtool, **TRENDS)
    assert not result.ok
    assert result.examined == 4
    assert watermark(tmp_path, "trends") == 4


def test_lookback_zero_does_not_read_history(tmp_path, fake_dqmtool):
    """An evaluator that needs no history is not failed by a history outage."""
    rows = numbers_frame(_flat_then_step(3))
    reader = FakeReader(rows, fail={"numbers#2"})
    result = run_driver(tmp_path, reader, fake_dqmtool)
    assert result.ok
    assert reader.calls["numbers"] == 1
