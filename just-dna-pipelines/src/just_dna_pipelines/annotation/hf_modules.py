"""
Annotator Modules - Dynamic discovery and utilities.

Discovers available annotation modules by scanning configured sources
(HuggingFace, GitHub, HTTP, S3, or any fsspec-compatible URL) at startup.
Sources are configured in modules.yaml (see module_config.py).
"""

import re
from enum import Enum
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Optional

import polars as pl
from eliot import log_message
from just_dna_format.manifest import ModuleManifest, read_manifest
from pydantic import BaseModel, model_validator

from just_dna_pipelines.annotation.module_cache import (
    invalidate_module_cache_on_version_change,
)
from just_dna_pipelines.module_config import (
    DEFAULT_REPOS,
    LEAD_TABLES,
    MODULES_CONFIG,
    Source,
    spec_version,
)


# Backward-compatible aliases sourced from modules.yaml
HF_DEFAULT_REPOS: list[str] = DEFAULT_REPOS
HF_REPO_ID: str = HF_DEFAULT_REPOS[0] if HF_DEFAULT_REPOS else ""

# Tables available in each module
MODULE_TABLES = ["annotations", "studies", "weights", "sources"]


class ModuleInfo(BaseModel):
    """Information about a discovered annotation module.

    Discovery used to probe for `weights.parquet` alone, which made a pharmacogenomics module
    (pharm_variants-led) undiscoverable, and therefore unpublishable to HuggingFace at all. A
    module's *lead table* is whichever family in `LEAD_TABLES` it actually carries; read `lead_url`
    unless you specifically need weights.
    """
    name: str
    repo_id: str  # HF repo ID or source URL
    source_url: str = ""  # Original source URL from config
    path: str  # Base path for the module data
    # Which 0.4 table family carries this module's rows, and where it lives. For the common
    # weights-led module these are "weights" and the same URL as `weights_url`.
    lead_table: str = "weights"
    lead_url: str = ""
    # None for a module led by a 0.4 table. Read `lead_url` unless you specifically need weights.
    weights_url: Optional[str] = None
    annotations_url: Optional[str] = None
    studies_url: Optional[str] = None
    # Licensing provenance for the data this module redistributes. Every module the compiler emits
    # carries one, and a report that embeds a module's curated prose owes its attribution — so this
    # is discovered rather than left to a consumer that happens to know the file is there.
    sources_url: Optional[str] = None
    logo_url: Optional[str] = None
    metadata_url: Optional[str] = None
    # What the source's own `manifest.json` states about these bytes, when it publishes one.
    #
    # Discovery already fetches and validates that manifest — `_attested_files` needs
    # `artifact.files` to decide which tables the module really has — and used to discard the rest
    # of it three lines later. `read_module_provenance` then answered `(None, None, None)` for
    # every remotely-discovered module, so a report rendered *Not stated* for data we had held in
    # memory and thrown away. Keeping these three costs nothing beyond the read already paid for.
    #
    # **All three stay tri-state.** `None` means the source did not state it — a module published
    # under 0.3 carries no manifest at all — and never "unversioned", "unverified" or "these
    # weights are comparable to another module's". A local install still answers from the manifest
    # on disk, which is the richer path; these are the remote fallback.
    manifest_version: Optional[str] = None
    manifest_digest: Optional[str] = None
    manifest_weighting: Optional[str] = None

    @model_validator(mode="after")
    def _default_lead_to_weights(self) -> "ModuleInfo":
        """A ModuleInfo built with only `weights_url` is weights-led.

        Callers predating the lead-table concept construct ModuleInfo directly, and so does anything
        deserializing a stored one. Without this they would get an empty `lead_url` and read nothing.
        """
        if not self.lead_url and self.weights_url:
            self.lead_url = self.weights_url
        return self


def _get_hf_filesystem() -> "HfFileSystem":
    """Create an HfFileSystem with optional token."""
    from huggingface_hub import HfFileSystem, get_token
    token = get_token()
    return HfFileSystem(token=token)


def _get_fsspec_filesystem(protocol: str, url: str) -> "AbstractFileSystem":
    """Create an fsspec filesystem for the given protocol."""
    import fsspec
    if protocol in ("http", "https"):
        return fsspec.filesystem("http")
    if protocol == "github":
        # github://org/repo -> extract org and repo
        path_part = url.split("://", 1)[1] if "://" in url else url
        parts = path_part.strip("/").split("/")
        if len(parts) >= 2:
            return fsspec.filesystem("github", org=parts[0], repo=parts[1])
        raise ValueError(f"Invalid GitHub URL: {url}")
    return fsspec.filesystem(protocol)


