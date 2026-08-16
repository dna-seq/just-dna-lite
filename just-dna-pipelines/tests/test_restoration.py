"""Tests for reference-genotype restoration.

The real case these were written against: our `lactose_tolerance` module authors a `G/G` row for
rs4988235 ("adult-type hypolactasia"), Anton Kulaga's variant-only WGS callset carries no record at
2:135851076, and the report therefore said "no variants found" instead of giving the reader the most
common lactose result there is.

Each test below pins one rule that keeps restoration from becoming a guess.
"""

from pathlib import Path

import polars as pl
import pytest
from just_prs.prs import GenotypeInputMode

from just_dna_pipelines.runtime import load_env

# Locally registered modules live under `JUST_DNA_PIPELINES_OUTPUT_DIR`, which is set in `.env`, and
# discovery runs at import of `hf_modules`. Loading the environment here rather than inside the test
# is the same reason `tests/test_modules_0_5.py` does it at import: the default is computed before
# anything gets a chance to call `load_env` later.
load_env()

from just_dna_pipelines.annotation.restoration import (
    EVIDENCE_COLUMN,
    EVIDENCE_RESTORED,
    FLANK_COLUMN,
    MIN_WGS_BREADTH,
    MIN_WGS_SITES,
    CallsetScope,
    RestorationContext,
    build_restoration_context,
    detect_callset_scope,
    hom_ref_rows,
    infer_genotype_input_mode,
    restored_rows,
)


def _wgs_context(vcf: pl.LazyFrame, max_flank_bp: int = 10_000) -> RestorationContext:
    """A context over a toy callset, with the whole-genome verdict asserted rather than measured.

    The per-site rules below are about one site each, so their fixtures hold a handful of calls —
    which `detect_callset_scope` correctly classifies as targeted and refuses to restore into. That
    refusal is the subject of `TestCallsetScope`; forcing the verdict here keeps each test to one
    claim, instead of every fixture having to fake a million rows to reach the code under test.
    """
    from just_dna_pipelines.annotation.restoration import build_restoration_context as _build

    base = _build(vcf, max_flank_bp)
    return RestorationContext(
        called_sites=base.called_sites,
        mode=base.mode,
        scope=CallsetScope.WGS,
        scope_reason="forced for this unit test",
        max_flank_bp=max_flank_bp,
    )


def _sites(chrom: str, positions) -> pl.DataFrame:
    return pl.DataFrame(
        {"chrom": [chrom] * len(positions), "start": positions},
        schema={"chrom": pl.String, "start": pl.UInt32},
    ).sort(["chrom", "start"])


def _vcf(rows: list[dict]) -> pl.LazyFrame:
    """A minimal prepared-VCF frame with the columns the engine actually reads."""
    return pl.DataFrame(
        rows,
        schema={
            "chrom": pl.String,
            "start": pl.UInt32,
            # `rsid` is always present on a prepared VCF (the reader renames `id` to it), and it
            # matters here: it collides with the lead table's own `rsid`, which is what pushes the
            # module's identifier under the join suffix. A fixture without it silently tests a
            # frame shape the pipeline never produces.
            "rsid": pl.String,
            "ref": pl.String,
            "alt": pl.String,
            "filter": pl.String,
            "GT": pl.String,
            "genotype": pl.List(pl.String),
        },
    ).lazy()


def _lead(rows: list[dict]) -> pl.LazyFrame:
    return pl.DataFrame(
        rows,
        schema={
            "rsid": pl.String,
            "chrom": pl.String,
            "start": pl.UInt32,
            "ref": pl.String,
            "genotype": pl.List(pl.String),
            "module": pl.String,
            "weight": pl.Float64,
            "state": pl.String,
        },
    ).lazy()


