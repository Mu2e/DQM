"""Flask routes for static figure export.

Registered on the same Flask server the Dash UI runs on, so a report-quality
image of what is on screen is just a URL from this process -- which is what
makes it linkable straight into an elog entry or a wiki page.

    /report/timeline.png?series=5:15&mode=time&window=365
    /report/timeline.pdf?series=115:98,115:99&mode=run&window=50

`series` is a comma-separated list of source:metric pairs, mirroring the rows
in the application. `sid=&vid=` is still accepted for a single series, so
links made before multiple timelines existed keep working. `window` is
optional: omitting it exports the entire history, matching what a blank
window field shows on screen.

The figure comes from the same PlotSpec the interactive view uses, rendered
through dqm.plot.static instead of dqm.plot.interactive, so the image and the
screen cannot disagree about content.
"""

from __future__ import annotations

import logging

from dqm.plot import PlotSpec

LOGGER = logging.getLogger("dqm.web.routes")

__all__ = ["register_routes"]

# Formats served, mapped to the content type to send them as.
FORMATS = {
    "png": "image/png",
    "pdf": "application/pdf",
    "svg": "image/svg+xml",
}


def _timeline_specs(pairs, mode: str, window):
    """Build one spec per panel -- the same construction the tab performs.

    Kept in step with dqm.web.timeline deliberately: an exported image that
    disagreed with the screen it came from would be worse than no export at
    all. In particular the run window is taken across every panel at once, so
    the exported stack has the single shared x range the screen does.

    Returns (specs, titles).
    """
    from dqm.plot.spec import PALETTE
    from dqm.web.common import reader, runs_for_metric
    from dqm.web.timeline import MODES

    r = reader()

    run_floor = None
    if mode == "run" and window is not None:
        all_runs = sorted({run for s, v in pairs for run in runs_for_metric(s, v)},
                          reverse=True)
        if all_runs:
            run_floor = all_runs[min(int(window), len(all_runs)) - 1]

    name_by_vid = {
        int(v.vid): f"{v.groupx}/{v.subgroup}/{v.namex}"
        for v in r.values(vid=[v for _, v in pairs], limit=None).itertuples()
    }
    source_by_sid = {
        int(s.sid): f"{s.process}/{s.stream} v{s.version}"
        for s in r.sources(sid=[s for s, _ in pairs], limit=None).itertuples()
    }

    specs, titles = [], []
    for index, (sid, vid) in enumerate(pairs):
        query = dict(sid=sid, vid=vid, limit=None)
        if mode == "run":
            if run_floor is not None:
                query["run_min"] = run_floor
        elif window is not None:
            query["recent_days"] = float(window)
        df = r.numbers(**query)

        metric = name_by_vid.get(vid, str(vid))
        titles.append(f"{metric}  -  {source_by_sid.get(sid, sid)}")
        spec = PlotSpec(xlabel=MODES[mode]["axis"], ylabel=metric, legend=False)
        if not df.empty:
            key = "start_run" if mode == "run" else "end_time"
            ordered = df.sort_values(key)
            spec.add_series(ordered[key], ordered["valuex"],
                            yerr=ordered["sigma"], label=metric,
                            color=PALETTE[index % len(PALETTE)], style="markers")
        specs.append(spec)
    return specs, titles


def _parse_series(request):
    """Read the requested (source, metric) pairs from the query string.

    Accepts `series=5:15,115:98`, and the older `sid=&vid=` for one pair.
    Returns (pairs, error_message).
    """
    raw = request.args.get("series")
    if raw:
        pairs = []
        for chunk in raw.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            try:
                sid_s, vid_s = chunk.split(":", 1)
                pairs.append((int(sid_s), int(vid_s)))
            except ValueError:
                return None, f"malformed series entry {chunk!r}; expected source:metric"
        if not pairs:
            return None, "series is empty"
        return pairs, ""

    try:
        sid = int(request.args.get("sid", 0))
        vid = int(request.args.get("vid", 0))
    except ValueError:
        return None, "sid and vid must be numbers"
    if not sid or not vid:
        return None, "give series=source:metric, or sid= and vid="
    return [(sid, vid)], ""


def register_routes(server, routes_pathname_prefix: str = "/") -> None:
    """Attach the export routes to a Flask server.

    `routes_pathname_prefix` must match what Dash was given, or the exports
    end up somewhere the proxy does not forward.  Dash moves its own routes
    under the prefix but knows nothing about these, so registering them at "/"
    unconditionally left them reachable only at the server root -- fine when
    the app is at a hostname root, broken behind a proxy serving it under a
    path.

    /healthz is deliberately NOT prefixed: it is for the proxy and for
    systemd, which check the process directly rather than through the path the
    browser uses, and keeping it at a fixed location means a health check does
    not have to be reconfigured alongside the prefix.
    """
    prefix = routes_pathname_prefix or "/"
    if not prefix.endswith("/"):
        prefix += "/"
    from flask import Response, request

    @server.route(prefix + "report/timeline.<fmt>")
    def report_timeline(fmt):
        if fmt not in FORMATS:
            return Response(f"unsupported format {fmt!r}; use "
                            f"{', '.join(sorted(FORMATS))}", status=400)
        mode = request.args.get("mode", "time")
        if mode not in ("time", "run"):
            return Response("mode must be 'time' or 'run'", status=400)
        pairs, problem = _parse_series(request)
        if problem:
            return Response(problem, status=400)

        try:
            # Absent or empty means no window at all -- the whole history --
            # matching a blank window field in the application. `days` is
            # still accepted so links made before the run axis existed keep
            # working.
            raw = request.args.get("window", request.args.get("days"))
            window = None if raw in (None, "") else float(raw)
        except ValueError:
            return Response("window must be a number", status=400)
        if window is not None and window <= 0:
            return Response("window must be greater than zero", status=400)

        try:
            specs, titles = _timeline_specs(pairs, mode, window)
        except Exception as exc:
            LOGGER.exception("report build failed")
            return Response(f"{type(exc).__name__}: {exc}", status=500)

        if all(sp.is_empty() for sp in specs):
            return Response("no data for that selection", status=404)

        stem = "_".join(f"{s}-{v}" for s, v in pairs[:3])
        if len(pairs) > 3:
            stem += f"_and{len(pairs) - 3}more"
        return _render(specs, titles, fmt, f"timeline_{stem}_{mode}")

    @server.route("/healthz")
    def healthz():
        """Liveness check, for the reverse proxy and for systemd."""
        from dqm import __version__

        return {"status": "ok", "version": __version__}


def _render(specs, titles, fmt: str, basename: str):
    """Render a stack of specs to an HTTP response in the requested format."""
    from flask import Response

    from dqm.plot.static import to_matplotlib_grid
    import matplotlib.pyplot as plt
    from io import BytesIO

    fig, axes = to_matplotlib_grid(specs, width=9.0,
                                   height_each=4.0 if len(specs) == 1 else 2.6)
    # matplotlib has no subplot_titles, so each panel is titled directly --
    # which is what ties a panel to the row that selected it.
    for ax, title in zip(axes, titles):
        ax.set_title(title, fontsize=10)
    buf = BytesIO()
    try:
        fig.savefig(buf, format=fmt, dpi=150, bbox_inches="tight")
    finally:
        # A long-running server renders many figures; an unclosed one leaks.
        plt.close(fig)

    return Response(
        buf.getvalue(),
        mimetype=FORMATS[fmt],
        headers={"Content-Disposition": f'inline; filename="{basename}.{fmt}"'},
    )
