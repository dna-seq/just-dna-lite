"""
Publish a compiled module to the HuggingFace annotator collection.

Uploads the compiled artifacts (weights/annotations/studies.parquet + manifest.json, and a logo if
present) to ``datasets/<collection>/data/<name>/`` in a single commit, matching the layout the
discovery machinery scans (``annotation.hf_modules``). Requires a HuggingFace token with write access
to the collection (``hf auth login`` or the ``HF_TOKEN`` env var).
"""

from pathlib import Path
from typing import Optional

from huggingface_hub import HfApi, get_token
from pydantic import BaseModel

from just_dna_pipelines.module_config import MODULES_CONFIG

# weights/annotations/studies are what discovery needs; manifest.json + logo are additive.
_REQUIRED = ("weights.parquet", "annotations.parquet", "studies.parquet")
_ALLOW_PATTERNS = [*_REQUIRED, "manifest.json", "logo.png", "logo.jpg"]


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


def plan_publish(module_dir: Path, name: str, repo_id: Optional[str] = None) -> PublishPlan:
    """Resolve the upload plan and validate the compiled artifacts are present."""
    repo_id = repo_id or default_collection_repo()
    present = [f for f in _ALLOW_PATTERNS if (module_dir / f).exists()]
    missing = [f for f in _REQUIRED if f not in present]
    if missing:
        raise FileNotFoundError(
            f"{name}: missing compiled artifact(s) {missing} in {module_dir} — "
            f"run `pipelines v1-port port --module {name} --compile` first"
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
