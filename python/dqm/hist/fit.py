"""Histogram fits: read one stored in the file, or compute one here.

A metric like a peak position can come from either place. Sometimes whatever
wrote the file already fitted the histogram and attached the result; sometimes
nothing did and the fit has to be done now. Both paths produce the same
`FitResult`, with `source` saying which, so everything downstream -- the
extractor writing a metric, the display drawing a curve -- is written once
against one type.

Fits computed here use lmfit, not ROOT's Minuit. On a real CRV histogram the
two agree to 0.001 in centre and 0.000 in sigma with an identical reduced
chi-square, so the choice is about readability rather than precision:

    model = GaussianModel()
    pars  = model.guess(y, x=x)
    res   = model.fit(y, pars, x=x)

Parameter names are canonical here, not ROOT's. A Gaussian always has
`center`, `sigma` and `height` whichever way it was obtained -- ROOT calls
those Mean, Sigma and Constant, and lmfit calls the third one height while
using `amplitude` for the area. Normalizing at the boundary means callers
never have to know where a fit came from.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from dqm.errors import DqmConfigError, DqmDependencyError, DqmFitError

LOGGER = logging.getLogger("dqm.hist.fit")

__all__ = [
    "FitResult",
    "fit_histogram",
    "stored_fit",
    "get_fit",
    "MODELS",
]

# Canonical parameter vocabulary per model. Both the stored-fit reader and the
# lmfit wrapper map into these names.
_GAUSSIAN_PARAMS = ("height", "center", "sigma")

# ROOT's built-in formula names, mapped to canonical parameter names in the
# order ROOT stores them. ROOT's gaus is [0]*exp(-0.5*((x-[1])/[2])^2), so its
# parameter 0 is the peak height, 1 the mean, 2 the width.
_ROOT_FORMULAS: Dict[str, Tuple[str, ...]] = {
    "gaus": _GAUSSIAN_PARAMS,
    "landau": ("height", "mpv", "sigma"),
    "expo": ("constant", "slope"),
}


def _gaussian(x, height, center, sigma):
    return height * np.exp(-0.5 * ((x - center) / sigma) ** 2)


def _expo(x, constant, slope):
    return np.exp(constant + slope * x)


def _polynomial(order: int) -> Callable:
    def f(x, **coeffs):
        out = np.zeros_like(np.asarray(x, dtype=float))
        for i in range(order + 1):
            out = out + coeffs[f"c{i}"] * np.asarray(x, dtype=float) ** i
        return out

    return f


def _landau(x, height, mpv, sigma):
    """Landau, via pylandau when available.

    scipy has no Landau; its Moyal is a similar-looking but different
    distribution, so substituting it silently would misreport a CRV MPV.
    Raising keeps that honest.
    """
    try:
        import pylandau
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise DqmDependencyError(
            "evaluating a Landau needs pylandau (pip install pylandau); "
            "scipy's Moyal is a different distribution and is not substituted"
        ) from exc
    return pylandau.landau(np.asarray(x, dtype=float), mpv, sigma, height)


_EVALUATORS: Dict[str, Callable] = {
    "gaus": _gaussian,
    "gaussian": _gaussian,
    "landau": _landau,
    "expo": _expo,
}


@dataclass
class FitResult:
    """One fit, however it was obtained.

    `params` and `errors` use canonical names (see the module docstring).
    `errors` may hold None for a parameter whose uncertainty is unknown --
    a stored fit does not always carry one.
    """

    model: str
    source: str  # "stored" (read from the file) or "fitted" (computed here)
    params: Dict[str, float]
    errors: Dict[str, Optional[float]] = field(default_factory=dict)
    chisq: Optional[float] = None
    ndf: Optional[int] = None
    success: bool = True
    message: str = ""
    _evaluator: Optional[Callable] = field(default=None, repr=False)

    @property
    def redchi(self) -> Optional[float]:
        """Reduced chi-square, the usual quick check on fit quality."""
        if self.chisq is None or not self.ndf:
            return None
        return self.chisq / self.ndf

    def value(self, name: str) -> float:
        """One parameter's value, by canonical name."""
        try:
            return self.params[name]
        except KeyError:
            raise DqmConfigError(
                f"fit has no parameter {name!r}; it has {sorted(self.params)}"
            ) from None

    def error(self, name: str) -> Optional[float]:
        """One parameter's uncertainty, or None if not available."""
        return self.errors.get(name)

    @property
    def can_evaluate(self) -> bool:
        """True if this fit can be drawn as a curve.

        False for a stored fit whose formula is not one this module knows how
        to reconstruct -- the parameters are still readable, only the curve is
        unavailable.
        """
        return self._evaluator is not None

    def evaluate(self, x) -> np.ndarray:
        """The fitted curve at `x`, for drawing."""
        if self._evaluator is None:
            raise DqmFitError(
                f"cannot evaluate a {self.model!r} fit: no evaluator for that "
                f"formula. Its parameters are still available via value(); "
                f"only the curve cannot be reconstructed."
            )
        return self._evaluator(np.asarray(x, dtype=float))

    def summary(self) -> List[str]:
        """Human-readable lines, for a stats box or a log message."""
        lines = [f"{self.model} ({self.source})"]
        for name, value in self.params.items():
            err = self.errors.get(name)
            if err is None:
                lines.append(f"{name} = {value:.4g}")
            else:
                lines.append(f"{name} = {value:.4g} +/- {err:.3g}")
        red = self.redchi
        if red is not None:
            lines.append(f"chi2/ndf = {red:.3f}")
        return lines

    def __repr__(self) -> str:
        pars = ", ".join(f"{k}={v:.4g}" for k, v in self.params.items())
        return f"FitResult({self.model}, {self.source}, {pars})"