def _build_url(protocol: str, path: str) -> str:
    """Build a full URL from protocol and path.

    **A local path is returned bare, never as a `file:` URI.** `f"file://{path}"` is only
    accidentally correct: on POSIX the path opens with `/`, so the result is `file:///data/…` —
    three slashes, an empty authority. On Windows it opens with a drive letter, so the result is
    `file://C:/Users/…` and `C:` is parsed as the URI *hostname*, which the object_store crate
    behind `pl.scan_parquet` rejects outright::

        failed to create CloudLocation: unsupported: non-empty hostname for 'file:' URI: 'C:'

    That made every locally-registered module (a registry install or a local compile — the
    registered-modules dir is a bare absolute path in `modules.yaml`) unannotatable on Windows,
    while discovery still found and listed it, so the run went green with the module silently
    missing from the report. Polars reads a native path on both platforms, and the rest of this
    repo already assumes a local module's URL is bare — see `local_module_dir`.
    """
    if protocol == "hf":
        return f"hf://{path}"
    if protocol in ("http", "https"):
        return path  # Already a full URL
    if protocol == "file":
        return path  # Native path: `file://` + a drive letter is not a valid URI
    return f"{protocol}://{path}"


#: The manifest, when a source publishes one, is the authority on what the module *contains*.
_MANIFEST_NAME: str = "manifest.json"


def _remote_manifest(fs: "AbstractFileSystem", base_path: str) -> Optional["ModuleManifest"]:
    """The source's validated `manifest.json`, or `None` when it publishes none / an unreadable one.

    Split out of `_attested_files` so the whole manifest survives the read. Discovery has always
    paid for this fetch and parse — `artifact.files` is what decides the module's *kind* — and then
    kept one field. Everything else it states about the module (`identity.version`,
    `artifact.digest`, the `weighting` block) was fetched and dropped, which is why every
    HF-discovered module reported no provenance at all.

    A manifest we cannot read must not make a real module undiscoverable, so a failure falls back
    to probing — the path every pre-0.6 module takes anyway — and says so rather than degrading
    silently.
    """
    manifest_path = f"{base_path}/{_MANIFEST_NAME}"
    if not fs.exists(manifest_path):
        return None
    try:
        raw = fs.cat_file(manifest_path)
        return ModuleManifest.model_validate_json(raw)
    except Exception as exc:
        log_message(
            message_type="warning",
            action="unreadable_remote_manifest",
            path=manifest_path,
            reason=str(exc),
        )
        return None


def _attested_names(manifest: Optional["ModuleManifest"]) -> Optional[frozenset[str]]:
    """The parquet basenames a manifest attests, or `None` when there is no manifest.

    `None` rather than an empty set, for the reason `_attested_files` gives: an empty set would read
    as "this module contains nothing", and every module on HuggingFace today has no manifest.
    """
    if manifest is None:
        return None
    return frozenset(
        Path(entry.name).name for entry in (manifest.artifact.files if manifest.artifact else [])
    )


def _attested_files(fs: "AbstractFileSystem", base_path: str) -> Optional[frozenset[str]]:
    """The parquet basenames `manifest.json` attests, or `None` when the source publishes no manifest.

    **This is the list `artifact.digest` is computed over, so it is what the module *is*** — and the
    difference from listing the directory is not cosmetic (just-dna-format INTEGRATION_0_6 § 2.8, the
    one change that document asks a consumer to make rather than making upstream).

    The publisher's `upload_folder` **adds and replaces but never removes**. So a module whose table
    set *shrank* between releases — a SNP-core module re-authored as a table-only PGx module — leaves
    the previous release's `weights.parquet` sitting at the path beside a manifest that does not
    attest it. A probe for named files still finds a SNP core: the old release's. Nothing is
    mis-hashed and verification would pass; the module is mis-**typed**, and on the discovery path,
    which fetches no manifest, a fossil is indistinguishable from a live table. Reading the attested
    list closes that for every module including the ones already published, which no publisher-side
    fix can reach.

    `None` (rather than an empty set) is what keeps this safe to adopt now: every module on
    HuggingFace today was published under 0.3 and carries no manifest at all, so the caller falls
    back to probing. An empty set would read as "this module contains nothing".

    Cost is one `fs.exists` plus, at most, one small read per module directory.

    Kept as the named predicate for callers that want only the file list; `_remote_manifest` is the
    one that reads, and `_probe_module_at_path` goes through it so the rest of the manifest is not
    discarded.
    """
    return _attested_names(_remote_manifest(fs, base_path))


