"""
Module Creator Agent: turns research papers / variant lists into annotation modules.

All declarative config (system prompt, model settings, agent name) lives in
module_creator.yaml next to this file. This module is pure wiring: it loads
the YAML spec, builds Agno tools from the module_registry API, and exposes
factory + runner functions.

Decoupled from the web UI -- usable from CLI, tests, or programmatically.
"""
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv

from agno.agent import Agent
from agno.models.google import Gemini
from agno.tools.mcp import MCPTools

load_dotenv()

_SPEC_PATH = Path(__file__).parent / "module_creator.yaml"
BIOCONTEXT_KB_URL = "https://biocontext-kb.fastmcp.app/mcp"


def _load_agent_spec() -> Dict[str, Any]:
    """Load the declarative agent spec from the co-located YAML file."""
    return yaml.safe_load(_SPEC_PATH.read_text(encoding="utf-8"))


def _resolve_model_id(spec: Dict[str, Any], override: Optional[str] = None) -> str:
    """Resolve model ID: explicit override > env var > YAML default."""
    if override:
        return override
    model_cfg = spec.get("model", {})
    env_key = model_cfg.get("env_override", "GEMINI_MODEL")
    return os.getenv(env_key) or model_cfg.get("default_id", "gemini-3-pro-preview")


def _resolve_api_key() -> str:
    """Resolve Gemini API key from environment."""
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ValueError("Set GEMINI_API_KEY or GOOGLE_API_KEY in environment / .env")
    return key


# ---------------------------------------------------------------------------
# Tool implementations (stateless, called by the agent)
# ---------------------------------------------------------------------------

def _write_spec_files(
    spec_dir: Path,
    module_name: str,
    title: str,
    description: str,
    report_title: str,
    icon: str,
    color: str,
    variants_csv_content: str,
    studies_csv_content: Optional[str] = None,
    version: int = 1,
) -> str:
    """Persist module_spec.yaml + CSV files to disk."""
    spec_dir.mkdir(parents=True, exist_ok=True)

    yaml_content = (
        f'schema_version: "1.0"\n\n'
        f"module:\n"
        f"  name: {module_name}\n"
        f"  version: {version}\n"
        f'  title: "{title}"\n'
        f'  description: "{description}"\n'
        f'  report_title: "{report_title}"\n'
        f"  icon: {icon}\n"
        f'  color: "{color}"\n\n'
        f"defaults:\n"
        f"  curator: ai-module-creator\n"
        f"  method: literature-review\n"
        f"  priority: medium\n\n"
        f"genome_build: GRCh38\n"
    )
    (spec_dir / "module_spec.yaml").write_text(yaml_content, encoding="utf-8")
    (spec_dir / "variants.csv").write_text(variants_csv_content, encoding="utf-8")

    files_written = ["module_spec.yaml", "variants.csv"]
    if studies_csv_content and studies_csv_content.strip():
        (spec_dir / "studies.csv").write_text(studies_csv_content, encoding="utf-8")
        files_written.append("studies.csv")

    return f"Spec files written to {spec_dir}: {', '.join(files_written)}"


def _validate_spec(spec_dir: str) -> str:
    """Validate a DSL spec directory (dry-run, no side effects)."""
    from just_dna_pipelines.module_registry import validate_module_spec

    result = validate_module_spec(Path(spec_dir))
    if result.valid:
        stats = result.stats or {}
        return (
            f"VALID. Module '{stats.get('module_name', '?')}': "
            f"{stats.get('variant_rows', '?')} variant rows, "
            f"{stats.get('unique_rsids', '?')} unique rsids, "
            f"categories: {stats.get('categories', '?')}. "
            f"Warnings: {result.warnings or 'none'}"
        )
    return f"INVALID. Errors: {result.errors}. Warnings: {result.warnings or 'none'}"


def _register_module(spec_dir: str) -> str:
    """Compile and register a module (writes parquet, updates modules.yaml)."""
    from just_dna_pipelines.module_registry import register_custom_module

    result = register_custom_module(Path(spec_dir))
    if result.success:
        stats = result.stats or {}
        return (
            f"SUCCESS. Module '{stats.get('module_name', '?')}' registered. "
            f"Output: {result.output_dir}. "
            f"Weights: {stats.get('weights_rows', '?')} rows, "
            f"Annotations: {stats.get('annotations_rows', '?')} rows."
        )
    return f"FAILED. Errors: {result.errors}. Warnings: {result.warnings or 'none'}"


def read_spec_meta(spec_dir: Path) -> Dict[str, Any]:
    """Read module metadata from a spec directory's module_spec.yaml.

    Returns dict with keys: name, version, title, description, report_title, icon, color.
    Returns empty dict if the yaml is missing or unparseable.
    """
    yaml_path = spec_dir / "module_spec.yaml"
    if not yaml_path.exists():
        return {}
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    module = raw.get("module", {})
    if not isinstance(module, dict):
        return {}
    return {
        "name": module.get("name", ""),
        "version": int(module.get("version", 1)),
        "title": module.get("title", ""),
        "description": module.get("description", ""),
        "report_title": module.get("report_title", ""),
        "icon": module.get("icon", "database"),
        "color": module.get("color", "#6435c9"),
    }


