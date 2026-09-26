"""The diplotype caller: status logic, restoration, and the parquet contract.

Fixtures are compiled from vendored spec dirs at test time (see ``phenotype_fixtures``), so the caller
runs against a real 0.7 artifact. Expected phenotypes are **derived** from each module's own diplotype
table rather than hardcoded — the runtime-ground-truth rule — so a wrong allele lookup or a sort bug
fails across the whole table, not just a hand-picked case.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from phenotype_fixtures import compile_fixture, probe_local

from just_dna_pipelines.annotation.phenotype_caller import (
    PHENOTYPE_CALL_SCHEMA,
    Candidate,
    GeneDefinition,
    PhenotypeCall,
    SiteEvidence,
    _allele_at,
    _write_calls,
    call_gene,
    call_phenotype_module,
    gather_site_evidence,
    load_phenotype_definition,
)
from just_dna_pipelines.annotation.restoration import (
    CallsetScope,
    RestorationContext,
    build_restoration_context,
)

APOE_SITE_1 = "19:44908684"  # rs429358
APOE_SITE_2 = "19:44908822"  # rs7412


@pytest.fixture(scope="module")
def apoe_def(tmp_path_factory) -> GeneDefinition:
    module_dir = compile_fixture("apoe_epsilon", tmp_path_factory.mktemp("apoe"))
    info = probe_local(module_dir, "apoe_epsilon")
    return load_phenotype_definition("apoe_epsilon", info).genes["APOE"]


@pytest.fixture(scope="module")
def hfe_def(tmp_path_factory) -> GeneDefinition:
    module_dir = compile_fixture("hfe_compound_het", tmp_path_factory.mktemp("hfe"))
    info = probe_local(module_dir, "hfe_compound_het")
    return load_phenotype_definition("hfe_compound_het", info).genes["HFE"]


def _evidence(gene_def: GeneDefinition, observed: dict[str, object]) -> list[SiteEvidence]:
    """Build a SiteEvidence list from a {site_key: [alleles] | "no_call" | "restored"} map."""
    out: list[SiteEvidence] = []
    for key, meta in gene_def.site_meta.items():
        chrom, start = key.split(":")
        value = observed.get(key, "no_call")
        if value == "no_call":
            out.append(SiteEvidence(rsid=meta["rsid"], chrom=chrom, start=int(start), ref=meta["ref"],
                                    observed=None, evidence="no_call", matched_by=None,
                                    restored_flank_bp=None))
        elif value == "restored":
            out.append(SiteEvidence(rsid=meta["rsid"], chrom=chrom, start=int(start), ref=meta["ref"],
                                    observed=[meta["ref"], meta["ref"]], evidence="restored_hom_ref",
                                    matched_by=None, restored_flank_bp=500))
        else:
            out.append(SiteEvidence(rsid=meta["rsid"], chrom=chrom, start=int(start), ref=meta["ref"],
                                    observed=list(value), evidence="called", matched_by="position",
                                    restored_flank_bp=None))
    return out


class TestCallGeneStatus:
    """The four statuses, exercised through the pure `call_gene`."""

    def test_nothing_observed_is_not_assessable(self, apoe_def: GeneDefinition) -> None:
        """Every site no_call → not_assessable. Never a silent e3/e3 default."""
        call = call_gene("apoe_epsilon", apoe_def, _evidence(apoe_def, {}))
        assert call.status == "not_assessable"
        assert call.phenotype is None
        # Every diplotype is trivially consistent when nothing constrains it — the reader is shown
        # what was considered rather than an empty card.
        assert len(call.candidates) == len(apoe_def.diplotypes)

    def test_a_genotype_no_pair_explains_is_no_match(self, apoe_def: GeneDefinition) -> None:
        call = call_gene(
            "apoe_epsilon",
            apoe_def,
            _evidence(apoe_def, {APOE_SITE_1: ["C", "C"], APOE_SITE_2: ["T", "T"]}),
        )
        assert call.status == "no_match"
        assert call.candidates == []

    def test_double_het_resolves_to_e2_e4(self, apoe_def: GeneDefinition) -> None:
        """The plan's headline case: unphased het at both sites, e1 undefined → called e2/e4."""
        call = call_gene(
            "apoe_epsilon",
            apoe_def,
            _evidence(apoe_def, {APOE_SITE_1: ["C", "T"], APOE_SITE_2: ["C", "T"]}),
        )
        assert call.status == "called"
        assert call.phenotype == "APOE ε2/ε4"
        assert {(c.haplotype_a, c.haplotype_b) for c in call.candidates} == {("e2", "e4")}

    def test_a_no_call_site_splits_candidates_and_phase_does_not_decide(self, apoe_def) -> None:
        """rs429358 het, rs7412 not called: e2/e4 and e3/e4 both fit — but at the *no_call* site, so a
        call there (not phase) would settle it. phase_would_decide must be False."""
        call = call_gene(
            "apoe_epsilon", apoe_def, _evidence(apoe_def, {APOE_SITE_1: ["C", "T"]})
        )
        assert call.status == "ambiguous"
        assert call.phase_would_decide is False
        phenos = {c.phenotype for c in call.candidates}
        assert len(phenos) > 1


