"""What to draw, described independently of how it gets drawn.

DQM needs the same figure twice: interactive in the browser, and as a static
image for a note, an elog post or a report. Writing each figure twice is how
the two versions quietly stop agreeing -- one gains an overlay the other
lacks, a threshold line moves in one and not the other.

So a figure is built once as a `PlotSpec`, which holds histograms, fit curves,
reference lines and labels, and knows nothing about plotly or matplotlib.
Each renderer is then a thin translation of that structure, and content lives
in exactly one place.

    spec = PlotSpec(title="crvPEsMPV sector 0")
    spec.add_hist(h, label="run 125086")
    spec.add_fit(fit, label="gaussian")

    to_plotly(spec)                    # -> a figure for the app
    save_image(spec, "report.pdf")     # -> a file for the note

Colours are named here, not resolved: a renderer maps a name through its own
palette so both come out looking native. Passing an explicit colour overrides
that, for the cases where a specific one carries meaning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

__all__ = [
    "HistTrace",
    "SeriesTrace",
    "FitTrace",
    "LineMarker",
    "PlotSpec",
    "PALETTE",
    "hist_points",
]

# The default colour cycle, applied in order to traces that do not name one.
# Chosen to stay distinguishable in grayscale print and for the most common
# forms of colour blindness -- a report may well be printed.
PALETTE: Tuple[str, ...] = (
    "#1f77b4",  # blue
    "#d62728",  # red
    "#2ca02c",  # green
    "#ff7f0e",  # orange
    "#9467bd",  # purple
    "#8c564b",  # brown
)


def hist_points(h) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """A 1-D histogram as plain arrays: centres, values, errors, edges.

    The single place a Hist is unpacked for drawing, so both renderers see
    identical numbers. Errors come from the stored variances when present,
    falling back to sqrt(N) -- which is what a histogram of counts means
    anyway, but being explicit avoids each renderer inventing its own answer.
    """
    centers = np.asarray(h.axes[0].centers, dtype=float)
    edges = np.asarray(h.axes[0].edges, dtype=float)
    values = np.asarray(h.values(), dtype=float)
    variances = h.variances()
    if variances is None:
        errors = np.sqrt(np.clip(values, 0, None))
    else:
        errors = np.sqrt(np.clip(np.asarray(variances, dtype=float), 0, None))
    return centers, values, errors, edges


@dataclass
class HistTrace:
    """One histogram to draw.

    `style` is "step" for an outline, "errorbar" for points with error bars,
    or "fill" for a filled area. The overlay display uses step for the
    reference and errorbar for what is being compared against it, matching the
    ROOT convention of drawing one as HIST and the other as E1 P.
    """

    hist: Any
    label: str = ""
    color: Optional[str] = None
    style: str = "step"
    alpha: float = 1.0
    stats: Optional[List[str]] = None  # lines for a statistics box

    def points(self):
        return hist_points(self.hist)


@dataclass
class SeriesTrace:
    """A plain x/y series with optional error bars.

    What a timeline is: a metric against time or run number, which is not a
    histogram and so cannot be a HistTrace. Keeping it in the same spec means
    timelines get static export on the same terms as histograms -- a trend
    plot is exactly the kind of figure a report wants.

    `x` may be datetimes; both renderers handle that natively.
    """

    x: Any
    y: Any
    yerr: Optional[Any] = None
    label: str = ""
    color: Optional[str] = None
    style: str = "markers"  # "markers", "lines", or "lines+markers"

    @property
    def is_datetime(self) -> bool:
        """True if x is a time axis.

        Checked through pandas rather than numpy: np.asarray on a tz-aware
        pandas Series yields dtype=object, so np.issubdtype(..., datetime64)
        is False even though the values are timestamps. Getting this wrong
        leaves date tick labels unrotated and overlapping.
        """
        try:
            import pandas as pd

            return bool(pd.api.types.is_datetime64_any_dtype(self.x))
        except Exception:
            return np.issubdtype(np.asarray(self.x).dtype, np.datetime64)

    def arrays(self):
        """The three arrays, with x left alone when it is a time axis.

        Both renderers consume pandas datetime series natively; converting
        would only lose the timezone and the dtype.
        """
        x = self.x if self.is_datetime else np.asarray(self.x)
        y = np.asarray(self.y, dtype=float)
        err = None if self.yerr is None else np.asarray(self.yerr, dtype=float)
        return x, y, err


@dataclass
class FitTrace:
    """A fitted curve to draw over the histograms.

    Holds a dqm.hist.FitResult. A fit whose formula cannot be reconstructed
    still contributes its parameters to the annotation -- only the curve is
    omitted. See FitResult.can_evaluate.
    """

    fit: Any
    label: str = ""
    color: Optional[str] = None
    npoints: int = 300
    show_params: bool = True

    def curve(self, xlim: Tuple[float, float]):
        """The curve sampled across `xlim`, or None if it cannot be drawn."""
        if not getattr(self.fit, "can_evaluate", False):
            return None
        xs = np.linspace(xlim[0], xlim[1], self.npoints)
        try:
            return xs, np.asarray(self.fit.evaluate(xs), dtype=float)
        except Exception:
            # A fit that will not evaluate should not take the whole figure
            # down -- the histograms are still worth showing.
            return None

    def annotation(self) -> List[str]:
        if not self.show_params or self.fit is None:
            return []
        return list(self.fit.summary())


@dataclass
class LineMarker:
    """A horizontal or vertical reference line -- a limit, a threshold.

    `orientation` is "v" or "h". The alarm and timeline displays use these to
    show the acceptable band from dqm.limits.
    """

    position: float
    orientation: str = "v"
    label: str = ""
    color: str = "#888888"
    dash: bool = True


@dataclass
class PlotSpec:
    """A complete figure, renderer-independent."""

    title: str = ""
    xlabel: str = ""
    ylabel: str = ""
    traces: List[HistTrace] = field(default_factory=list)
    series: List[SeriesTrace] = field(default_factory=list)
    fits: List[FitTrace] = field(default_factory=list)
    lines: List[LineMarker] = field(default_factory=list)
    logx: bool = False
    logy: bool = False
    xlim: Optional[Tuple[float, float]] = None
    ylim: Optional[Tuple[float, float]] = None
    legend: bool = True
    annotations: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------- building

    def add_hist(self, h, label: str = "", color: Optional[str] = None,
                 style: str = "step", alpha: float = 1.0,
                 stats: Optional[List[str]] = None) -> "PlotSpec":
        """Add a histogram. Returns self, so calls can be chained."""
        self.traces.append(
            HistTrace(hist=h, label=label, color=color, style=style,
                      alpha=alpha, stats=stats)
        )
        return self

    def add_series(self, x, y, yerr=None, label: str = "",
                   color: Optional[str] = None,
                   style: str = "markers") -> "PlotSpec":
        """Add an x/y series -- a timeline, or any non-histogram curve."""
        self.series.append(
            SeriesTrace(x=x, y=y, yerr=yerr, label=label, color=color, style=style)
        )
        return self

    def add_fit(self, fit, label: str = "", color: Optional[str] = None,
                show_params: bool = True) -> "PlotSpec":
        """Add a fitted curve."""
        self.fits.append(
            FitTrace(fit=fit, label=label or getattr(fit, "model", "fit"),
                     color=color, show_params=show_params)
        )
        return self

    def add_line(self, position: float, orientation: str = "v",
                 label: str = "", color: str = "#888888",
                 dash: bool = True) -> "PlotSpec":
        """Add a reference line -- a limit or a threshold."""
        self.lines.append(
            LineMarker(position=position, orientation=orientation,
                       label=label, color=color, dash=dash)
        )
        return self

    def add_band(self, low: float, high: float, label: str = "",
                 color: str = "#888888") -> "PlotSpec":
        """Add a pair of lines marking an acceptable range.

        The shape dqm.limits rows take: llimit and ulimit around a value.
        """
        self.add_line(low, "h", label=label, color=color)
        self.add_line(high, "h", label="", color=color)
        return self

    # -------------------------------------------------------------- queries

    def color_for(self, index: int, explicit: Optional[str]) -> str:
        """The colour for trace `index`, honouring an explicit choice.

        Histograms and series share one cycle, so a figure holding both does
        not draw two different things in the same colour.
        """
        return explicit or PALETTE[index % len(PALETTE)]

    def data_xlim(self) -> Tuple[float, float]:
        """The x range covered by the histograms, for sampling fit curves."""
        if self.xlim is not None:
            return self.xlim
        los, his = [], []
        for t in self.traces:
            edges = np.asarray(t.hist.axes[0].edges, dtype=float)
            los.append(float(edges[0]))
            his.append(float(edges[-1]))
        if not los:
            # No histograms: a series-only figure (a timeline) has no bin
            # edges to take a range from, and nothing here needs one -- fit
            # curves are drawn over histograms.
            return (0.0, 1.0)
        return (min(los), max(his))

    def all_annotations(self) -> List[str]:
        """Annotation lines plus every fit's parameter summary."""
        out = list(self.annotations)
        for f in self.fits:
            out.extend(f.annotation())
        return out

    def is_empty(self) -> bool:
        return not self.traces and not self.fits and not self.series

    def __repr__(self) -> str:
        return (
            f"PlotSpec({self.title!r}, {len(self.traces)} hist, "
            f"{len(self.series)} series, {len(self.fits)} fit, "
            f"{len(self.lines)} line)"
        )
