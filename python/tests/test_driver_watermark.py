"""Where the alarm driver leaves its watermark when a batch does not finish.

A point above the watermark is examined on the next run; a point at or below
it never is. So after a run that stopped partway through its batch, the
watermark must not cover any point that was not fully handled.
"""

from __future__ import annotations

from evaluate_fakes import (IN, OUT, SID, THREE, FakeReader, numbers_frame,
                            run_driver, watermark)

from dqm.evaluate.limits import LimitsEvaluator


class _RaisesOn(LimitsEvaluator):
    """The limits evaluator, except that it raises on iid 102."""

    def evaluate(self, point, history=()):
        if point.iid == 102:
            raise RuntimeError("evaluator bug")
        return super().evaluate(point, history)


def test_clean_batch_advances_to_the_end(tmp_path, fake_dqmtool):
    reader = FakeReader(numbers_frame([(101, 1001, IN, [1, 2]),
                                       (102, 1002, IN, [3, 4])]))
    result = run_driver(tmp_path, reader, fake_dqmtool)
    assert result.ok
    assert watermark(tmp_path) == 4


def test_out_of_band_points_are_committed(tmp_path, fake_dqmtool):
    result = run_driver(tmp_path, FakeReader(numbers_frame(THREE)), fake_dqmtool)
    assert result.ok
    assert result.committed == 2
    assert watermark(tmp_path) == 6


def test_commit_failure_mid_batch_stops_watermark_before_the_failed_point(
        tmp_path, fake_dqmtool):
    """101 is clean, 102's commit fails every retry, 103 is never reached.

    The watermark may cover 101 (nids 1-2) and nothing after it. Before the
    fix it was saved at 6, the end of the batch: 102's alarm was never written,
    103 was never examined, and a re-run found no work.
    """
    fake_dqmtool.fail_iids(102)
    result = run_driver(tmp_path, FakeReader(numbers_frame(THREE)), fake_dqmtool)

    assert not result.ok
    assert result.examined == 2
    assert watermark(tmp_path) == 2

    # The documented recovery is to re-run once the cause is gone. It must
    # find 102 and 103 again and commit both.
    fake_dqmtool.fail_iids()
    again = run_driver(tmp_path, FakeReader(numbers_frame(THREE)), fake_dqmtool)
    assert again.ok
    assert again.committed == 2
    assert watermark(tmp_path) == 6
    committed = [c for c in fake_dqmtool.calls() if c.startswith("OK ")]
    assert [c.split()[1].split(",")[0] for c in committed] == ["102", "103"]


def test_evaluator_exception_mid_batch_stops_watermark_before_the_failed_point(
        tmp_path, fake_dqmtool):
    reader = FakeReader(numbers_frame([(101, 1001, IN, [1, 2]),
                                       (102, 1002, IN, [3, 4]),
                                       (103, 1003, IN, [5, 6])]))
    result = run_driver(tmp_path, reader, fake_dqmtool,
                        evaluator=_RaisesOn(config="test", sid=SID))
    assert not result.ok
    assert watermark(tmp_path) == 2


def test_failure_on_the_first_point_leaves_the_watermark_where_it_was(
        tmp_path, fake_dqmtool):
    fake_dqmtool.fail_iids(102)
    result = run_driver(tmp_path, FakeReader(numbers_frame(THREE[1:])), fake_dqmtool)
    assert not result.ok
    assert watermark(tmp_path) == 0


def test_watermark_never_covers_a_failed_point_whose_nids_interleave(
        tmp_path, fake_dqmtool):
    """Two intervals whose rows were committed interleaved (two writers at once).

    101 has nids 1 and 6, 102 has nids 2 and 3. Points come in order of their
    first nid, so 101 is handled first, and its last nid, 6, is above 102's.
    Saving 6 after 102 fails would bury 102, so the watermark must stop at 1,
    just below the failed point's first nid.
    """
    rows = numbers_frame([(101, 1001, IN, [1, 6]), (102, 1002, OUT, [2, 3])])
    fake_dqmtool.fail_iids(102)
    result = run_driver(tmp_path, FakeReader(rows), fake_dqmtool)
    assert not result.ok
    assert watermark(tmp_path) == 1


def test_report_mode_still_advances_past_everything(tmp_path, fake_dqmtool):
    """Report mode is a dry run and advances anyway, by design (README)."""
    result = run_driver(tmp_path, FakeReader(numbers_frame(THREE)), fake_dqmtool,
                        evaluator=_RaisesOn(config="test", sid=SID), commit=False)
    assert not result.ok
    assert watermark(tmp_path) == 6
    assert fake_dqmtool.calls() == []
