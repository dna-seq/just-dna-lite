"""
Module Registry: compile DSL specs, persist to modules.yaml, refresh discovery.

Public API (Python — usable from agent tools, UI, or scripts):
    validate_module_spec(spec_dir)     → ValidationResult
    register_custom_module(spec_dir)   → CompilationResult
    unregister_custom_module(name)     → bool
    list_custom_modules()              → list[str]
    get_custom_module_specs()          → dict[str, Path]
    refresh_module_registry()          → list[str]

CLI (via ``uv run pipelines module``):
    module register  <spec_dir>        compile + register + refresh
    module unregister <name>           remove + refresh
    module list-custom                 list custom modules on disk

This is the single entry point for both the web UI and agent tools.
Calling ``register_custom_module`` compiles a DSL spec folder into
parquet, updates ``modules.yaml``, and refreshes the in-process
module discovery globals so changes take effect immediately.
"""

import shutil
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from eliot import log_message

from just_dna_pipelines.module_compiler import CompilationResult, ModuleSpecConfig, ValidationResult, validate_spec
from just_dna_pipelines.module_compiler.compiler import compile_module
from just_dna_pipelines.module_compiler.resolver import ensure_resolver_db
from just_dna_pipelines.annotation.resources import get_registered_modules_dir
from just_dna_pipelines.module_config import (
    ModuleMetadata,
    ModulesConfig,
    Source,
    get_config_path,
    save_config,
)

CUSTOM_MODULES_DIR: Path = get_registered_modules_dir()


def _read_spec_metadata(spec_dir: Path) -> Optional[ModuleSpecConfig]:
    """Read module_spec.yaml and return parsed config, or None on failure."""
    yaml_path = spec_dir / "module_spec.yaml"
    if not yaml_path.exists():
        return None
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if raw is None:
        return None
    return ModuleSpecConfig.model_validate(raw)


def _ensure_local_source(config: ModulesConfig) -> ModulesConfig:
    """Ensure the local collection source pointing to CUSTOM_MODULES_DIR exists."""
    local_url = str(CUSTOM_MODULES_DIR)
    for source in config.sources:
        if source.url == local_url:
            return config
    config.sources.append(Source(url=local_url, kind="collection"))
    return config


def _remove_local_source_if_empty(config: ModulesConfig) -> ModulesConfig:
    """Remove the local collection source if no custom modules remain on disk."""
    if CUSTOM_MODULES_DIR.exists() and any(CUSTOM_MODULES_DIR.iterdir()):
        return config
    local_url = str(CUSTOM_MODULES_DIR)
    config.sources = [s for s in config.sources if s.url != local_url]
    return config


def validate_module_spec(spec_dir: Path) -> ValidationResult:
    """Validate a DSL spec directory without any side effects.

    Use this as a dry-run check before calling ``register_custom_module``.
    Returns a ``ValidationResult`` with ``valid``, ``errors``, ``warnings``,
    and ``stats`` (module_name, variant_rows, unique_rsids, categories, etc.).

    Args:
        spec_dir: Path to a folder containing module_spec.yaml + CSVs.

    Returns:
        ValidationResult — check ``.valid`` for pass/fail.
    """
    return validate_spec(Path(spec_dir))


def register_custom_module(
    spec_dir: Path,
    resolve_with_ensembl: bool = True,
    ensembl_cache: Optional[Path] = None,
) -> CompilationResult:
    """Compile a DSL spec, persist to modules.yaml, and refresh discovery.

    This is idempotent: re-registering the same spec overwrites the
    existing parquet and refreshes metadata.

    Args:
        spec_dir: Path to a folder containing module_spec.yaml + CSVs.
        resolve_with_ensembl: Whether to resolve missing rsid/position via Ensembl.
        ensembl_cache: Explicit Ensembl cache path (None = default).

    Returns:
        CompilationResult with success status, errors, warnings, and stats.
    """
    spec_dir = Path(spec_dir)

    validation = validate_spec(spec_dir)
    if not validation.valid:
        return CompilationResult(
            success=False,
            errors=validation.errors,
            warnings=validation.warnings,
        )

    spec_config = _read_spec_metadata(spec_dir)
    if spec_config is None:
        return CompilationResult(
            success=False,
            errors=["Failed to read module_spec.yaml after validation passed"],
        )

    module_name = spec_config.module.name
    output_dir = CUSTOM_MODULES_DIR / module_name

    # just-dna-compiler is inject-only (it never downloads a reference), so provision the Ensembl
    # DuckDB here and pass it in. ensure_resolver_db is idempotent — cheap when the cache already
    # exists, building/downloading only when absent. On failure, degrade to inject-only: compile
    # skips resolution with a warning rather than erroring.
    if resolve_with_ensembl and ensembl_cache is None:
        try:
            ensembl_cache = ensure_resolver_db()
        except Exception as exc:  # noqa: BLE001 - provisioning is best-effort
            log_message(
                message_type="ensembl_provision_failed",
                module=module_name,
                error=str(exc),
            )

    result = compile_module(
        spec_dir,
        output_dir,
        resolve_with_ensembl=resolve_with_ensembl,
        ensembl_cache=ensembl_cache,
    )
    if not result.success:
        return result

    # Copy source spec files alongside compiled parquets so the module can be
    # loaded back into the editing slot for further editing.
    # Exclude parquets
    # (already written by compile_module).
    _SPEC_SUFFIXES = {".yaml", ".csv", ".md", ".png", ".jpg", ".jpeg", ".log", ".json"}
    for f in spec_dir.iterdir():
        if f.is_file() and f.suffix.lower() in _SPEC_SUFFIXES:
            shutil.copy2(f, output_dir / f.name)

    config_path = get_config_path()
    config = ModulesConfig.model_validate(
        yaml.safe_load(config_path.read_text()) or {}
    ) if config_path.exists() else ModulesConfig()

    config = _ensure_local_source(config)

    module_info = spec_config.module
    config.module_metadata[module_name] = ModuleMetadata(
        title=module_info.title,
        description=module_info.description,
        report_title=module_info.report_title,
        icon=module_info.icon,
        color=module_info.color,
    )

    save_config(config, config_path)

    refreshed = refresh_module_registry()

    log_message(
        message_type="info",
        action="register_custom_module",
        module_name=module_name,
        output_dir=str(output_dir),
        discovered_modules=refreshed,
    )

    return result


