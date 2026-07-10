"""Crawler-facing metadata and static asset generation for the Reflex app."""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from webui.deployment_urls import resolve_public_app_url

SITE_TITLE = "Just DNA Lite"
SITE_DESCRIPTION = (
    "A local-first bioinformatics tool for exploring and annotating your own genome data."
)
GITHUB_URL = "https://github.com/dna-seq/just-dna-lite"
OG_PREVIEW_SIZE = (1200, 630)
OG_PREVIEW_URL_PATH = "/images/og-preview.jpg"
OG_PREVIEW_VERSION = 1

_PACKAGE_DIR = Path(__file__).resolve().parents[2]
_ASSETS_DIR = _PACKAGE_DIR / "assets"


@dataclass(frozen=True)
class RouteMetadata:
    """Static route metadata that can be rendered before Reflex hydration."""

    path: str
    title: str
    description: str
    priority: str
    changefreq: str = "weekly"
    robots: str = "index, follow"


PUBLIC_ROUTES: tuple[RouteMetadata, ...] = (
    RouteMetadata(
        path="/",
        title="Personal Genome Annotation",
        description=SITE_DESCRIPTION,
        priority="1.0",
    ),
    RouteMetadata(
        path="/annotate",
        title="Annotate",
        description="Upload a GRCh38 VCF, select annotation modules, and inspect generated outputs.",
        priority="0.9",
    ),
    RouteMetadata(
        path="/modules",
        title="Module Creator",
        description="Create and manage annotation modules, including AI-assisted module drafts.",
        priority="0.8",
    ),
    RouteMetadata(
        path="/marketplace",
        title="Module Catalog",
        description="Browse, install, and manage annotation modules from the shared module catalog (free).",
        priority="0.8",
    ),
    RouteMetadata(
        path="/faq",
        title="FAQ",
        description="Answers about privacy, supported genome files, public demo mode, and responsible use.",
        priority="0.8",
    ),
    RouteMetadata(
        path="/analysis",
        title="Analysis",
        description="Explore reports, variant outputs, and interpretation workflows.",
        priority="0.6",
    ),
    RouteMetadata(
        path="/dashboard",
        title="Dashboard",
        description="A high-level dashboard for the local genomic analysis stack.",
        priority="0.5",
    ),
)

ROBOT_EXCLUDED_PATHS = ("/_event/", "/ping")


def _route_metadata(path: str) -> RouteMetadata:
    for route in PUBLIC_ROUTES:
        if route.path == path:
            return route
    raise ValueError(f"Unknown public route: {path}")


def _route_url(path: str) -> str:
    base = resolve_public_app_url()
    return f"{base}/" if path == "/" else f"{base}{path}"


def page_image_url() -> str:
    """Return the absolute URL for the shared site-wide preview image."""

    return f"{resolve_public_app_url()}{OG_PREVIEW_URL_PATH}?v={OG_PREVIEW_VERSION}"


def page_meta(path: str) -> list[dict[str, str]]:
    """Build static OG/Twitter metadata for a public page."""

    route = _route_metadata(path)
    title = SITE_TITLE if path == "/" else f"{route.title} | {SITE_TITLE}"
    image = page_image_url()
    url = _route_url(path)
    return [
        {"name": "robots", "content": route.robots},
        {"name": "description", "content": route.description},
        {"property": "og:type", "content": "website"},
        {"property": "og:site_name", "content": SITE_TITLE},
        {"property": "og:title", "content": title},
        {"property": "og:description", "content": route.description},
        {"property": "og:url", "content": url},
        {"property": "og:image", "content": image},
        {"property": "og:image:type", "content": "image/jpeg"},
        {"property": "og:image:width", "content": str(OG_PREVIEW_SIZE[0])},
        {"property": "og:image:height", "content": str(OG_PREVIEW_SIZE[1])},
        {"property": "og:image:alt", "content": "Just DNA Lite genome annotation interface."},
        {"name": "twitter:card", "content": "summary_large_image"},
        {"name": "twitter:title", "content": title},
        {"name": "twitter:description", "content": route.description},
        {"name": "twitter:image", "content": image},
        {"name": "twitter:image:alt", "content": "Just DNA Lite genome annotation interface."},
    ]


def build_robots_txt() -> str:
    """Build robots.txt with canonical sitemap references."""

    disallow_lines = "\n".join(f"Disallow: {path}" for path in ROBOT_EXCLUDED_PATHS)
    base = resolve_public_app_url()
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Allow: /llms.txt\n"
        f"{disallow_lines}\n\n"
        f"Sitemap: {base}/sitemap.xml\n"
        f"# LLM-readable overview: {base}/llms.txt\n"
    )


def build_sitemap_xml() -> str:
    """Build a canonical sitemap from the static public route table."""

    lastmod = date.today().isoformat()
    entries = []
    for route in PUBLIC_ROUTES:
        entries.append(
            "  <url>\n"
            f"    <loc>{html.escape(_route_url(route.path))}</loc>\n"
            f"    <lastmod>{lastmod}</lastmod>\n"
            f"    <changefreq>{route.changefreq}</changefreq>\n"
            f"    <priority>{route.priority}</priority>\n"
            "  </url>"
        )
    joined = "\n".join(entries)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{joined}\n"
        "</urlset>\n"
    )


def build_llms_txt() -> str:
    """Build a concise LLM-readable overview for crawlers and assistants."""

    base = resolve_public_app_url()
    route_lines = "\n".join(
        f"- {_route_url(route.path)}: {route.description}" for route in PUBLIC_ROUTES
    )
    excluded = ", ".join(ROBOT_EXCLUDED_PATHS)
    return (
        "# Just DNA Lite\n\n"
        f"> {SITE_DESCRIPTION}\n\n"
        "Just DNA Lite is a research-use bioinformatics tool for joining a user's GRCh38 VCF "
        "against annotation modules, Ensembl annotations, and polygenic risk score resources. "
        "It is not a medical device and does not provide medical advice.\n\n"
        "## Public Routes\n\n"
        f"{route_lines}\n\n"
        "## Crawl Guidance\n\n"
        "Route HTML includes default crawler metadata before Reflex WebSocket hydration. "
        f"Do not index internal Reflex endpoints: {excluded}.\n\n"
        "## Links\n\n"
        f"- Site: {base}\n"
        f"- Source: {GITHUB_URL}\n"
    )


def generate_crawler_assets() -> None:
    """Write crawler files using the current canonical URL.

    The site-wide OG preview image is intentionally not generated here. Place it
    at ``webui/assets/images/og-preview.jpg`` so deployments control the exact
    raster that social crawlers fetch.
    """

    _ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    (_ASSETS_DIR / "robots.txt").write_text(build_robots_txt(), encoding="utf-8")
    (_ASSETS_DIR / "sitemap.xml").write_text(build_sitemap_xml(), encoding="utf-8")
    (_ASSETS_DIR / "llms.txt").write_text(build_llms_txt(), encoding="utf-8")
    print(
        f"Generated crawler assets for {resolve_public_app_url()} in {_ASSETS_DIR}",
        flush=True,
    )
