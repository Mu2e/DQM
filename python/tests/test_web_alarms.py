"""The Alarms table: what order the episodes arrive in, and how the two
judgement columns are painted.

No browser and no database. The app is built as gunicorn would build it, and
the callback that fills the table is called directly with a fake reader, so
these check the rows and the conditional styles the browser would be sent.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

dash = pytest.importorskip("dash")

try:
    from dqm.web import alarms
    from dqm.web.app import create_app
except Exception as exc:  # a missing web extra (plotly, uproot, ...)
    pytest.skip(f"dqm.web cannot be imported here: {exc}", allow_module_level=True)

UTC = dt.timezone.utc


def _stamp(day):
    return pd.Timestamp(dt.datetime(2026, 11, day, 12, 0, tzinfo=UTC))


# One episode per status, deliberately out of order, with the levels and
# mtimes set so that each tie-break in turn decides something.
EPISODES = [
    {"aid": 1, "algo": "limits", "config": "c0", "subject": "out_of_limits",
     "sid": 118, "level": 2, "status": "retired", "open": False,
     "ctime": _stamp(1), "mtime": _stamp(1)},
    {"aid": 2, "algo": "limits", "config": "c0", "subject": "out_of_limits",
     "sid": 118, "level": 1, "status": "active", "open": True,
     "ctime": _stamp(2), "mtime": _stamp(2)},
    {"aid": 3, "algo": "trends", "config": "c1", "subject": "step",
     "sid": 118, "level": 3, "status": "acknowledged", "open": True,
     "ctime": _stamp(3), "mtime": _stamp(3)},
    {"aid": 4, "algo": "trends", "config": "c1", "subject": "step",
     "sid": 118, "level": 3, "status": "active", "open": True,
     "ctime": _stamp(4), "mtime": _stamp(4)},
    {"aid": 5, "algo": "limits", "config": "c0", "subject": "out_of_limits",
     "sid": 118, "level": 3, "status": "active", "open": True,
     "ctime": _stamp(5), "mtime": _stamp(5)},
    {"aid": 6, "algo": "limits", "config": "c0", "subject": "out_of_limits",
     "sid": 118, "level": 0, "status": "silenced", "open": False,
     "ctime": _stamp(6), "mtime": _stamp(6)},
]

SOURCES = [{"sid": 118, "process": "crvreco", "stream": "kpp_crv",
            "aggregation": "file", "version": "006-001"}]


class FakeReader:
    def __init__(self, episodes=None):
        self.rows = EPISODES if episodes is None else episodes

    def read_table(self, table, clauses=None, limit=None):
        assert table == "alarms"
        return pd.DataFrame(self.rows)

    def sources(self, sid=None, limit=None):
        return pd.DataFrame(SOURCES)


@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture
def load(app, monkeypatch):
    """The alarms-table callback, with the database replaced."""
    key = next(k for k in app.callback_map if "alarm-table.children" in k)
    fn = app.callback_map[key]["callback"].__wrapped__

    def call(episodes=None, status="", opts=None):
        monkeypatch.setattr(alarms, "reader", lambda: FakeReader(episodes))
        table, _line = fn(status, opts or [], 0)
        return table

    return call


def _styles(table, column, prop):
    """{cell value: style property} for one column's conditional styles."""
    out = {}
    for rule in table.style_data_conditional:
        if rule["if"].get("column_id") != column:
            continue
        query = rule["if"]["filter_query"]
        value = query.split("=", 1)[1].strip().strip('"')
        out[value] = rule.get(prop)
    return out


# -- order -------------------------------------------------------------------

def test_active_episodes_come_first(load):
    """What the first page has to show: active, then acknowledged, then the
    statuses nobody needs to look at."""
    data = load().data
    assert [r["status"] for r in data] == [
        "active", "active", "active", "acknowledged", "silenced", "retired"]


def test_within_a_status_the_worst_comes_first(load):
    data = load().data
    active = [r for r in data if r["status"] == "active"]
    assert [r["level"] for r in active] == [3, 3, 1]


def test_within_a_level_the_most_recently_extended_comes_first(load):
    """mtime, not ctime: an old episode still being extended is live news."""
    data = load().data
    assert [r["aid"] for r in data if r["status"] == "active"] == [5, 4, 2]


def test_a_status_outside_the_vocabulary_sorts_last_and_does_not_raise(load):
    """dqm.alarms.status is enforced in code, not by a constraint, so a value
    nobody here knows about can turn up. It must not crash the tab, and it
    must not outrank active."""
    odd = EPISODES + [{**EPISODES[1], "aid": 7, "status": "reticulating"}]
    data = load(episodes=odd).data
    assert data[-1]["status"] == "reticulating"
    assert data[0]["status"] == "active"


def test_the_viewer_can_still_re_sort(load):
    assert load().sort_action == "native"


# -- colour ------------------------------------------------------------------

def test_level_is_coloured_text_on_white(load):
    table = load()
    assert _styles(table, "level", "backgroundColor") == {
        str(lvl): "#fff" for lvl in alarms.LEVEL_TEXT_COLORS}
    assert _styles(table, "level", "color") == {
        str(lvl): c for lvl, c in alarms.LEVEL_TEXT_COLORS.items()}


def test_status_is_coloured_text_on_white(load):
    table = load()
    assert set(_styles(table, "status", "backgroundColor").values()) == {"#fff"}
    colors = _styles(table, "status", "color")
    assert colors["active"] == alarms.STATUS_TEXT_COLORS["active"]
    assert colors["acknowledged"] == alarms.STATUS_TEXT_COLORS["acknowledged"]


def test_active_is_red_and_acknowledged_is_orange(load):
    """Named rather than inferred: these two are what an operator scans for."""
    colors = _styles(load(), "status", "color")
    assert colors["active"] == "#C0392B"
    assert colors["acknowledged"] == "#AF601A"


def test_every_status_in_the_vocabulary_is_painted(load):
    """A status with no rule would render as plain black text, which reads as
    a missing value rather than as a quiet one."""
    colors = _styles(load(), "status", "color")
    for status in alarms.ALARM_STATUSES:
        assert colors.get(status), f"{status} has no colour"


def test_the_quiet_statuses_are_grey(load):
    colors = _styles(load(), "status", "color")
    for status in ("silenced", "retired", "deleted"):
        assert colors[status] == alarms._GREY


def test_the_text_colours_are_darker_than_the_background_palette(load):
    """The two palettes exist for opposite jobs. LEVEL_COLORS sit behind
    white text; used as text on white, the yellow would be unreadable."""
    def luma(hex_colour):
        r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
        return 0.299 * r + 0.587 * g + 0.114 * b

    for lvl, text in alarms.LEVEL_TEXT_COLORS.items():
        assert luma(text) < luma(alarms.LEVEL_COLORS[lvl])
        assert luma(text) < 160  # legible against white
