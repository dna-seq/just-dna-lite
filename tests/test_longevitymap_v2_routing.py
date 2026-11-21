"""Longevity Map 2.0.0 keeps the name `longevitymap` but not Generation I's pathway categories.

The report's longevity section files rows under `LONGEVITY_CATEGORIES` only, so the re-curated module,
whose `category` is the system a locus acts through, must take the generic module section instead.
The categories are read from the committed spec (`data/modules/longevitymap_v2/variants.csv`), not
restated here.
"""

from pathlib import Path

import polars as pl
import pytest
from fsspec.implementations.local import LocalFileSystem
from just_dna_compiler.compiler import compile_module

from just_dna_pipelines.annotation.hf_modules import ModuleInfo, _probe_module_at_path
from just_dna_pipelines.annotation.report_logic import (
    LONGEVITY_CATEGORIES,
    are_longevity_pathways,
    uses_longevity_pathways,
)

SPEC = Path(__file__).resolve().parents[1] / "data" / "modules" / "longevitymap_v2"


def test_the_recurated_modules_categories_are_not_pathways() -> None:
    variants = pl.read_csv(SPEC / "variants.csv", infer_schema_length=0)
    categories = set(variants["category"].drop_nulls().to_list())
    assert categories, "the v2 spec names a category on its rows"
    # The premise the routing rests on: none of v2's categories is a Generation I pathway.
    assert categories.isdisjoint(LONGEVITY_CATEGORIES)
    assert are_longevity_pathways(categories) is False


def test_generation_one_categories_are_pathways() -> None:
    assert are_longevity_pathways(set(LONGEVITY_CATEGORIES)) is True
    assert are_longevity_pathways({"other"}) is True


def test_no_category_at_all_keeps_the_pathway_section() -> None:
    assert are_longevity_pathways(set()) is True


@pytest.mark.parametrize("extra", ["heart_vessels", "general_ageing"])
def test_one_category_outside_the_pathways_is_enough_to_leave(extra: str) -> None:
    assert are_longevity_pathways({sorted(LONGEVITY_CATEGORIES)[0], extra}) is False


# ---- uses_longevity_pathways on real module tables (the path every routing decision takes)


def _info_with_annotations(tmp_path: Path, annotations: pl.DataFrame | None) -> ModuleInfo:
    url = None
    if annotations is not None:
        path = tmp_path / "annotations.parquet"
        annotations.write_parquet(path)
        url = str(path)
    return ModuleInfo(name="longevitymap", repo_id=str(tmp_path), path=str(tmp_path), annotations_url=url)


def test_the_compiled_v2_module_takes_the_generic_section(tmp_path: Path) -> None:
    out = tmp_path / "longevitymap"
    result = compile_module(SPEC, out, resolve_with_ensembl=True, ensembl_cache=None)
    if not result.success:
        pytest.skip(f"the v2 spec did not compile on this machine: {result.errors[:1]}")
    info = _probe_module_at_path(LocalFileSystem(), str(out), "file", "longevitymap", str(out), str(out))
    assert info is not None and info.annotations_url is not None
    assert uses_longevity_pathways("longevitymap", info) is False


def test_an_annotations_table_of_generation_one_categories_keeps_the_pathway_section(tmp_path: Path) -> None:
    keys = sorted(LONGEVITY_CATEGORIES)
    annotations = pl.DataFrame({"rsid": [f"rs{i}" for i in range(len(keys) + 1)], "category": [*keys, None]})
    assert uses_longevity_pathways("longevitymap", _info_with_annotations(tmp_path, annotations)) is True


def test_an_annotations_table_without_category_keeps_the_pathway_section(tmp_path: Path) -> None:
    annotations = pl.DataFrame({"rsid": ["rs1"], "gene": ["APOE"]})
    assert uses_longevity_pathways("longevitymap", _info_with_annotations(tmp_path, annotations)) is True


def test_no_annotations_table_keeps_the_pathway_section(tmp_path: Path) -> None:
    assert uses_longevity_pathways("longevitymap", _info_with_annotations(tmp_path, None)) is True
