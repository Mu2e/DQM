"""The DQM web application: one Dash app, one process, one URL.

Dash is built on Flask -- `app.server` is a real Flask application -- so this
is a Flask app with a Dash UI layered on it, not two separate things. That
matters practically: the static-image routes in dqm.web.routes are registered
directly on the same server, so a rendered report figure is just another URL
served by this process.

Everything users do with DQM lives here as a tab: timelines from the database,
histogram overlays from ROOT files, and alarm episodes. One install, one
service, one place to look.

Tab content is built lazily, the first time a tab is opened -- a tab nobody
opens costs nothing, which matters because the histogram tab reads files and
the timeline tab queries the database. Once built it is kept and merely
hidden, so switching away and back preserves everything the user set up.
`suppress_callback_exceptions` is required for that: callbacks reference
components that do not exist until their tab has first been shown.

Component ids are prefixed per tab (`timeline-`, `hist-`, `alarm-`) because
one Dash app has one id namespace -- three tabs that each independently wanted
an id called "graph" would silently collide.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from dqm.errors import DqmConfigError, DqmDependencyError

try:
    import dash
    from dash import Dash, Input, Output, State, dcc, html
except ImportError as exc:  # pragma: no cover - dependency error path
    raise DqmDependencyError(
        "dqm.web needs dash. Install the extra: pip install 'mu2e-dqm[web]'"
    ) from exc

from dqm import __version__
from dqm.web import alarms as alarms_tab
from dqm.web import histogram as hist_tab
from dqm.web import timeline as timeline_tab

LOGGER = logging.getLogger("dqm.web")

__all__ = ["create_app", "app", "server"]

TABS = {
    "timeline": ("Timelines", timeline_tab),
    "histogram": ("Histograms", hist_tab),
    "alarms": ("Alarms", alarms_tab),
}


def _body(key: str) -> str:
    """The id of the container holding one tab's content."""
    return f"tab-body-{key}"


def _header() -> Any:
    return html.Div(
        [
            html.Div(
                [
                    html.H1("Mu2e DQM", style={"margin": "0", "fontSize": "1.5rem"}),
                    html.Span(
                        f"mu2e-dqm {__version__}",
                        style={"color": "#888", "fontSize": "0.8rem",
                               "marginLeft": "0.75rem"},
                    ),
                ],
                style={"display": "flex", "alignItems": "baseline"},
            ),
        ],
        style={
            "padding": "0.75rem 1.25rem",
            "borderBottom": "1px solid #ddd",
            "background": "#fafafa",
        },
    )


