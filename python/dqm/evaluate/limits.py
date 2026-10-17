"""The `limits` evaluator: is each metric inside its stored band?

The simplest useful algorithm, and the one that exercises the whole driver
path without any history. For each metric in the point it compares the value
against the band in dqm.limits and reports the ones outside it.

    evaluators:
      algo: limits
      config: crv-tight-0
      sid: 115
      pars:
        level: 2            # severity to report, default alarm
        use_sigma: true     # widen the band by the measurement's own error
        metrics: []         # empty means every metric that has a limit

Subjects, which are this algorithm's controlled vocabulary:

    out_of_limits   at least one metric fell outside its band

A point with no band in force is passed over quietly, logged and not
reported. Most sources have no limits configured yet, so alarming on their
absence would open an episode on nearly every source and say nothing about
the data.

Which band is "in force" is resolved in dqm.evaluate.points: dqm.limits is
keyed per interval, but those intervals are intervals of validity, so the
band that applies is the most recently committed one whose range covers the
point. See _resolve_limits there.
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional, Sequence

from dqm.errors import DqmConfigError
from dqm.evaluate.base import LEVELS, Cause, Evaluator, Finding, Point

LOGGER = logging.getLogger("dqm.evaluate.limits")

__all__ = ["LimitsEvaluator"]


class LimitsEvaluator(Evaluator):
    """Compare each metric against its band in dqm.limits."""

    algo = "limits"
    subjects = ("out_of_limits",)
    lookback = 0

    def configure(self) -> None:
        level = self.pars.get("level", LEVELS["alarm"])
        if isinstance(level, str):
            if level not in LEVELS:
                raise DqmConfigError(
                    f"limits: level must be one of {sorted(LEVELS)} or 0-3, "
                    f"got {level!r}"
                )
            level = LEVELS[level]
        if level not in range(4):
            raise DqmConfigError(f"limits: level must be 0-3, got {level!r}")
        self._level = int(level)

        self._use_sigma = bool(self.pars.get("use_sigma", False))

        # An explicit metric list restricts what is checked; empty means
        # everything that has a band.  Accepts vids or "group/subgroup/name".
        metrics = self.pars.get("metrics") or []
        if not isinstance(metrics, (list, tuple)):
            raise DqmConfigError("limits: metrics must be a list")
        self._metrics = [str(m) for m in metrics]

        # Whether to report a point whose measurements are all flagged bad by
        # the producer.  Off by default: a missing measurement is the
        # extractor's problem, and alarming on it here would double-report.
        self._check_bad_code = bool(self.pars.get("check_bad_code", False))

    def _selected(self, point: Point) -> List[int]:
        if not self._metrics:
            return list(point.vids)
        chosen = []
        for vid in point.vids:
            if str(vid) in self._metrics or point.name(vid) in self._metrics:
                chosen.append(vid)
        return chosen

    def evaluate(self, point: Point, history: Sequence[Point] = ()) -> Sequence[Finding]:
        vids = self._selected(point)
        if not vids:
            return []

        causes: List[Cause] = []
        detail = []
        with_limits = 0

        for vid in vids:
            band = point.limit(vid)
            if band is None:
                continue
            if band.llimit is None and band.ulimit is None:
                continue
            with_limits += 1

            m = point[vid]
            if not m.ok and not self._check_bad_code:
                # Flagged by the producer as lowStats/missing/error.
                continue

            # The measurement's own uncertainty can widen the band, so a value
            # just outside it with a large error is not reported.  Off unless
            # asked for, because not every metric sets a meaningful sigma.
            slack = abs(m.sigma) if self._use_sigma else 0.0

            low = band.llimit
            high = band.ulimit
            below = low is not None and m.valuex < low - slack
            above = high is not None and m.valuex > high + slack
            if not (below or above):
                continue

            # A band may carry its own alarmcode; it wins over the configured
            # level, since it was set per metric and deliberately.
            level = band.alarmcode if band.alarmcode else self._level
            causes.append(point.cause(vid, level=level))
            detail.append({
                "metric": point.name(vid),
                "vid": vid,
                "value": m.valuex,
                "sigma": m.sigma,
                "low": low,
                "high": high,
                "side": "below" if below else "above",
            })

        if causes:
            worst = sorted(detail, key=lambda d: -abs(d["value"]))[:2]
            shown = ", ".join(
                "%s=%.4g (%s %s)" % (d["metric"].split("/")[-1], d["value"],
                                     d["side"],
                                     d["low"] if d["side"] == "below" else d["high"])
                for d in worst
            )
            LOGGER.info("%s: %d of %d out of limits -- %s%s",
                        point.label, len(causes), with_limits, shown,
                        ", ..." if len(detail) > len(worst) else "")
            return [self.finding("out_of_limits", *causes,
                                 note=json.dumps({"out": detail}))]

        if with_limits == 0:
            # Nothing to compare against: no band covers this point.  Logged
            # rather than reported -- see the module docstring.
            LOGGER.info("%s: no limits in force for any of %d metrics",
                        point.label, len(vids))
            return []

        # Debug: the driver's per-point "clean" line already says this.
        LOGGER.debug("%s: %d metric(s) checked, all inside limits",
                     point.label, with_limits)
        return []
