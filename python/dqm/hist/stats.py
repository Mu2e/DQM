"""Histogram statistics that match what ROOT reports.

This exists because the obvious implementation is wrong. ROOT's GetMean does
not recompute the mean from bin centres -- it returns a running sum maintained
at fill time (fTsumw, fTsumwx, fTsumwx2), which retains the within-bin
positions of the entries and so differs from the binned estimate. On a real
CRV histogram the two disagree by 0.017, and since these numbers are written
to the database as metrics, computing them the easy way would silently shift
every value away from what the existing rows hold.

So: read the accumulators when they are valid, and fall back to the binned
estimate only when they are not -- which is what ROOT itself does for a
histogram filled through SetBinContent rather than Fill.

Verified against ROOT 6.40: mean, standard deviation and mean error all agree
to full double precision.

These take the uproot object rather than a `hist.Hist`, because converting to
Hist keeps the bin contents and drops the accumulators.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional, Tuple

import numpy as np

LOGGER = logging.getLogger("dqm.hist.stats")

__all__ = ["HistStats", "statistics", "stats_lines"]


@dataclass(frozen=True)
class HistStats:
    """Summary statistics for a 1-D histogram, as ROOT would report them."""

    entries: float
    mean: float
    mean_error: float
    std_dev: float
    std_dev_error: float
    integral: float
    effective_entries: float
    from_accumulators: bool  # False if derived from bin contents instead

    def __repr__(self) -> str:
        return (
            f"HistStats(entries={self.entries:.0f}, mean={self.mean:.6g}, "
            f"std={self.std_dev:.6g})"
        )


def _member(obj: Any, name: str) -> Optional[float]:
    try:
        value = obj.member(name, none_if_missing=True)
    except Exception:
        return None
    return None if value is None else float(value)


def statistics(obj: Any, hist=None) -> HistStats:
    """Statistics for a histogram, preferring ROOT's fill-time accumulators.

    `obj` is the uproot object. `hist` is an optional already-converted Hist,
    used only for the fallback path and to save a conversion.
    """
    sumw = _member(obj, "fTsumw")
    sumw2 = _member(obj, "fTsumw2")
    sumwx = _member(obj, "fTsumwx")
    sumwx2 = _member(obj, "fTsumwx2")
    entries = _member(obj, "fEntries") or 0.0

    have_accumulators = bool(sumw) and sumwx is not None and sumwx2 is not None

    if have_accumulators:
        mean = sumwx / sumw
        variance = sumwx2 / sumw - mean * mean
        # Rounding can push a variance that should be zero slightly negative.
        std = float(np.sqrt(variance)) if variance > 0 else 0.0
        # ROOT's effective entries is (sum w)^2 / (sum w^2); for unweighted
        # fills that is just the number of entries.
        neff = (sumw * sumw / sumw2) if sumw2 else sumw
        integral = sumw
    else:
        # The histogram was filled by setting bin contents, so no accumulators
        # were maintained and the binned estimate is all there is -- the same
        # fallback ROOT applies.
        if hist is None:
            hist = obj.to_hist()
        values = np.asarray(hist.values(), dtype=float)
        centers = np.asarray(hist.axes[0].centers, dtype=float)
        total = float(values.sum())
        if total <= 0:
            return HistStats(entries, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False)
        mean = float((values * centers).sum() / total)
        variance = float((values * (centers - mean) ** 2).sum() / total)
        std = float(np.sqrt(variance)) if variance > 0 else 0.0
        neff = total
        integral = total

    mean_error = std / np.sqrt(neff) if neff > 0 else 0.0
    # ROOT's GetStdDevError for the unweighted case.
    std_error = std / np.sqrt(2.0 * neff) if neff > 0 else 0.0

    return HistStats(
        entries=entries,
        mean=float(mean),
        mean_error=float(mean_error),
        std_dev=float(std),
        std_dev_error=float(std_error),
        integral=float(integral),
        effective_entries=float(neff),
        from_accumulators=have_accumulators,
    )


def edges_above(hist, threshold: float = 0.0) -> Tuple[Optional[int], Optional[int]]:
    """Indices of the first and last bins above `threshold`.

    The equivalent of ROOT's FindFirstBinAbove / FindLastBinAbove, returning
    0-based indices into the no-flow arrays, or (None, None) if no bin
    qualifies.
    """
    values = np.asarray(hist.values(), dtype=float)
    above = np.nonzero(values > threshold)[0]
    if above.size == 0:
        return None, None
    return int(above[0]), int(above[-1])


def stats_lines(obj: Any, hist=None, name: str = "") -> list:
    """The lines of a ROOT-style statistics box.

    Matches what gStyle.SetOptStat(1111) displays, so a rendered plot carries
    the same summary a ROOT canvas would. Shared by both renderers, which is
    what keeps the interactive and static versions of a figure saying the same
    thing.
    """
    st = statistics(obj, hist=hist)
    lines = []
    if name:
        lines.append(name)
    lines.append(f"Entries  {st.entries:.0f}")
    lines.append(f"Mean     {st.mean:.4g}")
    lines.append(f"Std Dev  {st.std_dev:.4g}")
    return lines
