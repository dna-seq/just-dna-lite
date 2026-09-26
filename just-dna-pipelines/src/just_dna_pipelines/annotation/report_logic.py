"""
Report generation logic for annotation modules.

Reads annotated parquet files produced by the HF module annotation pipeline,
enriches them with annotations and studies data from HuggingFace,
and renders HTML reports using Jinja2 templates.
"""

import re
import urllib.parse
from pathlib import Path
from typing import Optional

import jinja2
import polars as pl
from eliot import log_message, start_action
from just_dna_format.alleles import split_genotype
from just_dna_format.derive import clin_sig_from_booleans, direction_from_state
from just_dna_format.manifest import read_manifest
from just_dna_format.vocab import RSID_PATTERN

from just_dna_pipelines.annotation.analytics import umami_script_tag
from just_dna_pipelines.annotation.hf_modules import (
    DISCOVERED_MODULES,
    AnnotationManifest,
    ModuleInfo,
    ModuleOutputMapping,
    ModuleTable,
    discover_hf_modules,
    local_module_dir,
    module_kind,
    scan_module_table,
)
from just_dna_pipelines.annotation.phenotype_caller import load_phenotype_definition
from just_dna_pipelines.annotation.restoration import (
    EVIDENCE_COLUMN,
    EVIDENCE_RESTORED,
    FLANK_COLUMN,
)
from just_dna_pipelines.module_config import (
    MODULES_CONFIG,
    build_display_names_dict,
    get_module_description,
    get_module_display_name,
)

ANNOTATION_REPORT_COLUMNS: tuple[str, ...] = ("gene", "category", "phenotype")
# How many rows a report table shows before the reader opens the rest. The template reads this
# for both the pre-collapsed markup and the inline JS constant, so the two cannot drift apart.
TABLE_PREVIEW_ROWS: int = 10
GENERIC_REPORT_TITLE = "Genomic Annotation Report"
# The privacy notice for an AI button lives in its tooltip, not beside it: an inline sentence dwarfs
# a 28 px icon and wrecks the layout, and the notice belongs to the action, so hover and screen
# readers (aria-label) carry it. The bottom "How to read this report" section explains it in full.
_AI_PRIVACY_NOTE = "Opens {provider} with a prompt containing your DNA letters at these positions; nothing is sent until you click."

AI_EXPLAIN_ASSISTANTS: tuple[tuple[str, str], ...] = (
    ("ChatGPT", "https://chatgpt.com/?q="),
    ("Claude", "https://claude.ai/new?q="),
    ("Perplexity", "https://www.perplexity.ai/search?q="),
    ("Grok", "https://grok.com/?q="),
)


def report_title_for_modules(module_names: list[str]) -> str:
    """Return a report-level title that does not imply an unrelated module.

    A single-module run can use that module's curated ``report_title``. A run
    containing several modules has no honest single-module title, so it uses a
    concise generic heading and keeps the full names on the module sections.
    """
    if len(module_names) == 1:
        return get_module_display_name(module_names[0])
    return GENERIC_REPORT_TITLE


def report_description_for_modules(module_names: list[str]) -> str:
    """Return the curated module description for a single-module report."""
    if len(module_names) == 1:
        return get_module_description(module_names[0])
    return (
        "What your DNA file shows for each of the modules you chose. Each section below is one "
        "module, with its results first and the evidence under More details."
    )


def report_filename_stem(module_names: list[str]) -> str:
    """Build a short, filesystem-safe stem from a single module's report title.

    At most two words are used so generated filenames stay easy to scan. Runs
    containing multiple modules deliberately use the neutral ``report`` stem.
    """
    if len(module_names) != 1:
        return "report"

    module_name = module_names[0]
    title_words = re.findall(r"[A-Za-z0-9]+", get_module_display_name(module_name))
    fallback_words = re.findall(r"[A-Za-z0-9]+", module_name)
    words = title_words or fallback_words
    return "_".join(word.lower() for word in words[:2]) or "report"


def _log_missing_module_table(module_name: str, table: ModuleTable, reason: str) -> None:
    """Log a non-fatal missing module table during report generation."""
    log_message(
        message_type="warning",
        action="missing_module_table_for_report",
        module=module_name,
        table=table.value,
        reason=reason,
    )


def _scan_optional_module_table(
    module_name: str,
    table: ModuleTable,
    module_info: Optional[ModuleInfo] = None,
) -> Optional[pl.LazyFrame]:
    """Scan a module table, returning None when optional report metadata is absent."""
    if module_info is not None:
        if table == ModuleTable.ANNOTATIONS and module_info.annotations_url is None:
            _log_missing_module_table(module_name, table, "module metadata has no annotations table")
            return None
        if table == ModuleTable.STUDIES and module_info.studies_url is None:
            _log_missing_module_table(module_name, table, "module metadata has no studies table")
            return None
        if table == ModuleTable.SOURCES and module_info.sources_url is None:
            _log_missing_module_table(module_name, table, "module metadata has no sources table")
            return None
        if table == ModuleTable.CONCORDANCE and module_info.concordance_url is None:
            _log_missing_module_table(
                module_name, table, "module metadata has no clin_sig_concordance table"
            )
            return None

    try:
        return scan_module_table(module_name, table, module_info=module_info)
    except ValueError as exc:
        _log_missing_module_table(module_name, table, str(exc))
        return None


