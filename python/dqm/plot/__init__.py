"""Build a figure once, render it interactively or as a static image.

    from dqm.plot import PlotSpec, to_plotly, save_image

    spec = PlotSpec(title="crvPEsMPV sector 0", xlabel="PEs")
    spec.add_hist(h, label="run 125086")
    spec.add_fit(fit)

    fig = to_plotly(spec)              # for the Dash app
    save_image(spec, "report.pdf")     # for a note or an elog post

The renderers are imported lazily, so importing this package does not pull in
plotly and matplotlib together -- a batch job that only writes PNGs should not
need plotly installed, and vice versa. Both arrive with the `plot` extra:

    pip install 'mu2e-dqm[plot]'
"""

from dqm.plot.spec import (  # noqa: F401
    PALETTE,
    FitTrace,
    HistTrace,
    LineMarker,
    PlotSpec,
    hist_points,
)

__all__ = [
    "PlotSpec",
    "HistTrace",
    "FitTrace",
    "LineMarker",
    "PALETTE",
    "hist_points",
    # lazily resolved, see __getattr__
    "to_plotly",
    "to_plotly_grid",
    "to_matplotlib",
    "to_matplotlib_grid",
    "save_image",
    "save_image_grid",
    "to_png_bytes",
    "to_data_uri",
]

_LAZY = {
    "to_plotly": "dqm.plot.interactive",
    "to_plotly_grid": "dqm.plot.interactive",
    "to_matplotlib": "dqm.plot.static",
    "to_matplotlib_grid": "dqm.plot.static",
    "save_image": "dqm.plot.static",
    "save_image_grid": "dqm.plot.static",
    "to_png_bytes": "dqm.plot.static",
    "to_data_uri": "dqm.plot.static",
}


def __getattr__(name):
    """Resolve a renderer on first use.

    Keeps `import dqm.plot` cheap and, more importantly, keeps it working
    where only one of the two rendering stacks is installed.
    """
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    return getattr(importlib.import_module(module), name)


def __dir__():
    return sorted(__all__)
