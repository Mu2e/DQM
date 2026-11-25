"""The `tranad` evaluator: score each new point with a trained TranAD model

The models are trained offline by mu2e-tranad (github.com/Mu2e/mu2e-tranad,
`python -m mu2e_tranad ... --save-model <pkl>`), which freezes the threshold, the
scaling and the weights into one bundle file. This evaluator only loads that bundle
and judges one point at a time, so it is cheap enough for a gpvm cron job (CPU, a
few ms per point; the cost is importing torch). It reads the bundle and prepares
its inputs with mu2e_tranad.training, so it needs the `tranad` extra:

    pip install 'mu2e-dqm[tranad]'

Without it `_registry()` leaves tranad out, and a tranad config is rejected as an
unknown algo; the other evaluators are unaffected. Not exported from
dqm.evaluate for the same reason.

    algo:    tranad
    config:  crv-tranad-v1       # bump on every retrain: it is part of alarm identity
    sid:     114                 # crvreco,kpp_crv,file,004-000
    commit:  false               # report only until the findings have been reviewed
    max_points: 200
    min_time: 2026-11-04         # go-live date: don't alarm on the whole back history
    workdir: /exp/mu2e/app/users/CHANGE_ME/dqm-drivers/crv-tranad
    log:     driver.log

    pars:
      model: /exp/mu2e/app/users/.../crv_tranad_v1.pkl   # from --save-model; default: the
                                 # model shipped in mu2e_tranad (models/crv_tranad_006-001.pkl)
      detectors: [tranad, drift] # any of tranad, pca, drift
      level: warn                # severity of a finding
      threshold_scale: 1.0       # multiply the trained thresholds (>1 = fewer findings)
      top_causes: 5              # metrics named as causes, by reconstruction error / shift
      drift_window: 50           # points in the drift median; default from the bundle
      drift_sigma: 3.0           # training stds a median may move; default from the bundle

    dqm-driver tranad.yaml --check      # loads config + model, then exits
    dqm-driver tranad.yaml              # one invocation (cron)

Subjects:

    tranad_outlier   TranAD's reconstruction error for the point, from it and the
                     n_window - 1 points before it, is above the trained threshold
    pca_outlier      the PCA reconstruction error is above the trained threshold
                     (refused while the bundle's PCA keeps every component)
    training_drift   over the last drift_window points, some input's median has moved
                     more than drift_sigma training stds from its training median: the
                     data no longer looks like what the model learned, so retrain

Each finding names the top_causes worst-reconstructed (or most-shifted) metrics as
its causes; its note holds the score, the threshold, those metrics' values and
errors, and the model's training date and source.

TranAD's threshold and scaling are frozen at training time, so a slow drift ends as a
run of tranad_outlier findings that cannot be told from a fault. training_drift says so
directly, and names the inputs that moved. It is unlike the `trends` evaluator's drift,
which compares a metric with its own recent past rather than with the training data.

A point that lacks one of the bundle's features, or has one flagged by its producer,
is skipped and the skip is logged; new metrics are ignored. When the metrics change,
retrain and bump `config`, so the new model's alarms do not extend the old episodes.
"""

import json
import logging
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from dqm.errors import DqmConfigError
from dqm.evaluate.base import LEVELS, Evaluator, Finding, Point

from mu2e_tranad.training.bundle import VALID_SUFFIX, default_model_path, load_bundle
from mu2e_tranad.training.tranad_prep import drift_min_points, sentinel_value

LOGGER = logging.getLogger("dqm.evaluate.tranad")

__all__ = ["TranADEvaluator"]

DETECTORS = ("tranad", "pca", "drift")


