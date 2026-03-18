"""BenchmarkControl Arcade MCP server.

Owns triggering, status, history, and comparisons for AIOA and GEO benchmark
runs.

Tool surface (v1):
- StartRun           — queue a new benchmark run
- GetRunStatus       — fetch the current state of a run
- ListRuns           — list recent runs (newest first)
- GetRunReport       — retrieve the Markdown or JSON report for a completed run
- GetRunArtifacts    — list artifact paths for a completed run
- CompareAioaRuns    — diff two completed AIOA runs (AIOA-only in v1)

Note: do NOT add `from __future__ import annotations` to this file.
arcade-mcp-server's @app.tool decorator uses inspect.signature() to read
parameter types at decoration time. The PEP 563 lazy-annotation behaviour
breaks that introspection, causing ToolDefinitionError at import.
"""

import json
import sys
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from arcade_mcp_server import MCPApp

from benchmark_control_arcade.compare import compare_aioa_runs
from benchmark_control_arcade.config import Settings
from benchmark_control_arcade.github_client import GitHubClient
from benchmark_control_arcade.history import (
    fetch_run_artifacts,
    fetch_run_report,
    search_geo_reports,
)
from benchmark_control_arcade.run_models import (
    RunRecord,
    RunSpec,
    RunStatus,
    RunType,
)

app = MCPApp(
    name="BenchmarkControl",
    version="0.1.0",
    instructions=(
        "Control plane for AIOA and GEO benchmark runs. "
        "Use StartRun to trigger a new benchmark, then GetRunStatus, "
        "ListRuns, GetRunReport, GetRunArtifacts, or CompareAioaRuns "
        "to inspect historical results. "
        "Use SearchGeoReports to find GEO and GEO compare runs by target, "
        "competitor, or date range."
    ),
    log_level="INFO",
)


# ---------------------------------------------------------------------------
# Inner handler functions — accept injected client for testability
# ---------------------------------------------------------------------------


async def _start_run(
    settings: Settings,
    client: GitHubClient,
    run_type: str,
    target: str,
    options_json: str,
) -> RunRecord:
    """Create a queued RunRecord, write it to the data branch, dispatch workflow."""
    options: dict[str, Any] = json.loads(options_json) if options_json.strip() else {}
    spec = RunSpec(run_type=RunType(run_type), target=target, options=options)
    now = datetime.now(tz=UTC)
    run_id = f"run-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    record = RunRecord(
        run_id=run_id,
        run_type=spec.run_type,
        status=RunStatus.queued,
        created_at=now,
        updated_at=now,
        repo=f"{settings.github_owner}/{settings.github_repo}",
        workflow_name=settings.github_run_workflow,
        data_branch=settings.github_data_branch,
        spec=spec,
    )
    # Write record BEFORE dispatching so the worker can find it on first poll.
    await client.create_initial_run_record(record)
    await client.dispatch_workflow(run_id, run_type, spec.model_dump_json())
    return record


async def _get_run_status(client: GitHubClient, run_id: str, created_at_iso: str) -> str:
    created_at = datetime.fromisoformat(created_at_iso)
    record = await client.get_run_record(run_id, created_at)
    return record.model_dump_json()


async def _list_runs(client: GitHubClient, limit: int) -> str:
    records = await client.list_run_records(limit=limit)
    return json.dumps([json.loads(r.model_dump_json()) for r in records])


async def _get_run_report(
    client: GitHubClient, run_id: str, created_at_iso: str, fmt: str = "md"
) -> str:
    created_at = datetime.fromisoformat(created_at_iso)
    return await fetch_run_report(client, run_id, created_at, fmt=fmt)


async def _get_run_artifacts(client: GitHubClient, run_id: str, created_at_iso: str) -> str:
    created_at = datetime.fromisoformat(created_at_iso)
    artifacts = await fetch_run_artifacts(client, run_id, created_at)
    return json.dumps([a.model_dump() for a in artifacts])


async def _compare_aioa_runs(
    client: GitHubClient,
    run_id_a: str,
    created_at_a_iso: str,
    run_id_b: str,
    created_at_b_iso: str,
) -> str:
    created_at_a = datetime.fromisoformat(created_at_a_iso)
    created_at_b = datetime.fromisoformat(created_at_b_iso)
    record_a = await client.get_run_record(run_id_a, created_at_a)
    record_b = await client.get_run_record(run_id_b, created_at_b)
    result = compare_aioa_runs(record_a, record_b)
    return json.dumps(result)


# ---------------------------------------------------------------------------
# MCP tool wrappers — thin; create Settings + client, delegate to inner fns
# ---------------------------------------------------------------------------


