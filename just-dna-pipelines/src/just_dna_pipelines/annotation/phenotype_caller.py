"""Call a compound phenotype from a VCF by reading several sites together.

A phenotype like APOE ε-status or an HFE compound-het finding is not a per-position match: it is a
function of the alleles a sample carries across a small set of *defining* sites, read as a pair of
named haplotypes (a diplotype). The per-position weights engine cannot express that, so a module
authored with ``haplotypes`` + ``diplotypes`` (format 0.7) lands in ``skipped_modules`` there. This
module is the second engine path that handles it.

Scope of this version (v1):

* **Enumerative combiner only.** A module's ``diplotypes`` table enumerates allele-pair → phenotype;
  each row is a candidate diplotype with a known phenotype. The score-and-bin combiner
  (``allele_function`` + ``activity_phenotype``) is not yet implemented — no reference example
  exercises it, and building untested paths is how the report came to render 11 of 37 columns.
* **Unphased.** The normalized parquet keeps ``GT`` but not ``PS``, so every call is made from the
  unphased genotype. An unphased double-het that two diplotypes both explain is reported
  ``ambiguous`` with ``phase_would_decide`` set, never resolved by a guess. Phase sets are a
  separate, later change.
* **Diploid.** A site's expected genotype is compared as a two-allele set, and a restored site is
  ``[ref, ref]``. A haploid contig (chrY/chrM, or the hemizygous X of a male G6PD call) therefore
  reads as ``no_match`` rather than a haploid call — out of v1 scope, tracked in PHENOTYPE_CALLS.md.

The result is one :class:`PhenotypeCall` per (module, gene), written to
``{module}_phenotypes.parquet`` and rendered in its own report section. A call is **never** a silent
default: a callset that cannot establish anything is ``not_assessable``, a genotype no diplotype
explains is ``no_match``, and an unobserved site is restored to hom-ref only under the same gates the
weights engine uses (:func:`restoration.restorable_sites`), tri-state on the row.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal, Optional

import polars as pl
from eliot import start_action
from pydantic import BaseModel

from just_dna_pipelines.annotation.hf_modules import (
    ModuleInfo,
    ModuleTable,
    scan_module_table,
)
from just_dna_pipelines.annotation.restoration import (
    FLANK_COLUMN,
    RestorationContext,
    restorable_sites,
)

# A `HaplotypeRow.allele` is "bases, or a symbolic/structural allele" (just_dna_format.pgx) — there is
# no separate sv_type/copy_number column on the haplotypes table (those live on allele_function). A
# structural allele is therefore one whose spelling is not plain bases: a symbolic `<DEL>`/`<CN0>`, or
# anything outside the nucleotide alphabet. An SNV VCF cannot confirm it, so a diplotype that needs it
# is reported `not_assessable` rather than `no_match` — the sample may carry it, we just cannot see it.
# v1 has no fixture carrying a structural allele (APOE/HFE are all SNVs); this is the honest gate for
# when one arrives (RhD, a CYP2C19 SV allele).
_BASE_ALLELE = re.compile(r"^[ACGTN]+$", re.IGNORECASE)


def _is_structural_allele(allele: Optional[str]) -> bool:
    if allele is None or allele == "":
        return False
    return not bool(_BASE_ALLELE.match(allele))


Evidence = Literal["called", "restored_hom_ref", "no_call"]
MatchedBy = Literal["position", "rsid"]
Status = Literal["called", "ambiguous", "not_assessable", "no_match"]


class SiteEvidence(BaseModel):
    """What the callset says at one of a gene's defining sites."""

    rsid: Optional[str]
    chrom: str
    start: int
    ref: str
    # The sample's alleles at this site (sorted, as the VCF stores a genotype), or None when nothing
    # was observed and nothing could be restored.
    observed: Optional[list[str]]
    evidence: Evidence
    matched_by: Optional[MatchedBy]
    restored_flank_bp: Optional[int]


class Candidate(BaseModel):
    """A diplotype consistent with the observed genotype, and the phenotype it maps to."""

    haplotype_a: str
    haplotype_b: str
    phenotype: Optional[str]
    conclusion: Optional[str]
    direction: Optional[str]
    clin_sig: Optional[str]
    # True when this candidate needs a structural/copy-number allele an SNV VCF cannot confirm.
    not_assessable: bool = False


class DrugRow(BaseModel):
    """A pharmacogenomic recommendation attached to a diplotype, grouped by clinical context."""

    drug: str
    response: Optional[str]
    evidence_level: Optional[str]
    recommendation_strength: Optional[str]
    clinical_context: Optional[str]


