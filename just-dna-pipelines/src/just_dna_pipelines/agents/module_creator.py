"""
Module Creator Team: multi-agent team that researches, drafts, reviews, and
compiles annotation modules.

All declarative config (system prompts, model settings, team structure) lives
in the prompts/ directory as per-role YAML files (team.yaml, pi.yaml,
researcher.yaml, reviewer.yaml). This module is pure wiring: it loads
the YAML specs, builds Agno agents and a Team, and exposes factory + runner
functions.

Architecture:
  - Researchers (1-3): each uses a different LLM (Gemini/Claude/OpenAI based
    on available API keys) with BioContext MCP tools for variant research.
  - Reviewer (1): Gemini with built-in Google Search for fact-checking drafts.
  - Principal Investigator (team leader): Gemini Pro, coordinates the team,
    holds the write/validate/register tools, produces the final module.

Decoupled from the web UI -- usable from CLI, tests, or programmatically.
"""
import asyncio
import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml
from dotenv import load_dotenv

from agno.agent import Agent, RunEvent
from agno.media import File as AgnoFile
from agno.models.anthropic import Claude
from agno.models.google import Gemini
from agno.models.openai import OpenAIResponses
from agno.team.mode import TeamMode
from agno.team.team import Team, TeamRunEvent
from agno.tools.mcp import MCPTools

from just_dna_pipelines.module_registry import register_custom_module, validate_module_spec

load_dotenv()

logger = logging.getLogger(__name__)

StatusCallback = Callable[[str], None]
# (event_type, label, detail, call_id) — event_type is one of:
#   "tool_pi"  "tool_pi_done"  "tool_member"  "tool_member_done"
# call_id links a _done event back to its corresponding start event so the
# UI can merge them in-place rather than appending a separate row.
EventCallback = Callable[[str, str, str, str], Any]


def _fmt_detail(obj: Any, max_chars: int = 2000) -> str:
    """Format tool args/result for display, truncating if necessary."""
    if obj is None:
        return ""
    text = obj if isinstance(obj, str) else json.dumps(obj, indent=2, default=str)
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n… ({len(text) - max_chars} chars truncated)"
    return text

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_SOLO_SPEC_PATH = _PROMPTS_DIR / "module_creator.yaml"
BIOCONTEXT_KB_URL = "https://biocontext-kb.fastmcp.app/mcp"
MAX_ATTACHMENTS = 5


def _load_prompt(name: str) -> Dict[str, Any]:
    """Load a single YAML prompt file from the prompts/ directory."""
    path = _PROMPTS_DIR / f"{name}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_agent_spec() -> Dict[str, Any]:
    """Load all prompt files and merge into a single spec dict."""
    team = _load_prompt("team")
    pi = _load_prompt("pi")
    researcher = _load_prompt("researcher")
    reviewer = _load_prompt("reviewer")
    team["instructions"] = pi.get("instructions", "")
    team["researcher_model"] = researcher.get("model", {})
    team["researcher_instructions"] = researcher.get("instructions", "")
    team["reviewer_model"] = reviewer.get("model", {})
    team["reviewer_instructions"] = reviewer.get("instructions", "")
    return team


def _resolve_model_id(spec: Dict[str, Any], override: Optional[str] = None) -> str:
    """Resolve PI model ID: explicit override > env var > YAML default."""
    if override:
        return override
    model_cfg = spec.get("model", {})
    env_key = model_cfg.get("env_override", "GEMINI_MODEL")
    return os.getenv(env_key) or model_cfg.get("default_id", "gemini-3-pro-preview")


def _resolve_gemini_api_key() -> str:
    """Resolve Gemini API key from environment."""
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ValueError("Set GEMINI_API_KEY or GOOGLE_API_KEY in environment / .env")
    return key


# ---------------------------------------------------------------------------
# Dynamic model detection
# ---------------------------------------------------------------------------