def _ensure_annotation_report_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Ensure fallback report rows have nullable annotation metadata columns."""
    missing_columns = [
        pl.lit(None).cast(pl.String).alias(column)
        for column in ANNOTATION_REPORT_COLUMNS
        if column not in df.columns
    ]
    if not missing_columns:
        return df
    return df.with_columns(missing_columns)


def _annotated_rows(df: pl.DataFrame) -> pl.DataFrame:
    """Keep only rows that actually matched a module entry (were annotated).

    A match is marked by the module-annotation columns being populated after the
    annotation left-join — NOT by a non-null ``weight``. Weight-less modules
    (``superhuman``, the ClinVar gene panels ``cardio``/``cancer``/``pathogenic``)
    carry ``weight=None`` on every variant, so filtering on ``weight`` silently
    drops all of their matches and the report shows 0 annotated variants. Use the
    ``module`` name column (always set on a real match), falling back to
    ``conclusion``/``state`` and finally ``weight`` if those columns are absent.
    """
    for marker in ("module", "conclusion", "state"):
        if marker in df.columns:
            return df.filter(pl.col(marker).is_not_null())
    return df.filter(pl.col("weight").is_not_null())


# Longevity pathway categories and their display metadata
LONGEVITY_CATEGORIES: dict[str, dict[str, str]] = {
    "lipids": {
        "title": "Genes involved in lipid transfer and lipid signaling",
        "description": (
            "Lipids play crucial roles in regulating aging and longevity. "
            "They are fundamental structural elements of cellular membranes, "
            "key molecules in energy metabolism, and act as signaling molecules. "
            "Lipid metabolism is not considered a separate longevity pathway, but genes "
            "that regulate lipid transfer, like APOE and CETP, show the strongest "
            "association with longevity."
        ),
    },
    "insulin": {
        "title": "Genes involved in the insulin/IGF-1 signaling pathway",
        "description": (
            "The insulin/insulin-like growth factor (IGF-1) signaling pathway is a key "
            "regulator of metabolism, growth, and aging. It has been extensively studied "
            "in various model organisms and is thought to play an important role in human "
            "aging and longevity. This pathway is also involved in glucose metabolism."
        ),
    },
    "antioxidant": {
        "title": "Genes involved in antioxidant defense",
        "description": (
            "Antioxidant defense plays an important role in the aging process and longevity. "
            "Oxidative stress, caused by an imbalance between reactive oxygen species (ROS) "
            "and the body's ability to neutralize them, is a major contributor to age-related "
            "diseases. The body's antioxidant enzymes (SOD, catalase, glutathione peroxidase) "
            "and non-enzymatic antioxidants (vitamins C and E, glutathione) work together "
            "to neutralize ROS."
        ),
    },
    "mitochondria": {
        "title": "Genes related to mitochondria function",
        "description": (
            "Mitochondria are the powerhouses of the cell, generating ATP for cellular processes. "
            "Mitochondrial dysfunction and increased oxidative stress are believed to play a role "
            "in aging and age-related diseases. Genes involved in mitochondrial function include "
            "UCP genes, respiratory chain genes, SIRT3, PGC1a, and others. They determine how "
            "well you are protected from oxidative stress and how effectively your cells generate energy."
        ),
    },
    "sirtuin": {
        "title": "Genes related to the sirtuin pathway",
        "description": (
            "The sirtuin genes (SIRT1-SIRT7) are involved in regulating DNA repair, metabolism, "
            "and stress response. Activation of sirtuins can increase lifespan in several model "
            "organisms. In humans, variations in SIRT genes have been associated with age-related "
            "diseases such as Alzheimer's, cardiovascular disease, and cancer."
        ),
    },
    "mtor": {
        "title": "Genes related to mTOR pathway",
        "description": (
            "mTOR (mechanistic target of rapamycin) is a protein kinase involved in growth, "
            "metabolism, and aging. While activation promotes cellular growth, chronic activation "
            "has been implicated in age-related diseases. Inhibition of the mTOR pathway can "
            "extend lifespan in mice, flies, and worms."
        ),
    },
    "tumor-suppressor": {
        "title": "Tumor-suppressor genes",
        "description": (
            "Tumor suppressor genes and cell cycle regulators play an important role in aging "
            "and age-related diseases, including cancer. TP53 regulates cellular senescence and "
            "prevents accumulation of damaged cells. CDK dysregulation has been implicated in "
            "cancer and neurodegenerative disorders."
        ),
    },
    "renin-angiotensin": {
        "title": "Genes of the renin-angiotensin system",
        "description": (
            "The renin-angiotensin system (RAS) regulates blood pressure, fluid balance, and "
            "electrolyte homeostasis. RAS influences aging through oxidative stress activation, "
            "inflammation, and cardiovascular disease. It is also implicated in insulin resistance "
            "and regulation of cellular senescence."
        ),
    },
    "heat-shock": {
        "title": "Heat-shock protein genes",
        "description": (
            "HSP (heat shock protein) genes encode chaperone proteins that protect cells from "
            "stress-induced damage. HSPs are involved in protein folding, DNA repair, and apoptosis. "
            "They may help protect cells from accumulated damage caused by stress and environmental factors."
        ),
    },
    "inflammation": {
        "title": "Inflammation and related pathways",
        "description": (
            "Chronic inflammation is a major contributor to aging. It is characterized by sustained "
            "activation of the immune system and release of pro-inflammatory molecules (cytokines, "
            "chemokines, ROS). Chronic inflammation can also activate mTOR and senescence-associated "
            "secretory phenotype (SASP), further exacerbating tissue damage."
        ),
    },
    "genome_maintenance": {
        "title": "Genome maintenance and post-transcriptional processes",
        "description": (
            "Genome maintenance prevents DNA damage and mutations that lead to age-related diseases. "
            "Post-transcriptional processes (RNA splicing, translation, decay) regulate gene expression "
            "to ensure proteins are produced at appropriate levels. Dysregulation of these processes "
            "can lead to shortened lifespans."
        ),
    },
    "other": {
        "title": "Other genes associated with longevity",
        "description": (
            "Although many longevity-associated genes can be classified into definite pathways, "
            "there are other genes that do not fall into these categories."
        ),
    },
}


def _weight_color(weight: float) -> str:
    """Return a CSS color for a weight value. Positive = green, negative = red."""
    if weight > 0:
        intensity = min(int(abs(weight) * 200), 200)
        return f"rgba(0, {100 + intensity}, 0, 0.3)"
    elif weight < 0:
        intensity = min(int(abs(weight) * 200), 200)
        return f"rgba({100 + intensity}, 0, 0, 0.3)"
    return "transparent"


def _effective_direction(
    direction: Optional[str], state: Optional[str], weight: Optional[float]
) -> str:
    """The 0.3 `direction` axis for a **parquet** row, robust across the format transition.

    Mirrors ``VariantRow.effective_direction`` (a Python-only accessor) for a row read from
    ``weights.parquet`` with SQL/polars: the authored ``direction`` column when it carries a value,
    else derived from the legacy ``state`` (+ ``weight`` sign) via the format's own pure leaf
    ``direction_from_state``. Legacy/0.5 modules leave ``direction`` empty and populate ``state``;
    format 1.0 drops ``state`` and populates ``direction`` — deriving here keeps a single code path
    correct in both eras. Returns a member of ``VALID_DIRECTIONS`` — {protective, risk, neutral,
    unknown, contested} since format 0.7 (RM150). ``contested`` means the sources disagree about
    the *sign*, where ``unknown`` means nobody assessed it: a finding and an absence, which used to
    share one member. It carries no benefit sign (``_variant_sign`` → 0, no colour) and can never be
    *derived* — no legacy ``state`` value means it — so a 0.5 artifact never reads it.
    """
    d = (direction or "").strip().lower()
    if d:
        return d
    return direction_from_state((state or "").strip().lower(), weight)


def _effective_clin_sig(
    clin_sig: Optional[str],
    pathogenic: Optional[bool],
    benign: Optional[bool],
    clinvar: Optional[bool],
) -> str:
    """The clinical-significance tier for a **parquet** row, across the format transition.

    The exact counterpart of ``_effective_direction``: the authored ``clin_sig`` column when it
    carries a value, else derived from the legacy ClinVar booleans via the format's own pure leaf
    ``clin_sig_from_booleans``. COMPILER.md is explicit that this fallback "lives in Python and does
    not travel with the parquet", so a polars-side consumer must apply it itself.

    Prefer the column and never round-trip through the booleans: the derivation is **one-way lossy**
    by construction — three booleans cannot express ``likely_pathogenic``. Our own ClinVar panels
    populate both, and reading the boolean collapsed 214,827 ``likely_pathogenic`` rows into the same
    rendering as 402,174 ``pathogenic`` ones. Returns "" when nothing can be established.
    """
    tier = (clin_sig or "").strip().lower()
    if tier:
        return tier
    return clin_sig_from_booleans(pathogenic, benign, clinvar) or ""


def _clin_sig_label(tier: str) -> str:
    """Human-readable form of a `clin_sig` tier ('likely_pathogenic' -> 'Likely pathogenic')."""
    if not tier:
        return ""
    return tier.replace("_", " ").capitalize()


def _variant_sign(
    weight: Optional[float], state: Optional[str], direction: Optional[str] = None
) -> int:
    """Benefit sign: +1 beneficial, -1 risk, 0 neutral/unknown.

    Prefers the numeric weight's sign (a weighted module states its own direction); when there is no
    weight (weight-less modules like superhuman / the ClinVar gene panels) falls back to the
    **effective direction** — the authored ``direction`` column, or ``state`` derived — so a
    protective variant reads as beneficial without a fabricated effect size, in both the 0.5 (state)
    and 1.0 (direction) schemas.
    """
    w = weight or 0.0
    if w > 0:
        return 1
    if w < 0:
        return -1
    d = _effective_direction(direction, state, weight)
    if d == "protective":
        return 1
    if d == "risk":
        return -1
    return 0


def _variant_color(
    weight: Optional[float], state: Optional[str], direction: Optional[str] = None
) -> str:
    """CSS color for a variant, weight-aware with an effective-direction fallback (see ``_variant_sign``)."""
    w = weight or 0.0
    if w != 0:
        return _weight_color(w)
    sign = _variant_sign(weight, state, direction)
    if sign > 0:
        return "rgba(0, 160, 0, 0.3)"  # protective — green
    if sign < 0:
        return "rgba(180, 0, 0, 0.3)"  # risk — red
    return "transparent"


# ClinPGx evidence tiers, strongest first. Anything unrecognised (including the empty string every
# non-pharmacogenomics module carries) ranks last.
_EVIDENCE_ORDER: tuple[str, ...] = ("1A", "1B", "2A", "2B", "3", "4")


def _evidence_rank(level: str | None) -> int:
    """Sort key for a ClinPGx evidence level: higher is stronger."""
    if not level:
        return 0
    normalized = level.strip().upper()
    if normalized not in _EVIDENCE_ORDER:
        return 0
    return len(_EVIDENCE_ORDER) - _EVIDENCE_ORDER.index(normalized)


def _genotype_alleles(genotype: list[str] | str | None) -> list[str]:
    """Alleles of a genotype, from either representation, in the order they were written.

    ``weights.parquet`` stores a genotype as a list of alleles; the 0.4 table families
    (``pharm_variants`` and friends) store the authored string, e.g. ``"G/G"``. Both reach the
    report, and treating the string as a sequence of characters silently produced ``G///G`` and a
    zygosity read off the separator.

    **The string case delegates to ``just_dna_format.alleles.split_genotype``** — the format's single
    definition of the split, made public in 0.6 precisely because consumers were re-deriving it from
    prose and getting it wrong (S30: reimplemented twice, in opposite directions, with no failing run
    either time to say which was right). Ours was wrong in a third way: it split on ``/`` only, so a
    **phased** authored genotype came back as one allele — ``"A|G"`` → ``["A|G"]`` — and
    ``_zygosity`` then read it as a single-allele row and rendered no zygosity at all. Nothing we
    ship carries a phased genotype, so no test in the corpus could have caught it; that is exactly
    the argument for calling the leaf instead of keeping a copy.

    Never sorted, in either representation. Sorting belongs in ``_genotype_join_key``, which rebuilds
    the *authored* key, and nowhere else.
    """
    if genotype is None:
        return []
    if isinstance(genotype, str):
        return split_genotype(genotype)
    return list(genotype)


def _genotype_str(genotype: list[str] | str | None) -> str:
    """Format a genotype as a human-readable string like 'A/G'."""
    return "/".join(_genotype_alleles(genotype))


def _alt_alleles(alts: list[str] | str | None) -> list[str]:
    """The module's alternate alleles, whichever way its lead table spells them.

    **`alts` is not one dtype across the format, and assuming it is rendered nonsense.**
    `weights.parquet` stores `List(Utf8)`; `pharm_variants.parquet` and its 0.4 siblings are
    materialized verbatim from the authored CSV and keep a comma-joined `String` — measured `'A,C'`.
    A bare `"/".join(...)` over the string case iterates *characters*, so `'A,C'` rendered as
    **`'A/,/C'`**, both as "Module alternate alleles" in the report and inside the AI-prefill prompt
    the reader can send to a third party.

    It was unreachable before format 0.6, which is why no test caught it: the column did not exist
    on a 0.4 table, so `row.get("alts", [])` returned `[]` and rendered empty. Our own shipped
    `pharmgkb` is still a 0.5 artifact with no `alts` column at all, so this is latent here and goes
    live the moment that module is recompiled. Reported by just-module-creator, 2026-08-20.

    The asymmetry is not a compiler defect to wait out: retyping `alts` to `List(Utf8)` removes a
    column type, which Principle 3 reserves for 1.0. Splitting here is the answer for the whole 0.x
    line. Separators accepted are `,` (the authored spelling) and `|` (polars-bio's multi-allelic
    ALT separator, so a VCF-side value passed in reads correctly too).
    """
    if alts is None:
        return []
    if isinstance(alts, str):
        return [a for a in re.split(r"[,|]", alts) if a]
    return [str(a) for a in alts if a]


def _alt_str(alts: list[str] | str | None) -> str:
    """The module's alternate alleles as one display string, e.g. ``A/C``."""
    return "/".join(_alt_alleles(alts))


