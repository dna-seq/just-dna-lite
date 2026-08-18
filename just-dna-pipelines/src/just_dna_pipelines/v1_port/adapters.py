"""
Per-shape adapters: read a Gen-I module's curated SQLite and emit validated DSL rows.

Each adapter returns ``(ModuleSpecConfig, variants, studies, warnings)``. Curated ``weight`` values
are copied verbatim; ``state`` is taken from the source when it carries a risk direction and
otherwise from the weight's sign (``genotype.state_from_weight``). Rows that can't produce a valid
genotype/rsid are skipped and reported as warnings rather than emitted invalid.
"""

import csv
import re
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
from just_dna_format.normalize import parse_p_value

from just_dna_pipelines.module_compiler.models import RSID_PATTERN
from just_dna_pipelines.v1_port.alleles import lookup_alleles
from just_dna_pipelines.v1_port.curation import (
    apply_study_corrections,
    apply_variant_corrections,
)
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
from just_dna_pipelines.v1_port.symbols import load_symbol_resolver, resolve_panel_genes

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


def _cyrillic_count(text: str) -> int:
    return sum(1 for ch in text if "Ѐ" <= ch <= "ӿ")


def _demojibake(text: str) -> str:
    """Undo UTF-8 text that was read as cp1251, where that reading is demonstrably what happened.

    Gen-I curation carries 12 coronary rows of it: ``monocyteвЂђendothelial`` is ``monocyte‐endothelial``
    (U+2010), ``TGF-ОІ`` is ``TGF-β``, ``adiponectinвЂ™s`` is ``adiponectin’s``. This is an *encoding*
    repair, not a content one — the bytes already say the right thing and were decoded with the wrong
    codec — so it does not cross report-never-repair.

    Guarded so it cannot damage legitimate text. The round-trip must succeed, and it must **reduce** the
    number of Cyrillic-block characters: mojibake is Latin text wearing Cyrillic, so undoing it always
    removes some, while genuine Cyrillic prose either fails to re-encode or would not lose any. ASCII
    round-trips unchanged, so the common case is a no-op. thrombophilia's real Cyrillic-ES homoglyph in
    an allele cell fails the encode and is correctly left alone for a curator to decide on.
    """
    if not _cyrillic_count(text):
        return text
    try:
        decoded = text.encode("cp1251").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
    return decoded if _cyrillic_count(decoded) < _cyrillic_count(text) else text


def _clean_str(raw: object) -> Optional[str]:
    if raw is None:
        return None
    text = _demojibake(str(raw).strip())
    return text or None


#: Typographic dashes Gen-I curation used inside *numeric literals*: U+2212 MINUS SIGN, EN DASH,
#: EM DASH. Folded to ASCII ``-`` only in the numeric-cell path below — never in prose, where a dash
#: is a dash and rewriting it would change a `conclusion` the curator wrote.
_UNICODE_DASHES = str.maketrans({"−": "-", "–": "-", "—": "-"})


def _numeric_str(raw: object) -> Optional[str]:
    """A cell that is meant to *be* a number, with its dash normalized to ASCII.

    ``just_dna_format.normalize.parse_p_value`` reads ``8.68E−6`` (U+2212) as unparseable and returns
    ``None`` — measured on three vo2max ``p_value`` cells, which is why their ``p_value_num`` was null
    while the string looked perfectly fine to a reader. Normalizing how a number is *spelled* is not
    repairing a fact: the value is untouched, only its encoding, so this stays on the right side of
    report-never-repair. Applied to `p_value`, not to `conclusion`.
    """
    text = _clean_str(raw)
    return text.translate(_UNICODE_DASHES) if text else None


