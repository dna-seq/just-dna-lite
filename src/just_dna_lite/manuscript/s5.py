"""`manuscript s5`: Supplementary Table S5 ("PGS Catalog coverage of just-prs").

S5 says, for every scoring file in one PGS Catalog release, how much of it just-prs scores as the
Catalog specifies it, how much it approximates, how much it drops, and which files it cannot score at
all. Two steps, so the slow part runs once:

- `scan` records the release (`/rest/info`, `/rest/score/all`) with the fetch time, downloads every
  harmonized scoring file of one build into a cache directory, and measures each file over all of its
  rows (`measure_file`): no row sampling and no size cut-off. One JSON line per file accumulates in
  the work directory, so an interrupted scan resumes where it stopped.
- `render` classifies each measured file (`classify`) and writes the Markdown table, a per-file CSV
  and the histogram of the share of absolute weight that cannot be placed or matched.

The rules mirror just-prs 0.10.1 (`just_prs.prs`, `just_prs.vcf`, `just_prs.scoring`); `RULES` names
the code each one reads. A scoring file states its model in its columns and in the Catalog's score
metadata, so every rule is read from one of the two, never typed per file.
"""

from __future__ import annotations

import gzip
import math
import multiprocessing
import time
from collections.abc import Callable, Iterable
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import polars as pl
import requests
from pydantic import BaseModel, ConfigDict

try:  # dev dependency group; `manuscript ledger` and `s5 scan` must keep working without it
    from matplotlib import rcParams
    from matplotlib.figure import Figure
    from matplotlib.ticker import FuncFormatter
except ImportError:
    Figure = None
    FuncFormatter = None
    rcParams = None

REST_URL = "https://www.pgscatalog.org/rest"
CATALOG_JSON = "s5_catalog.json"
MEASURES_JSONL = "s5_measures.jsonl"
SCAN_PARQUET = "s5_scan.parquet"
MD_NAME = "S5_pgs_coverage.md"
CSV_NAME = "S5_pgs_coverage.csv"
FIGURE_STEM = "S5_unplaceable_weight_histogram"
DEFAULT_BUILD = "GRCh38"
DEFAULT_THRESHOLD = 0.10
SENSITIVITY_THRESHOLDS = (0.01, 0.10, 0.25, 0.50)
FIGURE_FLOOR = 1e-6  # the histogram's left edge; smaller nonzero shares are counted in its first bin
# just-prs reads a scoring file with these null spellings (`just_prs.scoring._parse_gz_scoring_file`).
NULL_CELLS = ("", "NA", "None")
DOSAGE_COLUMNS = ("dosage_0_weight", "dosage_1_weight", "dosage_2_weight")
FLAG_COLUMNS = ("is_dominant", "is_recessive", "is_interaction", "is_diplotype", "is_haplotype")
TRUE_CELLS = ("True", "TRUE", "true", "1", "T")
# A VCF allele: what `just_prs.vcf.compute_dosage_expr` can find equal to REF or ALT.
NUCLEOTIDES = r"^[ACGT]+$"
# Most-weighted distinct effect alleles (with the variant name where it is not an rsID) kept per file from the
# rows that cannot be placed or matched.
EXAMPLES = 5
MULTIPLICATIVE_WEIGHT_TYPE = "over expected risk"
CANNOT_SCORE = "cannot be scored"
APPROXIMATED = "approximated"
AS_SPECIFIED = "as specified"
CATEGORIES = (AS_SPECIFIED, APPROXIMATED, CANNOT_SCORE)
JUST_PRS = "just-prs 0.10.1"


class CatalogScore(BaseModel):
    """One score as the Catalog's REST API describes it; only the fields S5 reads."""

    model_config = ConfigDict(frozen=True)

    pgs_id: str
    name: str
    weight_type: Optional[str]
    variants_number: Optional[int]
    variants_interactions: int
    method_name: Optional[str]
    date_release: Optional[str]
    harmonized_url: str


class CatalogRelease(BaseModel):
    """The release a scan read, when it read it, and the scores in it."""

    model_config = ConfigDict(frozen=True)

    release_date: str
    release_score_count: int
    rest_api_version: Optional[str]
    fetched_at: datetime
    build: str
    scores: list[CatalogScore]


class FileMeasure(BaseModel):
    """Every row of one harmonized scoring file, sorted into what just-prs does with it.

    Rows fall into exactly one class, in this order: `unplaced` (no usable harmonized position),
    `non_nucleotide` (placed, but the effect allele is not an A/C/G/T string a VCF could carry),
    `effect_is_other` (placed, nucleotide, effect allele equal to the other allele) and `scored`.
    Weights are absolute; a file with only per-dosage weights uses the largest of the three.
    """

    model_config = ConfigDict(frozen=True)

    pgs_id: str
    gz_bytes: int
    header_weight_type: Optional[str]
    header_genome_build: Optional[str]
    hm_build: Optional[str]
    hm_date: Optional[str]
    columns: list[str]
    position_columns: Optional[str]
    weight_source: str
    has_effect_weight: bool
    has_dosage_weights: bool
    rows: int
    rows_unplaced: int
    rows_non_nucleotide: int
    rows_effect_is_other: int
    rows_scored: int
    rows_weight_missing: int
    rows_dominant: int
    rows_recessive: int
    rows_interaction: int
    rows_diplotype: int
    rows_haplotype: int
    rows_scored_flagged: int
    weight_total: float
    weight_unplaced: float
    weight_non_nucleotide: float
    weight_effect_is_other: float
    weight_scored: float
    weight_scored_flagged: float
    rows_unplaced_non_nucleotide: int
    unplaceable_examples: list[str]


