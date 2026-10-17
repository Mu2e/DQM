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
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Tuple

import dash
from dash import Input, Output, State, dcc, html

from dqm.hist import (
    ComparePars,
    compare_histograms,
    fit_histogram,
    get_fit,
    open_file,
    statistics,
)
from dqm.plot import PlotSpec, to_plotly, to_plotly_grid
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
                                            placeholder="second file to compare against",
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
              fit_choice: Optional[str]):
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

    for entry in shown:
        try:
            ha = fa.read(entry.path)
        except Exception:
            # One unreadable histogram should not lose the other eighty.
            LOGGER.debug("could not read %s", entry.path)
            continue

        spec = PlotSpec(xlabel="", ylabel="", logy="logy" in opts, legend=False)
        spec.add_hist(ha, style="step")
        color = None

        if fb is not None:
            if entry.path in fb:
                try:
                    hb = fb.read(entry.path)
                    spec.add_hist(hb, style="errorbar")
                    c = compare_histograms(ha, hb, pars=ComparePars(), path=entry.path)
                    color = c.color
                    counts[c.status.name] = counts.get(c.status.name, 0) + 1
                except Exception:
                    LOGGER.debug("could not compare %s", entry.path)
            else:
                missing_in_b += 1

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
    if missing_in_b:
        notes.append(html.Span(f"  |  {missing_in_b} not in file B",
                               style={"color": "#8a6d00"}))
    if fit_choice and fit_choice != "none":
        notes.append(html.Span(
            "  |  fits are not drawn for all histograms at once; "
            "select a single histogram to fit it", style={"color": "#8a6d00"}))

    detail = html.Div(notes)
    if fb is not None:
        detail = html.Div([
            html.Div(notes),
            html.Div("Panel headings are coloured by comparison verdict.",
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
        return (hidden, shown, hidden, shown, options, options, None, None, note)

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
        Input(ID(PREFIX, "opts"), "value"),
        Input(ID(PREFIX, "file-b-path"), "value"),
        Input(ID(PREFIX, "file-b-pick"), "value"),
        State(ID(PREFIX, "file-a-path"), "value"),
        State(ID(PREFIX, "file-a-pick"), "value"),
        State(ID(PREFIX, "dataset"), "value"),
    )
    def _draw(path, fit_choice, opts, path_b, pick_b, path_a, pick_a, did):
        chosen_a = pick_a if did else path_a
        chosen_b = pick_b if did else path_b
        if not path or not chosen_a:
            return {}, ""
        opts = opts or []

        try:
            file_a = _resolve(chosen_a, did)
            file_b = _resolve(chosen_b, did) if chosen_b else None
        except Exception as exc:
            return {}, error_box(f"{type(exc).__name__}: {exc}")

        if path == ALL_HISTOGRAMS:
            return _draw_all(file_a, file_b, opts, fit_choice)

        try:
            fa = open_file(file_a)
            ha = fa.read(path)
            raw_a = fa.read_raw(path)
        except Exception as exc:
            return {}, error_box(f"{type(exc).__name__}: {exc}")

        spec = PlotSpec(title=path.rsplit("/", 1)[-1],
                        xlabel="", ylabel="entries", logy="logy" in opts)
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
                    spec.add_hist(hb, label="B", style="errorbar")
                else:
                    detail.append(error_box(f"{path} is not in file B", kind="warn"))
            except Exception as exc:
                detail.append(error_box(f"file B: {type(exc).__name__}: {exc}"))

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
            c = compare_histograms(ha, hb, pars=ComparePars(), path=path)
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
                            + ([("note", c.note)] if c.note else [])
                        ),
                    ],
                    style={"display": "inline-block", "verticalAlign": "top"},
                )
            )

        return to_plotly(spec), html.Div(detail)