#: LongevityMap's `variant.association` column is a significance *verdict*, not a p-value: its only
#: values are "significant" and "non-significant". It was written into `p_value`, which is documented
#: as the raw p-value string — so all 671 study rows carried a word where a number belongs, and
#: `stat_significance`, the standard axis a consumer reads, was empty on every one of them. Mapped
#: onto `VALID_SIGNIFICANCE` here instead. Anything unrecognised returns None rather than "unknown":
#: `unknown` is a verdict the source did not give, and an empty cell is the honest reading.
_SIGNIFICANCE_BY_ASSOCIATION = {
    "significant": "significant",
    "non-significant": "not_significant",
}


def _significance(raw: object) -> Optional[str]:
    """LongevityMap's ``association`` verdict as a ``VALID_SIGNIFICANCE`` member, else ``None``."""
    text = _clean_str(raw)
    return _SIGNIFICANCE_BY_ASSOCIATION.get(text.lower()) if text else None


def _p_value_pair(raw: object) -> tuple[Optional[str], Optional[float]]:
    """``(authored spelling, typed value)`` for a p-value cell.

    ``p_value_num`` is **authored**, never derived by the compiler, so a port that fills only the free
    -form string leaves `p_value_num` and `neg_log10_p` null on every row and the module cannot sort or
    threshold its own evidence. Gen-I wrote European decimal commas (``3,00E-11``), which
    ``parse_p_value`` also refuses, so the comma is folded here too.

    Returns ``None`` for the typed half whenever the cell is not a single number — a compound cell
    like ``'[PMID:24097068]:5E-13; [PMID: 26690388]: 9E-8'`` states two p-values for two papers and
    picking one would invent an attribution. An unparseable cell keeps its authored spelling and
    leaves the typed column empty, which is the honest reading.
    """
    text = _numeric_str(raw)
    if text is None:
        return None, None
    return text, parse_p_value(text.replace(",", "."))


