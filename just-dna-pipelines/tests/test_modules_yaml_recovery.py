"""A corrupt runtime working copy of modules.yaml must not take down the Dagster code location.

``module_config._load_config()`` runs at module scope (``MODULES_CONFIG``), and every Dagster
asset module imports it transitively, so anything it raises surfaces as
``Error loading repository location definitions.py`` — a warning that carries no traceback and
whose real stack is only in the code server's stdout. The one input that can differ between a
developer checkout and a deployment is the working copy at ``data/interim/modules.yaml``: it is
gitignored and *mutated at runtime* by register/unregister, so a half-written or hand-edited file
there could kill the whole pipeline with no readable reason.

The split these tests pin: a bad **working copy** is recoverable (ignore it, keep the shipped
defaults, say so loudly), a bad **shipped default** is not (it is git-tracked, so it is a build
error — degrading to an empty catalog would mean zero modules discovered while the app still
looks healthy).
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest
import yaml

from just_dna_pipelines import module_config
from just_dna_pipelines.module_config import (
    ModulesConfig,
    _load_config,
    read_config_for_update,
    save_config,
)


BAD_SYNTAX = 'sources:\n  - url: "unclosed\n'
BAD_SCHEMA = 'quality_filters:\n  min_depth: "not-a-number-at-all"\n'


def _defaults_only_urls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> set[str]:
    """The source urls a healthy load produces with no working copy present.

    Derived by running the real loader rather than read off modules.yaml, and derived under
    *whatever environment the test session is in*: ``_drop_project_runtime_sources`` strips the
    repo-local absolute sources whenever ``JUST_DNA_PIPELINES_OUTPUT_DIR`` is set, and some other
    test module's ``load_env()`` sets it for the whole session. Reading the YAML directly compares
    a filtered result against an unfiltered expectation and fails only when the suites run together.
    """
    monkeypatch.setenv("JUST_DNA_MODULES_YAML", str(tmp_path / "absent" / "modules.yaml"))
    baseline = _load_config()
    assert baseline.sources, "a defaults-only load must still yield sources, or these tests are vacuous"
    return {source.url for source in baseline.sources}


@pytest.mark.parametrize(
    ("label", "text"),
    [("malformed_yaml", BAD_SYNTAX), ("schema_invalid", BAD_SCHEMA)],
)
def test_an_unusable_working_copy_falls_back_to_the_shipped_defaults(
    label: str, text: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Before the guard both of these raised out of ``_load_config`` and killed every asset import.

    ``malformed_yaml`` escaped as ``yaml.scanner.ScannerError`` from the bare ``safe_load``;
    ``schema_invalid`` as a pydantic ``ValidationError`` from ``model_validate``.
    """
    expected = _defaults_only_urls(tmp_path, monkeypatch)

    working = tmp_path / "modules.yaml"
    working.write_text(text)
    monkeypatch.setenv("JUST_DNA_MODULES_YAML", str(working))

    with pytest.warns(UserWarning, match="modules.yaml"):
        config = _load_config()

    # Not merely "did not raise": the shipped catalog has to survive intact, or discovery
    # would come back empty and the app would look healthy while annotating nothing.
    assert {source.url for source in config.sources} == expected
    assert config.ensembl_source.repo_id


def test_the_warning_names_the_file_so_an_operator_can_find_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A silent fallback here is worse than the crash — the file stays broken forever."""
    working = tmp_path / "modules.yaml"
    working.write_text(BAD_SYNTAX)
    monkeypatch.setenv("JUST_DNA_MODULES_YAML", str(working))

    with pytest.warns(UserWarning) as caught:
        _load_config()

    text = "\n".join(str(w.message) for w in caught)
    assert str(working) in text


def test_a_valid_working_copy_is_still_merged_over_the_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard must not cost the merge: a healthy working copy still layers on top."""
    expected = _defaults_only_urls(tmp_path, monkeypatch)

    working = tmp_path / "modules.yaml"
    working.write_text(yaml.safe_dump({"sources": [{"url": "org/custom-module", "kind": "module"}]}))
    monkeypatch.setenv("JUST_DNA_MODULES_YAML", str(working))

    config = _load_config()
    urls = {source.url for source in config.sources}
    assert "org/custom-module" in urls
    assert expected <= urls


def test_a_corrupt_shipped_default_still_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The git-tracked default is a build error, not a runtime accident.

    Recovering here would hand back ``ModulesConfig()`` — zero sources, zero modules discovered,
    and nothing on screen to say why.
    """
    broken_default = tmp_path / "default.yaml"
    broken_default.write_text(BAD_SYNTAX)
    monkeypatch.setattr(module_config, "_default_config_path", lambda: broken_default)
    monkeypatch.delenv("JUST_DNA_MODULES_YAML", raising=False)
    monkeypatch.setenv("JUST_DNA_PIPELINES_INTERIM_DIR", str(tmp_path / "empty"))

    with pytest.raises(yaml.YAMLError):
        _load_config()


def test_save_config_repairs_a_corrupt_working_copy_and_keeps_the_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Register/unregister read the same file, so the crash just moves here without this.

    The broken bytes are moved aside rather than overwritten — they are the only record of
    whatever registrations the file held.
    """
    working = tmp_path / "modules.yaml"
    working.write_text(BAD_SYNTAX)
    monkeypatch.setenv("JUST_DNA_MODULES_YAML", str(working))

    with pytest.warns(UserWarning):
        save_config(ModulesConfig(sources=[{"url": "org/kept", "kind": "module"}]))

    backup = working.with_name("modules.yaml.corrupt")
    assert backup.exists() and backup.read_text() == BAD_SYNTAX
    written = yaml.safe_load(working.read_text())
    assert [entry["url"] for entry in written["sources"]] == ["org/kept"]


# ------------------------------------------------- the mutating callers read the same file

@pytest.mark.parametrize(
    ("label", "text"),
    [("malformed_yaml", BAD_SYNTAX), ("schema_invalid", BAD_SCHEMA)],
)
def test_an_unusable_working_copy_reads_as_absent_for_a_mutation(
    label: str, text: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guarding ``_load_config`` alone would only move the crash from import to the next register.

    ``register_custom_module`` / ``unregister_custom_module`` read the working copy *alone* (not
    merged) because ``save_config`` writes the result straight back. All three of their read sites
    go through ``read_config_for_update``; ``None`` means "treat as absent", which lets each keep
    its own fallback and lets ``save_config`` repair the file on the way out.
    """
    working = tmp_path / "modules.yaml"
    working.write_text(text)

    with pytest.warns(UserWarning, match="modules.yaml"):
        assert read_config_for_update(working) is None

    # What the call sites actually compose it with — the mutation still gets a usable config.
    assert isinstance(read_config_for_update(working) or ModulesConfig(), ModulesConfig)


def test_a_healthy_working_copy_is_read_alone_and_not_merged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mutation path must NOT see the merged defaults, or a write bakes them into the copy."""
    working = tmp_path / "modules.yaml"
    working.write_text(yaml.safe_dump({"sources": [{"url": "org/only-this", "kind": "module"}]}))

    config = read_config_for_update(working)
    assert config is not None
    assert [source.url for source in config.sources] == ["org/only-this"]


def test_an_absent_working_copy_reads_as_absent_without_warning(tmp_path: Path) -> None:
    """A first-ever register is the common case and must stay quiet."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert read_config_for_update(tmp_path / "never-written.yaml") is None