class PhenotypeCall(BaseModel):
    """The report contract: one call per (module, gene). See docs/PHENOTYPE_CALLS.md."""

    module: str
    gene: str
    status: Status
    # Set only when every consistent diplotype maps to the same phenotype.
    phenotype: Optional[str]
    candidates: list[Candidate]
    sites: list[SiteEvidence]
    # True when the candidates differ only by cis/trans assignment of the same observed alleles —
    # i.e. knowing the phase would settle the call. False when the ambiguity is a no_call site whose
    # genotype (not its phase) would decide.
    phase_would_decide: bool
    alleles_considered: list[str]
    alleles_not_assessable: list[str]
    # Haplotypes the module defines that no diplotype row pairs (measured upstream: CYP2C19 *40/*41).
    unpaired_haplotypes: list[str]
    drug_rows: list[DrugRow]
    # The module's own phase-ambiguity warnings from manifest.compilation, passed through verbatim.
    compiler_warnings: list[str]


class GeneDefinition(BaseModel):
    """Everything the caller needs about one gene of a phenotype module."""

    gene: str
    # allele name -> {(chrom, start) -> allele base at that site}. A haplotype carries `ref` at any
    # defining site it does not list (the PharmVar/CPIC unlisted-site convention).
    haplotype_alleles: dict[str, dict[str, str]]
    # (chrom, start) -> (rsid, ref, requires_callable) for every defining site of this gene.
    site_meta: dict[str, dict]
    # The diplotype rows: each a dict with haplotype_a/b, phenotype, conclusion, direction, clin_sig,
    # and the drug columns.
    diplotypes: list[dict]
    # Alleles that need a structural/copy-number call an SNV VCF cannot make.
    structural_alleles: set[str]


class PhenotypeDefinition(BaseModel):
    module: str
    genes: dict[str, GeneDefinition]
    compiler_warnings: list[str]


def _site_key(chrom: str, start: int) -> str:
    return f"{chrom}:{start}"


def load_phenotype_definition(module_name: str, info: ModuleInfo) -> PhenotypeDefinition:
    """Read a module's haplotypes + diplotypes into the per-gene structure the caller enumerates.

    The compiler's own manifest carries any phase-ambiguity warnings it raised; those are surfaced
    verbatim on every call for the module rather than recomputed here.
    """
    haplotypes = scan_module_table(module_name, ModuleTable.HAPLOTYPES, module_info=info).collect()
    diplotypes = scan_module_table(module_name, ModuleTable.DIPLOTYPES, module_info=info).collect()

    genes: dict[str, GeneDefinition] = {}
    for gene in haplotypes["gene"].unique().drop_nulls().to_list():
        gene_haps = haplotypes.filter(pl.col("gene") == gene)
        haplotype_alleles: dict[str, dict[str, str]] = {}
        site_meta: dict[str, dict] = {}
        structural_alleles: set[str] = set()
        for row in gene_haps.iter_rows(named=True):
            name = row["haplotype_name"]
            key = _site_key(row["chrom"], row["start"])
            haplotype_alleles.setdefault(name, {})[key] = row["allele"]
            site_meta.setdefault(
                key,
                {
                    "rsid": row.get("rsid"),
                    "ref": row["ref"],
                    "requires_callable": row.get("requires_callable"),
                },
            )
            if _is_structural_allele(row["allele"]):
                structural_alleles.add(name)

        gene_diplos = diplotypes.filter(pl.col("gene") == gene) if "gene" in diplotypes.columns else diplotypes
        genes[gene] = GeneDefinition(
            gene=gene,
            haplotype_alleles=haplotype_alleles,
            site_meta=site_meta,
            diplotypes=[dict(r) for r in gene_diplos.iter_rows(named=True)],
            structural_alleles=structural_alleles,
        )

    # The compiler's warnings for these bytes were kept on ModuleInfo at discovery time (the fsspec
    # probe already read and validated the manifest). Reading them from the manifest again here would
    # need the module's path resolved to a filesystem, which `info.path` on a remote module is not.
    return PhenotypeDefinition(
        module=module_name, genes=genes, compiler_warnings=list(info.manifest_compilation_warnings)
    )


