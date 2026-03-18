"""GEO competitive comparison runner using the Claude Agent SDK.

This module provides the Python-side runner for GEO compare benchmark runs. It:

1. Loads repo-owned prompt assets (NOT ~/.claude/skills).
2. Configures MCP servers explicitly from Settings.
3. Invokes claude-agent-sdk query() with the system prompt and schema instructions.
4. Extracts JSON from the agent response.
5. Writes report.md and report.json via Publisher.
6. Returns {run_id, artifacts, summary} — all GitHub writes are left to the caller.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
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
from benchmark_control_arcade.publisher import Publisher
from benchmark_control_arcade.run_models import RunSpec, RunType

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
_SYSTEM_PROMPT_PATH = _PROMPTS_DIR / "geo_compare_system.md"
_OUTPUT_SCHEMA_PATH = _PROMPTS_DIR / "geo_compare_output_schema.json"

_RUN_ID_RE = re.compile(r"^run-(\d{14})-")


def _parse_created_at_from_run_id(run_id: str) -> datetime | None:
    """Parse the UTC datetime encoded in a run_id (run-YYYYMMDDHHMMSS-<hex>)."""
    m = _RUN_ID_RE.match(run_id)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None


def build_geo_compare_system_prompt() -> str:
    """Load the repo-owned GEO compare system prompt.

    Returns the contents of
    tools/benchmark_control_arcade/prompts/geo_compare_system.md.
    This file is a repo asset — it must never reference ~/.claude/skills/.
    """
    return _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def _load_compare_output_schema() -> dict[str, Any]:
    """Load the GEO compare output JSON schema from repo-owned prompts directory."""
    return json.loads(_OUTPUT_SCHEMA_PATH.read_text(encoding="utf-8"))


def _build_compare_user_prompt(spec: RunSpec) -> str:
    """Construct the user-facing prompt for a geo_compare run from a RunSpec."""
    target = spec.target
    competitors: list[str] = spec.options.get("competitors", [])
    audit_mode: str = spec.options.get("audit_mode", "exhaustive")

    if competitors:
        competitor_list = ", ".join(competitors)
        comparison_clause = f" vs {competitor_list}"
    else:
        comparison_clause = ""

    return (
        f"Audit {target}{comparison_clause} — {audit_mode} mode\n\n"
        "Return ONLY a single JSON object conforming to the geo_compare_output_schema. "
        "Do not write any files."
    ).strip()


def _extract_json_from_result(text: str) -> dict[str, Any]:
    """Extract the JSON object from the agent's final text response.

    The agent may wrap JSON in a markdown code fence; this handles both cases.
    """
    code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if code_block:
        return json.loads(code_block.group(1))

    brace_start = text.find("{")
    if brace_start != -1:
        depth = 0
        for i, ch in enumerate(text[brace_start:], start=brace_start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[brace_start : i + 1])

    raise ValueError(f"No JSON object found in agent response: {text[:200]!r}")


async def run_geo_compare_benchmark(spec: RunSpec, run_id: str, output_dir: Path) -> dict[str, Any]:
    """Run a competitive GEO comparison using the Claude Agent SDK.

    Args:
        spec: The RunSpec for this run. run_type must be RunType.geo_compare.
             spec.target is the primary site; spec.options["competitors"] is the
             list of competitor URLs.
        run_id: Unique identifier for this run (used for Publisher + logging).
        output_dir: Root directory for local output. Publisher writes all files here.

    Returns:
        A dict with:
            run_id       — echoed run_id
            artifacts    — list of paths relative to output_dir
            summary      — {target, competitors, run_date, overall_winner,
                            winner_per_lever, scores}

    Raises:
        ValueError: If geo_audit_mcp_url is not configured, or run_type is wrong.
        RuntimeError: If claude-agent-sdk is unavailable or agent returns no output.
    """
    if query is None:
        raise RuntimeError(
            "claude-agent-sdk is not installed on this platform. "
            "GEO compare benchmark runs require macOS (arm64)."
        )
    if spec.run_type is not RunType.geo_compare:
        raise ValueError(
            f"run_geo_compare_benchmark only handles run_type=geo_compare, got {spec.run_type}"
        )

    settings = Settings()  # type: ignore[call-arg]

    if not settings.geo_audit_mcp_url:
        raise ValueError(
            "geo_audit_mcp_url is required for GEO compare benchmark runs but is not set. "
            "Set GEO_AUDIT_MCP_URL in your environment or .env file."
        )

    mcp_servers: dict[str, McpHttpServerConfig] = {
        "geo-audit": McpHttpServerConfig(type="http", url=settings.geo_audit_mcp_url),
    }
    if settings.geo_analyzer_mcp_url:
        mcp_servers["geo-analyzer"] = McpHttpServerConfig(
            type="http", url=settings.geo_analyzer_mcp_url
        )

    system_prompt = build_geo_compare_system_prompt()
    schema = _load_compare_output_schema()

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
        max_turns=40,
    )

    user_prompt = _build_compare_user_prompt(spec)

    result_text: str | None = None
    async for message in query(prompt=user_prompt, options=options):
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
            f"GEO compare benchmark run {run_id} produced no result text from the agent."
        )

    result = _extract_json_from_result(result_text)

    # Write artifacts via Publisher — this is the only code that writes files
    created_at = _parse_created_at_from_run_id(run_id) or datetime.now(tz=UTC)
    pub = Publisher(run_id, created_at, output_dir)

    report_md_abs = pub.write_report_md(result.get("report_markdown", ""))
    report_json_abs = pub.write_report_json(result)

    artifact_paths = [
        str(report_md_abs.relative_to(output_dir)),
        str(report_json_abs.relative_to(output_dir)),
    ]

    competitors: list[str] = spec.options.get("competitors", [])
    summary: dict[str, Any] = {
        "target": spec.target,
        "competitors": competitors,
        "run_date": created_at.date().isoformat(),
        "overall_winner": result.get("overall_winner"),
        "winner_per_lever": result.get("winner_per_lever", {}),
        "scores": {
            audit["url"]: audit.get("overall_score")
            for audit in result.get("audits", [])
            if isinstance(audit, dict)
        },
    }

    return {
        "run_id": run_id,
        "artifacts": artifact_paths,
        "summary": summary,
    }