def _build_spec(module: V1Module) -> ModuleSpecConfig:
    meta = display_meta(module.name)
    return ModuleSpecConfig(
        module=ModuleInfo(name=module.name, version=module.version, **meta),
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
    unattributed_p = 0

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
        study_design = _clean_str(row.get("studydesign") or row.get("gwas_study_design"))
        pmids = [p for p in normalize_pmids(row.get("pmid")) if (rsid, p) not in study_seen]
        # One source row states a single p-value beside a list of papers; copying it onto each row
        # asserts every one of them reported that figure. Measured: rs1333049 emits 10 study rows and
        # 81 of 108 rows' p_value text does not cite their own pmid. Attributed only where the row
        # cites exactly one paper — see `_three_table_studies` for the same rule and its reasoning.
        p_value, p_value_num = _p_value_pair(row.get("p_value")) if len(pmids) == 1 else (None, None)
        if len(pmids) > 1 and _clean_str(row.get("p_value")):
            unattributed_p += 1
        for pmid in pmids:
            study_seen.add((rsid, pmid))
            studies.append(StudyRow(
                rsid=rsid, pmid=pmid, population=population,
                p_value=p_value, p_value_num=p_value_num, study_design=study_design,
            ))

    if skipped:
        warnings.append(f"skipped {skipped} row(s) with invalid rsid/genotype/conclusion")
    if unattributed_p:
        warnings.append(
            f"{unattributed_p} row(s) state one p-value beside several papers — left unattributed "
            f"rather than copied onto each (it would assert a figure those papers did not report)"
        )
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
    # Which rsIDs the source weights, and which of them survived. An rsID losing *every* row is a
    # different event from losing one: the module stops mentioning a variant at all, and a bare
    # "skipped N rows" count cannot say so. Measured on thrombophilia: rs8176719 (ABO) vanished
    # entirely and the only trace was `skipped 4 weight row(s)`.
    source_rsids: set[str] = set()
    kept_rsids: set[str] = set()
    for row in _rows(db, weight_table):
        rsid = _valid_rsid(row.get("rsid"))
        genotype = to_slash_genotype(row.get("genotype"))
        if rsid is not None:
            source_rsids.add(rsid)
        if rsid is None or genotype is None:
            skipped += 1
            continue
        kept_rsids.add(rsid)
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
    vanished = sorted(source_rsids - kept_rsids)
    if vanished:
        # Named, not counted: this is the module silently ceasing to mention a variant. thrombophilia's
        # rs8176719 is the ABO blood-group determinant — the best-established common risk factor for
        # venous thromboembolism — and it disappears because its source cells are unparseable rather
        # than because anyone decided it should go. Reported, never guessed at (its `ref` is `-` and its
        # `alt` is a Cyrillic homoglyph of `C`, neither of which this adapter may silently reinterpret).
        warnings.append(
            f"{len(vanished)} rsID(s) lost every weight row and are absent from the module entirely: "
            f"{', '.join(vanished)}"
        )

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
        #
        # The rsID column is spelled `rsid` in thrombophilia and `snp` in lipidmetabolism. Reading
        # only `rsid` discarded all 43 lipidmetabolism study rows and fell through to the `rsids.pmids`
        # fallback below, which happens to also yield 43 — so no row count revealed it. What was lost
        # was per-study fidelity: the fallback carries one variant-level `population`/`p_value`
        # repeated across every paper of that variant, so 23 of 36 shipped (rsid, pmid) pairs asserted
        # a p-value the source never stated for that paper, and 7 study records vanished entirely.
        for row in _rows(db, studies_table):
            rsid = _valid_rsid(row.get("rsid") or row.get("snp"))
            if rsid is None:
                continue
            p_value, p_value_num = _p_value_pair(row.get("p_value"))
            for pmid in normalize_pmids(row.get("pubmed_id")):
                if (rsid, pmid) in seen:
                    continue
                seen.add((rsid, pmid))
                studies.append(StudyRow(
                    rsid=rsid, pmid=pmid,
                    population=_clean_str(row.get("populations") or row.get("population")),
                    p_value=p_value, p_value_num=p_value_num,
                ))

    # Top up from the bracketed pmids on the rsids table. This is the *only* source for vo2max (which
    # has no studies table) and it also covers pairs a dedicated table omits — five shipped
    # lipidmetabolism pairs exist here and nowhere else, so this is a merge and not an either/or. The
    # `seen` set means a pair the dedicated table already stated keeps its per-study values.
    unattributable = 0
    for rsid, meta in rsid_meta.items():
        population = _clean_str(meta.get("population"))
        pmids = [p for p in normalize_pmids(meta.get("pmids")) if (rsid, p) not in seen]
        # The rsids table states ONE p-value per variant beside a LIST of papers, so copying it onto
        # every row asserts that each paper reported that figure. Measured on vo2max: 12 of 19 study
        # rows carried a p-value at most one of the two cited papers could have reported, and on
        # coronary 81 of 108 rows' p_value did not even cite their own pmid. Attribute it only where
        # the variant cites a single paper; where it cites several the number is real but
        # unattributable, and the format's own posture on an ambiguous cell is to leave it empty
        # rather than pick. The authored string is not lost — it stays in the source and in the log.
        p_value, p_value_num = _p_value_pair(meta.get("p_value")) if len(pmids) == 1 else (None, None)
        if len(pmids) > 1 and _clean_str(meta.get("p_value")):
            unattributable += 1
        for pmid in pmids:
            seen.add((rsid, pmid))
            studies.append(StudyRow(
                rsid=rsid, pmid=pmid, population=population,
                p_value=p_value, p_value_num=p_value_num,
            ))
    if unattributable:
        warnings.append(
            f"{unattributable} variant(s) state one p-value beside several papers — left unattributed "
            f"rather than copied onto each (it would assert a figure those papers did not report)"
        )
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
                stat_significance=_significance(r.get("association")),
                conclusion=conclusion, study_design=study_design,
            ))

    return _build_spec(module), _dedup_variants(variants, warnings), studies, warnings


# ------------------------------------------------------------------- adapter D: superhuman

