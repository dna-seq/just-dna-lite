"""Feature gates for UI surfaces that are hidden from users.

Each flag gates every entry point to a surface — nav tab, route registration,
in-page links and the crawler route table — so flipping one back to ``True``
restores the whole thing with no other edit.

Entry points check the surface through :func:`module_creator_available` /
:func:`registry_publication_available`, not the bare flags, so both authoring
surfaces stay hidden and unreachable in immutable (public demo) mode even when
a deployment turns the flag on.
"""

from __future__ import annotations

from just_dna_pipelines.module_config import is_immutable_mode

# AI Module Creator (``/modules``): the module-source manager and the agent chat
# that drafts modules. Hidden until the creator flow is ready for users.
MODULE_CREATOR_ENABLED: bool = False

# Publication tab on the Module Catalog page: namespace registration, claiming,
# publishing, yanking and amending. Browsing and installing stay available.
REGISTRY_PUBLICATION_ENABLED: bool = False


def module_creator_available() -> bool:
    """Whether the AI Module Creator surface may be exposed.

    Always ``False`` in immutable (public demo) mode, regardless of the flag: a
    public box must never show an authoring or file-upload surface, even if the
    flag is later flipped on. The backend upload guards in ``state.py`` are the
    second line of defence; this keeps the controls from rendering, the route
    from registering and the nav link from appearing at all.
    """
    return MODULE_CREATOR_ENABLED and not is_immutable_mode()


def registry_publication_available() -> bool:
    """Whether the registry Publication surface may be exposed.

    Same rule as :func:`module_creator_available`: off in immutable (public
    demo) mode even when the flag is on, because publishing from a public box
    is never wanted.
    """
    return REGISTRY_PUBLICATION_ENABLED and not is_immutable_mode()
