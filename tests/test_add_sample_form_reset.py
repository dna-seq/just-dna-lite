"""Add Sample form must return to defaults after a successful upload."""

from __future__ import annotations

import pytest
import reflex as rx

from webui.state import AgentState, UploadState


@pytest.mark.parametrize(
    ("state_cls", "key"),
    [(UploadState, "form_key"), (AgentState, "agent_input_key")],
)
def test_remount_keys_are_frontend_vars(state_cls: type[rx.State], key: str) -> None:
    """A leading underscore would hide the remount token from the client.

    Uncontrolled inputs (default_value) only clear when React remounts them.
    ``_form_key`` was backend-only, so the typed Subject ID / Study name stayed
    visible after upload; ``_agent_input_key`` left the module-creator prompt in
    place the same way. ``base_vars`` holds exactly what reaches the client.
    """
    assert key in state_cls.base_vars
    assert f"_{key}" not in state_cls.get_fields()


def test_base_vars_exclude_backend_vars() -> None:
    """Control for the test above: a declared ``_`` var is a field, not a base var."""
    assert "_inproc_discover_partition" in UploadState.get_fields()
    assert "_inproc_discover_partition" not in UploadState.base_vars


def test_reset_new_sample_form_restores_defaults_and_bumps_key() -> None:
    """Would have left filled fields in place when the remount key was private."""
    state = UploadState()
    state.new_sample_subject_id = "Alice"
    state.new_sample_sex = "Female"
    state.new_sample_tissue = "Blood"
    state.new_sample_species = "Mus musculus"
    state.new_sample_reference_genome = "GRCm39"
    state.new_sample_study_name = "Pilot"
    state.new_sample_notes = "keep me out of the next upload"
    previous_key = state.form_key

    state._reset_new_sample_form()

    assert state.new_sample_subject_id == ""
    assert state.new_sample_sex == "N/A"
    assert state.new_sample_tissue == "Sample tissue"
    assert state.new_sample_species == "Homo sapiens"
    assert state.new_sample_reference_genome == "GRCh38"
    assert state.new_sample_study_name == ""
    assert state.new_sample_notes == ""
    assert state.form_key == previous_key + 1
