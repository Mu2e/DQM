"""The Histograms tab drawing a golden file over file A.

No browser, no database and no ROOT files: the tab's own callback is called
directly, with the lookup and the file opening replaced. What is checked is
what reaches the figure -- which trace is the reference, how it is drawn, and
that the page always says which file was used or why there was none.
"""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

import pytest

pytest.importorskip("dash")
pytest.importorskip("hist")

try:
    from dqm.web import histogram as H
except Exception as exc:  # a missing web extra
    pytest.skip(f"dqm.web cannot be imported here: {exc}", allow_module_level=True)

import hist as hist_lib

from dqm.golden import GoldenMatch
from dqm.plot.spec import PALETTE, REFERENCE_COLOR

NAME = "dqm.mu2e.cosmics_crv.crvreco-006-001-file.125873_000636-001.root"
GOLDEN_NAME = "dqm.mu2e.cosmics_crv.crvreco-006-001-file.125026_000001-001.root"
PATHS = ["crv/PEs", "crv/time"]


def a_hist(scale=1.0):
    h = hist_lib.Hist.new.Reg(10, 0, 10).Double()
    for i in range(10):
        h[i] = (i + 1) * scale
    return h


class FakeFile:
    """The bit of dqm.hist.HistFile the tab uses."""

    def __init__(self, paths=PATHS, scale=1.0):
        self.paths = list(paths)
        self.scale = scale

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __contains__(self, path):
        return path in self.paths

    def histograms(self, ndim=1):
        return [SimpleNamespace(path=p, name=p.split("/")[-1]) for p in self.paths]

    def read(self, path):
        return a_hist(self.scale)

    def read_raw(self, path):
        return None


ROW = SimpleNamespace(gid=4, sid=118, iid=33144, filename=GOLDEN_NAME,
                      note="first nominal golden file", start_run=120000,
                      end_run=999999)

MATCH = GoldenMatch(filename=GOLDEN_NAME, row=ROW, sid=118,
                    source="crvreco/kpp_crv 006-001", run=125873,
                    subrun=636001, how="files")


@pytest.fixture
def tab(monkeypatch):
    """The tab with its file reading and its golden lookup replaced."""
    def open_file(path):
        # the reference has one fewer histogram, which is ordinary for a
        # hand-made average and must not be reported as a problem
        if path.endswith("golden.root"):
            return FakeFile(paths=PATHS[:1], scale=1.1)
        return FakeFile(scale=1.0)

    monkeypatch.setattr(H, "open_file", open_file)
    monkeypatch.setattr(H, "_openable", lambda name: "/fake/golden.root")
    monkeypatch.setattr(H, "statistics", lambda raw, h: SimpleNamespace(
        entries=55, mean=4.5, mean_error=0.1, std_dev=2.9,
        from_accumulators=False))
    monkeypatch.setattr(H, "compare_histograms", lambda ha, hb, pars, path:
                        SimpleNamespace(status=SimpleNamespace(name="pass"),
                                        color="#2ca02c", kolmogorov=0.9,
                                        fraction=0.01, sum1=55, sum2=60,
                                        note=""))
    return H


@pytest.fixture
def draw(tab, monkeypatch):
    """Call the figure callback the way Dash would, with the lookup faked.

    A fixture rather than a plain function so the fake is undone afterwards:
    patching the module directly leaked into every later test and quietly
    stopped them exercising the real resolution.
    """
    def call(path=PATHS[0], chosen_b=None, match=MATCH, problem=None,
             norm=H.NORM_NONE):
        m = GoldenMatch(problem=problem) if problem is not None else match
        monkeypatch.setattr(
            H, "_golden_overlay",
            lambda name: ((None, None, m.problem) if not m
                          else ("/fake/golden.root", H._golden_caption(m), None)))
        return H._draw_for_test(path, chosen_b, norm)

    return call


# The callback is registered on an app, so reach it the way the app does.
@pytest.fixture(autouse=True)
def expose_callback(monkeypatch):
    from dqm.web.app import create_app

    app = create_app()
    key = next(k for k in app.callback_map if "hist-graph.figure" in k)
    fn = app.callback_map[key]["callback"].__wrapped__

    def _draw_for_test(path, chosen_b, norm=H.NORM_NONE):
        # (path, fit, norm, opts, file-b-path, file-b-pick, file-a-path,
        #  file-a-pick, dataset)
        return fn(path, "none", norm, [], chosen_b, None, NAME, None, None)

    monkeypatch.setattr(H, "_draw_for_test", _draw_for_test, raising=False)


def traces(figure):
    return list(figure.data) if hasattr(figure, "data") else []


