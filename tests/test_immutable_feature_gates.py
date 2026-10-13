"""The authoring surfaces stay hidden in immutable (public-demo) mode.

The AI Module Creator (`/modules`) and the registry Publication tab are hidden by feature flags
(`MODULE_CREATOR_ENABLED`, `REGISTRY_PUBLICATION_ENABLED`). Those flags are an editor convenience:
a deployment can turn one on. But a public-demo box must never expose a write/authoring surface,
and the backend upload guards (`test_immutable_upload_guards.py`) are only the second line — the
controls, route, nav link and crawler entry must not render at all.

So every entry point resolves availability through `module_creator_available()` /
`registry_publication_available()`, which fold immutable mode into the flag, and never the bare
flag. These tests pin both halves: the helpers go dark in immutable mode even with the flag on, and
no entry point outside `features.py` reaches for the bare flag (which would bypass immutable mode).
"""

import ast
from pathlib import Path

import webui.features as features

WEBUI_SRC = Path(features.__file__).resolve().parent
BARE_FLAGS = {"MODULE_CREATOR_ENABLED", "REGISTRY_PUBLICATION_ENABLED"}


def test_helpers_go_dark_in_immutable_mode_even_with_the_flag_on(monkeypatch) -> None:
    for helper, flag in (
        (features.module_creator_available, "MODULE_CREATOR_ENABLED"),
        (features.registry_publication_available, "REGISTRY_PUBLICATION_ENABLED"),
    ):
        # Flag on, normal mode: the surface is available.
        monkeypatch.setattr(features, flag, True)
        monkeypatch.setattr(features, "is_immutable_mode", lambda: False)
        assert helper() is True, f"{helper.__name__} should be available with the flag on in normal mode"

        # Flag on, immutable mode: the surface stays hidden regardless. This is the guard.
        monkeypatch.setattr(features, "is_immutable_mode", lambda: True)
        assert helper() is False, (
            f"{helper.__name__} exposed an authoring surface in immutable (public demo) mode; "
            "a public box must never render it even with the flag on"
        )

        # Flag off: hidden in either mode.
        monkeypatch.setattr(features, flag, False)
        monkeypatch.setattr(features, "is_immutable_mode", lambda: False)
        assert helper() is False, f"{helper.__name__} should stay hidden with the flag off"


def test_no_entry_point_reaches_for_the_bare_feature_flag() -> None:
    """Only features.py may name the raw flags; every surface gate goes through the helpers.

    A new nav link / route / tab gated on the bare flag would render in immutable mode, reopening
    the hole. AST over the source so a string mention (e.g. in a docstring) does not trip it.
    """
    offenders: dict[str, list[str]] = {}
    for path in WEBUI_SRC.rglob("*.py"):
        if path.name == "features.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        used = sorted(
            {
                node.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Name) and node.id in BARE_FLAGS
            }
        )
        if used:
            offenders[str(path.relative_to(WEBUI_SRC))] = used
    assert not offenders, (
        "these modules gate on the bare feature flag instead of module_creator_available() / "
        f"registry_publication_available(), so they ignore immutable mode: {offenders}"
    )