@app.tool
async def StartRun(
    run_type: Annotated[str, "Run type: 'aioa', 'geo', or 'geo_compare'"],
    target: Annotated[str, "URL or target identifier for the benchmark"],
    options_json: Annotated[str, "JSON object of extra run options (default: {})"] = "{}",
) -> Annotated[str, "Queued RunRecord as JSON"]:
    """Queue a new benchmark run and return the initial RunRecord."""
    settings = Settings()
    client = GitHubClient(settings)
    record = await _start_run(settings, client, run_type, target, options_json)
    return record.model_dump_json()


@app.tool
async def GetRunStatus(
    run_id: Annotated[str, "The run identifier returned by StartRun"],
    created_at: Annotated[str, "ISO-8601 creation timestamp from the RunRecord"],
) -> Annotated[str, "Current RunRecord as JSON"]:
    """Fetch the current state of a benchmark run."""
    settings = Settings()
    client = GitHubClient(settings)
    return await _get_run_status(client, run_id, created_at)


@app.tool
async def ListRuns(
    limit: Annotated[int, "Maximum number of runs to return (default: 20)"] = 20,
) -> Annotated[str, "JSON array of RunRecord objects, newest first"]:
    """List recent benchmark runs from the data branch."""
    settings = Settings()
    client = GitHubClient(settings)
    return await _list_runs(client, limit=limit)


@app.tool
async def GetRunReport(
    run_id: Annotated[str, "The run identifier"],
    created_at: Annotated[str, "ISO-8601 creation timestamp from the RunRecord"],
    fmt: Annotated[str, "Report format: 'md' (default) or 'json'"] = "md",
) -> Annotated[str, "Report content as a string"]:
    """Retrieve the benchmark report for a completed run."""
    settings = Settings()
    client = GitHubClient(settings)
    return await _get_run_report(client, run_id, created_at, fmt=fmt)


@app.tool
async def GetRunArtifacts(
    run_id: Annotated[str, "The run identifier"],
    created_at: Annotated[str, "ISO-8601 creation timestamp from the RunRecord"],
) -> Annotated[str, "JSON array of RunArtifact objects"]:
    """List the artifact paths for a completed benchmark run."""
    settings = Settings()
    client = GitHubClient(settings)
    return await _get_run_artifacts(client, run_id, created_at)


@app.tool
async def CompareAioaRuns(
    run_id_a: Annotated[str, "First AIOA run identifier"],
    created_at_a: Annotated[str, "ISO-8601 creation timestamp of the first run"],
    run_id_b: Annotated[str, "Second AIOA run identifier"],
    created_at_b: Annotated[str, "ISO-8601 creation timestamp of the second run"],
) -> Annotated[str, "Comparison result as JSON"]:
    """Compare two completed AIOA benchmark runs.

    Both runs must be of type 'aioa'. GEO runs are not supported in v1.
    Returns a structured diff of summaries, statuses, and targets.
    """
    settings = Settings()
    client = GitHubClient(settings)
    return await _compare_aioa_runs(client, run_id_a, created_at_a, run_id_b, created_at_b)


async def _search_geo_reports(
    client: GitHubClient,
    target: str,
    competitor: str,
    from_date: str,
    to_date: str,
    run_type: str,
    limit: int,
) -> str:
    records = await search_geo_reports(
        client,
        target=target,
        competitor=competitor,
        from_date=from_date,
        to_date=to_date,
        run_type=run_type,
        limit=limit,
    )
    return json.dumps([json.loads(r.model_dump_json()) for r in records])


@app.tool
async def SearchGeoReports(
    target: Annotated[str, "Primary site being audited (e.g. 'arcade.dev'). Empty = all."] = "",
    competitor: Annotated[str, "Filter runs that include this competitor URL. Empty = all."] = "",
    from_date: Annotated[str, "ISO-8601 start date inclusive (YYYY-MM-DD). Empty = no bound."] = "",
    to_date: Annotated[str, "ISO-8601 end date inclusive (YYYY-MM-DD). Empty = no bound."] = "",
    run_type: Annotated[str, "Run type filter: 'geo', 'geo_compare', or empty for both."] = "",
    limit: Annotated[int, "Max results (default 20)."] = 20,
) -> Annotated[str, "JSON array of matching RunRecord summaries, newest first"]:
    """Search GEO audit reports by target, competitor, date range, or run type.

    Returns geo and geo_compare runs matching all supplied filters, newest first.
    Omit a filter (or pass an empty string) to match all values for that field.
    """
    settings = Settings()
    client = GitHubClient(settings)
    return await _search_geo_reports(
        client, target, competitor, from_date, to_date, run_type, limit
    )


if __name__ == "__main__":
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    app.run(transport=transport, host="127.0.0.1", port=8001)