# Frozen, human-reviewed PMID curation (docs/SUPERHUMAN_REFRESH_PLAN.md, Phase 4). Every PMID was
# fetched + title-verified against the gene + protective phenotype via NCBI E-utilities; nothing is
# fabricated. This file is the authoritative, narrowed variant list: superhuman is scoped to the
# specific protective alleles the source/AREP names (not every dbSNP variant in a gene region).
_SUPERHUMAN_CURATION = Path(__file__).with_name("data") / "superhuman_pmid_curation.csv"


class _SuperhumanCuration:
    """Parsed curation: which source rsids to keep, gene-level LOF grounding, and new-gene rows."""

    def __init__(self) -> None:
        self.rsid_pmids: dict[str, list[str]] = {}          # source rsid -> verified PMID(s)
        self.gene_indel_pmids: dict[str, list[str]] = {}    # LOF gene -> gene-level PMID(s)
        self.conclusion_override: dict[str, str] = {}       # rsid -> corrected conclusion
        self.added: dict[str, dict[str, object]] = {}       # new rsid -> {gene, genotype, conclusion, pmids}

    @property
    def keep_rsids(self) -> set[str]:
        return set(self.rsid_pmids)


def _load_superhuman_curation(path: Path = _SUPERHUMAN_CURATION) -> _SuperhumanCuration:
    cur = _SuperhumanCuration()
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            gene = (row.get("gene") or "").strip()
            rsid = (row.get("rsid") or "").strip()
            scope = (row.get("scope") or "rsid").strip()
            genotype = (row.get("genotype") or "").strip()
            pmid = (row.get("pmid") or "").strip()
            conclusion = (row.get("conclusion") or "").strip()
            if not pmid.isdigit():  # ROADMAP 0.2 rule: digit-only PMIDs, enforced at load
                raise ValueError(f"superhuman curation: non-digit pmid {pmid!r} for {gene}/{rsid}")
            if scope == "gene-indel":
                gene_list = cur.gene_indel_pmids.setdefault(gene, [])
                if pmid not in gene_list:
                    gene_list.append(pmid)
                continue
            if genotype:  # an addition not present in the source SQLite
                entry = cur.added.setdefault(rsid, {"gene": gene, "genotypes": [],
                                                    "conclusion": conclusion, "pmids": []})
                # The genotype cell may list several protective genotypes separated by whitespace
                # (e.g. a dominant-ish allele matched in both het and hom carriers) — collect each.
                for gt in genotype.split():
                    if gt not in entry["genotypes"]:
                        entry["genotypes"].append(gt)  # type: ignore[union-attr]
                if pmid not in entry["pmids"]:
                    entry["pmids"].append(pmid)  # type: ignore[union-attr]
                continue
            plist = cur.rsid_pmids.setdefault(rsid, [])  # existing source rsid, keep + ground
            if pmid not in plist:
                plist.append(pmid)
            if conclusion:
                cur.conclusion_override[rsid] = conclusion
    return cur


def _is_indel(row: dict[str, object]) -> bool:
    """A deleterious/structural (non-SNV) source variant: differing allele lengths, or unspecified
    (empty/'-') alleles. The 'keep deletions, drop plain SNPs' rule for the LOF dump genes."""
    ref = str(row.get("ref_allele") or "").strip().replace("-", "")
    alt = str(row.get("alt_allele") or "").strip().replace("-", "")
    if not ref or not alt:
        return True
    return len(ref) != len(alt)


def _norm_allele(raw: object) -> Optional[str]:
    """Uppercase A/C/G/T allele (single- or multi-base for indels); None if not a clean sequence."""
    a = str(raw or "").strip().upper().replace("-", "")
    return a if a and set(a) <= set("ACGT") else None


