"""Restrict which addresses may reach the application.

The app binds 0.0.0.0 so a reverse proxy on another host can reach it, which
also leaves the port open to everything else that can route to it. This filter
closes that: requests from an address outside the allow list get 403 and never
touch a callback.

    DQM_WEB_ALLOW=131.225.111.176,131.225.111.177,2620:6a:0:400:f0:0:111:176

Comma-separated, and each entry may be a single address or a CIDR network, in
IPv4 or IPv6. Loopback is always allowed, so a filter cannot lock the host out
of its own service.

Unset means no filtering at all. That is deliberate: a security control that
switches itself on during an upgrade and cuts off access is worse than one
that has to be asked for. The policy in force is logged once at startup, so
which it is never has to be guessed.

What this does and does not buy
-------------------------------
It is not authentication. Anyone able to send packets from an allowed address
is allowed, and everything on the app's own host is allowed via loopback. What
it does is force traffic through the reverse proxy, which is where the real
authentication happens -- at Fermilab, SSO. Without it, the proxy's SSO is
merely the polite way in rather than the only way in.

The check uses the peer address of the TCP connection. X-Forwarded-For is
deliberately NOT consulted: a client can put anything in that header, so
trusting it here would hand the allow list to the caller. The consequence is
that the address seen is the proxy's, not the browser's -- which is exactly
what is being allowed.
"""

from __future__ import annotations

import ipaddress
import logging
import os
from typing import Iterable, List, Optional, Sequence, Tuple

LOGGER = logging.getLogger("dqm.web.access")

__all__ = ["ENV_VAR", "parse_allow", "is_allowed", "install_access_filter"]

ENV_VAR = "DQM_WEB_ALLOW"

# Always permitted, so that a mistake in the list cannot lock the service's own
# host out of it -- systemd's health check and a local curl both arrive this
# way.
_LOOPBACK = ("127.0.0.0/8", "::1/128")


def parse_allow(spec: Optional[str]) -> List[ipaddress._BaseNetwork]:
    """Turn the configured string into networks, loopback included.

    Unparseable entries are logged and skipped rather than raising: one typo
    in a list of five should not stop the application from starting, and the
    log says exactly which entry was ignored.
    """
    nets: List[ipaddress._BaseNetwork] = [
        ipaddress.ip_network(n) for n in _LOOPBACK
    ]
    if not spec:
        return nets

    for raw in spec.split(","):
        entry = raw.strip()
        if not entry:
            continue
        try:
            # strict=False so a host address with a prefix ("10.0.0.5/24") is
            # accepted as the containing network rather than rejected.
            nets.append(ipaddress.ip_network(entry, strict=False))
        except ValueError as exc:
            LOGGER.error("%s: ignoring %r -- not an address or network (%s)",
                         ENV_VAR, entry, exc)
    return nets


def _as_address(raw: Optional[str]) -> Optional[ipaddress._BaseAddress]:
    """The peer address as something comparable, or None if unreadable.

    An IPv4 client reaching a dual-stack socket appears as an IPv4-mapped IPv6
    address (::ffff:131.225.111.176).  Unmapping it is what lets one IPv4
    entry in the list match such a client; without this the list would
    silently fail to match and everything would be refused.
    """
    if not raw:
        return None
    try:
        addr = ipaddress.ip_address(raw)
    except ValueError:
        return None
    mapped = getattr(addr, "ipv4_mapped", None)
    return mapped or addr


def is_allowed(remote: Optional[str],
               nets: Sequence[ipaddress._BaseNetwork]) -> bool:
    """True if this peer address falls inside any allowed network.

    An address that cannot be parsed is refused.  That only happens when the
    WSGI server reports something unexpected, and in that case refusing is the
    safer reading of an ambiguous situation.
    """
    addr = _as_address(remote)
    if addr is None:
        return False
    return any(addr in net for net in nets)


def install_access_filter(server, spec: Optional[str] = None) -> bool:
    """Attach the filter to a Flask server. Returns True if it is active.

    Covers every route on the server -- Dash's internals, the assets, the
    export routes, /healthz -- because it runs before request dispatch rather
    than per view.
    """
    if spec is None:
        spec = os.environ.get(ENV_VAR)

    if not spec:
        LOGGER.info("no %s set -- every address that can reach the port is "
                    "served", ENV_VAR)
        return False

    nets = parse_allow(spec)
    # Only loopback parsed: the configured entries were all bad, and carrying
    # on would quietly serve nobody but the local host.  Say so loudly.
    if len(nets) == len(_LOOPBACK):
        LOGGER.error("%s=%r yielded no usable entries -- only loopback will "
                     "be served", ENV_VAR, spec)

    from flask import request

    @server.before_request
    def _restrict():  # pragma: no cover - exercised over HTTP
        if is_allowed(request.remote_addr, nets):
            return None
        # Info, not warning: a port open to an organisation collects scanner
        # traffic, and this line would otherwise flood the log.
        LOGGER.info("refused %s for %s", request.remote_addr, request.path)
        return ("Forbidden: this address is not permitted to reach the DQM "
                "application.\n", 403, {"Content-Type": "text/plain"})

    LOGGER.info("%s active -- serving %s", ENV_VAR,
                ", ".join(str(n) for n in nets))
    return True
