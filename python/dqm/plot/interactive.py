"""Render a PlotSpec with plotly, for the browser.

A thin translation of the spec: everything about *what* to show was decided
in dqm.plot.spec, and this file decides only how plotly should express it.
Keeping it thin is the point -- it is what stops the interactive and static
versions of a figure from drifting apart.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

import numpy as np

from dqm.errors import DqmDependencyError
from dqm.plot.spec import PlotSpec

try:
    import plotly.graph_objects as go
except ImportError as exc:  # pragma: no cover - dependency error path
    raise DqmDependencyError(
        "dqm.plot.interactive needs plotly. Install the extra: "
        "pip install 'mu2e-dqm[plot]'"
    ) from exc

__all__ = ["to_plotly", "to_plotly_grid"]


def _step_xy(edges, values):
    """Bin edges and contents as a staircase.

    plotly has no native step-histogram trace that also honours explicit bin
    edges, so the outline is built by hand -- each edge repeated to give the
    vertical risers.
    """
    x = np.repeat(edges, 2)[1:-1]
    y = np.repeat(values, 2)
    return x, y


def _draw(fig, spec: PlotSpec, row=None, col=None):
    """Add one spec's traces to a figure, optionally into a subplot cell.

    Shared by to_plotly and to_plotly_grid so a panel of a stack is drawn by
    exactly the same code as a figure on its own -- the alternative is two
    renderers that drift apart.
    """
    where = {} if row is None else {"row": row, "col": col or 1}

    for i, trace in enumerate(spec.traces):
        centers, values, errors, edges = trace.points()
        color = spec.color_for(i, trace.color)
        name = trace.label or f"hist {i + 1}"

        if trace.style == "errorbar":
            fig.add_trace(
                go.Scatter(
                    x=centers, y=values, mode="markers", name=name,
                    marker=dict(color=color, size=5),
                    error_y=dict(type="data", array=errors, visible=True,
                                 color=color, thickness=1),
                    opacity=trace.alpha,
                ), **where
            )
        elif trace.style == "fill":
            x, y = _step_xy(edges, values)
            fig.add_trace(
                go.Scatter(x=x, y=y, mode="lines", name=name, fill="tozeroy",
                           line=dict(color=color, width=1), opacity=trace.alpha),
                **where
            )
        else:  # "step"
            x, y = _step_xy(edges, values)
            fig.add_trace(
                go.Scatter(x=x, y=y, mode="lines", name=name,
                           line=dict(color=color, width=1.5),
                           opacity=trace.alpha),
                **where
            )

    # Series continue the colour cycle after the histograms, so a figure
    # holding both never draws two different things in one colour.
    for k, strace in enumerate(spec.series):
        x, y, err = strace.arrays()
        color = spec.color_for(len(spec.traces) + k, strace.color)
        mode = {"markers": "markers", "lines": "lines"}.get(strace.style, "lines+markers")
        fig.add_trace(
            go.Scatter(
                x=x, y=y, mode=mode, name=strace.label or f"series {k + 1}",
                marker=dict(color=color, size=6),
                line=dict(color=color, width=1.5),
                error_y=(dict(type="data", array=err, visible=True, color=color,
                              thickness=1) if err is not None else None),
            ), **where
        )

    xlim = spec.data_xlim()
    for j, ftrace in enumerate(spec.fits):
        curve = ftrace.curve(xlim)
        if curve is None:
            continue  # parameters still reach the annotation below
        xs, ys = curve
        color = ftrace.color or "#ff7f0e"
        fig.add_trace(
            go.Scatter(x=xs, y=ys, mode="lines", name=ftrace.label or "fit",
                       line=dict(color=color, width=2, dash="solid")), **where
        )

    for line in spec.lines:
        kw = dict(line_color=line.color,
                  line_dash="dash" if line.dash else "solid",
                  annotation_text=line.label or None, **where)
        if line.orientation == "v":
            fig.add_vline(x=line.position, **kw)
        else:
            fig.add_hline(y=line.position, **kw)

    notes = spec.all_annotations()
    if notes:
        # Pinned to the plot area rather than the data, so it stays put when
        # the user zooms. In a stack this has to reference the panel's own
        # domain; "paper" would put every panel's box in the same corner of
        # the whole figure.
        refs = (dict(xref="paper", yref="paper") if row is None
                else dict(xref="x domain", yref="y domain", **where))
        fig.add_annotation(
            x=0.99, y=0.99, text="<br>".join(notes),
            showarrow=False, align="left",
            xanchor="right", yanchor="top",
            bordercolor="#999999", borderwidth=1,
            bgcolor="rgba(255,255,255,0.8)",
            font=dict(size=11, family="monospace"),
            **refs,
        )
    return fig


def to_plotly(spec: PlotSpec, height: int = 500, template: str = "plotly_white"):
    """Build a plotly Figure from a PlotSpec."""
    fig = go.Figure()
    _draw(fig, spec)

    fig.update_layout(
        title=spec.title or None,
        xaxis_title=spec.xlabel or None,
        yaxis_title=spec.ylabel or None,
        template=template,
        height=height,
        showlegend=spec.legend and bool(spec.traces or spec.fits or spec.series),
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        margin=dict(l=60, r=30, t=50 if spec.title else 20, b=50),
        hovermode="x unified",
    )
    if spec.logx:
        fig.update_xaxes(type="log")
    if spec.logy:
        fig.update_yaxes(type="log")
    if spec.xlim:
        fig.update_xaxes(range=list(spec.xlim))
    if spec.ylim:
        fig.update_yaxes(range=list(spec.ylim))

    return fig


def to_plotly_grid(
    specs: Sequence[PlotSpec],
    shared_x: bool = True,
    height_each: int = 260,
    template: str = "plotly_white",
    titles: Optional[Sequence[str]] = None,
    cols: int = 1,
    title_colors: Optional[Sequence[str]] = None,
):
    """Arrange several specs as separate panels in one figure.

    Each panel keeps its own y axis, which is the point: quantities whose
    values differ by orders of magnitude cannot share a scale, and forcing
    them onto one flattens the smaller into a line along the axis.

    One column by default, which suits a handful of panels being compared
    against a common x axis. Pass `cols` for many panels at once -- a file of
    eighty histograms in a single column is twenty thousand pixels of
    scrolling, where a few columns is a page someone can actually scan.

    `shared_x` links the x axes so panels stay aligned and zooming one zooms
    all. That is right for timelines against a common axis and wrong for
    unrelated histograms, each of which has its own range, so a multi-column
    grid ignores it.

    `title_colors` colours the panel headings, which is how a grid can carry a
    per-panel verdict without a legend in every cell.
    """
    from plotly.subplots import make_subplots

    specs = list(specs)
    if not specs:
        return go.Figure()

    cols = max(1, int(cols))
    rows = -(-len(specs) // cols)  # ceiling division
    # Several columns means several x ranges side by side; linking them would
    # tie together axes that have nothing to do with each other.
    link_x = shared_x and cols == 1

    heads = list(titles) if titles is not None else [s.title for s in specs]
    fig = make_subplots(
        rows=rows, cols=cols,
        shared_xaxes=link_x,
        vertical_spacing=min(0.08, 0.5 / max(rows, 1)),
        horizontal_spacing=min(0.06, 0.4 / max(cols, 1)),
        subplot_titles=heads,
    )

    for i, spec in enumerate(specs):
        row, col = i // cols + 1, i % cols + 1
        _draw(fig, spec, row=row, col=col)
        fig.update_yaxes(title_text=spec.ylabel or None, row=row, col=col)
        if spec.logy:
            fig.update_yaxes(type="log", row=row, col=col)
        if spec.logx:
            fig.update_xaxes(type="log", row=row, col=col)
        if cols > 1 and spec.xlabel:
            # Every panel is independent here, so each carries its own label.
            fig.update_xaxes(title_text=spec.xlabel, row=row, col=col)

    if cols == 1:
        # x label on the bottom panel only; above, it would repeat between
        # panels that share the axis.
        fig.update_xaxes(title_text=specs[-1].xlabel or None, row=rows, col=1)

    fig.update_layout(
        template=template,
        height=max(height_each * rows, height_each),
        margin=dict(l=70, r=30, t=40, b=50),
        # Per-panel legends would stack into a column of near-identical
        # entries; the panel titles already say what each one is.
        showlegend=False,
        hovermode="x unified" if cols == 1 else "closest",
    )
    for i, note in enumerate(fig.layout.annotations[: len(specs)]):
        # make_subplots titles default to a size that competes with the
        # figure title; these are labels, not headings.
        note.font.size = 12 if cols == 1 else 10
        if title_colors and i < len(title_colors) and title_colors[i]:
            note.font.color = title_colors[i]
    return fig
