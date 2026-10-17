"""Evaluate DQM metrics and raise alarms.

One driver runs one evaluator over the points that have appeared since it last
looked, and commits whatever it finds. A cron entry per evaluator, each with
its own working directory, config file and log.

    from dqm.evaluate import load_config, Driver

    cfg = load_config("crv-tight.yaml")
    result = Driver(cfg).run()

Or from the command line, which is what cron uses:

    dqm-driver crv-tight.yaml

Needs the `evaluate` extra:

    pip install 'mu2e-dqm[evaluate]'

The pieces, in the order they matter:

    base.py     the driver-evaluator contract -- Point, Finding, Evaluator
    points.py   database rows -> Points, in the right order for each job
    state.py    the watermark, one small JSON file per driver
    config.py   one YAML -> one configured evaluator
    driver.py   the loop, the commits, the log
    limits.py   is each metric inside its band?
    trends.py   has each metric moved, compared with its own past?
"""

from dqm.evaluate.base import (  # noqa: F401
    LEVELS,
    LEVEL_NAMES,
    Cause,
    DqmEvaluateError,
    Evaluator,
    Finding,
    Limit,
    Measurement,
    Point,
)
from dqm.evaluate.config import (  # noqa: F401
    DriverConfig,
    build_evaluator,
    load_config,
)
from dqm.evaluate.driver import Driver, DriverResult, setup_logging  # noqa: F401
from dqm.evaluate.limits import LimitsEvaluator  # noqa: F401
from dqm.evaluate.trends import TrendsEvaluator  # noqa: F401
from dqm.evaluate.points import load_history, load_points, new_points  # noqa: F401
from dqm.evaluate.state import State, load_state, save_state  # noqa: F401

__all__ = [
    "LEVELS", "LEVEL_NAMES", "Cause", "DqmEvaluateError", "Evaluator",
    "Finding", "Limit", "Measurement", "Point",
    "DriverConfig", "build_evaluator", "load_config",
    "Driver", "DriverResult", "setup_logging",
    "LimitsEvaluator",
    "TrendsEvaluator",
    "load_history", "load_points", "new_points",
    "State", "load_state", "save_state",
]
