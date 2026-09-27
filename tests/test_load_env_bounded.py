"""``load_env`` must never read a ``.env`` that lives above the workspace root.

Regression for the sibling-project leak: this checkout had no ``.env``, ``find_dotenv`` climbed
to ``~/sources/.env`` (another project's), and every report link was built on that project's
``DEPLOY_URL``. The tests build a throwaway workspace under ``tmp_path`` with a poisoned ``.env``
one level *above* it, so the only way to pass is to stop at the root.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from just_dna_pipelines import runtime

POISON_KEY = "JDL_TEST_POISON_DEPLOY_URL"
TEMPLATE_KEY = "JDL_TEST_TEMPLATE_ONLY"
ENV_KEY = "JDL_TEST_REAL_ENV"


def _make_workspace(tmp_path: Path, with_env: bool) -> Path:
    """``tmp_path/outer/.env`` is the trap; ``tmp_path/outer/repo`` is the workspace."""
    outer = tmp_path / "outer"
    repo = outer / "repo"
    (repo / "sub" / "deeper").mkdir(parents=True)
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "fake"\n\n[tool.uv.workspace]\nmembers = []\n', encoding="utf-8"
    )
    (outer / ".env").write_text(f"{POISON_KEY}=https://other-project.example\n", encoding="utf-8")
    (repo / ".env.template").write_text(f"{TEMPLATE_KEY}=from-template\n", encoding="utf-8")
    if with_env:
        (repo / ".env").write_text(f"{ENV_KEY}=from-env\n", encoding="utf-8")
    return repo


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch):
    for key in (POISON_KEY, TEMPLATE_KEY, ENV_KEY, "JUST_DNA_PIPELINES_ROOT"):
        monkeypatch.delenv(key, raising=False)
    yield


def test_env_above_workspace_is_never_loaded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_env) -> None:
    repo = _make_workspace(tmp_path, with_env=False)
    monkeypatch.setenv("JUST_DNA_PIPELINES_ROOT", str(repo))
    monkeypatch.chdir(repo / "sub" / "deeper")

    loaded = runtime.load_env()

    assert loaded == str(repo / ".env.template")
    assert os.environ.get(TEMPLATE_KEY) == "from-template"
    assert POISON_KEY not in os.environ, "a .env above the workspace root was read"


def test_real_env_wins_over_template(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_env) -> None:
    repo = _make_workspace(tmp_path, with_env=True)
    monkeypatch.setenv("JUST_DNA_PIPELINES_ROOT", str(repo))
    monkeypatch.chdir(repo)

    loaded = runtime.load_env()

    assert loaded == str(repo / ".env")
    assert os.environ.get(ENV_KEY) == "from-env"
    assert TEMPLATE_KEY not in os.environ, ".env.template must only be the fallback"
    assert POISON_KEY not in os.environ


def test_cwd_walk_stops_at_workspace_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_env) -> None:
    """Without the env override and with the package's own root hidden, the cwd walk is bounded."""
    repo = _make_workspace(tmp_path, with_env=False)
    monkeypatch.chdir(repo / "sub" / "deeper")
    # Pretend runtime.py lives somewhere with no workspace above it (a site-packages install).
    monkeypatch.setattr(runtime, "__file__", str(tmp_path / "site-packages" / "just_dna_pipelines" / "runtime.py"))

    assert runtime.find_workspace_root() == repo
    assert runtime.load_env() == str(repo / ".env.template")
    assert POISON_KEY not in os.environ


def test_environ_guard_reverts_foreign_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_env) -> None:
    """A dependency that load_dotenv()s a foreign file inside the guard leaves os.environ untouched."""
    from dotenv import load_dotenv

    foreign = tmp_path / "foreign.env"
    foreign.write_text(f"{POISON_KEY}=https://other-project.example\n{ENV_KEY}=overwritten\n", encoding="utf-8")
    monkeypatch.setenv(ENV_KEY, "ours")

    with runtime.environ_guard():
        load_dotenv(foreign, override=True)
        assert os.environ[POISON_KEY] == "https://other-project.example"  # visible inside, as the import wants
        assert os.environ[ENV_KEY] == "overwritten"

    assert POISON_KEY not in os.environ
    assert os.environ[ENV_KEY] == "ours"