def gather_site_evidence(
    vcf_lf: pl.LazyFrame,
    gene_def: GeneDefinition,
    context: RestorationContext,
) -> list[SiteEvidence]:
    """Resolve every defining site of a gene against the callset.

    Match order (SNV v1): by ``(chrom, start)`` first, then by rsID where the site carries one and the
    VCF has IDs; an unmatched site falls back to :func:`restoration.restorable_sites` (→ hom-ref where
    the callset's coverage supports it), and otherwise records ``no_call``. The indel-window match the
    ABO indel needs is deliberately out of this version.
    """
    sites = list(gene_def.site_meta.items())  # [(key, {rsid, ref, requires_callable}), ...]

    site_frame = pl.DataFrame(
        {
            "_key": [k for k, _ in sites],
            "chrom": [k.split(":")[0] for k, _ in sites],
            "start": [int(k.split(":")[1]) for k, _ in sites],
            "rsid": [m["rsid"] for _, m in sites],
            "ref": [m["ref"] for _, m in sites],
            "requires_callable": [m.get("requires_callable") for _, m in sites],
        },
        schema_overrides={"start": pl.UInt32},
    )

    observed: dict[str, dict] = {}  # key -> {"observed": [...], "matched_by": ...}

    # 1. Position match. An inner join to the callset gives the sample's genotype at each site.
    pos = (
        site_frame.lazy()
        .join(
            vcf_lf.select("chrom", "start", "genotype"),
            on=["chrom", "start"],
            how="inner",
        )
        .select("_key", "genotype")
        .collect()
    )
    for row in pos.iter_rows(named=True):
        observed[row["_key"]] = {"observed": row["genotype"], "matched_by": "position"}

    # 2. rsID match for sites position did not find, when the site names one and the VCF carries IDs.
    unresolved = site_frame.filter(
        ~pl.col("_key").is_in(list(observed.keys())) & pl.col("rsid").is_not_null()
    )
    if unresolved.height and "rsid" in vcf_lf.collect_schema().names():
        # Cast first: a callset with no IDs at all can carry an all-null `rsid` column typed `Null`,
        # which `str.split` refuses. Casting to Utf8 makes it null-valued Utf8, which splits to null.
        vcf_by_rsid = vcf_lf.with_columns(
            pl.col("rsid").cast(pl.Utf8).str.split(";").alias("_rsid_key")
        ).explode("_rsid_key", empty_as_null=True)
        rs = (
            unresolved.lazy()
            .join(
                vcf_by_rsid.select(pl.col("_rsid_key"), pl.col("genotype")),
                left_on="rsid",
                right_on="_rsid_key",
                how="inner",
            )
            .select("_key", "genotype")
            .collect()
        )
        for row in rs.iter_rows(named=True):
            observed.setdefault(row["_key"], {"observed": row["genotype"], "matched_by": "rsid"})

    # 3. Restoration for sites still unresolved. `restorable_sites` returns those whose neighbourhood
    #    the callset demonstrably reached (and honours `requires_callable`); the rest are `no_call`.
    still_absent = site_frame.filter(~pl.col("_key").is_in(list(observed.keys())))
    restored: dict[str, int] = {}
    if still_absent.height:
        eligible = restorable_sites(
            still_absent.lazy().select("_key", "chrom", "start", "requires_callable"),
            context.called_sites,
            context,
        ).collect()
        for row in eligible.iter_rows(named=True):
            restored[row["_key"]] = int(row[FLANK_COLUMN])

    evidence: list[SiteEvidence] = []
    for key, meta in sites:
        if key in observed:
            evidence.append(
                SiteEvidence(
                    rsid=meta["rsid"],
                    chrom=key.split(":")[0],
                    start=int(key.split(":")[1]),
                    ref=meta["ref"],
                    observed=list(observed[key]["observed"]),
                    evidence="called",
                    matched_by=observed[key]["matched_by"],
                    restored_flank_bp=None,
                )
            )
        elif key in restored:
            evidence.append(
                SiteEvidence(
                    rsid=meta["rsid"],
                    chrom=key.split(":")[0],
                    start=int(key.split(":")[1]),
                    ref=meta["ref"],
                    observed=[meta["ref"], meta["ref"]],
                    evidence="restored_hom_ref",
                    matched_by=None,
                    restored_flank_bp=restored[key],
                )
            )
        else:
            evidence.append(
                SiteEvidence(
                    rsid=meta["rsid"],
                    chrom=key.split(":")[0],
                    start=int(key.split(":")[1]),
                    ref=meta["ref"],
                    observed=None,
                    evidence="no_call",
                    matched_by=None,
                    restored_flank_bp=None,
                )
            )
    return evidence


