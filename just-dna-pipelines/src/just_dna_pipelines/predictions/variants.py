"""Which of a sample's variants a prediction run scores, and why any of them is not scored.

Two selectors, both reading only files the pipeline already wrote for the sample:

- ``annotated_variants``: the variants the latest annotation run matched in a module, read from
  ``modules/manifest.json`` and each module's ``{module}_weights.parquet``. Only rows whose genotype
  was *called*; a ``restored_hom_ref`` row is an inference that the sample carries no variant there,
  so there is nothing to compare.
- ``region_variants``: every called variant in a bounded region ``chrom:start-end`` of
  ``user_vcf_normalized.parquet`` (never the raw VCF).

Every row a selector returns stays in the output. Those the model cannot score (an indel, a
mitochondrial site, an allele the sample does not carry, a row past the cap) carry
``status = not_assessed`` and a ``reason``, so the report can say what was left out and why.
"""

from pathlib import Path

import polars as pl
from just_dna_format.vrs import normalize_chrom

from just_dna_pipelines.annotation.hf_modules import MODULE_INFOS, AnnotationManifest
from just_dna_pipelines.annotation.report_logic import _annotated_rows, load_annotated_weights
from just_dna_pipelines.annotation.restoration import EVIDENCE_COLUMN, EVIDENCE_RESTORED
from just_dna_pipelines.predictions.run_config import parse_region

STATUS_SCORED = "scored"
STATUS_NOT_ASSESSED = "not_assessed"

REASON_INDEL = "Insertion or deletion: this version scores single-base substitutions only."
REASON_MITOCHONDRIAL = "Mitochondrial DNA: the model's exported graph reads nuclear DNA only."
REASON_NOT_CARRIED = "The sample does not carry this alternate allele."
REASON_NO_ALT = "No alternate allele in the file at this position."

# One row per (position, alternate allele), in this column order, whichever selector produced it.
VARIANT_SCHEMA: dict[str, pl.DataType] = {
    "chrom": pl.String,
    "pos": pl.Int64,
    "ref": pl.String,
    "alt": pl.String,
    "rsid": pl.String,
    "gene": pl.String,
    "genotype": pl.String,
    "modules": pl.String,
    "max_abs_weight": pl.Float64,
    "status": pl.String,
    "reason": pl.String,
}

def _split_alts(alt: pl.Expr) -> pl.Expr:
    """polars-bio writes multi-allelic ALT as ``A|T``; a plain VCF string would use ``,``."""
    return alt.str.replace_all(",", "|").str.split("|")


def _genotype_text(genotype: pl.Expr) -> pl.Expr:
    return genotype.list.join("/")


def _empty_variants() -> pl.DataFrame:
    return pl.DataFrame(schema=VARIANT_SCHEMA)


def classify_variants(variants: pl.DataFrame, max_variants: int) -> pl.DataFrame:
    """Set ``status``/``reason`` for what can be judged before reading the reference.

    One row per alternate allele (a multi-allelic site becomes several rows). Indels, mitochondrial
    sites and alleles the sample does not carry are ``not_assessed``. The first ``max_variants``
    remaining rows, in the order given, stay candidates (``status`` null, decided at scoring); the rest
    are ``not_assessed`` as over the cap. ``max_variants`` of 0 or less means no cap.
    """
    if variants.is_empty():
        return _empty_variants()
    exploded = (
        variants.with_columns(_split_alts(pl.col("alt")).alias("alt"))
        .explode("alt", empty_as_null=False)
        .with_columns(pl.col("alt").str.strip_chars())
    )
    genotype_alleles = pl.col("genotype").str.split("/")
    reason = (
        pl.when(pl.col("alt").is_null() | (pl.col("alt") == "") | (pl.col("alt") == "."))
        .then(pl.lit(REASON_NO_ALT))
        .when(pl.col("chrom").map_elements(normalize_chrom, return_dtype=pl.String) == "MT")
        .then(pl.lit(REASON_MITOCHONDRIAL))
        .when((pl.col("ref").str.len_chars() != 1) | (pl.col("alt").str.len_chars() != 1))
        .then(pl.lit(REASON_INDEL))
        .when(pl.col("genotype").is_not_null() & ~genotype_alleles.list.contains(pl.col("alt")))
        .then(pl.lit(REASON_NOT_CARRIED))
        .otherwise(pl.lit(None, dtype=pl.String))
    )
    classified = exploded.with_columns(reason.alias("reason"))
    candidate_rank = (
        pl.when(pl.col("reason").is_null()).then(pl.col("reason").is_null().cum_sum()).otherwise(None)
    )
    capped = classified.with_columns(candidate_rank.alias("_rank"))
    over_cap = (
        (pl.col("_rank") > max_variants) if max_variants > 0 else pl.lit(False)
    )
    cap_reason = f"Past the cap of {max_variants} variants for this run; raise the cap to score it."
    return capped.with_columns(
        pl.when(pl.col("reason").is_null() & over_cap)
        .then(pl.lit(cap_reason))
        .otherwise(pl.col("reason"))
        .alias("reason"),
    ).with_columns(
        pl.when(pl.col("reason").is_null())
        .then(pl.lit(None, dtype=pl.String))
        .otherwise(pl.lit(STATUS_NOT_ASSESSED))
        .alias("status")
    ).select(list(VARIANT_SCHEMA))


