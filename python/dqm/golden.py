"""Which golden file a histogram file should be compared against.

dqm.golden is keyed by source and by a range of validity, so resolving a
reference needs two things the database cannot supply on its own: which source
a file belongs to, and where on the timeline it sits. A person looking at a
file in the display has neither -- they have a file name.

This module closes that gap, and nothing else. The supersession rule lives in
dqm.bands and the queries in dqm.reader; here there is only the chain from a
name to the arguments those two need, and an honest account of how far it got.

    match = golden_for_file("dqm.mu2e.cosmics_crv."
                            "crvreco-006-001-file.125873_000636-001.root", r)
    if match.filename:
        ...                       # overlay it
    else:
        print(match.problem)      # say why not

Two routes to the source, tried in that order:

  * dqm.files, which is the back pointer a committed file leaves behind. An
    exact hit gives the sid *and* the iid, and the interval gives the run and
    subrun -- authoritative, and needing no convention at all. Only files
    committed with `dqmTool commit-value --file` are there.

  * the file name. A DQM file is tier.owner.description.configuration.
    sequencer.format, where the configuration is <process>-<version>-
    <aggregation> and the sequencer is <run>_<subrun>. That is enough to find
    a source, but only if exactly one matches: the *stream* appears nowhere in
    the name (a file of crvreco/kpp_crv is described "cosmics_crv"), so a
    family whose sources differ only by stream -- the CRV wideband boards --
    is ambiguous and is refused rather than guessed at.

Failure is a normal outcome and is reported, never silently turned into "no
reference exists". A reference is not rigorously maintained, so "nothing
covers this run" has to be distinguishable from "this file told us nothing".
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from dqm.bands import as_int, has_run, in_force_one, newest_first

LOGGER = logging.getLogger("dqm.golden")

__all__ = ["GoldenMatch", "MuseName", "parse_name", "golden_for_file",
           "LATEST_RUN"]

# The run used when the position cannot be worked out, or when nothing covers
# the position that was. It matches exactly the declarations left open ended,
# which is what "the reference in use now" means -- and anyone looking at a
# file by hand is almost always looking at a recent one.
LATEST_RUN = 999999


@dataclass
class MuseName:
    """A Mu2e file name split into its six fields, plus what they imply.

    `run` and `subrun` come from the sequencer, which for data is
    "<run>_<subrun>" with anything further appended -- "125873_000636-001"
    is run 125873, subrun 636001, as the interval written for that file also
    records. Simulation sequencers are plain counters and yield no run, which
    is one of the ways this can fail.
    """

    tier: str = ""
    owner: str = ""
    description: str = ""
    configuration: str = ""
    sequencer: str = ""
    extension: str = ""
    run: Optional[int] = None
    subrun: Optional[int] = None
    process: str = ""
    version: str = ""
    aggregation: str = ""

    @property
    def complete(self) -> bool:
        return bool(self.tier and self.configuration and self.sequencer)


_SEQUENCER = re.compile(r"^(\d+)_(\d+)")


def parse_name(name: str) -> MuseName:
    """Split a Mu2e file name. Anything unrecognised comes back empty.

    Takes a bare name or a path -- the basename is what is in dqm.files, and
    a display may well be holding a /pnfs path or a root:// url instead.
    """
    base = os.path.basename(str(name or "").split("?", 1)[0])
    parts = base.split(".")
    if len(parts) != 6:
        return MuseName()

    out = MuseName(tier=parts[0], owner=parts[1], description=parts[2],
                   configuration=parts[3], sequencer=parts[4],
                   extension=parts[5])

    seq = _SEQUENCER.match(out.sequencer)
    if seq:
        out.run = int(seq.group(1))
        # "000636-001" is subrun 636001: the pieces after the run are one
        # number with a separator in it, not a subrun and something else.
        out.subrun = int(re.sub(r"\D", "", out.sequencer[seq.start(2):]) or 0)

    # <process>-<version>-<aggregation>, where the version itself contains a
    # dash ("crvreco-006-001-file"), so the ends are taken and the middle is
    # whatever is left.
    bits = out.configuration.split("-")
    if len(bits) >= 3:
        out.process = bits[0]
        out.aggregation = bits[-1]
        out.version = "-".join(bits[1:-1])
    return out


@dataclass
class GoldenMatch:
    """What the lookup found, and how.

    `filename` is empty when there is no reference to show, and `problem`
    then says which step stopped. `how` is for the line a display puts under
    the plot: a reference that was found by falling back deserves to say so.
    """

    filename: str = ""
    row: Any = None                 # the dqm.golden row, for its range and note
    sid: Optional[int] = None
    source: str = ""                # "crvreco/kpp_crv 006-001", for a caption
    run: Optional[int] = None       # the position actually used
    subrun: Optional[int] = None
    how: str = ""                   # files | name | latest
    problem: str = ""
    notes: list = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.filename)


def _source_label(row) -> str:
    bits = [str(getattr(row, "process", "") or ""),
            str(getattr(row, "stream", "") or "")]
    label = "/".join(b for b in bits if b)
    version = str(getattr(row, "version", "") or "")
    return f"{label} {version}".strip()


def _by_files(reader, base: str):
    """(sid, run, subrun, time) from dqm.files, or None if it is not there."""
    try:
        rows = reader.files(filename=base, limit=None)
    except Exception as exc:
        LOGGER.warning("dqm.files lookup failed for %s: %s", base, exc)
        raise

    if rows.empty:
        return None
    # files_unique is (sid,iid,filename), so one name may be recorded against
    # more than one source. Two sources would each have their own reference
    # and nothing here can choose between them.
    sids = {int(s) for s in rows["sid"].dropna().unique()}
    if len(sids) != 1:
        return None

    row = rows.iloc[0]
    run = as_int(row.get("start_run"))
    return (sids.pop(),
            run if has_run(run) else None,
            as_int(row.get("start_subrun")),
            row.get("start_time"))


def _by_name(reader, parsed: MuseName):
    """The sid implied by the file name, or None if it is not a single one."""
    if not (parsed.process and parsed.version and parsed.aggregation):
        return None
    try:
        rows = reader.sources(process=parsed.process, version=parsed.version,
                              aggregation=parsed.aggregation, limit=None)
    except Exception as exc:
        LOGGER.warning("source lookup failed for %s: %s", parsed.configuration, exc)
        raise
    if len(rows) != 1:
        return None
    return int(rows.iloc[0]["sid"])


def golden_for_file(name: str, reader) -> GoldenMatch:
    """The golden file to compare `name` against, or why there is none.

    Never raises for an absence: a file this cannot place, a source with no
    reference, and a run no declaration covers are all ordinary answers and
    come back as a GoldenMatch with an empty filename and a problem that says
    which it was. A failed *read*, on the other hand, propagates -- a Query
    Engine outage must not read as "no reference".
    """
    base = os.path.basename(str(name or ""))
    if not base:
        return GoldenMatch(problem="no file to look up")

    parsed = parse_name(base)
    found = _by_files(reader, base)
    sid = run = subrun = None
    when = None
    how = ""

    if found is not None:
        sid, run, subrun, when = found
        how = "files"
    else:
        sid = _by_name(reader, parsed)
        if sid is None:
            if not parsed.complete:
                return GoldenMatch(
                    problem=f"{base} is not a Mu2e file name, so there is no "
                            f"source to look up a reference for")
            return GoldenMatch(
                problem=f"no single source matches {parsed.configuration!r} "
                        f"({parsed.process}/{parsed.version}/"
                        f"{parsed.aggregation}); a reference is per source, "
                        f"so there is nothing to look up")
        run, subrun = parsed.run, parsed.subrun
        how = "name"

    label = ""
    try:
        srcs = reader.sources(sid=sid, limit=None)
        if not srcs.empty:
            label = _source_label(srcs.iloc[0])
    except Exception:  # a caption is not worth failing the lookup for
        LOGGER.debug("could not name source %s", sid, exc_info=True)

    rows = newest_first(reader.golden(sid=sid, limit=None))
    if not rows:
        return GoldenMatch(sid=sid, source=label, run=run, subrun=subrun,
                           problem=f"no golden file is declared for {label or sid}")

    hit = None
    if has_run(run):
        hit = in_force_one(rows, run=run, subrun=subrun)
    elif when is not None:
        hit = in_force_one(rows, time=when)

    if hit is None:
        # Either the position could not be worked out, or no declaration
        # covers it. Both land on the open-ended declarations, which is the
        # reference in use now; the caller is told it came from there.
        hit = in_force_one(rows, run=LATEST_RUN)
        if hit is None:
            where = f"run {run}" if has_run(run) else "this file"
            return GoldenMatch(sid=sid, source=label, run=run, subrun=subrun,
                               problem=f"no golden file covers {where}, and "
                                       f"none is left open ended")
        how = "latest"

    return GoldenMatch(filename=str(getattr(hit, "filename", "") or ""),
                       row=hit, sid=sid, source=label,
                       run=run, subrun=subrun, how=how)
