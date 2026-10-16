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

from dqm.schema import ALARM_STATUSES, TERMINAL_ALARM_STATUSES
from dqm.web.common import ID, card, error_box, kv_table, reader, row

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
                    ]
                )
            ),
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


def register(app) -> None:
    @app.callback(
        Output(ID(PREFIX, "table"), "children"),
        Output(ID(PREFIX, "status-line"), "children"),
        Input(ID(PREFIX, "status"), "value"),
        Input(ID(PREFIX, "opts"), "value"),
    )
    def _load(status, opts):
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
            return "", error_box("No alarm episodes match.", kind="info")

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
        line = html.Span(f"{len(df)} episode(s); select one to see its causes",
                         style={"color": "#555"})
        return table, line

    @app.callback(
        Output(ID(PREFIX, "causes"), "children"),
        Input(ID(PREFIX, "dt"), "selected_rows"),
        Input(ID(PREFIX, "dt"), "data"),
    )
    def _causes(selected, data):
        if not selected or not data:
            return ""
        aid = data[selected[0]]["aid"]
        try:
            from dqm.reader.transport import where_eq

            r = reader()
            causes = r.read_table("alarm_causes",
                                  clauses=[where_eq("aid", int(aid))], limit=None)
        except Exception as exc:
            return error_box(f"{type(exc).__name__}: {exc}")

        if causes.empty:
            return error_box(f"Episode {aid} has no recorded causes.", kind="warn")

        rows = []
        for c in causes.itertuples():
            # A NULL vid is a global test -- one about the interval as a whole
            # rather than about a single variable.
            vid = "(global test)" if c.vid is None or str(c.vid) == "<NA>" else int(c.vid)
            rows.append((f"iid {int(c.iid)}", f"vid {vid}   level {int(c.level)}"))

        return html.Div(
            [
                html.H4(f"Causes for episode {aid}", style={"margin": "0 0 0.4rem"}),
                kv_table(rows),
            ]
        )
