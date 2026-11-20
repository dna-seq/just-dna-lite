"""Sort orders for a sample's lists in the right panel (issues #19 and #20).

The annotation files and the reports each get a sort selector; the PRS results grid gets a
``computed_at`` column, which the grid sorts like any other column. The first option of each list
is the order the panel always used, so nothing moves until someone picks another.
"""

from datetime import datetime
from typing import Any

from reflex_mui_datagrid.models import ColumnDef

# (value, label) pairs, the default first.
OUTPUT_FILE_SORTS: list[tuple[str, str]] = [
    ("module", "Module"),
    ("name", "Name"),
    ("type", "File type"),
    ("newest", "Newest first"),
    ("oldest", "Oldest first"),
]
REPORT_FILE_SORTS: list[tuple[str, str]] = [
    ("newest", "Newest first"),
    ("oldest", "Oldest first"),
    ("name", "Name"),
]

COMPUTED_AT_FIELD = "computed_at"


def created_fields(mtime: float) -> dict[str, Any]:
    """The two date fields every listed file carries: a sortable number and its display text."""
    return {
        "created_ts": mtime,
        "created_at": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
    }


def sort_files(files: list[dict[str, Any]], order: str) -> list[dict[str, Any]]:
    """Return ``files`` in ``order`` (a value of OUTPUT_FILE_SORTS or REPORT_FILE_SORTS).

    Every order ends on the file name, so two files equal on the chosen key keep one order
    between reloads. An unknown order raises: the selector offers only known values.
    """
    by_name = lambda f: f["name"].casefold()  # noqa: E731
    if order == "module":
        return sorted(files, key=lambda f: (f["module"], f["type"], by_name(f)))
    if order == "name":
        return sorted(files, key=by_name)
    if order == "type":
        return sorted(files, key=lambda f: (f["type"], by_name(f)))
    if order == "newest":
        return sorted(files, key=lambda f: (-f["created_ts"], by_name(f)))
    if order == "oldest":
        return sorted(files, key=lambda f: (f["created_ts"], by_name(f)))
    raise ValueError(f"Unknown sort order {order!r}")


def computed_at_now() -> str:
    """The stamp a freshly computed PRS row carries; text in this form sorts by time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def with_computed_at_column(
    results: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    columns: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Add a "Computed" column to the PRS results grid prs-ui built.

    prs-ui builds row ``i`` from ``results[i]`` and gives it ``id = i``; the stamp is looked up by
    that id. A row restored from a checkpoint written before the stamp existed shows nothing.
    """
    stamped = [
        {**row, COMPUTED_AT_FIELD: results[row["id"]].get(COMPUTED_AT_FIELD) or ""}
        for row in rows
    ]
    column = ColumnDef(field=COMPUTED_AT_FIELD, header_name="Computed", min_width=150).dict()
    kept = [c for c in columns if c.get("field") != COMPUTED_AT_FIELD]
    return stamped, [*kept, column]
