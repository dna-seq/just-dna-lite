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
from just_dna_pipelines.module_config import (
    ModuleMetadata,
    ModulesConfig,
    Source,
    _find_project_root,
    get_config_path,
    save_config,
)

_project_root = _find_project_root() or Path.cwd()
CUSTOM_MODULES_DIR: Path = _project_root / "data" / "output" / "modules"


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
    _SPEC_SUFFIXES = {".yaml", ".csv", ".md"}
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
    """Remove a custom module's parquet, update modules.yaml, refresh discovery.

    Args:
        module_name: The machine name of the module to remove.

    Returns:
        True if the module was found and removed, False otherwise.
    """
    module_dir = CUSTOM_MODULES_DIR / module_name
    if not module_dir.exists():
        log_message(
            message_type="warning",
            action="unregister_custom_module",
            module_name=module_name,
            message=f"Module directory does not exist: {module_dir}",
        )
        return False

    shutil.rmtree(module_dir)

    config_path = get_config_path()
    if config_path.exists():
        config = ModulesConfig.model_validate(
            yaml.safe_load(config_path.read_text()) or {}
        )
    else:
        config = ModulesConfig()

    config.module_metadata.pop(module_name, None)
    config = _remove_local_source_if_empty(config)
    save_config(config, config_path)

    refreshed = refresh_module_registry()

    log_message(
        message_type="info",
        action="unregister_custom_module",
        module_name=module_name,
        discovered_modules=refreshed,
    )

    return True


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
