"""Every file-upload handler must refuse in immutable (public-demo) mode.

Immutable mode serves only pre-configured public genomes and must accept no user file uploads.
The guard was on the sample-upload handlers (`handle_upload`, `handle_upload_with_metadata`) and
`delete_file`, but the module-editor, AI-agent, module-import, avatar and logo upload handlers had
none — so a genome could be uploaded to a locked public demo through, e.g., the agent-chat
attachment. This is the structural regression test for the class: a state method that receives
`rx.UploadFile` must check immutable mode among its first statements, so a newly added upload
handler cannot silently reopen the hole. Pure AST over the source — no Reflex runtime needed.
"""

import ast
from pathlib import Path

STATE_PY = Path(__file__).resolve().parents[1] / "webui" / "src" / "webui" / "state.py"


def _upload_handlers(tree: ast.Module) -> list[ast.AsyncFunctionDef]:
    """Every async method whose signature takes an `rx.UploadFile` (the shape of an upload handler)."""
    handlers: list[ast.AsyncFunctionDef] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        for arg in node.args.args:
            if arg.annotation is not None and "UploadFile" in ast.unparse(arg.annotation):
                handlers.append(node)
                break
    return handlers


def _guards_immutable_mode(node: ast.AsyncFunctionDef) -> bool:
    """True if the handler references the immutable-mode check among its first few statements.

    A docstring is skipped; the guard must sit before the body does any work with the files.
    """
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]  # drop the docstring
    for stmt in body[:3]:
        for sub in ast.walk(stmt):
            if isinstance(sub, ast.Name) and sub.id == "_is_immutable_mode":
                return True
            if isinstance(sub, ast.Attribute) and sub.attr in ("is_immutable_mode", "_is_immutable_mode"):
                return True
    return False


def test_every_upload_handler_blocks_in_immutable_mode() -> None:
    tree = ast.parse(STATE_PY.read_text(encoding="utf-8"))
    handlers = _upload_handlers(tree)
    # Sanity: the known handlers are found, so the test is not silently matching nothing.
    names = {h.name for h in handlers}
    assert {"handle_upload", "upload_agent_file", "upload_import"} <= names, (
        f"upload-handler detection is mis-targeting; found {sorted(names)}"
    )
    unguarded = sorted(h.name for h in handlers if not _guards_immutable_mode(h))
    assert not unguarded, (
        "these upload handlers accept files with no immutable-mode guard, so a genome could be "
        f"uploaded to a public demo through them: {unguarded}"
    )