class TestPhaseAmbiguity:
    def test_hfe_double_het_is_ambiguous_and_phase_would_decide(self, hfe_def: GeneDefinition) -> None:
        """Compound het (trans) vs cis carrier: same observed alleles, different homolog assignment."""
        sites = {k: ["A", "G"] if "26092913" in k else ["C", "G"] for k in hfe_def.site_meta}
        call = call_gene("hfe_compound_het", hfe_def, _evidence(hfe_def, sites))
        assert call.status == "ambiguous"
        assert call.phase_would_decide is True
        assert len(call.candidates) == 2


class TestDerivedFromTheModulesOwnTable:
    """For every diplotype the module defines, feed the exact genotype it implies and require the call.

    This is the runtime-ground-truth test: the expectation is read off the module, so it catches a
    wrong `_allele_at` (unlisted-site convention) or a sort bug over the whole table at once.
    """

    @pytest.mark.parametrize("fixture", ["apoe_epsilon", "hfe_compound_het"])
    def test_every_diplotype_calls_its_own_phenotype(self, fixture: str, tmp_path: Path) -> None:
        module_dir = compile_fixture(fixture, tmp_path / fixture)
        info = probe_local(module_dir, fixture)
        definition = load_phenotype_definition(fixture, info)
        for gene_def in definition.genes.values():
            for diplo in gene_def.diplotypes:
                a, b = diplo["haplotype_a"], diplo["haplotype_b"]
                observed = {
                    key: sorted([_allele_at(gene_def, a, key), _allele_at(gene_def, b, key)])
                    for key in gene_def.site_meta
                }
                call = call_gene(fixture, gene_def, _evidence(gene_def, observed))
                # The genotype may be explained by more than this one diplotype (a homozygote is
                # unambiguous, a double-het need not be), but the authored phenotype must always be
                # among the candidates, and whenever exactly one diplotype is consistent the call must
                # be `called` with that diplotype's own phenotype.
                candidate_pairs = {(c.haplotype_a, c.haplotype_b) for c in call.candidates}
                assert (a, b) in candidate_pairs, f"{fixture} {a}/{b} not among candidates"
                if len(call.candidates) == 1:
                    assert call.status == "called", f"{fixture} {a}/{b}"
                    assert call.phenotype == diplo["phenotype"], f"{fixture} {a}/{b}"

    def test_the_derived_check_fails_on_a_broken_allele_lookup(self, tmp_path: Path, monkeypatch) -> None:
        """Demonstrate the derived test catches a real bug: make `_allele_at` always return ref.

        With every haplotype reading as reference at every site, the only genotype any pair produces is
        hom-ref, so a heterozygous-diplotype genotype resolves to the wrong diplotype (or none) — the
        derived assertions above must then fail.
        """
        import just_dna_pipelines.annotation.phenotype_caller as pc

        module_dir = compile_fixture("apoe_epsilon", tmp_path / "apoe")
        info = probe_local(module_dir, "apoe_epsilon")
        gene_def = load_phenotype_definition("apoe_epsilon", info).genes["APOE"]

        monkeypatch.setattr(pc, "_allele_at", lambda gd, hap, key: gd.site_meta[key]["ref"])
        # e2/e4 implies a het genotype under the real alleles; feed that, expect the broken lookup to
        # NOT reproduce e2/e4 as the sole called diplotype.
        observed = {APOE_SITE_1: ["C", "T"], APOE_SITE_2: ["C", "T"]}
        call = call_gene("apoe_epsilon", gene_def, _evidence(gene_def, observed))
        assert not (
            call.status == "called" and call.phenotype == "APOE ε2/ε4"
        ), "broken _allele_at should not still produce the correct call"


