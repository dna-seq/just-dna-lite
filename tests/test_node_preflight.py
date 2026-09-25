"""`uv run start` refuses a Node.js the dev frontend cannot run on, and says what to do.

Below Reflex's minimum Node, Reflex falls back to `bun --bun run dev`, and react-router 8's
dev command then loops on a restart Bun cannot honour (it ignores `--conditions` passed through
NODE_OPTIONS) and dies with "restartWithMergedOptions() was called, but the process has already
been restarted". A Windows user on Node 22.15 hit exactly that.
"""

import pytest
import typer
from packaging import version
from reflex.utils import js_runtimes
from reflex_base import constants

from just_dna_lite import cli
from just_dna_lite.frontend_runtime import node_too_old_for_dev_server

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
    assert node_too_old_for_dev_server() == ""


def test_outdated_node_names_both_versions_and_both_ways_out(monkeypatch: pytest.MonkeyPatch) -> None:
    installed = _older(REQUIRED)
    monkeypatch.setattr(js_runtimes, "get_node_version", lambda: installed)
    message = node_too_old_for_dev_server()
    assert str(installed) in message
    assert str(REQUIRED) in message
    assert "uv run serve" in message
    assert "nodejs.org" in message


def test_missing_node_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(js_runtimes, "get_node_version", lambda: None)
    assert "No Node.js was found" in node_too_old_for_dev_server()


def test_start_refuses_before_spawning_anything(monkeypatch: pytest.MonkeyPatch) -> None:
    """The check runs in the launcher, ahead of Dagster, the reapers and the banner.

    Inside the UI child it would fire only after `uv run start` had already launched Dagster and
    printed "Stack is starting!", which reads as success.
    """
    monkeypatch.setattr(cli, "node_too_old_for_dev_server", lambda: "Node.js 22.15.0 is installed")

    def must_not_run(*args: object, **kwargs: object) -> None:
        raise AssertionError("the launcher reached process startup")

    monkeypatch.setattr(cli, "reap_dagster_instance", must_not_run)
    monkeypatch.setattr(cli.subprocess, "Popen", must_not_run)
    with pytest.raises(typer.Exit) as exited:
        cli.start_all()
    assert exited.value.exit_code == 1
