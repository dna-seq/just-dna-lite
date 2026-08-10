"""
Publish a compiled module to the HuggingFace annotator collection.

Uploads the compiled artifacts (weights/annotations/studies.parquet + manifest.json, and a logo if
present) to ``datasets/<collection>/data/<name>/`` in a single commit, matching the layout the
discovery machinery scans (``annotation.hf_modules``). Requires a HuggingFace token with write access
to the collection (``hf auth login`` or the ``HF_TOKEN`` env var).

**Canonical home (0.5+):** ``just_dna_enricher.upload`` / ``just-dna-enricher upload``
(``pip install 'just-dna-enricher[dev]'``). This module stays until pipelines adopts the enricher
tier and then becomes a thin modules.yaml-aware re-export.
"""

from pathlib import Path
from typing import Optional

from huggingface_hub import HfApi, get_token
from pydantic import BaseModel

from just_dna_pipelines.module_config import MODULES_CONFIG

# weights/annotations/studies are what discovery needs; manifest.json + logo are additive.
_REQUIRED = ("weights.parquet", "annotations.parquet", "studies.parquet")

# The 0.4/0.5 side tables a compiled module may also carry. Additive: HuggingFace discovery ignores
# what it does not know, and shipping them keeps the uploaded module a complete artifact.
#
# Ordered so the tables that can *lead* a module come first — the refusal below names the first one
# present, and "led by sources.parquet" is not a useful thing to tell an author.
_OPTIONAL_TABLES = (
    "pharm_variants.parquet", "diplotypes.parquet", "haplotypes.parquet", "pgs.parquet",
    "copynumbers.parquet", "heteroplasmy.parquet", "repeat_alleles.parquet",
    "activity_phenotype.parquet", "allele_function.parquet",
    "sources.parquet", "literature.parquet", "frequencies.parquet", "gene_metrics.parquet",
)
_ALLOW_PATTERNS = [*_REQUIRED, *_OPTIONAL_TABLES, "manifest.json", "logo.png", "logo.jpg"]


class PublishPlan(BaseModel):
    """What a publish would upload (also the dry-run result)."""

    module: str
    repo_id: str
    path_in_repo: str
    files: list[str]


def default_collection_repo() -> str:
    """The first HuggingFace collection source in modules.yaml (the annotator collection)."""
    for source in MODULES_CONFIG.sources:
        if source.is_hf and source.hf_repo_id:
            return source.hf_repo_id
    return "just-dna-seq/annotators"


def resolve_module_dir(module: str, out_root: Path) -> tuple[Path, str]:
    """Accept either a compiled module **directory** or a bare name under ``out_root``.

    Returns ``(module_dir, name)``, where the name is the directory's own basename — that is what
    the module is called in the collection, so a path and the equivalent name publish identically.

    Taking only a name meant a path was silently joined onto the output root, producing
    ``data/interim/v1_port/data/interim/v1_port/coronary`` and then an error advising a rebuild
    command that could not work. A publish route should accept the thing you are looking at.
    """
    candidate = Path(module)
    if candidate.is_dir():
        return candidate, candidate.name
    # Anything path-shaped that does not exist is a mistyped path, not a module name — say so
    # rather than searching for it under the output root and reporting a different absence.
    if len(candidate.parts) > 1:
        raise FileNotFoundError(f"no such module directory: {candidate}")
    return out_root / module, module


def plan_publish(module_dir: Path, name: str, repo_id: Optional[str] = None) -> PublishPlan:
    """Resolve the upload plan and validate the compiled artifacts are present."""
    repo_id = repo_id or default_collection_repo()
    present = [f for f in _ALLOW_PATTERNS if (module_dir / f).exists()]
    missing = [f for f in _REQUIRED if f not in present]
    if missing:
        # A module led by a 0.4 table (pharm_variants, diplotypes, pgs, …) compiles fine and has no
        # weights.parquet — but `annotation.hf_modules` probes for exactly that file to decide a
        # directory *is* a module, so uploading one here would put files where the app cannot see
        # them. The registry has no such constraint, so say which route the module has.
        led_by = [f for f in _OPTIONAL_TABLES if f in present]
        if led_by and "weights.parquet" in missing:
            raise FileNotFoundError(
                f"{name}: no weights.parquet — this module is led by {led_by[0]}, and HuggingFace "
                f"discovery (annotation.hf_modules) keys on weights.parquet, so the upload would be "
                f"invisible to the app. Publish it to the registry instead: "
                f"`pipelines marketplace publish just-dna-seq {name} <version> {module_dir}`."
            )
        if not module_dir.is_dir():
            raise FileNotFoundError(f"{name}: no such module directory: {module_dir}")
        raise FileNotFoundError(
            f"{name}: missing compiled artifact(s) {missing} in {module_dir} — this uploads the "
            f"compiled parquet, so compile the spec first — in place, since that is where the "
            f"upload reads from: `pipelines module compile {module_dir} --output {module_dir}`"
        )
    return PublishPlan(
        module=name, repo_id=repo_id, path_in_repo=f"data/{name}", files=present
    )


def publish_module(
    module_dir: Path,
    name: str,
    repo_id: Optional[str] = None,
    token: Optional[str] = None,
) -> PublishPlan:
    """Upload the compiled module to the HF collection. Raises PermissionError if no token."""
    plan = plan_publish(module_dir, name, repo_id)
    token = token or get_token()
    if not token:
        raise PermissionError(
            "No HuggingFace token found. Authenticate first (e.g. `hf auth login`, or set HF_TOKEN) "
            f"with write access to {plan.repo_id}."
        )
    api = HfApi(token=token)
    api.upload_folder(
        folder_path=str(module_dir),
        path_in_repo=plan.path_in_repo,
        repo_id=plan.repo_id,
        repo_type="dataset",
        allow_patterns=_ALLOW_PATTERNS,
        commit_message=f"Add {name} module (ported from Generation-I dna-seq/just_{name})",
    )
    return plan