def _genotype_join_key(genotype: list[str] | str | None, phased: Optional[bool]) -> str:
    """Rebuild the **authored** genotype string from a weights row, for keying against a 0.6
    ``annotations.parquet``.

    The exact inverse of ``_genotype_alleles`` above (keep the two together — they are one
    round-trip), and the same rule ``reverse_module`` re-emits with (COMPILER.md § Reverse): phased
    keeps authored order joined by ``|``; unphased is sorted and joined by ``/``, because an
    unphased genotype names an unordered pair and the grammar requires the sorted spelling.

    Sorting is correct **here** and wrong in the engine's ``_normalize_lead_genotype``: this rebuilds
    the authored key the module itself wrote, whereas the engine matches a sample's call against the
    artifact's own representation and must not fold ``A|G`` and ``G|A`` together.
    """
    alleles = _genotype_alleles(genotype)
    if not alleles:
        return ""
    if phased:
        return "|".join(alleles)
    return "/".join(sorted(alleles))


def _zygosity(genotype: list[str] | str | None) -> str:
    """Determine zygosity from a genotype."""
    alleles = _genotype_alleles(genotype)
    if len(alleles) < 2:
        return ""
    return "hom" if alleles[0] == alleles[1] else "het"


_ANNOTATION_FIELDS: tuple[str, ...] = ("gene", "category", "phenotype")
_GENOTYPE_KEY = "_genotype_join_key"


def _genotype_key_expr() -> pl.Expr:
    """Polars form of ``_genotype_join_key`` — see that function for why phased is not sorted."""
    return (
        pl.when(pl.col("phased").fill_null(False))
        .then(pl.col("genotype").list.join("|"))
        .otherwise(pl.col("genotype").list.sort().list.join("/"))
        .alias(_GENOTYPE_KEY)
    )


def _annotations_keying(
    weights_cols: list[str], annotations_cols: list[str], weights_schema: pl.Schema
) -> str:
    """Which key joins these two artifacts: ``genotype`` | ``variant_key`` | ``rsid``.

    Detected from the columns present rather than assumed, because three generations of artifact are
    in circulation at once: modules published on HuggingFace under 0.3 (rsid only), what we compile
    today under 0.5 (``variant_key``, no genotype), and 0.6 (``genotype``, per format RM80). The same
    style of detection ``reverse_module`` uses.
    """
    if (
        "genotype" in annotations_cols
        and "variant_key" in annotations_cols
        and "variant_key" in weights_cols
        and weights_schema.get("genotype") == pl.List(pl.String)
    ):
        return "genotype"
    if "variant_key" in annotations_cols and "variant_key" in weights_cols:
        return "variant_key"
    return "rsid"


def _join_annotations(
    weights_lf: pl.LazyFrame, annotations_lf: pl.LazyFrame, module_name: str
) -> pl.LazyFrame:
    """Attach gene/category/phenotype to the user's annotated rows **without inflating the count**.

    ``annotations.parquet`` has one row per *distinct annotation*, keyed
    ``(variant_key, conclusion, negatives)`` in 0.5 and gaining ``genotype`` in 0.6 (RM80). Joining
    it on ``rsid`` therefore fans a poly-effect variant out into one report row per annotation:
    measured at coronary 81 → 231 (x2.85), lipidmetabolism x2.73, vo2max x2.15, silently inflating
    ``total_variants`` and every count derived from it.

    The RM80 reply explicitly rejects deduplicating on ``variant_key`` as the general answer — a
    genuine poly-effect variant is one locus with two real annotations, so that dedup is "lossless
    only for as long as it happens to be". It is right only where the artifact offers no finer key,
    which is exactly the 0.5 era; where 0.6 states the genotype we key on it instead and keep both
    annotations of a variant that really has two.
    """
    weights_schema = weights_lf.collect_schema()
    weights_cols = weights_schema.names()
    ann_schema = annotations_lf.collect_schema()
    ann_cols = ann_schema.names()

    fields = [c for c in _ANNOTATION_FIELDS if c in ann_cols]
    keying = _annotations_keying(weights_cols, ann_cols, weights_schema)

    log_message(
        message_type="info",
        action="annotations_join_keying",
        module=module_name,
        keying=keying,
    )

    if keying == "genotype":
        right = annotations_lf.select("variant_key", "genotype", *fields).with_columns(
            pl.col("genotype").alias(_GENOTYPE_KEY)
        ).drop("genotype")
        return (
            weights_lf.with_columns(_genotype_key_expr())
            .join(right, on=["variant_key", _GENOTYPE_KEY], how="left", suffix="_ann")
            .drop(_GENOTYPE_KEY)
        )

    if keying == "variant_key":
        # No genotype to key on, so collapse the annotation rows to one per variant. The report
        # renders a single `conclusion` per row anyway; keeping the fan-out would double-count the
        # variant itself, which is the worse of the two losses.
        right = annotations_lf.select("variant_key", *fields).unique(
            subset=["variant_key"], keep="first"
        )
        return weights_lf.join(right, on="variant_key", how="left", suffix="_ann")

    right = annotations_lf.select("rsid", *fields).unique(subset=["rsid"], keep="first")
    return weights_lf.join(right, on="rsid", how="left", suffix="_ann")


_CONCORDANCE_COLUMN = "clin_sig_concordance"
_OPPOSED_COLUMN = "clin_sig_opposed"


def _join_concordance(
    weights_lf: pl.LazyFrame, concordance_lf: pl.LazyFrame, module_name: str
) -> pl.LazyFrame:
    """Attach the clinical-authority concordance verdict to each annotated row (format 0.7, RM130).

    ``clin_sig_concordance.parquet`` is keyed ``(variant_key, genotype)`` with the genotype spelled
    as ``variants.csv`` spells it, so the join key is the same authored string the 0.6 annotations
    join rebuilds through ``_genotype_key_expr``. Two columns come across: ``authority_concordance``
    (do the authorities agree *with each other* — ``discordant`` is the one the report badges) and
    ``opposed`` (does the disagreement cross the pathogenic/benign line). ``authored_position`` is
    deliberately not carried: it is a different axis (where the module sits) and the report already
    shows the module's own tier beside the badge.

    **Nothing here resolves the split.** No winner is read off ``authority_precedence`` — the format
    is explicit that the block is computed with by nothing — and ``unchecked`` renders nothing,
    because an authority that could not be consulted is not agreement.

    Skipped, with the rows left un-badged rather than the join guessed, when the lead table lacks
    anything ``_genotype_key_expr`` reads — ``variant_key``, a list ``genotype`` or ``phased``: a
    0.3/0.5 artifact has no concordance table to join anyway, and the predicate names every column
    the expression needs so a missing one is a logged skip rather than a ``ColumnNotFoundError``
    that fails the whole report for that module.
    """
    schema = weights_lf.collect_schema()
    names = set(schema.names())
    if (
        "variant_key" not in names
        or "phased" not in names
        or schema.get("genotype") != pl.List(pl.String)
    ):
        log_message(
            message_type="info",
            action="concordance_join_skipped",
            module=module_name,
            reason="lead table carries no variant_key + list genotype + phased to key on",
        )
        return weights_lf
    right = (
        concordance_lf.select(
            "variant_key",
            pl.col("genotype").alias(_GENOTYPE_KEY),
            pl.col("authority_concordance").alias(_CONCORDANCE_COLUMN),
            pl.col("opposed").alias(_OPPOSED_COLUMN),
        )
        .unique(subset=["variant_key", _GENOTYPE_KEY], keep="first")
    )
    return (
        weights_lf.with_columns(_genotype_key_expr())
        .join(right, on=["variant_key", _GENOTYPE_KEY], how="left")
        .drop(_GENOTYPE_KEY)
    )


def load_annotated_weights(
    weights_parquet: Path,
    module_name: str,
    module_info: Optional[ModuleInfo] = None,
) -> pl.DataFrame:
    """
    Load annotated weights parquet and enrich with annotation metadata.

    Joins the user's annotated weights with the module's annotations table
    (which has gene, phenotype, category) and the studies table.

    The weights parquet has the actual rsid values in a column named
    ``rsid_{module_name}`` (the plain ``rsid`` column from the VCF is
    typically empty). We resolve the correct column and use it for the
    join against the annotations table.

    Args:
        weights_parquet: Path to the user's {module}_weights.parquet
        module_name: Name of the HF module
        module_info: Optional ModuleInfo for the module

    Returns:
        Enriched DataFrame with annotation and study data joined in.
    """
    with start_action(action_type="load_annotated_weights", module=module_name, path=str(weights_parquet)):
        weights_lf = pl.scan_parquet(weights_parquet)

        # The actual rsid values live in rsid_{module_name}, not the VCF rsid column.
        # Resolve the correct column name for joining.
        schema_cols = weights_lf.collect_schema().names()
        module_rsid_col = f"rsid_{module_name}"
        if module_rsid_col in schema_cols:
            # Rename module-specific rsid column to "rsid" for the join,
            # dropping the original empty rsid column first.
            weights_lf = weights_lf.drop("rsid").rename({module_rsid_col: "rsid"})

        # Load annotations table from the module. If a custom module was removed
        # or published without optional report metadata, keep the report usable.
        annotations_lf = _scan_optional_module_table(
            module_name,
            ModuleTable.ANNOTATIONS,
            module_info=module_info,
        )
        enriched = (
            weights_lf
            if annotations_lf is None
            else _join_annotations(weights_lf, annotations_lf, module_name)
        )
        # Independent of the annotations table: a module can carry a concordance record without
        # curated annotations, so this join is not nested under the one above.
        concordance_lf = _scan_optional_module_table(
            module_name, ModuleTable.CONCORDANCE, module_info=module_info
        )
        if concordance_lf is not None:
            enriched = _join_concordance(enriched, concordance_lf, module_name)
        return _ensure_annotation_report_columns(enriched.collect())


