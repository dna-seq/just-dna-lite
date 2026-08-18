"""
Pre-publish check of **every** built module against the live registry, in one run.

**For a single module, use the client directly** — since 0.11 it does this natively and is the
supported surface:

    uv run pipelines marketplace check    just-dna-seq <name> <spec_dir> --identifiers
    uv run pipelines marketplace validate just-dna-seq <name> <spec_dir> --pack

This script drives the same `RegistryClient` methods and exists only for what the CLI does not do:
sweep all ten modules in one command, pick `check` or `validate` per module, pack the oversized ones,
back off through the endpoint's rate limit instead of failing, and dump every report to JSON.

Usage::

    uv run python scripts/registry_precheck.py                    # every built module
    uv run python scripts/registry_precheck.py coronary pharmgkb  # a subset
    uv run python scripts/registry_precheck.py --json out.json

Reads `REGISTRY_URL` and `REGISTRY_TOKEN` from `.env` (the 0.11 client's own variables), falling back
to the pre-0.11 `MARKETPLACE_*` spellings. **The token must own the namespace being checked** — one
that does not gets `403 insufficient_capability`, which reads like a spec problem and is not. Verify
with `curl -H "Authorization: Bearer $REGISTRY_TOKEN" "$REGISTRY_URL/api/v1/auth/whoami"`.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from just_dna_pipelines.module_config import LEAD_TABLE_CSVS
from just_dna_registry.client import RegistryClient, RegistryError

DEFAULT_URL = "https://module-registry.just-dna.life"
NAMESPACE = "just-dna-seq"
OUT_ROOT = Path("data/interim/v1_port")

#: The server's ceiling on the *enrichment* half of `/check` (`REGISTRY_ENRICH_MAX_VARIANTS`). Past
#: it the endpoint answers `422 too_many_variants` — the ClinVar panels are 57k–306k variants, so
#: they go to `/validate`, which has no network tier and is the half that decides publishability.
ENRICH_MAX_VARIANTS = 500

#: Raw bytes past which the spec is packed into one archive rather than sent as loose parts. The
#: server bounds the wire at 25 MiB; before client/server 0.11.1 there was no archive form on
#: `/validate` or `/check` at all, so a panel could be published but never rehearsed.
PACK_ABOVE_BYTES = 20 * 1024 * 1024

#: `/check` is the service's most expensive endpoint and is rate-limited per account, so a
#: back-to-back sweep hits `429`. A 429 means "not yet", not "would not publish".
RETRY_DELAYS = (30, 60, 120, 240)


def _authored_row_count(module_dir: Path) -> int:
    """Rows in whichever table leads the module — what the enrichment limit counts."""
    # Imported, not restated: the hand-kept copy named four of the ten families, so a module led by
    # any other one counted zero rows and was always routed to the enrichment half of `/check`.
    for table in LEAD_TABLE_CSVS:
        path = module_dir / table
        if path.exists():
            with path.open(encoding="utf-8") as handle:
                return max(sum(1 for _ in handle) - 1, 0)
    return 0


def _spec_bytes(module_dir: Path) -> int:
    return sum(
        f.stat().st_size
        for pattern in ("module_spec.yaml", "*.csv", "*.log")
        for f in module_dir.glob(pattern)
        if f.is_file()
    )


def _with_backoff(call, label: str) -> Any:
    """Run `call`, retrying only on the rate limiter."""
    for attempt, delay in enumerate((*RETRY_DELAYS, None)):
        try:
            return call()
        except RegistryError as exc:
            rate_limited = exc.status_code == 429
            if not (rate_limited and delay is not None):
                raise
            print(f"    {label}: rate limited; retrying in {delay}s "
                  f"(attempt {attempt + 1})", flush=True)
            time.sleep(delay)
    raise RuntimeError("unreachable")


def summarize(name: str, report: Any, endpoint: str) -> str:
    """One block per module: the verdict, the counts, and the findings worth acting on."""
    validation = getattr(report, "validation", report)
    verdict = (
        f"would_publish={report.would_publish}"
        if endpoint == "check"
        else f"valid={validation.valid}"
    )
    lines = [f"  {name}: {verdict}"]
    stats = getattr(validation, "stats", None)
    if stats is not None:
        lines.append(
            f"    variants={stats.variant_count:,} studies={stats.study_count:,} "
            f"genes={stats.gene_count:,}"
        )
    for level in ("errors", "warnings"):
        entries = getattr(validation, level, []) or []
        for entry in entries[:5]:
            lines.append(f"    {level[:-1]}: {entry[:200]}")
        if len(entries) > 5:
            lines.append(f"    … and {len(entries) - 5} more {level}")
    return "\n".join(lines)


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modules", nargs="*", help="Module names. Default: every built module.")
    parser.add_argument(
        "--url", default=os.getenv("REGISTRY_URL") or os.getenv("MARKETPLACE_URL") or DEFAULT_URL
    )
    parser.add_argument("--namespace", default=NAMESPACE)
    parser.add_argument("--out-root", type=Path, default=OUT_ROOT)
    parser.add_argument(
        "--offline", action="store_true", help="Validation tier only (skip the network passes)."
    )
    parser.add_argument(
        "--online-all", action="store_true",
        help="Force /check even for a module over the enrichment limit (it will 422).",
    )
    parser.add_argument("--json", type=Path, help="Write the full reports here.")
    parser.add_argument(
        "--token",
        default=os.getenv("REGISTRY_TOKEN") or os.getenv("MARKETPLACE_TOKEN"),
        help="API key owning the namespace. Default: $REGISTRY_TOKEN, else $MARKETPLACE_TOKEN.",
    )
    args = parser.parse_args()

    if not args.token:
        print("no API key found — set REGISTRY_TOKEN in .env (or pass --token).")
        return 2

    names = args.modules or sorted(
        d.name for d in args.out_root.iterdir() if d.is_dir() and not d.name.startswith("_")
    )
    client = RegistryClient(args.url, token=args.token)

    reports: dict[str, Any] = {}
    failures = 0
    # A 429 is not a verdict. `/check` is rate-limited per account and a ten-module sweep outruns
    # the backoff, so these are counted apart from modules the server actually rejected — folding
    # them into "would not publish" would report a content failure that did not happen.
    rate_limited: list[str] = []
    for name in names:
        module_dir = args.out_root / name
        if not (module_dir / "module_spec.yaml").exists():
            print(f"  {name}: skipped — no module_spec.yaml in {module_dir}")
            continue

        variant_count = _authored_row_count(module_dir)
        too_many = variant_count > ENRICH_MAX_VARIANTS and not args.online_all
        endpoint = "validate" if (args.offline or too_many) else "check"
        pack = _spec_bytes(module_dir) > PACK_ABOVE_BYTES
        note = f" [{endpoint}{', packed' if pack else ''}]"
        print(f"→ {name}: {variant_count:,} authored rows{note}", flush=True)

        try:
            if endpoint == "check":
                report = _with_backoff(
                    lambda: client.check(
                        args.namespace, name, module_dir,
                        strict=True, literature=True, identifiers=True, pack=pack,
                    ),
                    name,
                )
            else:
                report = _with_backoff(
                    lambda: client.validate(
                        args.namespace, name, module_dir, strict=True, pack=pack
                    ),
                    name,
                )
        except RegistryError as exc:
            print(f"  {name}: HTTP {exc.status_code} — {str(exc.detail)[:300]}")
            reports[name] = {"http_error": exc.status_code, "detail": str(exc.detail)}
            if exc.status_code == 429:
                rate_limited.append(name)
            else:
                failures += 1
            continue

        reports[name] = report.model_dump(mode="json")
        print(summarize(name, report, endpoint), flush=True)
        ok = report.would_publish if endpoint == "check" else report.valid
        if not ok:
            failures += 1

    if args.json:
        args.json.write_text(json.dumps(reports, indent=2), encoding="utf-8")
        print(f"\nfull reports → {args.json}")
    checked = len(reports) - len(rate_limited)
    print(f"\n{checked - failures}/{checked} module(s) checked would publish.")
    if rate_limited:
        print(
            f"{len(rate_limited)} not checked — rate limited after every retry: "
            f"{', '.join(rate_limited)}. Re-run just those; it is not a verdict."
        )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
