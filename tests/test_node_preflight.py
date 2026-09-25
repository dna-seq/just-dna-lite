"""`uv run start` refuses a Node.js the dev frontend cannot run on, and says what to do.

Below Reflex's minimum Node, Reflex falls back to `bun --bun run dev`, and react-router 8's
dev command then loops on a restart Bun cannot honour (it ignores `--conditions` passed through
NODE_OPTIONS) and dies with "restartWithMergedOptions() was called, but the process has already
been restarted". A Windows user on Node 22.15 hit exactly that.
"""

import pytest
from packaging import version
from reflex.utils import js_runtimes
from reflex_base import constants

from webui.run import _node_too_old_for_dev_server

REQUIRED = version.parse(constants.Node.MIN_VERSION)


def _older(v: version.Version) -> version.Version:
    major, minor, micro = v.release[0], v.release[1], v.release[2]
    if micro:
        return version.parse(f"{major}.{minor}.{micro - 1}")
    if minor:
        return version.parse(f"{major}.{minor - 1}.99")
    return version.parse(f"{major - 1}.99.99")


@pytest.mark.parametrize(
    "installed",
    [REQUIRED, version.parse(f"{REQUIRED.release[0] + 2}.0.0")],
    ids=["exactly-minimum", "newer-major"],
)
def test_supported_node_passes(monkeypatch: pytest.MonkeyPatch, installed: version.Version) -> None:
    monkeypatch.setattr(js_runtimes, "get_node_version", lambda: installed)
    assert _node_too_old_for_dev_server() == ""


def test_outdated_node_names_both_versions_and_both_ways_out(monkeypatch: pytest.MonkeyPatch) -> None:
    installed = _older(REQUIRED)
    monkeypatch.setattr(js_runtimes, "get_node_version", lambda: installed)
    message = _node_too_old_for_dev_server()
    assert str(installed) in message
    assert str(REQUIRED) in message
    assert "uv run serve" in message
    assert "nodejs.org" in message


def test_missing_node_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(js_runtimes, "get_node_version", lambda: None)
    assert "No Node.js was found" in _node_too_old_for_dev_server()