_AUTHORED_AXES: tuple[str, ...] = (
    "effect_size",
    "effect_measure",
    "effect_allele",
    "stat_significance",
    "negatives",
    "trait_efo_id",
    "flags",
    "priority",
    "method",
    "population",
    "p_value",
)


def _restored_count(variant_groups) -> int:
    """How many rendered variants were inferred from an absent call rather than observed.

    Takes the built view models rather than the frame, so it counts exactly what the reader sees —
    the same reason ``total_weight`` is summed over the view model.
    """
    return sum(
        1 for group in variant_groups for v in group["variants"] if v.get("restored")
    )


def _build_variant_ai_prompt(variant: dict[str, object]) -> str:
    """Build the cautious, evidence-oriented prompt shared by external assistants."""
    fields = (
        ("RSID", variant.get("rsid")),
        ("Gene", variant.get("gene")),
        ("My genotype", variant.get("genotype_str")),
        ("Reference allele", variant.get("ref")),
        ("Module alternate alleles", variant.get("alt")),
        ("Zygosity", variant.get("zygosity")),
        ("Direction", variant.get("direction")),
        ("Module weight", variant.get("weight")),
        ("Module conclusion", variant.get("conclusion")),
        ("ClinVar interpretation", variant.get("clin_sig_label")),
        ("Drug", variant.get("drug")),
        ("Drug response", variant.get("response")),
        ("Evidence level", variant.get("evidence_level")),
        ("Population", variant.get("population")),
        ("Effect size", variant.get("effect_size")),
        ("Effect measure", variant.get("effect_measure")),
        ("p-value", variant.get("p_value")),
    )
    facts = [f"- {label}: {value}" for label, value in fields if value not in (None, "")]
    rsid = str(variant.get("rsid", ""))
    studies = variant.get("studies")
    if isinstance(studies, list):
        pmids = [
            str(study.get("pmid"))
            for study in studies
            if isinstance(study, dict) and study.get("pmid")
        ]
        if pmids:
            facts.append(f"- Supporting PubMed IDs: {', '.join(pmids)}")

    return "\n".join(
        (
            (
                "Explain this genomic annotation in plain, cautious language for research and "
                "informational use. Explain what the genotype may mean, but do not diagnose or "
                "recommend treatment. Distinguish association from causation, discuss uncertainty "
                "and population relevance, and explain that a module weight is not an absolute "
                "clinical risk."
            ),
            "",
            "Annotation:",
            *facts,
            f"- dbSNP: https://www.ncbi.nlm.nih.gov/snp/{rsid}",
            "",
            (
                "Check current reliable sources, cite direct links, and say clearly when evidence "
                "is limited, conflicting, or not clinically actionable."
            ),
        )
    )


def _build_variant_ai_links(variant: dict[str, object]) -> list[dict[str, str]]:
    """Return prompt-prefill links matching the four assistants used by PRS analysis."""
    if not variant.get("rsid"):
        return []
    encoded_prompt = urllib.parse.quote(_build_variant_ai_prompt(variant), safe="")
    return [
        {
            "provider": provider.lower(),
            "label": f"Ask {provider} to explain {variant['rsid']}. {_AI_PRIVACY_NOTE.format(provider=provider)}",
            "url": f"{base_url}{encoded_prompt}",
        }
        for provider, base_url in AI_EXPLAIN_ASSISTANTS
    ]


_EVIDENCE_WORDS = {
    "called": "read from the file",
    "restored_hom_ref": "not recorded; assumed to match the reference from nearby coverage",
    "no_call": "no data",
}


def _build_phenotype_ai_prompt(module_title: str, gene: dict) -> str:
    """The prompt an assistant gets for one phenotype result: the result, the rule's inputs, the ask.

    A combined result is explained differently from a single variant: the reader needs how the
    versions of the gene combine into the result, so the prompt carries every defining position as
    read (and how it was read) plus the possibilities when the file could not decide. It asks for the
    same plain, layered explanation our own text aims at (docs/REPORT_VOICE.md), and for the limits of
    reading this from a DNA file.
    """
    status_words = {
        "called": f"Result: {gene.get('phenotype')}",
        "ambiguous": "Result: not fully determined; possible results: "
        + "; ".join(r["phenotype"] for r in gene.get("readings", [])),
        "not_assessable": "Result: could not be read from my DNA file; possible results: "
        + "; ".join(r["phenotype"] for r in gene.get("readings", [])),
        "no_match": "Result: my DNA shows a combination this module does not list",
    }
    sites = [
        f"- {s.get('rsid') or ''} (chr{s.get('chrom')}:{s.get('start')}, GRCh38, reference {s.get('ref')}): "
        + (f"{'/'.join(s['observed'])}, " if s.get("observed") else "")
        + _EVIDENCE_WORDS.get(s.get("evidence"), str(s.get("evidence")))
        for s in gene.get("sites", [])
    ]
    explanation = ""
    if gene.get("status") == "called":
        explanation = " ".join(
            c for r in gene.get("readings", []) if r["phenotype"] == gene.get("phenotype") for c in r["conclusions"]
        )
    lines = [
        "Explain this result from my DNA in plain language for someone without a science background, "
        "then add a short section for a professional. Explain how the versions of this gene combine "
        "into the result, what the result means in everyday life, any clear practical implications and "
        "interesting facts, and what a DNA file can and cannot tell compared with a lab test. Do not "
        "diagnose or recommend treatment.",
        "",
        f"Module: {module_title}",
        f"Gene: {gene.get('gene')}",
        status_words.get(gene.get("status"), f"Result status: {gene.get('status')}"),
    ]
    if explanation:
        lines.append(f"The module's explanation: {explanation}")
    lines += ["", "Positions read from my DNA file:", *sites, "",
              "Check current reliable sources, cite direct links, and say clearly where evidence is limited."]
    return "\n".join(lines)


def _build_phenotype_ai_links(module_title: str, gene: dict) -> list[dict[str, str]]:
    """Prompt-prefill links for one phenotype card, the same four assistants as a variant row."""
    encoded_prompt = urllib.parse.quote(_build_phenotype_ai_prompt(module_title, gene), safe="")
    topic = gene.get("phenotype") if gene.get("status") == "called" else gene.get("topic") or gene.get("gene")
    return [
        {
            "provider": provider.lower(),
            "label": f"Ask {provider} to explain: {topic}. {_AI_PRIVACY_NOTE.format(provider=provider)}",
            "url": f"{base_url}{encoded_prompt}",
        }
        for provider, base_url in AI_EXPLAIN_ASSISTANTS
    ]


def _build_variant(row: dict, studies_by_rsid: dict[str, list[dict[str, str]]]) -> dict:
    """The view model for one annotated variant, shared by every report shape.

    **Render-if-present, never a fixed field list.** The 0.5 artifact carries 37 columns and the
    template used to render 11 because the view model predated the rest; every authored axis in
    ``_AUTHORED_AXES`` is carried through here and given an ``{% if %}`` row in the template macro,
    so a module that populates ``effect_size`` or ``negatives`` shows it the day it is published.
    Our corpus leaves most of them empty — every module we hold is a Gen-I port authored against 0.2
    and mechanically uplifted — but that is a property of the corpus, not of the format, and the
    compiler correctly never fills a cell an author left blank. Absent means *render nothing*, never
    a fabricated default.
    """
    weight = row.get("weight", 0.0) or 0.0
    genotype = row.get("genotype")
    rsid = row.get("rsid", "") or ""
    state = row.get("state")
    direction = row.get("direction")
    clin_sig = _effective_clin_sig(
        row.get("clin_sig"), row.get("pathogenic"), row.get("benign"), row.get("clinvar")
    )

    variant = {
        "rsid": rsid,
        "gene": row.get("gene", "") or "",
        "genotype_str": _genotype_str(genotype),
        "ref": row.get("ref", "") or "",
        "alt": _alt_str(row.get("alts")),
        "zygosity": _zygosity(genotype),
        "weight": weight,
        "weight_color": _variant_color(weight, state, direction),
        "state": row.get("state", "") or "",
        # The 0.3 axis, derived when the column is empty. Format 1.0 removes `state`, so the
        # template renders this and never the raw column.
        "direction": _effective_direction(direction, state, weight),
        "conclusion": row.get("conclusion", "") or "",
        "clinvar": row.get("clinvar", False),
        "clin_sig": clin_sig,
        "clin_sig_label": _clin_sig_label(clin_sig),
        # Format 0.7 (RM130): whether the clinical authorities consulted agree with each other about
        # this subject. Only `discordant` is a badge; `concordant`/`single`/`none`/`unchecked` and a
        # module with no concordance table all render nothing — an authority that could not be
        # consulted is not agreement, and its absence is not a finding either. `opposed` says the
        # split crosses the pathogenic/benign line. Nothing resolves the split.
        "clin_sig_contested": row.get(_CONCORDANCE_COLUMN) == "discordant",
        "clin_sig_opposed": bool(row.get(_OPPOSED_COLUMN)) if row.get(_OPPOSED_COLUMN) is not None else None,
        # Keyed by rsID where the row has one, else by coordinate — a coordinate-authored variant's
        # citations are keyed the same way in `studies.parquet`. See `_study_key`.
        "studies": studies_by_rsid.get(
            _study_key(rsid, row.get("chrom"), row.get("start"), row.get("ref")) or rsid, []
        ),
        # Pharmacogenomics facts, present only on a pharm_variants-led module. Empty strings
        # elsewhere, so the template can show them unconditionally.
        # Whether the caller supplied this genotype or the engine inferred it from the absence of any
        # record at the site. Never merged into another field: an inferred reference genotype and a
        # sequenced one carry different weight and the reader has to be able to see which is which.
        "restored": row.get(EVIDENCE_COLUMN) == EVIDENCE_RESTORED,
        "restored_flank_bp": row.get(FLANK_COLUMN),
        # How many loci the authored key resolved onto (format 0.6, RM87 — `locus_count`, stamped by
        # the compiler, `1` on a row that was not expanded). `> 1` means the module authored **one**
        # row for an rsID that resolves to several positions, so the compiler paired that genotype
        # with every one of them and **at most one of the resulting rows is the variant the author
        # meant** — nothing on the row says which.
        #
        # Restoration withholds these outright (`restoration.hom_ref_rows`), because an unobserved
        # hom-ref row at N loci fabricates N results. A *called* row is different: the sample really
        # was sequenced there and really carries that genotype, so withholding would discard an
        # observation. It is labelled instead. The `ref`-agreement filter in the engine already drops
        # the members whose reference allele contradicts the call, which is most of them; what
        # survives to here is the same-`ref` case (a pseudoautosomal locus on X and Y, a paralogous
        # rsID over two positions with the same reference base), where every member matches equally
        # well and the ambiguity is real rather than resolvable.
        #
        # `None` on a pre-0.6 artifact, which is every module we have published — the template then
        # renders nothing, exactly as for an absent authored axis. Do not coalesce it to 1.
        "locus_count": row.get("locus_count"),
        "locus_index": row.get("locus_index"),
        "drug": row.get("drug", "") or "",
        "evidence_level": row.get("evidence_level", "") or "",
        "phenotype_category": row.get("phenotype_category", "") or "",
        "response": row.get("response", "") or "",
        # `pharm_variants.pmid` (format 0.7, RM132): the citation for *this row's own* drug/genotype
        # claim. A different axis from `evidence_level`, which is somebody else's grading *of* the
        # evidence where this points *at* it — so the template shows both or neither, never one
        # standing in for the other. Empty on `weights`-led rows, whose citations live in
        # `studies.parquet` and arrive through `studies` above.
        "pmid": row.get("pmid", "") or "",
    }
    for axis in _AUTHORED_AXES:
        value = row.get(axis)
        variant[axis] = "" if value is None else value
    variant["ai_explain_links"] = _build_variant_ai_links(variant)
    return variant


