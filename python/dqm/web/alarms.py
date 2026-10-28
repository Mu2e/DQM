"""Alarms tab: the alarm episodes in dqm.alarms, and their evidence.

An episode is identified by (algo, config, subject, sid) -- which evaluator,
under which configuration, found what, on which source. The run and time spans
are a hull over what fired and do not claim every run inside them alarmed;
dqm.alarm_causes is the ground truth, and is shown per episode below.

dqm.reader has no typed accessor for these tables yet, so this reads them
through read_table. That is the gap to close when dqm.evaluate lands.
"""

from __future__ import annotations

import logging
from typing import Any, List

from dash import Input, Output, dash_table, dcc, html

from dqm.schema import (ALARM_LEVEL_NAMES as LEVEL_NAMES,
                        ALARM_STATUSES, TERMINAL_ALARM_STATUSES)
from dqm.web.common import (ID, REFRESH_MS, card, drawn_stamp, error_box,
                            kv_table, reader, row)

LOGGER = logging.getLogger("dqm.web.alarms")

PREFIX = "alarm-"

# Level is the episode's severity, escalating as the maximum over its causes.
LEVEL_COLORS = {0: "#95A5A6", 1: "#F4D03F", 2: "#E67E22", 3: "#E74C3C"}


def layout() -> Any:
    return html.Div(
        [
            card(
                row(
                    [
                        html.Div(
                            [
                                html.Label("Status", style={"fontWeight": 600}),
                                dcc.Dropdown(
                                    id=ID(PREFIX, "status"),
                                    options=[{"label": "any", "value": ""}]
                                    + [{"label": s, "value": s} for s in ALARM_STATUSES],
                                    value="",
                                    clearable=False,
                                ),
                            ],
                            style={"flex": "0 0 200px"},
                        ),
                        html.Div(
                            [
                                html.Label("Show", style={"fontWeight": 600}),
                                dcc.Checklist(
                                    id=ID(PREFIX, "opts"),
                                    options=[{"label": " open episodes only",
                                              "value": "open"}],
                                    value=[],
                                    inline=True,
                                ),
                            ],
                            style={"flex": "0 0 220px"},
                        ),
                        html.Div(
                            [
                                html.Label("Refresh", style={"fontWeight": 600}),
                                # Its own control, not another entry in
                                # "opts": that one filters what is shown, and
                                # a filter and a refresh policy should not
                                # share a widget.
                                dcc.Checklist(
                                    id=ID(PREFIX, "auto"),
                                    options=[{"label": " auto (10 min)",
                                              "value": "auto"}],
                                    value=[],
                                    inline=True,
                                ),
                            ],
                            style={"flex": "0 0 160px"},
                        ),
                    ]
                )
            ),
            # Starts disabled; the callback below arms it. A disabled
            # Interval never fires, so an idle page costs nothing.
            dcc.Interval(id=ID(PREFIX, "tick"), interval=REFRESH_MS,
                         disabled=True, n_intervals=0),
            html.Div(id=ID(PREFIX, "status-line"), style={"margin": "0.5rem 0"}),
            dcc.Loading(
                html.Div(id=ID(PREFIX, "table")),
                type="default",
                overlay_style={"visibility": "visible", "opacity": 0.5},
                delay_show=300,
            ),
            html.Div(id=ID(PREFIX, "causes"), style={"marginTop": "1rem"}),
        ]
    )


def _cause_rows(aid: int):
    """One (label, detail) pair per cause, with the ids decoded.

    Returns None when the episode has no causes at all.

    An iid and a vid say nothing on their own, so each is resolved: the vid to
    its metric name, the iid to the run or date of its interval.  The same
    decoding the MCP's get_alarm_causes does -- the page a person reads during
    a shift should not be the less informative of the two.
    """
    from dqm.reader.transport import where_eq

    r = reader()
    causes = r.read_table("alarm_causes",
                          clauses=[where_eq("aid", int(aid))], limit=None)
    if causes.empty:
        return None

    names = {}
    try:
        vids = [int(v) for v in causes["vid"].dropna().unique()]
        if vids:
            vv = r.values(vid=vids, limit=None)
            names = {
                int(x.vid): f"{x.groupx}/{x.subgroup}/{x.namex}"
                for x in vv.itertuples()
            }
    except Exception:
        LOGGER.debug("could not decode vids for aid=%s", aid, exc_info=True)

    where = {}
    try:
        iids = [int(i) for i in causes["iid"].dropna().unique()]
        if iids:
            iv = r.intervals(iid=iids, limit=None)
            for x in iv.itertuples():
                run = getattr(x, "start_run", None)
                # Run 0 is this schema's "no run": a day-aggregation source
                # stores it for every interval and keeps the real position in
                # the timestamps.
                if run is not None and run == run and int(run) != 0:
                    sub = getattr(x, "start_subrun", None)
                    where[int(x.iid)] = f"run {int(run)}:{int(sub or 0)}"
                else:
                    t = getattr(x, "start_time", None)
                    where[int(x.iid)] = (f"{t:%Y-%m-%d}" if t is not None and t == t
                                         else f"iid {int(x.iid)}")
    except Exception:
        LOGGER.debug("could not decode iids for aid=%s", aid, exc_info=True)

    rows = []
    for c in causes.itertuples():
        iid = int(c.iid)
        # A NULL vid is a global test -- about the interval as a whole rather
        # than any single metric.  Guard against both spellings of missing:
        # pandas gives <NA> for a nullable column and nan for a float one.
        blank = c.vid is None or str(c.vid) in ("<NA>", "nan") or c.vid != c.vid
        metric = "(global test)" if blank else names.get(int(c.vid),
                                                         f"vid {int(c.vid)}")
        label = where.get(iid, f"iid {iid}")
        level = LEVEL_NAMES[int(c.level)] if int(c.level) in range(len(LEVEL_NAMES)) \
            else str(c.level)
        rows.append((label, f"{metric}   [{level}]"))
    return rows


