"""The `tranad` evaluator: anomaly detection with a trained TranAD model (plus the
optional PCA and training-drift detectors from the same bundle).

The evaluator itself lives in the mu2e-tranad package
(github.com/sophiemiddleton/mu2e-tranad, mu2e_tranad/evaluator/tranad_evaluator.py),
together with the training pipeline and the model bundles it loads. It needs
torch, which nothing else in dqm does, so it is not vendored here; this module
only re-exports it so the registry can find it. Install with:

    pip install 'mu2e-dqm[tranad]'

Without mu2e-tranad the import below fails, `_registry()` leaves tranad out, and
a tranad config is rejected as an unknown algo -- the other evaluators are
unaffected. See the module docstring of mu2e_tranad.evaluator.tranad_evaluator
for the pars and the subjects (tranad_outlier, pca_outlier, training_drift).
"""

from mu2e_tranad.evaluator.tranad_evaluator import TranADEvaluator

__all__ = ["TranADEvaluator"]
