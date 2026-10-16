"""Command-line access to the DQM database -- the `dqm-reader` script.

A tool for looking at the database by hand: checking what sources exist,
confirming a timeline looks sane, counting rows. It prints frames with
to_string(), so it is for reading rather than for extracting data into a
pipeline -- for anything programmatic, import DqmReader.

    dqm-reader --sources
    dqm-reader --sid 5 --vid 15 --summary
    dqm-reader --count
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Optional, Sequence

from dqm.errors import DqmError
from dqm.reader.reader import DqmReader
from dqm.reader.transport import DEFAULT_DBNAME, DEFAULT_QE_NOCACHE_URL
from dqm.schema import METRIC_TABLES

# Enough rows to see a pattern, few enough to fit a terminal.
DEFAULT_ROW_LIMIT = 20


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dqm-reader",
        description="Query the Mu2e DQM database through Query Engine.",
    )
    parser.add_argument("--dbname", default=DEFAULT_DBNAME)
    parser.add_argument("--base-url", default=DEFAULT_QE_NOCACHE_URL)
    parser.add_argument(
        "--table", default="numbers", choices=sorted(METRIC_TABLES),
        help="which measurement table to query (default: %(default)s)",
    )
    parser.add_argument("--sources", action="store_true", help="list sources and exit")
    parser.add_argument("--values", action="store_true", help="list metric names and exit")
    parser.add_argument("--sid", type=int, default=None, help="restrict to one source")
    parser.add_argument("--vid", type=int, default=None, help="restrict to one metric")
    parser.add_argument("--recent-days", type=float, default=None,
                        help="only intervals ending within this many days")
    parser.add_argument(
        "--limit", type=int, default=None,
        help=f"max rows; 0 means no limit (default: {DEFAULT_ROW_LIMIT} for rows, "
             f"no limit for --summary, since a summary of the first "
             f"{DEFAULT_ROW_LIMIT} rows answers a different question)",
    )
    parser.add_argument("--summary", action="store_true",
                        help="print statistics over the whole match, not rows")
    parser.add_argument("--count", action="store_true",
                        help="print the exact number of matching rows")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="log each Query Engine request")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    # --limit 0 means unlimited; absent means "the sensible default for what
    # was asked", which differs between rows and a summary.
    if args.limit is None:
        limit = None if args.summary else DEFAULT_ROW_LIMIT
    else:
        limit = args.limit or None

    reader = DqmReader(base_url=args.base_url, dbname=args.dbname)

    try:
        if args.sources:
            print(reader.sources(limit=limit).to_string(index=False))
            return 0
        if args.values:
            print(reader.values(limit=limit).to_string(index=False))
            return 0

        selection = dict(
            table=args.table,
            sid=args.sid,
            vid=args.vid,
            recent_days=args.recent_days,
        )

        if args.count:
            print(reader.count_metrics(**selection))
            return 0

        df = reader.metrics(limit=limit, **selection)
        if args.summary:
            print(json.dumps(reader.summarize(df), indent=2))
        else:
            if df.empty:
                print("(no matching rows)")
            else:
                print(df.to_string(index=False))
            if df.attrs.get("truncated"):
                total = reader.count_metrics(**selection)
                print(
                    f"\n[showing {len(df)} of {total}; "
                    f"raise --limit, or use --summary for the whole range]"
                )
        return 0
    except DqmError as exc:
        # Expected failures -- a bad table, an unreachable endpoint, a filter
        # too broad to push down -- are the user's problem to fix, so report
        # them as a message rather than a traceback.
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
