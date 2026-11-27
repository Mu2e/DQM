"""Which golden file applies to a histogram file, and how it was decided.

dqm.golden is keyed by source and by a range of validity, and a person
looking at a file has neither -- so the lookup is a chain of guesses with an
exact route at the front, and every step of it can fail. These pin which step
produced the answer, because a reference overlaid for the wrong reason is
worse than none at all.

Fake reader, no database.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from dqm.errors import QueryEngineError
from dqm.golden import LATEST_RUN, golden_for_file, parse_name

UTC = dt.timezone.utc
NO_TIME = pd.Timestamp("0001-01-01", tz=UTC)
OPEN_TIME = pd.Timestamp("9999-12-31 23:59:59.999999", tz=UTC)

# A real name from the crvreco dataset, and the source it belongs to.
NAME = "dqm.mu2e.cosmics_crv.crvreco-006-001-file.125873_000636-001.root"
SID = 118

SOURCES = [
    {"sid": 118, "process": "crvreco", "stream": "kpp_crv",
     "aggregation": "file", "version": "006-001"},
    # two sources differing only by stream: the name cannot choose between
    # them, which is the CRV wideband case
    {"sid": 200, "process": "CRVWB", "stream": "crvaging-001",
     "aggregation": "file", "version": "000-012-000"},
    {"sid": 201, "process": "CRVWB", "stream": "crvaging-002",
     "aggregation": "file", "version": "000-012-000"},
    # a source positioned by date rather than by run
    {"sid": 5, "process": "valNightly", "stream": "reco",
     "aggregation": "day", "version": "0"},
]


def interval(iid, sid, start_run=0, end_run=0, start_subrun=0,
             end_subrun=0, start=NO_TIME, end=NO_TIME):
    return {"iid": iid, "sid": sid, "start_run": start_run,
            "start_subrun": start_subrun, "end_run": end_run,
            "end_subrun": end_subrun, "start_time": start, "end_time": end}


class FakeReader:
    """Only the three calls the lookup makes, from frames a test hands it."""

    def __init__(self, files=(), golden=(), intervals=(), sources=SOURCES,
                 fail=()):
        self._files = list(files)
        self._golden = list(golden)
        self._intervals = list(intervals)
        self._sources = list(sources)
        self.fail = set(fail)
        self.calls = []

    def _check(self, what):
        self.calls.append(what)
        if what in self.fail:
            raise QueryEngineError(f"fake outage reading {what}")

    def files(self, sid=None, iid=None, filename=None, with_intervals=True,
              limit=None):
        self._check("files")
        rows = [r for r in self._files
                if (filename is None or r["filename"] == filename)
                and (sid is None or r["sid"] == sid)]
        frame = pd.DataFrame(rows, columns=["fid", "sid", "iid", "filename"])
        if with_intervals and rows:
            iv = pd.DataFrame(self._intervals)
            frame = frame.merge(iv.drop(columns=["sid"]), on="iid", how="left")
        return frame

    def golden(self, sid=None, with_intervals=True, limit=None):
        self._check("golden")
        rows = [r for r in self._golden if sid is None or r["sid"] == sid]
        frame = pd.DataFrame(rows, columns=["gid", "sid", "iid", "filename",
                                            "note"])
        if with_intervals and rows:
            iv = pd.DataFrame(self._intervals)
            frame = frame.merge(iv.drop(columns=["sid"]), on="iid", how="left")
        return frame

    def sources(self, sid=None, process=None, stream=None, aggregation=None,
                version=None, limit=None):
        self._check("sources")
        rows = [
            r for r in self._sources
            if (sid is None or r["sid"] == sid)
            and (process is None or r["process"] == process)
            and (stream is None or r["stream"] == stream)
            and (aggregation is None or r["aggregation"] == aggregation)
            and (version is None or r["version"] == version)
        ]
        return pd.DataFrame(rows, columns=["sid", "process", "stream",
                                           "aggregation", "version"])


# Intervals: one for the file itself, and three of validity.
IVS = [
    interval(28541, SID, 125873, 125873, 636001, 636001),      # the file's own
    interval(33144, SID, 120000, LATEST_RUN),                  # open ended
    interval(33200, SID, 125800, 125900),                      # a closed range
    interval(33300, 5, 0, 0, start=pd.Timestamp("2026-01-01", tz=UTC),
             end=OPEN_TIME),                                   # by time
]
FILES = [{"fid": 1, "sid": SID, "iid": 28541, "filename": NAME}]


def golden_row(gid, iid, filename, sid=SID, note=None):
    return {"gid": gid, "sid": sid, "iid": iid, "filename": filename,
            "note": note}


# -- the exact route ---------------------------------------------------------

def test_the_files_back_pointer_gives_both_source_and_run():
    r = FakeReader(files=FILES, intervals=IVS,
                   golden=[golden_row(4, 33144, "ref.root")])
    m = golden_for_file(NAME, r)
    assert m.filename == "ref.root"
    assert (m.sid, m.run, m.subrun) == (SID, 125873, 636001)
    assert m.how == "files"
    assert m.source == "crvreco/kpp_crv 006-001"


def test_a_path_is_reduced_to_its_basename():
    """dqm.files holds the bare name; a display may hold a /pnfs path."""
    r = FakeReader(files=FILES, intervals=IVS,
                   golden=[golden_row(4, 33144, "ref.root")])
    assert golden_for_file(f"/pnfs/mu2e/tape/dqm/ab/cd/{NAME}", r).how == "files"


def test_the_newest_covering_declaration_wins():
    r = FakeReader(files=FILES, intervals=IVS, golden=[
        golden_row(4, 33144, "old.root"),
        golden_row(7, 33200, "new.root"),   # covers 125800-125900, committed later
    ])
    assert golden_for_file(NAME, r).filename == "new.root"


def test_an_older_declaration_still_applies_outside_the_newer_range():
    r = FakeReader(files=FILES, intervals=IVS, golden=[
        golden_row(4, 33144, "open.root"),
        golden_row(7, 33200, "narrow.root"),
    ])
    other = NAME.replace("125873_000636", "121000_000001")
    m = golden_for_file(other, r)   # run 121000, outside the narrow range
    assert m.filename == "open.root"


# -- the name route ----------------------------------------------------------

def test_a_file_not_in_dqm_files_falls_back_to_the_name():
    r = FakeReader(files=[], intervals=IVS,
                   golden=[golden_row(4, 33144, "ref.root")])
    m = golden_for_file(NAME, r)
    assert m.filename == "ref.root"
    assert m.how == "name"
    assert (m.sid, m.run) == (SID, 125873)


def test_a_name_matching_several_sources_is_refused_not_guessed():
    """The stream is nowhere in a file name, so the CRV wideband family is
    ambiguous. Picking a board at random would overlay another board's
    reference."""
    name = "dqm.mu2e.CRV_wideband.CRVWB-000-012-000-file.125873_000001-001.root"
    r = FakeReader(files=[], intervals=IVS, golden=[])
    m = golden_for_file(name, r)
    assert not m
    assert "no single source" in m.problem


def test_a_name_matching_no_source_says_so():
    name = "dqm.mu2e.cosmics.cosmicreco-000-000-file.125873_000001-001.root"
    m = golden_for_file(name, FakeReader(files=[], golden=[]))
    assert not m
    assert "no single source" in m.problem


def test_something_that_is_not_a_mu2e_name_says_that_instead():
    m = golden_for_file("my_histograms.root", FakeReader())
    assert not m
    assert "not a Mu2e file name" in m.problem


# -- the 999999 fallback -----------------------------------------------------

def test_a_run_no_declaration_covers_falls_back_to_the_open_ended_one():
    r = FakeReader(files=FILES, intervals=IVS,
                   golden=[golden_row(7, 33200, "narrow.root")])  # 125800-125900
    other = NAME.replace("125873_000636", "119000_000001")        # before it
    m = golden_for_file(other, r)
    assert not m.filename        # nothing open ended exists here
    assert "no golden file covers run 119000" in m.problem


def test_the_open_ended_declaration_is_what_latest_means():
    r = FakeReader(files=[], intervals=IVS, golden=[
        golden_row(4, 33144, "open.root"),     # 120000-999999
        golden_row(7, 33200, "narrow.root"),   # 125800-125900
    ])
    # a simulation sequencer, so no run can be parsed at all
    sim = "dqm.mu2e.cosmics_crv.crvreco-006-001-file.0001.root"
    m = golden_for_file(sim, r)
    assert m.filename == "open.root"
    assert m.how == "latest"
    assert m.run is None


def test_a_covered_run_is_not_reported_as_a_fallback():
    r = FakeReader(files=FILES, intervals=IVS,
                   golden=[golden_row(4, 33144, "open.root")])
    assert golden_for_file(NAME, r).how == "files"


# -- absences ----------------------------------------------------------------

def test_a_source_with_no_declaration_at_all():
    r = FakeReader(files=FILES, intervals=IVS, golden=[])
    m = golden_for_file(NAME, r)
    assert not m
    assert "no golden file is declared" in m.problem
    assert "crvreco/kpp_crv" in m.problem


def test_one_name_recorded_against_two_sources_is_not_resolved_from_files():
    """files_unique is (sid,iid,filename), so this is possible, and each
    source would have its own reference."""
    files = FILES + [{"fid": 2, "sid": 200, "iid": 28541, "filename": NAME}]
    r = FakeReader(files=files, intervals=IVS,
                   golden=[golden_row(4, 33144, "ref.root")])
    m = golden_for_file(NAME, r)
    # falls through to the name route, which here resolves to 118 alone
    assert m.how == "name"


def test_a_time_positioned_source_is_resolved_by_time():
    """A day-aggregation source stores run 0, so a run lookup cannot work;
    the interval's timestamp is what places it."""
    name = "dqm.mu2e.nightly.valNightly-0-day.0001.root"
    files = [{"fid": 9, "sid": 5, "iid": 33300, "filename": name}]
    r = FakeReader(files=files, intervals=IVS,
                   golden=[golden_row(11, 33300, "nightly_ref.root", sid=5)])
    m = golden_for_file(name, r)
    assert m.filename == "nightly_ref.root"
    assert m.run is None


