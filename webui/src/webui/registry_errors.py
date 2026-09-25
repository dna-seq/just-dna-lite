"""Why a registry call never got an answer, in words the reader can act on.

Every Catalog call is wrapped in ``except Exception`` so an unreachable server cannot blank the
page (see ``webui.state.RegistryState``). That leaves the exception's own text as the entire
report, and for a transport failure that text is something like ``[Errno 101] Network is
unreachable`` — which names neither the host that was tried nor whose side the fault is on. A
user hit exactly that on a fresh install and had nothing on screen, and nothing on disk, saying
the app had tried ``module-registry.just-dna.life`` at all.

Two halves, both of which were missing:

* :func:`describe_registry_failure` names the server in every case and, where the OS said *why*,
  what to check. The URL matters most when it is **not** the default — a self-hosted store or a
  ``$REGISTRY_URL`` typo reads identically to a network outage otherwise.
* :func:`describe_contract_mismatch` covers the one refusal that *did* get an answer: the server
  speaks a different interface contract. It says which side is behind, judged on the contract the
  two sides speak (API version, then ``just-dna-format``), never on the registry package version,
  which is path-versioned and does not decide compatibility.
* :func:`report_registry_failure` also puts the traceback on the log. Nothing in this app
  configures a handler, so :mod:`logging`'s last-resort handler carries ``ERROR`` to stderr, i.e.
  the terminal running ``uv run start``. That is the only copy; do not describe it as a log file.

The errno walk goes through ``__cause__`` *and* ``__context__``: httpx raises
``ConnectError`` from httpcore's, which in turn wraps the ``OSError`` — three links deep, and
implicit chaining inside an ``except`` block sets only ``__context__``.
"""

from __future__ import annotations

import errno
import logging
import socket
from urllib.parse import urlsplit

from just_dna_format.identity import parse_version
from just_dna_registry.version import VersionInfo

logger = logging.getLogger(__name__)

#: Suffix on every message: where the traceback went. Nothing writes it to a file.
_WHERE_THE_DETAIL_IS: str = "Full details are in the terminal running the app."

#: OS-level causes worth translating. Anything absent falls through to the exception's own text,
#: which is the right outcome for a fault we have nothing better to say about.
_ERRNO_HINTS: dict[int, str] = {
    errno.ENETUNREACH: (
        "there is no network route to it from this machine (errno {code}). "
        "That usually means an IPv6-only network reaching an IPv4-only server, a VPN, "
        "or a firewall"
    ),
    errno.EHOSTUNREACH: (
        "the host cannot be reached from this machine (errno {code}) — check the network, "
        "a VPN, or a firewall"
    ),
    errno.ECONNREFUSED: (
        "the connection was refused (errno {code}) — the server may be down, or the URL "
        "may name the wrong host or port"
    ),
}


def _os_error_in(exc: BaseException) -> OSError | None:
    """The first ``OSError`` in the exception chain, or ``None``.

    Bounded by an identity set because a chain can loop back on itself.
    """
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, OSError):
            return current
        current = current.__cause__ or current.__context__
    return None


def _is_timeout(exc: BaseException) -> bool:
    """Whether the chain bottoms out in a timeout rather than a refusal or a routing failure.

    ``httpx.ConnectTimeout`` wraps no ``OSError`` at all, so the errno walk finds nothing and this
    is the only way to tell "silently dropped" apart from "we have no idea".
    """
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, TimeoutError):
            return True
        if type(current).__name__.endswith("Timeout"):
            return True
        current = current.__cause__ or current.__context__
    return False


def _reason(url: str, exc: BaseException) -> str:
    """The clause after the URL: why the call failed, in the OS's terms where it gave any."""
    os_error = _os_error_in(exc)
    if isinstance(os_error, socket.gaierror):
        host = urlsplit(url).hostname or url
        return (
            f"the name {host} could not be resolved — check this machine's DNS "
            "and whether it is online"
        )
    if os_error is not None and os_error.errno in _ERRNO_HINTS:
        return _ERRNO_HINTS[os_error.errno].format(code=os_error.errno)
    if _is_timeout(exc):
        return (
            "it did not answer in time — a firewall or proxy may be dropping the connection, "
            "or the server may be overloaded"
        )
    return f"{type(exc).__name__}: {exc}"


def describe_registry_failure(action: str, url: str, exc: BaseException) -> str:
    """User-facing text for a registry call that failed.

    ``action`` is an infinitive naming what was being attempted ("browse the catalog"), so the
    message reads as one sentence about this click rather than a decontextualised error.
    """
    return f"Could not {action} — {url}: {_reason(url, exc)}. {_WHERE_THE_DETAIL_IS}"


def report_registry_failure(action: str, url: str, exc: BaseException) -> str:
    """Log the traceback, return the text to show. One call so no site can do only half.

    ``exc_info=exc`` rather than :meth:`logging.Logger.exception`, which reads
    ``sys.exc_info()`` and would therefore log *no* traceback if this is ever called from
    outside the ``except`` block that caught it.
    """
    logger.error("Registry call failed: could not %s (%s)", action, url, exc_info=exc)
    return describe_registry_failure(action, url, exc)


def _contract_order(server: str | None, client: str | None, parse) -> int | None:
    """-1 if the server's side is older, 1 if newer, 0 if equal, ``None`` if it cannot be told."""
    if not server or not client:
        return None
    try:
        s, c = parse(server), parse(client)
    except ValueError:
        return None
    return (s > c) - (s < c)


def _api_number(api: str) -> int:
    """``"v1"`` → ``1``; raises ``ValueError`` for anything else."""
    return int(api.removeprefix("v"))


def describe_contract_mismatch(url: str, server: VersionInfo, client: VersionInfo) -> str:
    """User-facing text for a ``VersionMismatchError``: which contract differs and which side is behind.

    The registry client refuses on the API version or on the ``just-dna-format`` contract, so the
    direction is read from whichever of those differs. The registry *package* versions are
    deliberately not consulted: a server one registry release behind the client is routine and
    compatible, and reading direction off it is how this app came to say "the server is newer"
    to a user whose app was the newer side.
    """
    if server.api != client.api:
        what = f"API {client.api}, the server speaks API {server.api}"
        order = _contract_order(server.api, client.api, _api_number)
    else:
        what = f"just-dna-format {client.format}, the server speaks {server.format}"
        order = _contract_order(server.format, client.format, parse_version)
    if order is not None and order < 0:
        remedy = (
            "The server is behind this app; it has to be upgraded before this app can exchange "
            "modules with it. Nothing to do on this machine."
        )
    elif order is not None and order > 0:
        remedy = "This app is behind the server; update just-dna-lite."
    else:
        remedy = "Could not tell which side is older."
    return f"Incompatible catalog server {url}: this app speaks {what}. {remedy}"
