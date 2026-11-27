"""Normalizing an overlay's area: the drawing and the verdict together.

Two histograms of the same shape and different size are a different question
from two of the same size and different shape, and the tab now asks either.
The trap is that the comparison's `fraction` measure is area-sensitive while
its KS probability is not -- so scaling only what is drawn would show two
curves lying on top of each other and grade them a failure. These check that
one factor reaches both, and that the page says it did.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("hist")

import hist as hist_lib

from dqm.hist import ComparePars, area_scale, compare_histograms
from dqm.plot import PlotSpec


def shaped(scale=1.0, shift=0):
    """A gaussian-ish bump, scaled in area and optionally moved along."""
    h = hist_lib.Hist.new.Reg(20, 0, 20).Double()
    for i in range(20):
        h[i] = scale * 100.0 * np.exp(-0.5 * ((i - 10 - shift) / 3.0) ** 2)
    return h


# -- the factor --------------------------------------------------------------

def test_the_factor_puts_the_second_area_onto_the_first():
    a, b = shaped(1.0), shaped(0.25)
    assert area_scale(a, b) == pytest.approx(4.0)


def test_the_factor_is_one_for_equal_areas():
    assert area_scale(shaped(), shaped()) == pytest.approx(1.0)


def test_an_empty_overlay_has_no_factor():
    """0.0 rather than an exception or an infinity: there is no number that
    normalizes nothing, and the caller has to notice."""
    empty = hist_lib.Hist.new.Reg(20, 0, 20).Double()
    assert area_scale(shaped(), empty) == 0.0


def test_different_binning_has_no_factor():
    other = hist_lib.Hist.new.Reg(10, 0, 20).Double()
    other[0] = 5.0
    assert area_scale(shaped(), other) == 0.0


def test_the_factor_respects_the_flow_settings_it_is_given():
    """It has to measure the same bins the comparison does, or a normalized
    pair would not come back as a match."""
    a, b = shaped(1.0), shaped(0.5)
    no_flow = ComparePars(underflow=False, overflow=False)
    assert area_scale(a, b, no_flow) == pytest.approx(area_scale(a, b))


# -- what it does to the verdict ---------------------------------------------

def test_the_same_shape_at_a_different_size_fails_on_area_unnormalized():
    """The starting point: this is the behaviour normalization exists to
    change, and it is the right answer to the other question."""
    a, b = shaped(1.0), shaped(0.25)
    c = compare_histograms(a, b, pars=ComparePars())
    assert c.fraction < 0.9           # the areas differ fourfold
    assert c.kolmogorov > 0.99        # ... but the shapes do not


def test_normalizing_makes_the_same_shape_agree():
    a, b = shaped(1.0), shaped(0.25)
    factor = area_scale(a, b)
    c = compare_histograms(a, b, pars=ComparePars(scale2=factor))
    assert c.fraction > 0.999
    assert c.status.name in ("tight", "perfect")


def test_normalizing_does_not_excuse_a_different_shape():
    """The point of the option is to isolate shape, not to flatter it."""
    a, b = shaped(1.0), shaped(0.25, shift=4)
    c = compare_histograms(a, b, pars=ComparePars(scale2=area_scale(a, b)))
    assert c.fraction < 0.95
    assert c.status.name == "fail"


def test_the_reported_sums_stay_the_areas_as_found():
    """Whatever is drawn, the numbers under it are the real areas -- so the
    factor has to be stated beside them, which the tab does."""
    a, b = shaped(1.0), shaped(0.25)
    c = compare_histograms(a, b, pars=ComparePars(scale2=area_scale(a, b)))
    assert c.sum1 == pytest.approx(4 * c.sum2, rel=1e-6)


# -- what it does to the drawing ---------------------------------------------

def test_a_scaled_trace_scales_its_errors_with_its_values():
    """k counts carry k*sigma. Scaling the Hist itself would re-derive the
    errors from the scaled contents and quietly shrink them by sqrt(k)."""
    h = shaped(1.0)
    plain = PlotSpec(traces=[])
    plain.add_hist(h)
    scaled = PlotSpec(traces=[])
    scaled.add_hist(h, scale=4.0)

    _, v0, e0, _ = plain.traces[0].points()
    _, v1, e1, _ = scaled.traces[0].points()
    assert v1 == pytest.approx(v0 * 4.0)
    assert e1 == pytest.approx(e0 * 4.0)


def test_an_unscaled_trace_is_untouched():
    h = shaped(1.0)
    spec = PlotSpec()
    spec.add_hist(h)
    _, values, _, _ = spec.traces[0].points()
    assert values == pytest.approx(np.asarray(h.values(), dtype=float))


def test_scaling_does_not_mutate_the_histogram():
    h = shaped(1.0)
    before = np.asarray(h.values(), dtype=float).copy()
    spec = PlotSpec()
    spec.add_hist(h, scale=7.0)
    spec.traces[0].points()
    assert np.asarray(h.values(), dtype=float) == pytest.approx(before)


def test_both_renderers_see_the_scale():
    """The scale is applied in points(), which is the one thing both
    renderers call -- so an exported figure matches the browser."""
    pytest.importorskip("plotly")
    from dqm.plot import to_plotly
    from dqm.plot.spec import SeriesTrace  # noqa: F401  (import check)

    spec = PlotSpec()
    spec.add_hist(shaped(1.0), style="errorbar", scale=3.0)
    trace = to_plotly(spec).data[0]
    assert max(trace.y) == pytest.approx(300.0, rel=1e-6)
