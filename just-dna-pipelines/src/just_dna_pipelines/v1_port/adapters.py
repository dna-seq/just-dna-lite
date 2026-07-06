"""
Per-shape adapters: read a Gen-I module's curated SQLite and emit validated DSL rows.

Each adapter returns ``(ModuleSpecConfig, variants, studies, warnings)``. Curated ``weight`` values
are copied verbatim; ``state`` is taken from the source when it carries a risk direction and
otherwise from the weight's sign (``genotype.state_from_weight``). Rows that can't produce a valid
genotype/rsid are skipped and reported as warnings rather than emitted invalid.
"""

import sqlite3
from pathlib import Path
from typing import Optional

from just_dna_pipelines.module_compiler.models import (
    Defaults,
    ModuleInfo,
    ModuleSpecConfig,
    StudyRow,
    VariantRow,
)
from just_dna_pipelines.module_compiler.models import RSID_PATTERN
from just_dna_pipelines.v1_port.alleles import lookup_alleles
from just_dna_pipelines.v1_port.clinvar import (
    CLINVAR_RESOURCE_PMID,
    MAX_ALLELE_LEN,
    ClinVarVariant,
    load_gene_panel_variants,
)
from just_dna_pipelines.v1_port.genotype import (
    genotype_from_allele_zygosity,
    state_from_weight,
    to_slash_genotype,
)
from just_dna_pipelines.v1_port.pmid import normalize_pmids
from just_dna_pipelines.v1_port.sources import V1Module, display_meta

_CURATOR = "just-dna-seq"
_METHOD = "expert-curated"

AdapterResult = tuple[ModuleSpecConfig, list[VariantRow], list[StudyRow], list[str]]


# ---------------------------------------------------------------------------- helpers

def _rows(db: Path, table: str) -> list[dict[str, object]]:
    """Read a whole table as a list of lowercase-keyed dicts (case-insensitive columns)."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        con.row_factory = sqlite3.Row
        cur = con.execute(f'SELECT * FROM "{table}"')
        return [{str(k).lower(): r[k] for k in r.keys()} for r in cur.fetchall()]
    finally:
        con.close()


def _table_names(db: Path) -> list[str]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    finally:
        con.close()


def _parse_weight(raw: object) -> Optional[float]:
    """Parse a curated weight verbatim into a float. Blank/unparseable → None (never invented)."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        # European decimal comma used by some p_value-like fields; be lenient for weights too.
        try:
            return float(text.replace(",", "."))
        except ValueError:
            return None


def _valid_rsid(raw: object) -> Optional[str]:
    if raw is None:
        return None
    rsid = str(raw).strip()
    return rsid if RSID_PATTERN.match(rsid) else None


def _clean_str(raw: object) -> Optional[str]:
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _build_spec(module: V1Module) -> ModuleSpecConfig:
    meta = display_meta(module.name)
    return ModuleSpecConfig(
        module=ModuleInfo(name=module.name, **meta),
        defaults=Defaults(curator=_CURATOR, method=_METHOD, priority=None),
        genome_build="GRCh38",
    )


def _dedup_variants(
    variants: list[VariantRow], warnings: list[str]
) -> list[VariantRow]:
    """Drop duplicate (variant_key, genotype) pairs (the compiler rejects them), keeping the first."""
    seen: set[tuple[str, str]] = set()
    out: list[VariantRow] = []
    dropped = 0
    for v in variants:
        key = (v.variant_key, v.genotype)
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        out.append(v)
    if dropped:
        warnings.append(f"dropped {dropped} duplicate (variant, genotype) row(s)")
    return out


# ---------------------------------------------------------------------------- adapter A: coronary