def text_of(node) -> str:
    """Flatten a Dash component tree to text, for asserting on captions."""
    if node is None or isinstance(node, (str, int, float)):
        return str(node or "")
    children = getattr(node, "children", None)
    if isinstance(children, (list, tuple)):
        return " ".join(text_of(c) for c in children)
    return text_of(children)


# -- the option --------------------------------------------------------------

def test_golden_is_offered_for_b_and_not_for_a(monkeypatch):
    from dqm.web.app import create_app

    monkeypatch.setattr(H, "_file_options",
                        lambda did: ([{"label": "f", "value": "f.root"}], 1))
    app = create_app()
    key = next(k for k in app.callback_map if "hist-file-a-pick.options" in k)
    fn = app.callback_map[key]["callback"].__wrapped__
    out = fn("mu2e:some.dataset")
    a_options, b_options = out[4], out[5]
    assert [o["value"] for o in a_options] == ["f.root"]
    assert b_options[0]["value"] == H.GOLDEN_FILE
    assert "golden" in b_options[0]["label"]


@pytest.mark.parametrize("value, expected", [
    (H.GOLDEN_FILE, True), ("golden", True), ("  Golden ", True),
    ("GOLDEN", True), ("golden.root", False), ("/pnfs/x.root", False),
    (None, False), ("", False),
])
def test_the_typed_word_works_too(value, expected):
    assert H._is_golden(value) is expected


# -- drawing -----------------------------------------------------------------

def test_the_reference_is_drawn_first_heavier_and_in_its_own_colour(draw):
    figure, _ = draw(chosen_b=H.GOLDEN_FILE)
    ref, data = traces(figure)[0], traces(figure)[1]
    assert ref.name == "golden"
    assert ref.line.color == REFERENCE_COLOR
    assert ref.line.width > 1.5           # heavier than a normal step
    assert ref.mode == "lines"
    assert data.name == "A"
    assert data.mode == "markers"         # data as points over the reference
    assert data.marker.color == PALETTE[0]


def test_without_golden_the_styles_are_the_old_way_round(draw):
    figure, _ = draw(chosen_b="/some/other.root")
    first, second = traces(figure)[0], traces(figure)[1]
    assert (first.name, first.mode) == ("A", "lines")
    assert (second.name, second.mode) == ("B", "markers")


def test_one_file_alone_is_unchanged(draw):
    figure, _ = draw(chosen_b=None)
    assert [t.name for t in traces(figure)] == ["A"]


def test_the_caption_names_the_file_the_source_and_the_declaration(draw):
    _, detail = draw(chosen_b=H.GOLDEN_FILE)
    said = text_of(detail)
    assert GOLDEN_NAME in said
    assert "crvreco/kpp_crv 006-001" in said
    assert "run 125873" in said
    assert "gid 4" in said
    assert "first nominal golden file" in said   # the note
    assert "runs 120000-999999" in said


def test_a_fallback_to_the_open_ended_declaration_says_so(draw):
    _, detail = draw(chosen_b=H.GOLDEN_FILE,
                     match=GoldenMatch(filename=GOLDEN_NAME, row=ROW, sid=118,
                                       source="crvreco/kpp_crv 006-001",
                                       run=119000, how="latest"))
    said = text_of(detail)
    assert "No declaration covers run 119000" in said
    assert "in use now" in said


def test_no_reference_is_reported_and_file_a_is_still_drawn(draw):
    figure, detail = draw(chosen_b=H.GOLDEN_FILE,
                          problem="no golden file is declared for crvreco/kpp_crv")
    assert [t.name for t in traces(figure)] == ["A"]
    said = text_of(detail)
    assert "No golden file" in said
    assert "no golden file is declared" in said


def test_a_histogram_absent_from_the_reference_is_not_reported(draw):
    """The fake reference holds only the first path. For a hand-made average
    that is ordinary, and the empty overlay already shows it."""
    figure, detail = draw(path=PATHS[1], chosen_b=H.GOLDEN_FILE)
    assert [t.name for t in traces(figure)] == ["A"]
    assert "is not in file B" not in text_of(detail)


def test_the_same_absence_is_reported_for_a_file_someone_chose(draw):
    figure, detail = draw(path=PATHS[1], chosen_b="/fake/golden.root")
    assert "is not in file B" in text_of(detail)


# -- the resolution step itself ----------------------------------------------

def test_golden_overlay_turns_a_match_into_a_path_and_a_caption(monkeypatch):
    monkeypatch.setattr(H, "_openable", lambda name: f"/pnfs/{name}")
    import dqm.golden as G
    monkeypatch.setattr(G, "golden_for_file", lambda name, reader: MATCH)
    monkeypatch.setattr("dqm.web.common.reader", lambda: object())

    path, caption, problem = H._golden_overlay(NAME)
    assert path == f"/pnfs/{GOLDEN_NAME}"
    assert problem is None
    assert GOLDEN_NAME in text_of(caption)


