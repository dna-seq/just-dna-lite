"""Per-variant effect scores from a sequence-to-function ONNX graph: reference window vs alternate.

For each single-base substitution the model reads two windows of ``model.window`` bases centred on
the variant (index ``window // 2``): the reference sequence, and the same sequence with the
alternate base at the centre. Each goes through the graph as a call of one row: a batch of two took
5.7 GB at peak against 3.3 GB for one, for about 7% less time (measured on the 16-core desktop), and
the app shares that machine's memory. The scores compare the two outputs near the variant:

- **splice delta**: the largest absolute change in any of the four splice-site probabilities
  (donor and acceptor, each strand) within ``SPLICE_SPAN_BP`` bases either side of the variant, the
  same span SpliceAI's delta scores use. Kept with its sign (gain or loss), channel and offset.
- **DNase delta**: for each of the 13 DNase tracks, ``log1p`` of the mean predicted signal over the
  ``TRACK_BIN_BP`` bases centred on the variant (the bin and transform the model card evaluates
  tracks on), alternate minus reference; the track with the largest absolute change is reported.
- **top tracks**: the same binned ``log1p`` change for the NTv3 tracks of human samples (ids without
  a species prefix; the other NTv3 tracks belong to other species and say nothing about a human
  genome), the ``TOP_TRACKS`` largest by absolute change.

Before any of that, a variant whose window leaves its contig, whose contig the reference lacks, or
whose VCF REF differs from the reference base is ``not_assessed`` with the reason.
"""

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import onnxruntime as ort
import polars as pl
from eliot import log_message, start_action

from just_dna_pipelines.predictions.models import PredictionModel
from just_dna_pipelines.predictions.reference import ReferenceGenome, encode_bases
from just_dna_pipelines.predictions.variants import STATUS_NOT_ASSESSED, STATUS_SCORED, VARIANT_SCHEMA

SPLICE_SPAN_BP = 50
TRACK_BIN_BP = 128
TOP_TRACKS = 3

GPU_PROVIDER = "CUDAExecutionProvider"
CPU_PROVIDER = "CPUExecutionProvider"

SCORE_SCHEMA: dict[str, pl.DataType] = {
    "splice_delta": pl.Float64,
    "splice_change": pl.Float64,
    "splice_channel": pl.String,
    "splice_offset_bp": pl.Int64,
    "dnase_delta": pl.Float64,
    "dnase_track": pl.String,
    "dnase_biosample": pl.String,
    "top_tracks": pl.List(pl.Struct({"track": pl.String, "delta": pl.Float64})),
}
RESULT_SCHEMA: dict[str, pl.DataType] = {**VARIANT_SCHEMA, **SCORE_SCHEMA}


@dataclass(frozen=True)
class TrackChannels:
    """Names of the graph's output channels, read from the model's own ``onnx_meta.json`` / ``channels.json``."""

    splice: tuple[str, ...]
    dnase_ids: tuple[str, ...]
    dnase_biosamples: tuple[str, ...]
    ntv3_ids: tuple[str, ...]
    ntv3_human: tuple[int, ...]

    @classmethod
    def from_model_dir(cls, directory: Path) -> "TrackChannels":
        meta = json.loads((directory / "onnx_meta.json").read_text(encoding="utf-8"))
        channels = json.loads((directory / "channels.json").read_text(encoding="utf-8"))
        outputs = {o["name"]: o for o in meta["outputs"]}
        dnase = channels["xheads"]["dnase"]
        biosample = {t["file"]: t["biosample"] for t in dnase["tracks"]}
        dnase_ids = tuple(outputs["x_dnase"]["channels"])
        ntv3_ids = tuple(outputs["ntv3"]["channels"])
        return cls(
            splice=tuple(outputs["x_splice"]["channels"]),
            dnase_ids=dnase_ids,
            dnase_biosamples=tuple(biosample.get(i, i) for i in dnase_ids),
            ntv3_ids=ntv3_ids,
            ntv3_human=tuple(i for i, track in enumerate(ntv3_ids) if ":" not in track),
        )


NOT_LOADED = "not loaded (nothing to score)"


