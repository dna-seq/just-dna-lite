"""Genome prediction models: base encoding, reference windows, variant selection, scores, report, job config.

Ground truth is computed in each test from the data it builds (a FASTA written here, a parquet
written here) or, where a test reads the real GRCh38 FASTA or the real model, it skips when that file
is not on this machine.
"""

import json
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from dagster import validate_run_config
from just_dna_pipelines.annotation.definitions import defs
from just_dna_pipelines.annotation.report_logic import report_environment
from just_dna_pipelines.io import read_vcf_file
from just_dna_pipelines.predictions.download import model_dir, model_files_present
from just_dna_pipelines.predictions.models import KRONGENOME_F, PREDICTION_MODELS, get_prediction_model
from just_dna_pipelines.predictions.reference import (
    REFERENCE_FASTA_ENV,
    ReferenceGenome,
    encode_bases,
    reference_fasta_candidates,
)
from just_dna_pipelines.predictions.report import PredictionRun, build_report_context, render_prediction_report
from just_dna_pipelines.predictions.run_config import (
    MAX_REGION_BP,
    PREDICTION_ASSET,
    PREDICTION_JOB,
    VARIANT_SET_ANNOTATED,
    VARIANT_SET_REGION,
    RegionError,
    parse_region,
    prediction_run_config,
)
from just_dna_pipelines.predictions.scoring import (
    RESULT_SCHEMA,
    SPLICE_SPAN_BP,
    TOP_TRACKS,
    TRACK_BIN_BP,
    ModelSession,
    TrackChannels,
    prepare_window,
    rank_results,
    score_variants,
    variant_scores,
)
from just_dna_pipelines.predictions.variants import (
    REASON_INDEL,
    REASON_MITOCHONDRIAL,
    REASON_NOT_CARRIED,
    STATUS_NOT_ASSESSED,
    STATUS_SCORED,
    VARIANT_SCHEMA,
    annotated_variants,
    classify_variants,
    region_variants,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SMALL_VCF = REPO_ROOT / "data" / "input" / "tests" / "antku_small.vcf"
RNG = np.random.default_rng(20261120)


def _random_sequence(length: int, soft_masked_from: int | None = None) -> str:
    seq = "".join(RNG.choice(list("ACGT"), size=length))
    if soft_masked_from is not None:
        seq = seq[:soft_masked_from] + seq[soft_masked_from:].lower()
    return seq


@pytest.fixture
def small_fasta(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """A FASTA with a chr-prefixed contig (soft-masked tail, one N), an unprefixed one and chrM."""
    contigs = {
        "chr1": _random_sequence(1200, soft_masked_from=800),
        "2": _random_sequence(120),
        "chrM": _random_sequence(80),
    }
    contigs["chr1"] = contigs["chr1"][:150] + "N" + contigs["chr1"][151:]
    path = tmp_path / "ref.fa"
    with path.open("w", encoding="ascii") as handle:
        for name, seq in contigs.items():
            handle.write(f">{name} test contig\n")
            for i in range(0, len(seq), 60):
                handle.write(seq[i : i + 60] + "\n")
    return path, contigs


# ── base encoding ────────────────────────────────────────────────────────────────────────────────


def test_bases_encode_as_the_model_card_states() -> None:
    sequence = "ACGTNacgtnRYK-"
    expected = [0, 1, 2, 3, 4, 0, 1, 2, 3, 4, 4, 4, 4, 4]
    codes = encode_bases(sequence)
    assert codes.dtype == np.int64
    assert codes.tolist() == expected


# ── reference windows ───────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("query", ["1", "chr1", "CHR1"])
def test_contig_names_meet_through_normalize_chrom(small_fasta: tuple[Path, dict[str, str]], query: str) -> None:
    path, contigs = small_fasta
    reference = ReferenceGenome(path)
    assert reference.contig(query) == "chr1"
    assert reference.contig_length(query) == len(contigs["chr1"])
    assert reference.contig("MT") == "chrM"
    assert reference.contig("17") is None


@pytest.mark.parametrize("pos", [9, 10, 150, 151, 800, 801, 1192])
def test_window_puts_the_one_based_position_at_the_centre(small_fasta: tuple[Path, dict[str, str]], pos: int) -> None:
    path, contigs = small_fasta
    reference = ReferenceGenome(path)
    size = 16
    window = reference.window("1", pos, size)
    seq = contigs["chr1"]
    assert window == seq[pos - 1 - size // 2 : pos - 1 - size // 2 + size]
    assert window[size // 2] == seq[pos - 1]
    # Soft-masking is kept in the window and folded only by the encoder.
    assert encode_bases(window).tolist() == encode_bases(window.upper()).tolist()


@pytest.mark.parametrize("pos", [1, 8, 9, 1192, 1193, 1200])
def test_a_window_that_leaves_the_contig_is_none(small_fasta: tuple[Path, dict[str, str]], pos: int) -> None:
    path, contigs = small_fasta
    reference = ReferenceGenome(path)
    size = 16
    first, last = pos - size // 2, pos - size // 2 + size - 1
    inside = first >= 1 and last <= len(contigs["chr1"])
    assert (reference.window("1", pos, size) is not None) == inside


def _row(chrom: str, pos: int, ref: str, alt: str, genotype: str | None = None) -> dict:
    return {name: None for name in VARIANT_SCHEMA} | {"chrom": chrom, "pos": pos, "ref": ref, "alt": alt, "genotype": genotype}


def test_prepare_window_builds_reference_and_alternate_rows(small_fasta: tuple[Path, dict[str, str]]) -> None:
    path, contigs = small_fasta
    reference = ReferenceGenome(path)
    pos, size = 100, 16
    ref_base = contigs["chr1"][pos - 1].upper()
    alt_base = next(b for b in "ACGT" if b != ref_base)
    batch, reason = prepare_window(_row("chr1", pos, ref_base, alt_base), reference, size)
    assert reason is None
    assert batch.shape == (2, size)
    diff = np.flatnonzero(batch[0] != batch[1])
    assert diff.tolist() == [size // 2]
    assert batch[1, size // 2] == encode_bases(alt_base)[0]
    assert batch[0].tolist() == encode_bases(contigs["chr1"][pos - 1 - size // 2 : pos - 1 - size // 2 + size]).tolist()


def test_ref_mismatch_contig_end_and_unknown_contig_are_not_assessed(small_fasta: tuple[Path, dict[str, str]]) -> None:
    path, contigs = small_fasta
    reference = ReferenceGenome(path)
    pos = 100
    true_base = contigs["chr1"][pos - 1].upper()
    wrong = next(b for b in "ACGT" if b != true_base)
    alt = next(b for b in "ACGT" if b not in (true_base, wrong))
    batch, reason = prepare_window(_row("1", pos, wrong, alt), reference, 16)
    assert batch is None and f"reference genome's {true_base}" in reason
    batch, reason = prepare_window(_row("1", 3, contigs["chr1"][2].upper(), "A"), reference, 16)
    assert batch is None and "runs past the end of chromosome 1" in reason
    batch, reason = prepare_window(_row("17", 50, "A", "C"), reference, 16)
    assert batch is None and "no contig named 17" in reason
    # An N in the reference is never equal to a stated REF base.
    batch, reason = prepare_window(_row("1", 151, "A", "C"), reference, 16)
    assert batch is None and "reference genome's N" in reason


def _real_fasta() -> Path | None:
    return next((p for p in reference_fasta_candidates() if p.is_file()), None)


@pytest.mark.skipif(_real_fasta() is None, reason=f"no GRCh38 FASTA here (set {REFERENCE_FASTA_ENV})")
def test_polars_bio_start_is_the_one_based_vcf_pos_against_grch38() -> None:
    """The normalized parquet's ``start`` indexes the FASTA directly: every SNV's REF matches there.

    The same check one base to the left fails for most rows, so the test can tell the two apart.
    """
    snvs = (
        read_vcf_file(SMALL_VCF, save_parquet=None, with_formats=True)
        .filter((pl.col("ref").str.len_chars() == 1) & (pl.col("alt").str.len_chars() == 1))
        .select("chrom", "start", "ref")
        .collect()
    )
    assert snvs.height > 50
    reference = ReferenceGenome(_real_fasta())
    at_start = [reference.bases(r["chrom"], r["start"], r["start"]).upper() == r["ref"] for r in snvs.to_dicts()]
    one_left = [reference.bases(r["chrom"], r["start"] - 1, r["start"] - 1).upper() == r["ref"] for r in snvs.to_dicts()]
    assert all(at_start)
    assert sum(one_left) < len(one_left) / 2


# ── variant sets ────────────────────────────────────────────────────────────────────────────────


def test_classify_explodes_alleles_and_gives_every_skip_a_reason() -> None:
    rows = pl.DataFrame(
        [
            _row("1", 100, "A", "G", "A/G"),  # candidate
            _row("1", 200, "A", "AT", "A/AT"),  # insertion
            _row("MT", 300, "A", "G", "G/G"),  # mitochondrial
            _row("2", 400, "C", "T|G", "T/G"),  # multi-allelic, both carried
            _row("2", 500, "C", "T|G", "C/T"),  # multi-allelic, G not carried
            _row("3", 600, "G", "A", "G/A"),  # candidate, past a cap of 3
        ],
        schema=VARIANT_SCHEMA,
        orient="row",
    )
    out = classify_variants(rows, max_variants=3)
    assert out.columns == list(VARIANT_SCHEMA)
    keyed = {(r["chrom"], r["pos"], r["alt"]): r for r in out.to_dicts()}
    assert set(keyed) == {
        ("1", 100, "G"), ("1", 200, "AT"), ("MT", 300, "G"), ("2", 400, "T"), ("2", 400, "G"),
        ("2", 500, "T"), ("2", 500, "G"), ("3", 600, "A"),
    }
    assert keyed[("1", 200, "AT")]["reason"] == REASON_INDEL
    assert keyed[("MT", 300, "G")]["reason"] == REASON_MITOCHONDRIAL
    assert keyed[("2", 500, "G")]["reason"] == REASON_NOT_CARRIED
    candidates = [k for k, r in keyed.items() if r["status"] is None]
    assert candidates == [("1", 100, "G"), ("2", 400, "T"), ("2", 400, "G")]
    assert "cap of 3" in keyed[("3", 600, "A")]["reason"]
    assert all((r["status"] == STATUS_NOT_ASSESSED) == (r["reason"] is not None) for r in keyed.values())
    # No cap: every candidate stays.
    assert classify_variants(rows, max_variants=0).filter(pl.col("status").is_null()).height == 5


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("chr7:117,559,000-117,560,000", ("7", 117_559_000, 117_560_000)),
        ("X:5-5", ("X", 5, 5)),
        ("chrM:1-100", ("MT", 1, 100)),
    ],
)
def test_parse_region_reads_one_based_inclusive_spans(text: str, expected: tuple[str, int, int]) -> None:
    assert parse_region(text) == expected


@pytest.mark.parametrize("text", ["7", "7:10", "7:20-10", "7:0-5", f"1:1-{MAX_REGION_BP + 1}", "7:a-b", "ζ"])
def test_parse_region_refuses_malformed_or_oversized_regions(text: str) -> None:
    with pytest.raises(RegionError):
        parse_region(text)


def test_region_variants_take_rows_inside_the_region_from_the_normalized_parquet(tmp_path: Path) -> None:
    parquet = tmp_path / "user_vcf_normalized.parquet"
    frame = pl.DataFrame(
        {
            "chrom": ["1", "1", "1", "1", "2"],
            "start": [99, 100, 150, 201, 120],
            "end": [99, 100, 152, 201, 120],
            "rsid": ["", "rs1", "", "rs3", "rs4"],
            "ref": ["A", "C", "GTA", "T", "A"],
            "alt": ["G", "T", "G", "C", "C"],
            "genotype": [["A", "G"], ["C", "T"], ["GTA", "G"], ["C", "C"], ["A", "C"]],
        },
        schema_overrides={"start": pl.UInt32, "end": pl.UInt32},
    )
    frame.write_parquet(parquet)
    out = region_variants(parquet, "chr1:100-200")
    expected = frame.filter((pl.col("chrom") == "1") & pl.col("start").is_between(100, 200))
    assert out.get_column("pos").to_list() == expected.get_column("start").cast(pl.Int64).to_list()
    assert out.get_column("rsid").to_list() == ["rs1", None]
    assert out.get_column("genotype").to_list() == ["C/T", "GTA/G"]
    assert region_variants(parquet, "5:1-1000").is_empty()


def _weights_frame(module: str) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "chrom": ["1", "1", "2", "3"],
            "start": [100, 200, 300, 400],
            "rsid": ["", "", "", ""],
            f"rsid_{module}": ["rs100", "rs200", "rs300", None],
            "ref": ["A", "C", "G", "T"],
            "alt": ["G", "T", None, "C"],
            "genotype": [["A", "G"], ["C", "T"], ["G", "G"], ["T", "C"]],
            "module": [module, module, module, None],  # the last row matched nothing
            "weight": [0.5, -1.5, 0.2, None],
            "genotype_evidence": ["called", "called", "restored_hom_ref", None],
        },
        schema_overrides={"start": pl.UInt32},
    )


def test_annotated_variants_keep_matched_called_rows_merged_across_modules(tmp_path: Path) -> None:
    modules_dir = tmp_path / "modules"
    modules_dir.mkdir()
    entries = []
    for module in ("zz_test_module_a", "zz_test_module_b"):
        path = modules_dir / f"{module}_weights.parquet"
        frame = _weights_frame(module)
        if module.endswith("b"):
            frame = frame.with_columns(pl.when(pl.col("start") == 100).then(2.5).otherwise(pl.col("weight")).alias("weight"))
        frame.write_parquet(path)
        entries.append({"module": module, "lead_table": "weights", "weights_path": str(path)})
    (modules_dir / "manifest.json").write_text(
        json.dumps({"user_name": "u", "sample_name": "s", "source_vcf": "s.vcf", "modules": entries}), encoding="utf-8"
    )
    out = annotated_variants(modules_dir)
    # Matched and called: positions 100 and 200, each once, naming both modules.
    assert out.get_column("pos").to_list() == [100, 200]  # by largest |weight|: 2.5 then 1.5
    assert out.get_column("max_abs_weight").to_list() == [2.5, 1.5]
    assert out.get_column("rsid").to_list() == ["rs100", "rs200"]
    assert set(out.get_column("modules").to_list()) == {"zz_test_module_a, zz_test_module_b"}
    assert out.get_column("status").null_count() == out.height
    assert annotated_variants(tmp_path / "missing").is_empty()


# ── scores ──────────────────────────────────────────────────────────────────────────────────────


def _channels() -> TrackChannels:
    return TrackChannels(
        splice=("donor +", "acceptor +", "donor -", "acceptor -"),
        dnase_ids=("D1", "D2", "D3"),
        dnase_biosamples=("liver", "K562", "H1"),
        ntv3_ids=("ENCSR1", "ntv3_rat:SRR1", "ENCSR2", "ENCSR3", "ENCSR4"),
        ntv3_human=(0, 2, 3, 4),
    )


def test_a_window_too_small_for_the_scoring_spans_is_refused(small_fasta: tuple[Path, dict[str, str]]) -> None:
    path, _ = small_fasta
    model = KRONGENOME_F.model_copy(update={"window": TRACK_BIN_BP})
    with pytest.raises(ValueError, match="window"):
        score_variants(pl.DataFrame(schema=VARIANT_SCHEMA), ReferenceGenome(path), _FakeSession(TRACK_BIN_BP), model, _channels())


def test_variant_scores_pick_the_biggest_change_near_the_variant() -> None:
    window, center = 1024, 512
    base = {
        "x_splice": RNG.uniform(0, 0.01, size=(window, 4)).astype(np.float32),
        "x_dnase": RNG.uniform(0, 1, size=(window, 3)).astype(np.float32),
        "ntv3": RNG.uniform(0, 5, size=(window, 5)).astype(np.float32),
    }
    alt = {k: v.copy() for k, v in base.items()}
    alt["x_splice"][center + 7, 2] -= 0.004  # a loss inside the span
    alt["x_splice"][center + SPLICE_SPAN_BP + 3, 0] += 0.9  # larger, but outside the span
    alt["x_dnase"][center - TRACK_BIN_BP // 2 : center + TRACK_BIN_BP // 2, 1] += 2.0
    alt["ntv3"][center - TRACK_BIN_BP // 2 : center + TRACK_BIN_BP // 2, 1] += 50.0  # rat track: ignored
    alt["ntv3"][center - TRACK_BIN_BP // 2 : center + TRACK_BIN_BP // 2, 3] += 4.0
    scores = variant_scores(base, alt, center, _channels())
    expected_splice = float(alt["x_splice"][center + 7, 2]) - float(base["x_splice"][center + 7, 2])
    assert scores["splice_channel"] == "donor -"
    assert scores["splice_offset_bp"] == 7
    assert scores["splice_change"] == pytest.approx(expected_splice)
    assert scores["splice_delta"] == pytest.approx(abs(expected_splice))
    half = TRACK_BIN_BP // 2
    ref_mean = base["x_dnase"][center - half : center + half, 1].mean(dtype=np.float64)
    alt_mean = alt["x_dnase"][center - half : center + half, 1].mean(dtype=np.float64)
    assert scores["dnase_track"] == "D2" and scores["dnase_biosample"] == "K562"
    assert scores["dnase_delta"] == pytest.approx(np.log1p(alt_mean) - np.log1p(ref_mean))
    tracks = [t["track"] for t in scores["top_tracks"]]
    assert len(tracks) == TOP_TRACKS and tracks[0] == "ENCSR3" and "ntv3_rat:SRR1" not in tracks


class _FakeSession(ModelSession):
    """Returns outputs whose alternate row differs only in donor + at the variant, by a known amount."""

    def __init__(self, window: int) -> None:
        super().__init__(Path("unused.onnx"))
        self.window = window
        self.calls = 0
        self.provider = "fake"

    def run(self, bases: np.ndarray) -> dict[str, np.ndarray]:
        self.calls += 1
        rows = bases.shape[0]
        out = {
            "x_splice": np.zeros((rows, self.window, 4), dtype=np.float32),
            "x_dnase": np.zeros((rows, self.window, 3), dtype=np.float32),
            "ntv3": np.zeros((rows, self.window, 5), dtype=np.float32),
        }
        out["x_splice"][1, self.window // 2, 0] = 0.25
        return out


def test_score_variants_keeps_every_row_and_scores_only_candidates(small_fasta: tuple[Path, dict[str, str]]) -> None:
    path, contigs = small_fasta
    reference = ReferenceGenome(path)
    window = 2 * TRACK_BIN_BP
    model = KRONGENOME_F.model_copy(update={"window": window})
    good = contigs["chr1"][499].upper()
    rows = pl.DataFrame(
        [
            _row("1", 500, good, next(b for b in "ACGT" if b != good), "x"),
            _row("1", 2, contigs["chr1"][1].upper(), "A", "x"),  # window off the contig start
            _row("1", 200, "A", "AT", "A/AT"),
        ],
        schema=VARIANT_SCHEMA,
        orient="row",
    )
    classified = classify_variants(rows.with_columns(pl.lit(None, dtype=pl.String).alias("genotype")), max_variants=10)
    session = _FakeSession(window)
    results = rank_results(score_variants(classified, reference, session, model, _channels()))
    assert results.schema == pl.Schema(RESULT_SCHEMA)
    assert results.height == rows.height
    assert session.calls == 1
    assert results.get_column("status").to_list() == [STATUS_SCORED, STATUS_NOT_ASSESSED, STATUS_NOT_ASSESSED]
    top = results.row(0, named=True)
    assert top["splice_delta"] == pytest.approx(0.25) and top["splice_channel"] == "donor +" and top["splice_offset_bp"] == 0
    assert results.filter(pl.col("status") == STATUS_NOT_ASSESSED).get_column("reason").null_count() == 0


def test_a_run_with_nothing_to_score_never_loads_the_model(small_fasta: tuple[Path, dict[str, str]]) -> None:
    path, _ = small_fasta
    session = ModelSession(Path("does-not-exist.onnx"))
    rows = classify_variants(pl.DataFrame([_row("1", 200, "A", "AT", "A/AT")], schema=VARIANT_SCHEMA, orient="row"), 5)
    results = score_variants(rows, ReferenceGenome(path), session, KRONGENOME_F, _channels())
    assert results.get_column("status").to_list() == [STATUS_NOT_ASSESSED]
    assert session.load_seconds == 0.0 and session.provider.startswith("not loaded")


# ── report ──────────────────────────────────────────────────────────────────────────────────────


def _run(scored: int, not_assessed: int) -> PredictionRun:
    return PredictionRun(
        model_id=KRONGENOME_F.id, user_name="u", sample_name="Ünïcode sample", variant_set=VARIANT_SET_REGION,
        region="7:1-100", max_variants=5, provider="CPUExecutionProvider", model_load_seconds=12.0,
        scoring_seconds=80.0, reference_fasta="/x/Homo_sapiens.GRCh38.dna.primary_assembly.fa",
        splice_span_bp=SPLICE_SPAN_BP, track_bin_bp=TRACK_BIN_BP, top_tracks=TOP_TRACKS,
        candidates=scored, scored=scored, not_assessed=not_assessed, generated_at="2026-11-20 12:00 CET",
        parquet_path="/x/krongenome_variant_effects.parquet",
    )


def _results() -> pl.DataFrame:
    scored = {
        **_row("7", 1000, "A", "G", "A/G"), "rsid": "rs123", "gene": "CFTR", "status": STATUS_SCORED,
        "splice_delta": 0.31, "splice_change": -0.31, "splice_channel": "acceptor +", "splice_offset_bp": -2,
        "dnase_delta": 0.05, "dnase_track": "D1", "dnase_biosample": "liver",
        "top_tracks": [{"track": "ENCSR628PLS", "delta": 0.4}],
    }
    weaker = {**scored, "pos": 2000, "rsid": "not-an-rsid", "splice_delta": 0.01, "splice_change": 0.01}
    skipped = {
        **_row("7", 3000, "A", "AT", "A/AT"), "status": STATUS_NOT_ASSESSED, "reason": REASON_INDEL,
        **{k: None for k in RESULT_SCHEMA if k not in VARIANT_SCHEMA},
    }
    return rank_results(pl.DataFrame([skipped, weaker, scored], schema=RESULT_SCHEMA, orient="row"))


def test_report_ranks_scored_rows_and_lists_not_assessed_with_reasons(tmp_path: Path) -> None:
    results = _results()
    run = _run(scored=2, not_assessed=1)
    context = build_report_context(results, run, KRONGENOME_F)
    assert [r["variant"] for r in context["scored"]] == ["7:1,000 A>G", "7:2,000 A>G"]
    assert context["scored"][0]["rsid_url"] == "https://www.ncbi.nlm.nih.gov/snp/rs123"
    assert context["scored"][1]["rsid_url"] is None  # never a link for a malformed id
    out = render_prediction_report(results, run, KRONGENOME_F, tmp_path / "reports" / "r.html")
    html = out.read_text(encoding="utf-8")
    assert html == report_environment().get_template("variant_effects_report.html.j2").render(**context)
    assert html.index("rs123") < html.index("not-an-rsid") < html.index(REASON_INDEL)
    assert html.index("Your results") < html.index("How to read this") < html.index("Technical details")
    for fact in (KRONGENOME_F.revision, KRONGENOME_F.licence, KRONGENOME_F.author, KRONGENOME_F.model_card_url,
                 "CPUExecutionProvider", "Ünïcode sample", "not a clinical tool", "predictions, not measurements"):
        assert fact in html, fact
    assert "—" not in html  # no em-dashes in report prose
    assert 'href="https://www.ncbi.nlm.nih.gov/snp/not-an-rsid"' not in html


def test_report_with_nothing_scored_says_so(tmp_path: Path) -> None:
    results = _results().filter(pl.col("status") == STATUS_NOT_ASSESSED)
    html = render_prediction_report(results, _run(0, 1), KRONGENOME_F, tmp_path / "r.html").read_text(encoding="utf-8")
    assert "No variant could be scored" in html and REASON_INDEL in html


# ── models and job config ───────────────────────────────────────────────────────────────────────


def test_model_registry_entries_are_complete_and_keyed_by_id() -> None:
    assert set(PREDICTION_MODELS) == {m.id for m in PREDICTION_MODELS.values()}
    for model in PREDICTION_MODELS.values():
        assert len(model.revision) == 40 and model.onnx_file in model.files
        assert model.window > 0 and model.window % 2 == 0
    with pytest.raises(KeyError):
        get_prediction_model("no-such-model")


@pytest.mark.parametrize("region", [None, "7:117559000-117560000"])
def test_the_prediction_run_config_validates_against_its_job(region: str | None) -> None:
    config = prediction_run_config(variant_set=VARIANT_SET_REGION if region else VARIANT_SET_ANNOTATED, region=region)
    assert set(config["ops"]) == {PREDICTION_ASSET}
    job = defs.resolve_job_def(PREDICTION_JOB)
    validate_run_config(job, config)
    assert {node.name for node in job.graph.node_defs} == {PREDICTION_ASSET}


# ── the real model ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.slow
@pytest.mark.skipif(
    not model_files_present(KRONGENOME_F) or _real_fasta() is None,
    reason="KronGenome F not cached (uv run pipelines predict fetch-model) or no GRCh38 FASTA",
)
def test_krongenome_scores_one_real_snv() -> None:
    """One SNV through the real ONNX graph (minutes on a CPU): finite scores, human tracks only."""
    reference = ReferenceGenome(_real_fasta())
    pos = 117_559_600  # chr7, inside CFTR
    ref_base = reference.bases("7", pos, pos).upper()
    alt_base = next(b for b in "ACGT" if b != ref_base)
    rows = classify_variants(pl.DataFrame([_row("7", pos, ref_base, alt_base, f"{ref_base}/{alt_base}")], schema=VARIANT_SCHEMA, orient="row"), 1)
    directory = model_dir(KRONGENOME_F)
    session = ModelSession(directory / KRONGENOME_F.onnx_file)
    channels = TrackChannels.from_model_dir(directory)
    results = score_variants(rows, reference, session, KRONGENOME_F, channels)
    row = results.row(0, named=True)
    assert row["status"] == STATUS_SCORED, row["reason"]
    assert 0.0 <= row["splice_delta"] <= 1.0
    assert np.isfinite(row["dnase_delta"])
    assert len(row["top_tracks"]) == TOP_TRACKS
    assert all(":" not in t["track"] for t in row["top_tracks"])
    assert session.provider in ("CPUExecutionProvider", "CUDAExecutionProvider")
