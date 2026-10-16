"""Read and compare ROOT histograms, without ROOT.

    from dqm.hist import open_file, fit_histogram

    with open_file(path) as f:
        for entry in f.histograms(ndim=1):
            h = f.read(entry.path)

Needs the `hist` extra (uproot, hist, and fsspec-xrootd for root:// URLs),
plus the `fit` extra for fitting and comparison:

    pip install 'mu2e-dqm[hist,fit]'

uproot reads the ROOT file format directly, so none of this needs a Muse or
Offline environment -- which is what lets the display applications and the
extractors share it while running in different places.
"""

from dqm.hist.read import (  # noqa: F401
    DIR_CLASSES,
    HIST_CLASSES,
    HistEntry,
    HistFile,
    common_histograms,
    normalize_path,
    open_file,
)
from dqm.hist.stats import (  # noqa: F401
    HistStats,
    edges_above,
    statistics,
    stats_lines,
)
from dqm.hist.fit import (  # noqa: F401
    MODELS,
    FitResult,
    fit_histogram,
    get_fit,
    stored_fit,
)
from dqm.hist.compare import (  # noqa: F401
    ComparePars,
    Comparison,
    CompareStatus,
    compare_files,
    compare_histograms,
    kolmogorov_test,
    summarize,
)

__all__ = [
    # reading
    "open_file",
    "HistFile",
    "HistEntry",
    "common_histograms",
    # statistics
    "statistics",
    "HistStats",
    "stats_lines",
    "edges_above",
    "normalize_path",
    "HIST_CLASSES",
    "DIR_CLASSES",
    # fitting
    "FitResult",
    "fit_histogram",
    "stored_fit",
    "get_fit",
    "MODELS",
    # comparing
    "compare_histograms",
    "compare_files",
    "kolmogorov_test",
    "summarize",
    "Comparison",
    "ComparePars",
    "CompareStatus",
]
