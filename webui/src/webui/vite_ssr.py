"""Let Node prerender the app: bundle `@mui/*` into Vite's SSR build.

`@mui/x-data-grid` (reflex-mui-datagrid's grid) ships ESM that does ``import '../index.css'``. Vite
leaves ``node_modules`` external in the SSR bundle, so prerendering imports that file at runtime.
Bun resolves a ``.css`` import; Node's ESM loader refuses it (``ERR_UNKNOWN_FILE_EXTENSION``), the
server bundle fails to import, and every route prerenders as a 500 ("Prerender: Request failed
for /"), which stops the production build. Prod runs Node, and crawlers and link previews need the
prerendered HTML, so turning SSR off is not an answer.

Listing the packages in ``ssr.noExternal`` makes Vite bundle them into the server build, where its
CSS handling consumes the import. Only ``@mui/*`` is bundled: React and Emotion stay external, so
the server keeps one copy of each context.

Reflex has no setting for the SSR externals, so this is a Reflex plugin that patches the generated
``vite.config.js`` through ``add_modify_task``, the way Reflex's own ``EmbedPlugin`` adds a Vite
plugin. The upstream fix belongs in reflex-mui-datagrid, which knows its package imports CSS.
"""

from __future__ import annotations

from typing import Any

from reflex_base.constants.base import ReactRouter
from reflex_base.plugins.base import Plugin

_PLUGIN_NAME = "justDnaSsrBundleMui"
_PLUGIN_DEF = f"""
// just-dna-lite (webui.vite_ssr): bundle @mui/* into the SSR build so Node never imports its CSS.
function {_PLUGIN_NAME}() {{
  return {{
    name: "just-dna-ssr-bundle-mui",
    config() {{
      return {{ ssr: {{ noExternal: [/^@mui\\//] }} }};
    }},
  }};
}}
"""
_DEFINE_ANCHOR = "export default defineConfig"
_PLUGINS_ANCHOR = "alwaysUseReactDomServerNode(),"


def bundle_mui_for_ssr(content: str) -> str:
    """Add the SSR bundling plugin to a generated ``vite.config.js`` (idempotent).

    Raises:
        RuntimeError: If the Reflex template changed so the anchors are gone; a silent skip would
            bring back the Node prerender failure with no hint why.
    """
    if _PLUGIN_NAME in content:
        return content
    if _DEFINE_ANCHOR not in content or _PLUGINS_ANCHOR not in content:
        msg = (
            "webui.vite_ssr cannot patch vite.config.js: expected anchors "
            f"{_DEFINE_ANCHOR!r} and {_PLUGINS_ANCHOR!r} were not found. The Reflex Vite template "
            "changed; without this patch a Node prerender fails on @mui/x-data-grid's CSS import."
        )
        raise RuntimeError(msg)
    return content.replace(_DEFINE_ANCHOR, _PLUGIN_DEF + "\n" + _DEFINE_ANCHOR, 1).replace(
        _PLUGINS_ANCHOR, f"{_PLUGIN_NAME}(),\n    {_PLUGINS_ANCHOR}", 1
    )


class SsrBundleMuiPlugin(Plugin):
    """Register :func:`bundle_mui_for_ssr` on ``vite.config.js`` at every compile."""

    def pre_compile(self, **context: Any) -> None:
        """Queue the ``vite.config.js`` patch."""
        context["add_modify_task"](ReactRouter.VITE_CONFIG_FILE, bundle_mui_for_ssr)
