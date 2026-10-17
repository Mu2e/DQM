"""Render a PlotSpec with matplotlib, for reports and posts.

The counterpart to dqm.plot.interactive: same spec, same content, a file
instead of a browser figure. mplhep supplies the HEP conventions -- inward
ticks, the right aspect, no chartjunk -- so output looks like it belongs in a
note rather than in a dashboard.

PDF and SVG are vector, which is what a document wants; PNG is there for
places that only take a bitmap.

A deployment note that will bite otherwise: matplotlib caches its font list
under MPLCONFIGDIR, defaulting to the user's home. A service account whose
home is read-only or over quota gets a warning and a full font rescan on every
single call. `ensure_config_dir` below handles it; a systemd unit should set
MPLCONFIGDIR explicitly to somewhere writable.
"""

from __future__ import annotations

import logging
import os
import tempfile
from io import BytesIO
from typing import Any, Optional, Tuple

import numpy as np

from dqm.errors import DqmDependencyError
from dqm.plot.spec import PlotSpec

LOGGER = logging.getLogger("dqm.plot.static")


def ensure_config_dir() -> None:
    """Point MPLCONFIGDIR somewhere writable if it is not already set.

    Called before matplotlib is imported. Without it, a service account with
    an unwritable home rebuilds the font cache on every render -- which turns
    a fast operation into a slow one without ever failing outright, so it is
    easy to miss.
    """
    if os.environ.get("MPLCONFIGDIR"):
        return
    home = os.path.expanduser("~")
    if os.access(home, os.W_OK):
        return
    path = os.path.join(tempfile.gettempdir(), f"mpl-{os.getuid()}")
    os.makedirs(path, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = path
    LOGGER.debug("set MPLCONFIGDIR=%s (home is not writable)", path)


ensure_config_dir()

try:
    import matplotlib

    # Agg before pyplot: these run headless, in a web process or a batch job,
    # and any GUI backend would try to reach a display that is not there.
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError as exc:  # pragma: no cover - dependency error path
    raise DqmDependencyError(
        "dqm.plot.static needs matplotlib. Install the extra: "
        "pip install 'mu2e-dqm[plot]'"
    ) from exc

try:
    import mplhep as hep

    _HAVE_MPLHEP = True
except ImportError:  # pragma: no cover - optional styling
    _HAVE_MPLHEP = False

__all__ = ["to_matplotlib", "to_matplotlib_grid", "save_image",
           "save_image_grid", "to_png_bytes", "to_data_uri", "STYLES"]

# Named styles, so callers do not have to know mplhep's own vocabulary.
STYLES = ("root", "plain")


def _apply_style(style: str) -> None:
    """Select the figure style.

    matplotlib's rcParams are process-global, so "plain" has to actively
    restore the defaults rather than simply decline to apply the ROOT style --
    otherwise a ROOT-styled figure rendered earlier in the process leaves its
    settings behind and "plain" silently keeps them.
    """
    if style == "plain" or not _HAVE_MPLHEP:
        plt.style.use("default")
        return
    plt.style.use(hep.style.ROOT)


# Beyond this many characters an axis label is wrapped. DQM metric names are
# paths like "CRV/crvPEsMPV_CRVsector0/Centroid", which are routinely longer
# than the axis they label.
_LABEL_WRAP = 26

# Panel height the stylesheet's type size is assumed to suit, and the floor
# below which shrinking type further makes it unreadable rather than tidy.
_REFERENCE_PANEL_INCHES = 5.0
_MIN_FONT_SCALE = 0.45


def _wrap_label(text: str, width: int = _LABEL_WRAP) -> str:
    """Break a long axis label across lines, preferring path separators.

    textwrap is no use here: these names contain no spaces, so it returns them
    unbroken. Left unwrapped under the ROOT style -- which anchors axis labels
    at the end of the axis rather than centring them -- a long label overruns
    the axes, and `bbox_inches="tight"` then grows the saved image to contain
    it. A 33-character y label was inflating a 9x5 figure to a 1261x1048 image
    that was more than a third empty.
    """
    if len(text) <= width:
        return text
    # Keep the separator on the end of the segment it follows, so a reader can
    # see the name continues rather than guessing where the break fell.
    parts, buf = [], ""
    for seg in text.replace("/", "/\n").split("\n"):
        if buf and len(buf) + len(seg) > width:
            parts.append(buf)
            buf = seg
        else:
            buf += seg
    if buf:
        parts.append(buf)
    return "\n".join(parts)


def _draw(fig, ax, spec: PlotSpec, show_xlabel: bool = True) -> None:
    """Render one spec onto one axes.

    Shared by to_matplotlib and to_matplotlib_grid, so a panel of a stack is
    drawn by exactly the same code as a standalone figure.
    """
    for i, trace in enumerate(spec.traces):
        centers, values, errors, edges = trace.points()
        color = spec.color_for(i, trace.color)
        label = trace.label or None

        if trace.style == "errorbar":
            ax.errorbar(centers, values, yerr=errors, fmt="o", markersize=3,
                        color=color, label=label, alpha=trace.alpha,
                        elinewidth=1, capsize=0)
        elif trace.style == "fill":
            ax.stairs(values, edges, fill=True, color=color, label=label,
                      alpha=trace.alpha * 0.6)
        else:  # "step"
            ax.stairs(values, edges, color=color, label=label,
                      alpha=trace.alpha, linewidth=1.4)

    for k, strace in enumerate(spec.series):
        x, y, err = strace.arrays()
        color = spec.color_for(len(spec.traces) + k, strace.color)
        label = strace.label or None
        if err is not None:
            ax.errorbar(x, y, yerr=err, fmt="o" if strace.style == "markers" else "-o",
                        markersize=4, color=color, label=label, elinewidth=1, capsize=0)
        elif strace.style == "lines":
            ax.plot(x, y, "-", color=color, label=label, linewidth=1.5)
        elif strace.style == "markers":
            ax.plot(x, y, "o", color=color, label=label, markersize=4)
        else:
            ax.plot(x, y, "-o", color=color, label=label, markersize=4, linewidth=1.5)
    if any(s_.is_datetime for s_ in spec.series):
        # Date labels overlap illegibly otherwise -- see SeriesTrace.is_datetime
        # for why the obvious numpy check does not detect this.
        fig.autofmt_xdate()

    xlim = spec.data_xlim()
    for ftrace in spec.fits:
        curve = ftrace.curve(xlim)
        if curve is None:
            continue
        xs, ys = curve
        ax.plot(xs, ys, color=ftrace.color or "#ff7f0e", linewidth=2,
                label=ftrace.label or "fit")

    for line in spec.lines:
        style_kw = dict(color=line.color, linestyle="--" if line.dash else "-",
                        linewidth=1)
        if line.orientation == "v":
            ax.axvline(line.position, **style_kw)
            if line.label:
                ax.annotate(line.label, xy=(line.position, 0.98),
                            xycoords=("data", "axes fraction"),
                            fontsize=8, rotation=90, va="top", ha="right")
        else:
            ax.axhline(line.position, **style_kw)
            if line.label:
                ax.annotate(line.label, xy=(0.99, line.position),
                            xycoords=("axes fraction", "data"),
                            fontsize=8, va="bottom", ha="right")

    notes = spec.all_annotations()
    if notes:
        ax.text(
            0.97, 0.97, "\n".join(notes),
            transform=ax.transAxes, ha="right", va="top",
            fontsize=8, family="monospace",
            bbox=dict(boxstyle="square,pad=0.4", facecolor="white",
                      edgecolor="#999999", alpha=0.85),
        )

    if spec.title:
        ax.set_title(_wrap_label(spec.title, _LABEL_WRAP * 2))
    if spec.xlabel and show_xlabel:
        ax.set_xlabel(_wrap_label(spec.xlabel))
    if spec.ylabel:
        label = _wrap_label(spec.ylabel)
        # Centre a wrapped label. The ROOT style anchors axis labels at the
        # end of the axis, which reads well for a short name and pushes a
        # multi-line one off the top.
        ax.set_ylabel(label, loc="center" if "\n" in label else None)
    if spec.logx:
        ax.set_xscale("log")
    if spec.logy:
        ax.set_yscale("log")
    if spec.xlim:
        ax.set_xlim(*spec.xlim)
    if spec.ylim:
        ax.set_ylim(*spec.ylim)
    has_labels = (any(t.label for t in spec.traces)
                  or any(s_.label for s_ in spec.series)
                  or any(f.label for f in spec.fits))
    if spec.legend and has_labels:
        ax.legend(loc="best", frameon=False)


def to_matplotlib(
    spec: PlotSpec,
    figsize: Tuple[float, float] = (7.0, 5.0),
    style: str = "root",
    dpi: int = 150,
):
    """Build a matplotlib Figure from a PlotSpec.

    Returns (figure, axes). The caller is responsible for closing the figure;
    save_image does that for you.
    """
    _apply_style(style)
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    _draw(fig, ax, spec)
    fig.tight_layout()
    return fig, ax


def to_matplotlib_grid(
    specs,
    width: float = 9.0,
    height_each: float = 3.0,
    style: str = "root",
    dpi: int = 150,
    shared_x: bool = True,
):
    """Stack several specs as panels of one figure, sharing the x axis.

    The static counterpart of to_plotly_grid, so a page of stacked timelines
    exports as one image for a note rather than several to be assembled by
    hand. Each panel keeps its own y axis.
    """
    _apply_style(style)
    specs = list(specs)
    if not specs:
        fig, ax = plt.subplots(figsize=(width, height_each), dpi=dpi)
        return fig, [ax]

    # The ROOT style sets font.size=26 for its reference 10x10 figure. A panel
    # a couple of inches tall gets the same 26pt labels, which overflow it and
    # collide with the panels above and below. Scale type to the panel rather
    # than leaving it sized for a figure ten times the height.
    scale = max(_MIN_FONT_SCALE, min(1.0, height_each / _REFERENCE_PANEL_INCHES))
    overrides = {"font.size": plt.rcParams["font.size"] * scale}

    # rc_context rather than assignment: rcParams are process-global, and a
    # grid render must not shrink the type of every figure drawn afterwards.
    with plt.rc_context(overrides):
        fig, axes = plt.subplots(
            len(specs), 1, figsize=(width, height_each * len(specs)), dpi=dpi,
            sharex=shared_x, squeeze=False,
        )
        axes = [a[0] for a in axes]
        for i, (spec, ax) in enumerate(zip(specs, axes)):
            # x label on the bottom panel only; the axes are shared, so
            # repeating it between panels only uses up vertical space.
            _draw(fig, ax, spec, show_xlabel=(i == len(specs) - 1))
        fig.tight_layout()
    return fig, axes


def save_image(
    spec: PlotSpec,
    path: str,
    figsize: Tuple[float, float] = (7.0, 5.0),
    style: str = "root",
    dpi: int = 150,
) -> str:
    """Render a spec straight to a file. Format comes from the extension.

    PDF and SVG are vector and are what a note or paper should use; PNG suits
    anywhere that only accepts a bitmap.
    """
    fig, _ = to_matplotlib(spec, figsize=figsize, style=style, dpi=dpi)
    try:
        fig.savefig(path, dpi=dpi, bbox_inches="tight")
    finally:
        # Figures hold memory until closed, and a long-running web process
        # renders a great many of them.
        plt.close(fig)
    return path


def save_image_grid(
    specs,
    path: str,
    width: float = 9.0,
    height_each: float = 3.0,
    style: str = "root",
    dpi: int = 150,
) -> str:
    """Render a stack of specs straight to a file."""
    fig, _ = to_matplotlib_grid(specs, width=width, height_each=height_each,
                                style=style, dpi=dpi)
    try:
        fig.savefig(path, dpi=dpi, bbox_inches="tight")
    finally:
        plt.close(fig)
    return path


def to_png_bytes(
    spec: PlotSpec,
    figsize: Tuple[float, float] = (7.0, 5.0),
    style: str = "root",
    dpi: int = 150,
) -> bytes:
    """Render to PNG bytes, for serving over HTTP without a temporary file."""
    fig, _ = to_matplotlib(spec, figsize=figsize, style=style, dpi=dpi)
    buf = BytesIO()
    try:
        fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    finally:
        plt.close(fig)
    return buf.getvalue()


def to_data_uri(spec: PlotSpec, **kwargs) -> str:
    """Render to a base64 data URI, for embedding directly in a page."""
    import base64

    payload = base64.b64encode(to_png_bytes(spec, **kwargs)).decode("ascii")
    return f"data:image/png;base64,{payload}"
