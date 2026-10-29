"""Launch the DQM web application -- the `dqm-web` script.

    dqm-web --port 8100
    dqm-web --port 8100 --prefix /dqm/     # behind a reverse proxy

Dash's own server is for development. For a real deployment use a WSGI server
against the module-level app:

    gunicorn --bind 127.0.0.1:8100 'dqm.web.app:server'
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional, Sequence

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8100


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dqm-web", description=__doc__.split("\n")[0])
    p.add_argument(
        "--host", default=DEFAULT_HOST,
        help="bind address (default: %(default)s). Use 0.0.0.0 to accept "
             "connections from other machines -- note this bypasses any "
             "authentication the front-end web server enforces.",
    )
    p.add_argument("--port", type=int, default=DEFAULT_PORT,
                   help="bind port (default: %(default)s)")
    p.add_argument(
        "--prefix", default=None,
        help="serve under a path prefix, e.g. /dqm/ . Sets both Dash prefixes; "
             "if the proxy strips the prefix before forwarding, set "
             "--routes-prefix separately.",
    )
    p.add_argument("--routes-prefix", default=None,
                   help="override the routes prefix when it differs from --prefix")
    p.add_argument("--debug", action="store_true",
                   help="Dash debug mode with hot reload (development only)")
    p.add_argument("--check", action="store_true",
                   help="build the app and exit, without binding a socket")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from dqm import __version__
    from dqm.web.app import create_app

    application = create_app(
        requests_pathname_prefix=args.prefix,
        routes_pathname_prefix=args.routes_prefix or args.prefix,
    )

    if args.check:
        # Report what the app resolved, not just what was typed: under
        # gunicorn the prefix comes from the environment, and a --check that
        # echoed only the flags would say "prefix=None" for a correctly
        # configured deployment.
        import os as _os

        resolved = (args.prefix
                    or _os.environ.get("DASH_REQUESTS_PATHNAME_PREFIX") or "/")
        routes = (args.routes_prefix
                  or _os.environ.get("DASH_ROUTES_PATHNAME_PREFIX") or resolved)
        print(f"OK: dqm-web built (mu2e-dqm {__version__}, "
              f"browser path={resolved} served path={routes})")
        return 0

    url_path = args.prefix or "/"
    print(f"dqm-web {__version__} serving on http://{args.host}:{args.port}{url_path}",
          file=sys.stderr)
    application.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