class TestGenotypeInputMode:
    """Which callsets may be restored into, and why the parquet is what gets classified."""

    def test_a_plain_variant_only_callset_is_variant_only(self):
        lf = _vcf([{"chrom": "1", "start": 100, "rsid": None, "ref": "A", "alt": "G",
                    "filter": "PASS", "GT": "0/1", "genotype": ["A", "G"]}])
        assert infer_genotype_input_mode(lf) == GenotypeInputMode.VARIANT_ONLY

    @pytest.mark.parametrize(
        "marker",
        [
            {"alt": "<NON_REF>", "filter": "PASS"},
            {"alt": "G", "filter": "RefCall"},
        ],
        ids=["non_ref_allele", "refcall_filter"],
    )
    def test_a_reference_block_marker_makes_it_all_sites(self, marker):
        """Either marker a gVCF leaves behind is enough — one is the allele, one is the filter."""
        lf = _vcf([{"chrom": "1", "start": 100, "rsid": None, "ref": "A",
                    "GT": "0/0", "genotype": ["A", "A"], **marker}])
        assert infer_genotype_input_mode(lf) == GenotypeInputMode.ALL_SITES

    def test_an_all_sites_callset_disables_restoration(self):
        """It already carries the reference genotype, with the caller's own depth behind it.

        Restoring on top would invent a second row for a locus the caller already answered.
        """
        # Scope is WGS here on purpose: the mode gate alone must be enough to refuse.
        ctx = RestorationContext(
            called_sites=_sites("1", [100]),
            mode=GenotypeInputMode.ALL_SITES,
            scope=CallsetScope.WGS,
            scope_reason="test",
            max_flank_bp=10_000,
        )
        assert ctx.enabled is False
        rows, stats = restored_rows(_vcf([]), _lead([]), "m", ctx)
        assert rows is None
        assert stats["restored"] == 0


class TestCallsetScope:
    """The gate `GenotypeInputMode` cannot supply: does absence mean anything on this callset?"""

    FLANK = 10_000

    def test_a_dense_whole_genome_callset_is_wgs(self):
        """1.2M sites 300 bp apart — the spacing all four real samples in this repo show (p50 ~295)."""
        scope, reason = detect_callset_scope(
            _sites("1", list(range(0, 1_200_000 * 300, 300))), self.FLANK
        )
        assert scope == CallsetScope.WGS
        assert "of the span within" in reason

    def test_too_few_sites_is_targeted(self):
        """An exome carries ~50–100k sites; a panel far fewer. Absence there is uninformative."""
        scope, reason = detect_callset_scope(
            _sites("1", list(range(0, 80_000 * 300, 300))), self.FLANK
        )
        assert scope == CallsetScope.TARGETED
        assert "below the" in reason and f"{MIN_WGS_SITES:,}" in reason

    def test_enough_sites_but_clustered_is_targeted(self):
        """The shape the site count waves through, the flank test waves through, and p90 waved through.

        Exonic variants cluster densely, so a module site in the intron beside a captured exon has a
        neighbour within kilobases while never having been captured itself. 20 calls 50 bp apart
        every 100 kb puts **95% of gaps at 50 bp**, so a 90th-percentile gap check calls this dense —
        which is why breadth replaced it: 79% of the span is nowhere near a call.
        """
        rows: list[tuple[str, int]] = []
        for contig in range(1, 23):
            for cluster in range(2_400):
                base = cluster * 100_000
                rows += [(str(contig), base + j * 50) for j in range(20)]
        frame = pl.DataFrame(
            rows, schema={"chrom": pl.String, "start": pl.UInt32}, orient="row"
        ).sort(["chrom", "start"])
        assert frame.height > MIN_WGS_SITES  # the volume gate alone would pass this

        scope, reason = detect_callset_scope(frame, self.FLANK)
        assert scope == CallsetScope.TARGETED
        assert "clustered" in reason

    def test_scaffolds_do_not_skew_the_density_measurement(self):
        """A decoy contig with three calls megabases apart must not make a genome look targeted."""
        wgs = _sites("1", list(range(0, 1_200_000 * 300, 300)))
        noisy = pl.concat([wgs, _sites("KI270302.1", [1, 5_000_000, 9_000_000])]).sort(
            ["chrom", "start"]
        )
        assert detect_callset_scope(noisy, self.FLANK)[0] == CallsetScope.WGS

    @pytest.mark.skipif(
        not Path("/data/just-dna-lite/output/users/anonymous").exists(),
        reason="no local samples to measure against",
    )
    def test_every_real_sample_on_this_machine_classifies_as_wgs(self):
        """Ground truth for the threshold: breadth measured 0.942–0.950 across all four.

        The point is the margin, not the verdict — 0.75 is not a value any of these sits near.
        """
        from just_dna_pipelines.annotation.restoration import _coverage_breadth, MIN_WGS_BREADTH

        seen = 0
        for sample in sorted(Path("/data/just-dna-lite/output/users/anonymous").iterdir()):
            parquet = sample / "user_vcf_normalized.parquet"
            if not parquet.exists():
                continue
            seen += 1
            sites = (
                pl.scan_parquet(parquet).select("chrom", "start").unique()
                .sort(["chrom", "start"]).collect()
            )
            scope, _ = detect_callset_scope(sites, self.FLANK)
            assert scope == CallsetScope.WGS, sample.name
            primary = sites.filter(pl.col("chrom").str.contains(r"^(?:\d+|X|Y|MT)$"))
            assert _coverage_breadth(primary, self.FLANK) > MIN_WGS_BREADTH + 0.15, sample.name
        if not seen:
            pytest.skip("no normalized samples present")

    def test_a_targeted_callset_disables_restoration_even_when_variant_only(self):
        ctx = RestorationContext(
            called_sites=_sites("1", [100]),
            mode=GenotypeInputMode.VARIANT_ONLY,
            scope=CallsetScope.TARGETED,
            scope_reason="test",
            max_flank_bp=10_000,
        )
        assert ctx.enabled is False
        assert restored_rows(_vcf([]), _lead([]), "m", ctx) == (None, {
            "hom_ref_rows": 0, "absent": 0, "restored": 0
        })


