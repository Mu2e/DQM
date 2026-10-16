"""Find DQM files through metacat, and turn a file name into a path.

Two separate jobs, because metacat does only the first. It catalogs datasets
and their member files, but a file record carries no path or URL -- so knowing
a file exists is not the same as being able to open it. `mdh` closes that gap:
a Mu2e file name encodes its own location, and mdh_names.MFile derives the
path from the name by hashing it. No second lookup, no network.

    from dqm.catalog import datasets, dataset_files, file_url

    dss = datasets("dqm")                       # DQM datasets
    names = dataset_files(dss[0].did)           # file names within one
    path = file_url(names[0])                   # something uproot can open

Needs the `catalog` extra:

    pip install 'mu2e-dqm[catalog]'

A note on the mdh import. `mdh` itself pulls in rucio and data_dispatcher at
module scope, which are a heavy and awkward install. Everything needed here is
in `mdh_names`, which ships in the same distribution and imports nothing
beyond the standard library -- so this module imports that directly and the
rucio stack never has to be present.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from dqm.errors import DqmConfigError, DqmDependencyError, DqmError

LOGGER = logging.getLogger("dqm.catalog")

__all__ = [
    "Dataset",
    "datasets",
    "dataset_files",
    "file_url",
    "DqmCatalogError",
    "DEFAULT_NAMESPACE",
    "LOCATIONS",
]


class DqmCatalogError(DqmError):
    """A catalog lookup failed, or a file could not be located."""


DEFAULT_NAMESPACE = "mu2e"

# Where a file may live, in the order worth trying. `disk` first because that
# is where DQM output actually sits; `tape` is dCache-backed and a read there
# may stage from tape, which is slow enough to matter in a web request.
LOCATIONS: Tuple[str, ...] = ("disk", "tape", "scratch")


def _client():
    """A metacat client, with a clear message when it is not installed."""
    try:
        from metacat.webapi import MetaCatClient
    except ImportError as exc:  # pragma: no cover - dependency error path
        raise DqmDependencyError(
            "dqm.catalog needs the metacat client. Install the extra: "
            "pip install 'mu2e-dqm[catalog]'"
        ) from exc
    # No explicit URL: MetaCatClient reads METACAT_SERVER_URL, which the Mu2e
    # environment already sets. Hardcoding it here would silently override a
    # deliberate choice of test instance.
    try:
        return MetaCatClient()
    except Exception as exc:
        raise DqmCatalogError(f"cannot reach metacat: {type(exc).__name__}: {exc}") from exc


def _mfile(name: str):
    """mdh's view of a Mu2e file name, from which its path is derived."""
    try:
        from mdh_names import MFile
    except ImportError as exc:  # pragma: no cover - dependency error path
        raise DqmDependencyError(
            "resolving a file name to a path needs mdh. Install the extra: "
            "pip install 'mu2e-dqm[catalog]'"
        ) from exc
    try:
        return MFile(name)
    except Exception as exc:
        raise DqmCatalogError(
            f"{name!r} is not a Mu2e file name mdh can parse: {exc}"
        ) from exc


@dataclass(frozen=True)
class Dataset:
    """One metacat dataset."""

    namespace: str
    name: str
    file_count: Optional[int] = None

    @property
    def did(self) -> str:
        """The full identifier metacat wants, "namespace:name"."""
        return f"{self.namespace}:{self.name}"

    def __str__(self) -> str:
        return self.did


def datasets(
    pattern: str = "dqm",
    namespace: str = DEFAULT_NAMESPACE,
    with_counts: bool = False,
) -> List[Dataset]:
    """Datasets whose name contains `pattern`, newest-looking first.

    `pattern` is matched case-insensitively against the dataset name as a
    plain substring, not a glob -- "dqm" finds every DQM dataset however it is
    spelled. Pass "" for everything in the namespace.

    `with_counts` is off by default because metacat computes per-dataset file
    counts on demand and it is slow across a whole namespace. Ask for counts
    once the list is already narrow.
    """
    client = _client()
    try:
        raw = list(client.list_datasets(namespace_pattern=namespace,
                                        with_counts=with_counts))
    except Exception as exc:
        raise DqmCatalogError(
            f"listing datasets failed: {type(exc).__name__}: {exc}"
        ) from exc

    needle = pattern.lower()
    out = [
        Dataset(
            namespace=d.get("namespace", namespace),
            name=d.get("name", ""),
            file_count=d.get("file_count") if with_counts else None,
        )
        for d in raw
        if not needle or needle in d.get("name", "").lower()
    ]
    return sorted(out, key=lambda d: d.name)


def dataset_files(did: str, newest_first: bool = True) -> List[str]:
    """The file names in one dataset.

    Names only: a metacat file record carries no path, so a name is all that
    is on offer here. Use file_url to turn one into something openable.

    Sorted by name descending by default, which for Mu2e names puts the
    highest run and subrun first -- the files anyone is most likely to want.
    """
    if not did or ":" not in did:
        raise DqmConfigError(
            f"expected a dataset id of the form 'namespace:name', got {did!r}"
        )
    client = _client()
    try:
        raw = list(client.get_dataset_files(did=did, with_metadata=False))
    except Exception as exc:
        raise DqmCatalogError(
            f"listing files in {did} failed: {type(exc).__name__}: {exc}"
        ) from exc
    names = [f["name"] for f in raw if f.get("name")]
    return sorted(names, reverse=newest_first)


def file_url(
    name: str,
    locations: Sequence[str] = LOCATIONS,
    schema: str = "path",
    check: bool = True,
) -> str:
    """Turn a Mu2e file name into something that can be opened.

    The path is derived from the name itself -- mdh hashes it to get the
    directory -- so this needs no catalog lookup and no network.

    With `check` (the default) each candidate location is tested on the
    filesystem and the first that exists is returned, because the name alone
    does not say which one holds the file. Without it, the first location's
    path is returned unexamined, which is what a remote schema needs since
    there is nothing local to stat.

    schema="path" gives a /pnfs path; "root" and "http" give URLs for reading
    over the network, which dqm.hist can open given the xrootd extra.
    """
    f = _mfile(name)

    if schema != "path" or not check:
        try:
            return f.url(location=locations[0], schema=schema)
        except Exception as exc:
            raise DqmCatalogError(f"cannot build a {schema} url for {name!r}: {exc}") from exc

    tried = []
    for location in locations:
        try:
            candidate = f.url(location=location, schema="path")
        except Exception:
            continue
        tried.append(candidate)
        if os.path.exists(candidate):
            return candidate

    raise DqmCatalogError(
        f"{name!r} was not found in any of {list(locations)}. Looked at: "
        + "; ".join(tried)
    )


def available() -> bool:
    """True if the catalog dependencies are importable.

    Lets a caller offer dataset browsing only when it can actually work,
    rather than presenting a control that fails when used.
    """
    try:
        import mdh_names  # noqa: F401
        from metacat.webapi import MetaCatClient  # noqa: F401
    except ImportError:
        return False
    return True
