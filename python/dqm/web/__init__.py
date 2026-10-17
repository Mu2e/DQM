"""The DQM web application: one Dash app with a tab per activity.

    dqm-web --port 8100

Dash is built on Flask, so `dqm.web.app.server` is a real Flask application --
which is what lets the static-image export routes live in the same process as
the interactive UI.

Needs the web extra: pip install 'mu2e-dqm[web]'
"""

__all__ = ["create_app"]


def __getattr__(name):
    """Resolve create_app lazily, so importing this package does not build
    the application (and so does not connect to anything) as a side effect."""
    if name in ("create_app", "app", "server"):
        from dqm.web import app as _app

        return getattr(_app, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
