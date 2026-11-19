"""
Genotypes of VCFs split one row per ALT (`bcftools norm -m-`).

A site where the sample carries two different ALTs and no reference (`1/2`) splits into `1/0` and
`0/1`, and in each split row the `0` stands for the other ALT, not REF. Read row by row, both rows
claim a reference copy the sample does not have. `resolve_split_multiallelic_genotypes` restores
the site's genotype onto every row, written in that row's own REF frame.

Ground truth is the same public genome read unsplit: the split fixture is built at test time from
`antku_small.vcf` (9 multi-allelic records among 792), following bcftools' convention (one row per
ALT at the same POS, GT index k → 1 and every other ALT → 0, the common suffix trimmed).
"""

from pathlib import Path

import polars as pl
import pytest

from just_dna_pipelines.io import (
    SPANNING_DELETION_ALLELE,
    read_vcf_file,
    resolve_split_multiallelic_genotypes,
)

SOURCE_VCF = Path(__file__).parent.parent.parent / "data" / "input" / "tests" / "antku_small.vcf"
KEY = ["chrom", "start", "ref", "alt"]


def _trim_suffix(ref: str, alt: str) -> tuple[str, str]:
    while len(ref) > 1 and len(alt) > 1 and ref[-1] == alt[-1]:
        ref, alt = ref[:-1], alt[:-1]
    return ref, alt


def _split_gt(gt: str, k: int) -> str:
    out = []
    for ch in gt:
        if ch.isdigit():
            out.append("1" if ch == str(k) else "0")
        else:
            out.append(ch)
    return "".join(out)


def _write_split_and_unsplit(tmp_path: Path) -> tuple[Path, Path]:
    """Both files keep GT only, so the two differ in nothing but the split."""
    header: list[str] = []
    unsplit: list[str] = []
    split: list[str] = []
    for line in SOURCE_VCF.read_text(encoding="utf-8").splitlines():
        if line.startswith("##FORMAT") and not line.startswith("##FORMAT=<ID=GT,"):
            continue
        if line.startswith("#"):
            header.append(line)
            continue
        cols = line.split("\t")
        gt = cols[9].split(":")[0]
        base = cols[:7] + ["."]
        unsplit.append("\t".join(base + ["GT", gt]))
        alts = cols[4].split(",")
        for k, alt in enumerate(alts, start=1):
            ref, trimmed = _trim_suffix(cols[3], alt) if len(alts) > 1 else (cols[3], alt)
            row = base.copy()
            row[3], row[4] = ref, trimmed
            split.append("\t".join(row + ["GT", _split_gt(gt, k) if len(alts) > 1 else gt]))
    paths = []
    for name, body in (("unsplit.vcf", unsplit), ("split.vcf", split)):
        path = tmp_path / name
        path.write_text("\n".join(header + body) + "\n", encoding="utf-8")
        paths.append(path)
    return paths[0], paths[1]


def _in_frame(allele: str, suffix: str) -> str:
    """The inverse of re-padding: an allele of the full site written in a shorter REF's frame."""
    if allele.endswith(suffix) and len(allele) > len(suffix):
        return allele[: len(allele) - len(suffix)]
    return SPANNING_DELETION_ALLELE


@pytest.fixture
def split_pair(tmp_path: Path) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    unsplit_path, split_path = _write_split_and_unsplit(tmp_path)
    unsplit = read_vcf_file(unsplit_path, save_parquet=None, with_formats=True).select(KEY + ["GT", "genotype"]).collect()
    raw = read_vcf_file(split_path, save_parquet=None, with_formats=True)
    resolved, _ = resolve_split_multiallelic_genotypes(raw)
    return unsplit, raw.select(KEY + ["GT", "genotype"]).collect(), resolved.select(
        KEY + ["GT", "genotype"]
    ).collect()


def test_fixture_has_split_sites_that_read_wrong_before_the_fix(split_pair) -> None:
    unsplit, raw, _ = split_pair
    multi = unsplit.filter(pl.col("alt").str.contains(r"\|"))
    assert multi.height > 0
    sites = multi.select("chrom", "start")
    raw_at_sites = raw.join(sites, on=["chrom", "start"], how="semi")
    # Every split row reads as carrying its own REF unless it is the 1/1 one: the defect itself.
    wrong = raw_at_sites.filter(pl.col("genotype").list.contains(pl.col("ref")))
    assert wrong.height > 0


