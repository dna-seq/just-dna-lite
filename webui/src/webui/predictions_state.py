"""State behind the Predictions tab: pick a model and a variant set, start a prediction run.

The run itself is ``predict_variant_effects_job`` and goes through the same path as Start Analysis:
the run is created in Dagster, offered to the daemon, and on refusal handed to a spawned compute
child (``UploadState.execute_job_with_run_discovery``). Nothing here touches Polars, ONNX Runtime or a
job's work in the web process. Run tracking (history, polling, the per-file running state) is
``UploadState``'s, so a prediction run blocks a second run on the same file exactly like an analysis.
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Any

import reflex as rx
from just_dna_pipelines.annotation.resources import get_user_output_dir
from just_dna_pipelines.module_config import is_immutable_mode
from just_dna_pipelines.predictions.models import DEFAULT_PREDICTION_MODEL, PREDICTION_MODELS
from just_dna_pipelines.predictions.run_config import (
    DEFAULT_MAX_VARIANTS,
    MAX_REGION_BP,
    PREDICTION_JOB,
    VARIANT_SET_ANNOTATED,
    VARIANT_SET_REGION,
    RegionError,
    parse_region,
    prediction_run_config,
)

from webui.dagster_env import get_dagster_instance
from webui.state import AuthState, UploadState, defs, get_dagster_web_url

# A run is scored variant by variant at about 1.5 minutes each on a CPU; 200 is already hours.
MAX_VARIANTS_LIMIT = 200
_PLAIN_NUMBER = re.compile(r"[0-9]+(\.[0-9]*)?")


def region_problem(variant_set: str, region: str) -> str:
    """Why the region box cannot be run as it is, or "" when it can (or is not in use)."""
    if variant_set != VARIANT_SET_REGION:
        return ""
    if not region.strip():
        return "Enter a region such as 7:117,559,000-117,560,000."
    try:
        parse_region(region)
    except RegionError as exc:
        return str(exc)
    return ""


def clamp_max_variants(value: str | float) -> int:
    """The cap typed into the form, as an int between 1 and ``MAX_VARIANTS_LIMIT``.

    A number input reports a float, or the raw text while it is being edited; anything that is not a
    plain non-negative number falls back to the default.
    """
    text = str(value).strip()
    number = int(float(text)) if _PLAIN_NUMBER.fullmatch(text) else DEFAULT_MAX_VARIANTS
    return max(1, min(number, MAX_VARIANTS_LIMIT))


def model_option_rows() -> list[dict[str, str]]:
    """One card per registered model, in registry order."""
    return [
        {
            "id": m.id,
            "title": m.title,
            "summary": m.summary,
            "licence": m.licence,
            "card_url": m.model_card_url,
            "author": m.author,
        }
        for m in PREDICTION_MODELS.values()
    ]


class PredictionState(rx.State):
    """Form state of the Predictions tab. Per session; the running state stays per file."""

    model_id: str = DEFAULT_PREDICTION_MODEL
    variant_set: str = VARIANT_SET_ANNOTATED
    region: str = ""
    max_variants: int = DEFAULT_MAX_VARIANTS

    @rx.var
    def model_options(self) -> list[dict[str, str]]:
        return model_option_rows()

    @rx.var
    def selected_model(self) -> dict[str, str]:
        model = PREDICTION_MODELS.get(self.model_id) or PREDICTION_MODELS[DEFAULT_PREDICTION_MODEL]
        return {
            "id": model.id,
            "title": model.title,
            "summary": model.summary,
            "licence": model.licence,
            "licence_url": model.licence_url,
            "card_url": model.model_card_url,
            "author": model.author,
            "output_stem": model.output_stem,
            "research_note": model.research_note,
        }

    @rx.var
    def region_error(self) -> str:
        return region_problem(self.variant_set, self.region)

    @rx.var
    def uses_region(self) -> bool:
        return self.variant_set == VARIANT_SET_REGION

    @rx.var
    def max_region_text(self) -> str:
        return f"{MAX_REGION_BP:,}"

    @rx.event
    def set_model_id(self, value: str) -> None:
        if value in PREDICTION_MODELS:
            self.model_id = value

    @rx.event
    def set_variant_set(self, value: str | list[str]) -> None:
        # The segmented control reports a list only in multiple-selection mode, which this one is not.
        choice = value[0] if isinstance(value, list) and value else value
        if choice in (VARIANT_SET_ANNOTATED, VARIANT_SET_REGION):
            self.variant_set = choice

    @rx.event
    def set_region(self, value: str) -> None:
        self.region = value

    @rx.event
    def set_max_variants(self, value: float | str) -> None:
        self.max_variants = clamp_max_variants(value)

    @rx.event
    async def start_prediction_run(self):
        """Create and submit a prediction run for the selected sample (same path as Start Analysis)."""
        upload = await self.get_state(UploadState)
        if not upload.selected_file:
            yield rx.toast.error("Please select a file")
            return
        if is_immutable_mode():
            yield rx.toast.error("Predictions are turned off in this public demo.")
            return
        if upload.selected_build_unsupported:
            yield rx.toast.error(upload.selected_build_unsupported)
            return
        if upload.selected_file_is_running:
            yield rx.toast.warning("A run is already in progress for this sample.")
            return
        if self.region_error:
            yield rx.toast.error(self.region_error)
            return
        if not upload.safe_user_id:
            auth_state = await self.get_state(AuthState)
            upload.safe_user_id = upload._get_safe_user_id(auth_state.user_email)

        sample_name = upload.selected_file.replace(".vcf.gz", "").replace(".vcf", "")
        partition_key = f"{upload.safe_user_id}/{sample_name}"
        sample_dir = get_user_output_dir() / partition_key
        if not (sample_dir / "user_vcf_normalized.parquet").is_file():
            yield rx.toast.error("This sample is not prepared yet. Wait for its upload to finish normalizing.")
            return
        if self.variant_set == VARIANT_SET_ANNOTATED and not (sample_dir / "modules" / "manifest.json").is_file():
            yield rx.toast.error("No analysis found for this sample. Run an analysis first, or choose a region.")
            return

        model = PREDICTION_MODELS[self.model_id]
        run_config = prediction_run_config(
            model_id=model.id,
            variant_set=self.variant_set,
            region=self.region.strip() if self.variant_set == VARIANT_SET_REGION else None,
            max_variants=self.max_variants,
        )
        instance = get_dagster_instance()
        run = instance.create_run_for_job(
            job_def=defs.resolve_job_def(PREDICTION_JOB),
            run_config=run_config,
            tags={"dagster/partition": partition_key, "source": "webui"},
        )
        run_id = run.run_id
        run_info: dict[str, Any] = {
            "run_id": run_id,
            "filename": upload.selected_file,
            "sample_name": sample_name,
            "modules": [model.title],
            "include_ensembl": False,
            "status": "QUEUED",
            "started_at": datetime.now().isoformat(),
            "ended_at": None,
            "output_path": None,
            "error": None,
            "dagster_url": f"{get_dagster_web_url()}/runs/{run_id}",
        }
        upload.runs = [run_info] + upload.runs
        upload.active_run_id = run_id
        upload.polling_active = True
        upload.run_logs = []
        upload._add_log(f"Prediction run {run_id} with {model.title} ({self.variant_set})")
        yield

        submitted, error = upload._try_submit_to_daemon(instance, run_id)
        if submitted:
            yield rx.toast.info(f"Prediction started for {sample_name}")
            return
        upload._add_log(f"Daemon submission failed: {error}")
        instance.delete_run(run_id)
        upload._inproc_discover_partition = partition_key
        upload._inproc_discover_since = time.time()
        upload._inproc_original_run_id = run_id
        upload.runs = [{**r, "status": "RUNNING"} if r["run_id"] == run_id else r for r in upload.runs]
        yield rx.toast.info(f"Prediction running for {sample_name}; this takes several minutes.")
        yield UploadState.execute_job_with_run_discovery(PREDICTION_JOB, run_config, partition_key, run_id, sample_name)
