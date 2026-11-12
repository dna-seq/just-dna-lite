"""`webui.vite_ssr` patches the vite.config.js Reflex actually generates.

The patch is what lets Node prerender (prod runs Node; crawlers need the HTML). It anchors on two
strings in Reflex's template, so these tests render that template from the installed Reflex rather
than from a copy: a Reflex upgrade that moves an anchor fails here, not in a production build.
"""

from __future__ import annotations

import pytest
from reflex_base.compiler.templates import vite_config_template

from webui.vite_ssr import bundle_mui_for_ssr


@pytest.fixture
def generated_config() -> str:
    return vite_config_template(
        base="/", hmr=False, force_full_reload=False, experimental_hmr=False, sourcemap=False
    )


def test_the_patch_adds_mui_to_the_ssr_bundle(generated_config: str) -> None:
    patched = bundle_mui_for_ssr(generated_config)

    assert "noExternal: [/^@mui\\//]" in patched
    plugins_at = patched.index("plugins: [")
    assert patched.index("justDnaSsrBundleMui()", plugins_at) < patched.index(
        "alwaysUseReactDomServerNode(),", plugins_at
    )
    assert patched.index("function justDnaSsrBundleMui()") < patched.index("export default defineConfig")


def test_the_patch_is_idempotent(generated_config: str) -> None:
    once = bundle_mui_for_ssr(generated_config)
    assert bundle_mui_for_ssr(once) == once


def test_a_template_without_the_anchors_fails_loudly() -> None:
    with pytest.raises(RuntimeError, match="cannot patch vite.config.js"):
        bundle_mui_for_ssr("export const nothing = 1;\n")
