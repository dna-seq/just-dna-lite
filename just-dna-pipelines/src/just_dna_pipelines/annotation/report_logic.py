"""
Report generation logic for annotation modules.

Reads annotated parquet files produced by the HF module annotation pipeline,
enriches them with annotations and studies data from HuggingFace,
and renders HTML reports using Jinja2 templates.
"""

from pathlib import Path
from typing import Optional

import jinja2
import polars as pl
from eliot import log_message, start_action
from just_dna_format.alleles import split_genotype
from just_dna_format.derive import clin_sig_from_booleans, direction_from_state

from just_dna_pipelines.annotation.analytics import umami_script_tag
from just_dna_pipelines.annotation.hf_modules import (
    AnnotationManifest,
    ModuleInfo,
    ModuleOutputMapping,
    ModuleTable,
    scan_module_table,
    discover_hf_modules,
    DISCOVERED_MODULES,
)
from just_dna_pipelines.annotation.restoration import (
    EVIDENCE_COLUMN,
    EVIDENCE_RESTORED,
    FLANK_COLUMN,
)
from just_dna_pipelines.module_config import build_display_names_dict


ANNOTATION_REPORT_COLUMNS: tuple[str, ...] = ("gene", "category", "phenotype")


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
    correct in both eras. Returns one of {protective, risk, neutral, unknown}.
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
        if annotations_lf is None:
            return _ensure_annotation_report_columns(weights_lf.collect())

        enriched = _join_annotations(weights_lf, annotations_lf, module_name)
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
        "alt": "/".join(row.get("alts", []) or []),
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
        "studies": studies_by_rsid.get(rsid, []),
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
    }
    for axis in _AUTHORED_AXES:
        value = row.get(axis)
        variant[axis] = "" if value is None else value
    return variant


def load_studies_for_variants(
    rsids: list[str],
    module_name: str,
    module_info: Optional[ModuleInfo] = None,
) -> dict[str, list[dict[str, str]]]:
    """
    Load studies data for a set of rsids from an HF module.

    Returns a mapping of rsid -> list of study dicts.
    """
    with start_action(action_type="load_studies_for_variants", module=module_name):
        if not rsids:
            return {}

        studies_lf = _scan_optional_module_table(
            module_name,
            ModuleTable.STUDIES,
            module_info=module_info,
        )
        if studies_lf is None:
            return {}

        # Filter to relevant rsids
        studies_df = studies_lf.filter(
            pl.col("rsid").is_in(rsids)
        ).collect()

        result: dict[str, list[dict[str, str]]] = {}
        for row in studies_df.iter_rows(named=True):
            rsid = row["rsid"]
            if rsid not in result:
                result[rsid] = []
            result[rsid].append({
                "pmid": row.get("pmid", ""),
                "population": row.get("population", ""),
                "p_value": row.get("p_value", ""),
                "conclusion": row.get("conclusion", ""),
                "study_design": row.get("study_design", ""),
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
        studies_by_rsid = load_studies_for_variants(rsids, module_name, module_info)

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
        studies_by_rsid = load_studies_for_variants(rsids, module_name, module_info)

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
        studies_by_rsid = load_studies_for_variants(rsids, module_name, module_info)

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


def _module_outputs_from_manifest(modules_dir: Path) -> dict[str, ModuleOutputMapping]:
    """Read the run's ``manifest.json`` → one ``ModuleOutputMapping`` per annotated module.

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
        return {}

    try:
        manifest = AnnotationManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )
    except (ValueError, OSError) as exc:
        log_message(
            message_type="warning",
            action="unreadable_annotation_manifest",
            path=str(manifest_path),
            reason=str(exc),
        )
        return {}

    return {m.module: m for m in manifest.modules}


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
                "display_name": MODULE_DISPLAY_NAMES.get(
                    name, name.replace("_", " ").title()
                ),
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
    Generate a full longevity HTML report from annotated parquet files.

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
        module_outputs = _module_outputs_from_manifest(modules_dir)
        lead_tables = {name: m.lead_table for name, m in module_outputs.items()}

        # Find available parquet files
        available_modules: list[str] = []
        if module_names:
            for name in module_names:
                parquet_path = modules_dir / f"{name}_weights.parquet"
                if parquet_path.exists():
                    available_modules.append(name)
        else:
            for parquet_file in sorted(modules_dir.glob("*_weights.parquet")):
                mod_name = parquet_file.stem.replace("_weights", "")
                available_modules.append(mod_name)

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
            display_name = MODULE_DISPLAY_NAMES.get(
                mod_name, mod_name.replace("_", " ").title()
            )

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

        credits = build_report_credits(available_modules, module_infos)
        module_provenance = build_module_provenance(
            available_modules, module_outputs, module_infos
        )

        # Load and render template
        template_dir = Path(__file__).parent / "templates"
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(template_dir)),
            autoescape=True,
        )
        # Register custom filters
        env.filters["weight_color"] = _weight_color
        env.filters["genotype_str"] = _genotype_str

        template = env.get_template("longevity_report.html.j2")

        html = template.render(
            user_name=user_name,
            sample_name=sample_name,
            longevity=longevity_data,
            other_modules=other_modules_data,
            pgx_modules=pgx_modules_data,
            credits=credits,
            module_provenance=module_provenance,
            module_display_names=MODULE_DISPLAY_NAMES,
            umami_script_tag=umami_script_tag(),
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")

        return output_path
