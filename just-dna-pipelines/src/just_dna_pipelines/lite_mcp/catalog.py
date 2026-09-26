"""What this installation holds: genomes, annotation modules, and trial installs of new modules.

Read-only except for :func:`install_module` / :func:`uninstall_module`, which copy a compiled
module directory into the registered-modules dir the same way a registry download does (route A in
just-module-creator's ``module-install-local``), so the digest the author compiled is the digest
that runs. Installs made here are recorded in a ledger outside the module directory, which is what
lets a later install replace an earlier iteration without ever touching a registry install.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import polars as pl
from pydantic import BaseModel, Field

from just_dna_pipelines.annotation import hf_modules
from just_dna_pipelines.annotation.annotation_runner import sample_name_from_vcf
from just_dna_pipelines.annotation.hf_modules import (
    ModuleInfo,
    ModuleTable,
    local_module_dir,
    module_kind,
    read_module_provenance,
    scan_module_table,
)
from just_dna_pipelines.annotation.resources import (
    default_sample_aliases,
    get_user_input_dir,
    get_user_output_dir,
)
from just_dna_pipelines import module_config
from just_dna_pipelines.module_config import (
    find_lead_table,
    get_config_path,
    get_immutable_config,
)
from just_dna_pipelines.module_registry import (
    CUSTOM_MODULES_DIR,
    refresh_module_registry,
    register_downloaded_module,
    unregister_custom_module,
)

VCF_SUFFIXES = (".vcf", ".vcf.gz")


class SampleInfo(BaseModel):
    """One genome this installation can annotate."""

    sample_id: str = Field(description="`user/sample`; pass this to start_annotation")
    user: str
    sample: str
    vcf_path: Optional[str] = None
    vcf_size_mb: Optional[float] = None
    normalized: bool = Field(description="A normalized parquet exists (it may still be stale for new QC filters)")
    label: Optional[str] = None
    aliases: list[str] = Field(default_factory=list)
    license: Optional[str] = None
    reference_genome: str = "GRCh38"
    sex: Optional[str] = None
    annotated_modules: list[str] = Field(default_factory=list, description="Modules with output from an earlier run")
    reports: int = 0


class PublicSample(BaseModel):
    """A configured public genome that has not been downloaded into any user directory yet."""

    alias: str = Field(description="Pass this to start_annotation; the worker downloads it on first use")
    label: str
    zenodo_url: str
    filename: str
    license: str
    reference_genome: str
    sex: Optional[str] = None


class SampleListing(BaseModel):
    samples: list[SampleInfo]
    public_not_downloaded: list[PublicSample]
    input_dir: str
    output_dir: str


def _vcf_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if p.is_file() and p.name.endswith(VCF_SUFFIXES))


def _clean_sex(value: str | None) -> Optional[str]:
    return None if value in (None, "", "N/A") else value


def list_samples(user: Optional[str] = None) -> SampleListing:
    """Every VCF under ``data/input/users/*`` (or one user's), plus configured public genomes."""
    input_root = get_user_input_dir()
    output_root = get_user_output_dir()
    defaults = get_immutable_config().default_samples
    users = [user] if user else sorted(p.name for p in input_root.iterdir() if p.is_dir()) if input_root.is_dir() else []

    samples: list[SampleInfo] = []
    matched_defaults: set[str] = set()
    for user_name in users:
        for vcf in _vcf_files(input_root / user_name):
            sample = sample_name_from_vcf(vcf)
            out = output_root / user_name / sample
            modules_dir = out / "modules"
            annotated = sorted(
                p.name[: -len("_weights.parquet")]
                for p in modules_dir.glob("*_weights.parquet")
            ) if modules_dir.is_dir() else []
            default = next(
                (d for d in defaults if d.filename and d.filename == vcf.name),
                None,
            )
            if default is not None:
                matched_defaults.add(default.zenodo_url)
            samples.append(
                SampleInfo(
                    sample_id=f"{user_name}/{sample}",
                    user=user_name,
                    sample=sample,
                    vcf_path=str(vcf),
                    vcf_size_mb=round(vcf.stat().st_size / 1e6, 1),
                    normalized=(out / "user_vcf_normalized.parquet").exists(),
                    label=default.label if default else None,
                    aliases=sorted(default_sample_aliases(default)) if default else [],
                    license=default.license or None if default else None,
                    reference_genome=default.reference_genome if default else "GRCh38",
                    sex=_clean_sex(default.sex) if default else None,
                    annotated_modules=annotated,
                    reports=len(list((out / "reports").glob("*.html"))) if (out / "reports").is_dir() else 0,
                )
            )

    public = [
        PublicSample(
            alias=sorted(default_sample_aliases(d), key=len)[0],
            label=d.label,
            zenodo_url=d.zenodo_url,
            filename=d.filename,
            license=d.license,
            reference_genome=d.reference_genome,
            sex=_clean_sex(d.sex),
        )
        for d in defaults
        if d.zenodo_url not in matched_defaults
    ]
    return SampleListing(
        samples=samples,
        public_not_downloaded=public,
        input_dir=str(input_root),
        output_dir=str(output_root),
    )


def find_sample(sample_id: str) -> Optional[SampleInfo]:
    """The listed sample whose id, bare name, or alias is *sample_id* — ``None`` when not unique."""
    key = sample_id.strip()
    listing = list_samples()
    exact = [s for s in listing.samples if s.sample_id == key]
    if exact:
        return exact[0]
    by_name = [s for s in listing.samples if s.sample == key or key.lower() in s.aliases]
    return by_name[0] if len(by_name) == 1 else None


class ModuleSummary(BaseModel):
    name: str
    title: Optional[str] = None
    lead_table: str
    source: str = Field(description="The configured source this module was discovered from")
    local_dir: Optional[str] = Field(None, description="Set when the module's bytes are on this machine")
    trial_install: bool = Field(False, description="Installed through this MCP server's install_module")
    version: Optional[str] = None
    digest: Optional[str] = None
    weighting: Optional[str] = None


class _Ledger(BaseModel):
    """Modules installed through :func:`install_module`, by name → where they were copied from."""

    installs: dict[str, dict[str, str]] = Field(default_factory=dict)


def lite_mcp_dir() -> Path:
    """This server's own state, beside the working ``modules.yaml`` in the interim directory."""
    return get_config_path().parent / "lite_mcp"


def _ledger_path() -> Path:
    return lite_mcp_dir() / "installs.json"


def _read_ledger() -> _Ledger:
    path = _ledger_path()
    if not path.exists():
        return _Ledger()
    return _Ledger.model_validate_json(path.read_text(encoding="utf-8"))


def _write_ledger(ledger: _Ledger) -> None:
    path = _ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ledger.model_dump_json(indent=2), encoding="utf-8")


def module_infos() -> dict[str, ModuleInfo]:
    """The live discovery map (refreshed in place by installs)."""
    return hf_modules.MODULE_INFOS


def summarize_module(info: ModuleInfo, trial: bool) -> ModuleSummary:
    version, digest, weighting = read_module_provenance(info)
    local = local_module_dir(info)
    meta = module_config.MODULES_CONFIG.module_metadata.get(info.name)
    return ModuleSummary(
        name=info.name,
        title=meta.title if meta is not None and meta.title else None,
        lead_table=info.lead_table,
        source=info.source_url or info.repo_id,
        local_dir=str(local) if local else None,
        trial_install=trial,
        version=version,
        digest=digest,
        weighting=weighting,
    )


def list_modules() -> list[ModuleSummary]:
    ledger = _read_ledger()
    return [summarize_module(info, name in ledger.installs) for name, info in sorted(module_infos().items())]


class InstallResult(BaseModel):
    name: str
    installed_dir: str
    replaced_previous: bool
    lead_table: str
    discovered: bool = Field(description="Discovery found the module after the install; False means it is invisible")
    version: Optional[str] = None
    digest: Optional[str] = None
    lead_rows: Optional[int] = None
    rows_without_coordinates: Optional[int] = Field(
        None, description="Site rows with null chrom (lead rows, or haplotypes rows for a phenotype module) — these can only join on rsid"
    )
    warnings: list[str] = Field(default_factory=list)


class InstallError(ValueError):
    """The install was refused; the message says why and what to do instead."""


def install_module(compiled_dir: Path, name: Optional[str] = None, replace: bool = True) -> InstallResult:
    """Copy a compiled module into the registered-modules dir and make discovery see it.

    Refuses a name that another source already supplies (discovery would keep theirs and silently
    ignore this one), and refuses to overwrite anything it did not install itself — a registry
    install under the same name is someone else's bytes.
    """
    source = Path(compiled_dir).expanduser().resolve()
    if not source.is_dir():
        raise InstallError(f"{source} is not a directory")
    lead = find_lead_table(source)
    if lead is None:
        raise InstallError(
            f"{source} holds no lead parquet (weights.parquet, pharm_variants.parquet, …). "
            "Pass the compile OUTPUT directory, not the spec directory."
        )
    module_name = (name or source.name).strip()
    if not module_name or "/" in module_name or module_name.startswith("."):
        raise InstallError(f"{module_name!r} is not a usable module directory name")

    ledger = _read_ledger()
    target = CUSTOM_MODULES_DIR / module_name
    existing = module_infos().get(module_name)
    if existing is not None and local_module_dir(existing) != target:
        raise InstallError(
            f"{module_name!r} is already supplied by {existing.source_url or existing.repo_id}; discovery "
            "takes the earliest source, so this install would be shadowed. Choose another name."
        )
    replaced = False
    if target.exists():
        if module_name not in ledger.installs:
            raise InstallError(
                f"{target} exists and was not installed through this server (a registry install?). "
                "Refusing to overwrite it; choose another name."
            )
        if not replace:
            raise InstallError(f"{module_name!r} is already installed; pass replace=true to overwrite it")
        shutil.rmtree(target)
        replaced = True

    CUSTOM_MODULES_DIR.mkdir(parents=True, exist_ok=True)
    # Copy, never symlink: unregister does a recursive delete, which through a link deletes the original.
    shutil.copytree(source, target, symlinks=False)
    ledger.installs[module_name] = {
        "source": str(source),
        "installed_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_ledger(ledger)
    register_downloaded_module(target)

    info = module_infos().get(module_name)
    warnings: list[str] = []
    result = InstallResult(
        name=module_name,
        installed_dir=str(target),
        replaced_previous=replaced,
        lead_table=lead,
        discovered=info is not None,
    )
    if info is None:
        warnings.append(
            "Discovery did not pick the module up. A manifest.json whose artifact.files omits the lead "
            "parquet makes a module invisible; recompile rather than hand-assemble the directory."
        )
        return result.model_copy(update={"warnings": warnings})

    version, digest, _ = read_module_provenance(info)
    lead_rows = scan_module_table(module_name, ModuleTable.LEAD, module_info=info).select(pl.len()).collect().item()
    # A phenotype module's lead (diplotypes) names allele pairs and never carries coordinates; the
    # sites the caller matches against the VCF are the haplotypes rows, so that is the table to check.
    is_phenotype = module_kind(info) == "phenotype"
    site_table = ModuleTable.HAPLOTYPES if is_phenotype else ModuleTable.LEAD
    site_label = "haplotype rows" if is_phenotype else "lead rows"
    site_lf = scan_module_table(module_name, site_table, module_info=info)
    schema = site_lf.collect_schema().names()
    counts = site_lf.select(
        pl.len().alias("rows"),
        (pl.col("chrom").is_null().sum() if "chrom" in schema else pl.len()).alias("no_coords"),
    ).collect().row(0, named=True)
    if counts["no_coords"]:
        warnings.append(
            f"{counts['no_coords']} of {counts['rows']} {site_label} have no coordinates; they can only match a "
            "VCF that carries rsIDs in its ID column. Resolve the module (enrich) before relying on a run."
        )
    return result.model_copy(
        update={
            "lead_table": info.lead_table,
            "version": version,
            "digest": digest,
            "lead_rows": lead_rows,
            "rows_without_coordinates": counts["no_coords"],
            "warnings": warnings,
        }
    )


def uninstall_module(name: str) -> bool:
    """Remove a module installed through :func:`install_module`. Refuses anything else."""
    ledger = _read_ledger()
    if name not in ledger.installs:
        raise InstallError(f"{name!r} was not installed through this server; refusing to delete it")
    removed = unregister_custom_module(name)
    ledger.installs.pop(name)
    _write_ledger(ledger)
    return removed


def refresh() -> list[str]:
    return refresh_module_registry()


def module_names() -> list[str]:
    return sorted(module_infos())


def resolve_module_names(requested: list[str]) -> tuple[list[str], list[str]]:
    """``(resolved, unknown)``, case-insensitive, order kept, duplicates dropped."""
    by_lower = {n.lower(): n for n in module_infos()}
    resolved: list[str] = []
    unknown: list[str] = []
    for raw in requested:
        hit = by_lower.get(raw.strip().lower())
        if hit is None:
            unknown.append(raw)
        elif hit not in resolved:
            resolved.append(hit)
    return resolved, unknown


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)