def adapt_coronary(
    module: V1Module, db: Path, ensembl_cache: Optional[Path] = None
) -> AdapterResult:
    warnings: list[str] = []
    variants: list[VariantRow] = []
    study_seen: set[tuple[str, str]] = set()
    studies: list[StudyRow] = []
    skipped = 0

    for row in _rows(db, "coronary_disease"):
        rsid = _valid_rsid(row.get("rsid"))
        genotype = to_slash_genotype(row.get("genotype"))
        conclusion = _clean_str(row.get("conclusion"))
        if rsid is None or genotype is None or conclusion is None:
            skipped += 1
            continue
        weight = _parse_weight(row.get("weight"))
        variants.append(VariantRow(
            rsid=rsid,
            genotype=genotype,
            weight=weight,
            state=state_from_weight(weight),
            conclusion=conclusion,
            gene=_clean_str(row.get("gene")),
        ))
        population = _clean_str(row.get("population"))
        p_value = _clean_str(row.get("p_value"))
        study_design = _clean_str(row.get("studydesign") or row.get("gwas_study_design"))
        for pmid in normalize_pmids(row.get("pmid")):
            if (rsid, pmid) in study_seen:
                continue
            study_seen.add((rsid, pmid))
            studies.append(StudyRow(
                rsid=rsid, pmid=pmid, population=population,
                p_value=p_value, study_design=study_design,
            ))

    if skipped:
        warnings.append(f"skipped {skipped} row(s) with invalid rsid/genotype/conclusion")
    return _build_spec(module), _dedup_variants(variants, warnings), studies, warnings


# ------------------------------------------------------------------- adapter B: three-table shape

def _find_table(names: list[str], *candidates: str) -> Optional[str]:
    lower = {n.lower(): n for n in names}
    for c in candidates:
        if c in lower:
            return lower[c]
    return None


def adapt_three_table(
    module: V1Module, db: Path, ensembl_cache: Optional[Path] = None
) -> AdapterResult:
    """thrombophilia / lipidmetabolism / vo2max: rsids + weight(+studies)."""
    warnings: list[str] = []
    names = _table_names(db)
    weight_table = _find_table(names, "weight", "genotype_weights")
    rsids_table = _find_table(names, "rsids", "rsid")
    studies_table = _find_table(names, "studies")
    if weight_table is None or rsids_table is None:
        return _build_spec(module), [], [], [f"missing weight/rsids table in {names}"]

    # rsid -> curated variant-level metadata (gene, per-rsid conclusion, pmids, population, p_value)
    rsid_meta: dict[str, dict[str, object]] = {}
    for row in _rows(db, rsids_table):
        rsid = _valid_rsid(row.get("rsid"))
        if rsid is not None:
            rsid_meta[rsid] = row

    variants: list[VariantRow] = []
    skipped = 0
    for row in _rows(db, weight_table):
        rsid = _valid_rsid(row.get("rsid"))
        genotype = to_slash_genotype(row.get("genotype"))
        if rsid is None or genotype is None:
            skipped += 1
            continue
        weight = _parse_weight(row.get("weight"))
        meta = rsid_meta.get(rsid, {})
        conclusion = (
            _clean_str(row.get("genotype_specific_conclusion"))
            or _clean_str(meta.get("rsid_conclusion"))
            or ""
        )
        variants.append(VariantRow(
            rsid=rsid,
            genotype=genotype,
            weight=weight,
            state=state_from_weight(weight),
            conclusion=conclusion,
            gene=_clean_str(meta.get("gene")),
        ))

    if skipped:
        warnings.append(f"skipped {skipped} weight row(s) with invalid rsid/genotype")

    studies = _three_table_studies(db, studies_table, rsid_meta, warnings)
    return _build_spec(module), _dedup_variants(variants, warnings), studies, warnings


def _three_table_studies(
    db: Path,
    studies_table: Optional[str],
    rsid_meta: dict[str, dict[str, object]],
    warnings: list[str],
) -> list[StudyRow]:
    studies: list[StudyRow] = []
    seen: set[tuple[str, str]] = set()

    if studies_table is not None:
        # Dedicated studies table with a clean integer pubmed_id.
        for row in _rows(db, studies_table):
            rsid = _valid_rsid(row.get("rsid"))
            if rsid is None:
                continue
            for pmid in normalize_pmids(row.get("pubmed_id")):
                if (rsid, pmid) in seen:
                    continue
                seen.add((rsid, pmid))
                studies.append(StudyRow(
                    rsid=rsid, pmid=pmid,
                    population=_clean_str(row.get("populations") or row.get("population")),
                    p_value=_clean_str(row.get("p_value")),
                ))
        if studies:
            return studies

    # No studies table (vo2max) or it was empty: fall back to bracketed pmids on the rsids table.
    for rsid, meta in rsid_meta.items():
        population = _clean_str(meta.get("population"))
        p_value = _clean_str(meta.get("p_value"))
        for pmid in normalize_pmids(meta.get("pmids")):
            if (rsid, pmid) in seen:
                continue
            seen.add((rsid, pmid))
            studies.append(StudyRow(
                rsid=rsid, pmid=pmid, population=population, p_value=p_value,
            ))
    return studies


