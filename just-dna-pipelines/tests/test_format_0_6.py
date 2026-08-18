"""The 0.6 contract seams: the lists this repo derives from the compiler instead of restating.

Every test here exists because a hand-kept copy of an upstream list has already gone wrong at least
once — here or in the libraries. They are cheap, they need no network, and each one names the failure
it prevents rather than restating the constant.
"""

import polars as pl
import pytest
from just_dna_compiler.compiler import ARTIFACT_PARQUETS, LEAD_PARQUETS
from just_dna_format.alleles import split_genotype

from just_dna_pipelines.annotation.hf_logic import _normalize_lead_genotype
from just_dna_pipelines.annotation.report_logic import _genotype_alleles
from just_dna_pipelines.module_config import LEAD_TABLE_CSVS, LEAD_TABLES
from just_dna_pipelines.v1_port.publish import _ALLOW_PATTERNS, _LEAD_PARQUETS

#: Authored genotype cells, including shapes nothing in our corpus carries.
#:
#: **The phased ones are the point.** Every module we hold authors unphased genotypes, so a splitter
#: that mishandles `|` passes the entire suite — which is how the report's splitter came to read
#: `"A|G"` as the single allele `["A|G"]` and render no zygosity for it, and how the engine's first
#: version came to *sort*, folding `A|G` and `G|A` into one key and manufacturing a match no module
#: had stated. Neither could have been caught by a fixture drawn from the corpus.
GENOTYPE_CELLS = [
    "A/G",     # the ordinary unphased pair
    "A|G",     # phased, authored order
    "G|A",     # phased, the other homolog order — a distinct genotype, not a spelling of the above
    "G",       # hemizygous: how every haploid contig in the corpus is authored
    "G/G",     # homozygous
    "*/T",     # `*` — allele missing due to an overlapping deletion (VCF 1.6.1.5)
    "TA/TA",
    "AGAG/AG",
]


class TestLeadTableFamilies:
    """`LEAD_TABLES` is this repo's ordered view of the compiler's lead families — same members."""

    def test_lead_tables_covers_exactly_the_compilers_lead_families(self):
        """Set equality, because both directions are a real defect with a known symptom.

        A family the compiler leads with and we do not know is a module we cannot discover, publish
        or edit — which is how a `pharm_variants`-led registry install came to be annotatable but
        absent from the publish pane. A family we list and the compiler does not is a probe for a
        parquet that can never exist.

        Order is deliberately *not* asserted: ours is priority order (a module shipping several is
        led by the first) and the compiler's is `artifact.digest` order. They are different questions.
        """
        assert {f"{table}.parquet" for table in LEAD_TABLES} == set(LEAD_PARQUETS)

    def test_every_lead_family_maps_to_an_authored_csv(self):
        """`weights` is the only family whose CSV is not its own stem — the DSL spells it `variants.csv`.

        The mapping is derived, so this pins the one special case. If the compiler ever adds a family
        with a second irregular spelling, `LEAD_TABLE_CSVS` would invent a name that does not exist
        and the row count behind the registry's enrichment ceiling would silently read 0.
        """
        assert len(LEAD_TABLE_CSVS) == len(LEAD_TABLES)
        assert dict(zip(LEAD_TABLES, LEAD_TABLE_CSVS))["weights"] == "variants.csv"
        for table, csv_name in zip(LEAD_TABLES, LEAD_TABLE_CSVS):
            if table != "weights":
                assert csv_name == f"{table}.csv"


class TestPublisherAllowlist:
    """The allowlist must cover every parquet `artifact.digest` is computed over."""

    def test_the_allowlist_covers_every_artifact_parquet(self):
        """A name missing here is a file the manifest attests and the upload never sends.

        The published digest is then unreproducible from what arrived. Upstream measured fifteen of
        sixteen reference modules published wrong through a hand-kept allowlist of this exact shape,
        with `sources.parquet` — the licence terms — dropped every time it existed.
        """
        assert set(ARTIFACT_PARQUETS) <= set(_ALLOW_PATTERNS)

    def test_the_three_tables_0_6_added_are_covered(self):
        """Named explicitly: these are the ones a pre-0.6 hand-kept list omitted.

        `set <=` above would also pass on a list that happens to be stale in some *other* way, so
        this states the concrete regression rather than only the invariant.
        """
        for table in (
            "gene_validity.parquet",
            "clinical_assertions.parquet",
            "gwas_effects.parquet",
        ):
            assert table in _ALLOW_PATTERNS, table

    def test_the_publisher_and_discovery_agree_on_what_leads_a_module(self):
        """The publish gate and the discovery probe must accept the same set, or a module publishes
        and is then invisible (or is discoverable and refuses to publish)."""
        assert set(_LEAD_PARQUETS) == {f"{table}.parquet" for table in LEAD_TABLES}


class TestOneGenotypeSplit:
    """Both of this repo's splitters must agree with `just_dna_format.alleles.split_genotype`.

    That function was made public in 0.6 (S30) because the rule lives in three places that have to
    agree — the validator's grammar, the compiler's materializer, and every consumer reading a
    0.4-family table — and only the third had prose to work from. A reimplementation that is slightly
    wrong raises nothing; it just matches a quietly larger or smaller set.
    """

    @pytest.mark.parametrize("cell", GENOTYPE_CELLS)
    def test_the_reports_python_split_matches_the_format(self, cell: str) -> None:
        """`report_logic._genotype_alleles`, for a row already read out of a parquet."""
        assert _genotype_alleles(cell) == split_genotype(cell)

    @pytest.mark.parametrize("cell", GENOTYPE_CELLS)
    def test_the_engines_vectorized_split_matches_the_format(self, cell: str) -> None:
        """`hf_logic._normalize_lead_genotype`, the polars form the join actually uses.

        It cannot call `split_genotype` per row — that would be a Python call over millions of VCF
        rows — so it is a separate expression, and this is what keeps the two from drifting.
        """
        out = _normalize_lead_genotype(pl.LazyFrame({"genotype": [cell]})).collect()
        assert out["genotype"].to_list()[0] == split_genotype(cell)

    def test_neither_split_sorts(self) -> None:
        """Phase is homolog order, so `A|G` and `G|A` must stay two different genotypes.

        Sorting here would fold them into one key and manufacture a match the module never stated.
        Sorting belongs only in `_genotype_join_key`, which rebuilds the *authored* key for an
        unphased cell, and this test is the fence between the two.
        """
        assert _genotype_alleles("G|A") == ["G", "A"]
        assert _genotype_alleles("A|G") == ["A", "G"]
        engine = _normalize_lead_genotype(
            pl.LazyFrame({"genotype": ["G|A"]})
        ).collect()["genotype"].to_list()[0]
        assert engine == ["G", "A"]
