"""Time handling shared across DQM components.

Two jobs. First, normalize whatever a caller supplies -- an ISO string, a
datetime, naive or aware -- into a tz-aware UTC datetime, so an interval means
the same instant regardless of where the code runs. Second, render it in the
wire format whichever side of the database is being talked to expects.

A naive input is read as UTC rather than local time. That is a choice: local
time would make the same call mean different instants on different hosts, and
a monitoring database spanning years of runs cannot afford that ambiguity.
Callers wanting local-time semantics should attach a tzinfo themselves.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Union

__all__ = ["to_utc", "qe_time", "sql_time", "now_utc", "cutoff", "TimeLike"]

# What every entry point here accepts: an ISO-8601 string or a datetime.
TimeLike = Union[str, datetime]


def now_utc() -> datetime:
    """The current time, tz-aware in UTC."""
    return datetime.now(timezone.utc)


def to_utc(value: TimeLike) -> datetime:
    """Normalize an ISO-8601 string or datetime to a tz-aware UTC datetime.

    A trailing "Z" is accepted, which datetime.fromisoformat rejects before
    Python 3.11. A naive input is taken as UTC.
    """
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            raise ValueError("empty string is not a time")
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def cutoff(days: float, end: Optional[datetime] = None) -> datetime:
    """The instant `days` before `end` (default now), tz-aware in UTC.

    Used for "the last N days" filters, which several components express.
    """
    base = now_utc() if end is None else to_utc(end)
    return base - timedelta(days=days)


def qe_time(value: TimeLike) -> str:
    """Render a time for a Query Engine where clause.

    Includes the UTC offset, so the comparison is unambiguous regardless of
    the database server's timezone. Query Engine passes the literal through to
    PostgreSQL, which accepts this form for `timestamp with time zone`.
    """
    return to_utc(value).strftime("%Y-%m-%dT%H:%M:%S%z")


def sql_time(value: TimeLike) -> str:
    """Render a time for a dqmTool commit argument.

    Also carries an explicit UTC offset, for the same reason qe_time does: the
    value reaches PostgreSQL as a literal, and without an offset Postgres
    resolves it in the server's own timezone, which makes the stored instant
    depend on where the database happens to run.

    Note that dqmTool's own help documents the offset-less spelling
    ("2022-01-01T14:00:00"). Both are valid PostgreSQL; this one is merely
    unambiguous. DQM/inc/DqmTime.hh holds these as opaque strings and passes
    them straight into SQL, so nothing in the C++ constrains the choice --
    which also means this has not been exercised against a real commit yet.
    """
    return to_utc(value).strftime("%Y-%m-%dT%H:%M:%S%z")
