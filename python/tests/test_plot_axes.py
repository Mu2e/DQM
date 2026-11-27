"""The axes of an interactive figure are drawn, and read as axes.

plotly_white gives linecolor, gridcolor and zerolinecolor the same pale value
and no tick marks, so a panel arrived as a field of grid with the axis
indistinguishable from the lines crossing it. These check the frame is there,
that it is distinguishable from the grid, and that putting it there did not
tread on anything a caller asked for.
"""

from __future__ import annotations

import pytest

pytest.importorskip("plotly")

from dqm.plot import PlotSpec, to_plotly, to_plotly_grid
from dqm.plot.interactive import AXIS_STYLE
from dqm.plot.spec import SeriesTrace

X = list(range(20))
Y = [1.0 + 0.01 * i for i in X]


def panel(**kw):
    return PlotSpec(title="p", xlabel="x", ylabel="y",
                    series=[SeriesTrace(x=X, y=Y, label="s")], **kw)


def axes(fig, kind):
    """Every x or y axis in the figure, by layout key."""
    return {k: fig.layout[k] for k in fig.layout
            if k.startswith(kind) and "axis" in k}


def luma(hex_colour):
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return 0.299 * r + 0.587 * g + 0.114 * b


# -- one figure --------------------------------------------------------------

def test_both_axes_have_a_line():
    fig = to_plotly(panel())
    for ax in (fig.layout.xaxis, fig.layout.yaxis):
        assert ax.showline
        assert ax.linecolor == AXIS_STYLE["linecolor"]


def test_the_frame_is_mirrored_onto_all_four_sides():
    fig = to_plotly(panel())
    assert fig.layout.xaxis.mirror and fig.layout.yaxis.mirror


def test_there_are_tick_marks():
    fig = to_plotly(panel())
    assert fig.layout.xaxis.ticks == "outside"
    assert fig.layout.yaxis.ticks == "outside"


def test_the_frame_is_darker_than_the_grid_it_sits_in():
    """The whole complaint: an axis the same colour as the gridlines is not
    an axis. The grid keeps the template's colour, so compare against that."""
    import plotly.io as pio

    grid = pio.templates["plotly_white"].layout.xaxis.gridcolor
    fig = to_plotly(panel())
    assert luma(fig.layout.xaxis.linecolor) < luma(grid) - 100


def test_the_zero_line_is_between_the_two():
    """Darker than the grid so a quantity crossing zero shows it, lighter
    than the frame so it does not read as another axis."""
    fig = to_plotly(panel())
    assert (luma(AXIS_STYLE["linecolor"])
            < luma(fig.layout.yaxis.zerolinecolor)
            < luma("#EBF0F8"))


def test_the_grid_is_left_to_the_template():
    fig = to_plotly(panel())
    assert fig.layout.xaxis.gridcolor is None


# -- nothing a caller asked for is overwritten -------------------------------

def test_a_log_scale_still_wins():
    assert to_plotly(panel(logy=True)).layout.yaxis.type == "log"
    assert to_plotly(panel(logx=True)).layout.xaxis.type == "log"


def test_an_explicit_range_still_wins():
    fig = to_plotly(panel(xlim=(2, 5), ylim=(0, 3)))
    assert tuple(fig.layout.xaxis.range) == (2, 5)
    assert tuple(fig.layout.yaxis.range) == (0, 3)


def test_the_titles_survive():
    fig = to_plotly(panel())
    assert fig.layout.xaxis.title.text == "x"
    assert fig.layout.yaxis.title.text == "y"


# -- grids -------------------------------------------------------------------

def test_every_panel_of_a_stack_is_framed():
    fig = to_plotly_grid([panel(), panel(), panel()])
    assert len(axes(fig, "x")) == 3
    for ax in list(axes(fig, "x").values()) + list(axes(fig, "y").values()):
        assert ax.showline and ax.mirror


def test_a_log_panel_in_a_grid_keeps_its_scale():
    fig = to_plotly_grid([panel(), panel(logy=True)])
    assert fig.layout.yaxis2.type == "log"
    assert fig.layout.yaxis2.showline


def test_a_cell_left_over_by_the_last_row_is_hidden():
    """Three panels in two columns leaves a fourth cell with axes and no
    data. Framed, it would read as a panel that failed to draw."""
    fig = to_plotly_grid([panel(), panel(), panel()], cols=2)
    assert fig.layout.xaxis4.visible is False
    assert fig.layout.yaxis4.visible is False
    assert fig.layout.xaxis4.showline is None  # never styled at all


def test_a_full_grid_hides_nothing():
    fig = to_plotly_grid([panel()] * 4, cols=2)
    for ax in axes(fig, "x").values():
        assert ax.visible is not False
        assert ax.showline


def test_an_empty_grid_is_still_a_figure():
    assert to_plotly_grid([]).layout is not None
