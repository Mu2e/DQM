"""The driver's memory: how far this evaluator has got.

One small JSON file per driver instance, in that instance's working
directory. "Examined and found clean" leaves no trace in the database -- a
clean point writes nothing at all -- so progress cannot be recovered from the
database and has to be written down.

    {
      "algo": "limits",
      "config": "crv-tight-0",
      "sid": 115,
      "nid": 511082,
      "points": 3094,
      "updated": "2026-10-14T20:31:04+00:00",
      "mode": "commit"
    }

`nid` is the watermark: every measurement at or below it has been examined.
nid comes from a sequence, so it increases with commit order and never with
run order -- which is what makes it safe here.  A DQM file for an old run
processed today lands above the watermark and is picked up, where a run-based
watermark would skip it.

The file is written by replacing it, not by editing in place, so an
interrupted write leaves the previous state rather than half of the new one.
Back it up with cp before switching a driver from report to commit: the
watermark advances in either mode, so a re-run needs the old file restored.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from dqm.errors import DqmConfigError

LOGGER = logging.getLogger("dqm.evaluate.state")

__all__ = ["State", "load_state", "save_state", "DEFAULT_NAME"]

DEFAULT_NAME = "driver-state.json"


@dataclass
class State:
    """How far one (algo, config, sid) has been examined."""

    algo: str
    config: str
    sid: int
    nid: int = 0
    points: int = 0
    findings: int = 0
    updated: Optional[str] = None
    mode: Optional[str] = None

    @property
    def fresh(self) -> bool:
        """True if nothing has been examined yet -- the startup situation."""
        return self.nid <= 0

    def advance(self, nid: int, points: int, findings: int, mode: str) -> None:
        # Never move backwards: a re-run that happens to see fewer points must
        # not rewind the watermark and re-examine everything after it.
        self.nid = max(self.nid, int(nid))
        self.points += int(points)
        self.findings += int(findings)
        self.mode = mode
        self.updated = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _path(where: str | os.PathLike, name: str = DEFAULT_NAME) -> Path:
    p = Path(where)
    return p if p.suffix == ".json" else p / name


def load_state(where: str | os.PathLike, algo: str, config: str, sid: int,
               name: str = DEFAULT_NAME) -> State:
    """Read the state file, or start fresh if there is none.

    A missing file is the normal startup case and not an error.  A file
    describing a *different* evaluator is an error: it means the working
    directory is shared or the config changed under an existing watermark,
    and carrying on would record one evaluator's progress against another's.
    """
    target = _path(where, name)
    if not target.exists():
        LOGGER.info("no state file at %s -- starting from the beginning", target)
        return State(algo=algo, config=config, sid=sid)

    try:
        raw = json.loads(target.read_text())
    except Exception as exc:
        raise DqmConfigError(
            f"state file {target} is unreadable ({type(exc).__name__}: {exc}). "
            f"Move it aside to start over."
        ) from exc

    for field, want in (("algo", algo), ("config", config), ("sid", int(sid))):
        got = raw.get(field)
        if got is not None and got != want:
            raise DqmConfigError(
                f"state file {target} belongs to {raw.get('algo')}/"
                f"{raw.get('config')} sid={raw.get('sid')}, but this driver is "
                f"{algo}/{config} sid={sid}. Each driver needs its own working "
                f"directory."
            )

    state = State(
        algo=algo, config=config, sid=int(sid),
        nid=int(raw.get("nid") or 0),
        points=int(raw.get("points") or 0),
        findings=int(raw.get("findings") or 0),
        updated=raw.get("updated"),
        mode=raw.get("mode"),
    )
    LOGGER.info("resuming at nid=%d (%d points examined so far, last run %s)",
                state.nid, state.points, state.updated or "never")
    return state


def save_state(where: str | os.PathLike, state: State,
               name: str = DEFAULT_NAME) -> Path:
    """Write the state file atomically.

    Via a temporary file in the same directory and a rename, so that a cron
    job killed mid-write leaves the old watermark intact.  Losing the new
    value costs a re-examination, which is idempotent; a truncated file would
    cost the whole history.
    """
    target = _path(where, name)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=".state-",
                                   suffix=".json")
        with os.fdopen(fd, "w") as fh:
            json.dump(asdict(state), fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, target)
        tmp = None
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)
    LOGGER.debug("state written to %s (nid=%d)", target, state.nid)
    return target