def _find_lead_table(
    fs: "AbstractFileSystem", base_path: str, attested: Optional[frozenset[str]] = None
) -> Optional[str]:
    """Return the name of the table family leading this directory, or None if it is not a module.

    When the module publishes a manifest, the answer comes from `artifact.files` — see
    `_attested_files` for why a leftover parquet from an earlier release would otherwise decide the
    module's *kind*. Otherwise it probes, which is the pre-0.6 path.
    """
    for table in LEAD_TABLES:
        name = f"{table}.parquet"
        if attested is not None:
            if name in attested:
                return table
            continue
        if fs.exists(f"{base_path}/{name}"):
            return table
    return None


# Defined here rather than beside `read_module_provenance`, its other caller: discovery runs at
# import time (`MODULE_INFOS = discover_hf_modules()` below) and `_probe_module_at_path` calls
# this, so a definition further down the file is not yet bound. The symptom is not an ImportError
# — `discover_modules_from_source` catches it — but every source failing with
# "name '_weighting_summary' is not defined" and discovery returning nothing.
def _weighting_summary(manifest: "ModuleManifest") -> Optional[str]:
    """The module's `weighting` block as one line of its author's own words, or `None`.

    All three fields are free text on purpose (a closed vocabulary would have had to be guessed at),
    so they are rendered verbatim and never parsed. `None` when the block is absent **or** when every
    field in it is empty: an empty block establishes nothing, and rendering it as a present statement
    would be worse than rendering nothing.
    """
    block = getattr(manifest, "weighting", None)
    if block is None:
        return None
    parts = [
        f"{label}: {value.strip()}"
        for label, value in (
            ("scale", block.scale),
            ("method", block.method),
            ("note", block.note),
        )
        if value and value.strip()
    ]
    return " · ".join(parts) or None


def _probe_module_at_path(
    fs: "AbstractFileSystem",
    base_path: str,
    protocol: str,
    module_name: str,
    source_url: str,
    repo_id: str,
) -> Optional[ModuleInfo]:
    """
    Probe a directory for module files (weights.parquet, a 0.4 lead table, etc.).

    Returns ModuleInfo if any table in LEAD_TABLES exists, None otherwise.

    **Which tables the module has is decided by `manifest.artifact.files` where a manifest exists**,
    and by probing where it does not (every module published under 0.3, which is all of ours today).
    See `_attested_files`: the publisher never removes a file, so a directory can hold a union of two
    releases and a probe would read a previous release's table as a live one.
    """
    manifest = _remote_manifest(fs, base_path)
    attested = _attested_names(manifest)
    lead_table = _find_lead_table(fs, base_path, attested)
    if lead_table is None:
        return None
    lead_path = f"{base_path}/{lead_table}.parquet"

    def _has(name: str) -> bool:
        if attested is not None:
            return name in attested
        return fs.exists(f"{base_path}/{name}")

    annotations_path = f"{base_path}/annotations.parquet"
    studies_path = f"{base_path}/studies.parquet"
    sources_path = f"{base_path}/sources.parquet"
    metadata_json_path = f"{base_path}/metadata.json"
    metadata_yaml_path = f"{base_path}/metadata.yaml"

    # Logo can be .png, .jpg, or .jpeg
    logo_url = None
    for ext in ("png", "jpg", "jpeg"):
        logo_candidate = f"{base_path}/logo.{ext}"
        if fs.exists(logo_candidate):
            logo_url = _build_url(protocol, logo_candidate)
            break

    # Metadata can be .json or .yaml
    resolved_metadata_url = None
    if fs.exists(metadata_json_path):
        resolved_metadata_url = _build_url(protocol, metadata_json_path)
    elif fs.exists(metadata_yaml_path):
        resolved_metadata_url = _build_url(protocol, metadata_yaml_path)

    lead_url = _build_url(protocol, lead_path)
    return ModuleInfo(
        name=module_name,
        repo_id=repo_id,
        source_url=source_url,
        path=base_path,
        lead_table=lead_table,
        lead_url=lead_url,
        weights_url=lead_url if lead_table == "weights" else None,
        # These three are parquets inside `artifact.digest`, so `_has` consults the attested list.
        # `logo`/`metadata` below are deliberately left probing: neither is in `ARTIFACT_PARQUETS`,
        # so a manifest says nothing about them and asking it would drop the logo off every module.
        annotations_url=_build_url(protocol, annotations_path) if _has("annotations.parquet") else None,
        studies_url=_build_url(protocol, studies_path) if _has("studies.parquet") else None,
        sources_url=_build_url(protocol, sources_path) if _has("sources.parquet") else None,
        logo_url=logo_url,
        metadata_url=resolved_metadata_url,
        # Stated, not checked: the digest is what the module *claims*, exactly as on the local path.
        manifest_version=(manifest.identity.version or None) if manifest else None,
        manifest_digest=(manifest.artifact.digest or None) if manifest and manifest.artifact else None,
        manifest_weighting=_weighting_summary(manifest) if manifest else None,
    )


