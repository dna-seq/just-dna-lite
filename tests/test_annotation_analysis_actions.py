"""Focused state tests for the completed-analysis actions."""

from webui.state import UploadState


def _completed_state() -> UploadState:
    state = UploadState(_reflex_internal_init=True)
    state.selected_file = "sample.vcf.gz"
    state.safe_user_id = "anonymous"
    state.outputs_loaded_for_file = state.selected_file
    state.last_run_success = True
    state.runs = [
        {
            "run_id": "run-latest",
            "filename": state.selected_file,
            "modules": ["vo2max"],
            "status": "SUCCESS",
        }
    ]
    return state


def test_latest_run_output_targets_selected_module_parquet() -> None:
    state = _completed_state()
    state.output_files = [
        {
            "run_id": "run-latest",
            "module": "coronary",
            "type": "weights",
            "path": "/outputs/coronary_weights.parquet",
        },
        {
            "run_id": "run-latest",
            "module": "vo2max",
            "type": "weights",
            "path": "/outputs/vo2max_weights.parquet",
        },
    ]

    events = state.view_run_in_results("run-latest")

    assert state.right_panel_active_tab == "annotated_files"
    assert state.focused_output_path == "/outputs/vo2max_weights.parquet"
    assert state.latest_run_output_path == "/outputs/vo2max_weights.parquet"
    assert events is not None
    assert "view_output_file" in str(events[0])
    assert "/outputs/vo2max_weights.parquet" in str(events[0])


def test_latest_report_url_only_uses_latest_run_materialization() -> None:
    state = _completed_state()
    state.report_files = [
        {
            "run_id": "run-old",
            "sample_name": "sample",
            "name": "old_report.html",
        },
        {
            "run_id": "run-latest",
            "sample_name": "sample",
            "name": "latest_report.html",
        },
    ]

    assert state.last_run_success is True
    assert state.has_latest_report is True
    assert state.latest_report_url.endswith(
        "/api/report/anonymous/sample/latest_report.html"
    )


def test_latest_report_is_unavailable_for_reportless_run() -> None:
    state = _completed_state()
    state.report_files = [
        {
            "run_id": "run-old",
            "sample_name": "sample",
            "name": "old_report.html",
        }
    ]

    assert state.has_latest_report is False
    assert state.latest_report_url == ""


def test_changing_analysis_selection_resets_completed_actions() -> None:
    state = _completed_state()
    state.selected_modules = ["vo2max"]

    list(state.toggle_module("vo2max"))

    assert state.last_run_success is False
    assert state.selected_modules == []

    state.last_run_success = True
    state.toggle_ensembl()

    assert state.last_run_success is False
