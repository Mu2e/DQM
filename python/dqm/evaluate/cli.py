"""The `dqm-driver` script -- what cron runs.

    dqm-driver /path/to/crv-tight.yaml

Exit status is what a cron job needs to decide whether to shout: 0 if the
invocation did its work, 1 if anything failed. Everything else goes to the
log named in the config.
"""

from __future__ import annotations

import argparse
import logging
import sys

from dqm.errors import DqmError
from dqm.evaluate.config import load_config
from dqm.evaluate.driver import Driver, setup_logging


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Run one DQM evaluator over whatever is new.")
    ap.add_argument("config", help="the driver's YAML config file")
    ap.add_argument("--commit", action="store_true",
                    help="write findings to the database, overriding the "
                         "config's commit flag")
    ap.add_argument("--no-commit", action="store_true",
                    help="report only, overriding the config's commit flag")
    ap.add_argument("--max-points", type=int, default=None,
                    help="override max_points for this invocation")
    ap.add_argument("--check", action="store_true",
                    help="load the config and the evaluator, then exit")
    args = ap.parse_args(argv)

    try:
        cfg = load_config(args.config)
    except DqmError as exc:
        print(f"ERROR - {exc}", file=sys.stderr)
        return 1

    if args.commit and args.no_commit:
        print("ERROR - --commit and --no-commit are contradictory",
              file=sys.stderr)
        return 1
    if args.commit:
        cfg.commit = True
    if args.no_commit:
        cfg.commit = False
    if args.max_points is not None:
        if args.max_points <= 0:
            print("ERROR - --max-points must be positive", file=sys.stderr)
            return 1
        cfg.max_points = args.max_points

    setup_logging(cfg)
    log = logging.getLogger("dqm.evaluate")

    try:
        driver = Driver(cfg)
    except DqmError as exc:
        log.error("%s", exc)
        return 1

    if args.check:
        log.info("OK: %s ready (lookback=%s, workdir=%s)",
                 cfg, getattr(driver.evaluator, "lookback", 0), cfg.workdir)
        return 0

    try:
        result = driver.run()
    except DqmError as exc:
        log.error("%s", exc)
        return 1
    except Exception as exc:
        log.exception("unexpected failure: %s", exc)
        return 1

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