def _discover_hf_source(source: Source) -> dict[str, ModuleInfo]:
    """Discover modules from a HuggingFace source."""
    repo_id = source.hf_repo_id
    if not repo_id:
        return {}

    fs = _get_hf_filesystem()
    base_path = f"datasets/{repo_id}/data"
    module_infos: dict[str, ModuleInfo] = {}

    # Auto-detect or use explicit kind
    kind = source.kind

    if kind == "module" or (kind is None and not fs.exists(base_path)):
        # Single module: check for a lead table at data root or repo root.
        #
        # `_probe_module_at_path` is the whole test, rather than `_find_lead_table` first and then a
        # probe. It used to be both, and the duplicate decided *which candidate to stop at*: the probe
        # answers from `manifest.artifact.files` where a manifest exists, so a directory holding only
        # an unattested leftover parquet satisfied the outer check, returned no ModuleInfo, and
        # `break` then skipped the candidate that would have worked.
        for candidate_path in (base_path, f"datasets/{repo_id}"):
            name = source.name or repo_id.split("/")[-1]
            info = _probe_module_at_path(fs, candidate_path, "hf", name, source.url, repo_id)
            if info:
                module_infos[name] = info
                break
        return module_infos

    # Collection: scan subfolders
    if not fs.exists(base_path):
        return module_infos

    entries = fs.ls(base_path, detail=True)
    for entry in entries:
        if entry["type"] == "directory":
            folder_name = entry["name"].split("/")[-1]
            if folder_name in module_infos:
                continue
            info = _probe_module_at_path(fs, entry["name"], "hf", folder_name, source.url, repo_id)
            if info:
                module_infos[folder_name] = info

    return module_infos


def _discover_fsspec_source(source: Source) -> dict[str, ModuleInfo]:
    """Discover modules from a generic fsspec source."""
    protocol = source.protocol
    fs = _get_fsspec_filesystem(protocol, source.url)
    module_infos: dict[str, ModuleInfo] = {}

    # Determine the base path (strip protocol prefix)
    if "://" in source.url:
        raw_path = source.url.split("://", 1)[1]
    else:
        raw_path = source.url

    # For GitHub, strip org/repo from the path for fs operations
    if protocol == "github":
        parts = raw_path.strip("/").split("/")
        base_path = "/".join(parts[2:]) if len(parts) > 2 else ""
    else:
        base_path = raw_path.rstrip("/")

    kind = source.kind

    if kind == "module":
        name = source.name or base_path.split("/")[-1] if base_path else "unknown"
        info = _probe_module_at_path(fs, base_path, protocol, name, source.url, source.url)
        if info:
            module_infos[name] = info
        return module_infos

    # Auto-detect: is the root itself a single module? The probe is the test (see the HF branch
    # above) — asking `_find_lead_table` first would let an unattested leftover parquet at the root
    # return "yes, a module" and then return nothing, skipping the collection scan below.
    if kind is None:
        name = source.name or base_path.split("/")[-1] if base_path else "unknown"
        info = _probe_module_at_path(fs, base_path, protocol, name, source.url, source.url)
        if info:
            module_infos[name] = info
            return module_infos

    # Collection: scan subfolders
    _VERSION_RE = re.compile(r"^v(\d+)$")
    entries = fs.ls(base_path, detail=True) if base_path else fs.ls("", detail=True)
    for entry in entries:
        entry_type = entry.get("type", "")
        if entry_type == "directory":
            folder_name = entry["name"].split("/")[-1]
            if folder_name in module_infos:
                continue
            # Try flat layout first: {name}/weights.parquet
            info = _probe_module_at_path(fs, entry["name"], protocol, folder_name, source.url, source.url)
            if info:
                module_infos[folder_name] = info
                continue
            # Versioned layout: {name}/v{N}/weights.parquet — find highest
            try:
                sub_entries = fs.ls(entry["name"], detail=True)
            except Exception:
                continue
            best_version = -1
            best_path: Optional[str] = None
            for sub in sub_entries:
                if sub.get("type") == "directory":
                    sub_name = sub["name"].split("/")[-1]
                    m = _VERSION_RE.match(sub_name)
                    if m and int(m.group(1)) > best_version:
                        best_version = int(m.group(1))
                        best_path = sub["name"]
            if best_path:
                info = _probe_module_at_path(fs, best_path, protocol, folder_name, source.url, source.url)
                if info:
                    module_infos[folder_name] = info

    return module_infos


