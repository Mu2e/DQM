"""The `trends` evaluator: has a metric moved, compared with its own past?

Where `limits` asks "is this value inside its band", this asks "is this value
unlike the ones before it". No band needs to be configured: the metric's own
recent history supplies the scale, which is what makes it useful on the great
majority of metrics that have no limits set.

    algo:   trends
    config: crv-drift-0
    sid:    115
    lookback: 20              # points of history; the window

    pars:
      checks:   [step, drift] # which tests to run
      n_sigma:  5.0           # robust sigmas to call it
      rel_min:  0.02          # and at least this fractional change
      min_history: 5          # fewer points than this: say nothing
      sigma_floor: 0.0        # absolute floor on the scale, in metric units
      metrics:  []            # empty means every metric in the point

Subjects:

    step    this point has moved away from its recent baseline
    drift   the window as a whole is sloping

Two things the data forced on this design.

First, there is no "stuck" check, although a metric frozen at one value is a
real DQM failure. In this database being frozen is the *normal* state for
many metrics: for one CRV calibration constant 100% of consecutive points are
identical, in a run 1165 long. Those metrics are database constants that
legitimately do not change, so a stuck check would fire on nearly everything
and mean nothing. Spotting a frozen metric needs a comparison the evaluator
cannot make -- whether its siblings moved -- so it is deliberately left out
rather than shipped as a thing that cries wolf.

Second, every threshold is a pair: so many robust sigma AND so large a
fractional change. A sigma test alone is unusable here precisely because
constant history is common -- the median absolute deviation is then zero, and
any change at all is infinitely many sigma. `rel_min` is what stops that, and
`sigma_floor` is there for a metric whose units make a fractional test
awkward.

Scale is the median absolute deviation, scaled to be comparable with a
standard deviation, rather than the standard deviation itself: one bad point
in the window should not inflate the scale enough to mask the next ten.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional, Sequence, Tuple

from dqm.errors import DqmConfigError
from dqm.evaluate.base import LEVELS, Cause, Evaluator, Finding, Point

LOGGER = logging.getLogger("dqm.evaluate.trends")

__all__ = ["TrendsEvaluator", "CHECKS"]

CHECKS: Tuple[str, ...] = ("step", "drift")

# MAD * this estimates the standard deviation of a normal distribution. Named
# rather than inline so the 1.4826 is not a mystery number.
MAD_TO_SIGMA = 1.4826


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return 0.5 * (ordered[mid - 1] + ordered[mid])


def _mad_sigma(values: Sequence[float], centre: Optional[float] = None) -> float:
    """A robust standard-deviation estimate."""
    if not values:
        return 0.0
    mid = _median(values) if centre is None else centre
    return MAD_TO_SIGMA * _median([abs(v - mid) for v in values])


def _slope(values: Sequence[float]) -> float:
    """Slope per point, as the median of all pairwise slopes (Theil-Sen).

    Least squares was the first attempt and was wrong here: one bad point in
    the window tilts the fitted line enough to report a drift that is not
    there.  A single value of 99 among ten values of 10 produced a slope of
    -0.8 per point and a confident drift finding.

    The median of pairwise slopes ignores it -- most pairs are flat, so the
    median is flat -- at a cost in arithmetic that is irrelevant for a window
    of twenty points.
    """
    n = len(values)
    if n < 2:
        return 0.0
    slopes = [
        (values[j] - values[i]) / (j - i)
        for i in range(n - 1)
        for j in range(i + 1, n)
    ]
    return _median(slopes)


def _residual_sigma(values: Sequence[float], slope: float) -> float:
    """The robust scatter about the fitted line.

    This, not the spread of the window, is what a slope must be judged
    against.  A steadily rising series has a large spread *because* it is
    rising, so comparing the slope with that spread hides exactly the signal
    being looked for: a clean ramp from 10 to 14.5 was reported as no drift
    at all.  The scatter about the line is small for a clean ramp, which is
    what makes a real trend stand out.
    """
    if len(values) < 2:
        return 0.0
    level = _median([v - slope * i for i, v in enumerate(values)])
    return _mad_sigma([v - (level + slope * i) for i, v in enumerate(values)],
                      centre=0.0)


class TrendsEvaluator(Evaluator):
    """Compare each metric against its own recent history."""

    algo = "trends"
    subjects = CHECKS
    lookback = 20

    def configure(self) -> None:
        checks = self.pars.get("checks") or list(CHECKS)
        if isinstance(checks, str):
            checks = [checks]
        unknown = [c for c in checks if c not in CHECKS]
        if unknown:
            raise DqmConfigError(
                f"trends: unknown check(s) {unknown}; known: {list(CHECKS)}"
            )
        self._checks = tuple(checks)

        def number(name: str, default: float, minimum: float = 0.0) -> float:
            raw = self.pars.get(name, default)
            try:
                val = float(raw)
            except (TypeError, ValueError):
                raise DqmConfigError(f"trends: {name} must be a number, got {raw!r}")
            if val < minimum:
                raise DqmConfigError(f"trends: {name} cannot be below {minimum}")
            return val

        self._n_sigma = number("n_sigma", 5.0)
        self._rel_min = number("rel_min", 0.02)
        self._sigma_floor = number("sigma_floor", 0.0)
        self._min_history = int(number("min_history", 5, minimum=2))

        level = self.pars.get("level", LEVELS["warn"])
        if isinstance(level, str):
            if level not in LEVELS:
                raise DqmConfigError(
                    f"trends: level must be one of {sorted(LEVELS)} or 0-3, "
                    f"got {level!r}"
                )
            level = LEVELS[level]
        if int(level) not in range(4):
            raise DqmConfigError(f"trends: level must be 0-3, got {level!r}")
        self._level = int(level)

        metrics = self.pars.get("metrics") or []
        if not isinstance(metrics, (list, tuple)):
            raise DqmConfigError("trends: metrics must be a list")
        self._metrics = [str(m) for m in metrics]

    # -- internals ---------------------------------------------------------

    def _selected(self, point: Point) -> List[int]:
        if not self._metrics:
            return list(point.vids)
        return [
            vid for vid in point.vids
            if str(vid) in self._metrics or point.name(vid) in self._metrics
        ]

    def _series(self, vid: int, history: Sequence[Point]) -> List[float]:
        """This metric's usable values from the window, oldest first.

        Points where the producer flagged the measurement are left out: a
        lowStats or missing value is not evidence about a trend, and letting
        one into the scale would widen it for no reason.
        """
        out = []
        for p in history:
            m = p.get(vid)
            if m is not None and m.ok:
                out.append(float(m.valuex))
        return out

    def _scale(self, series: Sequence[float], history: Sequence[Point],
               vid: int) -> float:
        """How big a change has to be before it means anything.

        The largest of: the robust spread of the window, the metric's own
        quoted uncertainty, and the configured absolute floor. Taking the
        largest is deliberately conservative -- the alternative is a checker
        that fires whenever any of the three happens to be small.
        """
        robust = _mad_sigma(series)
        quoted = _median([abs(p[vid].sigma) for p in history
                          if vid in p and p[vid].ok] or [0.0])
        return max(robust, quoted, self._sigma_floor)

    def _exceeds(self, change: float, scale: float, centre: float) -> bool:
        """Both gates: statistically large, and fractionally large.

        Needing both is what makes this usable on metrics whose history is
        constant, where scale collapses to zero and the sigma test alone
        would pass for any change whatsoever.
        """
        big_enough = abs(change) > self._n_sigma * scale
        relative = abs(change) > self._rel_min * abs(centre) if centre else True
        return big_enough and relative

    # -- the check ---------------------------------------------------------

    def evaluate(self, point: Point, history: Sequence[Point] = ()) -> Sequence[Finding]:
        if len(history) < self._min_history:
            LOGGER.debug("%s: only %d point(s) of history, need %d -- skipping",
                         point.label, len(history), self._min_history)
            return []

        step_causes: List[Cause] = []
        drift_causes: List[Cause] = []
        step_detail: List[dict] = []
        drift_detail: List[dict] = []

        for vid in self._selected(point):
            m = point.get(vid)
            if m is None or not m.ok:
                continue
            series = self._series(vid, history)
            if len(series) < self._min_history:
                continue

            centre = _median(series)
            scale = self._scale(series, history, vid)

            if "step" in self._checks:
                change = float(m.valuex) - centre
                if self._exceeds(change, scale, centre):
                    step_causes.append(point.cause(vid, level=self._level))
                    step_detail.append({
                        "metric": point.name(vid), "vid": vid,
                        "value": float(m.valuex), "baseline": centre,
                        "change": change, "scale": scale,
                        "n_history": len(series),
                    })

            if "drift" in self._checks:
                # The slope over the window, expressed as the total change
                # across it, so the threshold means the same thing whatever
                # the window length.
                full = series + [float(m.valuex)]
                slope = _slope(full)
                span = slope * (len(full) - 1)
                # Judged against the scatter about the line, not the spread
                # of the window -- see _residual_sigma.
                drift_scale = max(_residual_sigma(full, slope),
                                  _median([abs(p[vid].sigma) for p in history
                                           if vid in p and p[vid].ok] or [0.0]),
                                  self._sigma_floor)
                if self._exceeds(span, drift_scale, centre):
                    drift_causes.append(point.cause(vid, level=self._level))
                    drift_detail.append({
                        "metric": point.name(vid), "vid": vid,
                        "span": span, "baseline": centre, "scale": drift_scale,
                        "n_history": len(series),
                        "direction": "up" if span > 0 else "down",
                    })

        findings: List[Finding] = []

        # One finding per subject, per spec rule (b): every metric that
        # stepped is a cause of the same "step" finding, not a finding of its
        # own, because two findings with one subject collide on alarm
        # identity.
        if step_causes:
            worst = max(step_detail, key=lambda d: abs(d["change"]))
            LOGGER.info(
                "%s: %d metric(s) stepped -- worst %s %.4g -> %.4g (%.1f x scale)",
                point.label, len(step_causes), worst["metric"].split("/")[-1],
                worst["baseline"], worst["value"],
                abs(worst["change"]) / worst["scale"] if worst["scale"] else float("inf"),
            )
            findings.append(self.finding("step", *step_causes,
                                         note=json.dumps({"step": step_detail})))

        if drift_causes:
            worst = max(drift_detail, key=lambda d: abs(d["span"]))
            LOGGER.info(
                "%s: %d metric(s) drifting -- worst %s %s by %.4g over %d points",
                point.label, len(drift_causes), worst["metric"].split("/")[-1],
                worst["direction"], abs(worst["span"]), worst["n_history"] + 1,
            )
            findings.append(self.finding("drift", *drift_causes,
                                         note=json.dumps({"drift": drift_detail})))

        if not findings:
            # Debug, not info: the driver logs one "clean" line per point for
            # every evaluator, and saying it twice makes a tailed log noise.
            LOGGER.debug("%s: no trend (%d metrics, %d points of history)",
                         point.label, len(self._selected(point)), len(history))
        return findings