def bump_spec_version(spec_dir: Path, new_version: int) -> None:
    """Rewrite version field in an existing module_spec.yaml.

    If the file already has a ``version:`` line, its value is replaced.
    Otherwise a ``version:`` line is inserted right after ``name:``.
    """
    yaml_path = spec_dir / "module_spec.yaml"
    if not yaml_path.exists():
        return
    content = yaml_path.read_text(encoding="utf-8")
    if re.search(r"^\s*version:\s*\d+", content, flags=re.MULTILINE):
        updated = re.sub(
            r"^(\s*version:\s*)\d+",
            rf"\g<1>{new_version}",
            content,
            count=1,
            flags=re.MULTILINE,
        )
    else:
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith("name:"):
                indent = " " * (len(line) - len(line.lstrip()))
                lines.insert(i + 1, f"{indent}version: {new_version}")
                break
        updated = "\n".join(lines)
    yaml_path.write_text(updated, encoding="utf-8")


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

def create_module_agent(
    model_id: Optional[str] = None,
    spec_output_dir: Optional[Path] = None,
) -> Agent:
    """Create an Agno agent from the declarative YAML spec.

    Args:
        model_id: Override Gemini model ID (else env / YAML default).
        spec_output_dir: Base directory for writing spec files.
            Defaults to a temp directory.

    Returns:
        Configured Agno Agent ready to process module creation requests.
    """
    spec = _load_agent_spec()
    resolved_model = _resolve_model_id(spec, model_id)
    api_key = _resolve_api_key()
    output_dir = spec_output_dir or Path(tempfile.mkdtemp(prefix="module_spec_"))

    agent_cfg = spec.get("agent", {})

    # Closures that bind output_dir for the agent's tool calls
    def write_spec_files(
        module_name: str,
        title: str,
        description: str,
        report_title: str,
        icon: str,
        color: str,
        variants_csv_content: str,
        studies_csv_content: str = "",
    ) -> str:
        """Write module_spec.yaml and CSV files to the output directory.

        Args:
            module_name: Machine name (lowercase, underscores only).
            title: Human-readable title.
            description: One-liner description.
            report_title: Report section title.
            icon: Icon name for UI display.
            color: Hex color string for UI display.
            variants_csv_content: Full CSV content for variants.csv including header row.
            studies_csv_content: Full CSV content for studies.csv including header row (empty string if none).
        """
        return _write_spec_files(
            spec_dir=output_dir / module_name,
            module_name=module_name,
            title=title,
            description=description,
            report_title=report_title,
            icon=icon,
            color=color,
            variants_csv_content=variants_csv_content,
            studies_csv_content=studies_csv_content,
        )

    def validate_spec(spec_dir: str) -> str:
        """Validate a module spec directory for correctness (dry-run, no side effects).

        Args:
            spec_dir: Path to the spec directory containing module_spec.yaml and CSV files.
        """
        return _validate_spec(spec_dir)

    def register_module(spec_dir: str) -> str:
        """Compile and register a validated module (writes parquet, updates config).

        Args:
            spec_dir: Path to the spec directory containing module_spec.yaml and CSV files.
        """
        return _register_module(spec_dir)

    def write_module_md(module_name: str, markdown_content: str) -> str:
        """Write or update the MODULE.md documentation file for a module.

        Call this to create or update the module's story / changelog / design
        notes.  If a MODULE.md already exists, the new content replaces it
        entirely — make sure to include everything that should be preserved.

        Args:
            module_name: Machine name matching the module (same as in module_spec.yaml).
            markdown_content: Full markdown content for MODULE.md.
        """
        md_path = output_dir / module_name / "MODULE.md"
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(markdown_content, encoding="utf-8")
        return f"MODULE.md written to {md_path} ({len(markdown_content)} chars)"

    biocontext = MCPTools(url=BIOCONTEXT_KB_URL)

    return Agent(
        name=spec.get("name", "ModuleCreator"),
        description=spec.get("description", ""),
        model=Gemini(id=resolved_model, api_key=api_key, vertexai=False), #search=True disables tool calls
        tools=[write_spec_files, validate_spec, register_module, write_module_md, biocontext],
        instructions=spec.get("instructions", ""),
        markdown=agent_cfg.get("markdown", True),
        debug_mode=agent_cfg.get("debug_mode", False),
    )


# ---------------------------------------------------------------------------
# Convenience runner
# ---------------------------------------------------------------------------

def run_agent_sync(
    message: str,
    file_path: Optional[Path] = None,
    model_id: Optional[str] = None,
    spec_output_dir: Optional[Path] = None,
    show_tool_calls: bool = False,
) -> str:
    """Run the module creator agent synchronously and return its response text.

    Args:
        message: User message / instructions for the agent.
        file_path: Optional PDF/CSV file to include as context.
        model_id: Override Gemini model ID.
        spec_output_dir: Override spec output directory.
        show_tool_calls: If True, print tool call info to stdout.

    Returns:
        Agent response text (markdown).
    """
    agent = create_module_agent(model_id=model_id, spec_output_dir=spec_output_dir)

    kwargs: dict = {"show_tool_calls": show_tool_calls}
    if file_path and file_path.exists():
        from agno.media import File
        kwargs["files"] = [File(filepath=file_path)]

    response = agent.run(message, **kwargs)
    return response.content if response and response.content else ""