# ------------------------------------------------------------------- adapter C: longevitymap

_ACGT = frozenset("ACGT")


def _is_base(a: Optional[str]) -> bool:
    """True only for a single uppercase ACGT base (rejects 2-base ``spec`` alleles and indels)."""
    return bool(a) and len(a) == 1 and a in _ACGT


def _longevitymap_genotype(
    row: dict[str, object], ref_alt: tuple[Optional[str], Optional[str]]
) -> Optional[str]:
    """Reconstruct the genotype from the curated effect allele + zygosity.

    hom → two copies of the curated effect allele. het → the effect allele paired with its
    complement: the Ensembl reference allele when the effect is an alt (the common case), else a
    single-base Ensembl alt when the effect *is* the reference. The Ensembl ``alt`` column is a
    ``|``-joined multiallelic list (e.g. ``A|G``), so we never concatenate it blindly — we pair the
    curated allele with its single complement. ``spec``-state rows spell the heterozygous genotype
    out directly in the two-base ``allele`` field (e.g. ``CT`` → ``C/T``), so we parse that verbatim.
    """
    zyg = str(row.get("zygosity") or "").strip().lower()
    allele = str(row.get("allele") or "").strip().upper()
    if zyg.startswith("hom"):
        return to_slash_genotype(f"{allele}{allele}")
    if zyg.startswith("het"):
        if not _is_base(allele):
            # A two-base curated allele is the heterozygous genotype spelled out ("CT" → C/T).
            return to_slash_genotype(allele)
        ref, alt = ref_alt
        ref = (ref or "").strip().upper()
        if _is_base(ref) and ref != allele:
            return to_slash_genotype(f"{ref}{allele}")
        # effect allele is the reference: pair it with a single-base alt from the Ensembl list.
        for candidate in str(alt or "").upper().split("|"):
            if _is_base(candidate) and candidate != allele:
                return to_slash_genotype(f"{allele}{candidate}")
    return None


def adapt_longevitymap(
    module: V1Module, db: Path, ensembl_cache: Optional[Path] = None
) -> AdapterResult:
    warnings: list[str] = []

    names = _table_names(db)
    genes = {r.get("id"): r for r in _rows(db, "gene")}
    pops = {r.get("id"): _clean_str(r.get("name")) for r in _rows(db, "population")}
    categories = (
        {r.get("id"): _clean_str(r.get("name")) for r in _rows(db, "categories")}
        if "categories" in {n.lower() for n in names} else {}
    )

    # Per rsid keep the row with the most informative (longest) curated conclusion — the first
    # study row for an rsid is often the empty/non-significant one.
    variant_meta: dict[str, dict[str, object]] = {}
    for r in _rows(db, "variant"):
        rsid = _valid_rsid(r.get("identifier"))
        if rsid is None:
            continue
        concl = _clean_str(r.get("conclusions")) or ""
        best = variant_meta.get(rsid)
        if best is None or len(concl) > len(_clean_str(best.get("conclusions")) or ""):
            variant_meta[rsid] = r

    allele_rows = _rows(db, "allele_weights")
    # The module stores only the effect allele; het genotypes need the ref/alt pair from Ensembl.
    ref_alt = lookup_alleles(
        {rsid for r in allele_rows if (rsid := _valid_rsid(r.get("rsid")))}, ensembl_cache
    )
    if not ref_alt:
        warnings.append(
            "Ensembl allele cache unavailable: heterozygous genotypes cannot be reconstructed; "
            "only homozygous rows kept"
        )

    variants: list[VariantRow] = []
    skipped = 0
    for row in allele_rows:
        rsid = _valid_rsid(row.get("rsid"))
        if rsid is None:
            skipped += 1
            continue
        genotype = _longevitymap_genotype(row, ref_alt.get(rsid, (None, None)))
        if genotype is None:
            skipped += 1
            continue
        weight = _parse_weight(row.get("weight"))
        vmeta = variant_meta.get(rsid, {})
        gene_row = genes.get(vmeta.get("gene_id"), {})
        gene = _clean_str(gene_row.get("symbol"))
        conclusion = _clean_str(vmeta.get("conclusions")) or (
            f"Longevity-associated variant in {gene}" if gene else "Longevity-associated variant"
        )
        variants.append(VariantRow(
            rsid=rsid,
            genotype=genotype,
            weight=weight,
            state=state_from_weight(weight),
            conclusion=conclusion,
            gene=gene,
            category=categories.get(row.get("category_id")),
            priority=_clean_str(row.get("priority")),
        ))

    if skipped:
        warnings.append(f"skipped {skipped} allele_weight row(s) (invalid rsid or unresolved genotype)")

    studies: list[StudyRow] = []
    seen: set[tuple[str, str]] = set()
    for r in _rows(db, "variant"):
        rsid = _valid_rsid(r.get("identifier"))
        if rsid is None:
            continue
        population = pops.get(r.get("population_id"))
        study_design = _clean_str(r.get("study_design"))
        conclusion = _clean_str(r.get("conclusions"))
        for pmid in normalize_pmids(r.get("quickpubmed")):
            if (rsid, pmid) in seen:
                continue
            seen.add((rsid, pmid))
            studies.append(StudyRow(
                rsid=rsid, pmid=pmid, population=population,
                p_value=_clean_str(r.get("association")),
                conclusion=conclusion, study_design=study_design,
            ))

    return _build_spec(module), _dedup_variants(variants, warnings), studies, warnings


