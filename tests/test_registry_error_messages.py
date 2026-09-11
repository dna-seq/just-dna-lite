"""What the Catalog says when the registry never answers.

Every registry call is caught so an outage cannot blank the page, which makes the message the
*entire* report — there is no traceback on screen and no log file behind it. The message that
shipped was `Could not reach the registry: [Errno 101] Network is unreachable`, which names
neither the host tried nor whose side the fault is on; a user on a fresh install had no way to
tell an IPv6-only network from a typo'd `$REGISTRY_URL`.

The chains here are produced by real `httpx` calls rather than hand-built, because the errno sits
three links down (`httpx.ConnectError` → `httpcore.ConnectError` → `OSError`) and only a live
failure pins that shape. They are network-free in the sense that matters: every address is
reserved or undelegated, so nothing leaves the machine.
"""

from __future__ import annotations

import errno
import logging
import socket

import httpx
import pytest

from webui.registry_errors import (
    _os_error_in,
    describe_registry_failure,
    report_registry_failure,
)

# RFC 3849 documentation prefix: routable to nobody, so a host with no IPv6 default route
# fails with ENETUNREACH immediately rather than hanging.
UNREACHABLE_V6 = "https://[2001:db8::1]"
# RFC 2606 reserves .invalid, so this can never resolve.
UNRESOLVABLE = "https://no-such-host.just-dna.invalid"


def _failure(url: str) -> Exception:
    """The exception an unreachable URL actually raises, chain intact."""
    with pytest.raises(httpx.HTTPError) as caught:
        httpx.get(url, timeout=5.0)
    return caught.value


def _routes_ipv6() -> bool:
    """Whether this machine has an IPv6 route at all — if it does, the probe URL times out
    instead of failing to route, and there is no ENETUNREACH to assert on."""
    probe = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    probe.settimeout(0.5)
    try:
        return probe.connect_ex(("2001:db8::1", 443)) != errno.ENETUNREACH
    finally:
        probe.close()


# --------------------------------------------------------------------------- the errno walk

def test_the_os_error_is_found_through_two_layers_of_wrapping() -> None:
    """httpx wraps httpcore wraps OSError, so a single `__cause__` hop finds nothing."""
    exc = _failure(UNRESOLVABLE)
    assert exc.__cause__ is not None, "chain flattened — the walk has nothing left to find"
    found = _os_error_in(exc)
    assert isinstance(found, socket.gaierror)


def test_a_chain_that_loops_back_terminates_instead_of_hanging() -> None:
    """No OSError anywhere in a cycle: the walk must end, not spin."""
    first, second = ValueError("a"), ValueError("b")
    second.__cause__ = first
    first.__context__ = second          # deliberate cycle
    assert _os_error_in(second) is None


# --------------------------------------------------------------------------- the message

def test_every_message_names_the_server_it_tried() -> None:
    """The missing fact that cost the afternoon: which host the app actually contacted."""
    exc = _failure(UNRESOLVABLE)
    message = describe_registry_failure("browse the catalog", UNRESOLVABLE, exc)
    assert UNRESOLVABLE in message
    assert "browse the catalog" in message


def test_a_name_that_does_not_resolve_is_reported_as_dns_not_as_a_dead_server() -> None:
    exc = _failure(UNRESOLVABLE)
    message = describe_registry_failure("browse the catalog", UNRESOLVABLE, exc)
    assert "could not be resolved" in message
    assert "no-such-host.just-dna.invalid" in message, "the bare hostname helps more than the URL"


@pytest.mark.skipif(_routes_ipv6(), reason="this machine routes IPv6, so the probe times out instead")
def test_no_route_names_the_cause_the_user_cannot_guess() -> None:
    """errno 101 on a fresh install: an IPv6-only client against an IPv4-only registry."""
    exc = _failure(UNREACHABLE_V6)
    message = describe_registry_failure("browse the catalog", UNREACHABLE_V6, exc)
    assert f"errno {errno.ENETUNREACH}" in message
    assert "IPv6-only" in message


def test_a_refusal_is_told_apart_from_a_routing_failure() -> None:
    """Different remedies: one is the server, the other is this machine's network."""
    refused = OSError(errno.ECONNREFUSED, "Connection refused")
    message = describe_registry_failure("browse the catalog", "https://localhost:9", refused)
    assert "refused" in message
    assert "IPv6-only" not in message


def test_a_dropped_connection_reads_as_a_timeout_even_though_no_oserror_survives() -> None:
    """`httpx.ConnectTimeout` wraps no OSError, so the errno walk finds nothing to say."""
    timed_out = httpx.ConnectTimeout("timed out")
    message = describe_registry_failure("browse the catalog", "https://example.invalid", timed_out)
    assert "did not answer in time" in message


def test_an_unclassifiable_failure_still_names_its_type_rather_than_going_blank() -> None:
    message = describe_registry_failure("browse the catalog", "https://example.invalid", RuntimeError("boom"))
    assert "RuntimeError" in message and "boom" in message


# --------------------------------------------------------------------------- the log

def test_reporting_puts_the_traceback_on_the_log_and_the_summary_on_screen(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The two halves are held together so no call site can do only one of them."""
    exc = _failure(UNRESOLVABLE)
    with caplog.at_level(logging.ERROR, logger="webui.registry_errors"):
        message = report_registry_failure("browse the catalog", UNRESOLVABLE, exc)
    record = next(r for r in caplog.records if r.name == "webui.registry_errors")
    assert record.exc_info is not None, "no traceback logged — the on-screen text is all there is"
    assert UNRESOLVABLE in record.getMessage()
    assert message == describe_registry_failure("browse the catalog", UNRESOLVABLE, exc)