class TestHomRefRowSelection:
    """Which authored rows are candidates at all."""

    def test_only_rows_whose_genotype_is_the_reference_genotype(self):
        lead = _lead([
            {"rsid": "rs1", "chrom": "1", "start": 10, "ref": "G", "genotype": ["G", "G"],
             "module": "m", "weight": 0.0, "state": "neutral"},
            {"rsid": "rs1", "chrom": "1", "start": 10, "ref": "G", "genotype": ["A", "G"],
             "module": "m", "weight": 1.0, "state": "protective"},
            {"rsid": "rs1", "chrom": "1", "start": 10, "ref": "G", "genotype": ["A", "A"],
             "module": "m", "weight": 1.2, "state": "protective"},
        ])
        got = hom_ref_rows(lead).collect()
        assert got.height == 1
        assert got["genotype"].to_list() == [["G", "G"]]

    def test_a_haploid_reference_genotype_counts(self):
        """chrY and chrM are called haploid, so a one-allele genotype equal to ref is hom-ref too."""
        lead = _lead([{"rsid": "rs1", "chrom": "MT", "start": 10, "ref": "T", "genotype": ["T"],
                       "module": "m", "weight": 0.0, "state": "neutral"}])
        assert hom_ref_rows(lead).collect().height == 1

    def test_a_multi_base_reference_allele_is_compared_whole(self):
        """`CTG/CTG` against `ref=CTG` is hom-ref; character-wise comparison would miss it."""
        lead = _lead([{"rsid": "rs1", "chrom": "1", "start": 10, "ref": "CTG",
                       "genotype": ["CTG", "CTG"], "module": "m", "weight": 0.0, "state": "neutral"}])
        assert hom_ref_rows(lead).collect().height == 1

    def test_a_locus_the_module_spells_with_two_reference_alleles_is_withheld(self):
        """The `rs1114167546` case, and the reason this guard exists.

        ClinVar holds two real records at 5:112767222 under one rsID — the duplication ``T -> TA``
        (Variation 428095) and the deletion ``TA -> T`` (Variation 2583495), both pathogenic. Our
        panel authors that faithfully, rsid-only: ``T/TA`` and ``TA/TA``, both meaning the
        duplication. The compiler then pairs each authored genotype with each resolved locus
        (``resolution.csv`` carries both under one ``variant_key``), so ``TA/TA`` also lands against
        ``ref=TA`` — where it reads as hom-REF instead of the hom-alt the author wrote. Taking that
        literally restored 2,579 rows into one genome's `pathogenic` section, every one telling the
        reader they carry a pathogenic variant they do not have.

        "Which allele is the reference" is the whole question restoration answers, so a locus that
        answers it two ways answers it not at all.
        """
        lead = _lead([
            {"rsid": "rs1114167546", "chrom": "5", "start": 112767222, "ref": "T",
             "genotype": ["TA", "TA"], "module": "cancer", "weight": None, "state": "risk"},
            {"rsid": "rs1114167546", "chrom": "5", "start": 112767222, "ref": "TA",
             "genotype": ["TA", "TA"], "module": "cancer", "weight": None, "state": "risk"},
        ])
        assert hom_ref_rows(lead).collect().height == 0

    def test_an_unambiguous_locus_beside_an_ambiguous_one_still_restores(self):
        """The guard is per locus, not per module — one bad site must not disarm the rest."""
        lead = _lead([
            {"rsid": "rs1", "chrom": "5", "start": 100, "ref": "T",
             "genotype": ["TA", "TA"], "module": "m", "weight": None, "state": "risk"},
            {"rsid": "rs1", "chrom": "5", "start": 100, "ref": "TA",
             "genotype": ["TA", "TA"], "module": "m", "weight": None, "state": "risk"},
            {"rsid": "rs2", "chrom": "5", "start": 900, "ref": "G",
             "genotype": ["G", "G"], "module": "m", "weight": 0.0, "state": "neutral"},
        ])
        got = hom_ref_rows(lead).collect()
        assert got["rsid"].to_list() == ["rs2"]

    def test_a_lead_table_without_coordinates_is_excluded_by_schema(self):
        """The `pharm_variants` case: no `ref`, no coordinates, so the question cannot be asked.

        Excluded by the columns the table has rather than by its family name, so format 0.6's RM43
        fill switches it on with no code change here.
        """
        lead = pl.DataFrame(
            {"rsid": ["rs1"], "genotype": [["C", "C"]], "drug": ["warfarin"]}
        ).lazy()
        assert hom_ref_rows(lead) is None