def unregister_custom_module(module_name: str) -> bool:
    """Remove a custom module's files and config entries, then refresh discovery.

    Handles stale entries gracefully: if the directory is already gone
    (e.g. path scheme changed), still cleans up config and refreshes.

    Args:
        module_name: The machine name of the module to remove.

    Returns:
        True if any cleanup was performed (files or config), False if
        the module was not found anywhere.
    """
    cleaned_anything = False

    module_dir = CUSTOM_MODULES_DIR / module_name
    if module_dir.exists():
        shutil.rmtree(module_dir)
        cleaned_anything = True

    config_path = get_config_path()
    if config_path.exists():
        config = ModulesConfig.model_validate(
            yaml.safe_load(config_path.read_text()) or {}
        )
    else:
        from just_dna_pipelines.module_config import _load_config
        config = _load_config()

    if module_name in config.module_metadata:
        config.module_metadata.pop(module_name)
        cleaned_anything = True

    config = _remove_local_source_if_empty(config)
    save_config(config, config_path)

    if not cleaned_anything:
        log_message(
            message_type="warning",
            action="unregister_custom_module",
            module_name=module_name,
            message=f"Module not found in files or config: {module_name}",
        )
        return False

    refreshed = refresh_module_registry()

    log_message(
        message_type="info",
        action="unregister_custom_module",
        module_name=module_name,
        discovered_modules=refreshed,
    )

    return True


def register_downloaded_module(module_dir: Path) -> str:
    """Wire an already-compiled module dir into local discovery WITHOUT recompiling.

    Used for registry installs: the tarball we extract into ``CUSTOM_MODULES_DIR/{name}``
    already contains ``weights.parquet`` + ``manifest.json`` (the server-compiled artifact) plus
    the spec inputs. Recompiling here would produce a fresh parquet whose digest no longer matches
    the catalog's, so we only ensure the local collection source exists, copy display metadata from
    the module's ``manifest.json`` (best-effort), and refresh discovery.

    Args:
        module_dir: ``CUSTOM_MODULES_DIR/{name}`` — must contain ``weights.parquet``.

    Returns:
        The module name (``module_dir.name``).
    """
    module_dir = Path(module_dir)
    module_name = module_dir.name

    config_path = get_config_path()
    config = ModulesConfig.model_validate(
        yaml.safe_load(config_path.read_text()) or {}
    ) if config_path.exists() else ModulesConfig()

    config = _ensure_local_source(config)

    manifest_path = module_dir / "manifest.json"
    if manifest_path.exists():
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        display = raw.get("display", {}) if isinstance(raw, dict) else {}
        config.module_metadata[module_name] = ModuleMetadata(
            title=display.get("title", module_name),
            description=display.get("description", ""),
            report_title=display.get("report_title", display.get("title", module_name)),
            icon=display.get("icon", "database"),
            color=display.get("color", "#6435c9"),
        )

    save_config(config, config_path)

    refreshed = refresh_module_registry()

    log_message(
        message_type="info",
        action="register_downloaded_module",
        module_name=module_name,
        module_dir=str(module_dir),
        discovered_modules=refreshed,
    )

    return module_name


def list_custom_modules() -> List[str]:
    """Return names of all compiled custom modules on disk."""
    if not CUSTOM_MODULES_DIR.exists():
        return []
    return sorted(
        d.name for d in CUSTOM_MODULES_DIR.iterdir()
        if d.is_dir() and (d / "weights.parquet").exists()
    )


def get_custom_module_specs() -> Dict[str, Path]:
    """Return {module_name: output_dir} for all custom modules on disk."""
    if not CUSTOM_MODULES_DIR.exists():
        return {}
    result: Dict[str, Path] = {}
    for d in sorted(CUSTOM_MODULES_DIR.iterdir()):
        if d.is_dir() and (d / "weights.parquet").exists():
            result[d.name] = d
    return result


def refresh_module_registry() -> List[str]:
    """Reload modules.yaml, re-discover all modules, update globals.

    Returns:
        Sorted list of all discovered module names.
    """
    from just_dna_pipelines.annotation.hf_modules import refresh_modules

    module_infos = refresh_modules()
    return sorted(module_infos.keys())
