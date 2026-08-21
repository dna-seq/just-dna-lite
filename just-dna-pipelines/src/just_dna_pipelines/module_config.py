"""
Module configuration loader.

Reads modules.yaml to determine which sources to scan for annotation modules
and provides optional display metadata overrides for discovered modules.

The file is searched in three locations (first found wins):
  1. Working copy ``modules.yaml`` in the runtime interim directory
  2. Project root ``modules.yaml`` (git-tracked, read-only defaults)
  3. Package directory ``just_dna_pipelines/`` (bundled fallback)

All writes (register/unregister custom modules) go to the working copy.
On first write the repo default is copied as the seed so settings like
quality_filters and ensembl_source carry over.

Modules are always auto-discovered from sources. This config only controls
which sources to scan and how modules are displayed in the UI, CLI, and
reports. Modules not listed in the YAML get sensible defaults.

Supported source types (auto-detected from URL):
  - "org/repo" or "hf://datasets/org/repo" -> HuggingFace
  - "github://org/repo"                    -> GitHub via fsspec
  - "https://..." / "http://..."           -> HTTP via fsspec
  - "s3://...", "gcs://...", etc.           -> cloud storage via fsspec

Each source can be a single module or a collection of modules.
Auto-detect: weights.parquet at root = module, subfolders = collection.
Override with kind: "module" or kind: "collection".
"""

import hashlib
import json
import os
import warnings
from pathlib import Path
from typing import Any, Dict, Literal, Optional

import polars as pl
import yaml
from eliot import log_message
from just_dna_format.identity import is_valid_version, version_from_legacy
from pydantic import BaseModel, ValidationError, model_validator


# Default values for modules not listed in the YAML
_DEFAULT_ICON = "database"
_DEFAULT_COLOR = "#6435c9"


