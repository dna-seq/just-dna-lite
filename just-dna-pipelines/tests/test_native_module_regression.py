"""The compound-phenotype work must not reroute a module that already works.

The new diplotype caller is reached only through ``module_kind(info) == "phenotype"``, which the
engine checks *before* the existing per-module call. These tests fence that seam: every module that
is not phenotype-shaped stays ``"variant"`` and keeps its current join strategy, and a compiled
phenotype fixture is classified ``"phenotype"`` only when it carries a usable combiner.
"""

from __future__ import annotations

import polars as pl
import pytest

from just_dna_pipelines.annotation.hf_modules import (
    MODULE_INFOS,
    ModuleInfo,
    module_kind,
)

GATE_MODULES = ["longevitymap", "thrombophilia", "coronary", "pharmgkb"]


class TestModuleKindIsPure:
    """`module_kind` reads only ModuleInfo fields — network-free, so it can enumerate exhaustively."""

    @pytest.mark.parametrize("name", GATE_MODULES)
    def test_the_gate_modules_stay_variant(self, name: str) -> None:
        if name not in MODULE_INFOS:
            pytest.skip(f"{name} not discovered in this checkout")
        assert module_kind(MODULE_INFOS[name]) == "variant"

    def test_no_currently_discovered_module_is_phenotype(self) -> None:
        """None of the modules we ship carry the phenotype tables, so all classify `variant`.

        This is the exhaustive half of the fence: if a future discovery starts returning a module
        the caller would grab, this catches it rather than a report silently changing shape.
        """
        for name, info in MODULE_INFOS.items():
            assert module_kind(info) == "variant", f"{name} unexpectedly classified phenotype"

    def _info(self, **kw: object) -> ModuleInfo:
        return ModuleInfo(name="m", repo_id="r", path="p", lead_url="u", **kw)  # type: ignore[arg-type]

    def test_enumerative_diplotype_module_is_phenotype(self) -> None:
        info = self._info(
            lead_table="diplotypes",
            haplotypes_url="h",
            diplotypes_url="d",
        )
        assert module_kind(info) == "phenotype"

    def test_score_and_bin_module_is_phenotype(self) -> None:
        info = self._info(
            lead_table="activity_phenotype",
            haplotypes_url="h",
            allele_function_url="a",
            activity_phenotype_url="p",
        )
        assert module_kind(info) == "phenotype"

    def test_haplotypes_without_a_combiner_is_unsupported(self) -> None:
        """A haplotypes lead with no diplotypes and no score-and-bin pair is neither the caller's job
        nor the weights engine's — it stays a recorded skip, exactly as today."""
        info = self._info(lead_table="haplotypes", haplotypes_url="h")
        assert module_kind(info) == "unsupported"

    def test_allele_function_without_activity_phenotype_is_unsupported(self) -> None:
        info = self._info(
            lead_table="allele_function", haplotypes_url="h", allele_function_url="a"
        )
        assert module_kind(info) == "unsupported"

    def test_a_weights_module_that_also_ships_haplotypes_stays_variant(self) -> None:
        """Routing is on the lead table: a mixed module keeps the per-position path."""
        info = self._info(lead_table="weights", weights_url="w", haplotypes_url="h", diplotypes_url="d")
        assert module_kind(info) == "variant"


class TestCompiledFixtureIsDiscoveredAsPhenotype:
    """End to end over the fsspec probe: a real 0.7 artifact wires the tables and classifies right."""

    @pytest.mark.parametrize("name", ["apoe_epsilon", "hfe_compound_het"])
    def test_compiled_reference_example_is_phenotype(self, name: str, tmp_path) -> None:
        from phenotype_fixtures import compile_fixture, probe_local

        module_dir = compile_fixture(name, tmp_path / name)
        info = probe_local(module_dir, name)
        # diplotypes outranks haplotypes in LEAD_TABLES, so the enumerative module leads with it.
        assert info.lead_table == "diplotypes"
        assert info.haplotypes_url is not None
        assert info.diplotypes_url is not None
        assert module_kind(info) == "phenotype"

    def test_lead_join_strategy_still_refuses_the_compiled_tables(self, tmp_path) -> None:
        """The safety argument, made concrete: the caller's seam is the only thing that reaches these
        artifacts. On the *old* path both their tables route to `unsupported` → a recorded skip."""
        from just_dna_pipelines.annotation.hf_logic import _lead_join_strategy
        from phenotype_fixtures import compile_fixture

        module_dir = compile_fixture("apoe_epsilon", tmp_path / "apoe")
        for table in ("diplotypes", "haplotypes"):
            strategy, _ = _lead_join_strategy(pl.scan_parquet(module_dir / f"{table}.parquet"))
            assert strategy == "unsupported"