@pytest.mark.parametrize("module", ["just_dna_lite.cli", "just_dna_pipelines.cli"])
def test_cli_import_keeps_foreign_dotenv_out_of_environ(module: str) -> None:
    """Importing a launcher must not leave variables from any dotenv file outside this repo in os.environ.

    Regression for just-dna-registry's import-time ``load_dotenv()``: on a machine with a ``.env`` in
    a parent of the checkout, ``import just_dna_lite.cli`` used to add that project's ``DEPLOY_URL``
    (21 variables on the machine this was found on). The subprocess spies on ``load_dotenv`` to learn
    which files were actually read and which keys they carried, then checks that every key that
    survived the import came from a file under the workspace root. Libraries that set their own
    flags directly (``polars_bio`` sets ``POLARS_FORCE_NEW_STREAMING``) are not dotenv and are ignored.
    """
    import json
    import subprocess
    import sys

    root = runtime.find_workspace_root()
    assert root is not None

    code = f"""
import json, os, sys
from pathlib import Path
import dotenv, dotenv.main as dm
root = Path({str(root)!r}).resolve()
foreign_keys = set()
orig = dm.load_dotenv
def spy(dotenv_path=None, stream=None, verbose=False, override=False, **kw):
    path = dotenv_path or dm.find_dotenv()
    if path and root not in Path(path).resolve().parents and Path(path).resolve() != root:
        foreign_keys.update(k for k, v in dm.dotenv_values(path).items() if v is not None)
    return orig(dotenv_path, stream, verbose, override, **kw)
dm.load_dotenv = spy
dotenv.load_dotenv = spy
import {module}
leaked = sorted(k for k in foreign_keys if k in os.environ)
print(json.dumps({{"foreign_files_read": sorted(foreign_keys) != [], "leaked": leaked}}))
"""
    out = subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True, cwd=root)
    result = json.loads(out.stdout.strip().splitlines()[-1])
    assert not result["leaked"], f"{module} import left foreign dotenv variables in os.environ: {result['leaked']}"


@pytest.mark.parametrize("module", ["just_dna_lite.cli", "just_dna_pipelines.cli"])
def test_local_env_values_survive_cli_import(tmp_path: Path, module: str) -> None:
    """DEPLOY_URL / API_URL from the workspace's own .env must reach the launcher's environment.

    The guard around the registry import may only revert what that import *adds*; a value our
    own .env set beforehand is part of the configuration and has to come through intact. Uses
    a throwaway workspace root (JUST_DNA_PIPELINES_ROOT) so the checkout's real .env is not touched.
    """
    import subprocess
    import sys

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[tool.uv.workspace]\nmembers = []\n', encoding="utf-8")
    (repo / ".env").write_text(
        "DEPLOY_URL=https://lite.example.org\nAPI_URL=https://lite.example.org\n", encoding="utf-8"
    )
    code = (
        "import os\n"
        f"import {module}\n"
        "print(os.environ.get('DEPLOY_URL', ''), os.environ.get('API_URL', ''))\n"
    )
    env = {k: v for k, v in os.environ.items() if k not in ("DEPLOY_URL", "API_URL", "PUBLIC_APP_URL")}
    env["JUST_DNA_PIPELINES_ROOT"] = str(repo)
    out = subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True, env=env, cwd=repo)
    assert out.stdout.strip().splitlines()[-1] == "https://lite.example.org https://lite.example.org"


def test_package_checkout_is_the_real_workspace_root() -> None:
    """The editable install resolves to this repo, where .env.template lives."""
    root = runtime.find_workspace_root()
    assert root is not None
    assert (root / ".env.template").is_file()
    assert "[tool.uv.workspace]" in (root / "pyproject.toml").read_text(encoding="utf-8")
