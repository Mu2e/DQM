"""Histograms tab: overlay two ROOT files, fit, and compare.

Reads through dqm.hist, which uses uproot -- so this runs anywhere the package
is installed, with no Muse environment and no ROOT.

There are two ways to say which files to look at, and the tab supports both
through the same two file fields:

  * Leave the dataset blank and type paths directly. Anything uproot can open
    works -- a local path, a /pnfs path, a root:// URL.

  * Choose a dataset and the file fields become dropdowns of that dataset's
    files, resolved to paths by dqm.catalog. Nothing is selected until you
    pick something, so choosing a dataset never loads a file on its own.

Either way the second file is optional: one file alone is a perfectly good
thing to look at, and the overlay and comparison simply do not appear.

The second file can also be the word "golden" -- the dropdown offers it, and
the path box accepts it typed -- which overlays whichever reference file
dqm.golden declares for file A instead of a file chosen by hand. What makes
that possible is that file A names its own run and, through dqm.files, its own
source; see dqm.golden for the chain and for how it fails. The reference is
drawn as the reference: a heavier gold outline with the data as points over
it, and a line under the plot saying which file was used and why, because a
reference is not rigorously maintained and the wrong one overlaid silently
would be worse than none.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Tuple

import dash
from dash import Input, Output, State, dcc, html

from dqm.hist import (
    ComparePars,
    area_scale,
    compare_histograms,
    fit_histogram,
    get_fit,
    open_file,
    statistics,
)
from dqm.plot import PlotSpec, to_plotly, to_plotly_grid
from dqm.plot.spec import PALETTE, REFERENCE_COLOR
from dqm.web.common import ID, card, error_box, kv_table, row

LOGGER = logging.getLogger("dqm.web.histogram")

PREFIX = "hist-"

# Files offered in one dropdown. A DQM dataset can hold a few thousand files,
# and every one sent becomes JSON the browser has to hold and search: the
# largest today would be ~450 KB per dropdown. The newest are the ones anyone
# wants, so the list is cut there and the count says what was left out.
MAX_FILE_OPTIONS = 500

# Datasets whose name contains this are offered. "" would list every dataset
# in the namespace, which is thousands and almost all irrelevant here.
DATASET_PATTERN = "dqm"

# The histogram dropdown's first entry: every histogram in the file at once.
ALL_HISTOGRAMS = "__all__"

# File B's first entry: not a file of this dataset but whichever golden file
# applies to file A, looked up when the plot is drawn. Offered for B and not
# for A because A is what the lookup is *about* -- it supplies both the
# histogram list and the run, so golden-as-A has nothing to resolve against.
GOLDEN_FILE = "__golden__"

# Typing this in the File B path box does the same thing, so the reference is
# reachable when a path was typed rather than a dataset chosen -- the run comes
# from file A's name either way.
GOLDEN_WORD = "golden"

# A reference is drawn heavier than the data it is being compared against, in
# a colour that is not in the data palette. See dqm.plot.spec.REFERENCE_COLOR.
GOLDEN_WEIGHT = 2.2

# How the overlay's area is treated. "as found" is the default because it is
# the honest picture: two histograms of different size look different because
# they are. Normalizing answers the other question -- whether they are the
# same shape -- and says so on the page, since a scaled plot that does not
# admit it invites someone to read absolute numbers off it.
NORM_NONE = "none"
NORM_AREA = "area"
NORM_OPTIONS = [
    {"label": "as found", "value": NORM_NONE},
    {"label": "area -> A (shapes)", "value": NORM_AREA},
]

# Columns in the all-histograms grid. One column would be twenty thousand
# pixels of scrolling for a typical DQM file; three is a page that can be
# scanned, and keeps each panel wide enough to read.
GRID_COLUMNS = 3
GRID_PANEL_HEIGHT = 240

# A ceiling on how many panels are drawn at once. A file of a hundred
# histograms is already a few megabytes of figure; beyond this the browser
# stops being responsive, so the extra ones are named rather than drawn.
MAX_GRID_PANELS = 120


def _catalog_available() -> bool:
    try:
        from dqm.catalog import available

        return available()
    except Exception:
        return False


def _dataset_options() -> List[dict]:
    """The DQM datasets, or an empty list if the catalog is unreachable."""
    try:
        from dqm.catalog import datasets

        return [{"label": d.name, "value": d.did} for d in datasets(DATASET_PATTERN)]
    except Exception:
        LOGGER.exception("could not list datasets")
        return []


def _file_options(did: Optional[str]) -> Tuple[List[dict], int]:
    """File options for a dataset, newest first. Returns (options, total).

    The label drops the dataset prefix every file shares, leaving the run and
    subrun -- which is the part that distinguishes them and the part worth
    reading in a dropdown.
    """
    if not did:
        return [], 0
    from dqm.catalog import dataset_files

    names = dataset_files(did)
    shown = names[:MAX_FILE_OPTIONS]
    options = []
    for n in shown:
        parts = n.split(".")
        label = parts[-2] if len(parts) >= 2 else n
        options.append({"label": label, "value": n})
    return options, len(names)


def _resolve(value: Optional[str], did: Optional[str]) -> Optional[str]:
    """Turn a field's value into something openable.

    With a dataset chosen the value is a metacat file name, which has to be
    resolved to a path; without one it is already a path or URL and is used
    as given.
    """
    if not value:
        return None
    if not did:
        return value
    from dqm.catalog import file_url

    return file_url(value)


def _is_golden(value: Optional[str]) -> bool:
    """True if the File B field is asking for the reference rather than a file."""
    return bool(value) and (value == GOLDEN_FILE
                            or str(value).strip().lower() == GOLDEN_WORD)


def _openable(name: str) -> str:
    """A golden file name as something uproot can open.

    The name in dqm.golden is recorded as given and never checked, so it may
    be a catalogued Mu2e name -- which mdh turns into a path with no lookup --
    or it may be a path already, which is how a hand-made average gets
    declared. Anything with a scheme or a leading slash is taken as the
    latter; the two are told apart here rather than by asking the catalog
    about something that was never in it.
    """
    if name.startswith("/") or "://" in name:
        return name
    from dqm.catalog import file_url

    return file_url(name)


def _normalization(norm: Optional[str], ha, hb):
    """(factor, ComparePars, note) for the chosen normalization.

    The factor goes to the drawing and the same factor goes to the
    comparison, because the `fraction` measure is area-sensitive: scaling one
    and not the other would draw two curves on top of each other and grade
    them a failure. See dqm.hist.compare.area_scale.
    """
    if norm != NORM_AREA or hb is None:
        return 1.0, ComparePars(), None

    pars = ComparePars()
    factor = area_scale(ha, hb, pars)
    if not factor:
        return 1.0, pars, ("areas not normalized: the overlay is empty, or "
                           "the two have different binning")
    return (factor, ComparePars(scale2=factor),
            f"overlay scaled by {factor:.4g} to match A's area")


def _declared_span(row) -> str:
    """"declared from <date>" for a time-positioned declaration.

    An open end reaches here as a real timestamp, not as a sentinel: dqmTool
    stores the word "infinity" and Postgres hands back 9999-12-31, so there
    is nothing for dqm.bands.as_time to read as absent. Printing that date
    would be noise, so a far-future end is rendered as "onwards" -- which is
    what an open-ended declaration means.
    """
    from dqm.bands import as_time

    start = as_time(getattr(row, "start_time", None))
    if start is None:
        return "declared range unknown"
    end = as_time(getattr(row, "end_time", None))
    if end is None or end.year > 9000:
        return f"declared from {start:%Y-%m-%d} onwards"
    return f"declared for {start:%Y-%m-%d} to {end:%Y-%m-%d}"


def _golden_caption(match) -> Any:
    """The provenance line for a reference overlay.

    A reference is not rigorously maintained, so which file was drawn, for
    which source, and how it was arrived at all have to be on the page. A
    silent overlay of the wrong reference is worse than none.
    """
    row = match.row
    bits = [html.Span("golden: ", style={"fontWeight": 600}),
            html.Code(match.filename)]
    where = []
    if match.source:
        where.append(match.source)
    if match.run is not None:
        where.append(f"run {match.run}")
    # The range of validity, however the declaration is positioned. A
    # time-ranged one stores run 0, so the run branch has to be the special
    # case and not the only one -- without this a nightly source's caption
    # said nothing at all about when the reference applies, which is most of
    # what the line is for.
    start, end = getattr(row, "start_run", None), getattr(row, "end_run", None)
    if start:
        where.append(f"declared for runs {start}-{end}")
    else:
        where.append(_declared_span(row))
    if getattr(row, "gid", None) is not None:
        where.append(f"gid {row.gid}")
    if where:
        bits.append(html.Span("  (" + ", ".join(str(w) for w in where) + ")",
                              style={"color": "#666"}))
    note = getattr(row, "note", None)
    if note is not None and str(note) not in ("", "None", "nan", "<NA>"):
        bits.append(html.Span(f"  -- {note}", style={"color": "#666",
                                                     "fontStyle": "italic"}))
    if match.how == "latest":
        bits.append(html.Div(
            f"No declaration covers {'run %s' % match.run if match.run else 'this file'}; "
            f"this is the one left open ended, i.e. the reference in use now.",
            style={"color": "#8a6d00"}))
    return html.Div(bits, style={"fontSize": "0.8rem", "marginTop": "0.3rem"})


def _with_golden(detail: Any, caption: Any, trouble: Optional[str]) -> Any:
    """The usual detail panel, with the reference's provenance above it.

    Either the caption naming what was overlaid or the reason there was
    nothing to overlay -- one of the two, always, whenever the reference was
    asked for. Silence would leave "no overlay appeared" meaning both "no
    reference is declared" and "the lookup broke".
    """
    if trouble:
        return html.Div([error_box(f"No golden file: {trouble}", kind="warn"),
                         detail])
    if caption is not None:
        return html.Div([caption, detail])
    return detail


def _golden_overlay(file_a_name: Optional[str]):
    """Resolve the reference for file A: (path, caption, problem).

    The lookup is dqm.golden.golden_for_file; everything here is turning its
    answer into something to open and something to read.
    """
    if not file_a_name:
        return None, None, "choose file A first -- the reference is looked up for it"
    try:
        from dqm.golden import golden_for_file
        from dqm.web.common import reader

        match = golden_for_file(file_a_name, reader())
    except Exception as exc:
        LOGGER.exception("golden lookup failed for %s", file_a_name)
        return None, None, f"golden lookup failed: {type(exc).__name__}: {exc}"

    if not match:
        return None, None, match.problem
    try:
        return _openable(match.filename), _golden_caption(match), None
    except Exception as exc:
        return None, None, (f"golden {match.filename} could not be located: "
                            f"{type(exc).__name__}: {exc}")


def layout() -> Any:
    have_catalog = _catalog_available()
    return html.Div(
        [
            card(
                [
                    row(
                        [
                            html.Div(
                                [
                                    html.Label("Dataset", style={"fontWeight": 600}),
                                    dcc.Dropdown(
                                        id=ID(PREFIX, "dataset"),
                                        options=_dataset_options() if have_catalog else [],
                                        value=None,
                                        placeholder=(
                                            "(optional) choose a dataset to pick files from"
                                            if have_catalog else
                                            "metacat not available -- type paths below"
                                        ),
                                        clearable=True,
                                        disabled=not have_catalog,
                                        style={"fontSize": "0.85rem"},
                                    ),
                                ],
                                style={"flex": "1", "minWidth": "340px"},
                            ),
                        ]
                    ),
                    html.Div(style={"height": "0.6rem"}),
                    row(
                        [
                            html.Div(
                                [
                                    html.Label("File A", style={"fontWeight": 600}),
                                    # Both widgets exist at all times and one is
                                    # hidden, because Dash fixes its callback
                                    # graph at startup -- a dropdown created
                                    # later would have no callbacks attached.
                                    html.Div(
                                        dcc.Input(
                                            id=ID(PREFIX, "file-a-path"),
                                            type="text",
                                            placeholder="/path/to/file.root  or  root://...",
                                            debounce=True,
                                            style={"width": "100%"},
                                        ),
                                        id=ID(PREFIX, "file-a-path-box"),
                                    ),
                                    html.Div(
                                        dcc.Dropdown(
                                            id=ID(PREFIX, "file-a-pick"),
                                            options=[], value=None,
                                            placeholder="(none)", clearable=True,
                                            style={"fontSize": "0.85rem"},
                                        ),
                                        id=ID(PREFIX, "file-a-pick-box"),
                                        style={"display": "none"},
                                    ),
                                ],
                                style={"flex": "1", "minWidth": "300px"},
                            ),
                            html.Div(
                                [
                                    html.Label("File B (optional overlay)",
                                               style={"fontWeight": 600}),
                                    html.Div(
                                        dcc.Input(
                                            id=ID(PREFIX, "file-b-path"),
                                            type="text",
                                            placeholder='second file, or "golden" for the reference',
                                            debounce=True,
                                            style={"width": "100%"},
                                        ),
                                        id=ID(PREFIX, "file-b-path-box"),
                                    ),
                                    html.Div(
                                        dcc.Dropdown(
                                            id=ID(PREFIX, "file-b-pick"),
                                            options=[], value=None,
                                            placeholder="(none)", clearable=True,
                                            style={"fontSize": "0.85rem"},
                                        ),
                                        id=ID(PREFIX, "file-b-pick-box"),
                                        style={"display": "none"},
                                    ),
                                ],
                                style={"flex": "1", "minWidth": "300px"},
                            ),
                        ]
                    ),
                    html.Div(id=ID(PREFIX, "dataset-note"),
                             style={"fontSize": "0.78rem", "color": "#666",
                                    "marginTop": "0.35rem"}),
                    html.Div(style={"height": "0.6rem"}),
                    row(
                        [
                            html.Div(
                                [
                                    html.Label("Histogram", style={"fontWeight": 600}),
                                    dcc.Dropdown(id=ID(PREFIX, "path"), options=[],
                                                 placeholder="choose a file first",
                                                 style={"fontSize": "0.85rem"}),
                                ],
                                style={"flex": "2", "minWidth": "320px"},
                            ),
                            html.Div(
                                [
                                    html.Label("Fit", style={"fontWeight": 600}),
                                    dcc.Dropdown(
                                        id=ID(PREFIX, "fit"),
                                        options=[
                                            {"label": "none", "value": "none"},
                                            {"label": "stored in file", "value": "stored"},
                                            {"label": "gaussian", "value": "gaussian"},
                                            {"label": "lorentzian", "value": "lorentzian"},
                                        ],
                                        value="none", clearable=False,
                                    ),
                                ],
                                style={"flex": "0 0 180px"},
                            ),
                            html.Div(
                                [
                                    html.Label("Normalize",
                                               style={"fontWeight": 600}),
                                    dcc.Dropdown(
                                        id=ID(PREFIX, "norm"),
                                        options=NORM_OPTIONS,
                                        value=NORM_NONE, clearable=False,
                                        style={"fontSize": "0.85rem"},
                                    ),
                                ],
                                style={"flex": "0 0 190px"},
                            ),
                            html.Div(
                                [
                                    html.Label("Options", style={"fontWeight": 600}),
                                    dcc.Checklist(
                                        id=ID(PREFIX, "opts"),
                                        options=[{"label": " log y", "value": "logy"}],
                                        value=[], inline=True,
                                    ),
                                ],
                                style={"flex": "0 0 120px"},
                            ),
                        ]
                    ),
                ]
            ),
            html.Div(id=ID(PREFIX, "status"), style={"margin": "0.5rem 0"}),
            dcc.Loading(
                dcc.Graph(id=ID(PREFIX, "graph")),
                type="default",
                overlay_style={"visibility": "visible", "opacity": 0.5},
                delay_show=300,
            ),
            html.Div(id=ID(PREFIX, "detail"), style={"marginTop": "0.75rem"}),
        ]
    )


def _draw_all(file_a: str, file_b: Optional[str], opts: List[str],
              fit_choice: Optional[str], golden: bool = False,
              norm: Optional[str] = None):
    """Every 1-D histogram in the file, as a grid of panels.

    Comparison runs for all of them when a second file is given -- it costs
    almost nothing -- and its verdict colours each panel's heading, so the
    ones that disagree can be picked out by eye without reading any numbers.

    Fits are deliberately not applied here. Fitting a typical file's worth of
    histograms takes the better part of ten seconds, and a fit is something to
    ask for once you know which histogram you care about. The status line says
    so rather than silently ignoring the setting.
    """
    opts = opts or []
    try:
        fa = open_file(file_a)
        entries = fa.histograms(ndim=1)
    except Exception as exc:
        return {}, error_box(f"{type(exc).__name__}: {exc}")

    if not entries:
        return {}, error_box("No 1-D histograms in that file.", kind="warn")

    fb = None
    if file_b:
        try:
            fb = open_file(file_b)
        except Exception as exc:
            return {}, error_box(f"file B: {type(exc).__name__}: {exc}")

    shown = entries[:MAX_GRID_PANELS]
    specs, titles, colors = [], [], []
    counts: dict = {}
    missing_in_b = 0
    normalized = 0

    for entry in shown:
        try:
            ha = fa.read(entry.path)
        except Exception:
            # One unreadable histogram should not lose the other eighty.
            LOGGER.debug("could not read %s", entry.path)
            continue

        spec = PlotSpec(xlabel="", ylabel="", logy="logy" in opts, legend=False)
        color = None

        hb = None
        if fb is not None:
            if entry.path in fb:
                try:
                    hb = fb.read(entry.path)
                except Exception:
                    LOGGER.debug("could not read %s from file B", entry.path)
                    hb = None
            else:
                missing_in_b += 1

        # Normalized per panel: each histogram has its own area, so one
        # factor for the file would be meaningless.
        factor, pars, _ = _normalization(norm, ha, hb)
        if factor != 1.0:
            normalized += 1

        # The reference goes down first and heavier, and the data over it as
        # points -- the ROOT habit of HIST then E1 P, which is also the only
        # order that keeps the data visible under a 2px line.
        if hb is not None and golden:
            spec.add_hist(hb, style="step", color=REFERENCE_COLOR,
                          weight=GOLDEN_WEIGHT, scale=factor)
            spec.add_hist(ha, style="errorbar", color=PALETTE[0])
        elif hb is not None:
            spec.add_hist(ha, style="step")
            spec.add_hist(hb, style="errorbar", scale=factor)
        else:
            spec.add_hist(ha, style="step")

        if hb is not None:
            try:
                c = compare_histograms(ha, hb, pars=pars, path=entry.path)
                color = c.color
                counts[c.status.name] = counts.get(c.status.name, 0) + 1
            except Exception:
                LOGGER.debug("could not compare %s", entry.path)

        specs.append(spec)
        titles.append(entry.name)
        colors.append(color)

    figure = to_plotly_grid(
        specs, titles=titles, cols=GRID_COLUMNS,
        height_each=GRID_PANEL_HEIGHT,
        title_colors=colors if fb is not None else None,
    )

    notes: List[Any] = [
        html.Span(f"{len(specs)} histograms", style={"fontWeight": 600})
    ]
    if len(entries) > len(shown):
        notes.append(html.Span(
            f"  |  showing the first {len(shown)} of {len(entries)}; "
            f"select one by name to see the rest", style={"color": "#8a6d00"}))
    if counts:
        tally = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
        notes.append(html.Span(f"  |  {tally}", style={"color": "#555"}))
    if missing_in_b and not golden:
        notes.append(html.Span(f"  |  {missing_in_b} not in file B",
                               style={"color": "#8a6d00"}))
    if normalized:
        notes.append(html.Span(
            f"  |  {normalized} overlay(s) scaled to match area -- shapes, "
            f"not sizes", style={"color": "#555"}))
    if fit_choice and fit_choice != "none":
        notes.append(html.Span(
            "  |  fits are not drawn for all histograms at once; "
            "select a single histogram to fit it", style={"color": "#8a6d00"}))

    detail = html.Div(notes)
    if fb is not None:
        detail = html.Div([
            html.Div(notes),
            html.Div("Panel headings are coloured by comparison verdict."
                     + ("  The reference is the heavier gold outline."
                        if golden else ""),
                     style={"fontSize": "0.8rem", "color": "#666",
                            "marginTop": "0.3rem"}),
        ])
    return figure, detail


def register(app) -> None:
    @app.callback(
        Output(ID(PREFIX, "file-a-path-box"), "style"),
        Output(ID(PREFIX, "file-a-pick-box"), "style"),
        Output(ID(PREFIX, "file-b-path-box"), "style"),
        Output(ID(PREFIX, "file-b-pick-box"), "style"),
        Output(ID(PREFIX, "file-a-pick"), "options"),
        Output(ID(PREFIX, "file-b-pick"), "options"),
        Output(ID(PREFIX, "file-a-pick"), "value"),
        Output(ID(PREFIX, "file-b-pick"), "value"),
        Output(ID(PREFIX, "dataset-note"), "children"),
        Input(ID(PREFIX, "dataset"), "value"),
    )
    def _dataset_chosen(did):
        """Swap the file fields between typed paths and dataset dropdowns.

        Both selections are cleared on every change, including when the
        dataset is cleared. Carrying a file over would leave a name from one
        dataset selected against another, or a bare file name sitting in a
        field that is now interpreted as a path -- either way the field would
        say something that is no longer true.
        """
        shown, hidden = {"display": "block"}, {"display": "none"}
        if not did:
            return (shown, hidden, shown, hidden, [], [], None, None, "")

        try:
            options, total = _file_options(did)
        except Exception as exc:
            LOGGER.exception("could not list files in %s", did)
            return (shown, hidden, shown, hidden, [], [], None, None,
                    error_box(f"{type(exc).__name__}: {exc}"))

        if not options:
            return (hidden, shown, hidden, shown, [], [], None, None,
                    error_box("That dataset has no files.", kind="warn"))

        note = f"{total} files"
        if total > len(options):
            note = (f"showing the newest {len(options)} of {total} files; "
                    f"clear the dataset to type a path directly")
        # B can also be the reference for whatever A is, which is not a file
        # of this dataset and is only resolved when the plot is drawn.
        b_options = [{"label": "golden (reference for file A)",
                      "value": GOLDEN_FILE}] + options
        return (hidden, shown, hidden, shown, options, b_options, None, None, note)

    @app.callback(
        Output(ID(PREFIX, "path"), "options"),
        Output(ID(PREFIX, "path"), "value"),
        Output(ID(PREFIX, "status"), "children"),
        Input(ID(PREFIX, "file-a-path"), "value"),
        Input(ID(PREFIX, "file-a-pick"), "value"),
        State(ID(PREFIX, "dataset"), "value"),
        State(ID(PREFIX, "path"), "value"),
    )
    def _load(path_a, pick_a, did, current):
        """List the histograms in file A, whichever way it was given."""
        chosen = pick_a if did else path_a
        if not chosen:
            return [], None, error_box(
                "Choose a dataset and a file, or type a file path.", kind="info")
        try:
            resolved = _resolve(chosen, did)
            with open_file(resolved) as f:
                entries = f.histograms(ndim=1)
        except Exception as exc:
            LOGGER.exception("could not open %s", chosen)
            return [], None, error_box(f"{type(exc).__name__}: {exc}")

        if not entries:
            return [], None, error_box("No 1-D histograms in that file.", kind="warn")

        options = ([{"label": f"all ({len(entries)} histograms)",
                     "value": ALL_HISTOGRAMS}]
                   + [{"label": e.path, "value": e.path} for e in entries])
        # Keep the current selection when the new file also has it, so
        # stepping through files of a dataset does not reset the view --
        # including "all", which stays meaningful across files.
        available = {o["value"] for o in options}
        value = current if current in available else entries[0].path
        return options, value, html.Span(
            f"{len(entries)} one-dimensional histograms", style={"color": "#555"})

    @app.callback(
        Output(ID(PREFIX, "graph"), "figure"),
        Output(ID(PREFIX, "detail"), "children"),
        Input(ID(PREFIX, "path"), "value"),
        Input(ID(PREFIX, "fit"), "value"),
        Input(ID(PREFIX, "norm"), "value"),
        Input(ID(PREFIX, "opts"), "value"),
        Input(ID(PREFIX, "file-b-path"), "value"),
        Input(ID(PREFIX, "file-b-pick"), "value"),
        State(ID(PREFIX, "file-a-path"), "value"),
        State(ID(PREFIX, "file-a-pick"), "value"),
        State(ID(PREFIX, "dataset"), "value"),
    )
    def _draw(path, fit_choice, norm, opts, path_b, pick_b, path_a, pick_a, did):
        chosen_a = pick_a if did else path_a
        chosen_b = pick_b if did else path_b
        if not path or not chosen_a:
            return {}, ""
        opts = opts or []

        # "golden" is not a file of the dataset: it is whichever reference
        # applies to file A, which is only known once A is known.
        golden = _is_golden(chosen_b)
        caption, trouble = None, None
        try:
            file_a = _resolve(chosen_a, did)
            if golden:
                file_b, caption, trouble = _golden_overlay(chosen_a)
            else:
                file_b = _resolve(chosen_b, did) if chosen_b else None
        except Exception as exc:
            return {}, error_box(f"{type(exc).__name__}: {exc}")

        if path == ALL_HISTOGRAMS:
            figure, detail = _draw_all(file_a, file_b, opts, fit_choice,
                                       golden=golden, norm=norm)
            return figure, _with_golden(detail, caption, trouble)

        try:
            fa = open_file(file_a)
            ha = fa.read(path)
            raw_a = fa.read_raw(path)
        except Exception as exc:
            return {}, error_box(f"{type(exc).__name__}: {exc}")

        spec = PlotSpec(title=path.rsplit("/", 1)[-1],
                        xlabel="", ylabel="entries", logy="logy" in opts)
        if not golden:
            spec.add_hist(ha, label="A", style="step")

        detail: List[Any] = []
        st = statistics(raw_a, ha)
        detail.append(
            html.Div(
                [
                    html.H4("File A", style={"margin": "0 0 0.3rem"}),
                    kv_table(
                        [
                            ("entries", f"{st.entries:.0f}"),
                            ("mean", f"{st.mean:.6g} +/- {st.mean_error:.3g}"),
                            ("std dev", f"{st.std_dev:.6g}"),
                            ("from fill-time stats", st.from_accumulators),
                        ]
                    ),
                ],
                style={"display": "inline-block", "verticalAlign": "top",
                       "marginRight": "2.5rem"},
            )
        )

        # File B is optional throughout: one file on its own is a perfectly
        # reasonable thing to look at, so its absence is not reported.
        hb = None
        if file_b:
            try:
                fb = open_file(file_b)
                if path in fb:
                    hb = fb.read(path)
                elif not golden:
                    # Worth saying for a file someone chose; not for a
                    # reference, where a histogram simply not being in it is
                    # ordinary and the empty overlay says so already.
                    detail.append(error_box(f"{path} is not in file B", kind="warn"))
            except Exception as exc:
                detail.append(error_box(f"file B: {type(exc).__name__}: {exc}"))

        # The overlay is scaled, if asked, before it is drawn or judged.
        factor, pars, scaled = _normalization(norm, ha, hb)
        if hb is not None:
            if golden:
                # Reference first and heavier, data over it as points.
                spec.add_hist(hb, label="golden", style="step", scale=factor,
                              color=REFERENCE_COLOR, weight=GOLDEN_WEIGHT)
            else:
                spec.add_hist(hb, label="B", style="errorbar", scale=factor)

        if golden:
            # After the reference, so the points sit on top of its outline.
            spec.add_hist(ha, label="A", style="errorbar", color=PALETTE[0])

        if fit_choice and fit_choice != "none":
            try:
                if fit_choice == "stored":
                    fit = get_fit(raw_a, hist=ha, prefer="stored")
                    if fit is not None and fit.source != "stored":
                        detail.append(
                            error_box(
                                "No fit is stored in the file for this histogram; "
                                "showing one computed here instead.",
                                kind="info",
                            )
                        )
                else:
                    fit = fit_histogram(ha, model=fit_choice)
                if fit is not None:
                    spec.add_fit(fit)
                    if not fit.success:
                        detail.append(error_box(f"fit did not converge: {fit.message}",
                                                kind="warn"))
            except Exception as exc:
                detail.append(error_box(f"fit: {type(exc).__name__}: {exc}", kind="warn"))

        if hb is not None:
            c = compare_histograms(ha, hb, pars=pars, path=path)
            detail.append(
                html.Div(
                    [
                        html.H4("Comparison", style={"margin": "0 0 0.3rem"}),
                        html.Div(
                            c.status.name,
                            style={"display": "inline-block",
                                   "padding": "0.15rem 0.6rem",
                                   "borderRadius": "4px", "color": "#fff",
                                   "background": c.color, "fontWeight": 600,
                                   "marginBottom": "0.4rem"},
                        ),
                        kv_table(
                            [
                                ("kolmogorov", f"{c.kolmogorov:.6g}"),
                                ("fraction", f"{c.fraction:.6g}"),
                                ("sum A / B", f"{c.sum1:.0f} / {c.sum2:.0f}"),
                            ]
                            # The sums above are always the areas as found, so
                            # the factor is worth stating next to them rather
                            # than leaving two numbers that look inconsistent
                            # with a plot where the curves coincide.
                            + ([("normalized", f"x{factor:.4g}")]
                               if factor != 1.0 else [])
                            + ([("note", c.note)] if c.note else [])
                        ),
                    ],
                    style={"display": "inline-block", "verticalAlign": "top"},
                )
            )

        if scaled:
            detail.append(html.Div(scaled, style={"fontSize": "0.8rem",
                                                  "color": "#666",
                                                  "marginTop": "0.3rem"}))
        return to_plotly(spec), _with_golden(html.Div(detail), caption, trouble)