def _available_researcher_models(
    gemini_api_key: str,
    spec: Dict[str, Any],
) -> List[Tuple[str, Any]]:
    """Build list of (display_name, model_instance) for available API keys.

    Always includes at least one Gemini researcher. Adds OpenAI and/or
    Anthropic researchers when their API keys are present.
    """
    researcher_model_id = spec.get("researcher_model", {}).get(
        "default_id", "gemini-3-pro-preview"
    )

    models: List[Tuple[str, Any]] = [
        (
            f"Gemini ({researcher_model_id})",
            Gemini(id=researcher_model_id, api_key=gemini_api_key, vertexai=False),
        ),
    ]

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        models.append(("OpenAI (gpt-4.1)", OpenAIResponses(id="gpt-5.2")))

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        models.append(("Claude (claude-sonnet-4-5-20250929)", Claude(id="claude-sonnet-4-5-20250929")))

    return models


# ---------------------------------------------------------------------------
# Tool implementations (stateless, called by the PI agent)
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
# Agent builders
# ---------------------------------------------------------------------------

def _build_researchers(
    spec: Dict[str, Any],
    gemini_api_key: str,
) -> List[Agent]:
    """Create researcher agents -- one per available model.

    Each researcher gets its own MCPTools instance (shared instances can cause
    connection-reuse issues when agents run concurrently).

    compress_tool_results=True prevents context overflow from large BioContext
    payloads -- critical for Claude researchers capped at 200k tokens.
    tool_call_limit caps MCP query depth to avoid runaway token accumulation.
    """
    models = _available_researcher_models(gemini_api_key, spec)
    researcher_instructions = spec.get("researcher_instructions", "")
    tool_call_limit = spec.get("researcher_tool_call_limit", 9)  # 3 tools × 3 queries

    researchers: List[Agent] = []
    for i, (display_name, model) in enumerate(models, 1):
        researchers.append(
            Agent(
                name=f"Researcher {i}",
                role=f"Genetics variant researcher ({display_name})",
                model=model,
                tools=[MCPTools(url=BIOCONTEXT_KB_URL)],
                instructions=researcher_instructions,
                markdown=True,
                compress_tool_results=True,
                tool_call_limit=tool_call_limit,
            )
        )

    return researchers


def _build_reviewer(
    spec: Dict[str, Any],
    gemini_api_key: str,
) -> Agent:
    """Create the reviewer/critic agent with Google Search for fact-checking."""
    reviewer_model_id = spec.get("reviewer_model", {}).get(
        "default_id", "gemini-3-flash-preview"
    )
    reviewer_instructions = spec.get("reviewer_instructions", "")

    return Agent(
        name="Reviewer",
        role="Quality reviewer — checks draft modules for errors and fact-checks claims via Google Search",
        model=Gemini(
            id=reviewer_model_id,
            api_key=gemini_api_key,
            vertexai=False,
            search=True,
        ),
        instructions=reviewer_instructions,
        markdown=True,
    )


# ---------------------------------------------------------------------------
# Shared tool builder (used by both team PI and solo agent)
# ---------------------------------------------------------------------------

def _generate_logo_image(module_name: str, prompt: str, output_dir: Path, api_key: str) -> str:
    """Generate a module logo via a small agno Agent with GeminiTools (Imagen 3)."""
    from agno.tools.models.gemini import GeminiTools

    logo_agent = Agent(
        model=Gemini(id="gemini-2.0-flash", api_key=api_key, vertexai=False),
        tools=[GeminiTools(api_key=api_key)],
    )
    try:
        response = logo_agent.run(f"Generate an image: {prompt}")
    except Exception as exc:
        return f"Logo generation failed: {exc}"

    if not (response and response.images):
        return "Logo generation returned no image."

    logo_path = output_dir / module_name / "logo.png"
    logo_path.parent.mkdir(parents=True, exist_ok=True)
    logo_path.write_bytes(response.images[0].content)
    return f"Logo saved to {logo_path}"


