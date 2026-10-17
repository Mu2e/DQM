"""The DQM database schema: tables, columns, dtypes and enums.

This module is the contract every other dqm component is written against, and
the reason they ship as one versioned distribution. The extractor writes
metrics, the evaluator reads them and compares against limits, the driver
commits alarm findings, and the web app displays all of it -- they have to
agree on what the tables look like and what the enum values mean. Defining
that once, here, makes the agreement a fact rather than a convention.

Several definitions mirror C++ in this same repository, which remains the
source of truth; each one names its header. Keeping a Python copy is a
deliberate duplication -- the alternative is parsing headers at runtime -- so
when a header changes, this file has to change with it. The tests check the
pairs that can be checked.

Nothing here touches the database or imports anything heavier than the
standard library and pandas' dtype names, so every component can rely on it
regardless of what environment it runs in.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, FrozenSet, Optional, Sequence, Tuple

__all__ = [
    "SCHEMA",
    "Table",
    "TABLES",
    "table",
    "dtypes_for",
    "SOURCES",
    "VALUES",
    "INTERVALS",
    "NUMBERS",
    "LIMITS",
    "FILES",
    "ALARMS",
    "ALARM_CAUSES",
    "METRIC_TABLES",
    "NumberCode",
    "AlarmCode",
    "CODE_VALUES",
    "ALARM_VALUES",
    "ALARM_STATUSES",
    "TERMINAL_ALARM_STATUSES",
    "DEFAULT_ALARM_STATUS",
    "ALARM_GRACE_HOURS",
    "valid_alarm_status",
    "terminal_alarm_status",
    "DTYPES",
    "TIME_COLUMNS",
    "QE_OPERATORS",
]

# Every DQM table lives in this one PostgreSQL schema, so table names reaching
# Query Engine are "dqm.<name>".
SCHEMA = "dqm"


# ----------------------------------------------------------------------- enums


class NumberCode(IntEnum):
    """Status of one measurement -- dqm.numbers.code.

    Mirrors DqmNumber::codeValues in DQM/inc/DqmNumber.hh. A fixed enum, not
    a per-source vocabulary: a source may not invent values.
    """

    OK = 0
    lowStats = 1
    missing = 2
    error = 3


class AlarmCode(IntEnum):
    """How seriously to treat a metric leaving its limits -- dqm.limits.alarmcode.

    Mirrors DqmLimit::alarmValues in DQM/inc/DqmLimit.hh.
    """

    ignore = 0
    warnOnly = 1
    standard = 2
    critical = 3


# Plain dict views of the two enums, for JSON responses and display code that
# wants {value: name} without depending on the enum type.
CODE_VALUES: Dict[int, str] = {int(c): c.name for c in NumberCode}
ALARM_VALUES: Dict[int, str] = {int(c): c.name for c in AlarmCode}

# The operator workflow vocabulary for an alarm episode -- dqm.alarms.status.
# Mirrors DqmAlarm::statusValues in DQM/inc/DqmAlarm.hh, which keeps it in code
# rather than as a SQL CHECK constraint so it can grow without a migration.
# That makes validating it the caller's job, hence the helpers below.
ALARM_STATUSES: Tuple[str, ...] = (
    "active",
    "acknowledged",
    "silenced",
    "retired",
    "deleted",
)

# The database default for a newly opened episode.
# An alarm episode's severity, and a cause's. Distinct from AlarmCode below,
# which is the alarmcode on a dqm.limits row (what to do about a threshold);
# this is how bad a finding was. They are both 0-3 and they are not the same
# vocabulary, which is exactly why both belong here rather than being spelled
# out wherever they happen to be needed.
ALARM_LEVEL_NAMES: Tuple[str, ...] = ("message", "warn", "alarm", "severe")
ALARM_LEVELS: Dict[int, str] = dict(enumerate(ALARM_LEVEL_NAMES))


def valid_alarm_level(level: int) -> bool:
    return level in ALARM_LEVELS


DEFAULT_ALARM_STATUS = "active"

# Setting either of these also closes the episode, so a later matching finding
# opens a fresh one rather than reviving this one -- DqmAlarm::terminalStatus.
TERMINAL_ALARM_STATUSES: FrozenSet[str] = frozenset({"retired", "deleted"})

# How long an episode stays extendable after its last extension, measured from
# mtime -- DqmAlarm::graceHours. Wall clock rather than run adjacency, because
# an evaluator sees runs out of order and cannot know whether a run it has not
# seen will ever arrive. A finding arriving after the window opens a new
# episode. One value for all evaluators for now; it belongs per (algo, config)
# eventually.
ALARM_GRACE_HOURS = 24


def valid_alarm_status(status: str) -> bool:
    """True if `status` is in the episode-status vocabulary."""
    return status in ALARM_STATUSES


def terminal_alarm_status(status: str) -> bool:
    """True if setting `status` also closes the episode."""
    return status in TERMINAL_ALARM_STATUSES


# ---------------------------------------------------------------------- tables


@dataclass(frozen=True)
class Table:
    """One DQM table: its name, primary key, columns and natural key.

    `columns` is the full column list in database order. `key` is the unique
    constraint that gives a row its identity, which is what a lookup-or-create
    matches on and what makes two reports the same thing -- distinct from the
    surrogate `pk`.
    """

    name: str
    pk: str
    columns: Tuple[str, ...]
    key: Tuple[str, ...] = ()
    doc: str = ""

    @property
    def qualified(self) -> str:
        """The name as Query Engine wants it, e.g. "dqm.numbers"."""
        return f"{SCHEMA}.{self.name}"

    def __str__(self) -> str:
        return self.qualified


SOURCES = Table(
    name="sources",
    pk="sid",
    columns=("sid", "process", "stream", "aggregation", "version"),
    key=("process", "stream", "aggregation", "version"),
    doc="One monitored source of metrics.",
)

VALUES = Table(
    name="values",
    pk="vid",
    columns=("vid", "groupx", "subgroup", "namex"),
    key=("groupx", "subgroup", "namex"),
    doc=(
        "The catalog of metric names that can be tracked. Source-independent: "
        "a row here says the name exists, not that any source reports it."
    ),
)

INTERVALS = Table(
    name="intervals",
    pk="iid",
    columns=(
        "iid",
        "sid",
        "start_run",
        "start_subrun",
        "end_run",
        "end_subrun",
        "start_time",
        "end_time",
    ),
    key=(
        "sid",
        "start_run",
        "start_subrun",
        "end_run",
        "end_subrun",
        "start_time",
        "end_time",
    ),
    doc=(
        "One time/run bucket belonging to one source. A run range, a time "
        "range, or both; only a start of one of them is required. A 'day' "
        "aggregation source gets roughly one per calendar day, a 'file' "
        "aggregation source one per file."
    ),
)

NUMBERS = Table(
    name="numbers",
    pk="nid",
    columns=("nid", "sid", "iid", "vid", "valuex", "sigma", "code"),
    key=("sid", "vid", "iid"),
    doc=(
        "One measurement. sigma=0.0 means not applicable or not computed, not "
        "literally zero error; code is a NumberCode."
    ),
)

LIMITS = Table(
    name="limits",
    pk="lid",
    columns=("lid", "sid", "iid", "vid", "llimit", "ulimit", "sigma", "alarmcode"),
    key=("sid", "vid", "iid"),
    doc=(
        "The acceptable range for the same (sid, vid, iid) a numbers row "
        "carries. Structurally parallel to numbers, differing only in payload. "
        "Populated independently, with no foreign key to numbers -- an "
        "interval can hold limits and no measurements, so an empty numbers "
        "result does not mean the interval is unused."
    ),
)

FILES = Table(
    name="files",
    pk="fid",
    columns=("fid", "sid", "iid", "filename"),
    key=("sid", "iid"),
    doc=(
        "The file a source's metrics for an interval were derived from, so an "
        "anomalous metric can be traced back to it."
    ),
)

ALARMS = Table(
    name="alarms",
    pk="aid",
    columns=(
        "aid",
        "algo",
        "config",
        "subject",
        "sid",
        "level",
        "start_run",
        "start_subrun",
        "end_run",
        "end_subrun",
        "start_time",
        "end_time",
        "ctime",
        "mtime",
        "open",
        "status",
        "status_time",
        "note",
    ),
    # What makes two reports the same episode -- see DqmAlarm.hh.
    key=("algo", "config", "subject", "sid"),
    doc=(
        "One alarm episode, identified by (algo, config, subject, sid): which "
        "evaluator, under which configuration, found what, on which source. "
        "`level` is the severity, escalating as the maximum over the episode's "
        "causes. The run and time spans are a hull of what fired and do not "
        "claim every run inside them alarmed -- alarm_causes is the ground "
        "truth. `note` is algo-internal JSON and is not queryable."
    ),
)

ALARM_CAUSES = Table(
    name="alarm_causes",
    pk="cid",
    columns=("cid", "aid", "iid", "vid", "level"),
    key=("aid", "iid", "vid"),
    doc=(
        "One piece of evidence for an episode: the interval it was seen in, "
        "and the variable it concerns. A NULL vid is a global test -- one "
        "about the interval as a whole rather than a single variable. A cause "
        "keeps the level it was first reported with; the episode's level still "
        "escalates above it."
    ),
)

# Every table, by bare name. Keyed on the bare name rather than the qualified
# one because that is what a caller has: a CLI argument, a config entry.
TABLES: Dict[str, Table] = {
    t.name: t
    for t in (SOURCES, VALUES, INTERVALS, NUMBERS, LIMITS, FILES, ALARMS, ALARM_CAUSES)
}

# The two measurement tables. They share the (sid, vid, iid) key shape, so the
# same filtering applies to either, and code that handles one generally handles
# both by name.
METRIC_TABLES: Dict[str, Table] = {"numbers": NUMBERS, "limits": LIMITS}


def table(name: str) -> Table:
    """Look up a Table by bare name, raising DqmConfigError if unknown."""
    from dqm.errors import DqmConfigError  # local: keeps this module import-light

    try:
        return TABLES[name]
    except KeyError:
        raise DqmConfigError(
            f"unknown DQM table {name!r}; known tables are {sorted(TABLES)}"
        ) from None


# ------------------------------------------------------------ column handling

# Columns holding a timestamp. Parsed as tz-aware UTC everywhere: Query Engine
# renders them with a local offset that shifts across DST ("-05:00" in summer,
# "-06:00" in winter), and a column of mixed offsets is left as opaque objects
# rather than comparable timestamps.
TIME_COLUMNS: FrozenSet[str] = frozenset(
    {"start_time", "end_time", "ctime", "mtime", "status_time"}
)

# pandas dtype per column, applied when parsing CSV from the database.
#
# Int64/Float64 are the nullable types: a blank CSV field becomes pd.NA instead
# of silently promoting the column to float or object. `boolean` is likewise
# nullable.
#
# The string columns are worth noting individually. `version` looks numeric but
# is not -- real values include both "0" and "005-001", and inferring would
# turn the first into an integer and break comparison against the second's
# format. `status` is constrained to ALARM_STATUSES but stored as text.
DTYPES: Dict[str, str] = {
    # surrogate keys
    "sid": "Int64",
    "vid": "Int64",
    "iid": "Int64",
    "nid": "Int64",
    "lid": "Int64",
    "fid": "Int64",
    "aid": "Int64",
    "cid": "Int64",
    # run/subrun ranges
    "start_run": "Int64",
    "start_subrun": "Int64",
    "end_run": "Int64",
    "end_subrun": "Int64",
    # measurements
    "valuex": "Float64",
    "sigma": "Float64",
    "llimit": "Float64",
    "ulimit": "Float64",
    # enums, held as their integer values
    "code": "Int64",
    "alarmcode": "Int64",
    "level": "Int64",
    # text
    "process": "string",
    "stream": "string",
    "aggregation": "string",
    "version": "string",
    "groupx": "string",
    "subgroup": "string",
    "namex": "string",
    "filename": "string",
    "algo": "string",
    "config": "string",
    "subject": "string",
    "status": "string",
    "note": "string",
    # flags
    "open": "boolean",
}


def dtypes_for(columns: Sequence[str], exclude: Optional[Sequence[str]] = None) -> Dict[str, str]:
    """The dtype map for `columns`, skipping any in `exclude`.

    Timestamp columns are normally excluded and converted after parsing, since
    a dtype cannot express the UTC normalization they need.
    """
    skip = set(exclude or ())
    return {c: DTYPES[c] for c in columns if c in DTYPES and c not in skip}


# ------------------------------------------------------------ query operators

# The complete set of Query Engine where-clause operators, lower-case.
#
# This is exhaustive and must not be guessed at. QE parses a clause as
# "col:op:val"; given an operator it does not recognize it does NOT report an
# error, but falls back to implicit equality and absorbs the rest as the value,
# building `col = 'op:val'`. On a typed column Postgres then fails the cast and
# the query errors loudly; on a text column the comparison is valid and matches
# nothing, returning zero rows under HTTP 200 -- indistinguishable from an
# honest absence of data. There is no `in`, no `like`, and `EQ` is not `eq`.
#
# Clause builders validate against this set so a bad operator raises here
# rather than becoming a silent empty result. See the aitools skill
# `coding-with-query-engine` for the full write-up.
QE_OPERATORS: FrozenSet[str] = frozenset({"lt", "le", "eq", "ne", "ge", "gt"})
