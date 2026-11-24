"""The supersession rule, for a table whose rows are not per metric.

dqm.golden says "from here on, this is the reference file", so several rows
for one source are normal and the question is always which one applies at a
position. in_force_one answers it with the same covers/newest_first machinery
dqm.limits uses -- these tests pin the shape of the answer and the cases where
the answer is nothing.
"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pandas as pd

from dqm.bands import covers, in_force_one, newest_first

UTC = dt.timezone.utc

# How Query Engine renders the stored sentinels: a run-ranged declaration
# carries '-infinity' for both times, which comes back as year 1, and an open
# time end carries 'infinity', which comes back as year 9999. Neither is the
# literal word, so these are the values covers() actually sees.
NO_TIME = pd.Timestamp("0001-01-01", tz=UTC)
OPEN_TIME = pd.Timestamp("9999-12-31 23:59:59.999999", tz=UTC)


def by_run(gid, start_run, end_run, name="g.root", start_subrun=0,
           end_subrun=999999):
    """A declaration positioned by run, as commit-golden --runs writes it."""
    return SimpleNamespace(gid=gid, sid=79, iid=100 + gid, filename=name,
                           start_run=start_run, start_subrun=start_subrun,
                           end_run=end_run, end_subrun=end_subrun,
                           start_time=NO_TIME, end_time=NO_TIME)


def by_time(gid, start, end=OPEN_TIME, name="g.root"):
    """A declaration positioned by time, as commit-golden --start writes it."""
    return SimpleNamespace(gid=gid, sid=79, iid=200 + gid, filename=name,
                           start_run=0, start_subrun=0, end_run=0,
                           end_subrun=0, start_time=start, end_time=end)


def at(text):
    return pd.Timestamp(text, tz=UTC)


# -- one declaration ---------------------------------------------------------

def test_a_run_range_covers_inside_and_not_outside():
    row = by_run(1, 1100, 1199)
    assert covers(row, run=1100)
    assert covers(row, run=1150)
    assert covers(row, run=1199)
    assert not covers(row, run=1099)
    assert not covers(row, run=1200)


def test_an_open_run_end_covers_everything_after():
    # end_run 999999 is how "from here onwards" is spelled for runs.
    row = by_run(1, 1100, 999999)
    assert covers(row, run=1150)
    assert covers(row, run=125873)
    assert not covers(row, run=1099)


def test_a_time_range_with_an_open_end():
    row = by_time(1, at("2025-05-21"))
    assert covers(row, time=at("2026-01-01"))
    assert not covers(row, time=at("2024-01-01"))


def test_the_two_kinds_do_not_answer_each_others_questions():
    """A declaration carries one position or the other, never both.

    A run-ranged row stores year 1 for both times and a time-ranged row
    stores run 0, so each is excluded from the other's query. Guessing
    instead would point a comparison at the wrong reference file.
    """
    assert not covers(by_run(1, 1100, 1199), time=at("2026-01-01"))
    assert not covers(by_time(1, at("2025-05-21")), run=1150)


def test_no_position_covers_nothing():
    assert not covers(by_run(1, 1100, 1199))
    assert not covers(by_time(1, at("2025-05-21")))


# -- several declarations ----------------------------------------------------

def test_the_newest_covering_declaration_wins():
    """Two files over the same range: the later commit is the reference.

    This is how a reference that turned out to be bad is replaced, there
    being no delete in dqmTool.
    """
    rows = [by_run(1, 1100, 1199, "first.root"),
            by_run(2, 1100, 1199, "second.root")]
    assert in_force_one(newest_first(rows[::-1]), run=1150).filename == "second.root"


def test_an_older_declaration_still_governs_a_range_the_newer_does_not_cover():
    older = by_run(1, 1100, 1199, "old.root")
    newer = by_run(2, 1200, 1299, "new.root")
    ordered = newest_first([newer, older])
    assert in_force_one(ordered, run=1250).filename == "new.root"
    assert in_force_one(ordered, run=1150).filename == "old.root"


def test_nothing_covering_is_none_not_an_error():
    """Most sources have no reference, and one that has may not cover here."""
    assert in_force_one(newest_first([by_run(1, 1100, 1199)]), run=2000) is None
    assert in_force_one([], run=1150) is None
    assert in_force_one(newest_first(None), run=1150) is None


# -- ordering ----------------------------------------------------------------

def test_newest_first_sorts_a_frame_on_gid():
    """The frame arrives in gid order from the reader; the rule reads the
    other way round, and nothing else in it knows the column is called gid."""
    frame = pd.DataFrame([{"gid": 1, "sid": 79, "filename": "a.root"},
                          {"gid": 3, "sid": 79, "filename": "c.root"},
                          {"gid": 2, "sid": 79, "filename": "b.root"}])
    assert [r.gid for r in newest_first(frame)] == [3, 2, 1]


def test_newest_first_still_sorts_limits_on_lid():
    frame = pd.DataFrame([{"lid": 5, "vid": 11}, {"lid": 7, "vid": 11}])
    assert [r.lid for r in newest_first(frame)] == [7, 5]


def test_newest_first_leaves_a_frame_with_neither_key_alone():
    frame = pd.DataFrame([{"sid": 79}, {"sid": 12}])
    assert [r.sid for r in newest_first(frame)] == [79, 12]


def test_newest_first_of_an_empty_frame_is_empty():
    assert newest_first(pd.DataFrame(columns=["gid", "sid"])) == []