def _study_key(rsid: object, chrom: object, start: object, ref: object) -> Optional[str]:
    """The key a study row and a variant row are matched on: the rsID, else the coordinate.

    A ``StudyRow`` names its subject the same way a ``VariantRow`` does — by rsID where the module
    authored one, and by coordinate where it did not (`REQUIRED_ANY_OF` was ``({rsid}, {chrom})``
    before RM47 relaxed it to ``()``). Keying study lookup on the rsID alone therefore drops every
    coordinate-authored citation: measured on cardio, **34,697 of 121,467 study rows (28.6%) carry a
    null rsid**, so 14,590 of 53,098 loci rendered with no grounding at all even though the module
    grounds every one of them. cancer and pathogenic have the same shape.

    Returns ``None`` when neither identity is available, so an unkeyable row is skipped rather than
    collected under a key that would collide with another variant's.
    """
    text = str(rsid).strip() if rsid is not None else ""
    if text:
        return text
    if chrom is None or start is None:
        return None
    contig, position = str(chrom).strip(), str(start).strip()
    if not contig or not position:
        return None
    # `ref` is part of the key because two records can share a position and differ only in reference
    # allele — the ClinVar dup/del mirror shape. An empty ref still keys, as an empty final field.
    return f"{contig}:{position}:{str(ref).strip() if ref is not None else ''}"


def _annotated_loci(annotated: pl.DataFrame) -> list[str]:
    """The ``chrom:start:ref`` keys of the rows that carry no rsID, for coordinate-keyed studies.

    Only rows with a null/blank rsid need one — a row with an rsID is found by it. Returns an empty
    list when the frame has no coordinate columns, which is the pre-0.5 artifact shape.
    """
    if not {"chrom", "start"}.issubset(annotated.columns):
        return []
    keys: set[str] = set()
    for row in annotated.select(
        [c for c in ("rsid", "chrom", "start", "ref") if c in annotated.columns]
    ).iter_rows(named=True):
        if str(row.get("rsid") or "").strip():
            continue
        key = _study_key(None, row.get("chrom"), row.get("start"), row.get("ref"))
        if key is not None:
            keys.add(key)
    return sorted(keys)


def load_studies_for_variants(
    rsids: list[str],
    module_name: str,
    module_info: Optional[ModuleInfo] = None,
    loci: Optional[list[str]] = None,
) -> dict[str, list[dict[str, str]]]:
    """
    Load studies data for a set of variants from an HF module.

    Returns a mapping of :func:`_study_key` -> list of study dicts: keyed by rsID for a row that has
    one, and by ``chrom:start:ref`` for a coordinate-authored row.
    """
    with start_action(action_type="load_studies_for_variants", module=module_name):
        if not rsids and not loci:
            return {}

        studies_lf = _scan_optional_module_table(
            module_name,
            ModuleTable.STUDIES,
            module_info=module_info,
        )
        if studies_lf is None:
            return {}

        wanted_rsids, wanted_loci = set(rsids or []), set(loci or [])
        # Collect both identities in one pass. A coordinate-keyed study row is only reachable where
        # `studies.parquet` carries the coordinate columns at all — they arrived in 0.5, so a 0.3-era
        # artifact simply has no coordinate branch to take, and `_study_key` falls back to the rsid.
        columns = set(studies_lf.collect_schema().names())
        has_coords = {"chrom", "start"}.issubset(columns)
        studies_df = studies_lf.collect()

        result: dict[str, list[dict[str, str]]] = {}
        for row in studies_df.iter_rows(named=True):
            key = _study_key(
                row.get("rsid"),
                row.get("chrom") if has_coords else None,
                row.get("start") if has_coords else None,
                row.get("ref") if has_coords else None,
            )
            if key is None or (key not in wanted_rsids and key not in wanted_loci):
                continue
            result.setdefault(key, []).append({
                "pmid": row.get("pmid", ""),
                "population": row.get("population", ""),
                "p_value": row.get("p_value", ""),
                "conclusion": row.get("conclusion", ""),
                "study_design": row.get("study_design", ""),
                # Format 0.7 columns (RM140, RM160), render-if-present like every other axis.
                # `statistical_test` says which analysis produced this row's `p_value` /
                # `effect_size`; `study_design` describes the study and one study runs several
                # analyses, so a p-value from one and an effect size from another sit on one row
                # with nothing but this column to say so. `confidence` is the *citing source's*
                # own review state in its own units (CIViC's `submitted` / `accepted`) and is
                # meaningless without `confidence_unit` beside it — the model refuses one without
                # the other, and the template renders them as a pair or not at all.
                "statistical_test": row.get("statistical_test") or "",
                "confidence": row.get("confidence") or "",
                "confidence_unit": row.get("confidence_unit") or "",
            })

        return result


def build_longevity_report_data(
    weights_parquet: Path,
    module_name: str = "longevitymap",
    module_info: Optional[ModuleInfo] = None,
) -> dict:
    """
    Build the full data structure needed for the longevity report template.

    Reads the annotated weights parquet, enriches with annotations and studies,
    groups variants by longevity pathway category, and computes summary statistics.

    Args:
        weights_parquet: Path to the user's longevitymap_weights.parquet
        module_name: Module name (default: "longevitymap")
        module_info: Optional ModuleInfo

    Returns:
        Dict with keys: categories, summary, module_name
    """
    with start_action(action_type="build_longevity_report_data", path=str(weights_parquet)):
        # Load and enrich weights
        enriched_df = load_annotated_weights(weights_parquet, module_name, module_info)

        # Keep the rows that matched a module entry (weight-agnostic: superhuman etc. have no weight)
        annotated = _annotated_rows(enriched_df)

        # Get all rsids for study lookup
        rsids = annotated.select("rsid").unique().to_series().to_list()
        studies_by_rsid = load_studies_for_variants(
            rsids, module_name, module_info, loci=_annotated_loci(annotated)
        )

        # Assign null categories to "other"
        annotated = annotated.with_columns(
            pl.col("category").fill_null("other").alias("category")
        )

        # Group variants by category
        categories: dict[str, dict] = {}
        for cat_key, cat_meta in LONGEVITY_CATEGORIES.items():
            cat_variants = annotated.filter(pl.col("category") == cat_key)

            if cat_variants.height == 0:
                categories[cat_key] = {
                    "title": cat_meta["title"],
                    "description": cat_meta["description"],
                    "variants": [],
                    "positive_count": 0,
                    "negative_count": 0,
                    "total_count": 0,
                }
                continue

            variants: list[dict] = [
                _build_variant(row, studies_by_rsid)
                for row in cat_variants.iter_rows(named=True)
            ]

            # Sort by absolute weight descending for better readability
            variants.sort(key=lambda v: abs(v["weight"]), reverse=True)

            positive = sum(1 for v in variants if _variant_sign(v["weight"], v["state"], v.get("direction")) > 0)
            negative = sum(1 for v in variants if _variant_sign(v["weight"], v["state"], v.get("direction")) < 0)

            categories[cat_key] = {
                "title": cat_meta["title"],
                "description": cat_meta["description"],
                "variants": variants,
                "positive_count": positive,
                "negative_count": negative,
                "total_count": len(variants),
            }

        # Summary statistics
        total_positive = sum(c["positive_count"] for c in categories.values())
        total_negative = sum(c["negative_count"] for c in categories.values())
        total_variants = sum(c["total_count"] for c in categories.values())
        # Sum the view model, not the frame: a lead family with no `weight` column at all (every 0.4
        # family) made `annotated.select("weight")` raise ColumnNotFoundError. Latent while only
        # longevitymap took this path, live the moment routing stopped being a hardcoded name.
        total_weight = sum(
            v["weight"] for c in categories.values() for v in c["variants"]
        )

        summary = {
            "total_variants": total_variants,
            "total_positive": total_positive,
            "total_negative": total_negative,
            "total_weight": round(total_weight, 2) if total_weight else 0.0,
            # Held apart from the total rather than folded into it: a restored row is the reference
            # genotype inferred from the absence of any call, and pooling it with sequenced results
            # in a headline count is exactly the merge `genotype_evidence` exists to prevent.
            "total_restored": _restored_count(categories.values()),
        }

        return {
            "categories": categories,
            "summary": summary,
            "module_name": module_name,
        }