def test_golden_overlay_passes_a_problem_through(monkeypatch):
    import dqm.golden as G
    monkeypatch.setattr(G, "golden_for_file",
                        lambda name, reader: GoldenMatch(problem="nothing declared"))
    monkeypatch.setattr("dqm.web.common.reader", lambda: object())
    path, caption, problem = H._golden_overlay(NAME)
    assert (path, caption) == (None, None)
    assert problem == "nothing declared"


def test_golden_overlay_reports_a_broken_lookup_rather_than_raising(monkeypatch):
    """A Query Engine outage must leave the tab usable: file A still draws,
    with the reason the reference is missing on the page."""
    import dqm.golden as G

    def boom(name, reader):
        raise RuntimeError("QE down")

    monkeypatch.setattr(G, "golden_for_file", boom)
    monkeypatch.setattr("dqm.web.common.reader", lambda: object())
    path, _caption, problem = H._golden_overlay(NAME)
    assert path is None
    assert "QE down" in problem


def test_golden_overlay_needs_file_a():
    path, _caption, problem = H._golden_overlay(None)
    assert path is None
    assert "file A" in problem


def test_an_unlocatable_reference_is_a_problem_not_a_crash(monkeypatch):
    import dqm.golden as G
    monkeypatch.setattr(G, "golden_for_file", lambda name, reader: MATCH)
    monkeypatch.setattr("dqm.web.common.reader", lambda: object())

    def nope(name):
        raise RuntimeError("not on disk anywhere")

    monkeypatch.setattr(H, "_openable", nope)
    path, _caption, problem = H._golden_overlay(NAME)
    assert path is None
    assert "could not be located" in problem


def test_openable_tells_a_path_from_a_catalogued_name(monkeypatch):
    assert H._openable("/pnfs/mu2e/x.root") == "/pnfs/mu2e/x.root"
    assert H._openable("root://host//x.root") == "root://host//x.root"
    import dqm.catalog as C
    monkeypatch.setattr(C, "file_url", lambda name: f"/resolved/{name}")
    assert H._openable(GOLDEN_NAME) == f"/resolved/{GOLDEN_NAME}"


# -- the all-histograms grid -------------------------------------------------

def test_the_grid_draws_the_reference_the_same_way(tab):
    figure, detail = H._draw_all("/fake/a.root", "/fake/golden.root", [], "none",
                                 golden=True)
    ref, data = figure.data[0], figure.data[1]
    assert ref.line.color == REFERENCE_COLOR
    assert ref.line.width > 1.5
    assert data.mode == "markers"
    assert "heavier gold outline" in text_of(detail)


def test_the_grid_without_golden_is_unchanged(tab):
    figure, _ = H._draw_all("/fake/a.root", "/fake/b.root", [], "none")
    assert figure.data[0].mode == "lines"      # A as the outline
    assert figure.data[1].mode == "markers"    # B as the points


def test_the_grid_does_not_count_histograms_missing_from_a_reference(tab):
    _, detail = H._draw_all("/fake/a.root", "/fake/golden.root", [], "none",
                            golden=True)
    assert "not in file B" not in text_of(detail)
    _, plain = H._draw_all("/fake/a.root", "/fake/golden.root", [], "none")
    assert "not in file B" in text_of(plain)


# -- normalization -----------------------------------------------------------

def test_the_overlay_is_drawn_scaled_when_asked(draw, monkeypatch):
    """The reference fake is 1.1x file A, so the factor is 1/1.1."""
    figure, _ = draw(chosen_b=H.GOLDEN_FILE, norm=H.NORM_AREA)
    ref = [t for t in traces(figure) if t.name == "golden"][0]
    data = [t for t in traces(figure) if t.name == "A"][0]
    assert max(ref.y) == pytest.approx(max(data.y), rel=1e-6)


def test_as_found_leaves_the_overlay_alone(draw):
    figure, _ = draw(chosen_b=H.GOLDEN_FILE, norm=H.NORM_NONE)
    ref = [t for t in traces(figure) if t.name == "golden"][0]
    data = [t for t in traces(figure) if t.name == "A"][0]
    assert max(ref.y) == pytest.approx(1.1 * max(data.y), rel=1e-6)


def test_the_page_says_the_overlay_was_scaled(draw):
    _, detail = draw(chosen_b=H.GOLDEN_FILE, norm=H.NORM_AREA)
    said = text_of(detail)
    assert "scaled by" in said
    assert "match A's area" in said