class TranADEvaluator(Evaluator):
    """Flag points the trained TranAD / PCA models find anomalous."""

    algo = "tranad"
    subjects = ("tranad_outlier", "pca_outlier", "training_drift")
    lookback = 4  # replaced in configure() by what the chosen detectors need

    def configure(self) -> None:
        # No model named: the packaged default (training/bundle.py, $MU2E_TRANAD_MODEL)
        path = self.pars.get("model") or default_model_path()
        try:
            self._bundle = load_bundle(str(path))
        except Exception as exc:
            raise DqmConfigError(f"tranad: cannot load model {path}: {exc}") from exc

        detectors = self.pars.get("detectors", ["tranad"])
        if not isinstance(detectors, (list, tuple)) or not detectors \
                or any(d not in DETECTORS for d in detectors):
            raise DqmConfigError(f"tranad: detectors must be a non-empty list from {DETECTORS}")
        self._detectors = tuple(detectors)
        pca = self._bundle["pca"]
        if "pca" in self._detectors and len(pca["components"]) >= len(pca["features"]):
            # Every component kept: reconstruction is exact and the "error" is rounding
            raise DqmConfigError(
                f"tranad: the PCA model keeps all {len(pca['components'])} components, so its "
                f"reconstruction error is numerical noise; retrain with fewer components")

        level = self.pars.get("level", LEVELS["warn"])
        if isinstance(level, str):
            if level not in LEVELS:
                raise DqmConfigError(f"tranad: level must be one of {sorted(LEVELS)} or 0-3")
            level = LEVELS[level]
        if level not in range(4):
            raise DqmConfigError(f"tranad: level must be 0-3, got {level!r}")
        self._level = int(level)

        try:
            self._scale = float(self.pars.get("threshold_scale", 1.0))
            self._top = int(self.pars.get("top_causes", 5))
        except (TypeError, ValueError) as exc:
            raise DqmConfigError(f"tranad: {exc}") from exc
        if self._scale <= 0 or self._top < 1:
            raise DqmConfigError("tranad: threshold_scale must be > 0 and top_causes >= 1")

        self._model = None
        self.lookback = 0
        if "tranad" in self._detectors:
            self._model = self._load_tranad()
            self.lookback = self._bundle["tranad"]["n_window"]
        if "drift" in self._detectors:
            self._configure_drift()
            self.lookback = max(self.lookback, self._drift_window - 1)

        LOGGER.info("tranad: model %s (trained %s on %s, %s rows), detectors %s",
                    path, self._bundle["created"], self._bundle["source"],
                    self._bundle["rows"], ",".join(self._detectors))

    def _configure_drift(self) -> None:
        d = self._bundle.get("drift")
        if d is None:
            raise DqmConfigError("tranad: the bundle has no drift reference; "
                                 "retrain with --save-model to add one")
        try:
            self._drift_window = int(self.pars.get("drift_window", d["window"]))
            self._drift_sigma = float(self.pars.get("drift_sigma", d["sigma"]))
        except (TypeError, ValueError) as exc:
            raise DqmConfigError(f"tranad: {exc}") from exc
        if self._drift_window < 2 or self._drift_sigma <= 0:
            raise DqmConfigError("tranad: drift_window must be >= 2 and drift_sigma > 0")
        # The same inputs and scaling the drift reference was measured on in training
        t = self._bundle["tranad"]
        if t is not None:
            inputs, mean, std, fill = t["inputs"], t["mean"], t["std"], t["fill"]
        else:
            p = self._bundle["pca"]
            inputs, mean, std, fill = p["features"], p["mean"], p["scale"], {}
        if len(d["center"]) != len(inputs):
            raise DqmConfigError("tranad: the bundle's drift reference does not match its inputs")
        self._drift_ref = (inputs, mean, std, fill, d["center"])

    def _load_tranad(self):
        t = self._bundle["tranad"]
        if t is None:
            raise DqmConfigError("tranad: the bundle has no TranAD model; use detectors: [pca]")
        # Imported here so a PCA-only driver never needs torch
        from mu2e_tranad.training.tranad_model import TRANAD_ANL_AVAILABLE, TranAD, TranADConfig, torch
        if not TRANAD_ANL_AVAILABLE:
            raise DqmConfigError("tranad: TranAD needs torch "
                                 "(pip install 'mu2e-dqm[tranad]')")
        model = TranAD(input_dims=len(t["inputs"]),
                       arch_config=TranADConfig(n_window=t["n_window"], **t["arch"]))
        model.load_state_dict({k: torch.from_numpy(v) for k, v in t["state_dict"].items()})
        model.eval()
        self._torch = torch
        return model

    # -- inputs -----------------------------------------------------------

    @staticmethod
    def _columns(point: Point) -> Dict[str, int]:
        """Pipeline column name -> vid. The pipeline names metrics groupx_subgroup_namex."""
        return {name.replace("/", "_"): vid for vid, name in point.names.items()}

    def _vector(self, point: Point, inputs: Sequence[str],
                fill: Dict[str, float]) -> Tuple[Optional[np.ndarray], List[int], Optional[str]]:
        """
        The model input row for this point, the vid behind each input, and the first
        input that could not be filled (None if all were).
        """
        cols = self._columns(point)
        x, vids = [], []
        for f in inputs:
            base = f[:-len(VALID_SUFFIX)] if f.endswith(VALID_SUFFIX) else f
            vid = cols.get(base)
            m = point.get(vid) if vid is not None else None
            if m is None:
                return None, [], base
            if base in fill:
                # A "no fit" feature: a sentinel or a flagged measurement is invalid,
                # replaced by the training median and marked in the __valid input
                ok = m.ok and m.valuex != sentinel_value(base)
                v = float(ok) if f.endswith(VALID_SUFFIX) else (m.valuex if ok else fill[base])
            elif not m.ok:
                return None, [], base
            else:
                v = m.valuex
            x.append(v)
            vids.append(vid)
        return np.asarray(x, dtype=float), vids, None

    # -- detectors --------------------------------------------------------

    def _tranad(self, point: Point, history: Sequence[Point]):
        """Per-input squared errors, the vids behind them, and the threshold; or None."""
        t = self._bundle["tranad"]
        n = t["n_window"]
        if len(history) < n:
            LOGGER.debug("%s: %d point(s) of history, TranAD needs %d -- skipping",
                         point.label, len(history), n)
            return None
        rows = []
        for p in list(history[-n:]) + [point]:
            x, vids, missing = self._vector(p, t["inputs"], t["fill"])
            if x is None:
                LOGGER.info("%s: TranAD skipped, %s missing or flagged at %s",
                            point.label, missing, p.label)
                return None
            rows.append(x)
        torch = self._torch
        X = torch.from_numpy((np.stack(rows) - t["mean"]) / t["std"]).float()
        with torch.no_grad():
            _, x2 = self._model(X[:n].unsqueeze(0), X[n].unsqueeze(0).unsqueeze(1))
        err = ((x2.reshape(-1) - X[n]) ** 2).numpy()
        return err, err.mean(), vids, t["threshold"]

    def _pca(self, point: Point):
        p = self._bundle["pca"]
        x, vids, missing = self._vector(point, p["features"], {})
        if x is None:
            LOGGER.info("%s: PCA skipped, %s missing or flagged", point.label, missing)
            return None
        z = (x - p["mean"]) / p["scale"] - p["center"]
        err = (z - z @ p["components"].T @ p["components"]) ** 2
        return err, err.sum(), vids, p["threshold"]

    def _drift(self, point: Point, history: Sequence[Point]):
        """
        Per-input shift of the window median from the training median (training stds),
        the vids behind the inputs, and the window length; or None.
        """
        inputs, mean, std, fill, center = self._drift_ref
        x, vids, missing = self._vector(point, inputs, fill)
        if x is None:
            LOGGER.info("%s: drift skipped, %s missing or flagged", point.label, missing)
            return None
        rows = [x]
        for p in history[-(self._drift_window - 1):]:
            y, _, _ = self._vector(p, inputs, fill)
            if y is not None:
                rows.append(y)
        if len(rows) < drift_min_points(self._drift_window):
            LOGGER.debug("%s: %d usable point(s) for drift, need %d -- skipping", point.label,
                         len(rows), drift_min_points(self._drift_window))
            return None
        shift = np.median((np.stack(rows) - mean) / std, axis=0) - center
        # A validity flag's median is 0 or 1; its feature's own shift carries the drift
        shift[[f.endswith(VALID_SUFFIX) for f in inputs]] = 0.0
        return shift, vids, len(rows)

    def _drift_finding(self, point: Point, scored) -> Optional[Finding]:
        shift, vids, n = scored
        drifted = [i for i in np.argsort(-np.abs(shift)) if abs(shift[i]) > self._drift_sigma]
        if not drifted:
            return None
        detail = [{"metric": point.name(vids[i]), "vid": vids[i],
                   "value": point[vids[i]].valuex, "shift": float(shift[i])}
                  for i in drifted[:self._top]]
        LOGGER.info("%s: training_drift in %d input(s) over %d points -- worst %s (%+.1f sigma)",
                    point.label, len(drifted), n,
                    "/".join(detail[0]["metric"].split("/")[-2:]), detail[0]["shift"])
        note = {"drifted": len(drifted), "sigma": self._drift_sigma, "window": n,
                "top": detail,
                "model": {"created": self._bundle["created"], "source": self._bundle["source"]}}
        return self.finding("training_drift",
                            *[point.cause(d["vid"], level=self._level) for d in detail],
                            note=json.dumps(note))

    def _finding(self, subject: str, point: Point, scored) -> Optional[Finding]:
        err, score, vids, threshold = scored
        threshold *= self._scale
        if score <= threshold:
            return None
        # The worst-reconstructed metrics are the causes; a sentinel feature and its
        # __valid flag share a vid, so keep each vid once
        top, seen = [], set()
        for i in np.argsort(err)[::-1]:
            if vids[i] not in seen:
                seen.add(vids[i])
                top.append(i)
            if len(top) == self._top:
                break
        detail = [{"metric": point.name(vids[i]), "vid": vids[i],
                   "value": point[vids[i]].valuex, "error": float(err[i])} for i in top]
        LOGGER.info("%s: %s score %.4g > %.4g (x%.1f) -- worst %s",
                    point.label, subject, score, threshold, score / threshold,
                    ", ".join("/".join(d["metric"].split("/")[-2:]) for d in detail[:2]))
        note = {"score": float(score), "threshold": threshold, "top": detail,
                "model": {"created": self._bundle["created"], "source": self._bundle["source"]}}
        return self.finding(subject, *[point.cause(d["vid"], level=self._level) for d in detail],
                            note=json.dumps(note))

    def evaluate(self, point: Point, history: Sequence[Point] = ()) -> Sequence[Finding]:
        if not point.names:
            # Without names nothing maps onto the trained features
            LOGGER.warning("%s: no metric names in the point -- skipping", point.label)
            return []
        findings = []
        if "tranad" in self._detectors:
            scored = self._tranad(point, history)
            if scored is not None:
                findings.append(self._finding("tranad_outlier", point, scored))
        if "pca" in self._detectors:
            scored = self._pca(point)
            if scored is not None:
                findings.append(self._finding("pca_outlier", point, scored))
        if "drift" in self._detectors:
            scored = self._drift(point, history)
            if scored is not None:
                findings.append(self._drift_finding(point, scored))
        return [f for f in findings if f is not None]