def build_module_report_data(
    weights_parquet: Path,
    module_name: str,
    module_info: Optional[ModuleInfo] = None,
) -> dict:
    """
    Build report data for a generic HF annotation module
    (lipidmetabolism, coronary, vo2max, etc.).

    These modules don't use longevity pathway categories;
    variants are displayed in a single flat table.

    Args:
        weights_parquet: Path to the user's {module}_weights.parquet
        module_name: Module name
        module_info: Optional ModuleInfo

    Returns:
        Dict with keys: variants, summary, module_name
    """
    with start_action(action_type="build_module_report_data", module=module_name, path=str(weights_parquet)):
        enriched_df = load_annotated_weights(weights_parquet, module_name, module_info)
        annotated = _annotated_rows(enriched_df)

        rsids = annotated.select("rsid").unique().to_series().to_list()
        studies_by_rsid = load_studies_for_variants(
            rsids, module_name, module_info, loci=_annotated_loci(annotated)
        )

        variants: list[dict] = [
            _build_variant(row, studies_by_rsid) for row in annotated.iter_rows(named=True)
        ]

        # A pharmacogenomics module carries no weights, so ordering by |weight| would leave it in
        # scan order. Evidence level is its ranking axis: 1A is a prescribing guideline, 2B the
        # weakest tier we admit.
        variants.sort(
            key=lambda v: (abs(v["weight"]), _evidence_rank(v["evidence_level"])), reverse=True
        )

        # Direction counts are weight-aware with a state fallback so weight-less protective
        # modules (superhuman) still tally as beneficial rather than 0 positive / 0 negative.
        positive = sum(1 for v in variants if _variant_sign(v["weight"], v["state"], v.get("direction")) > 0)
        negative = sum(1 for v in variants if _variant_sign(v["weight"], v["state"], v.get("direction")) < 0)

        summary = {
            "total_variants": len(variants),
            "total_positive": positive,
            "total_negative": negative,
            "total_weight": round(sum(v["weight"] for v in variants), 2),
            "total_restored": _restored_count([{"variants": variants}]),
        }

        return {
            "variants": variants,
            "summary": summary,
            "module_name": module_name,
        }


def build_pharmacogenomics_report_data(
    weights_parquet: Path,
    module_name: str,
    module_info: Optional[ModuleInfo] = None,
) -> dict:
    """Build report data for a ``pharm_variants``-led module, grouped by drug.

    A weight-ranked flat table is the wrong shape here: a pharmacogenomics module states no weights
    at all (every one is 0.0), so ordering by ``|weight|`` leaves the section in scan order. The
    ranking axis is the ClinPGx evidence level — 1A is a prescribing guideline, 4 a case report —
    and the unit a reader acts on is the *drug*, not the variant.
    """
    with start_action(
        action_type="build_pharmacogenomics_report_data",
        module=module_name,
        path=str(weights_parquet),
    ):
        enriched_df = load_annotated_weights(weights_parquet, module_name, module_info)
        annotated = _annotated_rows(enriched_df)

        rsids = annotated.select("rsid").unique().to_series().to_list()
        studies_by_rsid = load_studies_for_variants(
            rsids, module_name, module_info, loci=_annotated_loci(annotated)
        )

        variants = [
            _build_variant(row, studies_by_rsid) for row in annotated.iter_rows(named=True)
        ]

        drugs: dict[str, dict] = {}
        for variant in variants:
            # A variant with no drug named is still a real match; grouping it under "" would render
            # an unlabelled section, so it goes to an explicit bucket the template can title.
            key = variant["drug"] or "(drug not stated)"
            bucket = drugs.setdefault(
                key, {"drug": key, "variants": [], "best_evidence": "", "genes": []}
            )
            bucket["variants"].append(variant)

        for bucket in drugs.values():
            bucket["variants"].sort(
                key=lambda v: _evidence_rank(v["evidence_level"]), reverse=True
            )
            bucket["best_evidence"] = bucket["variants"][0]["evidence_level"]
            bucket["genes"] = sorted({v["gene"] for v in bucket["variants"] if v["gene"]})
            bucket["total_count"] = len(bucket["variants"])

        ordered = sorted(
            drugs.values(),
            key=lambda b: (_evidence_rank(b["best_evidence"]), b["total_count"]),
            reverse=True,
        )

        summary = {
            "total_variants": len(variants),
            "total_drugs": len(ordered),
            "guideline_count": sum(
                1 for v in variants if (v["evidence_level"] or "").upper() in ("1A", "1B")
            ),
        }

        return {
            "drugs": ordered,
            "summary": summary,
            "module_name": module_name,
        }


def load_module_credits(
    module_name: str, module_info: Optional[ModuleInfo] = None
) -> list[dict]:
    """Licensing/attribution rows a report owes for redistributing this module's data.

    Restricted to ``layer == "annotation"``. SCHEMAS.md § SourceRow is explicit that only that layer
    carries the derivative-work obligation: a source consulted to place a coordinate (Ensembl, at
    layer ``resolution``) is recorded for provenance without tainting the module's own terms, so
    crediting it as a licence condition would misstate what is owed.

    The permission booleans are **tri-state** and are kept that way: ``None`` means the terms could
    not be established, which is not the same as "does not forbid".
    """
    sources_lf = _scan_optional_module_table(
        module_name, ModuleTable.SOURCES, module_info=module_info
    )
    if sources_lf is None:
        return []

    cols = sources_lf.collect_schema().names()
    if "layer" in cols:
        sources_lf = sources_lf.filter(pl.col("layer") == "annotation")

    credits: list[dict] = []
    for row in sources_lf.collect().iter_rows(named=True):
        credits.append(
            {
                "module": module_name,
                "source": row.get("source", "") or "",
                "license": row.get("license", "") or "",
                "license_url": row.get("license_url", "") or "",
                "attribution": row.get("attribution", "") or "",
                "notice": row.get("notice", "") or "",
                "dataset": row.get("dataset", "") or "",
                "share_alike": row.get("share_alike"),
                "commercial_use": row.get("commercial_use"),
                "redistribution": row.get("redistribution"),
                "declared_use": row.get("declared_use", "") or "",
            }
        )
    return credits


def build_report_credits(
    module_names: list[str], module_infos: dict[str, ModuleInfo]
) -> list[dict]:
    """One credits list for the whole report, deduplicated across the modules actually rendered.

    Two modules built from the same upstream release owe one attribution, not two, so rows are keyed
    on the terms rather than the module — but the modules that pulled each one are listed, because
    that is what makes the obligation checkable.
    """
    merged: dict[tuple, dict] = {}
    for name in module_names:
        for credit in load_module_credits(name, module_infos.get(name)):
            key = (
                credit["source"],
                credit["license"],
                credit["attribution"],
                credit["notice"],
            )
            existing = merged.get(key)
            if existing is None:
                credit["modules"] = [name]
                merged[key] = credit
            elif name not in existing["modules"]:
                existing["modules"].append(name)

    credits = list(merged.values())
    credits.sort(key=lambda c: (c["source"], c["license"]))
    return credits


# Display names for modules (loaded from modules.yaml via module_config)
MODULE_DISPLAY_NAMES: dict[str, str] = build_display_names_dict(DISCOVERED_MODULES)


def _read_annotation_manifest(modules_dir: Path) -> Optional[AnnotationManifest]:
    """The run's ``manifest.json``, or ``None`` when there is none or it cannot be read.

    Parsed through ``AnnotationManifest`` rather than as raw JSON on purpose: manifests written
    before the engine learned about lead tables carry no ``lead_table`` key at all, and the model's
    default supplies ``"weights"`` — which is what those runs actually were. Reading the dict
    directly would yield ``None`` and route them nowhere. The same holds for the provenance fields,
    which are absent from every manifest written before they existed and read back as ``None``.

    A missing or unreadable manifest is not an error: the report is also generated from a directory
    of parquets alone, and the caller falls back to the discovered ``ModuleInfo``.
    """
    manifest_path = modules_dir / "manifest.json"
    if not manifest_path.exists():
        return None

    try:
        return AnnotationManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )
    except (ValueError, OSError) as exc:
        log_message(
            message_type="warning",
            action="unreadable_annotation_manifest",
            path=str(manifest_path),
            reason=str(exc),
        )
        return None


def _module_outputs_from_manifest(modules_dir: Path) -> dict[str, ModuleOutputMapping]:
    """One ``ModuleOutputMapping`` per annotated module, keyed by module name."""
    manifest = _read_annotation_manifest(modules_dir)
    return {m.module: m for m in manifest.modules} if manifest else {}


