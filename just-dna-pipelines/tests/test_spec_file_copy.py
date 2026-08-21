"""The compiled manifest survives the spec-file copy that runs after a compile.

`register_custom_module` compiles a spec into an output directory and then copies the
authored files alongside the parquets, so the module can be loaded back into the editing
slot. That copy used to include every `.json` in the spec directory — and `manifest.json`
is a `.json` in the spec directory of every module we ship.

The result was that a freshly registered module carried the manifest of a *previous*
build: wrong `artifact.digest`, wrong `compiled_at`, and — if the spec had been renamed —
wrong module name. `read_module_provenance` reads that file to fill the report's
"Modules in this report" table, whose entire purpose is tying a saved report to the module
version behind it, so the report stated the wrong identity with full confidence.

Reproduced end to end against a real compile in `docs/MODULE_DOGFOODING.md` § D24; pinned
here at the seam itself so it needs no compiler, no network and no fixture module.
"""

import json
from pathlib import Path

import pytest

from just_dna_pipelines.module_registry import (
    COMPILER_OWNED_OUTPUTS,
    SPEC_COPY_SUFFIXES,
    copy_spec_files,
)

FRESH = {"artifact": {"digest": "sha256:fresh"}, "compilation": {"compiled_at": "2026-08-21T00:00:00Z"}}
STALE = {"artifact": {"digest": "sha256:stale"}, "compilation": {"compiled_at": "2026-08-09T00:00:00Z"}}


@pytest.fixture
def spec_and_output(tmp_path: Path) -> tuple[Path, Path]:
    """A spec directory carrying a stale manifest, beside an output dir carrying a fresh one."""
    spec = tmp_path / "spec"
    out = tmp_path / "out"
    spec.mkdir()
    out.mkdir()

    (spec / "module_spec.yaml").write_text("schema_version: '1.0'\n")
    (spec / "variants.csv").write_text("rsid,genotype\nrs1,A/A\n")
    (spec / "README.md").write_text("# a module\n")
    (spec / "logo.png").write_bytes(b"\x89PNG\r\n")
    (spec / "v1_port.log").write_text("built\n")
    (spec / "weights.parquet").write_bytes(b"PAR1")  # compiler-written, wrong suffix to copy
    (spec / "manifest.json").write_text(json.dumps(STALE))
    (spec / "provenance.json").write_text(json.dumps({"kept": True}))  # a .json that SHOULD travel

    (out / "manifest.json").write_text(json.dumps(FRESH))
    return spec, out


def test_the_compiled_manifest_is_not_overwritten(spec_and_output: tuple[Path, Path]) -> None:
    spec, out = spec_and_output
    copy_spec_files(spec, out)

    survived = json.loads((out / "manifest.json").read_text())
    assert survived == FRESH, "the spec directory's stale manifest overwrote the compiled one"
    assert survived["artifact"]["digest"] != STALE["artifact"]["digest"]


def test_the_stale_manifest_is_left_where_it_was(spec_and_output: tuple[Path, Path]) -> None:
    """Excluded from the copy, not deleted — the spec directory is the author's, not ours."""
    spec, out = spec_and_output
    copy_spec_files(spec, out)

    assert json.loads((spec / "manifest.json").read_text()) == STALE


def test_every_other_authored_file_still_travels(spec_and_output: tuple[Path, Path]) -> None:
    """The exclusion is one name, not a retreat from copying spec files."""
    spec, out = spec_and_output
    copied = copy_spec_files(spec, out)

    expected = {
        f.name
        for f in spec.iterdir()
        if f.suffix.lower() in SPEC_COPY_SUFFIXES and f.name.lower() not in COMPILER_OWNED_OUTPUTS
    }
    assert set(copied) == expected
    assert "provenance.json" in copied, "a non-manifest .json must still be carried"
    for name in expected:
        assert (out / name).exists()


def test_compiler_written_parquets_are_never_copied(spec_and_output: tuple[Path, Path]) -> None:
    spec, out = spec_and_output
    copied = copy_spec_files(spec, out)

    assert "weights.parquet" not in copied
    assert not (out / "weights.parquet").exists()


def test_the_exclusion_is_case_insensitive(tmp_path: Path) -> None:
    """A spec written on a case-preserving filesystem must not slip past the name check."""
    spec = tmp_path / "spec"
    out = tmp_path / "out"
    spec.mkdir()
    out.mkdir()
    (spec / "MANIFEST.json").write_text(json.dumps(STALE))
    (out / "manifest.json").write_text(json.dumps(FRESH))

    copied = copy_spec_files(spec, out)

    assert copied == []
    assert json.loads((out / "manifest.json").read_text()) == FRESH
