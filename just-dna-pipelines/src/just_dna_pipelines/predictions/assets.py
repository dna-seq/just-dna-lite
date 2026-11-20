"""Dagster asset and job for genome prediction models on one sample.

``user_variant_effect_predictions`` reads the sample's ``user_vcf_normalized`` parquet (never the raw
VCF), scores the chosen variant set with the chosen model, and writes three files:

- ``<sample>/<model.output_stem>.parquet``: one row per variant and allele, scored or not assessed;
- ``<sample>/<model.output_stem>.json``: what the run did (``report.PredictionRun``);
- ``<sample>/reports/<model.output_stem>_<timestamp>.html``: the separate report.

``predict_variant_effects_job`` selects only this asset, so its run config names only it
(``prediction_run_config``) and the existing normalized parquet is loaded by the IO manager.
"""

import time
from datetime import datetime
from pathlib import Path

from dagster import (
    AssetExecutionContext,
    AssetIn,
    AssetSelection,
    Config,
    MetadataValue,
    Output,
    asset,
    define_asset_job,
)
from eliot import start_action

from just_dna_pipelines.annotation.assets import user_vcf_partitions
from just_dna_pipelines.annotation.resources import get_user_output_dir
from just_dna_pipelines.annotation.utils import resource_summary_hook
from just_dna_pipelines.predictions.download import ensure_model_files
from just_dna_pipelines.predictions.models import DEFAULT_PREDICTION_MODEL, get_prediction_model
from just_dna_pipelines.predictions.reference import ReferenceGenome, resolve_reference_fasta
from just_dna_pipelines.predictions.report import PredictionRun, render_prediction_report, report_filename
from just_dna_pipelines.predictions.run_config import (
    DEFAULT_MAX_VARIANTS,
    PREDICTION_ASSET,
    PREDICTION_JOB,
    VARIANT_SET_ANNOTATED,
    VARIANT_SET_REGION,
    VARIANT_SETS,
)
from just_dna_pipelines.predictions.scoring import (
    SPLICE_SPAN_BP,
    TOP_TRACKS,
    TRACK_BIN_BP,
    ModelSession,
    TrackChannels,
    rank_results,
    score_variants,
)
from just_dna_pipelines.predictions.variants import (
    STATUS_NOT_ASSESSED,
    STATUS_SCORED,
    annotated_variants,
    classify_variants,
    region_variants,
)
from just_dna_pipelines.runtime import resource_tracker


class VariantEffectConfig(Config):
    """Which model, which variants, how many."""

    model_id: str = DEFAULT_PREDICTION_MODEL
    variant_set: str = VARIANT_SET_ANNOTATED  # "annotated" | "region"
    region: str | None = None  # "chrom:start-end", 1-based inclusive, at most 1 Mb
    max_variants: int = DEFAULT_MAX_VARIANTS  # 0 or less: no cap
    user_name: str | None = None
    sample_name: str | None = None


