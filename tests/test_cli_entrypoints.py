"""The console entry points import and answer `--help`.

Two breaks in one session arrived as "the whole CLI is dead at import" and nothing pinned it: a
relock floated agno to 3.x against an mcp cap written for agno 2 (taking `webui.state` and
`pipelines` down together), and enricher 0.7.1's Typer app raised a protobuf gencode/runtime error
that the enricher's own guard did not catch (S107). Upstream's 0.7.1 note says the same about their
side — "a test imports the console entrypoint, which nothing did before". This is ours.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from just_dna_lite.cli import app as pipelines_app
from just_dna_lite.process import dg_dev_argv, webui_dev_argv
from just_dna_pipelines import enricher_cli
from just_dna_pipelines.cli import app as shadowed_pipelines_app


def test_the_installed_pipelines_entrypoint_answers_help() -> None:
    result = CliRunner().invoke(pipelines_app, ["--help"])
    assert result.exit_code == 0, result.output
    for command in ("annotate", "module", "enrich", "registry", "prepare-caches"):
        assert command in result.output, command


def test_the_shadowed_pipelines_entrypoint_still_imports() -> None:
    """Both packages install a `pipelines` script; the root one wins, but the other must not rot."""
    result = CliRunner().invoke(shadowed_pipelines_app, ["--help"])
    assert result.exit_code == 0, result.output


def test_the_enricher_mount_is_always_a_typer_app_and_says_why_when_it_is_the_stub() -> None:
    """`enricher_app` is the real app or the stub, never `None`; the stub's `status` exits 1 with
    the captured reason so the loss is visible rather than a missing command group."""
    assert isinstance(enricher_cli.enricher_app, typer.Typer)
    result = CliRunner().invoke(pipelines_app, ["enrich", "--help"])
    assert result.exit_code == 0, result.output
    if enricher_cli.ENRICHER_CLI_UNAVAILABLE is not None:
        status = CliRunner().invoke(pipelines_app, ["enrich", "status"])
        assert status.exit_code == 1
        assert "not available" in status.output
        assert enricher_cli.ENRICHER_CLI_UNAVAILABLE.split(":")[0] in status.output
    else:
        assert "cache" in result.output


def test_launcher_children_never_start_through_a_console_script_wrapper() -> None:
    """Every hop the launchers spawn is `<this interpreter> -m <module>`.

    uv's `.venv/Scripts/<name>.exe` wrappers are unsigned executables in a user-writable folder,
    which locked-down Windows laptops (AppLocker, Smart App Control) refuse to run. A user reported
    exactly that for `start.exe`; `run.exe` and `dg.exe` sat behind it on the same path.
    """
    for argv in (webui_dev_argv(), dg_dev_argv(Path("definitions.py"), 3005, "127.0.0.1")):
        assert argv[:2] == [sys.executable, "-m"], argv
        assert importlib.util.find_spec(argv[2]) is not None, argv[2]


@pytest.mark.parametrize(
    "module_args",
    [
        ["just_dna_lite.dg", "dev", "--help"],
        ["just_dna_lite.cli", "start", "--help"],
    ],
    ids=["dg-shim", "start-without-wrapper"],
)
def test_the_wrapperless_entry_modules_answer_help(module_args: list[str]) -> None:
    """The `python -m` forms the launchers and the Windows `.bat` rely on really run."""
    result = subprocess.run(
        [sys.executable, "-m", *module_args],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "Usage" in result.stdout
