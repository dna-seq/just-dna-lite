"""The separate HTML report of one prediction run, rendered through ``report_environment()``.

It is its own page, not a section of the annotation report: a model's prediction is a different kind
of statement from a curated module finding, and the two must never read as one. Results come first
(the ranked table, then what could not be assessed and why), then *How to read this*, then a folded
*Technical details* block with the model, its pinned revision, the provider that ran it and the
licence.
"""

from datetime import datetime
from pathlib import Path

import polars as pl
from pydantic import BaseModel

from just_dna_pipelines.annotation.analytics import umami_script_tag
from just_dna_pipelines.annotation.report_logic import dbsnp_url, report_environment
from just_dna_pipelines.predictions.models import PredictionModel
from just_dna_pipelines.predictions.run_config import VARIANT_SET_REGION
from just_dna_pipelines.predictions.variants import REASON_OVER_CAP_PREFIX, STATUS_NOT_ASSESSED, STATUS_SCORED

REPORT_TEMPLATE = "variant_effects_report.html.j2"


class PredictionRun(BaseModel):
    """What one run did, written beside its parquet as JSON and shown in the report's technical block."""

    model_id: str
    user_name: str
    sample_name: str
    variant_set: str
    region: str | None = None
    max_variants: int
    provider: str
    model_load_seconds: float
    scoring_seconds: float
    reference_fasta: str
    splice_span_bp: int
    track_bin_bp: int
    top_tracks: int
    candidates: int
    scored: int
    not_assessed: int
    generated_at: str
    parquet_path: str


def report_filename(model: PredictionModel, generated_at: datetime) -> str:
    """``krongenome_variant_effects_<timestamp>.html``; the Reports tab globs ``reports/*.html``."""
    return f"{model.output_stem}_{generated_at.strftime('%Y%m%d_%H%M%S')}.html"


def _variant_label(row: dict) -> str:
    return f"{row['chrom']}:{row['pos']:,} {row['ref']}>{row['alt']}"


# The graph's splice channel names (onnx_meta.json), as a reader would say them.
SPLICE_CHANNEL_LABELS: dict[str, str] = {
    "donor_plus": "donor site, + strand",
    "acceptor_plus": "acceptor site, + strand",
    "donor_minus": "donor site, − strand",
    "acceptor_minus": "acceptor site, − strand",
}


def _signed(value: float | None, digits: int = 3) -> str:
    return "" if value is None else f"{value:+.{digits}f}"


def _view_row(row: dict) -> dict:
    tracks = row.get("top_tracks") or []
    return {
        "rsid": row["rsid"],
        "rsid_url": dbsnp_url(row["rsid"]),
        "gene": row["gene"],
        "variant": _variant_label(row),
        "genotype": row["genotype"],
        "modules": row["modules"],
        "splice_delta": None if row["splice_delta"] is None else f"{row['splice_delta']:.3f}",
        "splice_change": _signed(row["splice_change"]),
        "splice_channel": SPLICE_CHANNEL_LABELS.get(row["splice_channel"], row["splice_channel"]),
        "splice_offset_bp": row["splice_offset_bp"],
        "dnase_delta": _signed(row["dnase_delta"]),
        "dnase_biosample": row["dnase_biosample"],
        "dnase_track": row["dnase_track"],
        "top_tracks": [{"track": t["track"], "delta": _signed(t["delta"])} for t in tracks],
        "reason": row["reason"],
    }


def variant_set_description(run: PredictionRun) -> str:
    """One sentence on which variants this run looked at."""
    if run.variant_set == VARIANT_SET_REGION:
        return f"Every variant your file lists in the region {run.region}."
    return "The variants of yours that the annotation modules you ran found a match for."


def build_report_context(results: pl.DataFrame, run: PredictionRun, model: PredictionModel) -> dict:
    """Everything the template reads. ``results`` is the run's parquet, already ranked."""
    scored = [_view_row(r) for r in results.filter(pl.col("status") == STATUS_SCORED).to_dicts()]
    skipped = results.filter(pl.col("status") == STATUS_NOT_ASSESSED)
    past_cap = pl.col("reason").str.starts_with(REASON_OVER_CAP_PREFIX)
    not_assessed = [_view_row(r) for r in skipped.filter(~past_cap).to_dicts()]
    over_cap = [_view_row(r) for r in skipped.filter(past_cap).to_dicts()]
    return {
        "report_title": f"Predicted variant effects: {model.title}",
        "sample_name": run.sample_name,
        "model": model,
        "run": run,
        "variant_set_text": variant_set_description(run),
        "scored": scored,
        "not_assessed": not_assessed,
        "over_cap": over_cap,
        "reference_fasta_name": Path(run.reference_fasta).name,
        "umami_script_tag": umami_script_tag(),
    }


def render_prediction_report(results: pl.DataFrame, run: PredictionRun, model: PredictionModel, output_path: Path) -> Path:
    """Render the report to ``output_path`` (directories created) and return it."""
    html = report_environment().get_template(REPORT_TEMPLATE).render(**build_report_context(results, run, model))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