class TestRestorationReachesAReferenceCall:
    """A WGS variant-only callset with no record at either site, but coverage nearby → e3/e3."""

    def _wgs_ctx(self, vcf: pl.LazyFrame) -> RestorationContext:
        base = build_restoration_context(vcf, 10_000)
        return RestorationContext(
            called_sites=base.called_sites, mode=base.mode, scope=CallsetScope.WGS,
            scope_reason="forced for this test", max_flank_bp=10_000,
        )

    def test_absent_apoe_sites_restore_to_e3_e3(self, tmp_path: Path) -> None:
        module_dir = compile_fixture("apoe_epsilon", tmp_path / "apoe")
        info = probe_local(module_dir, "apoe_epsilon")
        # A callset that carries neither APOE site but has calls 500 bp away on chr19.
        vcf = pl.DataFrame(
            {
                "chrom": ["19", "19"],
                "start": [44908184, 44909322],
                "rsid": [None, None],
                "ref": ["A", "A"],
                "alt": ["G", "G"],
                "filter": ["PASS", "PASS"],
                "GT": ["0/1", "0/1"],
                "genotype": [["A", "G"], ["A", "G"]],
            },
            schema_overrides={"start": pl.UInt32, "genotype": pl.List(pl.String)},
        ).lazy()
        ctx = self._wgs_ctx(vcf)
        out, n_called = call_phenotype_module(
            vcf, "apoe_epsilon", info, ctx, tmp_path / "out" / "apoe_epsilon_phenotypes.parquet"
        )
        df = pl.read_parquet(out)
        row = df.filter(pl.col("gene") == "APOE").to_dicts()[0]
        assert row["status"] == "called"
        assert row["phenotype"] == "APOE ε3/ε3"
        assert {s["evidence"] for s in row["sites"]} == {"restored_hom_ref"}
        assert n_called == 1

    def test_a_disabled_callset_restores_nothing_and_is_not_assessable(self, tmp_path: Path) -> None:
        """An exome (restoration off) with no APOE records must not become e3/e3."""
        module_dir = compile_fixture("apoe_epsilon", tmp_path / "apoe")
        info = probe_local(module_dir, "apoe_epsilon")
        vcf = pl.DataFrame(
            {"chrom": ["19"], "start": [44908184], "rsid": [None], "ref": ["A"], "alt": ["G"],
             "filter": ["PASS"], "GT": ["0/1"], "genotype": [["A", "G"]]},
            schema_overrides={"start": pl.UInt32, "genotype": pl.List(pl.String)},
        ).lazy()
        base = build_restoration_context(vcf, 10_000)
        disabled = RestorationContext(
            called_sites=base.called_sites, mode=base.mode, scope=CallsetScope.TARGETED,
            scope_reason="forced targeted", max_flank_bp=10_000,
        )
        assert not disabled.enabled
        out, _ = call_phenotype_module(
            vcf, "apoe_epsilon", info, disabled, tmp_path / "out" / "apoe_epsilon_phenotypes.parquet"
        )
        row = pl.read_parquet(out).filter(pl.col("gene") == "APOE").to_dicts()[0]
        assert row["status"] == "not_assessable"
        assert {s["evidence"] for s in row["sites"]} == {"no_call"}


class TestParquetContract:
    """The nested-column schema must survive a mixed-status module and an empty one."""

    def _call(self, gene: str, status: str, candidates: list[Candidate]) -> PhenotypeCall:
        return PhenotypeCall(
            module="m", gene=gene, status=status, phenotype=None, candidates=candidates,
            sites=[SiteEvidence(rsid="rs1", chrom="1", start=1, ref="A", observed=None,
                                evidence="no_call", matched_by=None, restored_flank_bp=None)],
            phase_would_decide=False, alleles_considered=["x"], alleles_not_assessable=[],
            unpaired_haplotypes=[], drug_rows=[], compiler_warnings=[],
        )

    def test_a_called_gene_beside_a_no_match_gene_round_trips(self, tmp_path: Path) -> None:
        """The case that breaks row-inferred schemas: empty `candidates` beside populated ones."""
        called = self._call(
            "G1", "called",
            [Candidate(haplotype_a="a", haplotype_b="b", phenotype="P", conclusion="c",
                       direction="risk", clin_sig=None)],
        )
        no_match = self._call("G2", "no_match", [])
        out = tmp_path / "m_phenotypes.parquet"
        _write_calls([called, no_match], out)
        df = pl.read_parquet(out)
        assert df.height == 2
        assert df.schema["candidates"] == PHENOTYPE_CALL_SCHEMA["candidates"]
        assert df.schema["sites"] == PHENOTYPE_CALL_SCHEMA["sites"]

    def test_an_empty_module_writes_typed_empty_columns(self, tmp_path: Path) -> None:
        out = tmp_path / "empty_phenotypes.parquet"
        _write_calls([], out)
        df = pl.read_parquet(out)
        assert df.height == 0
        assert set(df.columns) == set(PHENOTYPE_CALL_SCHEMA)


