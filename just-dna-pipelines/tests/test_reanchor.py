"""The indel re-anchor pass adopts ClinVar's placement for rsIDs the Ensembl cache mis-anchored.

Root cause and provenance: S117/S120/S121 in just-dna-format's CONSUMER_SUGGESTIONS, RM267. The
enricher resolves an insertion class one base off the caller/ClinVar convention and validates it
against Ensembl itself, so it ships self-consistent and unmatchable; `reanchor_indels_to_clinvar`
adopts ClinVar's spelling (the dbSNP/caller authority for the rsID) before compile. Hermetic: builds
a tiny chrom-partitioned ClinVar snapshot and a spec directory in tmp, no network, no real cache.
"""

from pathlib import Path

import polars as pl

from just_dna_pipelines.v1_port.reanchor import _remap_genotype, reanchor_indels_to_clinvar


def _clinvar_snapshot(root: Path, rows: list[dict]) -> Path:
    """A ClinVar reference dir (`<root>/data/clinvar-chr{N}.parquet`) from per-chrom rows."""
    data = root / "data"
    data.mkdir(parents=True)
    for chrom in {r["chrom"] for r in rows}:
        pl.DataFrame([r for r in rows if r["chrom"] == chrom]).write_parquet(
            data / f"clinvar-chr{chrom}.parquet"
        )
    return root


def _spec_dir(tmp: Path, resolution: list[dict], variants: list[dict]) -> Path:
    out = tmp / "mod"
    out.mkdir()
    pl.DataFrame(resolution).write_csv(out / "resolution.csv")
    pl.DataFrame(variants).write_csv(out / "variants.csv")
    return out


def test_remap_genotype_moves_alleles_by_role_and_sorts_unphased() -> None:
    # het (ref+alt) and hom-alt (alt+alt) re-spelled into the new frame; unphased stays sorted.
    assert _remap_genotype("A/AA", "A", "AA", "T", "TA") == "T/TA"
    assert _remap_genotype("AA/AA", "A", "AA", "T", "TA") == "TA/TA"
    # a deletion (ref longer than alt); the het sorts by string.
    assert _remap_genotype("A/A", "AAACA", "A", "GAAAC", "G") == "G/G"


def test_remap_genotype_keeps_phase_and_never_sorts_phased() -> None:
    assert _remap_genotype("AA|A", "A", "AA", "T", "TA") == "TA|T"  # order preserved, not sorted


def test_adopts_clinvar_placement_and_rederives_genotype(tmp_path: Path) -> None:
    clinvar = _clinvar_snapshot(
        tmp_path / "cv",
        [{"chrom": "4", "start": 87310240, "ref": "T", "alt": "TA", "rsid": "rs72613567"}],
    )
    out = _spec_dir(
        tmp_path,
        resolution=[{
            "variant_key": "rs72613567", "rsid": "rs72613567", "chrom": 4, "start": 87310241,
            "ref": "A", "alts": "AA", "vrs_id": "ga4gh:VA.stale", "source": "cache",
            "authority": "ensembl",
        }],
        variants=[
            {"rsid": "rs72613567", "genotype": "A/AA"},
            {"rsid": "rs72613567", "genotype": "AA/AA"},
        ],
    )
    report = reanchor_indels_to_clinvar(out, clinvar)

    res = pl.read_csv(out / "resolution.csv")
    row = res.row(0, named=True)
    assert (row["start"], row["ref"], row["alts"]) == (87310240, "T", "TA")  # ClinVar's anchor
    assert row["authority"] == "clinvar"
    assert row["vrs_id"] in (None, "")  # the Ensembl-anchored id is cleared, not kept
    assert sorted(pl.read_csv(out / "variants.csv")["genotype"].to_list()) == ["T/TA", "TA/TA"]
    assert any("adopted ClinVar placement" in line for line in report)


def test_leaves_a_multiallelic_authored_row_alone(tmp_path: Path) -> None:
    # A comma-separated authored alt cannot be re-anchored against one ClinVar record — skip + report.
    clinvar = _clinvar_snapshot(
        tmp_path / "cv",
        [{"chrom": "1", "start": 100, "ref": "C", "alt": "CA", "rsid": "rsMULTI"}],
    )
    out = _spec_dir(
        tmp_path,
        resolution=[{
            "variant_key": "rsMULTI", "rsid": "rsMULTI", "chrom": 1, "start": 101, "ref": "A",
            "alts": "AA,AAA", "vrs_id": "x", "source": "cache", "authority": "ensembl",
        }],
        variants=[{"rsid": "rsMULTI", "genotype": "A/AA"}],
    )
    report = reanchor_indels_to_clinvar(out, clinvar)
    res = pl.read_csv(out / "resolution.csv")
    assert res.row(0, named=True)["start"] == 101  # untouched
    assert res.row(0, named=True)["authority"] == "ensembl"
    assert any("multi-allelic" in line for line in report)


def test_leaves_a_row_clinvar_does_not_carry_alone(tmp_path: Path) -> None:
    clinvar = _clinvar_snapshot(
        tmp_path / "cv",
        [{"chrom": "9", "start": 1, "ref": "A", "alt": "AT", "rsid": "rsOTHER"}],
    )
    out = _spec_dir(
        tmp_path,
        resolution=[{
            "variant_key": "rsABSENT", "rsid": "rsABSENT", "chrom": 9, "start": 500, "ref": "G",
            "alts": "GT", "vrs_id": "x", "source": "cache", "authority": "ensembl",
        }],
        variants=[{"rsid": "rsABSENT", "genotype": "G/GT"}],
    )
    report = reanchor_indels_to_clinvar(out, clinvar)
    assert pl.read_csv(out / "resolution.csv").row(0, named=True)["start"] == 500  # untouched
    assert any("no single indel record" in line for line in report)


def test_a_substitution_is_not_touched(tmp_path: Path) -> None:
    # Same-length ref/alt is not an indel; even if ClinVar differs, the pass leaves SNVs alone.
    clinvar = _clinvar_snapshot(
        tmp_path / "cv",
        [{"chrom": "1", "start": 200, "ref": "C", "alt": "T", "rsid": "rsSNV"}],
    )
    out = _spec_dir(
        tmp_path,
        resolution=[{
            "variant_key": "rsSNV", "rsid": "rsSNV", "chrom": 1, "start": 201, "ref": "A",
            "alts": "G", "vrs_id": "x", "source": "cache", "authority": "ensembl",
        }],
        variants=[{"rsid": "rsSNV", "genotype": "A/G"}],
    )
    report = reanchor_indels_to_clinvar(out, clinvar)
    assert pl.read_csv(out / "resolution.csv").row(0, named=True)["start"] == 201  # untouched
    assert report == []
