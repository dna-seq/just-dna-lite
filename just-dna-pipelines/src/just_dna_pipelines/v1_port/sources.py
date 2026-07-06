"""
v1 module source registry and data-file fetching.

Each portable Gen-I module maps to a ``just_*`` repo in the ``dna-seq`` GitHub org and a data file
inside it. Files are fetched with fsspec's ``github`` filesystem (default branch, no auth needed for
public repos) — never ``snapshot_download``. Display metadata (title/description/icon/color) is
pulled from the repo's canonical ``modules.yaml`` overrides via ``module_config.get_module_meta`` so
the ported spec matches what the app already shows for these modules.
"""

from pathlib import Path
from typing import Literal, Optional

import fsspec
from pydantic import BaseModel, Field

from just_dna_pipelines.module_config import get_module_meta

AdapterKind = Literal["coronary", "three_table", "longevitymap", "superhuman"]

_GITHUB_ORG = "dna-seq"


class V1Module(BaseModel):
    """One portable Gen-I module: where its curated data lives and how to read it."""

    name: str = Field(description="Canonical module name (machine name, matches modules.yaml key)")
    repo: str = Field(description="GitHub repo in the dna-seq org, e.g. just_coronary")
    data_path: str = Field(description="Path to the data file inside the repo")
    adapter: AdapterKind = Field(description="Which adapter reads this module's SQLite shape")
    has_studies_table: bool = Field(
        default=False, description="three_table modules: whether a dedicated studies table exists"
    )


# The six variant-backed modules. cardio/cancer/pathogenic/drugs/lnewco are documented in GAPS.md
# rather than registered here — they don't carry per-variant curated weights.
REGISTRY: dict[str, V1Module] = {
    "coronary": V1Module(
        name="coronary", repo="just_coronary", data_path="data/coronary.sqlite", adapter="coronary"
    ),
    "thrombophilia": V1Module(
        name="thrombophilia", repo="just_thrombophilia",
        data_path="data/thrombophilia.sqlite", adapter="three_table", has_studies_table=True,
    ),
    "lipidmetabolism": V1Module(
        name="lipidmetabolism", repo="just_lipidmetabolism",
        data_path="data/lipid_metabolism.sqlite", adapter="three_table", has_studies_table=True,
    ),
    "vo2max": V1Module(
        name="vo2max", repo="just_vo2max",
        data_path="data/vo2max.sqlite", adapter="three_table", has_studies_table=False,
    ),
    "longevitymap": V1Module(
        name="longevitymap", repo="just_longevitymap",
        data_path="data/longevitymap.sqlite", adapter="longevitymap",
    ),
    "superhuman": V1Module(
        name="superhuman", repo="just_superhuman",
        data_path="data/superhuman.sqlite", adapter="superhuman",
    ),
}


def fetch_data_file(module: V1Module, cache_dir: Path) -> Path:
    """Download a module's curated data file into ``cache_dir`` (idempotent). Returns local path."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    local_path = cache_dir / f"{module.repo}__{Path(module.data_path).name}"
    if local_path.exists() and local_path.stat().st_size > 0:
        return local_path
    fs = fsspec.filesystem("github", org=_GITHUB_ORG, repo=module.repo)
    fs.get(module.data_path, str(local_path))
    return local_path


def display_meta(name: str) -> dict[str, str]:
    """Canonical title/description/report_title/icon/color for a module (YAML override or default)."""
    meta = get_module_meta(name)
    return {
        "title": meta.title or name.replace("_", " ").title(),
        "description": meta.description or f"Annotation module: {name}",
        "report_title": meta.report_title or (meta.title or name),
        "icon": meta.icon,
        "color": meta.color,
    }