def discover_modules_from_source(source: Source) -> dict[str, ModuleInfo]:
    """
    Discover modules from a single source.

    Dispatches to HF-specific or generic fsspec discovery based on the source URL.
    """
    try:
        if source.is_hf:
            return _discover_hf_source(source)
        return _discover_fsspec_source(source)
    except Exception as e:
        log_message(
            message_type="warning",
            action="discover_modules_from_source",
            source_url=source.url,
            message=f"Failed to discover modules from {source.url}: {e}",
        )
        return {}


def discover_all_modules() -> dict[str, ModuleInfo]:
    """
    Discover modules from all configured sources in modules.yaml.

    Earlier sources take precedence on name collisions.
    """
    all_modules: dict[str, ModuleInfo] = {}
    for source in MODULES_CONFIG.sources:
        discovered = discover_modules_from_source(source)
        for name, info in discovered.items():
            if name not in all_modules:
                all_modules[name] = info
                continue
            # Earlier-source-wins is the rule, but it was silent, and the shipped `modules.yaml`
            # lists the HuggingFace collection first while `_ensure_local_source` appends. So a
            # module you register locally under a name already published — ten of those names are
            # present by default — is shadowed by the remote one and annotates with somebody else's
            # bytes, with nothing anywhere saying so. Reported by just-module-creator, 2026-08-20.
            shadowed = all_modules[name]
            if shadowed.lead_url == info.lead_url:
                continue
            log_message(
                message_type="warning",
                action="module_name_collision",
                module=name,
                using=shadowed.lead_url,
                shadowed=info.lead_url,
                reason=(
                    "two sources supply a module with this name; the earlier source wins. Rename "
                    "the local module if you meant to use it instead of the published one."
                ),
            )

    log_message(
        message_type="info",
        action="discover_all_modules",
        modules=list(all_modules.keys()),
        sources=[s.url for s in MODULES_CONFIG.sources],
    )
    return all_modules


def discover_hf_modules(repo_ids: Optional[list[str]] = None) -> dict[str, ModuleInfo]:
    """
    Discover modules from HuggingFace repositories.

    Backward-compatible wrapper. If repo_ids is provided, scans those repos.
    Otherwise uses all configured sources from modules.yaml.

    Args:
        repo_ids: Optional list of HF repo IDs. If None, uses all configured sources.

    Returns:
        Mapping of module names to ModuleInfo.
    """
    if repo_ids is not None:
        # Explicit repo list: build Source objects and discover
        module_infos: dict[str, ModuleInfo] = {}
        for repo_id in repo_ids:
            source = Source(url=repo_id)
            discovered = discover_modules_from_source(source)
            for name, info in discovered.items():
                if name not in module_infos:
                    module_infos[name] = info
        return module_infos

    # Default: use all configured sources
    return discover_all_modules()


# On a version bump, drop stale HF-cached module snapshots BEFORE the first
# discovery/read, so a republished module isn't shadowed by an old cached revision.
# Cache housekeeping must never break import — swallow any failure.
try:
    invalidate_module_cache_on_version_change()
except Exception as _cache_exc:  # noqa: BLE001 - best-effort housekeeping
    log_message(
        message_type="warning",
        action="module_cache_invalidation_failed",
        error=str(_cache_exc),
    )

