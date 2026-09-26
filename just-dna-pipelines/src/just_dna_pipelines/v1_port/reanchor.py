"""Re-anchor a port's indel coordinates to the ClinVar snapshot before compile.

The enricher resolves rsID -> coordinate from the Ensembl cache alone (every ``resolution.csv``
row is ``authority=ensembl``) and validates ref/alt against that same source, so an Ensembl-dump
insertion anchored one base off the caller/ClinVar convention ships self-consistent and wrong: the
position join in ``hf_logic`` then misses real carriers with no error. Measured on ``superhuman``
against four GRCh38 genomes — rs72613567 ``4:87310241 A>AA`` where callers and ClinVar carry
``4:87310240 T>TA``, and two more. Filed upstream as S117 (the Ensembl-anchor defect), S120 (the
missing coordinate-normalization convention) and S121 (single-authority resolution with no
cross-authority discordance check); RM267 assigns the build-side re-anchor to this pipeline. This is
that re-anchor.

For each indel row (``len(ref) != len(alt)``) whose rsID the ClinVar snapshot places differently,
adopt ClinVar's ``(start, ref, alt)`` — the dbSNP/caller authority for that rsID — in
``resolution.csv``, clear the Ensembl-anchored VRS id (a stable id on a wrong anchor is worse than
none: it dedups and propagates), and re-derive the authored genotype in ``variants.csv`` from
ClinVar's ref/alt by zygosity role. Every change is logged. An rsID ClinVar does not carry, or
carries as more than one indel record, is left as-is and reported — never guessed. ClinVar is
chrom-partitioned, so the lookup uses the row's own chromosome.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import polars as pl


def _is_indel(ref: Optional[str], alt: Optional[str]) -> bool:
    """An indel is a length change; a same-length substitution or an empty cell is not."""
    return bool(ref) and bool(alt) and len(ref) != len(alt)


def _clinvar_indel_record(
    clinvar_data: Path, chrom: str, rsid: str
) -> Optional[tuple[int, str, str]]:
    """The single ClinVar indel placement for ``rsid`` on ``chrom``, or ``None``.

    Returns ``None`` when ClinVar does not carry the rsID, carries it only as a substitution, or
    carries more than one distinct indel placement (ambiguous — the caller reports and skips it).
    """
    table = clinvar_data / f"clinvar-chr{chrom}.parquet"
    if not table.is_file():
        return None
    hits = (
        pl.scan_parquet(table)
        .filter(pl.col("rsid") == rsid)
        .select(["start", "ref", "alt"])
        .unique()
        .collect()
    )
    indels = [
        (int(r["start"]), str(r["ref"]), str(r["alt"]))
        for r in hits.to_dicts()
        if _is_indel(r.get("ref"), r.get("alt"))
    ]
    return indels[0] if len(indels) == 1 else None


def _remap_genotype(genotype: str, old_ref: str, old_alt: str, new_ref: str, new_alt: str) -> str:
    """Re-spell a genotype from the old ref/alt frame into the new one, by allele role.

    The authored genotype was built from the (Ensembl) ref/alt, so each of its alleles is exactly
    ``old_ref`` or ``old_alt``; map those to ``new_ref`` / ``new_alt`` and re-emit. Unphased is
    sorted (the grammar requires it); phased keeps homolog order and never sorts (sorting would fold
    ``A|G`` and ``G|A`` into one call). An allele that is neither old ref nor old alt is left as-is —
    it should not occur, and leaving it makes such a row visibly wrong rather than silently remapped.
    """
    phased = "|" in genotype
    sep = "|" if phased else "/"
    swap = {old_ref: new_ref, old_alt: new_alt}
    alleles = [swap.get(a, a) for a in genotype.split(sep)]
    if not phased:
        alleles = sorted(alleles)
    return sep.join(alleles)


def reanchor_indels_to_clinvar(out_dir: Path, clinvar_reference: Optional[Path]) -> list[str]:
    """Adopt ClinVar's spelling for indel rsIDs the Ensembl resolution placed differently.

    Rewrites ``resolution.csv`` (coordinate + authority, clears the VRS id) and ``variants.csv``
    (genotype) in place, and returns one report line per rsID acted on or deliberately skipped.
    A no-op (empty report) when there is no resolution table, no ClinVar snapshot, or no indel rows.
    """
    resolution_path = out_dir / "resolution.csv"
    variants_path = out_dir / "variants.csv"
    if not resolution_path.is_file() or clinvar_reference is None:
        return []
    clinvar_data = clinvar_reference / "data"
    if not clinvar_data.is_dir():
        return []

    resolution = pl.read_csv(resolution_path, infer_schema_length=10000)
    indel_mask = [
        _is_indel(r.get("ref"), r.get("alts")) for r in resolution.iter_rows(named=True)
    ]
    if not any(indel_mask):
        return []

    report: list[str] = []
    # rsID -> (new_start, new_ref, new_alt, old_ref, old_alt) for the rows we will rewrite.
    adopted: dict[str, tuple[int, str, str, str, str]] = {}
    for row, is_indel in zip(resolution.iter_rows(named=True), indel_mask):
        if not is_indel:
            continue
        rsid = row.get("rsid")
        chrom = row.get("chrom")
        old_ref, old_alt = str(row.get("ref")), str(row.get("alts"))
        if not rsid or chrom is None:
            continue
        # A multi-allelic authored alt (e.g. "A,AAA") cannot be re-anchored against one ClinVar
        # record without deciding which allele it names — a per-allele question this pass does not
        # answer. Leave it and say so, rather than drop an allele silently.
        if "," in old_alt:
            report.append(f"{rsid}: multi-allelic authored alt {old_alt!r}; left Ensembl-anchored")
            continue
        clin = _clinvar_indel_record(clinvar_data, str(chrom), str(rsid))
        if clin is None:
            report.append(f"{rsid}: ClinVar has no single indel record; left Ensembl-anchored")
            continue
        new_start, new_ref, new_alt = clin
        if (int(row.get("start")), old_ref, old_alt) == (new_start, new_ref, new_alt):
            continue  # already agrees — nothing to do
        adopted[str(rsid)] = (new_start, new_ref, new_alt, old_ref, old_alt)
        report.append(
            f"{rsid}: {chrom}:{row.get('start')} {old_ref}>{old_alt} -> "
            f"{chrom}:{new_start} {new_ref}>{new_alt} [adopted ClinVar placement]"
        )

    if not adopted:
        return report

    # Rewrite resolution.csv: coordinate, ref/alt, clear the (now-wrong) VRS id, restate authority.
    def _res_expr(col: str, kind: str) -> pl.Expr:
        e = pl.col("rsid")
        branches = pl.col(col)
        for rsid, (ns, nr, na, _or, _oa) in adopted.items():
            value = {"start": ns, "ref": nr, "alts": na, "vrs_id": None,
                     "source": "clinvar", "authority": "clinvar"}[kind]
            branches = pl.when(pl.col("rsid") == rsid).then(pl.lit(value)).otherwise(branches)
        return branches.alias(col)

    resolution = resolution.with_columns(
        _res_expr("start", "start"), _res_expr("ref", "ref"), _res_expr("alts", "alts"),
        _res_expr("vrs_id", "vrs_id"), _res_expr("source", "source"),
        _res_expr("authority", "authority"),
    )
    resolution.write_csv(resolution_path)

    # Rewrite variants.csv genotype for every row of an adopted rsID.
    if variants_path.is_file():
        variants = pl.read_csv(variants_path, infer_schema_length=10000)
        new_gt: list[str] = []
        for r in variants.iter_rows(named=True):
            gt = r.get("genotype")
            rsid = str(r.get("rsid"))
            if rsid in adopted and gt:
                _ns, nr, na, orf, oal = adopted[rsid]
                new_gt.append(_remap_genotype(str(gt), orf, oal, nr, na))
            else:
                new_gt.append(gt)
        variants = variants.with_columns(pl.Series("genotype", new_gt))
        variants.write_csv(variants_path)

    report.append(f"re-anchored {len(adopted)} indel rsID(s) to ClinVar and re-derived their genotypes")
    return report
