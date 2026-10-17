"""Read histograms out of ROOT files, without ROOT.

uproot reads the file format directly, so nothing here needs a Muse or Offline
environment, a cvmfs ROOT, or a compiled extension -- it is a pip install.
That is what lets the web applications and the extractors share this code
while running in completely different places.

Histograms are handed back as `hist.Hist` objects rather than raw arrays.
A Hist keeps bin edges, axis metadata and per-bin variances together, so the
plot and comparison layers downstream never have to pass parallel arrays
around and never have to guess whether an array includes flow bins.

The raw uproot object is still reachable via `read_raw`, because a few things
live outside the histogram proper -- most importantly a fit stored in the file
by whatever produced it. See dqm.hist.fit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from dqm.errors import DqmConfigError, DqmDependencyError

try:
    import uproot
except ImportError as exc:  # pragma: no cover - dependency error path
    raise DqmDependencyError(
        "dqm.hist needs uproot. Install the extra: "
        "pip install 'mu2e-dqm[hist]'"
    ) from exc

LOGGER = logging.getLogger("dqm.hist.read")

__all__ = [
    "HistEntry",
    "HistFile",
    "open_file",
    "normalize_path",
    "HIST_CLASSES",
    "DIR_CLASSES",
]

# The classes treated as histograms, matching what the original ROOT-based
# reader accepted. TProfile is modeled by uproot; TEfficiency is not, and is
# read through uproot's streamer fallback -- it is listed because the old code
# listed it, but see `to_hist` below for what that actually supports.
HIST_CLASSES: Tuple[str, ...] = (
    "TH1F",
    "TH1D",
    "TH1I",
    "TH2F",
    "TH2D",
    "TH2I",
    "TProfile",
    "TEfficiency",
)

DIR_CLASSES: Tuple[str, ...] = ("TDirectory", "TDirectoryFile")


def normalize_path(path: str) -> str:
    """Strip a file:// prefix, leaving remote URLs alone.

    uproot opens a local path, root://, http:// and https:// directly, but a
    file:// URL has to have the scheme removed first. The web layer receives
    file:// from metacat, so this is the common case rather than an edge one.
    """
    text = str(path)
    if text.startswith("file://"):
        return text[len("file://") :]
    return text


def is_remote(path: str) -> bool:
    """True if reading this path goes over the network."""
    return str(path).startswith(("root://", "http://", "https://"))


@dataclass(frozen=True)
class HistEntry:
    """One histogram found in a file.

    `path` is the full path within the file with no ROOT cycle suffix (the
    ";1"), which is what callers match on when comparing two files.
    """

    path: str
    classname: str

    @property
    def name(self) -> str:
        """The histogram's own name, without its directory."""
        return self.path.rsplit("/", 1)[-1]

    @property
    def directory(self) -> str:
        """The directory holding it, or "" at the top level."""
        return self.path.rsplit("/", 1)[0] if "/" in self.path else ""

    @property
    def ndim(self) -> int:
        return 2 if self.classname.startswith(("TH2", "TProfile2D")) else 1


class HistFile:
    """One open ROOT file.

    Usable as a context manager, which is the form to prefer -- a remote file
    holds a network connection open:

        with HistFile(path) as f:
            for entry in f.histograms():
                h = f.read(entry.path)
    """

    def __init__(self, path: str):
        self.path = normalize_path(path)
        self.remote = is_remote(self.path)
        try:
            self._file = uproot.open(self.path)
        except Exception as exc:
            raise DqmConfigError(f"cannot open {self.path!r}: {exc}") from exc
        self._classnames: Optional[Dict[str, str]] = None

    def __enter__(self) -> "HistFile":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def close(self) -> None:
        try:
            self._file.close()
        except Exception:  # pragma: no cover - close is best effort
            pass

    def __repr__(self) -> str:
        return f"HistFile({self.path!r})"

    # ----------------------------------------------------------------- listing

    def _scan(self) -> Dict[str, str]:
        if self._classnames is None:
            # One recursive scan walks every directory, replacing the explicit
            # breadth-first queue the ROOT version had to maintain by hand.
            self._classnames = {
                k.split(";")[0]: v
                for k, v in self._file.classnames(recursive=True).items()
            }
        return self._classnames

    def histograms(
        self, classes: Sequence[str] = HIST_CLASSES, ndim: Optional[int] = None
    ) -> List[HistEntry]:
        """Every histogram in the file, depth-first through subdirectories.

        `ndim` filters to 1-D or 2-D when given, which is what a display
        wanting only overlayable histograms asks for.
        """
        out = [
            HistEntry(path=p, classname=c)
            for p, c in self._scan().items()
            if c in classes
        ]
        if ndim is not None:
            out = [e for e in out if e.ndim == ndim]
        return out

    def directories(self) -> List[str]:
        """Every directory path in the file."""
        return [p for p, c in self._scan().items() if c in DIR_CLASSES]

    def keys(self) -> List[str]:
        """Every object path, whatever its class."""
        return list(self._scan())

    def classname(self, path: str) -> Optional[str]:
        return self._scan().get(path.split(";")[0])

    def __contains__(self, path: str) -> bool:
        return path.split(";")[0] in self._scan()

    def __iter__(self) -> Iterator[HistEntry]:
        return iter(self.histograms())

    # ----------------------------------------------------------------- reading

    def read_raw(self, path: str) -> Any:
        """The uproot object, for things a Hist does not carry.

        Needed for a fit stored alongside the histogram -- converting to Hist
        drops it. See dqm.hist.fit.stored_fit.
        """
        key = path.split(";")[0]
        if key not in self._scan():
            raise DqmConfigError(
                f"{key!r} is not in {self.path!r} "
                f"({len(self._scan())} objects; use histograms() to list them)"
            )
        return self._file[key]

    def read(self, path: str):
        """One histogram as a `hist.Hist`.

        Raises DqmConfigError for a class uproot cannot convert, rather than
        returning something subtly wrong -- TEfficiency is the case that
        actually arises, since it is a pair of histograms plus a confidence
        model rather than a histogram.
        """
        obj = self.read_raw(path)
        try:
            return obj.to_hist()
        except Exception as exc:
            cls = self.classname(path)
            raise DqmConfigError(
                f"cannot convert {path!r} (class {cls}) to a histogram: {exc}. "
                f"Use read_raw() to work with the uproot object directly."
            ) from exc

    def read_many(self, paths: Sequence[str]) -> Dict[str, Any]:
        """Several histograms at once, keyed by path."""
        return {p: self.read(p) for p in paths}


def open_file(path: str) -> HistFile:
    """Open a ROOT file for reading. Accepts a plain path, file://, or root://."""
    return HistFile(path)


def common_histograms(
    file1: HistFile, file2: HistFile, ndim: Optional[int] = None
) -> List[HistEntry]:
    """Histograms present in both files, matched by path.

    The pairing rule for comparing two files. Returns file1's entries, in
    file1's order, so a display has a stable ordering to present.
    """
    other = {e.path for e in file2.histograms(ndim=ndim)}
    return [e for e in file1.histograms(ndim=ndim) if e.path in other]
