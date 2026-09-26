"""The report's "Phenotypes from combined variants" section, rendered end to end.

A phenotype module is run through the real engine on a small synthetic callset, and the real report
generator renders the result. The assertions are about what a reader sees: the status, the diplotype
and its conclusion, the per-site evidence (phase, indel spelling, inference), and the coverage line.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import polars as pl
import pytest

from phenotype_fixtures import compile_fixture, probe_local

from just_dna_pipelines.annotation import hf_logic, hf_modules, report_logic
from just_dna_pipelines.annotation.configs import HfModuleAnnotationConfig
from just_dna_pipelines.annotation.report_logic import generate_longevity_report


def _callset(path: Path, records: list[tuple[str, int, str, str, str, int | None]]) -> Path:
    rows = []
    for chrom, start, ref, alt, gt, ps in records:
        pool = [ref] + alt.split(",")
        rows.append({"chrom": chrom, "start": start, "rsid": None, "ref": ref, "alt": alt, "filter": "PASS",
                     "GT": gt, "PS": ps,
                     "genotype": sorted(pool[int(i)] for i in re.split(r"[/|]", gt))})
    pl.DataFrame(rows, schema_overrides={"start": pl.UInt32, "PS": pl.Int32,
                                         "genotype": pl.List(pl.String)}).write_parquet(path)
    return path


def _run(tmp_path: Path, monkeypatch, modules: list[str], records) -> str:
    infos = {m: probe_local(compile_fixture(m, tmp_path / "compiled" / m), m) for m in modules}
    for name, info in infos.items():
        monkeypatch.setitem(hf_logic.MODULE_INFOS, name, info)
    monkeypatch.setattr(hf_modules, "DISCOVERED_MODULES", [*hf_modules.DISCOVERED_MODULES, *modules])
    monkeypatch.setattr(report_logic, "discover_hf_modules", lambda: {**hf_logic.MODULE_INFOS, **infos})
    normalized = _callset(tmp_path / "sample.parquet", records)
    out_dir = tmp_path / "modules"
    config = HfModuleAnnotationConfig(vcf_path=str(normalized), user_name="t", modules=modules,
                                      output_dir=str(out_dir))
    hf_logic.annotate_vcf_with_all_modules(logging.getLogger("t"), normalized, config, "t", "sample", normalized)
    report = generate_longevity_report(out_dir, tmp_path / "report.html", module_names=modules)
    return report.read_text()


def _card(html: str, gene: str) -> str:
    start = html.index(f'id="phenotype-{gene}"')
    return html[start:html.index("</article>", start)]


class TestPhenotypeSection:
    def test_a_phased_trans_hfe_call_renders_its_diplotype_and_phase(self, tmp_path, monkeypatch) -> None:
        html = _run(tmp_path, monkeypatch, ["hfe_compound_het"], [
            ("6", 26092913, "G", "A", "0|1", 26090951),
            ("6", 26090951, "C", "G", "1|0", 26090951),
        ])
        assert "Phenotypes from combined variants" in html
        card = _card(html, "HFE")
        assert "Called" in card
        assert "C282Y/H63D compound heterozygous" in card
        assert "Diplotype <strong>C282Y / H63D</strong>" in card
        # The authored conclusion reaches the reader, not just the phenotype label.
        assert "in trans" in card
        assert card.count("phase set 26090951") == 2
        assert "Alleles considered: C282Y, C282Y-H63D, H63D, wt." in card

    def test_an_unphased_double_het_is_ambiguous_and_says_phase_would_decide(self, tmp_path, monkeypatch) -> None:
        html = _run(tmp_path, monkeypatch, ["hfe_compound_het"], [
            ("6", 26092913, "G", "A", "0/1", None),
            ("6", 26090951, "C", "G", "0/1", None),
        ])
        card = _card(html, "HFE")
        assert "Ambiguous" in card
        assert "would settle this" in card
        assert "C282Y / H63D" in card and "C282Y-H63D / wt" in card
        assert "phase set" not in card

    def test_an_indel_window_match_and_an_activity_score_are_labelled(self, tmp_path, monkeypatch) -> None:
        html = _run(tmp_path, monkeypatch, ["abo_phenotype", "fut2_secretor"], [
            ("9", 133255928, "C", "G", "0/1", None),
            ("9", 133255935, "G", "T", "0/1", None),
            ("9", 133257520, "G", "GC", "0/1", None),  # Ensembl's spelling of the 261 insertion
            ("19", 48703417, "G", "A", "1/1", None),   # se428 homozygous
            ("19", 48703374, "A", "T", "0/0", None),
        ])
        abo = _card(html, "ABO")
        assert "<strong>B</strong>" in abo
        assert "written at a nearby position" in abo
        fut2 = _card(html, "FUT2")
        assert "<strong>Non-secretor</strong>" in fut2
        assert "activity score 0.0" in fut2

    def test_no_phenotype_module_means_no_section(self, tmp_path) -> None:
        template = (Path(report_logic.__file__).parent / "templates" / "longevity_report.html.j2").read_text()
        assert "{% if phenotype_modules %}" in template
        assert report_logic.build_phenotype_report_data(None, tmp_path) == []