def create_app(
    requests_pathname_prefix: Optional[str] = None,
    routes_pathname_prefix: Optional[str] = None,
    title: str = "Mu2e DQM",
) -> "Dash":
    """Build the application.

    The two prefix arguments are for serving behind a reverse proxy. They are
    not the same setting and are not always equal: `routes_` is the path this
    process serves on, `requests_` is the path the browser asks for. They
    differ whenever the proxy strips the prefix before forwarding, which is
    the usual arrangement and the usual source of a blank page with 404s on
    every asset.
    """
    # Fall back to Dash's own environment variables, because a WSGI server
    # imports `server` from this module and never sees the CLI's flags:
    #
    #   DASH_REQUESTS_PATHNAME_PREFIX=/computing/ops/dqmapp/   browser asks for
    #   DASH_ROUTES_PATHNAME_PREFIX=/computing/ops/dqmapp/     served on
    #
    # Dash reads these itself, so Dash's own routes move whether or not this
    # function looks at them.  We read them too because the export routes in
    # dqm.web.routes are plain Flask routes that Dash knows nothing about: left
    # at "/" while Dash moved to the prefix, the page's export links pointed at
    # the prefixed path and got the catch-all HTML instead of a PNG.  Reading
    # the same variables Dash does is what keeps the two halves agreeing.
    if requests_pathname_prefix is None:
        requests_pathname_prefix = (
            os.environ.get("DASH_REQUESTS_PATHNAME_PREFIX") or None)
    if routes_pathname_prefix is None:
        routes_pathname_prefix = (os.environ.get("DASH_ROUTES_PATHNAME_PREFIX")
                                  or requests_pathname_prefix)

    kwargs = {"suppress_callback_exceptions": True, "title": title}
    if requests_pathname_prefix:
        # Dash requires both to start and end with "/", and requires
        # requests_ to end with routes_.  Catch it here with a message that
        # names the variable, rather than letting Dash raise about an argument
        # the operator never passed.
        for name, value in (
                ("DASH_REQUESTS_PATHNAME_PREFIX", requests_pathname_prefix),
                ("DASH_ROUTES_PATHNAME_PREFIX", routes_pathname_prefix)):
            if value and not (value.startswith("/") and value.endswith("/")):
                raise DqmConfigError(
                    f"{name}={value!r} must start and end with '/', "
                    f"e.g. '/computing/ops/dqmapp/'"
                )
        kwargs["requests_pathname_prefix"] = requests_pathname_prefix
    if routes_pathname_prefix:
        kwargs["routes_pathname_prefix"] = routes_pathname_prefix

    application = Dash(__name__, **kwargs)

    application.layout = html.Div(
        [
            _header(),
            dcc.Tabs(
                id="tabs",
                value="timeline",
                children=[
                    dcc.Tab(label=label, value=key)
                    for key, (label, _) in TABS.items()
                ],
            ),
            dcc.Loading(
                html.Div(
                    # One container per tab, all present from the start. A tab
                    # is built the first time it is opened and then only
                    # hidden, never torn down -- see the callback below.
                    [html.Div(id=_body(key)) for key in TABS],
                    style={"padding": "1rem 1.25rem"},
                ),
                type="default",
                # Only spin while a tab body is being built. Without this, the
                # wrapper reacts to *any* loading state among its descendants
                # -- so a slow graph query would unmount the whole tab, taking
                # keyboard focus off whatever control triggered it and blanking
                # its displayed value mid-interaction.
                target_components={_body(key): "children" for key in TABS},
            ),
        ],
        style={"fontFamily": "system-ui, sans-serif"},
    )

    @application.callback(
        [Output(_body(key), "children") for key in TABS],
        [Output(_body(key), "style") for key in TABS],
        Input("tabs", "value"),
        [State(_body(key), "children") for key in TABS],
    )
    def _switch_tab(value, *existing):
        """Show the selected tab, building it only if it has never been built.

        Tabs are hidden rather than destroyed. Rebuilding on every switch --
        which is what returning a fresh layout() does -- throws away
        everything the user set up: selected sources and metrics, the number
        of timelines, the window, and the zoom on every plot. Anyone
        comparing a timeline against a histogram switches back and forth
        constantly, and losing the arrangement each time makes that unusable.

        Returning no_update for an already-built tab leaves its component
        tree untouched in the browser, so its state survives; `display: none`
        is what hides it, and a hidden node keeps everything.
        """
        keys = list(TABS)
        children, styles = [], []
        for key, built in zip(keys, existing):
            if key == value and not built:
                _, module = TABS[key]
                try:
                    children.append(module.layout())
                except Exception as exc:  # one broken tab must not take the app down
                    LOGGER.exception("tab %s failed to build", key)
                    children.append(
                        html.Div(
                            [
                                html.H3("This tab could not be loaded"),
                                html.Pre(f"{type(exc).__name__}: {exc}",
                                         style={"whiteSpace": "pre-wrap",
                                                "color": "#b00"}),
                            ]
                        )
                    )
            else:
                children.append(dash.no_update)
            styles.append({"display": "block" if key == value else "none"})
        return children + styles

    # Each tab registers its own callbacks against the shared app.
    for _, module in TABS.values():
        module.register(application)

    from dqm.web.routes import register_routes

    # The exports must live where Dash lives, or a proxy serving the app
    # under a path will not forward them.
    register_routes(application.server, routes_pathname_prefix or "/")

    return application


# Module-level instances, so a WSGI server can be pointed straight at them:
#   gunicorn 'dqm.web.app:server'
app = create_app()
server = app.server
