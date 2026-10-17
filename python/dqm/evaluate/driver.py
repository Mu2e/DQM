"""The driver: find new points, hand them to one evaluator, commit findings.

One driver instance runs one evaluator, configured by one YAML file, from one
working directory, under one cron entry. Nothing is shared between drivers.

Startup and keepup are not modes here, they are the same loop seeing
different amounts of work. A driver with no state file starts at nid=0 and
walks forward `max_points` at a time; once it has caught up, each invocation
finds the handful of points that arrived since. The flow from one to the other
needs no decision and no switch.

What the driver owns, because it is identical for every algorithm:

  * finding new work, in commit order, so nothing is skipped
  * assembling history, in run/time order, so a trend sees the real timeline
  * the watermark, and only advancing it when the work actually landed
  * committing findings through dqmTool
  * the log

What it does not own: any judgement about the data. That is the evaluator's,
and the driver never inspects a finding beyond counting it.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from dqm.errors import DqmConfigError, DqmWriteError
from dqm.evaluate.base import Evaluator, Finding, Point
from dqm.evaluate.config import DriverConfig, build_evaluator
from dqm.evaluate.points import History, new_points
from dqm.evaluate.state import State, load_state, save_state

LOGGER = logging.getLogger("dqm.evaluate.driver")

__all__ = ["Driver", "DriverResult", "setup_logging"]

#: How many times to retry a commit that failed for a transient reason. Two
#: evaluators racing to open the same episode leaves the loser with a unique
#: violation and a rolled-back transaction; retrying wins it on the second
#: attempt. The alternative is a lost finding, because a point past the
#: watermark is never examined again.
COMMIT_RETRIES = 2
COMMIT_RETRY_WAIT = 2.0


def setup_logging(cfg: DriverConfig) -> None:
    """Log to the config's file, and to the console when run by hand.

    Deliberately terse and one line per event, so that `tail -f driver.log`
    reads as a running account of what the driver is doing rather than
    something to be grepped afterwards.
    """
    level = getattr(logging, cfg.log_level, logging.INFO)
    root = logging.getLogger("dqm")
    root.setLevel(level)
    for h in list(root.handlers):
        root.removeHandler(h)

    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    path = cfg.log_path
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(path)
        fh.setFormatter(fmt)
        root.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)


@dataclass
class DriverResult:
    """What one invocation did."""

    examined: int = 0
    findings: int = 0
    committed: int = 0
    failed: int = 0
    high_nid: int = 0
    caught_up: bool = True
    errors: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed and not self.errors


class Driver:
    """Runs one evaluator over whatever is new."""

    def __init__(self, cfg: DriverConfig, reader=None, evaluator: Optional[Evaluator] = None,
                 dqmtool: str = "dqmTool"):
        self.cfg = cfg
        self.evaluator = evaluator or build_evaluator(cfg)
        self.dqmtool = dqmtool
        self._reader = reader

    # -- reading ----------------------------------------------------------

    @property
    def reader(self):
        if self._reader is None:
            from dqm.reader import DqmReader

            self._reader = DqmReader()
        return self._reader

    # -- the loop ---------------------------------------------------------

    def run(self) -> DriverResult:
        cfg = self.cfg
        result = DriverResult()

        state = load_state(cfg.workdir, cfg.algo, cfg.config, cfg.sid,
                           name=cfg.state_file or "driver-state.json")
        situation = "startup" if state.fresh else "keepup"
        LOGGER.info("--- %s | %s | max %d points | %s | state nid=%d",
                    cfg, situation, cfg.max_points, cfg.floor, state.nid)

        try:
            points, high_nid = new_points(
                self.reader, cfg.sid, after_nid=state.nid,
                max_points=cfg.max_points,
                min_run=cfg.min_run, min_time=cfg.min_time,
            )
        except Exception as exc:
            LOGGER.error("could not read new points: %s: %s",
                         type(exc).__name__, exc)
            result.errors.append(f"read failed: {exc}")
            return result

        if not points:
            LOGGER.info("nothing new since nid=%d -- up to date", state.nid)
            # Everything new may have been below the floor, in which case the
            # watermark still moves so the same rows are not re-read next time.
            if high_nid > state.nid:
                state.advance(high_nid, 0, 0, cfg.mode)
                save_state(cfg.workdir, state,
                           name=cfg.state_file or "driver-state.json")
                LOGGER.info("watermark moved to %d past skipped rows", state.nid)
            return result

        # The real range these points cover, not state.nid+1: a source whose
        # measurements begin well above zero would otherwise be reported as
        # starting at 1.
        LOGGER.info("%d new point(s) to examine, %s .. %s (nid up to %d)",
                    len(points), points[0].label, points[-1].label, high_nid)

        lookback = int(getattr(self.evaluator, "lookback", 0) or 0)
        committed_nid = state.nid

        # One fetch for the whole batch rather than one per point: see
        # dqm.evaluate.points.History.
        past = None
        if lookback:
            try:
                past = History(self.reader, cfg.sid)
            except Exception as exc:
                LOGGER.warning("could not load history for sid=%s (%s) -- "
                               "evaluating without it", cfg.sid, type(exc).__name__)

        for point in points:
            history: Sequence[Point] = ()
            if past is not None:
                try:
                    history = past.before(point, lookback)
                except Exception as exc:
                    LOGGER.warning("%s: history unavailable (%s) -- evaluating "
                                   "without it", point.label, type(exc).__name__)

            try:
                findings = self.evaluator.evaluate(point, history)
                findings = self.evaluator.check_findings(findings or [])
            except Exception as exc:
                # One bad point must not end the run: the rest of the batch is
                # still worth examining, and the watermark simply does not
                # advance past the failure.
                LOGGER.error("%s: evaluator raised %s: %s",
                             point.label, type(exc).__name__, exc)
                result.errors.append(f"{point.label}: {exc}")
                result.failed += 1
                break

            result.examined += 1
            result.findings += len(findings)

            if not findings:
                # The examined-and-clean record. Log-only for now: it is the
                # only thing that can explain a hole in an episode's span, but
                # nothing reads it yet.
                LOGGER.info("%s: clean (%d metrics)",
                            point.label, len(point.measurements))
                committed_nid = max(committed_nid, self._nid_of(point, high_nid))
                continue

            for finding in findings:
                ok = self._commit(finding, point)
                if ok:
                    result.committed += 1
                else:
                    result.failed += 1
                    result.errors.append(f"{point.label}: commit failed")
                    break
            else:
                committed_nid = max(committed_nid, self._nid_of(point, high_nid))
                continue
            break

        # In report mode the watermark advances anyway: the run is a dry run,
        # and re-examining the same points on every invocation would never let
        # it reach the present. Back up the state file before switching to
        # commit mode -- see dqm.evaluate.state.
        advance_to = high_nid if (result.ok or not cfg.commit) else committed_nid
        state.advance(advance_to, result.examined, result.findings, cfg.mode)
        path = save_state(cfg.workdir, state,
                          name=cfg.state_file or "driver-state.json")

        result.high_nid = state.nid
        result.caught_up = len(points) < cfg.max_points

        LOGGER.info(
            "--- done: %d examined, %d finding(s), %d committed, %d failed | "
            "nid now %d%s",
            result.examined, result.findings, result.committed, result.failed,
            state.nid, "" if result.caught_up else " | more to do, batch was full",
        )
        if not cfg.commit and result.findings:
            LOGGER.info("report mode: %d finding(s) were NOT written to the "
                        "database", result.findings)
        LOGGER.debug("state file %s", path)
        return result

    @staticmethod
    def _nid_of(point: Point, fallback: int) -> int:
        """The watermark value this point accounts for.

        A point's measurements are one contiguous block of nids, so advancing
        to the batch high-water mark once the point is done is correct; the
        fallback is used because a Point does not carry its nids.
        """
        return fallback

    # -- writing ----------------------------------------------------------

    def _cause_arg(self, finding: Finding):
        """The value for dqmTool --cause, and a temp file to clean up if any.

        dqmTool decides how to read this argument by looking for a comma: a
        string containing one is a single inline cause, anything else is the
        name of a file holding one csv per line.  So a finding with several
        causes -- which is the normal case, one per metric -- has to go
        through a file.  Joining them with commas produced one malformed
        cause and a rejected commit.

        The file goes in the working directory rather than /tmp so that it
        sits beside the log when a commit fails, and its name cannot contain
        a comma or dqmTool would read the name itself as a cause.
        """
        lines = [c.as_csv() for c in finding.causes]
        if len(lines) == 1:
            return lines[0], None

        fd, path = tempfile.mkstemp(dir=str(self.cfg.workdir),
                                    prefix="causes-", suffix=".txt")
        with os.fdopen(fd, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        if "," in path:
            os.unlink(path)
            raise DqmWriteError(
                f"the working directory path contains a comma ({path}), which "
                f"dqmTool would read as an inline cause. Move the driver's "
                f"workdir somewhere without one."
            )
        return path, path

    def _commit(self, finding: Finding, point: Point) -> bool:
        """Write one finding, unless this driver is in report mode."""
        cfg = self.cfg
        causes = ",".join(c.as_csv() for c in finding.causes)

        if not cfg.commit:
            # One short line per finding: a cause list can run to dozens of
            # entries, which makes a tailed log unreadable.  The full list is
            # at debug level for when it is actually wanted.
            LOGGER.info("WOULD COMMIT subject=%s level=%d causes=%d",
                        finding.subject, finding.level, len(finding.causes))
            LOGGER.debug("causes: %s", causes)
            return True

        try:
            cause_arg, scratch = self._cause_arg(finding)
        except DqmWriteError as exc:
            LOGGER.error("%s", exc)
            return False

        cmd = [
            self.dqmtool, "commit-alarm",
            "--algo", cfg.algo,
            "--config", cfg.config,
            "--subject", finding.subject,
            "--sid", str(cfg.sid),
            "--cause", cause_arg,
        ]
        if finding.note:
            cmd += ["--note", finding.note]

        try:
            return self._attempt(cmd, finding)
        finally:
            # After every retry, not after the first: each attempt re-runs the
            # same command and re-reads the same file.
            if scratch:
                try:
                    os.unlink(scratch)
                except OSError:
                    LOGGER.debug("could not remove %s", scratch)

    def _attempt(self, cmd, finding: Finding) -> bool:
        for attempt in range(1, COMMIT_RETRIES + 2):
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True,
                                      timeout=120)
            except subprocess.TimeoutExpired:
                LOGGER.warning("commit timed out (attempt %d) for subject=%s",
                               attempt, finding.subject)
                proc = None
            except FileNotFoundError:
                LOGGER.error("%s is not on PATH -- cannot commit", self.dqmtool)
                return False

            if proc is not None and proc.returncode == 0:
                LOGGER.info("COMMITTED subject=%s level=%d causes=%d",
                            finding.subject, finding.level, len(finding.causes))
                return True

            detail = ""
            if proc is not None:
                detail = (proc.stderr or proc.stdout or "").strip().splitlines()
                detail = detail[-1] if detail else f"exit {proc.returncode}"
            if attempt <= COMMIT_RETRIES:
                LOGGER.warning("commit failed (%s), retrying in %.0fs",
                               detail, COMMIT_RETRY_WAIT)
                time.sleep(COMMIT_RETRY_WAIT)
            else:
                LOGGER.error("commit failed for subject=%s after %d attempts: %s",
                             finding.subject, attempt, detail)
        return False