class Rule(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    definition: str
    code: str


RULES: tuple[Rule, ...] = (
    Rule(
        key="unplaceable_weight",
        label="Weight on rows that cannot be placed or matched",
        definition="at least the threshold share of absolute weight sits on rows with no harmonized position, or "
        "whose effect allele is not an A/C/G/T string (HLA allele names, P/N, +/-, D/I, <CN0>, <INS:ME:ALU>, star "
        "alleles); those rows contribute nothing",
        code="`just_prs.prs._normalize_scoring_columns` (position from `hm_chr`/`hm_pos`), the variant-only left "
        "join in `just_prs.prs.compute_prs`, `just_prs.vcf.compute_dosage_expr` (effect allele compared with REF/ALT)",
    ),
    Rule(
        key="dominant_recessive",
        label="Dominant or recessive coding",
        definition="some row has `is_dominant` or `is_recessive` true; the weight is applied per allele copy "
        "(additively) instead",
        code="`just_prs.scoring.SCORING_FILE_SCHEMA` reads both columns; nothing in `just_prs.prs` uses them",
    ),
    Rule(
        key="interaction",
        label="Interaction terms",
        definition="some row has `is_interaction` true, or the Catalog's score metadata gives `variants_interactions` "
        "> 0; interaction terms are not computed",
        code="`is_interaction` is read by `just_prs.scoring.SCORING_FILE_SCHEMA` and used nowhere; the Catalog field "
        "is not read",
    ),
    Rule(
        key="diplotype",
        label="Diplotype rows",
        definition="some row has `is_diplotype` true; it is scored as a single allele",
        code="`just_prs.scoring.SCORING_FILE_SCHEMA` reads `is_diplotype`; `just_prs.vcf.compute_dosage_expr` counts "
        "one allele",
    ),
    Rule(
        key="multiplicative",
        label="Multiplicative odds ratios",
        definition=f"the weight type is an odds ratio '{MULTIPLICATIVE_WEIGHT_TYPE}', which the authors multiply; "
        "just-prs sums weight times dosage",
        code="`just_prs.prs.compute_prs` (score = sum of weight x dosage)",
    ),
    Rule(
        key="dosage_weights_ignored",
        label="Per-dosage weights ignored",
        definition="the file has both `effect_weight` and `dosage_0/1/2_weight`; just-prs uses `effect_weight`",
        code="`just_prs.prs.is_dosage_weight_format` (per-dosage weights only when `effect_weight` is absent)",
    ),
    Rule(
        key="effect_is_other",
        label="Effect allele equal to the other allele",
        definition="at least the threshold share of absolute weight sits on placed rows whose effect allele equals the "
        "other allele, so the file does not say which allele carries the weight",
        code="`just_prs.vcf.compute_dosage_expr` reads only `effect_allele`",
    ),
)


def _is_null(column: str) -> pl.Expr:
    return pl.col(column).is_null() | pl.col(column).str.strip_chars().is_in(NULL_CELLS)


def _is_true(column: str, columns: list[str]) -> pl.Expr:
    if column not in columns:
        return pl.lit(False)
    return pl.col(column).str.strip_chars().is_in(TRUE_CELLS).fill_null(False)


def _number(column: str) -> pl.Expr:
    return pl.when(_is_null(column)).then(None).otherwise(pl.col(column).str.strip_chars().cast(pl.Float64, strict=False))


def read_header(path: Path) -> tuple[dict[str, str], list[str]]:
    """`#key=value` header lines (parsed as `just_prs.scoring._parse_scoring_header` does) and the column names."""
    header: dict[str, str] = {}
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("#"):
                key, sep, value = line.strip().lstrip("#").partition("=")
                if sep and key.strip() and value.strip():
                    header.setdefault(key.strip(), value.strip())
                continue
            return header, [c.strip() for c in line.rstrip("\r\n").split("\t")]
    return header, []


def _position_columns(columns: list[str]) -> Optional[tuple[str, str]]:
    """The pair `just_prs.prs._normalize_scoring_columns` reads: harmonized first, else the author's."""
    for pair in (("hm_chr", "hm_pos"), ("chr_name", "chr_position")):
        if all(c in columns for c in pair):
            return pair
    return None


def _example_label(effect: pl.Expr, columns: list[str]) -> pl.Expr:
    """The effect allele, followed by the row's variant name when that is not an rsID (`P (HLA-B*2705)`)."""
    if "rsID" not in columns:
        return effect.fill_null("(empty)")
    rsid = pl.col("rsID").str.strip_chars()
    named = rsid.is_not_null() & ~rsid.is_in(NULL_CELLS) & ~rsid.str.starts_with("rs")
    allele = effect.fill_null("(empty)")
    return pl.when(named).then(pl.concat_str([allele, pl.lit(" ("), rsid, pl.lit(")")])).otherwise(allele)


def measure_file(path: Path, pgs_id: str) -> FileMeasure:
    """Read every row of one harmonized scoring file and sort it into the classes of `FileMeasure`."""
    header, columns = read_header(path)
    positions = _position_columns(columns)
    dosage_only = all(c in columns for c in DOSAGE_COLUMNS) and "effect_weight" not in columns
    weight_columns = list(DOSAGE_COLUMNS) if dosage_only else ["effect_weight"] if "effect_weight" in columns else []
    wanted = [c for c in (*(positions or ()), "rsID", "effect_allele", "other_allele", *weight_columns, *FLAG_COLUMNS) if c in columns]
    frame = pl.read_csv(
        path, separator="\t", comment_prefix="#", infer_schema=False, quote_char=None, columns=wanted,
        truncate_ragged_lines=True, encoding="utf8-lossy",
    )
    if positions is None:
        placed = pl.lit(False)
    else:
        placed = ~_is_null(positions[0]) & _number(positions[1]).is_not_null()
    effect = pl.col("effect_allele").str.strip_chars() if "effect_allele" in columns else pl.lit(None, dtype=pl.String)
    other = pl.col("other_allele").str.strip_chars() if "other_allele" in columns else pl.lit(None, dtype=pl.String)
    nucleotide = effect.str.contains(NUCLEOTIDES).fill_null(False)
    if dosage_only:
        weight = pl.max_horizontal(*(_number(c).abs() for c in DOSAGE_COLUMNS))
    elif weight_columns:
        weight = _number("effect_weight").abs()
    else:
        weight = pl.lit(None, dtype=pl.Float64)
    row_class = (
        pl.when(~placed).then(pl.lit("unplaced"))
        .when(~nucleotide).then(pl.lit("non_nucleotide"))
        .when((effect == other).fill_null(False)).then(pl.lit("effect_is_other"))
        .otherwise(pl.lit("scored"))
    )
    flagged = pl.any_horizontal(*(_is_true(c, columns) for c in FLAG_COLUMNS))
    rows = frame.select(
        row_class.alias("cls"),
        weight.alias("w"),
        flagged.alias("flagged"),
        _example_label(effect, columns).alias("effect"),
        nucleotide.alias("nucleotide"),
        *(_is_true(c, columns).alias(c) for c in FLAG_COLUMNS),
    )
    totals = rows.select(
        pl.len().alias("rows"),
        pl.col("w").is_null().sum().alias("rows_weight_missing"),
        pl.col("w").fill_null(0.0).sum().alias("weight_total"),
        ((pl.col("cls") == "scored") & pl.col("flagged")).sum().alias("rows_scored_flagged"),
        pl.col("w").filter((pl.col("cls") == "scored") & pl.col("flagged")).fill_null(0.0).sum().alias("weight_scored_flagged"),
        *(pl.col(c).sum().alias(f"rows_{c.removeprefix('is_')}") for c in FLAG_COLUMNS),
        *(
            expr
            for name in ("unplaced", "non_nucleotide", "effect_is_other", "scored")
            for expr in (
                (pl.col("cls") == name).sum().alias(f"rows_{name}"),
                pl.col("w").filter(pl.col("cls") == name).fill_null(0.0).sum().alias(f"weight_{name}"),
            )
        ),
    ).row(0, named=True)
    examples = (
        rows.filter(pl.col("cls").is_in(["unplaced", "non_nucleotide"]))
        .group_by("effect")
        .agg(pl.col("w").fill_null(0.0).sum())
        .sort(["w", "effect"], descending=[True, False])
        .head(EXAMPLES)["effect"]
        .to_list()
    )
    return FileMeasure(
        pgs_id=pgs_id,
        gz_bytes=path.stat().st_size,
        header_weight_type=header.get("weight_type"),
        header_genome_build=header.get("genome_build"),
        hm_build=header.get("HmPOS_build"),
        hm_date=header.get("HmPOS_date"),
        columns=columns,
        position_columns="/".join(positions) if positions else None,
        weight_source="dosage_k_weight (largest)" if dosage_only else "effect_weight" if weight_columns else "none",
        has_effect_weight="effect_weight" in columns,
        has_dosage_weights=all(c in columns for c in DOSAGE_COLUMNS),
        rows_unplaced_non_nucleotide=rows.filter((pl.col("cls") == "unplaced") & ~pl.col("nucleotide")).height,
        unplaceable_examples=examples,
        **{k: (float(v) if k.startswith("weight_") else int(v)) for k, v in totals.items()},
    )


RETRY_STATUS = (429, 500, 502, 503, 504)


def _get_json(session: requests.Session, url: str, attempts: int = 7) -> dict:
    """GET a REST page, backing off (1 s, 2 s, ... 32 s) while the server answers busy."""
    for attempt in range(attempts):
        response = session.get(url, timeout=120)
        if response.status_code not in RETRY_STATUS or attempt == attempts - 1:
            break
        time.sleep(2**attempt)
    response.raise_for_status()
    return response.json()


def fetch_release_info() -> dict:
    """The Catalog's `latest_release` block (date and counts)."""
    with requests.Session() as session:
        return _get_json(session, f"{REST_URL}/info")["latest_release"]


def fetch_catalog(build: str) -> CatalogRelease:
    """The current release and every score's metadata, read from the Catalog's REST API.

    Refuses when the release changed during the listing, or when the listing and the release disagree on
    the number of scores, so one scan never mixes two releases.
    """
    fetched_at = datetime.now(timezone.utc)
    with requests.Session() as session:
        info = _get_json(session, f"{REST_URL}/info")
        scores: list[CatalogScore] = []
        url: Optional[str] = f"{REST_URL}/score/all?limit=250"
        while url:
            page = _get_json(session, url)
            for record in page["results"]:
                scores.append(
                    CatalogScore(
                        pgs_id=record["id"],
                        name=record["name"],
                        weight_type=record.get("weight_type"),
                        variants_number=record.get("variants_number"),
                        variants_interactions=record.get("variants_interactions") or 0,
                        method_name=record.get("method_name"),
                        date_release=record.get("date_release"),
                        harmonized_url=record["ftp_harmonized_scoring_files"][build]["positions"],
                    )
                )
            url = page.get("next")
        after = _get_json(session, f"{REST_URL}/info")
    release = info["latest_release"]
    if after["latest_release"] != release:
        raise RuntimeError(f"the Catalog released during the listing ({release['date']} -> {after['latest_release']['date']}); scan again")
    ids = [s.pgs_id for s in scores]
    if len(ids) != len(set(ids)) or len(ids) != release["scores"]:
        raise RuntimeError(f"the listing holds {len(set(ids))} distinct scores, the release says {release['scores']}")
    return CatalogRelease(
        release_date=release["date"],
        release_score_count=release["scores"],
        rest_api_version=info.get("rest_api", {}).get("version"),
        fetched_at=fetched_at,
        build=build,
        scores=sorted(scores, key=lambda s: s.pgs_id),
    )


def cached_path(cache_dir: Path, score: CatalogScore) -> Path:
    return cache_dir / score.harmonized_url.rsplit("/", 1)[1]


def download(score: CatalogScore, cache_dir: Path, attempts: int = 5) -> Path:
    """The harmonized file in `cache_dir`, downloaded whole (`.part`, length-checked, renamed) if absent."""
    target = cached_path(cache_dir, score)
    if target.is_file():
        return target
    part = target.with_name(target.name + ".part")
    last: Optional[Exception] = None
    for attempt in range(attempts):
        try:
            if last is not None:
                time.sleep(2 ** min(attempt, 5))
            with requests.get(score.harmonized_url, stream=True, timeout=300) as response:
                response.raise_for_status()
                expected = int(response.headers.get("Content-Length", "-1"))
                with part.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1 << 20):
                        handle.write(chunk)
            if expected >= 0 and part.stat().st_size != expected:
                raise OSError(f"{score.pgs_id}: got {part.stat().st_size} bytes of {expected}")
            part.replace(target)
            return target
        except (requests.RequestException, OSError) as exc:
            last = exc
    raise RuntimeError(f"{score.pgs_id}: download failed after {attempts} attempts: {last}")