def _superhuman_genotypes(
    row: dict[str, object], resolved: Optional[tuple[Optional[str], Optional[str]]]
) -> list[str]:
    """Protective genotype(s) for a kept superhuman variant.

    The source rarely stores alleles for its named protective variants (it relied on runtime dbSNP
    lookup), so we reconstruct ref/alt from the Ensembl cache (``resolved``) exactly like
    longevitymap. The HF annotator joins on chrom+start+**genotype** (ref/alt are not compared), so
    the genotype allele-list must equal what a carrier's VCF would produce: het = sorted(ref, alt),
    hom = alt/alt. Zygosity ``both`` emits both so heterozygous and homozygous carriers each match.

    Ensembl lists **every** observed alt at the position (``C`` -> ``A|G|T``). We cannot guess which
    one the source meant, and **guessing is not harmless**: this used to emit het/hom for every
    single-base alt on the reasoning that "extra genotypes match nobody". They match somebody. Each
    one is a rendered sentence telling a real carrier they have a protective variant.

    Measured on the shipped module: 31 rsIDs carry no source allele at a multi-allelic locus,
    producing 95 of 190 weight rows, **54 of which name an allele nothing in the provenance chain
    ever stated**. `HBB rs334` asserted `A/T`, `C/T` and `G/T` all as "Malaria resistance" — only
    `T>A` is HbS. `T>C` is HbC, which the module's *own* citation (PMID 35811813) reports as **not**
    protective in that cohort (p=0.26), and `T>G` is Hb-Makassar, a benign non-sickling variant. Two
    of those three rows were fabricated claims about a person's malaria risk.

    So: a locus with exactly one alt is unambiguous and is reconstructed. A locus with several, where
    the source named none, yields **nothing** and is reported — the same rule the rest of this port
    follows for a symbol it cannot resolve. Indel alts (multi-base) are used only when no SNV alt
    exists; indel ref/alt spelling can differ between Ensembl and the VCF, so those may still miss."""
    gt = to_slash_genotype(row.get("genotype"))
    if gt:  # explicit two-base genotype in the source (e.g. APOA2 'CC', APOE 'TT')
        return [gt]

    ref = _norm_allele(row.get("ref_allele"))
    src_alt = _norm_allele(row.get("alt_allele"))
    if ref is not None and src_alt is not None:
        alts = [src_alt]  # the source spelled out this row's specific alt
    else:
        rref, ralt = resolved or (None, None)
        ref = ref or _norm_allele(rref)
        clean = [a for a in (_norm_allele(t) for t in str(ralt or "").split("|")) if a]
        singles = [a for a in clean if len(a) == 1]
        alts = singles or clean  # SNV alts; fall back to indel alts only if no SNV
        if src_alt is not None and src_alt not in alts:
            alts.append(src_alt)
        # The source named no allele. One alt at the locus is determined; several is a guess, and a
        # guess here is a fabricated clinical claim (see the docstring's rs334 case).
        if src_alt is None and len(alts) > 1:
            return []
    if not alts:
        return []

    zyg = str(row.get("zygosity") or "").strip().lower()
    out: list[str] = []
    for alt in alts:
        hom = "/".join(sorted([alt, alt]))
        het = "/".join(sorted([ref, alt])) if ref else None
        if zyg.startswith("hom"):
            out.append(hom)
        elif zyg.startswith("het"):
            out.append(het or hom)
        else:  # 'both' or unspecified: match carriers in either zygosity
            out.extend(g for g in (het, hom) if g)
    return list(dict.fromkeys(out))