# ------------------------------------------------------------ stored in file


def stored_fit(obj: Any, index: int = 0) -> Optional[FitResult]:
    """Read a fit already attached to a histogram in the file.

    Returns None when the histogram simply carries no fit -- which is normal,
    and is the case the original extractor described as "led runs". Raises
    DqmFitError when a fit IS present but cannot be read.

    That distinction is the whole point of this function. The code this
    replaced collapsed both cases into a bare `except: value = 0.0`, and since
    zero is also a legitimate measured value, a fit that stopped being
    readable would have been indistinguishable from data.

    `obj` is the uproot object, not a Hist -- converting to Hist drops the
    attached functions. Use HistFile.read_raw().
    """
    functions = obj.member("fFunctions", none_if_missing=True)
    if functions is None:
        return None
    try:
        items = list(functions)
    except Exception as exc:
        raise DqmFitError(f"cannot read the function list: {exc}") from exc
    if not items:
        return None  # no fit attached: the normal, honest "nothing here"
    if index >= len(items):
        raise DqmFitError(
            f"fit index {index} out of range; {len(items)} function(s) attached"
        )

    fn = items[index]
    name = str(fn.member("fName", none_if_missing=True) or "unknown")

    # ROOT 6 keeps a TF1's parameter VALUES in its TFormula base
    # (fClingParameters); the TF1-level fParams is left empty. Errors stay on
    # the TF1 as fParErrors. Reading only fParams -- the obvious guess -- would
    # silently find nothing.
    values = None
    names: Optional[Sequence[str]] = None
    formula = fn.member("fFormula", none_if_missing=True)
    if formula is not None:
        values = formula.member("fClingParameters", none_if_missing=True)
        names = formula.member("fParams", none_if_missing=True)
    if values is None:
        values = fn.member("fParams", none_if_missing=True)  # ROOT 5 layout
    if values is None:
        raise DqmFitError(
            f"a {name!r} fit is attached but its parameters could not be read "
            f"(neither fFormula.fClingParameters nor fParams is present). This "
            f"is NOT the same as a histogram with no fit, which returns None."
        )

    values = [float(v) for v in values]
    errors = fn.member("fParErrors", none_if_missing=True)
    errors = [float(e) for e in errors] if errors is not None else []

    canonical = _ROOT_FORMULAS.get(name)
    if canonical is None and name.startswith("pol") and name[3:].isdigit():
        canonical = tuple(f"c{i}" for i in range(int(name[3:]) + 1))
    if canonical is None or len(canonical) != len(values):
        # An unrecognized formula still yields usable numbers; fall back to
        # ROOT's own parameter names, or positional ones.
        if names is not None and len(names) == len(values):
            canonical = tuple(str(n).lower() for n in names)
        else:
            canonical = tuple(f"p{i}" for i in range(len(values)))

    params = dict(zip(canonical, values))
    errs: Dict[str, Optional[float]] = {
        n: (errors[i] if i < len(errors) else None) for i, n in enumerate(canonical)
    }

    evaluator = None
    base = _EVALUATORS.get(name)
    if base is not None:
        evaluator = lambda x, _p=params, _f=base: _f(x, **_p)  # noqa: E731
    elif name.startswith("pol") and name[3:].isdigit():
        poly = _polynomial(int(name[3:]))
        evaluator = lambda x, _p=params, _f=poly: _f(x, **_p)  # noqa: E731

    return FitResult(
        model=name,
        source="stored",
        params=params,
        errors=errs,
        chisq=fn.member("fChisquare", none_if_missing=True),
        ndf=fn.member("fNDF", none_if_missing=True),
        _evaluator=evaluator,
    )


# ---------------------------------------------------------------- fitted here

# Model names this module fits, mapped to the lmfit class providing them.
MODELS: Tuple[str, ...] = ("gaussian", "lorentzian", "voigt", "exponential", "linear")