# Cache discovered modules at import time
MODULE_INFOS: dict[str, ModuleInfo] = discover_hf_modules()
DISCOVERED_MODULES: list[str] = sorted(list(MODULE_INFOS.keys()))


def refresh_modules() -> dict[str, ModuleInfo]:
    """Reload modules.yaml from disk, re-discover all modules, and update globals.

    This allows runtime registration/unregistration of custom modules
    without restarting the process.

    Returns:
        The refreshed MODULE_INFOS dict.
    """
    import just_dna_pipelines.module_config as mc
    global MODULES_CONFIG, HF_REPO_ID

    mc.MODULES_CONFIG = mc._load_config()
    mc.DEFAULT_REPOS[:] = [
        s.hf_repo_id for s in mc.MODULES_CONFIG.sources
        if s.is_hf and s.hf_repo_id is not None
    ]
    MODULES_CONFIG = mc.MODULES_CONFIG
    DEFAULT_REPOS[:] = mc.DEFAULT_REPOS
    HF_DEFAULT_REPOS[:] = mc.DEFAULT_REPOS
    HF_REPO_ID = HF_DEFAULT_REPOS[0] if HF_DEFAULT_REPOS else ""

    fresh = discover_all_modules()
    # Update existing entries and add new ones first (readers always see
    # valid data), then remove stale keys.  The previous clear()+update()
    # pattern left an empty window that caused crashes when other threads
    # read MODULE_INFOS concurrently (e.g. PRS background task).
    MODULE_INFOS.update(fresh)
    for stale_key in list(MODULE_INFOS.keys()):
        if stale_key not in fresh:
            MODULE_INFOS.pop(stale_key, None)
    DISCOVERED_MODULES[:] = sorted(MODULE_INFOS.keys())

    log_message(
        message_type="info",
        action="refresh_modules",
        modules=list(DISCOVERED_MODULES),
    )
    return MODULE_INFOS


class ModuleTable(str, Enum):
    """Tables available in each annotator module."""
    ANNOTATIONS = "annotations"
    STUDIES = "studies"
    WEIGHTS = "weights"
    SOURCES = "sources"
    # Whichever table family carries this module's rows — weights for most, pharm_variants for a
    # pharmacogenomics module. Ask for this rather than WEIGHTS unless you truly need weights.
    LEAD = "lead"


def get_module_info(module_name: str) -> ModuleInfo:
    """Get ModuleInfo for a specific module."""
    if module_name not in MODULE_INFOS:
        raise ValueError(f"Module {module_name} not found in discovered modules")
    return MODULE_INFOS[module_name]


def get_module_table_url(module_name: str, table: str | ModuleTable, module_info: Optional[ModuleInfo] = None) -> str:
    """
    Get the URL for a specific module table.

    Args:
        module_name: Name of the module (e.g., "longevitymap")
        table: Table name or ModuleTable enum
        module_info: Optional ModuleInfo. If not provided, uses global MODULE_INFOS.
    """
    info = module_info or get_module_info(module_name)
    table_name = table.value if isinstance(table, ModuleTable) else table

    # "lead" is the alias; the family's own name resolves the same way, so a caller iterating table
    # names gets the real URL rather than the protocol-less fallback at the end of this function.
    if table_name in ("lead", info.lead_table):
        return info.lead_url
    elif table_name == "weights":
        if not info.weights_url:
            raise ValueError(
                f"Module {module_name} has no weights table — it is led by {info.lead_table}. "
                f"Ask for ModuleTable.LEAD instead."
            )
        return info.weights_url
    elif table_name == "annotations":
        if not info.annotations_url:
            raise ValueError(f"Module {module_name} does not have an annotations table")
        return info.annotations_url
    elif table_name == "studies":
        if not info.studies_url:
            raise ValueError(f"Module {module_name} does not have a studies table")
        return info.studies_url
    elif table_name == "sources":
        if not info.sources_url:
            raise ValueError(f"Module {module_name} does not have a sources table")
        return info.sources_url

    # Fallback for unknown tables
    return f"{info.path}/{table_name}.parquet"


def scan_module_table(
    module_name: str,
    table: str | ModuleTable,
    cache_dir: Optional[str] = None,
    module_info: Optional[ModuleInfo] = None,
) -> pl.LazyFrame:
    """
    Lazily scan a module table.

    Uses Polars' native support for various storage backends.

    Args:
        module_name: Name of the module (e.g., "longevitymap")
        table: Which table to load (annotations, studies, weights)
        cache_dir: Optional local cache directory
        module_info: Optional ModuleInfo for the module

    Returns:
        LazyFrame for memory-efficient processing
    """
    url = get_module_table_url(module_name, table, module_info=module_info)
    return pl.scan_parquet(url)