# ------------------------------------------------------------------- adapter D: superhuman

def adapt_superhuman(
    module: V1Module, db: Path, ensembl_cache: Optional[Path] = None
) -> AdapterResult:
    warnings: list[str] = []
    variants: list[VariantRow] = []
    studies: list[StudyRow] = []
    study_seen: set[tuple[str, str]] = set()
    skipped = 0

    for row in _rows(db, "superhuman"):
        rsid = _valid_rsid(row.get("rsid"))
        if rsid is None:
            skipped += 1
            continue
        genotype = to_slash_genotype(row.get("genotype"))
        if genotype is None:
            # No explicit genotype: build from the beneficial (alt) allele + zygosity.
            genotype = genotype_from_allele_zygosity(
                row.get("alt_allele"), row.get("zygosity"),
                row.get("ref_allele"), row.get("alt_allele"),
            )
        if genotype is None:
            skipped += 1
            continue
        superability = _clean_str(row.get("superability")) or ""
        adverse = _clean_str(row.get("adverse_effects"))
        conclusion = superability + (f" Adverse effects: {adverse}" if adverse else "")
        variants.append(VariantRow(
            rsid=rsid,
            genotype=genotype,
            weight=None,  # superhuman carries no curated effect size — never invented
            state="significant",
            conclusion=conclusion or superability or "Beneficial variant",
            gene=_clean_str(row.get("gene")),
        ))
        # Most `references` are dbSNP URLs (no PMID); a subset are real PubMed links. Ground only
        # those (rsid-specific, verified citations). The full literature backfill + March-2026
        # refresh is v2 — see docs/SUPERHUMAN_REFRESH_PLAN.md.
        ref = row.get("references")
        if ref and "pubmed" in str(ref).lower():
            for pmid in normalize_pmids(ref):
                if (rsid, pmid) in study_seen:
                    continue
                study_seen.add((rsid, pmid))
                studies.append(StudyRow(rsid=rsid, pmid=pmid, conclusion=superability or None))

    if skipped:
        warnings.append(f"skipped {skipped} row(s) with invalid rsid/genotype")
    warnings.append(
        f"grounded {len(studies)} variant(s) from in-source PubMed references (subset-studies v1); "
        f"the remaining variants are ungrounded pending literature curation "
        f"(docs/SUPERHUMAN_REFRESH_PLAN.md → v2)"
    )
    return _build_spec(module), _dedup_variants(variants, warnings), studies, warnings


# -------------------------------------------------------------- adapter E: ClinVar gene panel

