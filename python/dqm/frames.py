"""DataFrame conventions shared between whatever produces a frame and whatever
consumes it.

Two things live here. The first is the truncation convention. Every DQM result
is capable of being larger than anyone wants to hold -- dqm.numbers is heading
for millions of rows -- so results carry a limit, and a limited result has to
say so. A short frame that stopped early and a short frame that is complete
look identical, and mistaking the first for the second is how "this source has
no data" gets reported about a source that has plenty. So producers tag frames
with `tag()` and consumers check `is_truncated()`; neither has to know the
other's internals.

pandas carries this in `DataFrame.attrs`, which survives slicing but not
concatenation or merging -- so any operation combining frames has to restore
it deliberately. `preserve_attrs` does that.

The second is `to_records`, for the JSON boundary.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

__all__ = [
    "ATTR_TABLE",
    "ATTR_LIMIT",
    "ATTR_TRUNCATED",
    "tag",
    "is_truncated",
    "preserve_attrs",
    "empty_frame",
    "to_records",
]

# attrs keys. Named constants rather than bare strings so a typo in a consumer
# is a NameError rather than a silent False -- the exact failure this
# convention exists to prevent.
ATTR_TABLE = "table"
ATTR_LIMIT = "limit"
ATTR_TRUNCATED = "truncated"


def tag(
    df: pd.DataFrame,
    table: Optional[str] = None,
    limit: Optional[int] = None,
    truncated: bool = False,
) -> pd.DataFrame:
    """Record query provenance on a frame, in place, and return it.

    `truncated` is the one a consumer must not ignore: True means the query
    stopped at its limit and more matching rows exist, which is a different
    claim from "this is all the data there is".
    """
    df.attrs[ATTR_TABLE] = table
    df.attrs[ATTR_LIMIT] = limit
    df.attrs[ATTR_TRUNCATED] = truncated
    return df


def is_truncated(df: pd.DataFrame) -> bool:
    """True if this frame is known to have stopped at a limit.

    Defaults to False for an untagged frame, which is the right default for a
    frame built locally rather than fetched -- but means a consumer judging
    completeness should be sure its producer tags.
    """
    return bool(df.attrs.get(ATTR_TRUNCATED, False))


def preserve_attrs(source: pd.DataFrame, result: pd.DataFrame) -> pd.DataFrame:
    """Copy `source`'s attrs onto `result`, for operations that drop them.

    merge and concat return a frame with empty attrs, so joining interval or
    name columns onto a metric frame would quietly lose its truncation flag --
    turning a known-partial result into an apparently complete one.
    """
    result.attrs.update(source.attrs)
    return result


def empty_frame(columns, dtypes: Optional[Dict[str, str]] = None) -> pd.DataFrame:
    """An empty frame with the right columns and dtypes.

    Typed rather than bare so downstream code sees the same dtypes it would
    from a populated result, and an empty result does not become a special
    case that has to be handled separately.
    """
    dtypes = dtypes or {}
    return pd.DataFrame(
        {c: pd.Series(dtype=dtypes.get(c, "object")) for c in columns}
    )


def to_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Convert a frame to JSON-safe dicts.

    Needed because DataFrame.to_dict("records") returns numpy scalars and
    pd.NA/NaT, none of which the standard json encoder accepts. Timestamps
    become ISO-8601 strings and missing values become None.

    For the small results that cross a JSON boundary -- an MCP tool response,
    an HTTP endpoint -- not for bulk data: the per-row dict cost is exactly
    what the DataFrame representation exists to avoid.
    """
    if df.empty:
        return []
    out: List[Dict[str, Any]] = []
    for row in df.to_dict("records"):
        clean: Dict[str, Any] = {}
        for key, value in row.items():
            if isinstance(value, pd.Timestamp):
                clean[key] = value.isoformat()
            elif value is None or value is pd.NaT:
                clean[key] = None
            elif isinstance(value, (list, dict)):
                clean[key] = value
            elif pd.isna(value):
                clean[key] = None
            elif hasattr(value, "item"):  # numpy / pandas scalar
                clean[key] = value.item()
            else:
                clean[key] = value
        out.append(clean)
    return out
