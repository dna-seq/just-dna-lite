"""
Orchestration for the v1 port: fetch → adapt → write spec → validate → compile.

Produces a standalone module directory under ``data/interim/v1_port/<module>/`` containing the
authored spec (module_spec.yaml + variants.csv + studies.csv), the compiled artifacts
(weights/annotations/studies.parquet + manifest.json), and a v1_port.log provenance record.
"""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from just_dna_pipelines.module_compiler.compiler import compile_module, validate_spec
from just_dna_pipelines.v1_port.adapters import run_adapter
from just_dna_pipelines.v1_port.sources import REGISTRY, V1Module, fetch_data_file
from just_dna_pipelines.v1_port.writer import write_spec_dir

# The Ensembl variations parquet cache (rsid -> GRCh38 position). On /data, not the small root fs.
DEFAULT_ENSEMBL_CACHE = Path("/data/just-dna-cache/ensembl_variations")
DEFAULT_OUT_ROOT = Path("data/interim/v1_port")
DEFAULT_DOWNLOAD_CACHE = Path("data/interim/v1_port/_sources")


class PortResult(BaseModel):
    """Outcome of porting one module."""

    name: str
    output_dir: Path
    variant_count: int = 0
    study_count: int = 0
    valid: bool = False
    compiled: bool = False
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def port_module(
    module: V1Module,
    *,
    out_root: Path = DEFAULT_OUT_ROOT,
    download_cache: Path = DEFAULT_DOWNLOAD_CACHE,
    do_compile: bool = True,
    ensembl_cache: Optional[Path] = DEFAULT_ENSEMBL_CACHE,
) -> PortResult:
    """Port a single module end-to-end. Compilation is skipped gracefully if it can't run."""
    out_dir = out_root / module.name
    db_path = fetch_data_file(module, download_cache)
    cache = ensembl_cache if (ensembl_cache and ensembl_cache.exists()) else None
    spec, variants, studies, warnings = run_adapter(module, db_path, cache)

    write_spec_dir(
        spec, variants, studies, out_dir,
        source_repo=module.repo, source_file=db_path, warnings=warnings,
    )

    result = PortResult(
        name=module.name, output_dir=out_dir,
        variant_count=len(variants), study_count=len(studies), warnings=list(warnings),
    )

    validation = validate_spec(out_dir)
    result.valid = validation.valid
    result.errors.extend(validation.errors)
    result.warnings.extend(validation.warnings)
    if not validation.valid:
        return result

    if do_compile:
        cache = ensembl_cache if (ensembl_cache and ensembl_cache.exists()) else None
        compiled = compile_module(
            out_dir, out_dir,
            resolve_with_ensembl=cache is not None,
            ensembl_cache=cache,
        )
        result.compiled = compiled.success
        result.errors.extend(compiled.errors)
        result.warnings.extend(compiled.warnings)

    return result


def port_all(
    names: Optional[list[str]] = None,
    *,
    out_root: Path = DEFAULT_OUT_ROOT,
    download_cache: Path = DEFAULT_DOWNLOAD_CACHE,
    do_compile: bool = True,
    ensembl_cache: Optional[Path] = DEFAULT_ENSEMBL_CACHE,
) -> list[PortResult]:
    targets = names or list(REGISTRY.keys())
    results: list[PortResult] = []
    for name in targets:
        module = REGISTRY[name]
        results.append(port_module(
            module, out_root=out_root, download_cache=download_cache,
            do_compile=do_compile, ensembl_cache=ensembl_cache,
        ))
    return results