def _panel_conclusion(cv: ClinVarVariant) -> str:
    sig = cv.significance.replace("_", " ").replace("|", ", ")
    generic = {"", "not specified", "not provided"}
    cond = f" — {cv.condition}" if cv.condition and cv.condition.lower() not in generic else ""
    return f"ClinVar {sig} variant in {cv.gene}{cond}"


def adapt_gene_panel(
    module: V1Module, db: Path, ensembl_cache: Optional[Path] = None
) -> AdapterResult:
    """cardio / cancer: a gene list flagging ClinVar pathogenic variants in those genes.

    Reference implementation for the gene-panel module type (just-dna-format ROADMAP item 7). The
    authored source is just a gene list; ClinVar supplies the actual pathogenic variants, which we
    enumerate as risk-state rows (both heterozygous and homozygous-alt carrier genotypes) so any
    carrier is flagged. Every variant is grounded to the ClinVar resource paper.
    """
    warnings: list[str] = []
    genes = {line.strip() for line in Path(db).read_text().splitlines() if line.strip()}
    if not genes:
        return _build_spec(module), [], [], [f"empty gene list in {db.name}"]

    try:
        cv_variants, stats = load_gene_panel_variants(genes)
    except FileNotFoundError as exc:
        return _build_spec(module), [], [], [f"ClinVar VCF unavailable ({exc}); gene-panel not built"]

    # An rsid can map to more than one position across ClinVar records (indel anchor-base shifts);
    # the compiler requires one position per rsid, so null the rsid for those and key by position.
    positions_per_rsid: dict[str, set[tuple[str, int]]] = {}
    for cv in cv_variants:
        if cv.rsid:
            positions_per_rsid.setdefault(cv.rsid, set()).add((cv.chrom, cv.pos))
    ambiguous_rsids = {rs for rs, pos in positions_per_rsid.items() if len(pos) > 1}

    variants: list[VariantRow] = []
    studies: list[StudyRow] = []
    study_seen: set[str] = set()
    for cv in cv_variants:
        rsid = cv.rsid if cv.rsid and cv.rsid not in ambiguous_rsids else None
        conclusion = _panel_conclusion(cv)
        het = "/".join(sorted((cv.ref, cv.alt)))
        hom = "/".join(sorted((cv.alt, cv.alt)))
        for genotype in (het, hom):
            variants.append(VariantRow(
                rsid=rsid, chrom=cv.chrom, start=cv.pos, ref=cv.ref, alts=cv.alt,
                genotype=genotype, weight=None, state="risk", conclusion=conclusion,
                gene=cv.gene, phenotype=cv.condition, clinvar=True, pathogenic=True,
            ))
        key = rsid or f"{cv.chrom}:{cv.pos}:{cv.ref}"
        if key not in study_seen:
            study_seen.add(key)
            studies.append(StudyRow(
                rsid=rsid,
                chrom=None if rsid else cv.chrom,
                start=None if rsid else cv.pos,
                ref=None if rsid else cv.ref,
                pmid=CLINVAR_RESOURCE_PMID, conclusion=cv.condition,
                study_design="ClinVar aggregate germline classification",
            ))
    if ambiguous_rsids:
        warnings.append(
            f"{len(ambiguous_rsids)} rsid(s) mapped to multiple positions (indel anchoring) — "
            f"keyed by chrom:pos:ref instead"
        )

    warnings.append(
        f"gene-panel over ClinVar: {stats['matched']} pathogenic variant record(s) across "
        f"{len(genes)} panel gene(s); {stats['skipped_non_acgt']} non-ACGT/symbolic and "
        f"{stats['skipped_too_long']} structural (>{MAX_ALLELE_LEN}bp) allele(s) skipped (not "
        f"matchable as a two-allele genotype); grounded to ClinVar resource PMID {CLINVAR_RESOURCE_PMID}"
    )
    return _build_spec(module), _dedup_variants(variants, warnings), studies, warnings


ADAPTERS = {
    "coronary": adapt_coronary,
    "three_table": adapt_three_table,
    "longevitymap": adapt_longevitymap,
    "superhuman": adapt_superhuman,
    "gene_panel": adapt_gene_panel,
}


def run_adapter(
    module: V1Module, db: Path, ensembl_cache: Optional[Path] = None
) -> AdapterResult:
    return ADAPTERS[module.adapter](module, db, ensembl_cache)