def _allele_at(gene_def: GeneDefinition, haplotype: str, key: str) -> Optional[str]:
    """The base a haplotype carries at a site, applying the unlisted-site → ref convention.

    Returns None only when the haplotype is not defined at all (a diplotype naming an undefined
    allele — e.g. an unsynthesised ``*1``), which the caller records rather than guessing.
    """
    alleles = gene_def.haplotype_alleles.get(haplotype)
    if alleles is None:
        return None
    if key in alleles:
        return alleles[key]
    return gene_def.site_meta[key]["ref"]


def call_gene(
    module: str,
    gene_def: GeneDefinition,
    evidence: list[SiteEvidence],
) -> PhenotypeCall:
    """Turn the site evidence into a set of consistent diplotypes and a status.

    A candidate diplotype is *consistent* when its expected unordered genotype equals the observed
    one at every called or restored site; a no_call site is a wildcard. The phenotype is *called*
    only when every consistent candidate maps to the same phenotype, ``ambiguous`` when they disagree,
    ``no_match`` when none is consistent, and ``not_assessable`` when nothing could be observed at all
    (or the only consistent candidates need an allele an SNV VCF cannot confirm).
    """
    evidence_by_key = {_site_key(e.chrom, e.start): e for e in evidence}
    observed_keys = [k for k, e in evidence_by_key.items() if e.evidence != "no_call"]
    no_call_keys = [k for k, e in evidence_by_key.items() if e.evidence == "no_call"]

    considered = sorted(gene_def.haplotype_alleles.keys())
    not_assessable_alleles = sorted(gene_def.structural_alleles)
    paired: set[str] = set()

    kept: list[tuple[dict, dict[str, list[str]]]] = []  # (diplotype row, expected genotype per key)
    unpaired_candidates_structural = False
    for diplo in gene_def.diplotypes:
        a, b = diplo["haplotype_a"], diplo["haplotype_b"]
        paired.update({a, b})
        expected: dict[str, list[str]] = {}
        undefined = False
        for key in gene_def.site_meta:
            allele_a = _allele_at(gene_def, a, key)
            allele_b = _allele_at(gene_def, b, key)
            if allele_a is None or allele_b is None:
                undefined = True
                break
            expected[key] = sorted([allele_a, allele_b])
        if undefined:
            continue
        # Consistent with every observed (called or restored) site?
        consistent = all(
            expected[key] == sorted(evidence_by_key[key].observed) for key in observed_keys
        )
        if consistent:
            kept.append((diplo, expected))

    unpaired = sorted(set(gene_def.haplotype_alleles.keys()) - paired)

    candidates: list[Candidate] = []
    for diplo, _ in kept:
        needs_structural = (
            diplo["haplotype_a"] in gene_def.structural_alleles
            or diplo["haplotype_b"] in gene_def.structural_alleles
        )
        candidates.append(
            Candidate(
                haplotype_a=diplo["haplotype_a"],
                haplotype_b=diplo["haplotype_b"],
                phenotype=diplo.get("phenotype"),
                conclusion=diplo.get("conclusion"),
                direction=diplo.get("direction"),
                clin_sig=diplo.get("clin_sig"),
                not_assessable=needs_structural,
            )
        )

    # Status.
    assessable = [c for c in candidates if not c.not_assessable]
    if not observed_keys:
        # Nothing was seen and nothing could be restored — every candidate is trivially consistent,
        # so there is no call to make. Never fall back to a reference diplotype here.
        status: Status = "not_assessable"
        phenotype = None
    elif not candidates:
        status = "no_match"
        phenotype = None
    elif not assessable:
        # The only consistent diplotypes need a structural allele we cannot confirm from an SNV VCF.
        status = "not_assessable"
        phenotype = None
    else:
        phenotypes = {c.phenotype for c in assessable}
        if len(phenotypes) == 1:
            status = "called"
            phenotype = next(iter(phenotypes))
        else:
            status = "ambiguous"
            phenotype = None

    # phase_would_decide: the ambiguity is pure cis/trans when the consistent candidates agree on the
    # expected genotype at every no_call site (so no missing *call* is what splits them) — the only
    # remaining unknown is which homolog carries which observed allele.
    phase_would_decide = False
    if status == "ambiguous":
        no_call_sigs = {
            tuple(tuple(expected[k]) for k in no_call_keys) for _, expected in kept
        }
        phase_would_decide = len(no_call_sigs) == 1

    drug_rows = _drug_rows([diplo for diplo, _ in kept])

    # module-level warnings are attached by the caller; per-gene call carries a placeholder filled in
    # by call_phenotype_module so every gene of a module shows the same compiler warnings.
    return PhenotypeCall(
        module=module,
        gene=gene_def.gene,
        status=status,
        phenotype=phenotype,
        candidates=candidates,
        sites=evidence,
        phase_would_decide=phase_would_decide,
        alleles_considered=considered,
        alleles_not_assessable=not_assessable_alleles,
        unpaired_haplotypes=unpaired,
        drug_rows=drug_rows,
        compiler_warnings=[],
    )


