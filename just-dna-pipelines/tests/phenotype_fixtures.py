"""Shared helpers for the compound-phenotype tests.

The fixtures under ``tests/fixtures/phenotypes/`` are *spec directories* (authored CSVs +
``module_spec.yaml``), vendored copies of just-dna-format's reference examples. They are compiled
at test time with the installed compiler so the tests run against a real 0.7 artifact — the same
bytes discovery and the caller see in production — rather than a hand-written parquet that could
drift from the compiler's actual output.

Vendoring the spec (not the parquet) keeps the tests honest across a compiler bump and avoids a path
dependency on a sibling checkout (the repo rule).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from just_dna_compiler.compiler import compile_module

from just_dna_pipelines.annotation.hf_modules import ModuleInfo, _probe_module_at_path

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "phenotypes"
PHENOTYPE_FIXTURES = ("apoe_epsilon", "hfe_compound_het")


def compile_fixture(name: str, out_dir: Path) -> Path:
    """Compile a vendored spec directory into ``out_dir`` and return the artifact path.

    Uses the canonical 0.5+ call: ``resolve_with_ensembl=True, ensembl_cache=None``. That flag is
    the master switch for resolution, not a choice of reference — with it False, a module with a
    complete ``resolution.csv`` still compiles but with ``chrom=None`` on every row (CLAUDE.md's
    "0.5 traps"). The fixtures carry inline coordinates and a ``resolution.csv``, so True keeps them.
    """
    spec_dir = FIXTURES_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    compile_module(spec_dir, out_dir, resolve_with_ensembl=True, ensembl_cache=None)
    return out_dir


def probe_local(module_dir: Path, name: Optional[str] = None) -> ModuleInfo:
    """Build a ``ModuleInfo`` from a compiled directory over ``LocalFileSystem``.

    This is discovery's own probe (the fsspec path), so the ``*_url`` fields and ``lead_table`` are
    wired exactly as they would be for a registry-installed module.
    """
    from fsspec.implementations.local import LocalFileSystem

    module_name = name or module_dir.name
    info = _probe_module_at_path(
        LocalFileSystem(), str(module_dir), "file", module_name, str(module_dir), str(module_dir)
    )
    if info is None:
        raise AssertionError(f"{module_dir} did not probe to a module")
    return info
