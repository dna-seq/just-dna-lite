"""
Smoke test for the Module Creator Agent.

Runs a REAL Gemini API call using the mthfr_nad eval input.
Requires GEMINI_API_KEY or GOOGLE_API_KEY in .env.

Usage:
    uv run pytest tests/test_agent_smoke.py -m integration
"""
import shutil
from pathlib import Path

import pytest

EVAL_INPUT = Path("data/module_specs/evals/mthfr_nad/freeform_input.md")
EVAL_REF_VARIANTS = Path("data/module_specs/evals/mthfr_nad/variants.csv")


@pytest.fixture
def agent_output_dir(tmp_path: Path) -> Path:
    out = tmp_path / "agent_output"
    out.mkdir()
    return out


@pytest.mark.integration
def test_agent_creates_valid_module(agent_output_dir: Path) -> None:
    """Agent reads freeform input, writes spec files, and validates them."""
    from just_dna_pipelines.agents.module_creator import create_module_agent

    assert EVAL_INPUT.exists(), f"Eval input not found: {EVAL_INPUT}"

    freeform_text = EVAL_INPUT.read_text(encoding="utf-8")

    agent = create_module_agent(spec_output_dir=agent_output_dir)

    message = (
        f"{freeform_text}\n\n"
        f"Write the spec files to: {agent_output_dir}/<module_name>/ "
        f"using the write_spec_files tool. "
        f"Then call validate_spec on the resulting directory."
    )

    response = agent.run(message)
    assert response is not None
    assert response.content, "Agent returned empty response"

    print(f"\n{'='*60}")
    print("AGENT RESPONSE:")
    print(f"{'='*60}")
    print(response.content[:2000])
    print(f"{'='*60}\n")

    # Check that spec files were actually written
    spec_dirs = [
        d for d in agent_output_dir.iterdir()
        if d.is_dir() and (d / "module_spec.yaml").exists()
    ]
    assert len(spec_dirs) >= 1, (
        f"Agent did not write any spec directories to {agent_output_dir}. "
        f"Contents: {list(agent_output_dir.iterdir())}"
    )

    spec_dir = spec_dirs[0]
    print(f"Spec dir: {spec_dir}")
    print(f"Files: {list(spec_dir.iterdir())}")

    assert (spec_dir / "module_spec.yaml").exists(), "module_spec.yaml not written"
    assert (spec_dir / "variants.csv").exists(), "variants.csv not written"

    # Validate the generated spec independently
    from just_dna_pipelines.module_registry import validate_module_spec

    result = validate_module_spec(spec_dir)
    print(f"Validation: valid={result.valid}")
    print(f"  errors={result.errors}")
    print(f"  warnings={result.warnings}")
    print(f"  stats={result.stats}")

    assert result.valid, f"Generated spec is invalid: {result.errors}"

    stats = result.stats or {}
    assert stats.get("variant_rows", 0) > 0, "No variant rows generated"
    assert stats.get("unique_rsids", 0) > 0, "No rsids generated"

    # Check that at least some of the expected rsids are present
    variants_text = (spec_dir / "variants.csv").read_text(encoding="utf-8")
    expected_rsids = ["rs1801133", "rs1801131", "rs4680"]
    found = [rs for rs in expected_rsids if rs in variants_text]
    print(f"Expected rsids found: {found} / {expected_rsids}")
    assert len(found) >= 2, (
        f"Agent missed key variants. Found {found} out of {expected_rsids}"
    )
