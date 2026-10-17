"""Shared helpers for the tabs: id prefixing, layout furniture, a cached reader."""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from dash import html

from dqm.reader import DqmReader

LOGGER = logging.getLogger("dqm.web.common")

__all__ = ["ID", "reader", "card", "row", "error_box", "kv_table",
           "values_for_source", "runs_for_source", "runs_for_metric",
           "has_run_structure", "REFRESH_MS", "drawn_stamp",
           "source_reports", "clear_caches"]

# How often an auto-refresh tick fires, in milliseconds. Shared by the tabs
# that offer one, so they do not drift apart. Ten minutes suits what actually
# changes: the nightly sources publish once a day, the per-file CRV sources
# once a subrun, and alarms appear when a driver runs. The catalogue caches
# expire in five minutes, so a tick always sees a fresh metric list too.
REFRESH_MS = 10 * 60 * 1000


def drawn_stamp() -> str:
    """"drawn HH:MM:SS UTC", for the end of a status line.

    Without it there is no way to tell a working auto-refresh from a stalled
    one: a refresh that returns the same rows looks exactly like no refresh.
    UTC, to match the timestamps in the data.
    """
    import datetime as dt

    return "drawn " + dt.datetime.now(dt.timezone.utc).strftime("%H:%M:%S UTC")

_READER: Optional[DqmReader] = None


def reader() -> DqmReader:
    """The shared database reader.

    One instance per process, so the underlying requests.Session reuses its
    TLS connection across callbacks instead of renegotiating on every user
    interaction. The reader holds no mutable per-query state, so sharing it
    between concurrent requests is safe.
    """
    global _READER
    if _READER is None:
        _READER = DqmReader()
    return _READER


# How long a cached "what does this source report?" answer stays good. New
# metrics appear for an existing source rarely -- a new extractor version, a
# new detector element -- so minutes is generous, while the cache saves a
# ~0.2s query on every interaction with the controls.
_VALUES_TTL_SECONDS = 300.0
_VALUES_CACHE: dict = {}


def values_for_source(sid: int, ttl: float = _VALUES_TTL_SECONDS):
    """Cached dqm.reader.values_for_source.

    Called both to build the metric dropdown and to check that a (source,
    metric) pair is valid before querying it, so without a cache a single
    source change would repeat the same lookup several times.
    """
    import time

    key = int(sid)
    now = time.monotonic()
    hit = _VALUES_CACHE.get(key)
    if hit is not None and (now - hit[0]) < ttl:
        return hit[1]
    df = reader().values_for_source(key)
    _VALUES_CACHE[key] = (now, df)
    return df


_RUNS_CACHE: dict = {}


def runs_for_source(sid: int, ttl: float = _VALUES_TTL_SECONDS):
    """Cached dqm.reader.runs_for_source.

    Consulted whenever the run window changes, so it is worth not re-reading
    every interval each time. Same TTL as the metric list: new runs appear
    often enough to matter but not between two clicks.
    """
    import time

    key = int(sid)
    now = time.monotonic()
    hit = _RUNS_CACHE.get(key)
    if hit is not None and (now - hit[0]) < ttl:
        return hit[1]
    runs = reader().runs_for_source(key)
    _RUNS_CACHE[key] = (now, runs)
    return runs


_METRIC_RUNS_CACHE: dict = {}


def runs_for_metric(sid: int, vid: int, ttl: float = _VALUES_TTL_SECONDS):
    """Cached dqm.reader.runs_for_metric, keyed on the (source, metric) pair."""
    import time

    key = (int(sid), int(vid))
    now = time.monotonic()
    hit = _METRIC_RUNS_CACHE.get(key)
    if hit is not None and (now - hit[0]) < ttl:
        return hit[1]
    runs = reader().runs_for_metric(*key)
    _METRIC_RUNS_CACHE[key] = (now, runs)
    return runs


def has_run_structure(sid: int) -> bool:
    """True if a run-based view of this source means anything.

    The nightly validation sources file every interval under run 0 because
    they are organised by date, so plotting them against run number would
    collapse everything onto one x value. Better to say so than to draw it.
    """
    try:
        runs = [r for r in runs_for_source(sid) if r > 0]
    except Exception:
        LOGGER.exception("could not read runs for sid=%s", sid)
        return True
    return len(runs) >= 2


def source_reports(sid: int, vid: int) -> bool:
    """True if this source has measurements for this metric.

    The question that makes an empty plot meaningful: a pairing that was never
    valid is a different thing from a source that has stopped reporting, and
    only the second is worth telling the user about.
    """
    try:
        df = values_for_source(sid)
    except Exception:
        # If the check itself fails, do not block the query -- let the real
        # one run and report its own error.
        LOGGER.exception("could not check metrics for sid=%s", sid)
        return True
    return int(vid) in set(df["vid"].dropna().astype(int))


def clear_caches() -> None:
    """Drop cached catalogue lookups, for tests and for a manual refresh."""
    _VALUES_CACHE.clear()
    _RUNS_CACHE.clear()
    _METRIC_RUNS_CACHE.clear()


def ID(prefix: str, name: str) -> str:
    """Build a component id inside a tab's namespace.

    One Dash app has one flat id namespace. Three tabs that each wanted a
    component called "graph" would collide silently -- the callbacks would
    wire themselves to whichever happened to exist. Going through this
    function makes the prefix impossible to forget.
    """
    return f"{prefix}{name}"


def card(children: Any, **style) -> Any:
    """A bordered panel, for a row of controls."""
    base = {
        "border": "1px solid #ddd",
        "borderRadius": "6px",
        "padding": "0.75rem",
        "background": "#fff",
        "marginBottom": "0.75rem",
    }
    base.update(style)
    return html.Div(children, style=base)


def row(children: List[Any], gap: str = "1rem") -> Any:
    """A flex row that wraps on a narrow window."""
    return html.Div(
        children,
        style={"display": "flex", "gap": gap, "flexWrap": "wrap",
               "alignItems": "flex-end"},
    )


def error_box(message: str, kind: str = "error") -> Any:
    """A visible message. `kind` is "error", "info" or "warn"."""
    colors = {
        "error": ("#b00020", "#fdecea"),
        "warn": ("#8a6d00", "#fff8e1"),
        "info": ("#01579b", "#e1f5fe"),
    }
    fg, bg = colors.get(kind, colors["error"])
    return html.Div(
        message,
        style={
            "color": fg, "background": bg, "padding": "0.6rem 0.8rem",
            "borderRadius": "4px", "border": f"1px solid {fg}33",
            "fontSize": "0.9rem",
        },
    )


def kv_table(pairs, width: str = "auto") -> Any:
    """A small two-column table of label/value pairs."""
    return html.Table(
        [
            html.Tbody(
                [
                    html.Tr(
                        [
                            html.Td(str(k), style={"paddingRight": "1rem",
                                                   "color": "#555"}),
                            html.Td(str(v), style={"fontFamily": "monospace"}),
                        ]
                    )
                    for k, v in pairs
                ]
            )
        ],
        style={"width": width, "fontSize": "0.9rem"},
    )