def _module_rows(weights_path: Path, module_name: str) -> pl.DataFrame:
    """One module's matched, called rows in ``VARIANT_SCHEMA`` columns (``status``/``reason`` null)."""
    annotated = _annotated_rows(load_annotated_weights(weights_path, module_name, MODULE_INFOS.get(module_name)))
    if EVIDENCE_COLUMN in annotated.columns:
        annotated = annotated.filter(pl.col(EVIDENCE_COLUMN).is_null() | (pl.col(EVIDENCE_COLUMN) != EVIDENCE_RESTORED))
    gene = pl.col("gene") if "gene" in annotated.columns else pl.lit(None, dtype=pl.String)
    weight = pl.col("weight").cast(pl.Float64).abs() if "weight" in annotated.columns else pl.lit(None, dtype=pl.Float64)
    return annotated.select(
        pl.col("chrom").cast(pl.String),
        pl.col("start").cast(pl.Int64).alias("pos"),
        pl.col("ref").cast(pl.String),
        pl.col("alt").cast(pl.String),
        pl.when(pl.col("rsid").cast(pl.String) == "").then(None).otherwise(pl.col("rsid").cast(pl.String)).alias("rsid"),
        gene.cast(pl.String).alias("gene"),
        _genotype_text(pl.col("genotype")).alias("genotype"),
        pl.lit(module_name).alias("modules"),
        weight.alias("max_abs_weight"),
    ).filter(pl.col("chrom").is_not_null() & pl.col("pos").is_not_null())


def annotated_variants(modules_dir: Path) -> pl.DataFrame:
    """The called variants the sample's latest annotation run matched, one row per site and allele.

    A site several modules matched appears once, naming every module. Ordered by the largest
    absolute weight any module gave it (unweighted rows last), then by position, so a cap keeps the
    variants the modules weigh most.
    """
    manifest_path = modules_dir / "manifest.json"
    if not manifest_path.is_file():
        return _empty_variants()
    manifest = AnnotationManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    frames = [
        _module_rows(Path(entry.weights_path), entry.module)
        for entry in manifest.modules
        if entry.lead_table == "weights" and entry.weights_path and Path(entry.weights_path).is_file()
    ]
    if not frames:
        return _empty_variants()
    rows = pl.concat(frames, how="vertical_relaxed")
    merged = rows.group_by("chrom", "pos", "ref", "alt").agg(
        pl.col("rsid").drop_nulls().first(),
        pl.col("gene").drop_nulls().first(),
        pl.col("genotype").drop_nulls().first(),
        pl.col("modules").unique().sort().str.join(", "),
        pl.col("max_abs_weight").max(),
    )
    ordered = merged.sort(
        ["max_abs_weight", "chrom", "pos", "alt"], descending=[True, False, False, False], nulls_last=True
    )
    return ordered.with_columns(
        pl.lit(None, dtype=pl.String).alias("status"), pl.lit(None, dtype=pl.String).alias("reason")
    ).select(list(VARIANT_SCHEMA))


def region_variants(normalized_parquet: Path, region: str) -> pl.DataFrame:
    """Every called variant of ``user_vcf_normalized.parquet`` inside ``region``, in position order."""
    chrom, start, end = parse_region(region)
    lf = pl.scan_parquet(normalized_parquet)
    contigs = lf.select(pl.col("chrom").unique()).collect().get_column("chrom").to_list()
    matching = [c for c in contigs if c is not None and normalize_chrom(c) == chrom]
    if not matching:
        return _empty_variants()
    rsid = pl.col("rsid").cast(pl.String) if "rsid" in lf.collect_schema().names() else pl.lit(None, dtype=pl.String)
    rows = (
        lf.filter(pl.col("chrom").is_in(matching) & pl.col("start").is_between(start, end))
        .select(
            pl.col("chrom").cast(pl.String),
            pl.col("start").cast(pl.Int64).alias("pos"),
            pl.col("ref").cast(pl.String),
            pl.col("alt").cast(pl.String),
            pl.when(rsid == "").then(None).otherwise(rsid).alias("rsid"),
            pl.lit(None, dtype=pl.String).alias("gene"),
            _genotype_text(pl.col("genotype")).alias("genotype"),
            pl.lit(None, dtype=pl.String).alias("modules"),
            pl.lit(None, dtype=pl.Float64).alias("max_abs_weight"),
            pl.lit(None, dtype=pl.String).alias("status"),
            pl.lit(None, dtype=pl.String).alias("reason"),
        )
        .sort("pos", "ref", "alt")
        .collect()
    )
    return rows.select(list(VARIANT_SCHEMA))