def _drug_rows(diplotypes: list[dict]) -> list[DrugRow]:
    """Pharmacogenomic rows from the consistent diplotypes, one per (drug, clinical_context).

    The caller never picks a clinical setting — every distinct (drug, context) is carried so the
    report can render them side by side.
    """
    seen: set[tuple] = set()
    rows: list[DrugRow] = []
    for diplo in diplotypes:
        drug = diplo.get("drug")
        if drug in (None, ""):
            continue
        key = (drug, diplo.get("clinical_context"))
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            DrugRow(
                drug=drug,
                response=diplo.get("response"),
                evidence_level=diplo.get("evidence_level"),
                recommendation_strength=diplo.get("recommendation_strength"),
                clinical_context=diplo.get("clinical_context"),
            )
        )
    return rows


def call_phenotype_module(
    vcf_lf: pl.LazyFrame,
    module_name: str,
    info: ModuleInfo,
    context: RestorationContext,
    output_path: Path,
) -> tuple[Path, int]:
    """Call every gene of a phenotype module and write ``{module}_phenotypes.parquet``.

    Returns ``(path, n_called)`` where ``n_called`` is the number of genes whose status is ``called``.
    v1 treats every call as unphased.
    """
    with start_action(action_type="call_phenotype_module", module=module_name):
        definition = load_phenotype_definition(module_name, info)
        calls: list[PhenotypeCall] = []
        for gene, gene_def in definition.genes.items():
            evidence = gather_site_evidence(vcf_lf, gene_def, context)
            call = call_gene(module_name, gene_def, evidence)
            call.compiler_warnings = definition.compiler_warnings
            calls.append(call)

        n_called = sum(1 for c in calls if c.status == "called")
        _write_calls(calls, output_path)
        return output_path, n_called


# The parquet schema is stated explicitly rather than inferred from the rows: polars infers a struct
# dtype per row from a dict, and a module with a `no_match` gene (empty `candidates`) beside a `called`
# one (populated `candidates`), or a `sites` list whose `observed` is null on one row and a list on
# another, gives per-row struct dtypes that will not unify into one column. Stating the schema also
# lets an empty module write typed-empty columns rather than a 0x0 frame.
_CANDIDATE_STRUCT = pl.Struct(
    {
        "haplotype_a": pl.String,
        "haplotype_b": pl.String,
        "phenotype": pl.String,
        "conclusion": pl.String,
        "direction": pl.String,
        "clin_sig": pl.String,
        "not_assessable": pl.Boolean,
    }
)
_SITE_STRUCT = pl.Struct(
    {
        "rsid": pl.String,
        "chrom": pl.String,
        "start": pl.Int64,
        "ref": pl.String,
        "observed": pl.List(pl.String),
        "evidence": pl.String,
        "matched_by": pl.String,
        "restored_flank_bp": pl.Int64,
    }
)
_DRUG_STRUCT = pl.Struct(
    {
        "drug": pl.String,
        "response": pl.String,
        "evidence_level": pl.String,
        "recommendation_strength": pl.String,
        "clinical_context": pl.String,
    }
)
PHENOTYPE_CALL_SCHEMA: dict[str, pl.DataType] = {
    "module": pl.String,
    "gene": pl.String,
    "status": pl.String,
    "phenotype": pl.String,
    "candidates": pl.List(_CANDIDATE_STRUCT),
    "sites": pl.List(_SITE_STRUCT),
    "phase_would_decide": pl.Boolean,
    "alleles_considered": pl.List(pl.String),
    "alleles_not_assessable": pl.List(pl.String),
    "unpaired_haplotypes": pl.List(pl.String),
    "drug_rows": pl.List(_DRUG_STRUCT),
    "compiler_warnings": pl.List(pl.String),
}


def _write_calls(calls: list[PhenotypeCall], output_path: Path) -> None:
    """One row per gene, with nested list/struct columns for candidates, sites and drug rows.

    An empty module (no genes) still writes a file with the right schema, so a reader never has to
    special-case "the parquet is missing" against "the module found nothing".
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = [c.model_dump() for c in calls]
    frame = pl.DataFrame(records, schema=PHENOTYPE_CALL_SCHEMA)
    frame.write_parquet(output_path)