def read_measures(path: Path) -> dict[str, FileMeasure]:
    if not path.is_file():
        return {}
    measures = (FileMeasure.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return {m.pgs_id: m for m in measures}


def scan(
    release: CatalogRelease,
    work_dir: Path,
    cache_dir: Path,
    downloads: int,
    workers: int,
    progress: Callable[[str], None],
) -> list[str]:
    """Download and measure every score of `release` not yet in `work_dir`; returns the IDs that failed."""
    measures_path = work_dir / MEASURES_JSONL
    done = read_measures(measures_path)
    todo = [s for s in release.scores if s.pgs_id not in done]
    progress(f"{len(done)} measured, {len(todo)} to go")
    failed: list[str] = []
    cache_dir.mkdir(parents=True, exist_ok=True)
    context = multiprocessing.get_context("spawn")  # never fork after Polars (docs/GRANIAN_POLARS_FORK_DEADLOCK.md)
    with (
        ThreadPoolExecutor(max_workers=downloads) as fetchers,
        ProcessPoolExecutor(max_workers=workers, mp_context=context) as measurers,
        measures_path.open("a", encoding="utf-8") as sink,
    ):
        fetched = {fetchers.submit(download, score, cache_dir): score for score in todo}
        measuring: dict[Future, CatalogScore] = {}
        pending: set[Future] = set(fetched)
        measured = 0
        while pending:
            finished, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in finished:
                score = fetched.get(future) or measuring[future]
                if future.exception() is not None:
                    failed.append(score.pgs_id)
                    progress(f"failed {score.pgs_id}: {future.exception()}")
                elif future in fetched:
                    job = measurers.submit(measure_file, future.result(), score.pgs_id)
                    measuring[job] = score
                    pending.add(job)
                else:
                    sink.write(future.result().model_dump_json() + "\n")
                    sink.flush()
                    measured += 1
                    if measured % 250 == 0:
                        progress(f"measured {measured} of {len(todo)}")
    return sorted(failed)


def write_catalog(path: Path, release: CatalogRelease) -> None:
    path.write_text(release.model_dump_json(indent=1) + "\n", encoding="utf-8")


def read_catalog(path: Path) -> CatalogRelease:
    return CatalogRelease.model_validate_json(path.read_text(encoding="utf-8"))


class Classified(BaseModel):
    """One scoring file with its category, the rules it met, and its weight split into shares."""

    model_config = ConfigDict(frozen=True)

    score: CatalogScore
    measure: FileMeasure
    category: str
    reasons: tuple[str, ...]
    share_unplaceable: float
    share_unplaced: float
    share_non_nucleotide: float
    share_effect_is_other: float
    share_scored_flagged: float
    share_scored_plain: float


def _share(part: float, total: float) -> float:
    return part / total if total > 0 else 0.0


def classify(score: CatalogScore, measure: FileMeasure, threshold: float = DEFAULT_THRESHOLD) -> Classified:
    """Sort one file into `CATEGORIES` by `RULES`, every rule read from the file or the Catalog metadata.

    A file *cannot be scored* when no row carries weight just-prs could apply as written: every row is
    unplaced, non-nucleotide, or names the effect allele as the other allele too. A file is
    *approximated* when it meets any rule in `RULES` (the two share rules at `threshold`), and *as
    specified* otherwise. Weight shares are of the file's total absolute weight, so they sum to 1.
    """
    total = measure.weight_total
    unplaceable = _share(measure.weight_unplaced + measure.weight_non_nucleotide, total)
    effect_is_other = _share(measure.weight_effect_is_other, total)
    met = {
        "unplaceable_weight": unplaceable >= threshold,
        "dominant_recessive": measure.rows_dominant + measure.rows_recessive > 0,
        "interaction": measure.rows_interaction > 0 or score.variants_interactions > 0,
        "diplotype": measure.rows_diplotype > 0,
        "multiplicative": MULTIPLICATIVE_WEIGHT_TYPE in (score.weight_type or "").lower(),
        "dosage_weights_ignored": measure.has_effect_weight and measure.has_dosage_weights,
        "effect_is_other": effect_is_other >= threshold,
    }
    reasons = tuple(rule.key for rule in RULES if met[rule.key])
    if measure.rows_scored == 0 or measure.weight_scored <= 0:
        category = CANNOT_SCORE
    elif reasons:
        category = APPROXIMATED
    else:
        category = AS_SPECIFIED
    return Classified(
        score=score,
        measure=measure,
        category=category,
        reasons=reasons,
        share_unplaceable=unplaceable,
        share_unplaced=_share(measure.weight_unplaced, total),
        share_non_nucleotide=_share(measure.weight_non_nucleotide, total),
        share_effect_is_other=effect_is_other,
        share_scored_flagged=_share(measure.weight_scored_flagged, total),
        share_scored_plain=_share(measure.weight_scored - measure.weight_scored_flagged, total),
    )


def classify_release(release: CatalogRelease, measures: dict[str, FileMeasure], threshold: float = DEFAULT_THRESHOLD) -> list[Classified]:
    """Every score of the release, classified; refuses when a score was not measured or a measure is not in the release."""
    ids = {s.pgs_id for s in release.scores}
    missing = sorted(ids - set(measures))
    extra = sorted(set(measures) - ids)
    if missing or extra:
        raise ValueError(f"measures do not match release {release.release_date}: missing {missing[:10]}, not in the release {extra[:10]}")
    return [classify(score, measures[score.pgs_id], threshold) for score in release.scores]


class Sensitivity(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: str
    threshold: Optional[float]
    over_threshold: int
    approximated: int
    as_specified: int
    cannot: int


def sensitivity(release: CatalogRelease, measures: dict[str, FileMeasure], thresholds: Iterable[float] = SENSITIVITY_THRESHOLDS) -> list[Sensitivity]:
    """The category counts when the two share rules use each threshold, plus 'any weight at all' (> 0)."""
    rows = []
    for threshold in (None, *thresholds):
        # `None` means any nonzero share: the smallest positive float meets it, zero does not
        files = classify_release(release, measures, threshold if threshold is not None else 5e-324)
        over = sum(1 for f in files if f.category != CANNOT_SCORE and "unplaceable_weight" in f.reasons)
        rows.append(
            Sensitivity(
                label="any (> 0)" if threshold is None else f"{threshold:.0%}",
                threshold=threshold,
                over_threshold=over,
                approximated=sum(1 for f in files if f.category == APPROXIMATED),
                as_specified=sum(1 for f in files if f.category == AS_SPECIFIED),
                cannot=sum(1 for f in files if f.category == CANNOT_SCORE),
            )
        )
    return rows


def _pct(value: float) -> str:
    """A share as a percentage that never rounds to 0% or 100% unless it is exactly that."""
    if value == 0 or value == 1:
        return f"{value:.0%}"
    if value < 0.001:
        return "<0.1%"
    if value >= 0.9995:
        return ">99.9%"
    return f"{value:.1%}"


def _unplaceable_text(f: Classified) -> str:
    m = f.measure
    what = []
    if m.rows_unplaced:
        alleles = f", {m.rows_unplaced_non_nucleotide:,} of them with a non-nucleotide allele" if m.rows_unplaced_non_nucleotide else ""
        what.append(f"{_rows(m.rows_unplaced)} without a position{alleles}")
    if m.rows_non_nucleotide:
        what.append(f"{m.rows_non_nucleotide:,} placed {'row' if m.rows_non_nucleotide == 1 else 'rows'} with a non-nucleotide allele")
    examples = f" (alleles: {', '.join(f'`{e}`' for e in m.unplaceable_examples)})" if m.unplaceable_examples else ""
    return f"{_pct(f.share_unplaceable)} of weight unplaceable: {'; '.join(what)}{examples}"


def _reason_text(f: Classified) -> str:
    m = f.measure
    parts = []
    for key in f.reasons:
        if key == "unplaceable_weight":
            parts.append(_unplaceable_text(f))
        elif key == "dominant_recessive":
            parts.append(f"{m.rows_dominant:,} dominant / {m.rows_recessive:,} recessive rows scored additively")
        elif key == "interaction":
            in_file = f"{m.rows_interaction:,} interaction rows in the file" if m.rows_interaction else "no interaction row in the file"
            parts.append(f"interaction terms left out (Catalog metadata: {f.score.variants_interactions}; {in_file})")
        elif key == "diplotype":
            parts.append(f"{m.rows_diplotype:,} diplotype rows scored as single alleles")
        elif key == "multiplicative":
            parts.append(f"weight type '{f.score.weight_type}': odds ratios summed, not multiplied")
        elif key == "dosage_weights_ignored":
            parts.append("per-dosage weights present, `effect_weight` used")
        elif key == "effect_is_other":
            parts.append(f"{m.rows_effect_is_other:,} rows ({_pct(f.share_effect_is_other)} of weight) with effect allele = other allele")
    if f.category == CANNOT_SCORE and m.rows_effect_is_other and "effect_is_other" not in f.reasons:
        parts.append(f"{m.rows_effect_is_other:,} of {m.rows:,} rows name the same allele as effect and other allele")
    if not parts and f.share_unplaceable > 0:
        parts.append(_unplaceable_text(f))
    return "; ".join(parts)


def _rows(n: int) -> str:
    return f"{n:,} row" if n == 1 else f"{n:,} rows"


def _files(n: int) -> str:
    return f"{n:,} file" if n == 1 else f"{n:,} files"


def _detail_table(files: list[Classified]) -> list[str]:
    lines = [
        "| PGS ID | Name | Rows | Unplaceable rows | Weight unplaceable | Weight effect = other | Weight on flagged rows | Reason |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for f in files:
        m = f.measure
        lines.append(
            f"| {m.pgs_id} | {f.score.name} | {m.rows:,} | {m.rows_unplaced + m.rows_non_nucleotide:,} | {_pct(f.share_unplaceable)} | "
            f"{_pct(f.share_effect_is_other)} | {_pct(f.share_scored_flagged)} | {_reason_text(f)} |"
        )
    return lines


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def render_markdown(
    release: CatalogRelease,
    files: list[Classified],
    table: list[Sensitivity],
    threshold: float = DEFAULT_THRESHOLD,
) -> str:
    total = len(files)
    by_category = {c: [f for f in files if f.category == c] for c in CATEGORIES}
    rows_read = sum(f.measure.rows for f in files)
    lines = [
        "# Supplementary Table S5. PGS Catalog coverage of just-prs",
        "",
        f"PGS Catalog release of {release.release_date} ({release.release_score_count:,} scores), listed through the "
        f"Catalog REST API (version {release.rest_api_version or 'not reported'}) at "
        f"{release.fetched_at.strftime('%Y-%m-%d %H:%M UTC')}. Every score's harmonized scoring file for "
        f"{release.build} (`hmPOS_{release.build}`) was downloaded and read in full: {rows_read:,} rows in "
        f"{total:,} files, no sampling. The scoring engine described is {JUST_PRS}.",
        "",
        "## Method",
        "",
        "just-prs computes every score as an additive sum: for each row, the dosage of the effect allele (0, 1 or 2 "
        "copies, counted against the VCF's REF and ALT) times the row's weight. Each row of each file is sorted into "
        "exactly one class, in this order:",
        "",
        "1. **Unplaced**: no usable harmonized position (`hm_chr` or `hm_pos` empty), so the row joins no VCF record.",
        "2. **Non-nucleotide**: placed, but the effect allele is not a string of A, C, G and T (HLA allele names, "
        "P/N, +/-, D/I, `<CN0>`, `<INS:ME:ALU>`, star alleles), so it never equals a VCF allele.",
        "3. **Effect = other**: placed and nucleotide, but the effect allele equals the other allele, so the file "
        "does not say which allele carries the weight.",
        "4. **Scored**: everything else. Scored rows flagged `is_dominant`, `is_recessive`, `is_interaction`, "
        "`is_diplotype` or `is_haplotype` are counted apart, because just-prs scores them as plain additive alleles.",
        "",
        "Shares are of the file's total absolute weight (`|effect_weight|`; for a file with only per-dosage weights, the "
        "largest of `|dosage_0/1/2_weight|`, as just-prs's weight-mass coverage does), so the four shares of a file sum "
        "to 1. *Unplaceable* below is classes 1 and 2 together: rows that cannot be placed or matched. Weights are on "
        "each file's own scale, so shares are compared across files and weights never are. A row with no weight "
        f"counts as zero weight, as it adds nothing to a just-prs score ({sum(f.measure.rows_weight_missing for f in files):,} "
        f"rows in {sum(1 for f in files if f.measure.rows_weight_missing):,} files).",
        "",
        "## Categories",
        "",
        f"- **{CANNOT_SCORE.capitalize()}**: no row is left in class 4 with nonzero weight, so no result could follow "
        "the file.",
        f"- **{APPROXIMATED.capitalize()}**: the file can be scored, but meets at least one rule below; the share rules "
        f"use a threshold of {threshold:.0%} of absolute weight.",
        f"- **{AS_SPECIFIED.capitalize()}**: neither. A file in this category can still lose up to {threshold:.0%} of "
        "its weight to unplaceable rows; the threshold sensitivity table and the CSV give every file's share.",
        "",
        "| Rule | Definition | just-prs code |",
        "|---|---|---|",
        *(f"| {r.label} | {r.definition} | {r.code} |" for r in RULES),
        "",
        "## Summary",
        "",
        f"| Category | Files | % of {total:,} | Mean share of weight scored plainly | Mean on flagged rows | Mean effect = other | "
        "Mean unplaceable | Median unplaceable | Max unplaceable |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for category in CATEGORIES:
        group = by_category[category]
        unplaceable = [f.share_unplaceable for f in group]
        lines.append(
            f"| {category.capitalize()} | {len(group):,} | {len(group) / total:.1%} | {_pct(_mean([f.share_scored_plain for f in group]))} | "
            f"{_pct(_mean([f.share_scored_flagged for f in group]))} | {_pct(_mean([f.share_effect_is_other for f in group]))} | "
            f"{_pct(_mean(unplaceable))} | {_pct(_median(unplaceable))} | {_pct(max(unplaceable, default=0.0))} |"
        )
    lines += [f"| Total | {total:,} | 100% | | | | | | |", ""]
    approximated = by_category[APPROXIMATED]
    lines += [
        "Files meeting each rule (a file can meet several; the category column counts each file once):",
        "",
        "| Rule | Files that can be scored | Of which meet no other rule | Files that cannot be scored |",
        "|---|---|---|---|",
    ]
    for rule in RULES:
        hits = [f for f in approximated if rule.key in f.reasons]
        alone = [f for f in hits if f.reasons == (rule.key,)]
        cannot = [f for f in by_category[CANNOT_SCORE] if rule.key in f.reasons]
        lines.append(f"| {rule.label} | {len(hits):,} | {len(alone):,} | {len(cannot):,} |")
    lines += [
        "",
        "## Threshold sensitivity",
        "",
        "The two share rules (unplaceable weight, effect = other) at other thresholds. *Over threshold* counts the "
        "files that can be scored and whose unplaceable share reaches the threshold; the category counts include the "
        "files that meet the other rules regardless of threshold.",
        "",
        "| Threshold | Over threshold (unplaceable) | Approximated | As specified | Cannot be scored |",
        "|---|---|---|---|---|",
        *(
            f"| {s.label}{' (used here)' if s.threshold == threshold else ''} | {s.over_threshold:,} | {s.approximated:,} | "
            f"{s.as_specified:,} | {s.cannot:,} |"
            for s in table
        ),
        "",
        f"![Per-file share of absolute weight on unplaceable rows]({FIGURE_STEM}.svg)",
        "",
        f"*Figure S5.* Per-file share of absolute weight on rows just-prs cannot place or match, in quarter-decade "
        f"bins, for the {sum(1 for f in files if f.share_unplaceable > 0):,} files where it is above zero (the "
        f"{sum(1 for f in files if 0 < f.share_unplaceable < FIGURE_FLOOR):,} below {FIGURE_FLOOR * 100:g}% are counted in "
        f"the first bin, and the other {sum(1 for f in files if f.share_unplaceable == 0):,} files lose no weight this "
        f"way), with the sensitivity thresholds dashed and the {threshold:.0%} threshold used drawn solid.",
        "",
    ]
    for category in (CANNOT_SCORE, APPROXIMATED):
        group = sorted(by_category[category], key=lambda f: f.measure.pgs_id)
        lines += [f"## {category.capitalize()} ({_files(len(group))})", "", *_detail_table(group), ""]
    plain = by_category[AS_SPECIFIED]
    near = sorted((f for f in plain if f.share_unplaceable >= SENSITIVITY_THRESHOLDS[0]), key=lambda f: -f.share_unplaceable)
    lines += [
        f"## {AS_SPECIFIED.capitalize()} ({_files(len(plain))})",
        "",
        f"{sum(1 for f in plain if f.share_unplaceable == 0):,} lose no weight to unplaceable rows; "
        f"{sum(1 for f in plain if 0 < f.share_unplaceable < SENSITIVITY_THRESHOLDS[0]):,} lose less than "
        f"{SENSITIVITY_THRESHOLDS[0]:.0%}; the {len(near):,} below lose between {SENSITIVITY_THRESHOLDS[0]:.0%} and "
        f"{threshold:.0%}, and would move to *approximated* at a lower threshold. Every file is in `{CSV_NAME}`.",
        "",
        *(_detail_table(near) if near else []),
        "",
    ]
    return "\n".join(lines)


CSV_COLUMNS = (
    "catalog_release", "listed_at_utc", "build", "pgs_id", "name", "category", "reasons", "catalog_weight_type",
    "catalog_variants_number", "catalog_variants_interactions", "rows", "rows_unplaced", "rows_non_nucleotide",
    "rows_effect_is_other", "rows_scored", "rows_scored_flagged", "rows_weight_missing", "rows_dominant", "rows_recessive",
    "rows_interaction", "rows_diplotype", "rows_haplotype", "share_unplaceable", "share_unplaced", "share_non_nucleotide",
    "share_effect_is_other", "share_scored_flagged", "share_scored_plain", "rows_unplaced_non_nucleotide",
    "unplaceable_examples", "weight_source",
    "has_effect_weight", "has_dosage_weights", "position_columns", "hm_date", "gz_bytes",
)


def coverage_frame(release: CatalogRelease, files: list[Classified]) -> pl.DataFrame:
    """One row per PGS ID with every measure, share and the category: the CSV."""
    return pl.DataFrame(
        [
            {
                "catalog_release": release.release_date,
                "listed_at_utc": release.fetched_at.isoformat(),
                "build": release.build,
                "pgs_id": f.score.pgs_id,
                "name": f.score.name,
                "category": f.category,
                "reasons": ";".join(f.reasons),
                "catalog_weight_type": f.score.weight_type,
                "catalog_variants_number": f.score.variants_number,
                "catalog_variants_interactions": f.score.variants_interactions,
                **{c: getattr(f.measure, c) for c in CSV_COLUMNS if c.startswith("rows")},
                **{c: getattr(f, c) for c in CSV_COLUMNS if c.startswith("share_")},
                "unplaceable_examples": ";".join(f.measure.unplaceable_examples),
                "weight_source": f.measure.weight_source,
                "has_effect_weight": f.measure.has_effect_weight,
                "has_dosage_weights": f.measure.has_dosage_weights,
                "position_columns": f.measure.position_columns,
                "hm_date": f.measure.hm_date,
                "gz_bytes": f.measure.gz_bytes,
            }
            for f in files
        ],
        infer_schema_length=None,
    ).select(CSV_COLUMNS)


def write_csv(path: Path, frame: pl.DataFrame) -> None:
    frame.with_columns(pl.col(c).round(9) for c in CSV_COLUMNS if c.startswith("share_")).write_csv(path, line_terminator="\n")


def write_histogram(stem: Path, files: list[Classified], threshold: float = DEFAULT_THRESHOLD) -> list[Path]:
    """`stem`.svg and `stem`.png: histogram of the nonzero unplaceable shares in quarter-decade bins.

    Shares below `FIGURE_FLOOR` are counted in the first bin (the annotation says how many), so the
    axis spends its width where the thresholds are. Bars from the lowest threshold up carry their count.
    """
    if Figure is None:
        raise RuntimeError("matplotlib is not installed; it is in the dev dependency group (`uv sync --group dev`)")
    shares = sorted(f.share_unplaceable for f in files if f.share_unplaceable > 0)
    zero = sum(1 for f in files if f.share_unplaceable == 0)
    below = sum(1 for s in shares if s < FIGURE_FLOOR)
    decades = round(-math.log10(FIGURE_FLOOR))
    edges = [FIGURE_FLOOR * 10 ** (k / 4) for k in range(4 * decades + 1)]
    rcParams["svg.hashsalt"] = "s5"
    rcParams["font.family"] = "DejaVu Sans"
    fig = Figure(figsize=(7.0, 3.6), dpi=200)
    ax = fig.add_subplot()
    counts, _, _ = ax.hist([max(s, FIGURE_FLOOR) for s in shares], bins=edges, color="#6b6b6b", edgecolor="white", linewidth=0.8)
    for left, right, count in zip(edges, edges[1:], counts):
        if count and left >= SENSITIVITY_THRESHOLDS[0] * 0.999:
            ax.text(math.sqrt(left * right), count, f"{int(count)}", ha="center", va="bottom", fontsize=7, color="#333333")
    ax.set_xscale("log")
    ax.set_xlim(edges[0], 1.0)
    ax.set_xlabel("Share of the file's absolute weight on unplaceable rows (log scale)")
    ax.set_ylabel("Scoring files (count)")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value * 100:g}%"))
    for value in SENSITIVITY_THRESHOLDS:
        used = value == threshold
        ax.axvline(value, color="#111111" if used else "#8a8a8a", linewidth=1.6 if used else 0.9, linestyle="-" if used else (0, (4, 3)))
        ax.text(value, 1.01, f"{value:.0%}", transform=ax.get_xaxis_transform(), ha="center", va="bottom", fontsize=8,
                color="#111111", fontweight="bold" if used else "normal")
    floor = f"{FIGURE_FLOOR * 100:g}%"
    ax.text(
        0.40, 0.96,
        f"{len(shares):,} files above zero;\n{below:,} of them below {floor},\ncounted in the first bin\n"
        f"{zero:,} files at zero, not shown\nsolid line: {threshold:.0%} (used)\ndashed: sensitivity",
        transform=ax.transAxes, ha="left", va="top", fontsize=7, color="#333333", linespacing=1.4,
    )
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(labelsize=8)
    ax.xaxis.label.set_size(9)
    ax.yaxis.label.set_size(9)
    fig.tight_layout()
    paths = [stem.with_suffix(".svg"), stem.with_suffix(".png")]
    fig.savefig(paths[0], format="svg", metadata={"Date": None})
    fig.savefig(paths[1], format="png", metadata={"Software": None})
    return paths