def adapt_superhuman(
    module: V1Module, db: Path, ensembl_cache: Optional[Path] = None
) -> AdapterResult:
    warnings: list[str] = []
    variants: list[VariantRow] = []
    studies: list[StudyRow] = []
    study_seen: set[tuple[str, str]] = set()
    skipped = 0
    dropped_unnamed = 0
    ambiguous_allele: set[str] = set()

    curation = _load_superhuman_curation()

    # Pass 1: select the kept source rows (narrowing) and collect rsids that need allele resolution.
    kept: list[tuple[dict[str, object], str, str, list[str]]] = []  # (row, rsid, gene, pmids)
    need_alleles: set[str] = set()
    for row in _rows(db, "superhuman"):
        rsid = _valid_rsid(row.get("rsid"))
        if rsid is None:
            # A blank rsid is a citation-only / non-variant source row (e.g. the PCSK9 row that only
            # carries the Cohen-2006 URL — its variant is R46L, curated as rs11591147), not malformed
            # data: skip it silently. Only a present-but-unparseable rsid is a real skip worth warning.
            if str(row.get("rsid") or "").strip():
                skipped += 1
            continue
        gene = _clean_str(row.get("gene"))
        gene_norm = (gene.strip() if gene else gene) or ""

        # Keep a source variant only if it is a curated named allele, or an indel-class (deleterious)
        # variant of a gene grounded at the gene level. Plain unnamed SNPs are dropped (narrowing).
        if rsid in curation.keep_rsids:
            study_pmids = curation.rsid_pmids[rsid]
        elif gene_norm in curation.gene_indel_pmids and _is_indel(row):
            study_pmids = curation.gene_indel_pmids[gene_norm]
        else:
            dropped_unnamed += 1
            continue
        kept.append((row, rsid, gene_norm, study_pmids))
        if to_slash_genotype(row.get("genotype")) is None and (
            _norm_allele(row.get("ref_allele")) is None or _norm_allele(row.get("alt_allele")) is None
        ):
            need_alleles.add(rsid)

    ref_alt = lookup_alleles(need_alleles, ensembl_cache)
    if need_alleles and not ref_alt:
        warnings.append(
            "Ensembl allele cache unavailable: named protective genotypes could not be "
            "reconstructed for variants lacking source alleles; those rows were skipped"
        )

    # Pass 2: build variants + study rows.
    for row, rsid, gene_norm, study_pmids in kept:
        genotypes = _superhuman_genotypes(row, ref_alt.get(rsid))
        if not genotypes:
            skipped += 1
            ambiguous_allele.add(rsid)
            continue
        superability = _clean_str(row.get("superability")) or ""
        adverse = _clean_str(row.get("adverse_effects"))
        base = superability + (f" Adverse effects: {adverse}" if adverse else "")
        conclusion = curation.conclusion_override.get(rsid) or base or superability or "Beneficial variant"
        for genotype in genotypes:
            variants.append(VariantRow(
                rsid=rsid,
                genotype=genotype,
                weight=None,  # superhuman carries no curated effect size — never invented
                # AREP "protective alleles" are beneficial by definition; with no numeric weight the
                # direction is carried by `state` (the report colors by it), not a fabricated weight.
                state="protective",
                conclusion=conclusion,
                gene=gene_norm or None,
            ))
        for pmid in study_pmids:
            if (rsid, pmid) in study_seen:
                continue
            study_seen.add((rsid, pmid))
            # `conclusion`, not `superability`: the curated override is a *correction* of the source
            # text, and building the study row from the raw string shipped both readings on one page
            # — the report renders the study conclusion in the per-variant citations table beside the
            # corrected weights text. Measured: rs5082 (APOA2) read "Low coronary disease" here while
            # weights carried "…BMI and food intake (not coronary disease; label corrected per
            # Corella 2007)", and rs324420 (FAAH) likewise. Those are two of the four flag fixes
            # GAPS.md records as done; half of each landed.
            studies.append(StudyRow(rsid=rsid, pmid=pmid, conclusion=conclusion or None))

    # New additions not present in the source SQLite (refresh genes + curated missing alleles).
    for rsid, entry in curation.added.items():
        for genotype in entry["genotypes"]:  # type: ignore[union-attr]
            variants.append(VariantRow(
                rsid=rsid,
                genotype=str(genotype),
                weight=None,
                state="protective",  # additions are protective alleles too (see above)
                conclusion=str(entry["conclusion"]) or "Beneficial variant",
                gene=str(entry["gene"]),
            ))
        for pmid in entry["pmids"]:  # type: ignore[union-attr]
            if (rsid, pmid) in study_seen:
                continue
            study_seen.add((rsid, pmid))
            studies.append(StudyRow(rsid=rsid, pmid=pmid, conclusion=str(entry["conclusion"]) or None))

    if skipped:
        warnings.append(f"skipped {skipped} row(s) with invalid rsid/unresolvable genotype")
    if ambiguous_allele:
        warnings.append(
            f"{len(ambiguous_allele)} rsID(s) name no allele in the source and sit at a multi-allelic "
            f"locus, so which alt is the protective one cannot be established — no genotype emitted "
            f"rather than one per alt (that fabricated 54 of 190 rows, incl. HBB rs334 asserting HbC "
            f"and Hb-Makassar as malaria-protective): {', '.join(sorted(ambiguous_allele))}"
        )
    warnings.append(
        f"narrowed to {len(variants)} curated protective-allele genotype row(s) across the named "
        f"genes (dropped {dropped_unnamed} unnamed dbSNP variant(s)); grounded {len(studies)} study "
        f"row(s) on human-verified PMIDs (superhuman_pmid_curation.csv; docs/SUPERHUMAN_REFRESH_PLAN.md)"
    )
    return _build_spec(module), _dedup_variants(variants, warnings), studies, warnings