class TestRestorationEvidence:
    """The rules that stop an absence from being read as a result it has not earned."""

    def test_a_site_the_caller_emitted_is_never_restored(self):
        """It was observed. Whatever the caller said there is the answer, including a contradiction."""
        vcf = _vcf([{"chrom": "1", "start": 500, "rsid": None, "ref": "G", "alt": "A",
                     "filter": "PASS", "GT": "0/1", "genotype": ["A", "G"]}])
        lead = _lead([{"rsid": "rs1", "chrom": "1", "start": 500, "ref": "G",
                       "genotype": ["G", "G"], "module": "m", "weight": 0.0, "state": "neutral"}])
        ctx = _wgs_context(vcf)
        rows, stats = restored_rows(vcf, lead, "m", ctx)
        assert stats["hom_ref_rows"] == 1
        assert stats["absent"] == 0
        assert rows is None

    def test_a_site_with_no_nearby_call_is_left_unrestored(self):
        """Absence in a region the callset never reached is absence of evidence, not hom-ref."""
        vcf = _vcf([{"chrom": "1", "start": 500, "rsid": None, "ref": "G", "alt": "A",
                     "filter": "PASS", "GT": "0/1", "genotype": ["A", "G"]}])
        lead = _lead([{"rsid": "rs1", "chrom": "1", "start": 9_000_000, "ref": "T",
                       "genotype": ["T", "T"], "module": "m", "weight": 0.0, "state": "neutral"}])
        ctx = _wgs_context(vcf)
        rows, stats = restored_rows(vcf, lead, "m", ctx)
        assert stats["absent"] == 1
        assert stats["restored"] == 0
        assert rows is None

    def test_a_site_on_a_contig_the_callset_never_touched_is_left_unrestored(self):
        """The nearest-call join yields nothing at all, which must drop the row, not pass it."""
        vcf = _vcf([{"chrom": "1", "start": 500, "rsid": None, "ref": "G", "alt": "A",
                     "filter": "PASS", "GT": "0/1", "genotype": ["A", "G"]}])
        lead = _lead([{"rsid": "rs1", "chrom": "22", "start": 500, "ref": "T",
                       "genotype": ["T", "T"], "module": "m", "weight": 0.0, "state": "neutral"}])
        ctx = _wgs_context(vcf)
        rows, stats = restored_rows(vcf, lead, "m", ctx)
        assert stats["restored"] == 0
        assert rows is None

    def test_a_nearby_absent_site_is_restored_and_labelled_with_its_distance(self):
        vcf = _vcf([{"chrom": "2", "start": 135850896, "rsid": None, "ref": "C", "alt": "A",
                     "filter": "PASS", "GT": "1/1", "genotype": ["A", "A"]}])
        lead = _lead([{"rsid": "rs4988235", "chrom": "2", "start": 135851076, "ref": "G",
                       "genotype": ["G", "G"], "module": "lactose", "weight": 0.0,
                       "state": "neutral"}])
        ctx = _wgs_context(vcf)
        rows, stats = restored_rows(vcf, lead, "lactose", ctx)
        assert stats == {"hom_ref_rows": 1, "absent": 1, "restored": 1}

        got = rows.collect()
        assert got.height == 1
        assert got[EVIDENCE_COLUMN][0] == EVIDENCE_RESTORED
        # 135851076 - 135850896; the real flank distance for this site in Anton Kulaga's genome.
        assert got[FLANK_COLUMN][0] == 180
        # The restored row carries the module's own reference genotype, at the module's coordinate.
        assert got["genotype"][0].to_list() == ["G", "G"]
        assert got["ref"][0] == "G"
        # Nothing the caller would have supplied is invented.
        assert got["GT"][0] is None
        assert got["filter"][0] is None

    def test_the_restored_frame_carries_the_vcf_schema_so_it_can_be_concatenated(self):
        """Built from an empty slice of the real frame, so a new VCF column cannot desynchronise it."""
        vcf = _vcf([{"chrom": "2", "start": 100, "rsid": None, "ref": "C", "alt": "A",
                     "filter": "PASS", "GT": "1/1", "genotype": ["A", "A"]}])
        lead = _lead([{"rsid": "rs1", "chrom": "2", "start": 200, "ref": "G",
                       "genotype": ["G", "G"], "module": "m", "weight": 0.0, "state": "neutral"}])
        ctx = _wgs_context(vcf)
        rows, _ = restored_rows(vcf, lead, "m", ctx)
        got = rows.collect()
        for column in vcf.collect_schema().names():
            assert column in got.columns
        # The module's own rsid is held under the join suffix, exactly as the position join leaves it,
        # so `report_logic.load_annotated_weights` finds it in the same place for both row kinds.
        assert "rsid_m" in got.columns


