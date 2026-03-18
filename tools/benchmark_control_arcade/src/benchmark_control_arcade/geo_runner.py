"""GEO benchmark runner using the Claude Agent SDK.

This module provides the Python-side runner for GEO (Generative Engine
Optimization) benchmark runs. It:

1. Loads repo-owned prompt assets (NOT ~/.claude/skills).
2. Configures MCP servers explicitly from Settings.
3. Invokes claude-agent-sdk query() with the system prompt and structured-output
   instructions.
4. Returns the result dict — all file I/O is left to the caller.

No files are written by this module.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    from claude_agent_sdk import ClaudeAgentOptions, query
    from claude_agent_sdk.types import McpHttpServerConfig
except ImportError:  # claude-agent-sdk ships macOS-only wheels; CI runs on Linux
    ClaudeAgentOptions = None  # type: ignore[assignment,misc]
    McpHttpServerConfig = None  # type: ignore[assignment,misc]
    query = None  # type: ignore[assignment]

from benchmark_control_arcade.config import Settings
from benchmark_control_arcade.run_models import RunSpec, RunType

# Paths relative to this file so the package is self-contained.
_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
_SYSTEM_PROMPT_PATH = _PROMPTS_DIR / "geo_site_audit_system.md"
_OUTPUT_SCHEMA_PATH = _PROMPTS_DIR / "geo_site_audit_output_schema.json"


def build_geo_system_prompt() -> str:
    """Load the repo-owned GEO audit system prompt.

    Returns the contents of
    tools/benchmark_control_arcade/prompts/geo_site_audit_system.md.
    This file is a repo asset — it must never reference ~/.claude/skills/.
    """
    return _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def _load_output_schema() -> dict[str, Any]:
    """Load the GEO output JSON schema from repo-owned prompts directory."""
    return json.loads(_OUTPUT_SCHEMA_PATH.read_text(encoding="utf-8"))


def _build_user_prompt(spec: RunSpec) -> str:
    """Construct the user-facing prompt for a GEO run from a RunSpec."""
    target = spec.target
    audit_mode = spec.options.get("audit_mode", "exhaustive")
    extra_instructions = ""
    if spec.options:
        competitors = spec.options.get("competitors")
        if competitors:
            competitor_list = ", ".join(competitors) if isinstance(competitors, list) else competitors
            extra_instructions += f"\nAlso audit these competitor URLs for comparison: {competitor_list}"

    return (
        f"Perform a GEO site audit for: {target}\n"
        f"Audit mode: {audit_mode}\n"
        f"{extra_instructions}\n"
        "Return ONLY a single JSON object conforming to the geo_site_audit_output_schema. "
        "Do not write any files."
    ).strip()


def _extract_json_from_result(text: str) -> dict[str, Any]:
    """Extract the JSON object from the agent's final text response.

    The agent may wrap JSON in a markdown code fence; this handles both cases.
    """
    # Try to find a JSON code block first
    code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if code_block:
        return json.loads(code_block.group(1))

    # Fallback: find the first top-level JSON object in the text
    brace_start = text.find("{")
    if brace_start != -1:
        # Find the matching closing brace
        depth = 0
        for i, ch in enumerate(text[brace_start:], start=brace_start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[brace_start : i + 1])

    raise ValueError(f"No JSON object found in agent response: {text[:200]!r}")


async def run_geo_benchmark(spec: RunSpec, run_id: str, output_dir: Path) -> dict[str, Any]:
    """Run a GEO audit using the Claude Agent SDK.

    Args:
        spec: The RunSpec describing this benchmark run. run_type must be RunType.geo.
        run_id: Unique identifier for this run (used for logging).
        output_dir: The canonical output directory for this run. This function does NOT
            write any files; the directory is accepted so callers can pass it without
            needing to modify the signature later when file writing is added.

    Returns:
        A dict containing at minimum:
            - All fields from geo_site_audit_output_schema.json
            - "overall_score" (int)
            - "report_markdown" (str)

    Raises:
        ValueError: If geo_audit_mcp_url is not configured in Settings.
    """
    if query is None:
        raise RuntimeError(
            "claude-agent-sdk is not installed on this platform. "
            "GEO benchmark runs require macOS (arm64)."
        )
    if spec.run_type is not RunType.geo:
        raise ValueError(f"run_geo_benchmark only handles run_type=geo, got {spec.run_type}")

    settings = Settings()  # type: ignore[call-arg]

    if not settings.geo_audit_mcp_url:
        raise ValueError(
            "geo_audit_mcp_url is required for GEO benchmark runs but is not set. "
            "Set GEO_AUDIT_MCP_URL in your environment or .env file."
        )

    # Build MCP server configuration from Settings
    mcp_servers: dict[str, McpHttpServerConfig] = {
        "geo-audit": McpHttpServerConfig(type="http", url=settings.geo_audit_mcp_url),
    }
    if settings.geo_analyzer_mcp_url:
        mcp_servers["geo-analyzer"] = McpHttpServerConfig(
            type="http", url=settings.geo_analyzer_mcp_url
        )

    system_prompt = build_geo_system_prompt()
    schema = _load_output_schema()

    # Append a compact schema reference to the system prompt so the agent
    # knows exactly what fields are required.
    schema_hint = (
        "\n\n---\n## Required output schema (abridged)\n\n"
        "```json\n"
        + json.dumps(
            {
                "type": schema["type"],
                "required": schema.get("required", []),
                "properties": {
                    k: {"type": v.get("type"), "description": v.get("description", "")}
                    for k, v in schema.get("properties", {}).items()
                },
            },
            indent=2,
        )
        + "\n```"
    )
    full_system_prompt = system_prompt + schema_hint

    options = ClaudeAgentOptions(
        system_prompt=full_system_prompt,
        mcp_servers=mcp_servers,  # type: ignore[arg-type]
        permission_mode="bypassPermissions",
        max_turns=30,
    )

    user_prompt = _build_user_prompt(spec)

    result_text: str | None = None
    async for message in query(prompt=user_prompt, options=options):
        # Collect the last ResultMessage text
        msg_type = type(message).__name__
        if msg_type == "ResultMessage":
            content = getattr(message, "content", None)
            if content:
                for block in content:
                    block_type = getattr(block, "type", None)
                    if block_type == "text":
                        result_text = getattr(block, "text", "")

    if not result_text:
        raise RuntimeError(
            f"GEO benchmark run {run_id} produced no result text from the agent."
        )

    result = _extract_json_from_result(result_text)
    return result
