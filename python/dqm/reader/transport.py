"""Query Engine HTTP transport: build a query, stream the response, parse CSV.

Separated from the query logic in reader.py because this is the only part that
touches the network and the only part that knows Query Engine's URL and
where-clause syntax. The queries above it work in terms of tables and filters.

Sizing shapes everything here. dqm.numbers holds ~475k rows and is expected to
reach millions, so the parse goes straight from the socket into typed pandas
columns via read_csv: the CSV body for a million rows is tens of megabytes,
and `response.text` would hold all of it as one string alongside the frame
being built from it.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator, List, Optional, Sequence, Tuple, Union

import pandas as pd
import requests

from dqm.errors import DqmConfigError, QueryEngineError
from dqm.schema import QE_OPERATORS, TIME_COLUMNS, dtypes_for

LOGGER = logging.getLogger("dqm.reader.transport")

__all__ = [
    "QEClient",
    "DEFAULT_QE_NOCACHE_URL",
    "DEFAULT_DBNAME",
    "DEFAULT_TIMEOUT_SECONDS",
    "where",
    "where_eq",
]

# The nocache endpoint (:9443). The cache endpoint (:8444) can serve stale
# rows, which is wrong for a monitoring database whose whole point is what
# landed most recently -- QEClient rejects it outright.
DEFAULT_QE_NOCACHE_URL = "https://dbdata0vm.fnal.gov:9443/QE/mu2e/prod/app/SQ/query?"
DEFAULT_DBNAME = "mu2e_dqm_prd"

# Generous, because this client is sized for bulk pulls: a full unfiltered
# fetch of dqm.numbers takes a few seconds today and will grow with the table.
DEFAULT_TIMEOUT_SECONDS = 120

# Bytes read ahead to confirm the response is the CSV that was asked for. QE
# reports some failures as an HTML page under HTTP 200, which read_csv would
# otherwise parse into a frame of nonsense.
_PEEK_BYTES = 4096


def where(column: str, op: str, value: Any) -> str:
    """Build one Query Engine where clause, validating the operator.

    QE parses a clause as "col:op:val". Given an operator it does not
    recognize it does NOT report an error: it falls back to implicit equality
    and absorbs the remainder as the value, building `col = 'op:val'`. On a
    typed column PostgreSQL then fails the cast and the query errors loudly,
    but on a text column the comparison is valid and matches nothing --
    returning zero rows under HTTP 200, indistinguishable from an honest
    absence of data.

    Since this reader reports an empty result as authoritative, that failure
    mode would counterfeit exactly the claim it is most important to get
    right. Validating here turns it into an exception at the call site.
    """
    if op not in QE_OPERATORS:
        raise DqmConfigError(
            f"unsupported Query Engine operator {op!r}; QE accepts only "
            f"{sorted(QE_OPERATORS)} and, for anything else on a text column, "
            f"silently returns no rows instead of an error. There is no 'in' "
            f"or 'like', and operators are lower-case."
        )
    return f"{column}:{op}:{value}"


def where_eq(column: str, value: Any) -> str:
    """Build an equality clause using QE's bare "col:value" form.

    Preferred over where(column, "eq", value) when the operator is not itself
    a variable: there is no operator present to get wrong.
    """
    return f"{column}:{value}"


class _IterStream(io.RawIOBase):
    """A readable file object over requests' chunk iterator.

    read_csv needs a file-like object, and requests' own `response.raw` is not
    quite one: urllib3 closes it as soon as the body is exhausted, so pandas
    hits "I/O operation on closed file" while finishing the parse -- reliably
    on small responses, where the first read already reaches the end.
    iter_content handles both the chunking and any content-encoding, and
    returning 0 at exhaustion gives pandas the clean EOF it expects.
    """

    def __init__(self, chunks: Iterable[bytes]) -> None:
        self._chunks = iter(chunks)
        self._buffer = b""

    def readable(self) -> bool:
        return True

    def readinto(self, target) -> int:  # type: ignore[override]
        wanted = len(target)
        while len(self._buffer) < wanted:
            try:
                chunk = next(self._chunks)
            except StopIteration:
                break
            if chunk:
                self._buffer += chunk
        taken = self._buffer[:wanted]
        self._buffer = self._buffer[len(taken):]
        target[: len(taken)] = taken
        return len(taken)


@dataclass
class QEClient:
    """An HTTP connection to one database through Query Engine.

    Holds the endpoint and the session; knows nothing about DQM tables beyond
    the dtypes it applies while parsing. reader.py builds the queries.
    """

    base_url: str = DEFAULT_QE_NOCACHE_URL
    dbname: str = DEFAULT_DBNAME
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    session: Optional[requests.Session] = None

    def __post_init__(self) -> None:
        if ":8444/" in self.base_url:
            raise DqmConfigError(
                "base_url points at the Query Engine cache endpoint (:8444), "
                "which can serve stale rows; the nocache endpoint (:9443) is "
                "required for a monitoring database"
            )
        if self.session is None:
            # A Session reuses the TLS connection, which matters when a
            # multi-id filter turns into a few hundred sequential queries.
            self.session = requests.Session()

    def __repr__(self) -> str:
        return f"QEClient(dbname={self.dbname!r}, base_url={self.base_url!r})"

    # ------------------------------------------------------------------ request

    def _request(
        self,
        table: str,
        columns: Sequence[str],
        clauses: Optional[Sequence[str]],
        order: Optional[str],
        limit: Optional[int],
    ) -> requests.Response:
        column_spec = ",".join(columns)
        params: List[Tuple[str, str]] = [
            ("dbname", self.dbname),
            ("t", table),
            ("c", column_spec),
            ("f", "csv"),
        ]
        # Repeated `w` parameters are ANDed by QE.
        for clause in clauses or []:
            params.append(("w", clause))
        if order:
            params.append(("o", order))
        if limit is not None:
            params.append(("l", str(limit)))

        LOGGER.debug("QE t=%s c=%s w=%s o=%s l=%s", table, column_spec, clauses, order, limit)
        response = self.session.get(
            self.base_url, params=params, timeout=self.timeout_seconds, stream=True
        )
        if response.status_code >= 400:
            # QE puts the actual cause -- a bad column name, a where clause
            # the SQL layer rejected -- in the body. A bare raise_for_status
            # would discard that, leaving only a 500 and a URL to work back
            # from.
            raise QueryEngineError(
                f"Query Engine returned HTTP {response.status_code} for "
                f"t={table} c={column_spec} w={list(clauses or [])}: "
                f"{self._error_detail(response)}"
            )
        return response

    @staticmethod
    def _error_detail(response: requests.Response, max_chars: int = 400) -> str:
        """Pull the human-readable cause out of a QE error page."""
        try:
            body = response.text
        except Exception:  # pragma: no cover - body already consumed
            return "(no response body)"
        # The useful line is the <h3> in QE's error page; the rest is a Python
        # traceback from the web layer that says nothing about the query.
        for marker in ("<h3>", "<h2>"):
            if marker in body:
                fragment = body.split(marker, 1)[1].split("<", 1)[0]
                if fragment.strip():
                    return " ".join(fragment.split())[:max_chars]
        return " ".join(body.split())[:max_chars]

    # -------------------------------------------------------------------- parse

    def query(
        self,
        table: str,
        columns: Sequence[str],
        clauses: Optional[Sequence[str]] = None,
        order: Optional[str] = None,
        limit: Optional[int] = None,
        chunksize: Optional[int] = None,
    ) -> Union[pd.DataFrame, Iterator[pd.DataFrame]]:
        """Run one query and return a typed DataFrame.

        With `chunksize`, returns an iterator of frames instead, so a result
        too large to hold can be processed a piece at a time.

        No limit is applied unless given -- QE with no `l` parameter returns
        the entire table. Enforcing a default belongs to the layer above,
        which knows what the caller asked for.
        """
        response = self._request(table, columns, clauses, order, limit)
        return self._read_csv(response, columns, chunksize=chunksize)

    def _read_csv(
        self,
        response: requests.Response,
        columns: Sequence[str],
        chunksize: Optional[int] = None,
    ):
        buffered = io.BufferedReader(
            _IterStream(response.iter_content(chunk_size=65536)), buffer_size=65536
        )

        # peek() does not consume, so the same bytes still reach read_csv.
        self._check_payload(buffered.peek(_PEEK_BYTES), columns)

        parse_dates = [c for c in columns if c in TIME_COLUMNS]
        frames = pd.read_csv(
            buffered,
            dtype=dtypes_for(columns, exclude=parse_dates),
            chunksize=chunksize,
        )
        if chunksize is None:
            return self._finish(frames, parse_dates)
        return (self._finish(chunk, parse_dates) for chunk in frames)

    @staticmethod
    def _finish(df: pd.DataFrame, parse_dates: Sequence[str]) -> pd.DataFrame:
        # utc=True is required, not cosmetic: QE renders timestamps with a
        # local offset that shifts across DST ("-05:00" in summer, "-06:00" in
        # winter), and a column of mixed offsets is left as opaque objects
        # rather than a comparable datetime64 column.
        #
        # format is required for the same reason.  Left to infer, pandas takes
        # the format of the first value and coerces everything that does not
        # match it to NaT.  QE renders a postgres infinity as
        # "9999-12-31 23:59:59.999999+00:00", with microseconds, where an
        # ordinary timestamp has none - so one infinity sorting first turns a
        # whole column of good timestamps into NaT.  ISO8601 accepts both.
        for column in parse_dates:
            if column in df.columns:
                df[column] = pd.to_datetime(
                    df[column], utc=True, errors="coerce", format="ISO8601"
                )
        return df

    @staticmethod
    def _check_payload(head: bytes, columns: Sequence[str]) -> None:
        """Reject a response that is not the CSV header that was asked for.

        QE reports some failures as an HTML page served under HTTP 200.
        Without this check read_csv would parse that page into a frame of
        nonsense and the caller would see an odd-looking result rather than
        an error.
        """
        text = head.decode("utf-8", errors="replace").lstrip()
        if not text:
            raise QueryEngineError("Query Engine returned an empty response")
        first_line = text.splitlines()[0].strip()
        expected = ",".join(columns)
        if first_line != expected:
            detail = text[:500].replace("\n", " ")
            raise QueryEngineError(
                f"Query Engine did not return the requested CSV "
                f"(expected header {expected!r}, got {first_line!r}): {detail}"
            )
