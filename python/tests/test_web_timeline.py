"""The Timelines tab's window field: one owner, and a dashboard's window kept.

No browser and no database. The app is built as gunicorn would build it, its
callback graph is read from /_dash-dependencies (what the browser receives),
and callbacks are called directly with a Dash callback context, following the
renderer's rule for what fires next: after a callback returns, every *other*
callback with a returned property among its inputs runs, whether or not the
value changed (a callback is never re-fired by its own output).

Only the callbacks that write the window field are followed down the chain;
the plot callback needs a database and does not write the window.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Dict, List

import pytest

dash = pytest.importorskip("dash")

try:
    from dqm.web import timeline
    from dqm.web.app import create_app
except Exception as exc:  # a missing web extra (plotly, uproot, ...)
    pytest.skip(f"dqm.web cannot be imported here: {exc}", allow_module_level=True)

from dash._callback_context import context_value
from dash._utils import AttributeDict

WINDOW = "timeline-window.value"
WINDOW_PROPS = {WINDOW, "timeline-window.placeholder", "timeline-window-label.children"}
NO_UPDATE = type(dash.no_update)


def _outputs(spec: str) -> List[str]:
    """"..a.x...b.y.." -> ["a.x", "b.y"]; a single output is just "a.x"."""
    if spec.startswith(".."):
        return spec[2:-2].split("...")
    return [spec]


def _key(dep: Dict) -> str:
    cid = dep["id"]
    if isinstance(cid, dict):
        cid = json.dumps(cid, sort_keys=True, separators=(",", ":"))
    return f"{cid}.{dep['property']}"


@pytest.fixture(scope="module")
def app():
    return create_app()


def test_no_output_is_written_by_two_callbacks(app):
    """The check the renderer makes under `dqm-web --debug`.

    With duplicate outputs and no allow_duplicate, the renderer reports
    "Duplicate callback outputs" and builds no callback graph, so no callback
    in the app runs. Without --debug the check is skipped and both writers run.
    """
    deps = app.server.test_client().get("/_dash-dependencies").get_json()
    writers = Counter(out for d in deps for out in _outputs(d["output"])
                      if "@" not in out)  # "@<hash>" marks allow_duplicate
    assert writers[WINDOW] == 1
    assert [o for o, n in writers.items() if n > 1] == []


class _Page:
    """The browser's view of the Timelines controls, and the renderer's loop."""

    def __init__(self, app):
        self.app = app
        rows = timeline.MAX_SERIES
        sid_all = '{"index":["ALL"],"type":"timeline-sid"}'
        vid_all = '{"index":["ALL"],"type":"timeline-vid"}'
        # As timeline.layout() builds the tab.
        self.props = {
            f"{sid_all}.value": [timeline.DEFAULT_SID] + [None] * (rows - 1),
            f"{vid_all}.value": [timeline.DEFAULT_VID] + [None] * (rows - 1),
            f"{vid_all}.options": [[]] * rows,
            "timeline-count.value": 1,
            "timeline-mode.value": "time",
            WINDOW: timeline.DEFAULT_DAYS,
            "timeline-window.placeholder": timeline.DEFAULT_DAYS,
            "timeline-window-label.children": timeline.MODES["time"]["label"],
            "timeline-opts.value": ["limits"],
            "timeline-dashboard.value": None,
            "timeline-dashboard-note.children": "",
        }

    def _call(self, key: str, trigger: str):
        cb = self.app.callback_map[key]
        args = [self.props.get(_key(d)) for d in cb["inputs"] + cb["state"]]
        context_value.set(AttributeDict(
            triggered_inputs=[{"prop_id": trigger, "value": self.props.get(trigger)}]))
        out = cb["callback"].__wrapped__(*args)
        names = _outputs(key)
        if len(names) == 1:
            out = (out,)
        returned = set()
        for name, value in zip(names, out):
            if isinstance(value, NO_UPDATE):
                continue
            if isinstance(value, list) and name.startswith("{"):
                old = self.props.get(name) or [None] * len(value)
                value = [o if isinstance(v, NO_UPDATE) else v for v, o in zip(value, old)]
            self.props[name] = value
            returned.add(name)
        return returned

    def user_sets(self, prop: str, value) -> None:
        """A user edit, then every window-writing callback it sets off.

        A callback already run in this chain is not run again, as the
        renderer drops a callback whose own output comes back to its input.
        """
        self.props[prop] = value
        fired = set()
        pending = [prop]
        while pending:
            changed = pending.pop(0)
            for key, cb in self.app.callback_map.items():
                if key in fired or not (WINDOW_PROPS & set(_outputs(key))):
                    continue
                if changed not in {_key(d) for d in cb["inputs"]}:
                    continue
                fired.add(key)
                pending.extend(self._call(key, changed))


@pytest.fixture
def page(app, monkeypatch):
    """The page with the database calls the controls make replaced."""
    vids: Dict[str, int] = {}

    def resolve_series(spec, _reader):
        metric = getattr(spec, "metric", None) or str(spec)
        return timeline.DEFAULT_SID, vids.setdefault(metric, 100 + len(vids)), None

    def value_options(sid):
        return [{"label": f"m{v}", "value": v} for v in [timeline.DEFAULT_VID, *vids.values()]]

    monkeypatch.setattr(timeline, "reader", lambda: object())
    monkeypatch.setattr(timeline, "resolve_series", resolve_series)
    monkeypatch.setattr(timeline, "_value_options", value_options)
    return _Page(app)


@pytest.mark.parametrize("name, window", [
    ("Nightly reco - calorimeter", "90"),
    ("Nightly job resources", "180"),
])
def test_dashboard_window_is_kept(page, name, window):
    """Before the fix the mode the dashboard set fired the second writer,
    which put the mode default (365) back over the dashboard's window."""
    if name not in timeline.DASHBOARDS_BY_NAME:
        pytest.skip(f"shipped dashboard {name!r} not configured here")
    page.user_sets("timeline-dashboard.value", name)
    assert page.props["timeline-mode.value"] == "time"
    assert page.props[WINDOW] == window


def test_run_mode_dashboard_sets_run_label(page):
    name = "CRV calibration - recent runs"
    if name not in timeline.DASHBOARDS_BY_NAME:
        pytest.skip(f"shipped dashboard {name!r} not configured here")
    page.user_sets("timeline-dashboard.value", name)
    assert page.props["timeline-mode.value"] == "run"
    assert page.props[WINDOW] == "50"
    assert page.props["timeline-window-label.children"] == timeline.MODES["run"]["label"]


def test_mode_change_resets_window_to_that_modes_default(page):
    """Unchanged behaviour: switching the axis by hand resets the window."""
    page.props[WINDOW] = "90"
    page.user_sets("timeline-mode.value", "run")
    assert page.props[WINDOW] == timeline.DEFAULT_RUNS
    assert page.props["timeline-window.placeholder"] == timeline.DEFAULT_RUNS
    assert page.props["timeline-window-label.children"] == timeline.MODES["run"]["label"]


def test_mode_change_keeps_a_blank_window(page):
    page.props[WINDOW] = ""
    page.user_sets("timeline-mode.value", "run")
    assert page.props[WINDOW] == ""
    assert page.props["timeline-window-label.children"] == timeline.MODES["run"]["label"]
