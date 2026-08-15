"""Feature gates for UI surfaces that are hidden from users.

Each flag gates every entry point to a surface — nav tab, route registration,
in-page links and the crawler route table — so flipping one back to ``True``
restores the whole thing with no other edit.
"""

from __future__ import annotations

# AI Module Creator (``/modules``): the module-source manager and the agent chat
# that drafts modules. Hidden until the creator flow is ready for users.
MODULE_CREATOR_ENABLED: bool = False

# Publication tab on the Module Catalog page: namespace registration, claiming,
# publishing, yanking and amending. Browsing and installing stay available.
REGISTRY_PUBLICATION_ENABLED: bool = False
