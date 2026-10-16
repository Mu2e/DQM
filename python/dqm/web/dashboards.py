"""Named, preconfigured sets of timelines, loaded from a JSON file.

A dashboard is a saved arrangement of the Timelines tab: which metrics to
plot, against time or run, over what window. Selecting one fills in every
control, so a routine check is one click rather than six dropdowns.

The file is read once when the application starts. Point at it with
DQM_DASHBOARDS; otherwise the copy shipped beside this module is used.

    {
      "dashboards": [
        {
          "name": "Nightly validation",
          "description": "calorimeter cluster energies",
          "mode": "time",
          "window": 90,
          "options": ["limits"],
          "series": [
            {"source": "valNightly/reco/day/0", "metric": "cal/clus/meanE0"},
            {"source": "valNightly/reco/day/0", "metric": "cal/clus/meanE1"}
          ]
        }
      ]
    }

A series may be written by name or by id. Names are the better choice --
`valNightly/reco/day/0` says what it is, where `sid: 5` does not, and a name
keeps meaning if the database is rebuilt with different ids:

    {"source": "process/stream/aggregation/version", "metric": "groupx/subgroup/namex"}
    {"sid": 5, "vid": 15}

Names are resolved against the database the first time a dashboard is used,
not at startup. A dashboard naming a metric that no longer exists is then a
message in the application rather than a failure to start -- which matters
because the file is edited by hand and one stale entry should not take the
whole tab down.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

LOGGER = logging.getLogger("dqm.web.dashboards")

__all__ = ["Dashboard", "SeriesSpec", "load_dashboards", "resolve_series",
           "DEFAULT_PATH", "ENV_VAR"]

ENV_VAR = "DQM_DASHBOARDS"
DEFAULT_PATH = Path(__file__).with_name("dashboards.json")


@dataclass(frozen=True)
class SeriesSpec:
    """One timeline in a dashboard, by name or by id."""

    source: Optional[str] = None      # "process/stream/aggregation/version"
    metric: Optional[str] = None      # "groupx/subgroup/namex"
    sid: Optional[int] = None
    vid: Optional[int] = None

    @property
    def described(self) -> str:
        if self.source or self.metric:
            return f"{self.source or '?'} / {self.metric or '?'}"
        return f"sid={self.sid} vid={self.vid}"


@dataclass(frozen=True)
class Dashboard:
    """A saved arrangement of the Timelines tab."""

    name: str
    series: Tuple[SeriesSpec, ...]
    description: str = ""
    mode: str = "time"
    window: Optional[float] = None
    options: Tuple[str, ...] = ("limits",)

    @property
    def window_text(self) -> str:
        """The window as the text field holds it; "" means the whole history."""
        if self.window is None:
            return ""
        return f"{self.window:g}"


def _parse_series(raw: Any, where: str) -> Optional[SeriesSpec]:
    if not isinstance(raw, dict):
        LOGGER.warning("%s: a series must be an object, got %r", where, type(raw).__name__)
        return None
    spec = SeriesSpec(
        source=raw.get("source"),
        metric=raw.get("metric"),
        sid=raw.get("sid"),
        vid=raw.get("vid"),
    )
    named = spec.source and spec.metric
    numbered = spec.sid is not None and spec.vid is not None
    if not (named or numbered):
        LOGGER.warning(
            "%s: a series needs either source and metric, or sid and vid; got %r",
            where, raw,
        )
        return None
    return spec


def _parse_dashboard(raw: Any, index: int) -> Optional[Dashboard]:
    where = f"dashboard {index}"
    if not isinstance(raw, dict):
        LOGGER.warning("%s: expected an object, got %r", where, type(raw).__name__)
        return None

    name = raw.get("name")
    if not name:
        LOGGER.warning("%s: has no name; skipped", where)
        return None

    series = []
    for i, entry in enumerate(raw.get("series") or []):
        parsed = _parse_series(entry, f"{name!r} series {i}")
        if parsed is not None:
            series.append(parsed)
    if not series:
        LOGGER.warning("%r: has no usable series; skipped", name)
        return None

    mode = raw.get("mode", "time")
    if mode not in ("time", "run"):
        LOGGER.warning("%r: mode must be 'time' or 'run', got %r; using 'time'",
                       name, mode)
        mode = "time"

    window = raw.get("window")
    if window is not None:
        try:
            window = float(window)
        except (TypeError, ValueError):
            LOGGER.warning("%r: window must be a number, got %r; using no window",
                           name, window)
            window = None

    options = raw.get("options", ["limits"])
    if not isinstance(options, (list, tuple)):
        options = []

    return Dashboard(
        name=str(name),
        description=str(raw.get("description", "")),
        mode=mode,
        window=window,
        options=tuple(str(o) for o in options),
        series=tuple(series),
    )


def load_dashboards(path: Optional[str] = None) -> List[Dashboard]:
    """Read the dashboard definitions.

    Never raises. A missing file means no dashboards, which is a perfectly
    good state -- the tab works without them. A malformed file logs what is
    wrong and yields whatever entries did parse, so one bad dashboard does not
    cost the others.
    """
    target = Path(path or os.environ.get(ENV_VAR) or DEFAULT_PATH)
    if not target.exists():
        LOGGER.info("no dashboard file at %s", target)
        return []

    try:
        raw = json.loads(target.read_text())
    except Exception as exc:
        LOGGER.error("could not read %s: %s: %s", target, type(exc).__name__, exc)
        return []

    entries = raw.get("dashboards") if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        LOGGER.error("%s: expected a list of dashboards, or an object with a "
                     "'dashboards' key", target)
        return []

    out = []
    for i, entry in enumerate(entries):
        parsed = _parse_dashboard(entry, i)
        if parsed is not None:
            out.append(parsed)
    LOGGER.info("loaded %d dashboard(s) from %s", len(out), target)
    return out


def _split(text: str, n: int, what: str) -> Optional[List[str]]:
    parts = [p.strip() for p in text.split("/")]
    if len(parts) != n:
        LOGGER.warning("%s %r should have %d parts separated by '/'", what, text, n)
        return None
    return parts


def resolve_series(spec: SeriesSpec, reader) -> Tuple[Optional[int], Optional[int], str]:
    """Turn one series into (sid, vid, problem).

    `problem` is empty on success and describes what went wrong otherwise --
    returned rather than raised because a dashboard is hand-written and the
    useful response to a stale entry is to say which one, not to fail.
    """
    sid, vid = spec.sid, spec.vid

    if sid is None and spec.source:
        parts = _split(spec.source, 4, "source")
        if parts is None:
            return None, None, f"source {spec.source!r} is not process/stream/aggregation/version"
        process, stream, aggregation, version = parts
        try:
            df = reader.sources(process=process, stream=stream,
                                aggregation=aggregation, version=version)
        except Exception as exc:
            return None, None, f"looking up source {spec.source!r} failed: {exc}"
        if df.empty:
            return None, None, f"no source matches {spec.source!r}"
        if len(df) > 1:
            return None, None, f"source {spec.source!r} matches {len(df)} sources"
        sid = int(df["sid"].iloc[0])

    if vid is None and spec.metric:
        parts = _split(spec.metric, 3, "metric")
        if parts is None:
            return None, None, f"metric {spec.metric!r} is not groupx/subgroup/namex"
        groupx, subgroup, namex = parts
        try:
            df = reader.values(groupx=groupx, subgroup=subgroup, namex=namex)
        except Exception as exc:
            return None, None, f"looking up metric {spec.metric!r} failed: {exc}"
        if df.empty:
            return None, None, f"no metric matches {spec.metric!r}"
        if len(df) > 1:
            return None, None, f"metric {spec.metric!r} matches {len(df)} metrics"
        vid = int(df["vid"].iloc[0])

    if sid is None or vid is None:
        return None, None, f"{spec.described}: incomplete"
    return sid, vid, ""