def scan_module_weights(module_name: str) -> pl.LazyFrame:
    """Convenience function to scan a module's weights table."""
    return scan_module_table(module_name, ModuleTable.WEIGHTS)


def scan_module_annotations(module_name: str) -> pl.LazyFrame:
    """Convenience function to scan a module's annotations table."""
    return scan_module_table(module_name, ModuleTable.ANNOTATIONS)


def scan_module_studies(module_name: str) -> pl.LazyFrame:
    """Convenience function to scan a module's studies table."""
    return scan_module_table(module_name, ModuleTable.STUDIES)


def get_all_modules() -> list[str]:
    """Return all discovered modules."""
    return DISCOVERED_MODULES.copy()


def validate_module(module_name: str) -> bool:
    """Check if a module name is valid (exists in discovered modules)."""
    return module_name.lower() in [m.lower() for m in DISCOVERED_MODULES]


def validate_modules(module_names: list[str]) -> list[str]:
    """
    Validate and filter a list of module names.

    Returns only valid modules that exist in DISCOVERED_MODULES.
    """
    valid = []
    for name in module_names:
        name_lower = name.lower()
        for discovered in DISCOVERED_MODULES:
            if discovered.lower() == name_lower:
                valid.append(discovered)
                break
    return valid


def local_module_path(url: str) -> Optional[Path]:
    """The filesystem path a module URL names, or ``None`` when it names a remote one.

    The one predicate for "are these bytes on this machine", so that a caller does not have to
    guess at prefixes. A local module's URL is a bare absolute path (`_build_url` returns the path
    unchanged for the `file` protocol), and `startswith("/")` — the test three call sites used to
    apply — answers *False* for every Windows path, so a locally-installed module was rendered as
    a HuggingFace one there and its logo was never served. A legacy `file://` URL is still
    accepted: an artifact written before the fix may carry one.
    """
    if not url:
        return None
    if "://" in url and not url.startswith("file://"):
        return None  # hf://, http(s)://, s3://, github://, …
    raw = url[len("file://"):] if url.startswith("file://") else url
    if not raw:
        return None
    # Absolute in *either* grammar, so the answer does not change with the interpreter's platform:
    # `Path("C:/Users/…").is_absolute()` is False on POSIX and True on Windows, and a test that can
    # only run on one of them is no fence at all. There is no false positive to trade away — a
    # relative path is relative in both grammars — and the URL was produced by fsspec on the same
    # machine that is now asking, so the native reading is the one that matters in production.
    if not (PurePosixPath(raw).is_absolute() or PureWindowsPath(raw).is_absolute()):
        return None
    return Path(raw)


def is_local_module_url(url: str) -> bool:
    """Whether the URL names a module on this filesystem. See `local_module_path`."""
    return local_module_path(url) is not None


def local_module_dir(info: Optional[ModuleInfo]) -> Optional[Path]:
    """The module's directory when its bytes live on this filesystem, else ``None``.

    A registry install or a local compile is a real directory under the registered-modules dir
    (the local source's URL is a bare absolute path, so `ModuleInfo.path` is that directory). An
    HF- or HTTP-discovered module has a relative or remote base path and no local directory —
    `scan_module_table` goes straight to the parquet URL and never fetches a manifest.
    """
    if info is None:
        return None
    path = Path(info.path)
    if not path.is_absolute() or not path.is_dir():
        return None
    return path


