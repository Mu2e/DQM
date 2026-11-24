"""DqmReader.files, DqmReader.golden and DqmReader.golden_in_force.

Served from a fake Query Engine client, so these check what the reader asks
for and what it makes of the answer -- the clauses it pushes down, the
interval join that puts the ranges on the rows, and the one-row answer -- with
no database and no network.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from dqm.reader import DqmReader

UTC = dt.timezone.utc

# Query Engine renders a stored '-infinity' as year 1 and 'infinity' as year
# 9999; see test_bands_golden.
NO_TIME = pd.Timestamp("0001-01-01", tz=UTC)
OPEN_TIME = pd.Timestamp("9999-12-31 23:59:59.999999", tz=UTC)

GOLDEN_ROWS = [
    # two declarations over the same run range, the second superseding
    {"gid": 1, "sid": 79, "iid": 33016, "filename": "first.root",
     "note": "an average, by hand"},
    {"gid": 2, "sid": 79, "iid": 33016, "filename": "second.root",
     "note": None},
    # and one positioned by time instead
    {"gid": 3, "sid": 79, "iid": 33017, "filename": "bytime.root",
     "note": None},
    # another source's declaration, which must not leak into sid 79's answer
    {"gid": 4, "sid": 12, "iid": 27170, "filename": "other.root",
     "note": None},
]

INTERVAL_ROWS = [
    {"iid": 33016, "sid": 79, "start_run": 1100, "start_subrun": 0,
     "end_run": 1199, "end_subrun": 999999,
     "start_time": NO_TIME, "end_time": NO_TIME},
    {"iid": 33017, "sid": 79, "start_run": 0, "start_subrun": 0,
     "end_run": 0, "end_subrun": 0,
     "start_time": pd.Timestamp("2025-05-21", tz=UTC), "end_time": OPEN_TIME},
    {"iid": 27170, "sid": 12, "start_run": 1100, "start_subrun": 0,
     "end_run": 1100, "end_subrun": 999999,
     "start_time": NO_TIME, "end_time": NO_TIME},
]

FILE_ROWS = [
    {"fid": 1, "sid": 12, "iid": 27170, "filename": "a.root"},
    {"fid": 2, "sid": 12, "iid": 27170, "filename": "b.root"},
    {"fid": 3, "sid": 79, "iid": 33016, "filename": "c.root"},
]

TABLE_ROWS = {
    "dqm.golden": GOLDEN_ROWS,
    "dqm.intervals": INTERVAL_ROWS,
    "dqm.files": FILE_ROWS,
}


class FakeQE:
    """The query engine, as DqmReader uses it: one table, clauses, columns.

    Applies the clauses it is given rather than ignoring them, so a test can
    tell a filter that was pushed down from one the reader did in pandas --
    and so a clause with a bad operator would show up as a wrong answer here
    rather than passing silently.
    """

    base_url = "fake://qe"
    dbname = "mu2e_dqm_prd"
    timeout_seconds = 1

    def __init__(self):
        self.calls = []

    def query(self, table, columns, clauses=None, order=None, limit=None,
              chunksize=None):
        self.calls.append({"table": table, "clauses": list(clauses or []),
                           "order": order, "limit": limit})
        rows = TABLE_ROWS[table]
        for clause in clauses or []:
            column, op, value = _parse(clause)
            rows = [r for r in rows if _passes(r[column], op, value)]
        df = pd.DataFrame(rows, columns=list(columns))
        if order:
            df = df.sort_values(order.lstrip("-"),
                                ascending=not order.startswith("-"))
        if limit is not None:
            df = df.iloc[:limit]
        return df.reset_index(drop=True)


def _parse(clause):
    """A clause as QE reads it: "col:op:val", or "col:val" meaning equality.

    transport.where_eq writes the second form deliberately -- with no
    operator present there is none to get wrong -- so a fake that only
    understood the first would reject every equality filter.
    """
    parts = clause.split(":", 2)
    if len(parts) == 3 and parts[1] in {"eq", "ne", "lt", "le", "gt", "ge"}:
        return parts[0], parts[1], parts[2]
    column, value = clause.split(":", 1)
    return column, "eq", value


def _passes(cell, op, value):
    want = int(value) if str(value).lstrip("-").isdigit() else value
    if isinstance(cell, pd.Timestamp) and not isinstance(want, pd.Timestamp):
        want = pd.Timestamp(want)
    return {"eq": cell == want, "ne": cell != want, "le": cell <= want,
            "lt": cell < want, "ge": cell >= want, "gt": cell > want}[op]


@pytest.fixture
def reader():
    return DqmReader(client=FakeQE())


# -- golden ------------------------------------------------------------------

def test_golden_scopes_to_one_source_in_the_query(reader):
    df = reader.golden(sid=79, limit=None)
    assert list(df["gid"]) == [1, 2, 3]
    assert "sid:79" in reader.client.calls[0]["clauses"]


def test_golden_carries_the_ranges_from_the_interval_join(reader):
    """Without these columns dqm.bands could not judge anything: the payload
    is in dqm.golden and the range it applies over is not."""
    df = reader.golden(sid=79, limit=None)
    row = df[df["gid"] == 1].iloc[0]
    assert (row["start_run"], row["end_run"]) == (1100, 1199)
    assert [c["table"] for c in reader.client.calls] == ["dqm.golden",
                                                         "dqm.intervals"]


def test_golden_without_the_join_asks_one_question_only(reader):
    df = reader.golden(sid=79, with_intervals=False, limit=None)
    assert "start_run" not in df.columns
    assert [c["table"] for c in reader.client.calls] == ["dqm.golden"]


def test_golden_comes_back_in_commit_order(reader):
    reader.golden(limit=None)
    assert reader.client.calls[0]["order"] == "gid"


def test_golden_of_a_source_with_none_is_empty_not_an_error(reader):
    df = reader.golden(sid=115, limit=None)
    assert df.empty
    assert "gid" in df.columns


# -- golden_in_force ---------------------------------------------------------

def test_in_force_picks_the_newest_covering_declaration(reader):
    assert reader.golden_in_force(79, run=1150).filename == "second.root"


def test_in_force_by_time_picks_the_time_ranged_declaration(reader):
    row = reader.golden_in_force(79, time="2026-01-01T00:00:00Z")
    assert row.filename == "bytime.root"


def test_in_force_accepts_a_datetime_as_well_as_a_string(reader):
    when = dt.datetime(2026, 1, 1, tzinfo=UTC)
    assert reader.golden_in_force(79, time=when).filename == "bytime.root"


def test_in_force_outside_every_range_is_none(reader):
    assert reader.golden_in_force(79, run=2000) is None
    assert reader.golden_in_force(79, time="2024-01-01T00:00:00Z") is None


def test_in_force_of_a_source_with_no_declaration_is_none(reader):
    assert reader.golden_in_force(115, run=1150) is None


def test_in_force_does_not_see_another_sources_declaration(reader):
    """sid 12 has one covering run 1100; asking about sid 79 at run 1100
    must answer with sid 79's own, not whichever row happened to cover."""
    assert reader.golden_in_force(79, run=1100).sid == 79


# -- files -------------------------------------------------------------------

def test_files_scopes_to_one_source(reader):
    df = reader.files(sid=12, limit=None)
    assert sorted(df["filename"]) == ["a.root", "b.root"]
    assert "sid:12" in reader.client.calls[0]["clauses"]


def test_files_keeps_several_files_for_one_interval(reader):
    """Unlike golden, a (sid, iid) may have more than one file, and both are
    the provenance of that interval's metrics."""
    df = reader.files(iid=27170, limit=None)
    assert len(df) == 2


def test_files_carries_the_interval_of_measurement(reader):
    df = reader.files(sid=79, limit=None)
    assert int(df.iloc[0]["start_run"]) == 1100