def test_nothing_is_said_when_nothing_was_scaled(draw):
    _, detail = draw(chosen_b=H.GOLDEN_FILE, norm=H.NORM_NONE)
    assert "scaled by" not in text_of(detail)


def test_normalization_reaches_the_comparison_not_just_the_drawing(draw, monkeypatch):
    """The whole trap: the fraction measure is area-sensitive, so the factor
    has to arrive as ComparePars.scale2 as well."""
    seen = {}

    def spy(ha, hb, pars, path):
        seen["scale2"] = pars.scale2
        return SimpleNamespace(status=SimpleNamespace(name="pass"),
                               color="#2ca02c", kolmogorov=1.0, fraction=1.0,
                               sum1=55, sum2=60, note="")

    monkeypatch.setattr(H, "compare_histograms", spy)
    draw(chosen_b=H.GOLDEN_FILE, norm=H.NORM_AREA)
    assert seen["scale2"] == pytest.approx(1 / 1.1, rel=1e-6)

    seen.clear()
    draw(chosen_b=H.GOLDEN_FILE, norm=H.NORM_NONE)
    assert seen["scale2"] == 1.0


def test_an_overlay_that_cannot_be_scaled_says_so_and_draws_as_found(draw,
                                                                     monkeypatch):
    import dqm.web.histogram as mod
    monkeypatch.setattr(mod, "area_scale", lambda ha, hb, pars: 0.0)
    figure, detail = draw(chosen_b=H.GOLDEN_FILE, norm=H.NORM_AREA)
    assert len(traces(figure)) == 2          # still drawn
    assert "areas not normalized" in text_of(detail)


def test_the_grid_normalizes_each_panel_on_its_own(tab):
    figure, detail = H._draw_all("/fake/a.root", "/fake/golden.root", [], "none",
                                 golden=True, norm=H.NORM_AREA)
    ref, data = figure.data[0], figure.data[1]
    assert max(ref.y) == pytest.approx(max(data.y), rel=1e-6)
    assert "scaled to match area" in text_of(detail)


def test_the_grid_as_found_is_unscaled(tab):
    figure, detail = H._draw_all("/fake/a.root", "/fake/golden.root", [], "none",
                                 golden=True)
    ref, data = figure.data[0], figure.data[1]
    assert max(ref.y) == pytest.approx(1.1 * max(data.y), rel=1e-6)
    assert "scaled to match area" not in text_of(detail)


def test_the_dropdown_defaults_to_as_found():
    """Literal areas are the honest default: a plot nobody asked to be
    normalized must not be."""
    assert H.NORM_OPTIONS[0]["value"] == H.NORM_NONE
    assert [o["value"] for o in H.NORM_OPTIONS] == [H.NORM_NONE, H.NORM_AREA]


# -- the declared range, however the declaration is positioned ---------------

def test_the_caption_gives_a_time_ranged_declarations_window():
    """A time-positioned declaration stores run 0, so the run branch cannot
    be the only one: a nightly source's caption said nothing at all about
    when its reference applied, which is most of what the line is for."""
    row = SimpleNamespace(
        gid=5, sid=5, iid=33171, filename="ref.root", note=None,
        start_run=0, end_run=0,
        start_time=pd.Timestamp("2026-11-13", tz="UTC"),
        end_time=pd.Timestamp("9999-12-31 23:59:59.999999", tz="UTC"))
    said = text_of(H._golden_caption(
        GoldenMatch(filename="ref.root", row=row, sid=5,
                    source="valNightly/reco 0", how="files")))
    assert "declared from 2026-11-13 onwards" in said


def test_a_closed_time_range_names_both_ends():
    row = SimpleNamespace(
        gid=6, start_run=0, end_run=0, filename="ref.root", note=None,
        start_time=pd.Timestamp("2026-11-13", tz="UTC"),
        end_time=pd.Timestamp("2026-11-20", tz="UTC"))
    said = text_of(H._golden_caption(GoldenMatch(filename="ref.root", row=row)))
    assert "declared for 2026-11-13 to 2026-11-20" in said


def test_a_run_ranged_declaration_still_reads_as_runs():
    said = text_of(H._golden_caption(MATCH))
    assert "declared for runs 120000-999999" in said
    assert "declared from" not in said


def test_a_declaration_with_no_usable_range_says_so_rather_than_guessing():
    row = SimpleNamespace(gid=7, start_run=0, end_run=0, filename="ref.root",
                          note=None, start_time=None, end_time=None)
    said = text_of(H._golden_caption(GoldenMatch(filename="ref.root", row=row)))
    assert "declared range unknown" in said