class QualityFilters(BaseModel):
    """VCF quality filter thresholds loaded from modules.yaml.

    Applied during normalization to remove low-quality variants before annotation.
    All fields default to None (no filtering) for backward compatibility.
    """
    pass_filters: Optional[list[str]] = None
    min_depth: Optional[int] = None
    min_qual: Optional[float] = None

    @property
    def is_active(self) -> bool:
        """True if at least one filter is configured."""
        return bool(self.pass_filters) or bool(self.min_depth) or bool(self.min_qual)

    def config_hash(self) -> str:
        """Deterministic hash of the active filter settings for DataVersion tracking."""
        canonical = json.dumps(self.model_dump(), sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _find_column(schema_names: list[str], candidates: tuple[str, ...]) -> Optional[str]:
    """Return the first column name from *candidates* found in *schema_names*, or None."""
    for col in candidates:
        if col in schema_names:
            return col
    return None


def _expand_pass_filters(pass_filters: list[str]) -> list[str]:
    """Expand the FILTER allow-list to cover the VCF "missing" sentinel.

    The VCF spec uses ``.`` for an unfiltered/missing FILTER, but ``polars-bio``
    decodes ``.`` as an empty string ``""``. So a config of ``["PASS", "."]``
    would never match GATK HaplotypeCaller-style records (FILTER=".") and would
    drop every row. Treat ``.`` and ``""`` as the same "no filter applied" value.
    """
    allowed = set(pass_filters)
    if "." in allowed or "" in allowed:
        allowed.update({".", ""})
    return list(allowed)


def build_quality_filter_expr(
    filters: QualityFilters,
    schema_names: list[str],
) -> Optional[pl.Expr]:
    """Build a combined Polars filter expression from quality filter config.

    Returns None if no filters are active or no matching columns exist.
    """
    conditions: list[pl.Expr] = []

    if filters.pass_filters:
        col = _find_column(schema_names, ("filter", "Filter", "FILTER"))
        if col is not None:
            conditions.append(pl.col(col).is_in(_expand_pass_filters(filters.pass_filters)))

    if filters.min_depth is not None and filters.min_depth > 0:
        col = _find_column(schema_names, ("DP", "Dp", "dp"))
        if col is not None:
            conditions.append(pl.col(col).cast(pl.Int64, strict=False) >= filters.min_depth)

    if filters.min_qual is not None and filters.min_qual > 0:
        col = _find_column(schema_names, ("qual", "Qual", "QUAL"))
        if col is not None:
            conditions.append(pl.col(col).cast(pl.Float64, strict=False) >= filters.min_qual)

    if not conditions:
        return None
    return conditions[0] if len(conditions) == 1 else pl.all_horizontal(conditions)


class ModuleMetadata(BaseModel):
    """Display metadata for an annotation module."""
    title: Optional[str] = None
    description: Optional[str] = None
    report_title: Optional[str] = None
    icon: str = _DEFAULT_ICON
    color: str = _DEFAULT_COLOR


class Source(BaseModel):
    """
    A source of annotation modules.

    Can be a collection (scans subfolders) or a single module.
    Source type is auto-detected from the URL pattern.
    """
    url: str
    kind: Optional[Literal["module", "collection"]] = None  # None = auto-detect
    name: Optional[str] = None  # Name override for single-module sources

    @property
    def is_hf(self) -> bool:
        """Check if this is a HuggingFace source."""
        if self.url.startswith("hf://"):
            return True
        # Shorthand: "org/repo" with no protocol prefix and exactly one slash
        if "://" not in self.url and self.url.count("/") == 1:
            return True
        return False

    @property
    def hf_repo_id(self) -> Optional[str]:
        """Extract HuggingFace repo ID from the URL."""
        if not self.is_hf:
            return None
        if self.url.startswith("hf://datasets/"):
            return self.url.removeprefix("hf://datasets/").rstrip("/")
        if self.url.startswith("hf://"):
            return self.url.removeprefix("hf://").rstrip("/")
        # Shorthand: "org/repo"
        return self.url.rstrip("/")

    @property
    def protocol(self) -> str:
        """Extract the fsspec protocol from the URL."""
        if "://" in self.url:
            return self.url.split("://")[0]
        # Shorthand HF
        if self.is_hf:
            return "hf"
        return "file"


class EnsemblSource(BaseModel):
    """Ensembl variation reference dataset configuration.

    Loaded from ``ensembl_source:`` in modules.yaml.
    The ``repo_id`` must be a HuggingFace dataset (``org/repo``).
    """
    repo_id: str = "just-dna-seq/ensembl_variations"


#: Where the public registry lives. The client, the CLI and ``scripts/registry_precheck.py`` all
#: read ``$REGISTRY_URL``; this is only the fallback when nothing configures a store list.
DEFAULT_REGISTRY_URL: str = "https://module-registry.just-dna.life"


class RegistryStore(BaseModel):
    """A module registry server ("store") the Catalog can browse, install from and publish to.

    Configured under ``registries:`` in modules.yaml. Two are shipped: the public registry, and
    the ``polygon`` testing ground (``module-polygon.just-dna.life``), which answers
    ``"mode": "test"`` on ``/api/v1/version`` and exists so a namespace claim or a publish can be
    rehearsed without touching the public catalog.

    ``token_env`` names the environment variable holding *this server's* bearer token, and it is
    per store rather than one global name on purpose: an account token is minted by one server and
    is meaningless to another. Writing a test server's token into ``REGISTRY_TOKEN`` has broken
    publishing here before, and it does not surface as anything auth-shaped — the public server
    answers ``403 insufficient_capability``, which reads as a namespace-permissions bug.
    """
    key: str                      # stable slug used in URLs, identity slots and env names
    label: str                    # what the store selector shows
    url: str
    mode: str = "prod"            # "prod" | "test" — mirrors /api/v1/version's `mode`
    description: str = ""
    token_env: str = ""           # "" = never mirror this store's token into the environment

    @property
    def base_url(self) -> str:
        """URL with any trailing slash removed (what ``RegistryClient`` wants)."""
        return self.url.rstrip("/")

    @property
    def is_test(self) -> bool:
        return self.mode == "test"


class DefaultSample(BaseModel):
    """A pre-configured public genome sample for immutable mode."""
    zenodo_url: str
    filename: str = ""
    label: str
    subject_id: str = ""
    sex: str = "N/A"
    species: str = "Homo sapiens"
    reference_genome: str = "GRCh38"
    license: str = ""


_DEFAULT_DISCLAIMER = (
    "This is a public demo with pre-loaded public genomes. "
    "To analyze your own genome, install just-dna-lite locally: "
    "https://github.com/dna-seq/just-dna-lite"
)


class ImmutableModeConfig(BaseModel):
    """Configuration for immutable (public demo) mode.

    When enabled, file uploads are disabled and only pre-configured
    public genomes from ``default_samples`` are available.  The
    ``allow_zenodo_import`` flag controls whether users can also
    import additional genomes from Zenodo URLs.
    """
    enabled: bool = False
    allow_zenodo_import: bool = False
    disclaimer: str = _DEFAULT_DISCLAIMER
    default_samples: list[DefaultSample] = []


class ModulesConfig(BaseModel):
    """Top-level configuration from modules.yaml."""
    sources: list[Source] = [Source(url="just-dna-seq/annotators")]
    module_metadata: dict[str, ModuleMetadata] = {}
    quality_filters: QualityFilters = QualityFilters()
    ensembl_source: EnsemblSource = EnsemblSource()
    immutable_mode: ImmutableModeConfig = ImmutableModeConfig()
    registries: list[RegistryStore] = [
        RegistryStore(
            key="prod",
            label="Just-DNA Registry",
            url=DEFAULT_REGISTRY_URL,
            token_env="REGISTRY_TOKEN",
        )
    ]

    @model_validator(mode="before")
    @classmethod
    def _normalize_sources(cls, data: dict) -> dict:
        """Allow sources to be plain strings or dicts."""
        if "sources" in data and isinstance(data["sources"], list):
            normalized = []
            for item in data["sources"]:
                if isinstance(item, str):
                    normalized.append({"url": item})
                else:
                    normalized.append(item)
            data["sources"] = normalized
        return data


def _find_project_root() -> Optional[Path]:
    """Find the workspace root.

    Resolution: ``JUST_DNA_PIPELINES_ROOT`` env var, then walk up from CWD
    looking for a pyproject.toml with ``[tool.uv.workspace]``.
    """
    env_root = os.getenv("JUST_DNA_PIPELINES_ROOT")
    if env_root:
        return Path(env_root).resolve()
    candidate = Path.cwd()
    for _ in range(10):
        pyproject = candidate / "pyproject.toml"
        if pyproject.exists() and "[tool.uv.workspace]" in pyproject.read_text():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    return None


def _runtime_data_root_from_output(output_dir: Path) -> Path:
    """Infer the runtime data root from JUST_DNA_PIPELINES_OUTPUT_DIR."""
    resolved = output_dir.resolve()
    if resolved.name == "users" and resolved.parent.name == "output":
        return resolved.parent.parent
    if resolved.name == "output":
        return resolved.parent
    return resolved.parent


def _working_config_path() -> Optional[Path]:
    """Return the path for the mutable working copy of modules.yaml.

    Resolution order:
      1. ``JUST_DNA_MODULES_YAML`` env var (absolute path)
      2. ``JUST_DNA_PIPELINES_INTERIM_DIR`` env var
      3. ``JUST_DNA_PIPELINES_OUTPUT_DIR``-derived runtime data root
      4. ``data/interim/modules.yaml`` under the project root (gitignored)

    Returns None when neither is available.
    """
    env = os.getenv("JUST_DNA_MODULES_YAML")
    if env:
        return Path(env).expanduser().resolve()

    env_interim = os.getenv("JUST_DNA_PIPELINES_INTERIM_DIR")
    if env_interim:
        return Path(env_interim).expanduser().resolve() / "modules.yaml"

    env_output = os.getenv("JUST_DNA_PIPELINES_OUTPUT_DIR")
    if env_output:
        data_root = _runtime_data_root_from_output(Path(env_output).expanduser())
        return data_root / "interim" / "modules.yaml"

    project_root = _find_project_root()
    if project_root is None:
        return None
    return project_root / "data" / "interim" / "modules.yaml"


def _default_config_path() -> Optional[Path]:
    """Return the path of the repo-shipped (read-only) modules.yaml.

    Checks project root first, then falls back to the package directory.
    """
    project_root = _find_project_root()
    if project_root is not None:
        candidate = project_root / "modules.yaml"
        if candidate.exists():
            return candidate
    pkg = Path(__file__).parent / "modules.yaml"
    if pkg.exists():
        return pkg
    return None


def _drop_project_runtime_sources(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Remove repo-local generated/interim sources in env-backed runtimes."""
    if not os.getenv("JUST_DNA_PIPELINES_OUTPUT_DIR"):
        return raw

    project_root = _find_project_root()
    if project_root is None:
        return raw

    project_data = (project_root / "data").resolve()
    filtered_sources = []
    for source in raw.get("sources", []):
        url = source.get("url") if isinstance(source, dict) else source
        if isinstance(url, str) and url.startswith("/"):
            source_path = Path(url).expanduser().resolve()
            if source_path == project_data or project_data in source_path.parents:
                continue
        filtered_sources.append(source)

    raw = dict(raw)
    raw["sources"] = filtered_sources
    return raw


def _merge_config(default: Dict[str, Any], working: Dict[str, Any]) -> Dict[str, Any]:
    """Layer the mutable working copy over the shipped defaults.

    ``module_metadata``, ``sources`` and ``registries`` are merged rather than replaced. The first
    two are what a runtime mutates (register/unregister); ``registries`` is merged so a working copy
    seeded before a store existed still sees it. Merging means: a working copy that names one custom module must not
    delete the display metadata of the ten shipped ones. Every other key is taken from the working
    copy when it is present, since those are settings the deployment has deliberately overridden.

    This replaces a first-found-wins load that silently dropped the defaults. The failure was quiet
    and total: once ``register_custom_module`` wrote a working copy, every built-in module fell back
    to the auto-generated title/description/``database`` icon, in the app *and* in every spec a port
    wrote — which is how it was found (a rebuilt `coronary` came out as "Annotation module:
    coronary"). See ``save_config``, which patches only these two keys for the same reason.
    """
    merged = dict(default)
    for key, value in working.items():
        if key == "module_metadata" and isinstance(value, dict):
            base = dict(merged.get("module_metadata") or {})
            base.update(value)
            merged[key] = base
        elif key == "sources" and isinstance(value, list):
            by_url: Dict[str, Any] = {}
            for entry in list(merged.get("sources") or []) + value:
                url = entry.get("url") if isinstance(entry, dict) else entry
                by_url[str(url)] = entry
            merged[key] = list(by_url.values())
        elif key == "registries" and isinstance(value, list):
            # Merged by ``key`` for the same reason ``sources`` is merged by url: a working copy
            # written before a store was shipped must not delete it, and one that overrides a
            # store (a self-hosted URL, say) must not lose the other shipped ones.
            by_key: Dict[str, Any] = {}
            for entry in list(merged.get("registries") or []) + value:
                if isinstance(entry, dict):
                    by_key[str(entry.get("key") or entry.get("url"))] = entry
            merged[key] = list(by_key.values())
        else:
            merged[key] = value
    return merged


def _read_yaml(path: Path) -> Optional[Dict[str, Any]]:
    """Read a YAML mapping, raising on a malformed file.

    Used for the *shipped* default only. That file is git-tracked, so a parse failure is a build
    error and must stay loud — see ``_load_config``.
    """
    if not path.exists():
        return None
    with open(path) as f:
        raw = yaml.safe_load(f)
    return raw if isinstance(raw, dict) else None


def _read_yaml_tolerant(path: Path) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Read a YAML mapping, returning the parse failure as text instead of raising.

    The counterpart of ``_read_yaml``, used for the *working copy* only. That file is gitignored
    and mutated at runtime by register/unregister, so it is the one input that can be broken on a
    deployment and nowhere else. Returns ``(mapping, None)`` on success and ``(None, reason)`` on
    a failure the caller is expected to recover from; ``(None, None)`` means simply absent or empty.
    """
    if not path.exists():
        return None, None
    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
    except (yaml.YAMLError, OSError, UnicodeDecodeError) as exc:
        return None, str(exc)
    if raw is None:
        return None, None
    if not isinstance(raw, dict):
        return None, f"expected a YAML mapping at the top level, found {type(raw).__name__}"
    return raw, None


def _warn_unusable_working_copy(action: str, path: Path, message: str) -> None:
    """Report a working copy we could not use, on both the structured and the visible channel.

    Eliot alone is not enough here. This runs at import inside the Dagster code server, where an
    eliot message reaches a log the operator has no reason to open, while the symptom they *do*
    see is a bare ``Error loading repository location definitions.py`` with no traceback attached.
    A ``UserWarning`` is not filtered by default and lands in the code server's own output beside
    that line. Staying silent is not an option either: a config that quietly degrades to the
    shipped defaults leaves the broken file in place forever.
    """
    log_message(message_type="warning", action=action, path=str(path), message=message)
    warnings.warn(message)


def _load_config() -> ModulesConfig:
    """Load modules.yaml from the shipped defaults, with the working copy layered on top.

    1. Project root ``modules.yaml``, else package ``modules.yaml`` — the shipped defaults
    2. Working copy at ``data/interim/modules.yaml`` (mutable, gitignored) — merged over them

    Returns bare defaults if neither exists.

    **A broken working copy is recovered from; a broken default is not**, and the asymmetry is the
    point. This function runs at module scope (``MODULES_CONFIG``) and every Dagster asset module
    imports it transitively, so whatever it raises comes out as ``Error loading repository location
    definitions.py`` — a warning that carries no traceback, with the real stack only in the code
    server's stdout. The working copy is gitignored and rewritten at runtime by register/unregister,
    so a half-written or hand-edited file there is a runtime accident: ignore it, keep the shipped
    catalog, and say so loudly. The default is git-tracked, so a bad one is a build error, and
    recovering would hand back an empty ``ModulesConfig()`` — zero sources, zero modules discovered,
    and an app that looks healthy while annotating nothing.

    Validation runs on the *merged* mapping, so a working copy that is well-formed YAML but breaks
    the schema (``quality_filters.min_depth: "ten"``) is caught here too. Falling through re-validates
    the defaults alone, which either succeeds or raises the default's own error rather than the
    working copy's.
    """
    default_path = _default_config_path()
    raw: Dict[str, Any] = (_read_yaml(default_path) if default_path else None) or {}

    working = _working_config_path()
    if working is not None:
        working_raw, unreadable = _read_yaml_tolerant(working)
        if unreadable is not None:
            _warn_unusable_working_copy(
                "load_modules_config",
                working,
                f"Ignoring the modules.yaml working copy at {working}: {unreadable}. "
                "Falling back to the shipped defaults — any custom modules registered in that "
                "file are not loaded. Fix or delete it to restore them.",
            )
        elif working_raw is not None:
            merged = _drop_project_runtime_sources(_merge_config(raw, working_raw))
            try:
                return ModulesConfig.model_validate(merged)
            except ValidationError as exc:
                _warn_unusable_working_copy(
                    "load_modules_config",
                    working,
                    f"Ignoring the modules.yaml working copy at {working}: merged with the "
                    f"shipped defaults it does not validate — {exc}. Falling back to the shipped "
                    "defaults — any custom modules registered in that file are not loaded. "
                    "Fix or delete it to restore them.",
                )

    if not raw:
        return ModulesConfig()
    return ModulesConfig.model_validate(_drop_project_runtime_sources(raw))


def get_config_path() -> Path:
    """Return the writable modules.yaml path (working copy).

    All mutations (register/unregister) target this path, never the
    git-tracked repo default.  Falls back to the package directory only
    when no project root can be found.
    """
    working = _working_config_path()
    if working is not None:
        return working
    return Path(__file__).parent / "modules.yaml"


def read_config_for_update(path: Optional[Path] = None) -> Optional[ModulesConfig]:
    """Read the working copy as the base for a mutation, or ``None`` when it is unusable.

    The mutating callers (``register_custom_module`` / ``unregister_custom_module`` in
    ``module_registry``) read the working copy **alone** rather than merged over the defaults,
    because ``save_config`` then patches ``sources`` / ``module_metadata`` and writes the result
    back — handing them the merged mapping would bake every shipped default into the working copy.
    That is why this is not ``_load_config``.

    Returning ``None`` rather than a fallback keeps each caller's own behaviour for an absent file
    (two of the three want bare defaults, one wants a full load). An unusable file is reported and
    treated as absent, so the mutation goes on to ``save_config``, which moves the broken bytes
    aside and re-seeds — the write repairs the file instead of crashing on it. Without this the
    guard in ``_load_config`` would only move the crash from import time to the next register.
    """
    target = path or get_config_path()
    raw, unreadable = _read_yaml_tolerant(target)
    if unreadable is not None:
        _warn_unusable_working_copy(
            "read_modules_config_for_update",
            target,
            f"The modules.yaml working copy at {target} could not be parsed: {unreadable}. "
            "Treating it as absent for this update; it will be moved aside and re-seeded on write.",
        )
        return None
    if raw is None:
        return None
    try:
        return ModulesConfig.model_validate(raw)
    except ValidationError as exc:
        _warn_unusable_working_copy(
            "read_modules_config_for_update",
            target,
            f"The modules.yaml working copy at {target} does not validate — {exc}. "
            "Treating it as absent for this update; it will be moved aside and re-seeded on write.",
        )
        return None


def save_config(config: ModulesConfig, path: Optional[Path] = None) -> None:
    """Persist a ModulesConfig to the working copy using a merge strategy.

    On first write the repo default is copied as the seed so that
    quality_filters, ensembl_source, etc. are preserved.  Only the
    ``sources`` and ``module_metadata`` keys are patched.

    An existing working copy we cannot parse is **moved aside, not overwritten**, and the write
    re-seeds from the shipped default as if this were the first one. ``_load_config`` already
    disregards such a file, so without this the crash would simply move here and register/unregister
    would stay broken for good. The broken bytes are the only record of whatever registrations the
    file held, so they are kept next to it rather than destroyed.
    """
    target = path or get_config_path()

    raw: Dict[str, Any] = {}
    usable = target.exists()
    if usable:
        existing, unreadable = _read_yaml_tolerant(target)
        if unreadable is not None:
            corrupt = target.with_name(target.name + ".corrupt")
            target.replace(corrupt)
            _warn_unusable_working_copy(
                "save_modules_config",
                target,
                f"The modules.yaml working copy at {target} could not be parsed: {unreadable}. "
                f"Moved it to {corrupt} and re-seeded this write from the shipped defaults.",
            )
            usable = False
        else:
            raw = existing or {}

    if not usable:
        default = _default_config_path()
        if default is not None and default.exists():
            with open(default) as f:
                raw = yaml.safe_load(f) or {}

    sources_data = []
    for src in config.sources:
        entry: Dict[str, Any] = {"url": src.url}
        if src.kind is not None:
            entry["kind"] = src.kind
        if src.name is not None:
            entry["name"] = src.name
        sources_data.append(entry)
    raw["sources"] = sources_data

    metadata_data: Dict[str, Any] = {}
    for name, meta in config.module_metadata.items():
        entry = {}
        if meta.title is not None:
            entry["title"] = meta.title
        if meta.description is not None:
            entry["description"] = meta.description
        if meta.report_title is not None:
            entry["report_title"] = meta.report_title
        if meta.icon != _DEFAULT_ICON:
            entry["icon"] = meta.icon
        if meta.color != _DEFAULT_COLOR:
            entry["color"] = meta.color
        metadata_data[name] = entry
    raw["module_metadata"] = metadata_data

    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w") as f:
        yaml.dump(raw, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


# Loaded once at import time
MODULES_CONFIG: ModulesConfig = _load_config()


def is_immutable_mode() -> bool:
    """Check whether immutable (public demo) mode is active.

    The environment variable ``JUST_DNA_IMMUTABLE_MODE`` takes precedence
    over the YAML ``immutable_mode.enabled`` flag.
    """
    env = os.getenv("JUST_DNA_IMMUTABLE_MODE")
    if env is not None:
        return env.lower() in ("true", "1", "yes")
    return MODULES_CONFIG.immutable_mode.enabled


def get_immutable_config() -> ImmutableModeConfig:
    """Return the immutable mode configuration from modules.yaml."""
    return MODULES_CONFIG.immutable_mode

# The table families that can *lead* a compiled module — carry its rows in place of
# weights.parquet. A directory holding any of these is a module; discovery and the HuggingFace
# publisher both key on this list, so a new 0.4 family becomes discoverable and publishable by being
# added here once. Order is priority: a module shipping several is led by the first.
#
# Lives here rather than in `annotation.hf_modules` because importing that module runs discovery
# (and therefore network I/O) at import time, and the publisher must not pay for that.
def get_registry_stores() -> list[RegistryStore]:
    """Every registry server the app can offer, never empty.

    ``$REGISTRY_URL`` is honoured even when it names a server the YAML does not list: a
    self-hosted or forked deployment points the bundled client, the CLI and
    ``scripts/registry_precheck.py`` at it, and the UI must not quietly browse a different server
    than every command line in the same checkout. Such a server joins the list as its own store
    rather than replacing the configured ones, so the test ground stays one click away.
    """
    stores = list(MODULES_CONFIG.registries) or list(ModulesConfig().registries)
    env_url = (os.getenv("REGISTRY_URL") or "").rstrip("/")
    if env_url and not any(store.base_url == env_url for store in stores):
        host = env_url.split("://")[-1].split("/")[0]
        stores.insert(0, RegistryStore(
            key="env", label=host, url=env_url,
            description="Configured by $REGISTRY_URL.", token_env="REGISTRY_TOKEN",
        ))
    return stores


def get_registry_store(key: str) -> Optional[RegistryStore]:
    """The store with this ``key``, or ``None`` when nothing configures it."""
    for store in get_registry_stores():
        if store.key == key:
            return store
    return None


def default_registry_store() -> RegistryStore:
    """The store to open on: whichever one ``$REGISTRY_URL`` names, else the first configured.

    ``REGISTRY_URL`` stays authoritative because the bundled client, the CLI and
    ``scripts/registry_precheck.py`` all read it — a deployment that points those at one server
    must not silently open the UI on another. Call after ``load_env()``; before it, the variable
    from ``.env`` is not visible yet and the first configured store is used.
    """
    stores = get_registry_stores()
    env_url = (os.getenv("REGISTRY_URL") or "").rstrip("/")
    if env_url:
        for store in stores:
            if store.base_url == env_url:
                return store
    return stores[0]


LEAD_TABLES: tuple[str, ...] = (
    "weights",
    "pharm_variants",
    "diplotypes",
    "haplotypes",
    "pgs",
    "copynumbers",
    "repeat_alleles",
    "heteroplasmy",
    "activity_phenotype",
    "allele_function",
)


#: The **authored** CSV that compiles into each lead table, in the same priority order.
#:
#: Derived rather than hand-listed, because the hand-listed copies covered four of the ten families
#: — so a `heteroplasmy`- or `copynumbers`-led spec counted zero authored rows, and the registry's
#: enrichment ceiling (which counts the leading table's rows) was applied against 0 instead of
#: against the real height. `weights` is the only family whose CSV is not its own stem: the authored
#: DSL spells it `variants.csv`, which is checked against the compiler's own `_TABLE_KINDS` in
#: `tests/test_format_0_6.py` so a new family cannot arrive without either side noticing.
LEAD_TABLE_CSVS: tuple[str, ...] = tuple(
    "variants.csv" if table == "weights" else f"{table}.csv" for table in LEAD_TABLES
)


def find_lead_table(module_dir: Path) -> Optional[str]:
    """Return the table family leading a compiled module *directory*, or None if it is not one.

    The local-filesystem twin of `annotation.hf_modules._find_lead_table`, which asks the same
    question of an fsspec path. Both exist so that "is this a module" has one answer keyed on
    schema rather than on a family name: ten families exist today and the format keeps adding
    them, so probing `weights.parquet` alone silently excludes every pharmacogenomics, diplotype
    or PGS module — which is exactly how a `pharm_variants`-led registry install came to be
    annotatable but impossible to list, edit or publish from the UI.
    """
    for table in LEAD_TABLES:
        if (module_dir / f"{table}.parquet").exists():
            return table
    return None


def has_lead_table(module_dir: Path) -> bool:
    """True when the directory holds a compiled module — any lead table, not just weights."""
    return find_lead_table(module_dir) is not None


def spec_version(module_dir: Path) -> str:
    """Authored version from ``module_spec.yaml`` (``module.version``), normalized to SemVer.

    Identity beyond ``name`` (version/namespace/canonical_id) is a marketplace concern assigned at
    publish time — the compiler emits ``Identity(name=...)`` only, so a locally-compiled
    ``manifest.json`` carries a null ``identity.version``. The authored version still lives in the
    spec (possibly a legacy int/``vN`` like ``2``), so read it there and coerce (``2``/``v2`` →
    ``2.0.0``). Returns ``""`` when no usable version is found.
    """
    spec_path = module_dir / "module_spec.yaml"
    if not spec_path.exists():
        return ""
    try:
        raw = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError):
        return ""
    version = (raw.get("module") or {}).get("version")
    if version is None or str(version).strip() == "":
        return ""
    candidate = str(version).strip()
    if is_valid_version(candidate):
        return candidate
    try:
        return version_from_legacy(candidate)
    except ValueError:
        return ""


# Backward-compatible: list of HF repo IDs extracted from sources
DEFAULT_REPOS: list[str] = [
    s.hf_repo_id for s in MODULES_CONFIG.sources
    if s.is_hf and s.hf_repo_id is not None
]


def get_module_meta(name: str) -> ModuleMetadata:
    """
    Get display metadata for a module.

    Returns the YAML override if present, otherwise auto-generates
    sensible defaults from the module folder name.
    """
    if name in MODULES_CONFIG.module_metadata:
        meta = MODULES_CONFIG.module_metadata[name]
        title = meta.title or name.replace("_", " ").title()
        return ModuleMetadata(
            title=title,
            description=meta.description or f"Annotation module: {name}",
            report_title=meta.report_title or title,
            icon=meta.icon,
            color=meta.color,
        )
    # Fully auto-generated for unknown modules
    title = name.replace("_", " ").title()
    return ModuleMetadata(
        title=title,
        description=f"Annotation module: {name}",
        report_title=title,
        icon=_DEFAULT_ICON,
        color=_DEFAULT_COLOR,
    )


def get_module_display_name(name: str) -> str:
    """Get the report/display title for a module."""
    return get_module_meta(name).report_title or name.replace("_", " ").title()


def get_module_description(name: str) -> str:
    """Get the description for a module."""
    return get_module_meta(name).description or f"Annotation module: {name}"


def build_module_metadata_dict(module_names: list[str]) -> dict[str, dict[str, str]]:
    """
    Build a MODULE_METADATA-style dict for a list of discovered module names.

    Returns a dict compatible with the format used by webui state.py:
        {name: {"title": ..., "description": ..., "icon": ..., "color": ...}}
    """
    result: dict[str, dict[str, str]] = {}
    for name in module_names:
        meta = get_module_meta(name)
        result[name] = {
            "title": meta.title or name,
            "description": meta.description or "",
            "icon": meta.icon,
            "color": meta.color,
        }
    return result


def build_display_names_dict(module_names: list[str]) -> dict[str, str]:
    """
    Build a MODULE_DISPLAY_NAMES-style dict for a list of discovered module names.

    Returns {name: report_title} compatible with report_logic.py.
    """
    return {name: get_module_display_name(name) for name in module_names}
