"""What a prediction run is asked to do, importable without module discovery or Dagster definitions.

The CLI and the web UI build run config and check a region here before touching the pipeline, so
this module imports nothing heavier than the model list.
"""

import re
from typing import Any

from just_dna_format.vrs import normalize_chrom

from just_dna_pipelines.predictions.models import DEFAULT_PREDICTION_MODEL

PREDICTION_ASSET = "user_variant_effect_predictions"
REFERENCE_ASSET = "grch38_reference_fasta"
PREDICTION_JOB = "predict_variant_effects_job"

VARIANT_SET_ANNOTATED = "annotated"
VARIANT_SET_REGION = "region"
VARIANT_SETS: tuple[str, ...] = (VARIANT_SET_ANNOTATED, VARIANT_SET_REGION)

# Each scored variant is two graph calls over 131,072-base windows: 68-96 s on the 16-core desktop at
# nice 19 (quiet to loaded), after a model load of seconds once the optimized graph is saved. Five
# keeps a default run near ten minutes; the UI and CLI raise it.
DEFAULT_MAX_VARIANTS = 5

# Largest region a run accepts. A region is scored variant by variant, so its size bounds the work.
MAX_REGION_BP = 1_000_000

_REGION = re.compile(r"^\s*([^:\s]+)\s*:\s*([\d,_]+)\s*-\s*([\d,_]+)\s*$")


class RegionError(ValueError):
    """A region string that cannot be read or is larger than ``MAX_REGION_BP``."""


def parse_region(region: str) -> tuple[str, int, int]:
    """``"chr7:117,559,000-117,560,000"`` → ``("7", 117559000, 117560000)``, 1-based inclusive."""
    match = _REGION.match(region)
    if match is None:
        raise RegionError(
            f"Region {region!r} is not of the form chrom:start-end (for example 7:117559000-117560000)."
        )
    chrom = normalize_chrom(match.group(1))
    start = int(re.sub(r"[,_]", "", match.group(2)))
    end = int(re.sub(r"[,_]", "", match.group(3)))
    if chrom is None:
        raise RegionError(f"Region {region!r} names no chromosome.")
    if start < 1 or end < start:
        raise RegionError(f"Region {region!r} must have 1 <= start <= end.")
    if end - start + 1 > MAX_REGION_BP:
        raise RegionError(f"Region {region!r} spans {end - start + 1:,} bases; the limit is {MAX_REGION_BP:,}.")
    return chrom, start, end


def prediction_run_config(
    model_id: str = DEFAULT_PREDICTION_MODEL,
    variant_set: str = VARIANT_SET_ANNOTATED,
    region: str | None = None,
    max_variants: int = DEFAULT_MAX_VARIANTS,
) -> dict[str, Any]:
    """The ``ops``-keyed run config of ``predict_variant_effects_job``; it names only that job's asset."""
    config: dict[str, Any] = {"model_id": model_id, "variant_set": variant_set, "max_variants": max_variants}
    if region:
        config["region"] = region
    return {"ops": {PREDICTION_ASSET: {"config": config}}}
