"""
`pipelines registry org …` — organization management for the just-dna-registry (0.9.1).

Orgs are shared accounts that own namespaces through a role cascade: **owner > admin > member**.
Owners edit settings and set roles; admins add namespaces and members; members can publish to the
org's namespaces and read the member list. CLI-first — the web UI can layer on later.

Auth mirrors the bundled `registry` client: server via ``--url`` (or ``$REGISTRY_URL``), token via
``--token`` (or ``$REGISTRY_TOKEN``).
"""
from __future__ import annotations

import os
from typing import Optional

import typer
from dotenv import load_dotenv

from just_dna_registry import RegistryClient, RegistryError

load_dotenv()  # pick up REGISTRY_URL / REGISTRY_TOKEN from a local .env

app = typer.Typer(
    help="Organization management: create orgs, claim org namespaces, manage members and roles.",
    no_args_is_help=True,
)

_URL_ENV = "REGISTRY_URL"
_TOKEN_ENV = "REGISTRY_TOKEN"
_SKIP_VERSION_ENV = "REGISTRY_SKIP_VERSION_CHECK"

UrlOpt = typer.Option(None, "--url", help=f"Registry base URL (or ${_URL_ENV})")
TokenOpt = typer.Option(None, "--token", help=f"API key (or ${_TOKEN_ENV})")
RoleOpt = typer.Option("member", "--role", help="owner | admin | member")


def _client(url: Optional[str], token: Optional[str]) -> RegistryClient:
    base = url or os.getenv(_URL_ENV) or "http://127.0.0.1:8000"
    tok = token or os.getenv(_TOKEN_ENV)
    if not tok:
        raise typer.BadParameter(f"a token is required (pass --token or set ${_TOKEN_ENV})")
    timeout = float(os.getenv("REGISTRY_TIMEOUT", "600"))
    check_version = os.getenv(_SKIP_VERSION_ENV, "").strip().lower() not in ("1", "true", "yes")
    return RegistryClient(base, tok, timeout=timeout, check_version=check_version)


def _run(fn):
    """Execute a client call, printing a red error + exit(1) on RegistryError."""
    try:
        return fn()
    except RegistryError as e:
        typer.secho(f"✗ {e.status_code}: {e.detail}", fg=typer.colors.RED)
        raise typer.Exit(1)


def _print_members(members: list[dict]) -> None:
    if not members:
        typer.echo("  (no members)")
        return
    for m in members:
        typer.echo(f"  {m.get('account')}  [{m.get('role')}]")


@app.command("create")
def create_org(
    name: str = typer.Argument(..., help="Org handle (slug). You become its owner."),
    url: Optional[str] = UrlOpt,
    token: Optional[str] = TokenOpt,
) -> None:
    """Create an organization; the calling account becomes its owner."""
    with _client(url, token) as c:
        res = _run(lambda: c.create_org(name))
    typer.secho(f"✓ created org {res.get('name', name)} (you are owner)", fg=typer.colors.GREEN)


@app.command("namespace")
def create_org_namespace(
    org: str = typer.Argument(..., help="Org that will own the namespace"),
    namespace: str = typer.Argument(..., help="Namespace slug to claim for the org"),
    url: Optional[str] = UrlOpt,
    token: Optional[str] = TokenOpt,
) -> None:
    """Claim a namespace owned by the org (admin or owner)."""
    with _client(url, token) as c:
        _run(lambda: c.create_org_namespace(org, namespace))
    typer.secho(f"✓ {org} now owns namespace '{namespace}'", fg=typer.colors.GREEN)


@app.command("members")
def list_members(
    org: str = typer.Argument(..., help="Org to inspect"),
    url: Optional[str] = UrlOpt,
    token: Optional[str] = TokenOpt,
) -> None:
    """List an org's members and their roles."""
    with _client(url, token) as c:
        members = _run(lambda: c.org_members(org))
    typer.echo(f"{org} — {len(members)} member(s):")
    _print_members(members)


@app.command("add-member")
def add_member(
    org: str = typer.Argument(...),
    account: str = typer.Argument(..., help="Account handle to add"),
    role: str = RoleOpt,
    url: Optional[str] = UrlOpt,
    token: Optional[str] = TokenOpt,
) -> None:
    """Add (or re-role) an org member. Granting admin/owner requires owner."""
    with _client(url, token) as c:
        res = _run(lambda: c.add_org_member(org, account, role))
    typer.secho(f"✓ {account} is now '{role}' in {org}", fg=typer.colors.GREEN)
    _print_members(res.get("members", []))


@app.command("remove-member")
def remove_member(
    org: str = typer.Argument(...),
    member: str = typer.Argument(..., help="Account handle to remove"),
    url: Optional[str] = UrlOpt,
    token: Optional[str] = TokenOpt,
) -> None:
    """Remove an org member (admin+; removing an owner requires owner)."""
    with _client(url, token) as c:
        _run(lambda: c.remove_org_member(org, member))
    typer.secho(f"✓ removed {member} from {org}", fg=typer.colors.GREEN)


@app.command("set-role")
def set_role(
    org: str = typer.Argument(...),
    member: str = typer.Argument(...),
    role: str = typer.Argument(..., help="owner | admin | member"),
    url: Optional[str] = UrlOpt,
    token: Optional[str] = TokenOpt,
) -> None:
    """Change an org member's role (owner only)."""
    with _client(url, token) as c:
        _run(lambda: c.set_org_role(org, member, role))
    typer.secho(f"✓ {member} is now '{role}' in {org}", fg=typer.colors.GREEN)


@app.command("settings")
def update_settings(
    org: str = typer.Argument(...),
    display_name: Optional[str] = typer.Option(None, "--display-name", help='"" clears'),
    email: Optional[str] = typer.Option(None, "--email", help='"" clears'),
    avatar_url: Optional[str] = typer.Option(None, "--avatar-url", help='"" clears'),
    funding_url: Optional[str] = typer.Option(None, "--funding-url", help='"" clears'),
    url: Optional[str] = UrlOpt,
    token: Optional[str] = TokenOpt,
) -> None:
    """Edit an org's profile (owner only). Only the flags you pass are sent; "" clears a field."""
    fields = {
        "display_name": display_name, "email": email,
        "avatar_url": avatar_url, "funding_url": funding_url,
    }
    fields = {k: v for k, v in fields.items() if v is not None}
    if not fields:
        raise typer.BadParameter("pass at least one of --display-name/--email/--avatar-url/--funding-url")
    with _client(url, token) as c:
        _run(lambda: c.update_org_settings(org, **fields))
    typer.secho(f"✓ updated {org} settings: {', '.join(fields)}", fg=typer.colors.GREEN)