_LMFIT_CANONICAL = {
    # lmfit's `amplitude` on a GaussianModel is the AREA under the curve, while
    # ROOT's first gaus parameter is the peak HEIGHT. lmfit derives `height`
    # too, so taking that keeps a fitted Gaussian directly comparable to a
    # stored one.
    "gaussian": {"center": "center", "sigma": "sigma", "height": "height"},
    "lorentzian": {"center": "center", "sigma": "sigma", "height": "height"},
    "voigt": {"center": "center", "sigma": "sigma", "height": "height"},
    "exponential": {"amplitude": "amplitude", "decay": "decay"},
    "linear": {"slope": "slope", "intercept": "intercept"},
}


def _lmfit_model(name: str):
    try:
        from lmfit import models
    except ImportError as exc:  # pragma: no cover - dependency error path
        raise DqmDependencyError(
            "fitting needs lmfit. Install the extra: pip install 'mu2e-dqm[fit]'"
        ) from exc

    lookup = {
        "gaussian": models.GaussianModel,
        "lorentzian": models.LorentzianModel,
        "voigt": models.VoigtModel,
        "exponential": models.ExponentialModel,
        "linear": models.LinearModel,
    }
    try:
        return lookup[name]()
    except KeyError:
        raise DqmConfigError(
            f"unknown fit model {name!r}; available: {sorted(lookup)}"
        ) from None


def fit_histogram(
    h,
    model: str = "gaussian",
    range: Optional[Tuple[float, float]] = None,
    min_entries: int = 10,
) -> FitResult:
    """Fit a 1-D histogram and return the result.

    Empty bins are excluded and the remaining ones weighted by 1/sqrt(N), which
    is the chi-square fit ROOT performs by default -- on a real CRV histogram
    this reproduces ROOT's answer to within 0.001.

    A fit that fails to converge comes back with `success=False` and a message
    rather than raising, since one bad histogram should not stop an extractor
    working through a file. A histogram with too few filled bins to constrain
    the model raises DqmFitError instead, because that is a question that
    should not have been asked.
    """
    if len(h.axes) != 1:
        raise DqmConfigError(f"can only fit a 1-D histogram; this one has {len(h.axes)} axes")

    centers = np.asarray(h.axes[0].centers, dtype=float)
    values = np.asarray(h.values(), dtype=float)

    mask = values > 0
    if range is not None:
        lo, hi = range
        mask &= (centers >= lo) & (centers <= hi)

    n_filled = int(mask.sum())
    if n_filled < min_entries:
        raise DqmFitError(
            f"only {n_filled} filled bin(s) in the fit range; need at least "
            f"{min_entries}. Check the histogram before fitting, or lower "
            f"min_entries deliberately."
        )

    x, y = centers[mask], values[mask]
    weights = 1.0 / np.sqrt(y)

    lm = _lmfit_model(model)
    try:
        pars = lm.guess(y, x=x)
        out = lm.fit(y, pars, x=x, weights=weights)
    except Exception as exc:
        return FitResult(
            model=model,
            source="fitted",
            params={},
            success=False,
            message=f"fit raised {type(exc).__name__}: {exc}",
        )

    wanted = _LMFIT_CANONICAL.get(model, {})
    params: Dict[str, float] = {}
    errors: Dict[str, Optional[float]] = {}
    for canonical, lmname in wanted.items():
        par = out.params.get(lmname)
        if par is None or par.value is None:
            continue
        params[canonical] = float(par.value)
        errors[canonical] = float(par.stderr) if par.stderr is not None else None

    evaluator = lambda xs, _o=out: _o.eval(x=np.asarray(xs, dtype=float))  # noqa: E731

    return FitResult(
        model=model,
        source="fitted",
        params=params,
        errors=errors,
        chisq=float(out.chisqr) if out.chisqr is not None else None,
        ndf=int(out.nfree) if out.nfree else None,
        success=bool(out.success),
        message="" if out.success else (out.message or "fit did not converge"),
        _evaluator=evaluator,
    )


def get_fit(
    obj,
    hist=None,
    model: str = "gaussian",
    prefer: str = "stored",
    **fit_kwargs,
) -> Optional[FitResult]:
    """Get a fit for a histogram, from the file or by fitting.

    `prefer="stored"` uses a fit already in the file and only fits when there
    is none -- what an extractor reproducing existing metrics wants.
    `prefer="fitted"` always fits here, ignoring anything stored, which is what
    a display offering a consistent model across files wants.

    Returns None only when there is nothing stored and fitting was not asked
    for. A stored fit that is present but unreadable still raises.
    """
    if prefer not in ("stored", "fitted"):
        raise DqmConfigError("prefer must be 'stored' or 'fitted'")

    if prefer == "stored":
        result = stored_fit(obj)
        if result is not None:
            return result
    if hist is None:
        hist = obj.to_hist()
    return fit_histogram(hist, model=model, **fit_kwargs)
