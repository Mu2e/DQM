"""In-memory stand-ins for the alarm driver's inputs.

The reader serves the four DqmReader calls the evaluator makes, with the same
signatures, from pandas frames built here. No database is needed.

The property the driver tests check throughout is the watermark (state.nid in
driver-state.json): every measurement at or below it counts as examined and is
never looked at again.
"""

from __future__ import annotations

from typing import Dict, Iterable, Optional, Sequence, Tuple

import pandas as pd

from dqm.errors import QueryEngineError
from dqm.evaluate.config import DriverConfig
from dqm.evaluate.driver import Driver
from dqm.evaluate.state import load_state

SID = 115
VID = 11
NAME = "grp/sub/m11"

# The band for VID is [10, 30]: IN is inside it and OUT is outside it.
IN = 20.0
OUT = 99.0

# Three points committed one after another: nids 1-2, 3-4, 5-6.
# Each is (iid, run, value of VID, nids).
THREE = [
    (101, 1001, IN, [1, 2]),
    (102, 1002, OUT, [3, 4]),
    (103, 1003, OUT, [5, 6]),
]


def numbers_frame(points: Iterable[Tuple[int, int, float, Sequence[int]]],
                  with_geometry: bool = True) -> pd.DataFrame:
    """dqm.numbers rows for SID, joined to their interval as DqmReader does.

    One row per nid. The first row of a point is VID with the given value;
    any further rows are VID+1, VID+2, ... inside the band, so each row is a
    distinct metric of the same interval.
    """
    rows = []
    for iid, run, value, nids in points:
        for k, nid in enumerate(nids):
            row = {
                "nid": nid, "sid": SID, "iid": iid, "vid": VID + k,
                "valuex": value if k == 0 else IN, "sigma": 0.0, "code": 0,
            }
            if with_geometry:
                row.update({
                    "start_run": run, "start_subrun": 0,
                    "end_run": run, "end_subrun": 0,
                    "start_time": pd.NaT, "end_time": pd.NaT,
                })
            rows.append(row)
    return pd.DataFrame(rows)


def limits_frame(vids: Iterable[int] = (VID,)) -> pd.DataFrame:
    """One open-ended band per vid, [10, 30], valid from run 1 onwards."""
    columns = ["lid", "sid", "iid", "vid", "llimit", "ulimit", "sigma",
               "alarmcode", "start_run", "start_subrun", "end_run",
               "end_subrun", "start_time", "end_time"]
    rows = [
        {"lid": i + 1, "sid": SID, "iid": 1, "vid": vid,
         "llimit": 10.0, "ulimit": 30.0, "sigma": 0.0, "alarmcode": 2,
         "start_run": 1, "start_subrun": 0, "end_run": None, "end_subrun": None,
         "start_time": pd.NaT, "end_time": pd.NaT}
        for i, vid in enumerate(vids)
    ]
    return pd.DataFrame(rows, columns=columns)


class FakeReader:
    """The DqmReader calls the evaluator makes, served from memory.

    `fail` names calls that raise QueryEngineError, which is what DqmReader
    raises on a real query failure (HTTP status >= 400, or a payload that is
    not the CSV asked for). "numbers#2" fails only the second numbers() call.
    """

    def __init__(self, numbers: pd.DataFrame, limits: Optional[pd.DataFrame] = None,
                 fail: Iterable[str] = ()):
        self._numbers = numbers
        self._limits = limits_frame() if limits is None else limits
        self.fail = set(fail)
        self.calls: Dict[str, int] = {}

    def _call(self, name: str) -> None:
        n = self.calls.get(name, 0) + 1
        self.calls[name] = n
        if name in self.fail or f"{name}#{n}" in self.fail:
            raise QueryEngineError(
                f"Query Engine returned HTTP 503 for t={name}: (fake outage)")

    def numbers(self, sid=None, limit=None, **_):
        self._call("numbers")
        return self._numbers[self._numbers["sid"] == sid].copy()

    def limits(self, sid=None, limit=None, **_):
        self._call("limits")
        return self._limits[self._limits["sid"] == sid].copy()

    def values_for_source(self, sid, **_):
        self._call("values_for_source")
        vids = sorted(set(int(v) for v in self._numbers["vid"]))
        return pd.DataFrame({
            "vid": vids,
            "groupx": ["grp"] * len(vids),
            "subgroup": ["sub"] * len(vids),
            "namex": [f"m{v}" for v in vids],
        })

    def intervals(self, sid=None, limit=None, **_):
        self._call("intervals")
        raise AssertionError("intervals() is only read when numbers() lacks geometry")


def make_cfg(tmp_path, algo="limits", commit=True, pars=None, lookback=None):
    return DriverConfig(algo=algo, config="test", sid=SID, commit=commit,
                        workdir=tmp_path, log=None, pars=dict(pars or {}),
                        lookback=lookback)


def watermark(tmp_path, algo="limits") -> int:
    """The nid saved in the state file (0 if the run never wrote one)."""
    return load_state(tmp_path, algo, "test", SID).nid


def run_driver(tmp_path, reader, tool, evaluator=None, **kw):
    cfg = make_cfg(tmp_path, **kw)
    return Driver(cfg, reader=reader, evaluator=evaluator, dqmtool=tool.path).run()


def warned(caplog, text: str) -> bool:
    """True if something at WARNING or above mentioned `text`."""
    return any(r.levelno >= 30 and text in r.getMessage() for r in caplog.records)
