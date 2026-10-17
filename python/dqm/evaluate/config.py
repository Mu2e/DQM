"""The YAML one cron job hands its driver.

One file, one evaluator. Each cron has its own working directory, config and
log, so nothing here is shared and two drivers cannot tread on each other.

    # crv-tight.yaml
    algo:    limits
    config:  crv-tight-0
    sid:     115

    commit:     false        # false = report only, nothing written
    max_points: 200          # per invocation; startup walks forward
    lookback:   0            # overrides the algorithm's own default

    # Where to start on the physics timeline. Without one of these, switching
    # an evaluator on means examining the whole history first. Either, or
    # both, or neither.
    min_run:  125000
    min_time: 2026-10-01     # a date, or a full timestamp

    workdir:  /exp/mu2e/app/users/rlc/dqm-drivers/crv-tight
    log:      driver.log     # relative to workdir
    log_level: INFO

    pars:                    # passed to the evaluator, algorithm-specific
      level: alarm
      use_sigma: false

`commit` defaults to false, so a driver that is run before anyone has thought
about the switch reports and writes nothing. Turning it on is a deliberate
edit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from dqm.errors import DqmConfigError, DqmDependencyError

LOGGER = logging.getLogger("dqm.evaluate.config")

__all__ = ["DriverConfig", "load_config", "REGISTRY", "build_evaluator"]


# algo name -> class. A plain dict rather than entry points: there will be a
# handful of these, all in this package, and a registry that can be read in
# one screen is worth more than a plug-in mechanism.
def _registry() -> Dict[str, type]:
    from dqm.evaluate.limits import LimitsEvaluator

    out = {LimitsEvaluator.algo: LimitsEvaluator}
    try:  # trends arrives in a later pass; absence must not break limits
        from dqm.evaluate.trends import TrendsEvaluator

        out[TrendsEvaluator.algo] = TrendsEvaluator
    except ImportError:
        pass
    return out


REGISTRY = _registry


@dataclass
class DriverConfig:
    """Everything one driver instance needs."""

    algo: str
    config: str
    sid: int

    commit: bool = False
    max_points: int = 200
    lookback: Optional[int] = None
    min_run: Optional[int] = None
    min_time: Optional[Any] = None

    workdir: Path = field(default_factory=Path.cwd)
    log: Optional[str] = "driver.log"
    log_level: str = "INFO"
    state_file: Optional[str] = None

    pars: Dict[str, Any] = field(default_factory=dict)

    source: Optional[Path] = None

    @property
    def floor(self) -> str:
        """The configured starting place, for a log line."""
        bits = []
        if self.min_run is not None:
            bits.append(f"run>={self.min_run}")
        if self.min_time is not None:
            bits.append(f"time>={self.min_time:%Y-%m-%d}")
        return " ".join(bits) or "no floor"

    @property
    def mode(self) -> str:
        return "commit" if self.commit else "report"

    @property
    def log_path(self) -> Optional[Path]:
        if not self.log:
            return None
        p = Path(self.log)
        return p if p.is_absolute() else self.workdir / p

    def __str__(self) -> str:
        return f"{self.algo}/{self.config} sid={self.sid} [{self.mode}]"


def load_config(path: str | Path) -> DriverConfig:
    """Read and validate one driver's YAML.

    Everything that can be wrong about a config is reported here, at startup,
    rather than when the first point is examined -- a cron job that fails in
    its first second is much easier to diagnose than one that fails an hour
    in.
    """
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - dependency error path
        raise DqmDependencyError(
            "reading a driver config needs PyYAML. Install the extra: "
            "pip install 'mu2e-dqm[evaluate]'"
        ) from exc

    target = Path(path)
    if not target.exists():
        raise DqmConfigError(f"no such config file: {target}")

    try:
        raw = yaml.safe_load(target.read_text()) or {}
    except Exception as exc:
        raise DqmConfigError(
            f"{target} is not valid YAML ({type(exc).__name__}: {exc})"
        ) from exc

    if not isinstance(raw, Mapping):
        raise DqmConfigError(f"{target} should hold a mapping, got {type(raw).__name__}")

    # One evaluator per driver. A list is rejected rather than quietly taking
    # its first entry: if someone writes two, they meant two, and silently
    # running one of them would leave the other never examined.
    if isinstance(raw.get("evaluators"), (list, tuple)):
        raise DqmConfigError(
            f"{target}: this driver runs exactly one evaluator. Give algo, "
            f"config and sid at the top level and use one config file (and "
            f"one cron entry) per evaluator."
        )

    missing = [k for k in ("algo", "config", "sid") if raw.get(k) in (None, "")]
    if missing:
        raise DqmConfigError(f"{target}: missing required key(s) {missing}")

    algo = str(raw["algo"])
    known = REGISTRY()
    if algo not in known:
        raise DqmConfigError(
            f"{target}: unknown algo {algo!r}. Known: {sorted(known)}"
        )

    try:
        sid = int(raw["sid"])
    except (TypeError, ValueError):
        raise DqmConfigError(f"{target}: sid must be an integer, got {raw['sid']!r}")

    try:
        max_points = int(raw.get("max_points", 200))
    except (TypeError, ValueError):
        raise DqmConfigError(
            f"{target}: max_points must be an integer, got {raw.get('max_points')!r}"
        )
    if max_points <= 0:
        raise DqmConfigError(f"{target}: max_points must be positive, got {max_points}")

    min_run = raw.get("min_run")
    if min_run is not None:
        try:
            min_run = int(min_run)
        except (TypeError, ValueError):
            raise DqmConfigError(
                f"{target}: min_run must be an integer run number, got {min_run!r}")

    min_time = raw.get("min_time")
    if min_time is not None:
        # YAML parses a bare date into datetime.date; everything downstream
        # compares against pandas timestamps, so normalise here rather than
        # discovering the mismatch mid-run.
        try:
            from dqm.timeutil import to_utc

            min_time = to_utc(min_time)
        except Exception as exc:
            raise DqmConfigError(
                f"{target}: min_time {min_time!r} is not a time I can read "
                f"({exc})") from exc

    lookback = raw.get("lookback")
    if lookback is not None:
        try:
            lookback = int(lookback)
        except (TypeError, ValueError):
            raise DqmConfigError(f"{target}: lookback must be an integer")
        if lookback < 0:
            raise DqmConfigError(f"{target}: lookback cannot be negative")

    # Absolute, always.  cron runs with whatever working directory it likes,
    # so a relative workdir would put the state file and the log somewhere
    # other than beside the config -- and a driver that cannot find its own
    # state file starts from the beginning every time it runs.
    workdir = Path(raw.get("workdir") or target.parent).expanduser().resolve()

    pars = raw.get("pars") or {}
    if not isinstance(pars, Mapping):
        raise DqmConfigError(f"{target}: pars should be a mapping")

    cfg = DriverConfig(
        algo=algo,
        config=str(raw["config"]),
        sid=sid,
        commit=bool(raw.get("commit", False)),
        max_points=max_points,
        lookback=lookback,
        min_run=min_run,
        min_time=min_time,
        workdir=workdir,
        log=raw.get("log", "driver.log"),
        log_level=str(raw.get("log_level", "INFO")).upper(),
        state_file=raw.get("state_file"),
        pars=dict(pars),
        source=target,
    )
    return cfg


def build_evaluator(cfg: DriverConfig):
    """Construct the evaluator this config names."""
    known = REGISTRY()
    cls = known.get(cfg.algo)
    if cls is None:
        raise DqmConfigError(f"unknown algo {cfg.algo!r}; known: {sorted(known)}")
    evaluator = cls(config=cfg.config, sid=cfg.sid, pars=cfg.pars)
    if cfg.lookback is not None:
        # A config may ask for more or less history than the algorithm's
        # default; the algorithm still decides what to do with it.
        evaluator.lookback = cfg.lookback
    return evaluator