def _build_pi_tools(output_dir: Path, api_key: str) -> List[Any]:
    """Return the list of PI tool functions bound to *output_dir*."""

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
        entirely -- make sure to include everything that should be preserved.

        Args:
            module_name: Machine name matching the module (same as in module_spec.yaml).
            markdown_content: Full markdown content for MODULE.md.
        """
        md_path = output_dir / module_name / "MODULE.md"
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(markdown_content, encoding="utf-8")
        return f"MODULE.md written to {md_path} ({len(markdown_content)} chars)"

    def generate_logo(module_name: str, prompt: str) -> str:
        """Generate a square logo image for the module using Gemini image generation.

        The logo is saved as logo.png inside the module's spec directory.
        Call this after write_module_md as the final step.

        Args:
            module_name: Machine name of the module (same as in module_spec.yaml).
            prompt: Visual description for the logo — include style, dominant colors,
                    symbolic elements, and the module's health/genetics theme.
                    Example: "Minimalist flat icon of a DNA helix intertwined with a heart,
                    deep purple gradient, white background, clean vector style."
        """
        return _generate_logo_image(module_name, prompt, output_dir, api_key)

    return [write_spec_files, validate_spec, register_module, write_module_md, generate_logo]


# ---------------------------------------------------------------------------
# Team factory
# ---------------------------------------------------------------------------

def create_module_team(
    model_id: Optional[str] = None,
    spec_output_dir: Optional[Path] = None,
) -> Team:
    """Create an Agno Team for module creation.

    Args:
        model_id: Override Gemini model ID for the PI (else env / YAML default).
        spec_output_dir: Base directory for writing spec files.
            Defaults to a temp directory.

    Returns:
        Configured Agno Team ready to process module creation requests.
    """
    spec = _load_agent_spec()
    resolved_model = _resolve_model_id(spec, model_id)
    api_key = _resolve_gemini_api_key()
    output_dir = spec_output_dir or Path(tempfile.mkdtemp(prefix="module_spec_"))
    team_cfg = spec.get("team", {})

    researchers = _build_researchers(spec, api_key)
    reviewer = _build_reviewer(spec, api_key)

    return Team(
        name=spec.get("name", "ModuleCreatorTeam"),
        description=spec.get("description", ""),
        model=Gemini(id=resolved_model, api_key=api_key, vertexai=False),
        members=researchers + [reviewer],
        mode="coordinate",
        tools=_build_pi_tools(output_dir, api_key),
        instructions=spec.get("instructions", ""),
        show_members_responses=team_cfg.get("show_members_responses", True),
        markdown=team_cfg.get("markdown", True),
        debug_mode=team_cfg.get("debug_mode", True),
    #    debug_level=2,
        max_iterations=team_cfg.get("max_iterations", 10),
    )


# ---------------------------------------------------------------------------
# Solo agent factory
# ---------------------------------------------------------------------------

def create_module_agent_solo(
    model_id: Optional[str] = None,
    spec_output_dir: Optional[Path] = None,
) -> Agent:
    """Create a single Agno Agent for module creation (no sub-team).

    Uses the declarative config from ``module_creator.yaml``.  The agent has
    all PI tools plus BioContext MCP tools for variant research — it works
    alone without delegating to researchers or a reviewer.

    Args:
        model_id: Override Gemini model ID (else env / YAML default).
        spec_output_dir: Base directory for writing spec files.

    Returns:
        Configured Agno Agent ready to process module creation requests.
    """
    spec = yaml.safe_load(_SOLO_SPEC_PATH.read_text(encoding="utf-8"))
    resolved_model = _resolve_model_id(spec, model_id)
    api_key = _resolve_gemini_api_key()
    output_dir = spec_output_dir or Path(tempfile.mkdtemp(prefix="module_spec_"))
    agent_cfg = spec.get("agent", {})

    biocontext = MCPTools(url=BIOCONTEXT_KB_URL)

    return Agent(
        name=spec.get("name", "ModuleCreator"),
        model=Gemini(id=resolved_model, api_key=api_key, vertexai=False),
        tools=_build_pi_tools(output_dir, api_key) + [biocontext],
        instructions=spec.get("instructions", ""),
        markdown=agent_cfg.get("markdown", True),
        debug_mode=agent_cfg.get("debug_mode", False),
    )


def create_module_agent(
    model_id: Optional[str] = None,
    spec_output_dir: Optional[Path] = None,
) -> Team:
    """Backward-compatible alias for create_module_team()."""
    return create_module_team(model_id=model_id, spec_output_dir=spec_output_dir)


# ---------------------------------------------------------------------------
# Team description for status messages
# ---------------------------------------------------------------------------

def _describe_team(team: Team) -> str:
    """Human-readable one-liner describing team composition."""
    parts: List[str] = []
    for member in team.members or []:
        if isinstance(member, Agent):
            parts.append(f"{member.name} ({member.role or 'agent'})")
    return ", ".join(parts)


def _build_attachment_files(
    file_path: Optional[Path] = None,
    file_paths: Optional[List[Path]] = None,
) -> List[AgnoFile]:
    """Collect and validate attachment files for team.run().

    Accepts legacy single ``file_path`` and/or ``file_paths`` list.
    Non-existent paths are ignored for backward compatibility.
    """
    candidate_paths: List[Path] = []
    if file_path:
        candidate_paths.append(file_path)
    if file_paths:
        candidate_paths.extend(file_paths)

    unique_paths: List[Path] = []
    seen: set = set()
    for candidate in candidate_paths:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique_paths.append(candidate)

    existing_paths = [path for path in unique_paths if path.exists()]
    if len(existing_paths) > MAX_ATTACHMENTS:
        raise ValueError(f"At most {MAX_ATTACHMENTS} attachments are supported")

    return [AgnoFile(filepath=path) for path in existing_paths]


# ---------------------------------------------------------------------------
# Convenience runners (with status callbacks)
# ---------------------------------------------------------------------------

async def run_agent_async(
    message: str,
    file_path: Optional[Path] = None,
    file_paths: Optional[List[Path]] = None,
    model_id: Optional[str] = None,
    spec_output_dir: Optional[Path] = None,
    on_status: Optional[StatusCallback] = None,
    on_event: Optional[EventCallback] = None,
) -> str:
    """Run the solo module creator agent with agno event streaming.

    Args:
        message: User message / instructions for the agent.
        file_path: Optional single PDF/CSV file to include as context (legacy).
        file_paths: Optional list of attachment files to include as context (max 5).
        model_id: Override Gemini model ID.
        spec_output_dir: Override spec output directory.
        on_status: Optional callback for plain progress label updates.
        on_event: Optional callback for structured tool-call events
            ``(event_type, label, detail, call_id)``.

    Returns:
        Agent response text (markdown).
    """
    async def _emit(msg: str) -> None:
        if on_status:
            result = on_status(msg)
            if asyncio.iscoroutine(result):
                await result

    async def _emit_event(
        event_type: str, label: str, detail: str = "", call_id: str = ""
    ) -> None:
        await _emit(label)
        if on_event:
            result = on_event(event_type, label, detail, call_id)
            if asyncio.iscoroutine(result):
                await result

    await _emit("Preparing agent...")
    agent = create_module_agent_solo(model_id=model_id, spec_output_dir=spec_output_dir)
    await _emit("Agent ready")

    kwargs: Dict[str, Any] = {}
    attachment_files = _build_attachment_files(file_path=file_path, file_paths=file_paths)
    if attachment_files:
        kwargs["files"] = attachment_files

    content_chunks: List[str] = []

    async for event in agent.arun(message, stream=True, stream_events=True, **kwargs):
        if event.event == RunEvent.run_started:
            await _emit("Agent run started")

        elif event.event == RunEvent.run_completed:
            await _emit("Agent run completed")

        elif event.event == RunEvent.tool_call_started:
            tool_name = event.tool.tool_name if event.tool else "unknown"
            args = event.tool.tool_args if event.tool else {}
            cid = (event.tool.tool_call_id or "") if event.tool else ""
            await _emit_event("tool_pi", tool_name, _fmt_detail(args), cid)

        elif event.event == RunEvent.tool_call_completed:
            tool_name = event.tool.tool_name if event.tool else "unknown"
            result = event.tool.result if event.tool else None
            cid = (event.tool.tool_call_id or "") if event.tool else ""
            await _emit_event("tool_pi_done", f"{tool_name} \u2713", _fmt_detail(result), cid)

        elif event.event == RunEvent.run_content:
            if event.content:
                content_chunks.append(event.content)

    await _emit("Agent finished. Processing results...")
    return "".join(content_chunks)


async def run_team_async(
    message: str,
    file_path: Optional[Path] = None,
    file_paths: Optional[List[Path]] = None,
    model_id: Optional[str] = None,
    spec_output_dir: Optional[Path] = None,
    on_status: Optional[StatusCallback] = None,
    on_event: Optional[EventCallback] = None,
) -> str:
    """Run the module creator team with agno event streaming.

    Lifecycle progress is reported via ``on_status`` (spinner label updates).
    Structured tool-call events (with args/result detail) are reported via
    ``on_event(event_type, label, detail)``.

    Args:
        message: User message / instructions for the team.
        file_path: Optional single PDF/CSV file to include as context (legacy).
        file_paths: Optional list of attachment files to include as context (max 5).
        model_id: Override Gemini model ID for the PI.
        spec_output_dir: Override spec output directory.
        on_status: Optional callback for plain progress label updates.
        on_event: Optional callback for structured tool-call events
            ``(event_type, label, detail, call_id)``.

    Returns:
        Team response text (markdown).
    """
    async def _emit(msg: str) -> None:
        if on_status:
            result = on_status(msg)
            if asyncio.iscoroutine(result):
                await result

    async def _emit_event(
        event_type: str, label: str, detail: str = "", call_id: str = ""
    ) -> None:
        await _emit(label)
        if on_event:
            result = on_event(event_type, label, detail, call_id)
            if asyncio.iscoroutine(result):
                await result

    def _pi_tool_label(tool_name: str, args: Dict[str, Any]) -> str:
        """Human-friendly label for a PI tool call."""
        if tool_name == "delegate_task_to_member":
            target = args.get("member_id") or args.get("member_name") or "member"
            return f"PI \u2192 {target}"
        if tool_name == "delegate_task_to_members":
            return "PI \u2192 all members"
        return f"PI: {tool_name}"

    await _emit("Assembling research team...")
    team = create_module_team(model_id=model_id, spec_output_dir=spec_output_dir)
    await _emit(f"Team ready: {_describe_team(team)}")

    kwargs: Dict[str, Any] = {}
    attachment_files = _build_attachment_files(file_path=file_path, file_paths=file_paths)
    if attachment_files:
        kwargs["files"] = attachment_files

    content_chunks: List[str] = []

    async for event in team.arun(message, stream=True, stream_events=True, **kwargs):
        if event.event == TeamRunEvent.run_started:
            await _emit("Team run started")

        elif event.event == TeamRunEvent.run_completed:
            await _emit("Team run completed")

        elif event.event == TeamRunEvent.tool_call_started:
            tool_name = event.tool.tool_name if event.tool else "unknown"
            args = event.tool.tool_args if event.tool else {}
            cid = (event.tool.tool_call_id or "") if event.tool else ""
            label = _pi_tool_label(tool_name, args)
            await _emit_event("tool_pi", label, _fmt_detail(args), cid)

        elif event.event == TeamRunEvent.tool_call_completed:
            tool_name = event.tool.tool_name if event.tool else "unknown"
            args = event.tool.tool_args if event.tool else {}
            result = event.tool.result if event.tool else None
            cid = (event.tool.tool_call_id or "") if event.tool else ""
            label = _pi_tool_label(tool_name, args)
            await _emit_event("tool_pi_done", f"{label} \u2713", _fmt_detail(result), cid)

        elif event.event == RunEvent.tool_call_started:
            agent_name = getattr(event, "agent_name", None) or getattr(event, "agent_id", None) or "agent"
            tool_name = event.tool.tool_name if event.tool else "unknown"
            args = event.tool.tool_args if event.tool else {}
            cid = (event.tool.tool_call_id or "") if event.tool else ""
            await _emit_event("tool_member", f"{agent_name}: {tool_name}", _fmt_detail(args), cid)

        elif event.event == RunEvent.tool_call_completed:
            agent_name = getattr(event, "agent_name", None) or getattr(event, "agent_id", None) or "agent"
            tool_name = event.tool.tool_name if event.tool else "unknown"
            result = event.tool.result if event.tool else None
            cid = (event.tool.tool_call_id or "") if event.tool else ""
            await _emit_event("tool_member_done", f"{agent_name}: {tool_name} \u2713", _fmt_detail(result), cid)

        elif event.event == TeamRunEvent.run_content:
            if event.content:
                content_chunks.append(event.content)
        else:
            if event.event.startswith("Team"):
                await _emit(f"Last team run event: {event.event}")

    await _emit("Team finished. Processing results...")
    return "".join(content_chunks)