# -- failures are not absences -----------------------------------------------

@pytest.mark.parametrize("table", ["files", "golden"])
def test_a_query_failure_propagates_rather_than_reading_as_no_reference(table):
    """The lesson from the evaluator: a failed read that looks like an empty
    one is how a display says "all clear" about data it never saw."""
    r = FakeReader(files=FILES, intervals=IVS,
                   golden=[golden_row(4, 33144, "ref.root")], fail=[table])
    with pytest.raises(QueryEngineError):
        golden_for_file(NAME, r)


def test_the_source_name_is_cosmetic_and_its_failure_is_survivable():
    """The caption wants a readable source name; not having one is no reason
    to withhold the reference."""
    class NoNames(FakeReader):
        def sources(self, sid=None, **kw):
            if sid is not None:
                raise QueryEngineError("no names today")
            return super().sources(sid=sid, **kw)

    r = NoNames(files=FILES, intervals=IVS,
                golden=[golden_row(4, 33144, "ref.root")])
    m = golden_for_file(NAME, r)
    assert m.filename == "ref.root"
    assert m.source == ""


# -- the name parser ---------------------------------------------------------

def test_the_sequencer_parses_the_way_the_interval_was_written():
    """"125873_000636-001" is run 125873, subrun 636001 -- which is exactly
    what the interval committed for that file records."""
    p = parse_name(NAME)
    assert (p.run, p.subrun) == (125873, 636001)
    assert (p.process, p.version, p.aggregation) == ("crvreco", "006-001", "file")


def test_a_version_containing_a_dash_survives_the_split():
    p = parse_name("dqm.mu2e.x.CRVWB-000-012-000-file.1_1.root")
    assert (p.process, p.version, p.aggregation) == ("CRVWB", "000-012-000", "file")


def test_a_name_with_the_wrong_number_of_fields_yields_nothing():
    assert not parse_name("a.b.c.d.root").complete
    assert not parse_name("").complete