# -------------------------------------------------------------- adapter E: ClinVar gene panel

def _panel_conclusion(cv: ClinVarVariant) -> str:
    sig = cv.significance.replace("_", " ").replace("|", ", ")
    generic = {"", "not specified", "not provided"}
    cond = f" — {cv.condition}" if cv.condition and cv.condition.lower() not in generic else ""
    return f"ClinVar {sig} variant in {cv.gene}{cond}"


def adapt_gene_panel(
    module: V1Module, db: Optional[Path], ensembl_cache: Optional[Path] = None
) -> AdapterResult:
    """cardio / cancer / pathogenic: flag ClinVar pathogenic variants (optionally by gene panel).

    Reference implementation for the gene-panel module type (just-dna-format ROADMAP item 7). The
    authored source is just a gene list (``cardio``/``cancer``); ClinVar supplies the actual
    pathogenic variants, which we enumerate as risk-state rows (both heterozygous and homozygous-alt
    carrier genotypes) so any carrier is flagged. ``pathogenic`` has no gene list — ``db`` is ``None``
    and every pathogenic ClinVar variant is kept (a genome-wide pathogenicity flag). Every variant is
    grounded to the ClinVar resource paper.
    """
    warnings: list[str] = []
    if db is None:
        genes: Optional[set[str]] = None  # pathogenic: no gene filter, keep all pathogenic variants
    else:
        raw_genes = {line.strip() for line in Path(db).read_text().splitlines() if line.strip()}
        if not raw_genes:
            return _build_spec(module), [], [], [f"empty gene list in {db.name}"]
        # Reconcile legacy/alias symbols to the current NCBI symbols ClinVar's GENEINFO uses.
        resolver = load_symbol_resolver()
        genes, alias_map, unresolved = resolve_panel_genes(raw_genes, resolver)
        if resolver is None:
            warnings.append(
                "gene-symbol resolver unavailable (no NCBI gene_info cache) — panel matched by "
                "literal symbol only; legacy aliases may miss variants"
            )
        if alias_map:
            pairs = ", ".join(f"{old}→{new}" for old, new in sorted(alias_map.items()))
            warnings.append(f"resolved {len(alias_map)} legacy gene alias(es): {pairs}")
        if unresolved:
            warnings.append(
                f"{len(unresolved)} panel symbol(s) not current NCBI symbols or known aliases "
                f"(likely source typos; kept but match nothing): {', '.join(unresolved)}"
            )

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

    scope = (
        f"{len(genes)} panel gene(s), {stats['genes_matched']} matched"
        if genes is not None else f"all pathogenic genes ({stats['genes_matched']} matched)"
    )
    warnings.append(
        f"gene-panel over ClinVar: {stats['matched']} pathogenic variant record(s) across "
        f"{scope}; {stats['skipped_non_acgt']} non-ACGT/symbolic and "
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


#: Separators Gen-I curation used inside a single `gene` cell. `ABCG8, ABCG5` and `BIRC7, YTHDF1`
#: are two genes in one cell; `CXCL12 (LINC02881)` is a symbol with its lncRNA in parentheses.
_GENE_SPLIT = re.compile(r"[,;/]| \(")

#: Curation decisions, not guesses: two Gen-I cells are one-character truncations of a symbol the
#: variant unambiguously identifies, so the reading is settled by the variant rather than by string
#: similarity. Recorded here, per row, with the reason — anything less certain stays reported.
#:
#: * ``GUCYA3`` on rs7692387 — the chromosome-4 coronary GWAS locus in *GUCY1A3*, which HGNC has
#:   since renamed *GUCY1A1*. Both the truncation and the rename are resolved in one step.
#: * ``SERPINE`` on rs1799889 — the PAI-1 4G/5G promoter indel, which is in *SERPINE1*.
_CURATED_SYMBOL_FIXES: dict[str, str] = {
    "GUCYA3": "GUCY1A1",
    "SERPINE": "SERPINE1",
}


def normalize_genes(variants: list[VariantRow], warnings: list[str]) -> list[VariantRow]:
    """Resolve each row's ``gene`` to a symbol HGNC still recognises.

    The registry's pre-publish check runs a gene-symbol currency pass, and it is what surfaced this:
    Gen-I curation put two genes in one cell (``ABCG8, ABCG5``), parenthesised a second identifier
    (``CXCL12 (LINC02881)``), and carries plain truncations and retired aliases (``SERPINE`` for
    SERPINE1, ``FLJ44450``, ``GUCYA3``). A cell like that is not a gene symbol at all, so nothing
    downstream can join on it.

    The rule: split the cell, resolve each token against NCBI ``gene_info`` (current symbol, else
    known synonym), and keep the **first token that resolves**. A cell where nothing resolves is
    left exactly as authored and reported — a symbol nobody recognises is a curation question, and
    guessing at it would be inventing an assertion the source never made.
    """
    resolver = load_symbol_resolver()
    if resolver is None:
        warnings.append(
            "gene-symbol resolver unavailable (no NCBI gene_info cache) — gene cells left as authored"
        )
        return variants

    remapped: dict[str, str] = {}
    unresolved: set[str] = set()
    out: list[VariantRow] = []
    for variant in variants:
        raw = (variant.gene or "").strip()
        if not raw:
            out.append(variant)
            continue
        current = _CURATED_SYMBOL_FIXES.get(raw) or next(
            (
                resolved
                for token in _GENE_SPLIT.split(raw)
                if (resolved := resolver.current(token.strip().rstrip(")"))) is not None
            ),
            None,
        )
        if current is None:
            unresolved.add(raw)
            out.append(variant)
            continue
        if current != raw:
            remapped[raw] = current
            variant = variant.model_copy(update={"gene": current})
        out.append(variant)

    if remapped:
        pairs = ", ".join(f"{old}→{new}" for old, new in sorted(remapped.items()))
        warnings.append(f"normalized {len(remapped)} gene symbol(s): {pairs}")
    if unresolved:
        warnings.append(
            f"{len(unresolved)} gene cell(s) match no current NCBI symbol or known synonym "
            f"(kept as authored, never guessed): {', '.join(sorted(unresolved))}"
        )
    return out


def run_adapter(
    module: V1Module, db: Path, ensembl_cache: Optional[Path] = None
) -> AdapterResult:
    spec, variants, studies, warnings = ADAPTERS[module.adapter](module, db, ensembl_cache)
    variants = normalize_genes(variants, warnings)
    # Curated corrections come last, so they act on the rows as finally authored and a reason is
    # recorded for each. They are the only place this port changes a *fact* the source states — the
    # adapters transcribe, `normalize_genes` reconciles a symbol to HGNC, and anything that needs a
    # judgement about the science lives in `data/curation/` with its evidence. See curation.py.
    variants = apply_variant_corrections(module.name, variants, warnings)
    studies = apply_study_corrections(module.name, studies, warnings)
    return spec, variants, studies, warnings
