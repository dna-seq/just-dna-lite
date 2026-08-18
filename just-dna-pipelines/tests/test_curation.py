"""
Curated corrections to Gen-I module content: the mechanism, and the trap in it.

The corrections themselves are adjudicated per row in `data/curation/*.csv` with their evidence; what
is tested here is that applying one does what it claims, and in particular that a weight correction
carries `state` with it.
"""

import pytest

from just_dna_pipelines.module_compiler.models import StudyRow, VariantRow
from just_dna_pipelines.v1_port import curation
from just_dna_pipelines.v1_port.curation import (
    apply_study_corrections,
    apply_variant_corrections,
    variant_corrections,
)


def _variant(rsid: str, genotype: str, weight: float, state: str) -> VariantRow:
    return VariantRow(rsid=rsid, genotype=genotype, weight=weight, state=state, conclusion="x")


@pytest.fixture
def curation_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(curation, "_CURATION_DIR", tmp_path)
    return tmp_path


class TestWeightCarriesState:
    """A sign correction that leaves `state` stale changes the number and keeps the wrong rendering.

    This is the defect the coronary corrections exist to fix, and it was briefly reintroduced *by* them:
    `state` is derived from the weight at adapter time, and `report_logic._effective_direction` falls
    back to `direction_from_state`, so a row reading `weight=-1.6, state=protective` still renders
    benefit-green. The correction is only complete if both move.
    """

    def test_a_weight_flipped_negative_becomes_risk(self, curation_dir):
        (curation_dir / "m.csv").write_text(
            "rsid,genotype,field,new_value,reason\n"
            "rs1,C/C,weight,-1.6,\"risk allele is C per GWAS Catalog\"\n",
            encoding="utf-8",
        )
        warnings: list[str] = []
        out = apply_variant_corrections("m", [_variant("rs1", "C/C", 1.6, "protective")], warnings)
        assert out[0].weight == -1.6
        assert out[0].state == "risk", "state must follow the corrected weight, not stay as authored"

    def test_a_weight_zeroed_becomes_neutral(self, curation_dir):
        (curation_dir / "m.csv").write_text(
            "rsid,genotype,field,new_value,reason\n"
            "rs1,A/A,weight,0.0,\"the magnitude belonged to the other homozygote\"\n",
            encoding="utf-8",
        )
        out = apply_variant_corrections("m", [_variant("rs1", "A/A", -1.54, "risk")], [])
        assert (out[0].weight, out[0].state) == (0.0, "neutral")

    def test_an_explicit_state_correction_wins(self, curation_dir):
        """A `state` row is applied in its own right, so it overrides the weight-derived value."""
        (curation_dir / "m.csv").write_text(
            "rsid,genotype,field,new_value,reason\n"
            "rs1,C/C,weight,-1.0,\"sign\"\n"
            "rs1,C/C,state,protective,\"deliberate override\"\n",
            encoding="utf-8",
        )
        out = apply_variant_corrections("m", [_variant("rs1", "C/C", 1.0, "protective")], [])
        assert (out[0].weight, out[0].state) == (-1.0, "protective")


class TestMechanism:
    def test_a_correction_is_reported_not_silent(self, curation_dir):
        """A silent correction is indistinguishable from a silent corruption."""
        (curation_dir / "m.csv").write_text(
            "rsid,genotype,field,new_value,reason\n"
            "rs1,C/C,weight,-1.6,\"because the GWAS Catalog says C is the risk allele\"\n",
            encoding="utf-8",
        )
        warnings: list[str] = []
        apply_variant_corrections("m", [_variant("rs1", "C/C", 1.6, "protective")], warnings)
        assert any("curated correction" in w for w in warnings)
        assert any("GWAS Catalog" in w for w in warnings), "the reason must reach the build log"

    def test_a_correction_matching_nothing_is_reported(self, curation_dir):
        """A stale override is exactly when silence is dangerous — the source moved under it."""
        (curation_dir / "m.csv").write_text(
            "rsid,genotype,field,new_value,reason\n"
            "rs_absent,C/C,weight,-1.0,\"stale\"\n",
            encoding="utf-8",
        )
        warnings: list[str] = []
        apply_variant_corrections("m", [_variant("rs1", "C/C", 1.0, "protective")], warnings)
        assert any("matched no row" in w for w in warnings)

    def test_star_matches_every_genotype_of_an_rsid(self, curation_dir):
        (curation_dir / "m.csv").write_text(
            "rsid,genotype,field,new_value,reason\n"
            "rs1,*,gene,GUCY1A1,\"retired alias\"\n",
            encoding="utf-8",
        )
        rows = [_variant("rs1", "C/C", 0.0, "neutral"), _variant("rs1", "C/T", -1.0, "risk")]
        out = apply_variant_corrections("m", rows, [])
        assert [r.gene for r in out] == ["GUCY1A1", "GUCY1A1"]

    def test_drop_removes_the_row(self, curation_dir):
        (curation_dir / "m.csv").write_text(
            "rsid,genotype,field,new_value,reason\n"
            "rs1,C/C,drop,,\"strand duplicate of the C/G row\"\n",
            encoding="utf-8",
        )
        rows = [_variant("rs1", "C/C", 0.0, "neutral"), _variant("rs1", "C/T", -1.0, "risk")]
        out = apply_variant_corrections("m", rows, [])
        assert [r.genotype for r in out] == ["C/T"]

    def test_no_table_is_a_no_op(self, curation_dir):
        rows = [_variant("rs1", "C/C", 1.0, "protective")]
        assert apply_variant_corrections("nosuchmodule", rows, []) == rows

    def test_a_study_pmid_is_corrected(self, curation_dir):
        (curation_dir / "m_studies.csv").write_text(
            "rsid,pmid,field,new_value,reason\n"
            "rs1,2783984,pmid,12783984,\"a dropped leading digit; 2783984 is an unrelated 1989 paper\"\n",
            encoding="utf-8",
        )
        warnings: list[str] = []
        out = apply_study_corrections("m", [StudyRow(rsid="rs1", pmid="2783984")], warnings)
        assert out[0].pmid == "12783984"
        assert any("curated study correction" in w for w in warnings)


class TestShippedTables:
    """The tables that actually ship must be loadable and well-formed."""

    @pytest.mark.parametrize("module", ["coronary"])
    def test_every_field_is_one_the_applier_understands(self, module):
        rows = variant_corrections(module)
        assert rows, f"{module}.csv should not be empty if it exists"
        for row in rows:
            assert row["field"] in curation.VARIANT_FIELDS, row
            assert row["reason"], f"a correction without a reason is not a curation decision: {row}"
            if row["field"] == "weight":
                float(row["new_value"])  # raises if it is not a number
