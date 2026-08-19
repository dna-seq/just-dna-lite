"""Output-preview interaction tests."""

from pathlib import Path

from reflex.event import EventSpec
from webui.pages.annotate import _output_preview_grid
from webui.state import OutputPreviewState, UploadState


def test_view_output_file_expands_preview_before_loading(tmp_path: Path) -> None:
    preview_file = tmp_path / "preview.csv"
    preview_file.write_text("value\n1\n")
    state = OutputPreviewState(_reflex_internal_init=True)

    events = state.view_output_file(str(preview_file))

    assert next(events) is None
    assert state.output_preview_expanded is True
    assert state.output_preview_loading is True

    events.close()


def test_preview_output_file_moves_selection_and_scrolls_to_heading() -> None:
    state = UploadState(_reflex_internal_init=True)

    events = state.preview_output_file("/outputs/another.parquet")

    assert state.focused_output_path == "/outputs/another.parquet"
    assert len(events) == 2
    assert all(isinstance(event, EventSpec) for event in events)
    assert "view_output_file" in str(events[0])
    assert "output-preview-heading" in str(events[1])
    assert "scrollIntoView" in str(events[1])
    assert "block: 'start'" in str(events[1])


def test_output_preview_heading_has_scroll_anchor() -> None:
    rendered_preview = str(_output_preview_grid())

    assert "output-preview-heading" in rendered_preview
    assert "scrollMarginTop" in rendered_preview
    assert "50px" in rendered_preview