@asset(
    name=PREDICTION_ASSET,
    description="Per-variant effects predicted by a sequence model (reference vs alternate window), "
                "with a separate HTML report.",
    compute_kind="onnx",
    group_name="user_predictions",
    partitions_def=user_vcf_partitions,
    io_manager_key="user_asset_io_manager",
    ins={"user_vcf_normalized": AssetIn()},
    op_tags={"dagster/concurrency_key": "variant_effect_prediction"},
    metadata={"partition_type": "user", "output_format": "parquet", "storage": "output"},
)
def user_variant_effect_predictions(
    context: AssetExecutionContext,
    user_vcf_normalized: Path,
    config: VariantEffectConfig,
) -> Output[Path]:
    partition_key = context.partition_key
    user_name, _, sample_name = partition_key.partition("/")
    user_name = config.user_name or user_name
    sample_name = config.sample_name or sample_name
    if config.variant_set not in VARIANT_SETS:
        raise ValueError(f"Unknown variant set {config.variant_set!r}; use one of {VARIANT_SETS}.")
    model = get_prediction_model(config.model_id)
    sample_dir = get_user_output_dir() / partition_key

    with resource_tracker("Predict variant effects", context=context), start_action(
        action_type="predict_variant_effects", partition=partition_key, model=model.id
    ):
        if config.variant_set == VARIANT_SET_REGION:
            if not config.region:
                raise ValueError("The region variant set needs a region (chrom:start-end).")
            variants = region_variants(user_vcf_normalized, config.region)
        else:
            modules_dir = sample_dir / "modules"
            if not (modules_dir / "manifest.json").is_file():
                raise FileNotFoundError(
                    f"No annotation run found for {partition_key} ({modules_dir}). Run an analysis with "
                    "at least one module first, or choose a region."
                )
            variants = annotated_variants(modules_dir)
        classified = classify_variants(variants, config.max_variants)
        candidates = classified.filter(classified["status"].is_null()).height
        context.log.info(f"{variants.height} variant rows selected, {candidates} to score with {model.title}")

        model_dir = ensure_model_files(model)
        fasta = resolve_reference_fasta()
        reference = ReferenceGenome(fasta)
        session = ModelSession(model_dir / model.onnx_file)
        scoring_started = time.perf_counter()
        results = rank_results(
            score_variants(
                classified,
                reference,
                session,
                model,
                TrackChannels.from_model_dir(model_dir),
                on_progress=lambda done, total: context.log.info(f"Scored {done}/{total}"),
            )
        )
        reference.close()
        context.log.info(f"Model load {session.load_seconds:.0f} s on {session.provider}")
        scoring_seconds = time.perf_counter() - scoring_started - session.load_seconds

        sample_dir.mkdir(parents=True, exist_ok=True)
        parquet_path = sample_dir / f"{model.output_stem}.parquet"
        results.write_parquet(parquet_path)
        generated_at = datetime.now().astimezone()
        run = PredictionRun(
            model_id=model.id,
            user_name=user_name,
            sample_name=sample_name,
            variant_set=config.variant_set,
            region=config.region,
            max_variants=config.max_variants,
            provider=session.provider,
            model_load_seconds=session.load_seconds,
            scoring_seconds=scoring_seconds,
            reference_fasta=str(fasta),
            splice_span_bp=SPLICE_SPAN_BP,
            track_bin_bp=TRACK_BIN_BP,
            top_tracks=TOP_TRACKS,
            candidates=candidates,
            scored=results.filter(results["status"] == STATUS_SCORED).height,
            not_assessed=results.filter(results["status"] == STATUS_NOT_ASSESSED).height,
            generated_at=generated_at.strftime("%Y-%m-%d %H:%M %Z"),
            parquet_path=str(parquet_path),
        )
        (sample_dir / f"{model.output_stem}.json").write_text(run.model_dump_json(indent=2), encoding="utf-8")
        report_path = render_prediction_report(
            results, run, model, sample_dir / "reports" / report_filename(model, generated_at)
        )

    return Output(
        parquet_path,
        metadata={
            "partition_key": MetadataValue.text(partition_key),
            "model": MetadataValue.text(model.id),
            "model_revision": MetadataValue.text(model.revision),
            "provider": MetadataValue.text(run.provider),
            "variant_set": MetadataValue.text(run.variant_set),
            "scored": MetadataValue.int(run.scored),
            "not_assessed": MetadataValue.int(run.not_assessed),
            "report_path": MetadataValue.path(str(report_path)),
            "parquet_path": MetadataValue.path(str(parquet_path)),
        },
    )


predict_variant_effects_job = define_asset_job(
    name=PREDICTION_JOB,
    selection=AssetSelection.assets(PREDICTION_ASSET),
    description="Score a sample's variants with a genome prediction model and write a separate report.",
    tags={"prediction": "variant_effects", "multi-user": "true"},
    hooks={resource_summary_hook},
)
