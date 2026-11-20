"""A failed read of limits, metric names or interval ranges is a failed run.

DqmReader returns an empty frame when there is simply nothing to read and
raises QueryEngineError when the query itself failed. Only the first is "no
limits"; treating the second the same way judged every point against no band,
called it clean, exited 0 and moved the watermark past it for good.
"""

from __future__ import annotations

import logging

from evaluate_fakes import (NAME, THREE, FakeReader, limits_frame,
                            numbers_frame, run_driver, warned, watermark)


def test_limits_query_failure_fails_the_run_and_holds_the_watermark(
        tmp_path, fake_dqmtool, caplog):
    """Two of the three points are out of band. If the limits cannot be read,
    the run cannot call them clean: before the fix it did, exited 0 and moved
    the watermark to 6, and those alarms were lost."""
    caplog.set_level(logging.DEBUG, logger="dqm")
    reader = FakeReader(numbers_frame(THREE), fail={"limits"})
    result = run_driver(tmp_path, reader, fake_dqmtool)

    assert not result.ok
    assert result.examined == 0
    assert watermark(tmp_path) == 0
    assert fake_dqmtool.calls() == []
    assert warned(caplog, "limits")


def test_no_limits_configured_is_clean_and_advances(tmp_path, fake_dqmtool):
    """An empty limits frame is the normal "no band set" case, not a failure."""
    reader = FakeReader(numbers_frame(THREE), limits=limits_frame(vids=()))
    result = run_driver(tmp_path, reader, fake_dqmtool)
    assert result.ok
    assert result.findings == 0
    assert watermark(tmp_path) == 6


def test_metric_names_failure_fails_the_run(tmp_path, fake_dqmtool, caplog):
    """With a name-based metric list, losing the names selects nothing and
    every point looks clean. Before the fix that was logged at DEBUG, the run
    exited 0 and the watermark moved past the out-of-band points."""
    caplog.set_level(logging.DEBUG, logger="dqm")
    reader = FakeReader(numbers_frame(THREE), fail={"values_for_source"})
    result = run_driver(tmp_path, reader, fake_dqmtool, pars={"metrics": [NAME]})

    assert not result.ok
    assert watermark(tmp_path) == 0
    assert fake_dqmtool.calls() == []
    assert warned(caplog, "metric names")


def test_name_based_metric_list_alarms_when_names_read(tmp_path, fake_dqmtool):
    result = run_driver(tmp_path, FakeReader(numbers_frame(THREE)), fake_dqmtool,
                        pars={"metrics": [NAME]})
    assert result.ok
    assert result.committed == 2


def test_interval_ranges_failure_fails_the_run(tmp_path, fake_dqmtool):
    """Rows that arrive without their interval's run range cannot be matched
    to any band. If the fallback intervals() read fails too, every point was
    judged against no band and passed."""
    rows = numbers_frame(THREE, with_geometry=False)
    reader = FakeReader(rows, fail={"intervals"})
    result = run_driver(tmp_path, reader, fake_dqmtool)
    assert not result.ok
    assert watermark(tmp_path) == 0