def optimized_graph_path(onnx_path: Path, provider: str) -> Path:
    """Where the session's optimized graph is kept, per ONNX Runtime version and provider.

    Building a session optimizes the exported graph, which took about six minutes on a busy CPU;
    loading the saved result takes seconds. An optimized graph is only valid for the runtime version
    and provider that wrote it, so both are in the name.
    """
    tag = f"ort{ort.__version__}-{provider.removesuffix('ExecutionProvider').lower()}"
    return onnx_path.with_name(f"{onnx_path.stem}.optimized.{tag}.onnx")


class ModelSession:
    """An ONNX Runtime session on the best provider this install offers (CUDA, else CPU).

    Loaded on the first ``run``: a run whose variants were all set aside before scoring should not
    pay for it. The first load on a machine writes the optimized graph beside the model
    (``optimized_graph_path``); later loads read it with no further optimization.
    """

    def __init__(self, onnx_path: Path) -> None:
        self.onnx_path = onnx_path
        self.load_seconds = 0.0
        self.provider = NOT_LOADED
        self._session: ort.InferenceSession | None = None
        self._output_names: list[str] = []

    def _load(self) -> ort.InferenceSession:
        available = ort.get_available_providers()
        providers = [p for p in (GPU_PROVIDER,) if p in available] + [CPU_PROVIDER]
        cached = optimized_graph_path(self.onnx_path, providers[0])
        options = ort.SessionOptions()
        started = time.perf_counter()
        if cached.is_file():
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
            session = ort.InferenceSession(str(cached), sess_options=options, providers=providers)
        else:
            partial = cached.with_name(f"{cached.name}.{os.getpid()}.partial")
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_EXTENDED
            options.optimized_model_filepath = str(partial)
            session = ort.InferenceSession(str(self.onnx_path), sess_options=options, providers=providers)
            partial.replace(cached)
        self.load_seconds = time.perf_counter() - started
        self.provider = session.get_providers()[0]
        self._output_names = [o.name for o in session.get_outputs()]
        log_message(
            message_type="prediction_model_loaded",
            provider=self.provider,
            seconds=round(self.load_seconds, 1),
            optimized_graph=str(cached),
        )
        return session

    def run(self, bases: np.ndarray) -> dict[str, np.ndarray]:
        if self._session is None:
            self._session = self._load()
        return dict(zip(self._output_names, self._session.run(None, {"bases": bases}), strict=True))


def _not_assessed(row: dict, reason: str) -> dict:
    return {**row, "status": STATUS_NOT_ASSESSED, "reason": reason}


def _empty_scores() -> dict:
    return {name: None for name in SCORE_SCHEMA}


def _binned_log1p(values: np.ndarray, center: int) -> np.ndarray:
    """``log1p`` of the mean over the ``TRACK_BIN_BP`` bases centred on ``center``, per track."""
    half = TRACK_BIN_BP // 2
    return np.log1p(np.maximum(values[center - half : center + half].mean(axis=0, dtype=np.float64), 0.0))


def variant_scores(ref_out: dict[str, np.ndarray], alt_out: dict[str, np.ndarray], center: int, channels: TrackChannels) -> dict:
    """The scores of one variant from the graph's outputs for its reference and alternate windows.

    Each array is one row of the batch: ``[window, channels]``.
    """
    lo, hi = center - SPLICE_SPAN_BP, center + SPLICE_SPAN_BP + 1
    splice = alt_out["x_splice"][lo:hi].astype(np.float64) - ref_out["x_splice"][lo:hi].astype(np.float64)
    pos_idx, chan_idx = np.unravel_index(int(np.argmax(np.abs(splice))), splice.shape)
    dnase = _binned_log1p(alt_out["x_dnase"], center) - _binned_log1p(ref_out["x_dnase"], center)
    dnase_idx = int(np.argmax(np.abs(dnase)))
    human = np.asarray(channels.ntv3_human, dtype=np.int64)
    ntv3 = _binned_log1p(alt_out["ntv3"][:, human], center) - _binned_log1p(ref_out["ntv3"][:, human], center)
    top = np.argsort(-np.abs(ntv3), kind="stable")[:TOP_TRACKS]
    return {
        "splice_delta": float(abs(splice[pos_idx, chan_idx])),
        "splice_change": float(splice[pos_idx, chan_idx]),
        "splice_channel": channels.splice[chan_idx],
        "splice_offset_bp": int(pos_idx) - SPLICE_SPAN_BP,
        "dnase_delta": float(dnase[dnase_idx]),
        "dnase_track": channels.dnase_ids[dnase_idx],
        "dnase_biosample": channels.dnase_biosamples[dnase_idx],
        "top_tracks": [{"track": channels.ntv3_ids[int(human[i])], "delta": float(ntv3[i])} for i in top],
    }


