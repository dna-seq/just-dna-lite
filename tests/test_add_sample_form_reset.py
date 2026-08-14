"""Add Sample form must return to defaults after a successful upload."""

from __future__ import annotations

from reflex_base.utils.types import is_backend_base_variable

from webui.state import UploadState


def test_form_key_is_a_frontend_var() -> None:
    """A leading underscore would hide the remount token from the client.

    Uncontrolled inputs (default_value) only clear when React remounts them.
    ``_form_key`` is backend-only, so the typed Subject ID / Study name stayed
    visible after upload. ``form_key`` must be in ``base_vars``.
    """
    assert "form_key" in UploadState.base_vars
    assert "form_key" not in UploadState.backend_vars
    assert "_form_key" not in UploadState.base_vars
    assert not is_backend_base_variable("form_key", UploadState)
    assert is_backend_base_variable("_form_key", UploadState)


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