def build_module_exclusions(manifest: Optional[AnnotationManifest]) -> list[dict]:
    """One row per module the run was asked for and did not annotate, with the engine's reason.

    The engine records these on the manifest (`skipped_modules` / `failed_modules`) and both CLIs
    print them, but the HTML report used to render only what succeeded — so a selected module that
    failed left no trace a reader could see. The run itself still succeeds by design (one module's
    failure must not cost the others), which makes the report the only place a reader would ever
    find out, and its silence read as "this module found nothing" rather than "this module was
    never read".

    The two kinds are held apart because they mean different things. *Skipped* is a statement about
    the module — its lead table carries no per-variant key, so there is nothing to join and no
    amount of retrying changes that. *Failed* is a statement about this run — an unreadable path, a
    schema clash — and is usually worth acting on.
    """
    if manifest is None:
        return []
    rows: list[dict] = []
    for name, reason in sorted(manifest.skipped_modules.items()):
        rows.append(
            {
                "name": name,
                "display_name": get_module_display_name(name),
                "kind": "skipped",
                "reason": reason,
            }
        )
    for name, reason in sorted(manifest.failed_modules.items()):
        rows.append(
            {
                "name": name,
                "display_name": get_module_display_name(name),
                "kind": "failed",
                "reason": reason,
            }
        )
    return rows


def phenotype_readings(candidates: list[dict]) -> list[dict]:
    """Group a gene's candidate diplotypes into the distinct results a reader has to choose between.

    A reader cares about *results* ("blood group AB"), not allele pairs: two diplotypes that give
    the same phenotype (RHCE Ce/cE and CE/ce) are one reading, and repeating the explanation twice
    is noise. Order is the caller's; each reading keeps its distinct conclusions (normally one) and
    the diplotypes behind it for the technical fold. A candidate needing a structural call keeps
    that flag, so the template can say the file cannot confirm it.
    """
    readings: dict[str, dict] = {}
    for c in candidates:
        label = c.get("phenotype") or f"{c['haplotype_a']} / {c['haplotype_b']}"
        reading = readings.setdefault(
            label,
            {"phenotype": label, "conclusions": [], "diplotypes": [], "needs_structural_call": False},
        )
        if c.get("conclusion") and c["conclusion"] not in reading["conclusions"]:
            reading["conclusions"].append(c["conclusion"])
        reading["diplotypes"].append(f"{c['haplotype_a']}/{c['haplotype_b']}")
        reading["needs_structural_call"] = reading["needs_structural_call"] or bool(c.get("not_assessable"))
    return list(readings.values())


_PHENOTYPE_STATUS_ORDER = {"called": 0, "ambiguous": 1, "no_match": 2, "not_assessable": 3}
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def phenotype_topic(readings: list[dict], gene_symbol: str) -> str:
    """What a gene's card is about, in the module's own words, for headings a lay reader can parse.

    A gene symbol (``RHCE``) reads as a code. The result labels a module writes already name the
    topic ("RhD positive" / "RhD negative", "Rh markers C+ …"), so the longest run of leading words
    every label shares is the topic ("RhD", "Rh markers"). With one reading, or no shared words, it
    falls back to the gene symbol, which the card also shows as a tag.
    """
    labels = [r["phenotype"].split() for r in readings if r.get("phenotype")]
    if len(labels) < 2:
        return gene_symbol
    shared: list[str] = []
    for words in zip(*labels):
        if len(set(words)) != 1:
            break
        shared.append(words[0])
    return " ".join(shared) if shared else gene_symbol


def factor_shared_sentences(readings: list[dict]) -> list[str]:
    """Pull the sentences every reading's conclusion shares out, so the report says them once.

    When a file cannot settle a result the report lists every possible reading, and a module's
    conclusions for sibling results legitimately share their general explanation ("Rh markers are
    proteins on red blood cells…"). Printed under each reading, that paragraph repeats three times
    and buries the one sentence that differs. This keeps each reading's distinct sentences on the
    reading (``distinct``) and returns the shared ones, in the first reading's order, for the card
    to print once. With fewer than two readings nothing is factored.
    """
    if len(readings) < 2:
        for r in readings:
            r["distinct"] = list(r["conclusions"])
        return []
    split = [[s for c in r["conclusions"] for s in _SENTENCE_SPLIT.split(c.strip()) if s] for r in readings]
    common = set(split[0]).intersection(*map(set, split[1:]))
    for r, sentences in zip(readings, split):
        r["distinct"] = [" ".join(s for s in sentences if s not in common)] if any(s not in common for s in sentences) else []
    return [s for s in split[0] if s in common]


def build_phenotype_report_data(
    manifest: Optional[AnnotationManifest],
    modules_dir: Path,
    module_infos: Optional[dict[str, ModuleInfo]] = None,
) -> list[dict]:
    """One entry per phenotype module in the run, each with its per-gene calls, for the template.

    Reads ``{module}_phenotypes.parquet`` for every module the manifest recorded as
    ``kind == "phenotype"``. The parquet is the caller's contract (see phenotype_caller), so this is a
    straight projection into template dicts — no interpretation. A module whose parquet is missing
    (an error the manifest already recorded under ``failed_modules``) is skipped here and surfaces in
    "Modules not read" instead.

    Returns ``[]`` when the run had no phenotype module, so the template renders no section at all and
    a variant-only report is byte-identical to one produced before this existed.
    """
    if manifest is None:
        return []
    entries: list[dict] = []
    for output in manifest.modules:
        if output.kind != "phenotype":
            continue
        parquet_path = modules_dir / f"{output.module}_phenotypes.parquet"
        if not parquet_path.exists():
            continue
        frame = pl.read_parquet(parquet_path)
        genes = [
            {
                "gene": row["gene"],
                "status": row["status"],
                "phenotype": row["phenotype"],
                "candidates": row["candidates"],
                "sites": row["sites"],
                "phase_would_decide": row["phase_would_decide"],
                "alleles_considered": row["alleles_considered"],
                "alleles_not_assessable": row["alleles_not_assessable"],
                "unpaired_haplotypes": row["unpaired_haplotypes"],
                "drug_rows": row["drug_rows"],
                "compiler_warnings": row["compiler_warnings"],
                "readings": phenotype_readings(row["candidates"]),
            }
            for row in frame.iter_rows(named=True)
        ]
        for gene in genes:
            gene["shared_explanation"] = factor_shared_sentences(gene["readings"])
            gene["topic"] = phenotype_topic(gene["readings"], gene["gene"])
        # Firm results first, then partial ones, then what the file could not read: a reader should
        # meet what their DNA does say before the caveats. Gene symbol breaks ties so the order is
        # stable across runs (the caller's order is not).
        genes.sort(key=lambda g: (_PHENOTYPE_STATUS_ORDER.get(g["status"], 9), g["gene"]))
        info = (module_infos or {}).get(output.module)
        rules = phenotype_rules(output.module, info)
        display_name, description = module_display(output.module, info)
        for gene in genes:
            gene["rules"] = rules.get(gene["gene"], {"alleles": [], "pairs": [], "activity": [], "bins": []})
            gene["ai_explain_links"] = _build_phenotype_ai_links(display_name, gene)
            gene["phased_sites"] = sum(1 for s in gene["sites"] if s.get("phase_set") is not None)
        entries.append(
            {
                "module_name": output.module,
                "display_name": display_name,
                "description": description,
                "how_it_works": readme_section(local_module_dir(info), "How this works"),
                "genes": genes,
            }
        )
    return entries


# External links for identifiers. Each goes straight to the one human record the identifier names,
# never to a search page that could list another species or several hits, and each is built only for
# a well-formed identifier: a malformed one renders as plain text rather than a link to nowhere.
# Positions get no link: every genome-browser target we tried (Ensembl's new browser, UCSC behind a
# bot check) could not be verified to land on the right place, and a site with an rsID already links
# to dbSNP, which states its GRCh38 position.
_GENE_SYMBOL = re.compile(r"^[A-Z0-9][A-Za-z0-9-]*$")


def dbsnp_url(rsid: object) -> Optional[str]:
    """dbSNP's page for an rsID (it follows merges to the current record), or None if not an rsID."""
    return f"https://www.ncbi.nlm.nih.gov/snp/{rsid}" if isinstance(rsid, str) and RSID_PATTERN.match(rsid) else None


def hgnc_url(symbol: object) -> Optional[str]:
    """HGNC's report for an approved human gene symbol. HGNC names human genes, so no other species."""
    if not isinstance(symbol, str) or not _GENE_SYMBOL.match(symbol):
        return None
    return f"https://www.genenames.org/data/gene-symbol-report/#!/symbol/{symbol}"


def report_environment() -> jinja2.Environment:
    """The Jinja environment the report renders in, with every filter and global its templates use.

    One definition for the generator and the tests: a template that gains a filter must not render
    in production and fail in a test's hand-built environment, or the other way round.
    """
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(Path(__file__).parent / "templates")),
        autoescape=True,
    )
    env.filters["weight_color"] = _weight_color
    env.filters["genotype_str"] = _genotype_str
    env.filters["dbsnp_url"] = dbsnp_url
    env.filters["hgnc_url"] = hgnc_url
    return env


def module_display(module_name: str, info: Optional[ModuleInfo]) -> tuple[str, str]:
    """A module's title and description for the report: modules.yaml first, then the module's own manifest.

    modules.yaml only knows the modules someone configured. An installed module states its own
    ``display.title`` / ``display.description`` in ``manifest.json``, and without this fallback the
    report printed "Apoe Epsilon" over "Annotation module: apoe_epsilon" for a module that says
    "APOE ε2/ε3/ε4" about itself. A remote module has no local manifest and keeps the config defaults.
    """
    if module_name not in MODULES_CONFIG.module_metadata:
        module_dir = local_module_dir(info)
        if module_dir is not None and (module_dir / "manifest.json").exists():
            display = read_manifest(module_dir / "manifest.json").display
            if display is not None and display.title:
                return display.report_title or display.title, display.description or ""
    return get_module_display_name(module_name), get_module_description(module_name)


