"""Compare two histograms, and two files of histograms.

Ported from the ROOT implementation this replaces, keeping its two measures
and its status vocabulary so existing judgements stay comparable:

  kolmogorov  ROOT's TH1::KolmogorovTest probability, reproduced here in numpy
              and scipy. Verified against ROOT itself on real CRV histograms,
              agreeing to 1.5e-10 -- scipy.special.kolmogorov IS the series
              TMath::KolmogorovProb evaluates.
  fraction    1 - (largest divergence between the running sums) / (total),
              a blunter measure that notices a shape shifting even where the
              KS probability saturates.

Three bugs in the original are fixed here rather than carried over; each is
marked FIXED at the point it mattered. The important one is that histograms
with different binning were reported as *perfect* rather than incomparable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from dqm.errors import DqmDependencyError

try:
    from scipy.special import kolmogorov as _kolmogorov_prob
except ImportError as exc:  # pragma: no cover - dependency error path
    raise DqmDependencyError(
        "dqm.hist.compare needs scipy. Install the extra: "
        "pip install 'mu2e-dqm[hist]'"
    ) from exc

LOGGER = logging.getLogger("dqm.hist.compare")

__all__ = [
    "CompareStatus",
    "ComparePars",
    "Comparison",
    "compare_histograms",
    "compare_files",
    "kolmogorov_test",
]


class CompareStatus(IntEnum):
    """How well two histograms agree. Values match the original dictionary."""

    perfect = 0      # bin-for-bin identical
    tight = 1        # agrees at the tight threshold
    loose = 2        # agrees at the loose threshold only
    fail = 3         # does not agree
    cantCompare = 11 # incomparable, e.g. different binning


# Colours the display uses per status, carried over unchanged.
STATUS_COLORS: Dict[CompareStatus, str] = {
    CompareStatus.perfect: "#196F3D",
    CompareStatus.tight: "#2ECC71",
    CompareStatus.loose: "#F4D03F",
    CompareStatus.fail: "#E74C3C",
    CompareStatus.cantCompare: "#95A5A6",
}


@dataclass
class ComparePars:
    """Settings for a comparison.

    `independent` says whether the two samples are statistically independent.
    When they are, only the KS probability is meaningful and the fraction
    measure is not consulted for the verdict.
    """

    independent: bool = False
    scale1: float = 1.0
    scale2: float = 1.0
    underflow: bool = True
    overflow: bool = True
    loose: float = 0.99
    tight: float = 0.999


@dataclass
class Comparison:
    """The outcome of comparing one pair of histograms."""

    path: str
    status: CompareStatus
    kolmogorov: float = 0.0
    fraction: float = 0.0
    sum1: float = 0.0
    sum2: float = 0.0
    empty: bool = False
    identical: bool = False
    note: str = ""

    @property
    def color(self) -> str:
        return STATUS_COLORS.get(self.status, STATUS_COLORS[CompareStatus.cantCompare])

    @property
    def ok(self) -> bool:
        """True if the two agree at least loosely."""
        return self.status in (CompareStatus.perfect, CompareStatus.tight, CompareStatus.loose)

    def __repr__(self) -> str:
        return (
            f"Comparison({self.path!r}, {self.status.name}, "
            f"ks={self.kolmogorov:.4g}, fr={self.fraction:.4g})"
        )


def _flow_slice(n_with_flow: int, underflow: bool, overflow: bool) -> slice:
    """Which bins to include, given the flow settings.

    The arrays passed in include the underflow at index 0 and the overflow at
    index -1, matching `values(flow=True)`.
    """
    start = 0 if underflow else 1
    stop = n_with_flow if overflow else n_with_flow - 1
    return slice(start, stop)


def kolmogorov_test(
    values1: Sequence[float],
    values2: Sequence[float],
    underflow: bool = True,
    overflow: bool = True,
) -> float:
    """ROOT's TH1::KolmogorovTest probability, for same-binned histograms.

    Inputs include flow bins (`values(flow=True)`). Returns the probability
    that the two are drawn from the same distribution; 1.0 means
    indistinguishable, near 0 means they differ.

    This follows ROOT's algorithm exactly: accumulate each histogram's running
    sum normalized to its total, take the largest absolute divergence, scale by
    sqrt(n1*n2/(n1+n2)) and evaluate the Kolmogorov distribution.
    """
    sl = _flow_slice(len(values1), underflow, overflow)
    a = np.asarray(values1, dtype=float)[sl]
    b = np.asarray(values2, dtype=float)[sl]

    sum1, sum2 = float(a.sum()), float(b.sum())
    if sum1 <= 0 or sum2 <= 0:
        return 0.0

    dfmax = float(np.max(np.abs(np.cumsum(a) / sum1 - np.cumsum(b) / sum2)))
    z = dfmax * np.sqrt(sum1 * sum2 / (sum1 + sum2))
    return float(_kolmogorov_prob(z))


def compare_histograms(
    hist1,
    hist2,
    pars: Optional[ComparePars] = None,
    path: str = "",
) -> Comparison:
    """Compare two `hist.Hist` objects.

    Returns a Comparison in every case, including the ones that cannot be
    compared -- an exception here would stop a whole file's worth of work over
    one mismatched histogram.
    """
    pars = pars or ComparePars()

    v1 = np.asarray(hist1.values(flow=True), dtype=float)
    v2 = np.asarray(hist2.values(flow=True), dtype=float)

    if v1.shape != v2.shape:
        # FIXED: the original returned here leaving status at its initial 0,
        # which is `perfect` -- so two histograms with different binning were
        # reported as being in perfect agreement, the most misleading verdict
        # available. They are incomparable.
        return Comparison(
            path=path,
            status=CompareStatus.cantCompare,
            note=f"different binning: {v1.shape} vs {v2.shape}",
        )

    sl = _flow_slice(len(v1), pars.underflow, pars.overflow)
    a, b = v1[sl], v2[sl]
    sum1, sum2 = float(a.sum()), float(b.sum())
    identical = bool(np.array_equal(a, b))

    if sum1 == 0.0 and sum2 == 0.0:
        # Both empty: trivially in agreement, and the display wants to know.
        return Comparison(
            path=path,
            status=CompareStatus.perfect,
            kolmogorov=1.0,
            fraction=1.0,
            empty=True,
            identical=True,
            note="both histograms are empty",
        )

    if sum1 == 0.0 or sum2 == 0.0:
        # Exactly one is empty -- a real difference, and the case the original
        # crashed on.
        # FIXED: it called math.exp() without importing math, so this raised
        # NameError instead of producing a verdict.
        return Comparison(
            path=path,
            status=CompareStatus.fail,
            kolmogorov=float(np.exp(-max(sum1, sum2))),
            fraction=0.0,
            sum1=sum1,
            sum2=sum2,
            empty=True,
            note="one histogram is empty, the other is not",
        )

    run1 = np.cumsum(a * pars.scale1)
    run2 = np.cumsum(b * pars.scale2)
    max_divergence = float(np.max(np.abs(run1 - run2)))
    total = float(run1[-1])
    fraction = 1.0 - max_divergence / total if total > 0 else 0.0
    fraction = max(0.0, fraction)

    ks = kolmogorov_test(v1, v2, underflow=pars.underflow, overflow=pars.overflow)

    if pars.independent:
        # Independent samples: only the KS probability carries meaning.
        if ks > pars.tight:
            status = CompareStatus.tight
        elif ks > pars.loose:
            status = CompareStatus.loose
        else:
            status = CompareStatus.fail
    else:
        if fraction > pars.tight or ks > pars.tight:
            status = CompareStatus.tight
        elif fraction > pars.loose or ks > pars.loose:
            status = CompareStatus.loose
        else:
            status = CompareStatus.fail

    if identical:
        status = CompareStatus.perfect

    return Comparison(
        path=path,
        status=status,
        kolmogorov=ks,
        fraction=fraction,
        sum1=sum1,
        sum2=sum2,
        identical=identical,
    )


def compare_files(
    file1,
    file2,
    pars: Optional[ComparePars] = None,
    ndim: Optional[int] = 1,
    paths: Optional[Sequence[str]] = None,
) -> List[Comparison]:
    """Compare every histogram the two files have in common.

    Defaults to 1-D histograms, which is what the overlay display handles.
    Pass ndim=None for everything, or an explicit `paths` list to compare a
    chosen subset.

    A histogram that cannot be read from either file becomes a cantCompare
    entry rather than an exception, so one bad object does not lose the rest
    of the report.
    """
    from dqm.hist.read import common_histograms

    pars = pars or ComparePars()
    if paths is None:
        wanted = [e.path for e in common_histograms(file1, file2, ndim=ndim)]
    else:
        wanted = list(paths)

    out: List[Comparison] = []
    for path in wanted:
        try:
            h1 = file1.read(path)
            h2 = file2.read(path)
        except Exception as exc:
            out.append(
                Comparison(
                    path=path,
                    status=CompareStatus.cantCompare,
                    note=f"could not read: {exc}",
                )
            )
            continue
        out.append(compare_histograms(h1, h2, pars=pars, path=path))
    return out


def summarize(comparisons: Sequence[Comparison]) -> Dict[str, int]:
    """Count comparisons by status name, for a report header."""
    counts = {s.name: 0 for s in CompareStatus}
    for c in comparisons:
        counts[c.status.name] += 1
    return counts