def test_every_split_row_carries_the_unsplit_site_genotype(split_pair) -> None:
    unsplit, raw, resolved = split_pair
    truth = {
        (r["chrom"], r["start"]): (r["ref"], r["genotype"])
        for r in unsplit.filter(pl.col("alt").str.contains(r"\|")).iter_rows(named=True)
    }
    checked = 0
    for row in resolved.iter_rows(named=True):
        site = truth.get((row["chrom"], row["start"]))
        if site is None:
            continue
        site_ref, site_genotype = site
        assert site_ref.startswith(row["ref"])
        suffix = site_ref[len(row["ref"]):]
        expected = sorted(_in_frame(a, suffix) for a in site_genotype)
        assert row["genotype"] == expected, row
        # Round trip: every allele but a spanning one re-pads to the site's own allele.
        repadded = sorted(a + suffix for a in row["genotype"] if a != SPANNING_DELETION_ALLELE)
        assert set(repadded) <= set(site_genotype)
        checked += 1
    assert checked == raw.join(
        pl.DataFrame({"chrom": [c for c, _ in truth], "start": [s for _, s in truth]}).cast(
            {"chrom": raw.schema["chrom"], "start": raw.schema["start"]}
        ),
        on=["chrom", "start"],
        how="semi",
    ).height


def test_rows_outside_split_sites_are_untouched(split_pair) -> None:
    _, raw, resolved = split_pair
    assert resolved.height == raw.height
    multi_positions = raw.group_by("chrom", "start").len().filter(pl.col("len") > 1)
    outside_raw = raw.join(multi_positions, on=["chrom", "start"], how="anti").sort(KEY)
    outside_resolved = resolved.join(multi_positions, on=["chrom", "start"], how="anti").sort(KEY)
    assert outside_resolved.equals(outside_raw)


def test_an_unsplit_file_is_left_alone(split_pair) -> None:
    unsplit, _, _ = split_pair
    resolved, stats = resolve_split_multiallelic_genotypes(unsplit.lazy())
    assert resolved.collect().sort(KEY).equals(unsplit.sort(KEY))
    assert stats.rows_resolved == 0


def _frame(rows: list[tuple[str, int, str, str, str, list[str]]]) -> pl.LazyFrame:
    return pl.DataFrame(
        rows,
        schema={"chrom": pl.String, "start": pl.UInt32, "ref": pl.String, "alt": pl.String,
                "GT": pl.String, "genotype": pl.List(pl.String)},
        orient="row",
    ).lazy()


@pytest.mark.parametrize(
    ("rows", "reason"),
    [
        # Two independent heterozygous records at one position: both claim the second slot.
        ([("1", 10, "A", "G", "0/1", ["A", "G"]), ("1", 10, "A", "AT", "0/1", ["A", "AT"])],
         "slot_claimed_twice"),
        # REFs that are not prefixes of one another describe different spans.
        ([("1", 10, "AT", "A", "1/0", ["A", "AT"]), ("1", 10, "AG", "A", "0/1", ["A", "AG"])],
         "ref_not_prefix"),
        # A missing call names no allele to restore.
        ([("1", 10, "A", "G", "./1", ["G"]), ("1", 10, "A", "T", "1/0", ["A", "T"])], "missing_call"),
        # An already multi-allelic row is not a split.
        ([("1", 10, "A", "G|T", "1/2", ["G", "T"]), ("1", 10, "A", "C", "0/1", ["A", "C"])],
         "not_split"),
        # One ALT written twice would make the join back ambiguous.
        ([("1", 10, "A", "G", "1/0", ["A", "G"]), ("1", 10, "A", "G", "0/1", ["A", "G"])],
         "duplicate_allele"),
    ],
)
def test_groups_that_are_not_a_split_keep_their_genotypes(rows, reason) -> None:
    frame = _frame(rows)
    resolved, stats = resolve_split_multiallelic_genotypes(frame)
    assert resolved.collect().sort(KEY).equals(frame.collect().sort(KEY))
    assert stats.groups_skipped == {reason: 1}


def test_a_hom_alt_split_drops_the_false_hom_ref_row() -> None:
    # Unsplit `A>G,T 1/1`: the T row reads 0/0, two reference copies the sample does not have.
    resolved, stats = resolve_split_multiallelic_genotypes(
        _frame([("1", 10, "A", "G", "1/1", ["G", "G"]), ("1", 10, "A", "T", "0/0", ["A", "A"])])
    )
    assert resolved.collect()["genotype"].to_list() == [["G", "G"], ["G", "G"]]
    assert stats.rows_resolved == 2


def test_a_phased_split_and_a_deletion_beyond_the_row_frame() -> None:
    # Unsplit `AT>A,ATT 1|2`, split and trimmed to `AT>A 1|0` and `A>AT 0|1`. In the A>AT row's
    # one-base frame the deletion of T cannot be written, so it reads as a spanning deletion.
    resolved, _ = resolve_split_multiallelic_genotypes(
        _frame([("1", 10, "AT", "A", "1|0", ["A", "AT"]), ("1", 10, "A", "AT", "0|1", ["A", "AT"])])
    )
    assert resolved.collect()["genotype"].to_list() == [["A", "ATT"], [SPANNING_DELETION_ALLELE, "AT"]]