def readme_section(module_dir: Optional[Path], heading: str) -> list[str]:
    """Paragraphs of one ``## <heading>`` section of a module's README, or ``[]`` when there is none.

    A phenotype result is produced by a rule ("A and B both show; O shows only when both copies are
    O"), and a lay reader needs that rule in words before the result makes sense. The format has no
    field for it, but the README travels with the module, so the report reads the section by name.
    Only a module on this machine has its README at hand; a remote one simply renders no block.
    """
    if module_dir is None or not (module_dir / "README.md").exists():
        return []
    lines = (module_dir / "README.md").read_text(encoding="utf-8").splitlines()
    wanted = f"## {heading}".lower()
    inside, body = False, []
    for line in lines:
        if line.startswith("## "):
            if inside:
                break
            inside = line.strip().lower() == wanted
            continue
        if inside:
            body.append(line)
    paragraphs = [" ".join(p.split()) for p in "\n".join(body).split("\n\n")]
    return [p for p in paragraphs if p]


def phenotype_rules(module_name: str, info: Optional[ModuleInfo]) -> dict[str, dict]:
    """Per gene, the rule a professional checks a call against, read through the caller's own loader.

    ``alleles`` lists each named version with the bases that define it. The combiner then comes in
    one of the format's two shapes: ``pairs`` (enumerative: every allele pair the module maps and the
    result it gives) or ``activity`` + ``bins`` (score-and-bin: each allele's activity value, and
    the score range each result covers). This is the phenotype module's equivalent of a variant
    row's evidence, and it lives in the professional fold. Empty when the module is not a phenotype
    module.
    """
    if info is None or module_kind(info) != "phenotype":
        return {}
    definition = load_phenotype_definition(module_name, info)
    rules: dict[str, dict] = {}
    for gene, g in definition.genes.items():
        alleles = [
            {
                "name": name,
                "defined_by": [
                    {
                        "rsid": g.site_meta[key].get("rsid"),
                        "chrom": key.split(":")[0],
                        "start": int(key.split(":")[1]),
                        "allele": base,
                    }
                    for key, base in sites.items()
                ],
            }
            for name, sites in g.haplotype_alleles.items()
        ]
        pairs = [
            {"pair": f"{d['haplotype_a']}/{d['haplotype_b']}", "phenotype": d.get("phenotype") or ""}
            for d in g.diplotypes
        ]
        activity = [{"allele": allele, "value": value} for allele, value in g.activity_values.items()]
        bins = [
            {
                "range": _score_range(b.get("measure_min"), b.get("measure_max")),
                "phenotype": b.get("phenotype") or "",
            }
            for b in g.activity_bins
        ]
        rules[gene] = {"alleles": alleles, "pairs": pairs, "activity": activity, "bins": bins}
    return rules


def _score_range(low: Optional[float], high: Optional[float]) -> str:
    """An activity bin's bounds as a professional reads them: ``0``, ``0.25 to 0.5``, ``at least 1``."""
    if low is not None and high is not None:
        return f"{low:g}" if low == high else f"{low:g} to {high:g}"
    if low is not None:
        return f"at least {low:g}"
    if high is not None:
        return f"at most {high:g}"
    return "any"


def build_module_provenance(
    module_names: list[str],
    module_outputs: dict[str, ModuleOutputMapping],
    module_infos: dict[str, ModuleInfo],
) -> list[dict]:
    """One row per rendered module naming the bytes it came from.

    This is what lets a saved report be tied to the module version that produced it, and a stale
    one be told from a current one — the report used to name only the module, which is a moving
    target across a republish.

    Every field is reported exactly as far as it was established. A module discovered on
    HuggingFace has no manifest fetched at all (``scan_module_table`` reads the parquet URL and
    nothing else), so its version and digest are genuinely unknown here, and the template says so
    rather than implying an unversioned module. The digest is the module's own claim, never
    verified against the files — see ``read_module_provenance``.
    """
    rows: list[dict] = []
    for name in module_names:
        output = module_outputs.get(name)
        info = module_infos.get(name)
        digest = (output.digest if output else None) or ""
        rows.append(
            {
                "name": name,
                "display_name": get_module_display_name(name),
                "version": (output.version if output else None) or "",
                "digest": digest,
                # Merkle roots are 64 hex characters and the leading ones identify a build well
                # enough to compare two reports by eye; the full value stays in manifest.json.
                "digest_short": digest.split(":")[-1][:12],
                "lead_table": (output.lead_table if output else None)
                or (info.lead_table if info is not None else "weights"),
                # What the module says its `weight` column means (format 0.6, RM92), verbatim and
                # unparsed. Empty means the module has not said — which the template must render as
                # *Not stated*, never as an assurance that the weights mean anything in particular.
                "weighting": (output.weighting if output else None) or "",
                "source_url": (output.source_url if output else None)
                or (info.source_url if info is not None else "")
                or "",
            }
        )
    return rows


def generate_longevity_report(
    modules_dir: Path,
    output_path: Path,
    module_names: Optional[list[str]] = None,
    user_name: str = "",
    sample_name: str = "",
) -> Path:
    """
    Generate a full HTML annotation report from annotated parquet files.

    Reads all available module parquet files from the modules directory,
    builds report data structures, and renders the Jinja2 template.

    Args:
        modules_dir: Directory containing {module}_weights.parquet files
        output_path: Where to write the output HTML
        module_names: Optional list of modules to include. If None, auto-discovers.
        user_name: User name for report header
        sample_name: Sample name for report header

    Returns:
        Path to the generated HTML report
    """
    with start_action(action_type="generate_longevity_report", modules_dir=str(modules_dir)):
        # Discover module infos
        module_infos = discover_hf_modules()
        manifest = _read_annotation_manifest(modules_dir)
        module_outputs = {m.module: m for m in manifest.modules} if manifest else {}
        module_exclusions = build_module_exclusions(manifest)
        lead_tables = {name: m.lead_table for name, m in module_outputs.items()}

        # Phenotype modules are a separate engine path with no weights parquet, so they never enter
        # `available_modules` (the variant loop below is untouched by them). Build their section here so
        # their names can reach `reported_modules` too — a single-module APOE run must take APOE's own
        # report title and filename stem, not the generic multi-module heading.
        phenotype_modules = build_phenotype_report_data(manifest, modules_dir, module_infos)
        phenotype_names = [entry["module_name"] for entry in phenotype_modules]

        # Find available parquet files
        available_modules: list[str] = []
        if module_names:
            for name in module_names:
                parquet_path = modules_dir / f"{name}_weights.parquet"
                # When a manifest exists it is the authority for *this run*. A parquet left by an
                # earlier run must not override a current skipped/failed outcome and leak stale rows
                # into the report.
                produced_this_run = manifest is None or name in module_outputs
                if produced_this_run and parquet_path.exists():
                    available_modules.append(name)
        elif manifest is not None:
            available_modules = [
                name
                for name in module_outputs
                if (modules_dir / f"{name}_weights.parquet").exists()
            ]
        else:
            for parquet_file in sorted(modules_dir.glob("*_weights.parquet")):
                mod_name = parquet_file.stem.replace("_weights", "")
                available_modules.append(mod_name)

        # A module the run could not read is still a module this report is about: it gets a row in
        # "Modules not read", and a single-module run that was skipped must not fall back to the
        # generic multi-module heading as though nothing had been selected.
        reported_modules = list(available_modules)
        for name in phenotype_names:
            if name not in reported_modules:
                reported_modules.append(name)
        for excluded in module_exclusions:
            if excluded["name"] not in reported_modules:
                reported_modules.append(excluded["name"])

        # Build report data for each module
        longevity_data: Optional[dict] = None
        other_modules_data: list[dict] = []
        pgx_modules_data: list[dict] = []

        for mod_name in available_modules:
            parquet_path = modules_dir / f"{mod_name}_weights.parquet"
            info = module_infos.get(mod_name)
            lead_table = lead_tables.get(mod_name) or (
                info.lead_table if info is not None else "weights"
            )
            display_name = get_module_display_name(mod_name)

            # Route on the lead table, not the module name. A hardcoded `== "longevitymap"` meant
            # the next 0.4 family needed another branch; the engine now records `lead_table` on
            # every module it annotated, so this is a data change instead.
            if lead_table == "pharm_variants":
                mod_data = build_pharmacogenomics_report_data(parquet_path, mod_name, info)
                mod_data["display_name"] = display_name
                pgx_modules_data.append(mod_data)
            elif mod_name == "longevitymap":
                longevity_data = build_longevity_report_data(parquet_path, mod_name, info)
            else:
                mod_data = build_module_report_data(parquet_path, mod_name, info)
                mod_data["display_name"] = display_name
                other_modules_data.append(mod_data)

        # Phenotype modules are named in the provenance table too, so a saved report ties a phenotype
        # call to the module bytes behind it exactly as a variant module.
        credits = build_report_credits(available_modules, module_infos)
        module_provenance = build_module_provenance(
            available_modules + phenotype_names, module_outputs, module_infos
        )

        template = report_environment().get_template("longevity_report.html.j2")

        report_title = report_title_for_modules(reported_modules)
        report_description = report_description_for_modules(reported_modules)
        # A single phenotype module names itself from its own manifest when modules.yaml does not
        # know it (module_display), and the page header should say the same as the section would.
        if len(reported_modules) == 1 and len(phenotype_modules) == 1:
            report_title = phenotype_modules[0]["display_name"]
            report_description = phenotype_modules[0]["description"] or report_description

        html = template.render(
            report_title=report_title,
            report_description=report_description,
            preview_row_limit=TABLE_PREVIEW_ROWS,
            user_name=user_name,
            sample_name=sample_name,
            longevity=longevity_data,
            other_modules=other_modules_data,
            pgx_modules=pgx_modules_data,
            phenotype_modules=phenotype_modules,
            credits=credits,
            module_provenance=module_provenance,
            module_exclusions=module_exclusions,
            module_display_names=MODULE_DISPLAY_NAMES,
            umami_script_tag=umami_script_tag(),
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")

        return output_path
