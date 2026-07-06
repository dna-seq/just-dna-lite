"""
ClinVar reader for gene-panel modules (cardio / cancer / pathogenic).

Generation-I ``just_cardio`` / ``just_cancer`` shipped only a gene list (``data/genes.txt``) and, at
runtime, flagged the ClinVar pathogenic/likely-pathogenic variants whose ``GENEINFO`` gene fell in
that list. There is no per-variant curated genotype/weight — the curation *is* the gene set plus the
"pathogenic" rule. This module reproduces that mechanism deterministically by scanning the local
ClinVar VCF (``clinvar.vcf.gz``, GRCh38) once and yielding the matching variants.

This is the app-level **reference implementation** for the gene-panel module type proposed in
``just-dna-format/docs/ROADMAP.md`` (item 7); the eventual home is the format/compiler so the authored
spec stays a tiny gene set rather than an enumerated table. Symbolic/complex alleles (non-ACGT) can't
be expressed as a two-allele genotype and are skipped and counted.
"""

import gzip
import os
import re
from pathlib import Path
from typing import Iterator, Optional

from pydantic import BaseModel, Field

# Default location of the hauled ClinVar VCF (see docs/V1_PARITY.md); override with $JUST_DNA_CLINVAR_VCF.
DEFAULT_CLINVAR_VCF = Path(
    os.environ.get("JUST_DNA_CLINVAR_VCF", "/data/just-dna-cache/clinvar/clinvar_GRCh38.vcf.gz")
)

# The ClinVar resource paper (Landrum et al., NAR 2018) — the honest citation for the data source.
# Verified via PubMed E-utilities. Per-submission citations are a future enhancement (ROADMAP item 7).
CLINVAR_RESOURCE_PMID = "29165669"

# CLNSIG tokens we treat as "pathogenic" for a gene panel. ClinVar joins multiple values with '|' and
# also uses '/' inside a single aggregate call (e.g. "Pathogenic/Likely_pathogenic").
_PATHOGENIC_SIG = frozenset({"pathogenic", "likely_pathogenic"})

_ACGT_RE = re.compile(r"^[ACGT]+$")
_VALID_CHROMS = frozenset([str(i) for i in range(1, 23)] + ["X", "Y", "MT"])

# Longest ref/alt allele we keep. SNVs and short indels (<= this) are the variants a user's
# small-variant VCF can actually carry and match; ClinVar's multi-kb exon/gene deletions are
# structural variants that would never match a genotype call and only bloat the artifact.
MAX_ALLELE_LEN = 50


class ClinVarVariant(BaseModel):
    """One ClinVar pathogenic variant matched to a gene panel."""

    chrom: str
    pos: int = Field(description="1-based VCF position")
    ref: str
    alt: str
    rsid: Optional[str] = None
    gene: str
    significance: str = Field(description="Raw CLNSIG value, e.g. Pathogenic/Likely_pathogenic")
    condition: Optional[str] = Field(default=None, description="CLNDN preferred disease name")


def _parse_info(info: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for field in info.split(";"):
        if "=" in field:
            key, _, value = field.partition("=")
            out[key] = value
    return out


def _genes(geneinfo: Optional[str]) -> list[str]:
    """GENEINFO is ``SYMBOL:id|SYMBOL2:id2`` — return the bare symbols."""
    if not geneinfo:
        return []
    return [pair.split(":", 1)[0] for pair in geneinfo.split("|") if pair]


def _is_pathogenic(clnsig: Optional[str]) -> bool:
    if not clnsig:
        return False
    tokens = {t.strip().lower() for chunk in clnsig.split("|") for t in chunk.split("/")}
    return bool(tokens & _PATHOGENIC_SIG)


def _norm_chrom(raw: str) -> Optional[str]:
    c = raw.removeprefix("chr")
    if c in ("M", "MT", "chrM"):
        c = "MT"
    return c if c in _VALID_CHROMS else None


def load_gene_panel_variants(
    genes: set[str], vcf_path: Path = DEFAULT_CLINVAR_VCF
) -> tuple[list[ClinVarVariant], dict[str, int]]:
    """Scan the ClinVar VCF for pathogenic/likely-pathogenic variants in ``genes``.

    Returns the matched variants plus a small ``stats`` dict (matched, skipped_non_acgt, total_path).
    Raises ``FileNotFoundError`` if the VCF is absent so the caller can skip with a clear warning.
    """
    if not vcf_path.exists():
        raise FileNotFoundError(f"ClinVar VCF not found at {vcf_path}")

    wanted = {g.strip().upper() for g in genes if g.strip()}
    matched: list[ClinVarVariant] = []
    skipped_non_acgt = 0
    skipped_too_long = 0
    total_path = 0

    for record in _iter_pathogenic_records(vcf_path):
        chrom_raw, pos_s, _vid, ref, alt_field, info = record
        info_d = _parse_info(info)
        if not _is_pathogenic(info_d.get("CLNSIG")):
            continue
        hit_genes = [g for g in _genes(info_d.get("GENEINFO")) if g.upper() in wanted]
        if not hit_genes:
            continue
        total_path += 1
        chrom = _norm_chrom(chrom_raw)
        if chrom is None:
            skipped_non_acgt += 1
            continue
        rs = info_d.get("RS")
        rsid = f"rs{rs.split('|')[0]}" if rs else None
        condition = (info_d.get("CLNDN") or "").replace("_", " ").strip() or None
        ref_u = ref.strip().upper()
        for alt in alt_field.split(","):
            alt_u = alt.strip().upper()
            if not (_ACGT_RE.match(ref_u) and _ACGT_RE.match(alt_u)) or ref_u == alt_u:
                skipped_non_acgt += 1
                continue
            if len(ref_u) > MAX_ALLELE_LEN or len(alt_u) > MAX_ALLELE_LEN:
                skipped_too_long += 1
                continue
            matched.append(ClinVarVariant(
                chrom=chrom, pos=int(pos_s), ref=ref_u, alt=alt_u, rsid=rsid,
                gene=hit_genes[0], significance=info_d.get("CLNSIG", ""), condition=condition,
            ))

    return matched, {
        "matched": len(matched),
        "skipped_non_acgt": skipped_non_acgt,
        "skipped_too_long": skipped_too_long,
        "pathogenic_in_panel": total_path,
    }


def _iter_pathogenic_records(vcf_path: Path) -> Iterator[tuple[str, str, str, str, str, str]]:
    """Yield (chrom, pos, id, ref, alt, info) for data lines mentioning a pathogenic classification.

    A cheap substring pre-filter (``Pathogenic`` appears in CLNSIG) skips the ~95% benign/VUS bulk
    before any splitting, so a full 190 MB scan stays fast.
    """
    with gzip.open(vcf_path, "rt") as handle:
        for line in handle:
            if line.startswith("#") or "athogenic" not in line:
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) >= 8:
                yield cols[0], cols[1], cols[2], cols[3], cols[4], cols[7]