def _local_lactose_module():
    """Discover the locally registered lactose module without touching global state.

    Not read from `MODULE_INFOS`: that dict is built at import of `hf_modules`, and under the full
    suite some earlier test has already imported it — before this file's `load_env()` runs — so the
    locally registered source was not on the path yet and the module is missing from the global.
    Running discovery here against the one source we need is both order-independent and free of the
    cross-test mutation that `refresh_module_registry()` would cause.
    """
    from just_dna_pipelines.annotation.hf_modules import discover_hf_modules
    from just_dna_pipelines.annotation.resources import get_user_output_dir

    registered = get_user_output_dir() / "registered_modules"
    if not (registered / "eric_mods__lactose_tolerance").exists():
        return None
    return discover_hf_modules([str(registered)]).get("eric_mods__lactose_tolerance")


def test_the_real_lactose_module_restores_both_of_its_sites():
    """Ground truth, end to end: the case this feature exists for.

    rs4988235 (2:135851076) and rs182549 (2:135859184) are both absent from Anton Kulaga's callset,
    both have a called variant within a kilobase, and both authored genotypes are the reference one.
    """
    from just_dna_pipelines.annotation.hf_logic import _normalize_lead_genotype, _normalize_vcf_contigs
    from just_dna_pipelines.annotation.hf_modules import ModuleTable, scan_module_table
    from just_dna_pipelines.annotation.resources import get_user_output_dir

    info = _local_lactose_module()
    if info is None:
        pytest.skip("local lactose module not registered on this machine")

    normalized = get_user_output_dir() / "anonymous/antonkulaga/user_vcf_normalized.parquet"
    if not normalized.exists():
        pytest.skip("antonkulaga sample not annotated on this machine")

    vcf = _normalize_vcf_contigs(pl.scan_parquet(normalized))
    ctx = build_restoration_context(vcf, 10_000)
    assert ctx.mode == GenotypeInputMode.VARIANT_ONLY

    name = "eric_mods__lactose_tolerance"
    lead = _normalize_lead_genotype(scan_module_table(name, ModuleTable.LEAD, module_info=info))
    rows, stats = restored_rows(vcf, lead, name, ctx)
    assert stats == {"hom_ref_rows": 2, "absent": 2, "restored": 2}

    got = rows.collect().sort("start")
    assert got["start"].to_list() == [135851076, 135859184]
    assert got["genotype"].to_list() == [["G", "G"], ["C", "C"]]
    assert set(got[EVIDENCE_COLUMN].to_list()) == {EVIDENCE_RESTORED}