def read_module_provenance(
    info: Optional[ModuleInfo],
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """``(version, artifact digest, weighting)`` for the module, as far as the source states them.

    `None` means *not established*, never "unversioned" or "unverified".

    Two sources answer, in order. A local install or a local compile puts `manifest.json` on disk
    and is the richer path — it can also fall back to the authored spec for a version the compiler
    left null. A remote source answers from whatever its published manifest stated at discovery
    time, which `ModuleInfo` now carries: discovery already fetched and validated that manifest to
    decide the module's kind, and used to drop everything but the file list, so a remotely
    discovered module reported *Not stated* for facts we had already read. A module published
    before manifests existed — every one of ours on HuggingFace today — still answers `None` to all
    three, which is the honest answer rather than a degraded one.

    The digest is the value the module **claims** — read from its manifest, not recomputed. Nothing
    in this repo calls `just_dna_format.integrity.verify_manifest`, so recording it ties a report to
    a stated identity, not to a checked one. Do not present it to a reader as verification.

    `weighting` is the module's own statement of what its authored `weight` column *means* — scale,
    method, free-text note (format 0.6, RM92). It exists because `weight` is a bare float with no
    unit column, so nothing in a pre-0.6 artifact could say what scale it runs on; the report shows a
    per-module net weight, and a reader cannot interpret that number without it. **Absent is
    `None`, and `None` means the module has not said — never that its weights are comparable to
    anything else's.**
    """
    module_dir = local_module_dir(info)
    if module_dir is None:
        # No manifest on disk. Fall back to what the remote source's own manifest stated, which is
        # `None` on all three for a source that publishes none.
        if info is None:
            return (None, None, None)
        return (info.manifest_version, info.manifest_digest, info.manifest_weighting)

    manifest_path = module_dir / "manifest.json"
    version: Optional[str] = None
    digest: Optional[str] = None
    weighting: Optional[str] = None
    if manifest_path.exists():
        try:
            manifest = read_manifest(manifest_path)
        except (ValueError, OSError) as exc:
            log_message(
                message_type="warning",
                action="unreadable_module_manifest",
                path=str(manifest_path),
                reason=str(exc),
            )
        else:
            version = manifest.identity.version or None
            digest = manifest.artifact.digest or None
            weighting = _weighting_summary(manifest)

    # The compiler leaves `identity.version` null — the registry stamps identity at publish time —
    # so a locally-compiled module's version lives only in the authored spec.
    if version is None:
        version = spec_version(module_dir) or None

    # A local manifest that is silent on a field must not lose what discovery already read from the
    # source. Never the reverse: an on-disk manifest describes the bytes we actually annotated with.
    if info is not None:
        version = version or info.manifest_version
        digest = digest or info.manifest_digest
        weighting = weighting or info.manifest_weighting

    return (version, digest, weighting)


class ModuleOutputMapping(BaseModel):
    """Mapping of output files to their source modules."""
    module: str
    # Which table family actually carried this module's rows. The output file is named
    # `{module}_weights.parquet` whatever the family, because every downstream consumer globs for
    # that; this says what is really inside, so `pharmgkb_weights.parquet` is not read as weights.
    lead_table: str = "weights"
    weights_path: Optional[str] = None
    logo_path: Optional[str] = None
    metadata_path: Optional[str] = None
    # Which module *bytes* produced these rows, so a saved report can be tied to them and a stale
    # one can be told from a current one. All three are `None` where the acquisition path does not
    # state them — see `read_module_provenance`: HF discovery reads the parquet URL and nothing
    # else, so only `source_url` is known there. `None` means not established, never "none".
    version: Optional[str] = None
    digest: Optional[str] = None
    source_url: Optional[str] = None
    # What the module says its `weight` column means (format 0.6, RM92), verbatim. `None` means the
    # module has not said, which a reader must not take as "these weights are comparable".
    weighting: Optional[str] = None


class AnnotationManifest(BaseModel):
    """Manifest describing all annotation outputs for a user's VCF."""
    user_name: str
    sample_name: str
    source_vcf: str
    # Where the outputs were written. Stated rather than reconstructed from `modules[0]`, which is
    # not there to reconstruct from when every selected module was skipped.
    output_dir: str = ""
    modules: list[ModuleOutputMapping]
    # Modules asked for that produced no output, by name → reason: an unjoinable lead family
    # (skipped) or an error (failed). Absent from `modules`, so recorded here instead of lost.
    skipped_modules: dict[str, str] = {}
    failed_modules: dict[str, str] = {}
    # Rows that actually matched a module entry — NOT the height of the parquets, which keep the
    # unmatched rows of a position join on purpose.
    total_variants_annotated: int = 0
    # Rows reported from the *absence* of a call: the module authored the reference genotype and the
    # callset, being variant-only, emitted no record at that site. Held apart from the annotated
    # total because these were inferred, never observed, and a reader is owed that distinction.
    restored_variants: dict[str, int] = {}
    total_variants_restored: int = 0
    # Execution metrics
    duration_sec: Optional[float] = None
    cpu_percent: Optional[float] = None
    peak_memory_mb: Optional[float] = None
    timestamp: Optional[str] = None  # ISO format
