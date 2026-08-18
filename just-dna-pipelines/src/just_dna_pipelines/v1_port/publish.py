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

from just_dna_compiler.compiler import ARTIFACT_PARQUETS, LEAD_PARQUETS

from just_dna_pipelines.module_config import MODULES_CONFIG

# A module must carry one of the lead families — that is exactly what discovery probes for. The rest
# are additive: discovery ignores what it does not know, and shipping them keeps the uploaded module
# a complete artifact.
#
# **Both tuples are imported from the compiler, and a hand-kept copy here is a publish-time data
# loss, not an untidiness.** `ARTIFACT_PARQUETS` is the list `artifact.digest` is a Merkle root over,
# so a name missing from the allowlist is a parquet the manifest *attests* and the upload never
# sends: the published digest then cannot be reproduced from what arrived. Upstream measured exactly
# this on its own hand-kept allowlist over sixteen reference modules — seven refused outright and
# eight of the remaining nine published a manifest attesting files that were never uploaded, fifteen
# of sixteen wrong, with `sources.parquet` in the dropped set every time it existed (so the module
# arrived carrying no licence terms at all). Deriving it means a new table family reaches the
# publisher in the same release that adds it; 0.6 added three (`gene_validity`,
# `clinical_assertions`, `gwas_effects`) and this list named none of them.
_LEAD_PARQUETS = LEAD_PARQUETS
_ALLOW_PATTERNS = [*ARTIFACT_PARQUETS, "manifest.json", "logo.png", "logo.jpg"]

# What a weights-led module is expected to carry. A missing side table here is worth stopping for —
# it means an interrupted or partial compile — but only for the weights-led shape, since a
# pharm_variants-led module legitimately has neither annotations nor studies.
_EXPECTED_WITH_WEIGHTS = ("annotations.parquet", "studies.parquet")


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

    # The lead table is the whole requirement: it is exactly what discovery probes for, so a module
    # led by a 0.4 family (pharm_variants, diplotypes, pgs, …) publishes here like any other.
    lead = next((f for f in _LEAD_PARQUETS if f in present), None)
    if lead is None:
        if not module_dir.is_dir():
            raise FileNotFoundError(f"{name}: no such module directory: {module_dir}")
        raise FileNotFoundError(
            f"{name}: no compiled table in {module_dir} — expected one of {list(_LEAD_PARQUETS)}. "
            f"This uploads the compiled parquet, so compile the spec first — in place, since that "
            f"is where the upload reads from: "
            f"`pipelines module compile {module_dir} --output {module_dir}`"
        )

    if lead == "weights.parquet":
        missing = [f for f in _EXPECTED_WITH_WEIGHTS if f not in present]
        if missing:
            raise FileNotFoundError(
                f"{name}: missing compiled artifact(s) {missing} in {module_dir} — a weights-led "
                f"module should carry these, so this looks like a partial compile. Rebuild with "
                f"`pipelines module compile {module_dir} --output {module_dir}`"
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