def prepare_window(row: dict, reference: ReferenceGenome, window: int) -> tuple[np.ndarray | None, str | None]:
    """The encoded reference/alternate pair ``[2, window]`` for a candidate SNV, or the reason it has none."""
    chrom, pos, ref, alt = row["chrom"], int(row["pos"]), row["ref"].upper(), row["alt"].upper()
    if reference.contig(chrom) is None:
        return None, f"The reference genome has no contig named {chrom}."
    sequence = reference.window(chrom, pos, window)
    if sequence is None:
        length = reference.contig_length(chrom)
        return None, (
            f"The {window:,}-base window centred here runs past the end of chromosome {chrom} "
            f"({length:,} bases long)."
        )
    center = window // 2
    genome_base = sequence[center].upper()
    if genome_base != ref:
        return None, f"The file's reference base {ref} differs from the reference genome's {genome_base} at this position."
    ref_codes = encode_bases(sequence)
    alt_codes = ref_codes.copy()
    alt_codes[center] = encode_bases(alt)[0]
    return np.stack([ref_codes, alt_codes]), None


def score_variants(
    variants: pl.DataFrame,
    reference: ReferenceGenome,
    session: ModelSession,
    model: PredictionModel,
    channels: TrackChannels,
    on_progress: Callable[[int, int], None] | None = None,
) -> pl.DataFrame:
    """Score every candidate row (``status`` null) and return all rows in ``RESULT_SCHEMA``.

    Rows already ``not_assessed`` pass through with null scores. Each scored variant is two graph calls
    of one row: the reference window, then the alternate window.
    """
    if model.window < 2 * max(SPLICE_SPAN_BP + 1, TRACK_BIN_BP):
        raise ValueError(f"A {model.window}-base window is too small for the scoring spans of this model.")
    center = model.window // 2
    rows = variants.to_dicts()
    candidates = sum(1 for r in rows if r["status"] is None)
    done = 0
    results: list[dict] = []
    with start_action(action_type="score_variants", model=model.id, candidates=candidates, provider=session.provider):
        for row in rows:
            if row["status"] is not None:
                results.append({**row, **_empty_scores()})
                continue
            batch, reason = prepare_window(row, reference, model.window)
            if batch is None:
                results.append({**_not_assessed(row, reason), **_empty_scores()})
                continue
            started = time.perf_counter()
            ref_out = {name: values[0] for name, values in session.run(batch[0:1]).items()}
            alt_out = {name: values[0] for name, values in session.run(batch[1:2]).items()}
            results.append({**row, "status": STATUS_SCORED, "reason": None, **variant_scores(ref_out, alt_out, center, channels)})
            done += 1
            log_message(
                message_type="variant_scored",
                chrom=row["chrom"],
                pos=row["pos"],
                seconds=round(time.perf_counter() - started, 2),
            )
            if on_progress is not None:
                on_progress(done, candidates)
    return pl.DataFrame(results, schema=RESULT_SCHEMA, orient="row") if results else pl.DataFrame(schema=RESULT_SCHEMA)


def rank_results(results: pl.DataFrame) -> pl.DataFrame:
    """Scored rows first, by splice delta (the score with a published benchmark), then DNase change.

    Ties fall back to position and allele so the order is the same on every run.
    """
    return results.with_columns(
        (pl.col("status") == STATUS_SCORED).alias("_scored"), pl.col("dnase_delta").abs().alias("_dnase_abs")
    ).sort(
        ["_scored", "splice_delta", "_dnase_abs", "chrom", "pos", "alt"],
        descending=[True, True, True, False, False, False],
        nulls_last=True,
    ).drop("_scored", "_dnase_abs")