class TestEngineDispatch:
    """The engine routes a phenotype module to the caller and records it apart from variant totals."""

    def test_a_phenotype_module_writes_a_phenotypes_parquet_and_manifest_entry(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        import logging

        from just_dna_pipelines.annotation import hf_logic, hf_modules
        from just_dna_pipelines.annotation.configs import HfModuleAnnotationConfig

        module_dir = compile_fixture("apoe_epsilon", tmp_path / "apoe_mod")
        info = probe_local(module_dir, "apoe_epsilon")

        # Inject the compiled module into discovery so the engine treats it as a first-class module,
        # without registering it on the machine.
        monkeypatch.setitem(hf_logic.MODULE_INFOS, "apoe_epsilon", info)
        monkeypatch.setattr(
            hf_modules, "DISCOVERED_MODULES", [*hf_modules.DISCOVERED_MODULES, "apoe_epsilon"]
        )

        # A tiny callset carrying both APOE sites het → called ε2/ε4 (restoration is off on a frame
        # this small, but the sites are present so it is not needed).
        normalized = tmp_path / "sample.parquet"
        pl.DataFrame(
            {
                "chrom": ["19", "19"],
                "start": [44908684, 44908822],
                "rsid": [None, None],
                "ref": ["T", "C"],
                "alt": ["C", "T"],
                "filter": ["PASS", "PASS"],
                "GT": ["0/1", "0/1"],
                "genotype": [["C", "T"], ["C", "T"]],
            },
            schema_overrides={"start": pl.UInt32, "genotype": pl.List(pl.String)},
        ).write_parquet(normalized)

        out_dir = tmp_path / "modules"
        config = HfModuleAnnotationConfig(
            vcf_path=str(normalized),
            user_name="t",
            modules=["apoe_epsilon"],
            output_dir=str(out_dir),
        )
        manifest, _ = hf_logic.annotate_vcf_with_all_modules(
            logging.getLogger("t"), normalized, config, "t", "sample", normalized
        )

        assert (out_dir / "apoe_epsilon_phenotypes.parquet").exists()
        assert not (out_dir / "apoe_epsilon_weights.parquet").exists()
        entry = next(m for m in manifest.modules if m.module == "apoe_epsilon")
        assert entry.kind == "phenotype"
        assert entry.phenotypes_path is not None
        assert manifest.phenotype_calls["apoe_epsilon"].get("called") == 1
        assert manifest.total_phenotypes_called == 1
        # A phenotype call is never folded into the variant totals.
        assert manifest.total_variants_annotated == 0
        assert manifest.total_variants_restored == 0


@pytest.mark.integration
class TestRealSample:
    """Anton is het at both APOE sites (0/1, no rsIDs), so this matches by position → e2/e4."""

    def test_apoe_on_anton_is_e2_e4(self, tmp_path: Path) -> None:
        from just_dna_pipelines.annotation.hf_logic import _normalize_vcf_contigs
        from just_dna_pipelines.annotation.resources import get_user_output_dir
        from just_dna_pipelines.runtime import load_env

        load_env()
        normalized = get_user_output_dir() / "anonymous/antonkulaga/user_vcf_normalized.parquet"
        if not normalized.exists():
            pytest.skip("antonkulaga sample not present on this machine")
        module_dir = compile_fixture("apoe_epsilon", tmp_path / "apoe")
        info = probe_local(module_dir, "apoe_epsilon")
        vcf = _normalize_vcf_contigs(pl.scan_parquet(normalized))
        ctx = build_restoration_context(vcf, 10_000)
        out, _ = call_phenotype_module(
            vcf, "apoe_epsilon", info, ctx, tmp_path / "out" / "apoe_epsilon_phenotypes.parquet"
        )
        row = pl.read_parquet(out).filter(pl.col("gene") == "APOE").to_dicts()[0]
        assert row["status"] == "called"
        assert row["phenotype"] == "APOE ε2/ε4"
        assert {s["matched_by"] for s in row["sites"]} == {"position"}