def register(app) -> None:
    @app.callback(
        Output(ID(PREFIX, "tick"), "disabled"),
        Input(ID(PREFIX, "auto"), "value"),
    )
    def _arm_refresh(auto):
        """Run the timer only while the box is ticked."""
        return "auto" not in (auto or [])

    @app.callback(
        Output(ID(PREFIX, "table"), "children"),
        Output(ID(PREFIX, "status-line"), "children"),
        Input(ID(PREFIX, "status"), "value"),
        Input(ID(PREFIX, "opts"), "value"),
        # Only to make the timer reload: its value is never read. The alarms
        # query is not cached, so re-running this callback is the refresh.
        Input(ID(PREFIX, "tick"), "n_intervals"),
    )
    def _load(status, opts, _tick):
        opts = opts or []
        try:
            r = reader()
            clauses = []
            if status:
                from dqm.reader.transport import where_eq

                clauses.append(where_eq("status", status))
            if "open" in opts:
                from dqm.reader.transport import where_eq

                clauses.append(where_eq("open", "true"))
            df = r.read_table("alarms", clauses=clauses or None, limit=500)
        except Exception as exc:
            LOGGER.exception("alarm query failed")
            return "", error_box(f"{type(exc).__name__}: {exc}")

        if df.empty:
            return "", html.Div([
                error_box("No alarm episodes match.", kind="info"),
                html.Span(drawn_stamp(), style={"color": "#888",
                                                "fontSize": "0.8rem"}),
            ])

        # Decorate with the source each episode concerns -- an sid alone is
        # not something anyone can read.
        try:
            sources = r.sources(sid=[int(s) for s in df["sid"].dropna().unique()],
                                limit=None)
            df = df.merge(sources, on="sid", how="left")
            df["source"] = (df["process"].astype(str) + "/" + df["stream"].astype(str))
        except Exception:
            df["source"] = df["sid"].astype(str)

        show = df[["aid", "algo", "config", "subject", "source", "level",
                   "status", "open", "ctime", "mtime"]].copy()
        for col in ("ctime", "mtime"):
            show[col] = show[col].dt.strftime("%Y-%m-%d %H:%M")

        table = dash_table.DataTable(
            id=ID(PREFIX, "dt"),
            columns=[{"name": c, "id": c} for c in show.columns],
            data=show.to_dict("records"),
            row_selectable="single",
            page_size=15,
            sort_action="native",
            style_cell={"fontFamily": "monospace", "fontSize": "0.85rem",
                        "textAlign": "left", "padding": "0.4rem"},
            style_header={"fontWeight": 600, "background": "#f2f2f2"},
            style_data_conditional=[
                {
                    "if": {"filter_query": f"{{level}} = {lvl}", "column_id": "level"},
                    "backgroundColor": color,
                    "color": "#fff",
                }
                for lvl, color in LEVEL_COLORS.items()
            ]
            + [
                {
                    "if": {"filter_query": f'{{status}} = "{s}"', "column_id": "status"},
                    "color": "#888",
                }
                for s in TERMINAL_ALARM_STATUSES
            ],
        )
        line = html.Div([
            html.Span(f"{len(df)} episode(s); select one to see its causes",
                      style={"color": "#555"}),
            html.Span("  |  " + drawn_stamp(), style={"color": "#888"}),
        ])
        return table, line

    @app.callback(
        Output(ID(PREFIX, "causes"), "children"),
        Input(ID(PREFIX, "dt"), "selected_rows"),
        Input(ID(PREFIX, "dt"), "data"),
    )
    def _causes(selected, data):
        """The evidence for the selected episode.

        Everything after the selection check is inside one try.  It was not,
        and a NameError in the rendering raised out of the callback -- which
        Dash answers by leaving the output at its previous value.  The panel
        was empty, so it stayed empty: no causes, no error box, no clue.  A
        failure here has to be visible, because the alternative is a display
        that looks like it works.
        """
        if not selected or not data:
            return ""

        try:
            aid = data[selected[0]]["aid"]
            rows = _cause_rows(int(aid))
        except Exception as exc:
            LOGGER.exception("could not build the causes panel")
            return error_box(f"{type(exc).__name__}: {exc}")

        if rows is None:
            return error_box(f"Episode {aid} has no recorded causes.", kind="warn")

        return html.Div(
            [
                html.H4(f"Causes for episode {aid}", style={"margin": "0 0 0.4rem"}),
                kv_table(rows),
            ]
        )
