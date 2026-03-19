"""BenchmarkControl Arcade MCP server.

Owns triggering, status, history, and comparisons for AIOA and GEO benchmark
runs.

Tool surface (v1):
- StartRun           — queue a new benchmark run
- GetRunStatus       — fetch the current state of a run
- ListRuns           — list recent runs (newest first)
- GetLatestRun       — fetch the most recent run matching filters
- GetRunReport       — retrieve the Markdown or JSON report for a completed run
- GetRunArtifacts    — list artifact paths for a completed run
- CompareAioaRuns    — diff two completed AIOA runs (AIOA-only in v1)
- SearchGeoReports   — search GEO runs by target, competitor, date range

Note: do NOT add ``from __future__ import annotations`` to this file.
arcade-mcp-server's @app.tool decorator uses inspect.signature() to read
parameter types at decoration time. The PEP 563 lazy-annotation behaviour
breaks that introspection, causing ToolDefinitionError at import.
"""

import json
import re
import sys
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from arcade_mcp_server import MCPApp
from arcade_mcp_server.exceptions import ToolExecutionError
from arcade_mcp_server.metadata import (
    Behavior,
    Classification,
    Operation,
    ServiceDomain,
    ToolMetadata,
)
from arcade_tdk import ToolContext
from geo_audit_arcade.models import AuditMode, CoveragePreset
from geo_audit_arcade.tools.run_geo_audit import run_geo_audit
from geo_audit_arcade.tools.run_geo_compare import run_geo_compare

from benchmark_control_arcade.compare import compare_aioa_runs
from benchmark_control_arcade.config import Settings
from benchmark_control_arcade.github_client import GitHubClient
from benchmark_control_arcade.history import (
    fetch_run_artifacts,
    fetch_run_report,
    filter_runs,
    get_average_elapsed_seconds,
    search_geo_reports,
)
from benchmark_control_arcade.run_models import (
    GeoSearchRunType,
    ReportFormat,
    RunRecord,
    RunSpec,
    RunStatus,
    RunType,
)


def _settings_from_context(ctx: ToolContext) -> Settings:
    """Build Settings, pulling secrets from ToolContext when available.

    Arcade injects declared secrets into ToolContext, not os.environ.
    Falls back to os.environ / .env for local development.
    """

    def _get(key: str) -> str | None:
        try:
            return ctx.get_secret(key)
        except (ValueError, AttributeError):
            return None

    overrides: dict[str, Any] = {}
    for field, key in [
        ("github_token", "GITHUB_TOKEN"),
        ("github_owner", "GITHUB_OWNER"),
        ("github_repo", "GITHUB_REPO"),
    ]:
        val = _get(key)
        if val:
            overrides[field] = val

    return Settings(**overrides) if overrides else Settings()  # type: ignore[call-arg]


def _validate_run_id(run_id: str) -> str:
    run_id = run_id.strip()
    if not run_id:
        raise ToolExecutionError("`run_id` must not be empty.")
    return run_id


def _validate_iso_date(value: str, param_name: str) -> str:
    value = value.strip()
    if not value:
        raise ToolExecutionError(f"`{param_name}` must not be empty.")
    try:
        datetime.fromisoformat(value)
    except ValueError as exc:
        raise ToolExecutionError(
            f"`{param_name}` is not valid ISO-8601: {value!r}",
            developer_message=f"datetime.fromisoformat() failed for {value!r}.",
        ) from exc
    return value


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(value, hi))


_URL_RE = re.compile(r"^https?://[^\s/$.?#].\S*$", re.IGNORECASE)


def _validate_url(url: str, param_name: str = "target_url") -> str:
    url = url.strip()
    if not url:
        raise ToolExecutionError(f"`{param_name}` must not be empty.")
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    if not _URL_RE.match(url):
        raise ToolExecutionError(
            f"`{param_name}` is not a valid URL: {url!r}",
            developer_message=f"Received {url!r} which did not match URL pattern.",
        )
    return url


def _parse_urls(raw: str) -> list[str]:
    raw = raw.strip()
    if raw.startswith("["):
        try:
            return [u.strip() for u in json.loads(raw) if u.strip()]
        except (json.JSONDecodeError, TypeError):
            pass
    parts = re.split(r"[\n,]+", raw)
    return [p.strip() for p in parts if p.strip()]


app = MCPApp(
    name="BenchmarkControl",
    version="0.2.0",
    instructions=(
        "Control plane for AIOA and GEO benchmark runs. "
        "Use RunGeoSiteAudit and RunGeoCompare for instant GEO audits. "
        "Use StartRun, GetRunStatus, ListRuns, GetLatestRun, GetRunReport, "
        "GetRunArtifacts, CompareAioaRuns, and SearchGeoReports for tracked runs."
    ),
    log_level="INFO",
)

_REQUIRED_SECRETS = ["GITHUB_TOKEN", "GITHUB_OWNER", "GITHUB_REPO", "ANTHROPIC_API_KEY"]

_WRITE_METADATA = ToolMetadata(
    classification=Classification(
        service_domains=[ServiceDomain.SOURCE_CODE],
    ),
    behavior=Behavior(
        operations=[Operation.CREATE],
        read_only=False,
        destructive=False,
        idempotent=False,
        open_world=True,
    ),
)

_READ_METADATA = ToolMetadata(
    classification=Classification(
        service_domains=[ServiceDomain.SOURCE_CODE],
    ),
    behavior=Behavior(
        operations=[Operation.READ],
        read_only=True,
        destructive=False,
        idempotent=True,
        open_world=True,
    ),
)

_AUDIT_METADATA = ToolMetadata(
    classification=Classification(
        service_domains=[ServiceDomain.WEB_SCRAPING],
    ),
    behavior=Behavior(
        operations=[Operation.READ],
        read_only=True,
        destructive=False,
        idempotent=True,
        open_world=True,
    ),
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
    await client.create_initial_run_record(record)
    await client.dispatch_workflow(run_id, run_type, spec.model_dump_json())
    return record


async def _get_run_status(client: GitHubClient, run_id: str, created_at_iso: str) -> str:
    created_at = datetime.fromisoformat(created_at_iso)
    record = await client.get_run_record(run_id, created_at)
    return record.model_dump_json()


async def _list_runs(client: GitHubClient, limit: int) -> str:
    records = await client.list_run_records(limit=limit)
    return json.dumps([r.model_dump(mode="json") for r in records])


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


@app.tool(
    requires_secrets=_REQUIRED_SECRETS,
    metadata=_WRITE_METADATA,
)
async def StartRun(
    ctx: ToolContext,
    run_type: Annotated[RunType, "Run type: aioa, geo, or geo_compare"],
    target: Annotated[str, "URL or target identifier for the benchmark"],
    options_json: Annotated[str, "JSON object of extra run options (default: {})"] = "{}",
) -> Annotated[str, "Queued RunRecord as JSON with estimated_wait_seconds"]:
    """Queue a new benchmark run and return the initial RunRecord.

    The response includes an ``estimated_wait_seconds`` field computed from the
    average elapsed time of recent *completed* runs of the same type.
    Failed runs are excluded from the average.  Returns null when no history
    exists yet.
    """
    target = target.strip()
    if not target:
        raise ToolExecutionError("`target` must not be empty.")
    try:
        json.loads(options_json) if options_json.strip() else {}
    except json.JSONDecodeError as exc:
        raise ToolExecutionError(
            f"`options_json` is not valid JSON: {exc}",
            developer_message=f"Received options_json={options_json!r}.",
        ) from exc
    settings = _settings_from_context(ctx)
    client = GitHubClient(settings)
    record = await _start_run(settings, client, run_type.value, target, options_json)
    avg = await get_average_elapsed_seconds(client, run_type.value)
    result = record.model_dump(mode="json")
    result["estimated_wait_seconds"] = round(avg) if avg is not None else None
    return json.dumps(result)


@app.tool(
    requires_secrets=_REQUIRED_SECRETS,
    metadata=_READ_METADATA,
)
async def GetRunStatus(
    ctx: ToolContext,
    run_id: Annotated[str, "The run identifier returned by StartRun"],
    created_at: Annotated[str, "ISO-8601 creation timestamp from the RunRecord"],
) -> Annotated[str, "Current RunRecord as JSON"]:
    """Fetch the current state of a benchmark run."""
    run_id = _validate_run_id(run_id)
    created_at = _validate_iso_date(created_at, "created_at")
    settings = _settings_from_context(ctx)
    client = GitHubClient(settings)
    return await _get_run_status(client, run_id, created_at)


@app.tool(
    requires_secrets=_REQUIRED_SECRETS,
    metadata=_READ_METADATA,
)
async def ListRuns(
    ctx: ToolContext,
    limit: Annotated[int, "Maximum number of runs to return (default: 20)"] = 20,
    run_type: Annotated[
        RunType | None,
        "Filter by run type. None = all types.",
    ] = None,
    target: Annotated[str, "Filter by target site (e.g. 'arcade.dev'). Empty = all."] = "",
    from_date: Annotated[str, "Start date inclusive (YYYY-MM-DD). Empty = no lower bound."] = "",
    to_date: Annotated[str, "End date inclusive (YYYY-MM-DD). Empty = no upper bound."] = "",
) -> Annotated[str, "JSON array of RunRecord objects, newest first"]:
    """List benchmark runs with optional filters by type, target, and date range."""
    limit = _clamp(limit, 1, 100)
    settings = _settings_from_context(ctx)
    client = GitHubClient(settings)
    rt = run_type.value if run_type is not None else ""
    if rt or target or from_date or to_date:
        records = await filter_runs(
            client,
            run_type=rt,
            target=target,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
        )
        return json.dumps([r.model_dump(mode="json") for r in records])
    return await _list_runs(client, limit=limit)


@app.tool(
    requires_secrets=_REQUIRED_SECRETS,
    metadata=_READ_METADATA,
)
async def GetLatestRun(
    ctx: ToolContext,
    run_type: Annotated[
        RunType | None,
        "Filter by run type. None = any type.",
    ] = None,
    target: Annotated[str, "Filter by target site (e.g. 'arcade.dev'). Empty = any target."] = "",
    status: Annotated[
        RunStatus | None,
        "Filter by status. None = any status.",
    ] = RunStatus.completed,
    include_report: Annotated[
        bool,
        "If true, fetch the full report artifact and embed it in the response.",
    ] = False,
) -> Annotated[str, "The most recent matching RunRecord as JSON, with optional report"]:
    """Return the most recent run matching the given filters.

    Defaults to the latest completed run of any type.  Use run_type and target
    to narrow down (e.g. latest completed AIOA run for arcade.dev).

    If include_report=True the full report artifact JSON is embedded under a
    'report' key in the response — no need for a separate GetRunReport call.
    """
    settings = _settings_from_context(ctx)
    client = GitHubClient(settings)

    rt = run_type.value if run_type is not None else ""
    st = status.value if status is not None else ""
    records = await filter_runs(
        client,
        run_type=rt,
        target=target,
        status=st,
        limit=1,
    )

    if not records:
        raise ToolExecutionError(
            "No matching run found.",
            developer_message=f"Filters: run_type={rt!r}, target={target!r}, status={st!r}.",
        )

    record = records[0]
    result = record.model_dump(mode="json")

    if include_report and record.artifacts:
        report_artifact = next(
            (
                a
                for a in record.artifacts
                if a.name.startswith("report_") and a.name.endswith(".json")
            ),
            None,
        )
        if report_artifact:
            try:
                raw = await client.get_file_content(report_artifact.path)
                result["report"] = json.loads(raw)
            except Exception:
                result["report"] = None

    return json.dumps(result)


@app.tool(
    requires_secrets=_REQUIRED_SECRETS,
    metadata=_READ_METADATA,
)
async def GetRunReport(
    ctx: ToolContext,
    run_id: Annotated[str, "The run identifier"],
    created_at: Annotated[str, "ISO-8601 creation timestamp from the RunRecord"],
    fmt: Annotated[ReportFormat, "Report format"] = ReportFormat.md,
) -> Annotated[str, "Report content as a string"]:
    """Retrieve the benchmark report for a completed run."""
    run_id = _validate_run_id(run_id)
    created_at = _validate_iso_date(created_at, "created_at")
    settings = _settings_from_context(ctx)
    client = GitHubClient(settings)
    return await _get_run_report(client, run_id, created_at, fmt=fmt.value)


@app.tool(
    requires_secrets=_REQUIRED_SECRETS,
    metadata=_READ_METADATA,
)
async def GetRunArtifacts(
    ctx: ToolContext,
    run_id: Annotated[str, "The run identifier"],
    created_at: Annotated[str, "ISO-8601 creation timestamp from the RunRecord"],
) -> Annotated[str, "JSON array of RunArtifact objects"]:
    """List the artifact paths for a completed benchmark run."""
    run_id = _validate_run_id(run_id)
    created_at = _validate_iso_date(created_at, "created_at")
    settings = _settings_from_context(ctx)
    client = GitHubClient(settings)
    return await _get_run_artifacts(client, run_id, created_at)


@app.tool(
    requires_secrets=_REQUIRED_SECRETS,
    metadata=_READ_METADATA,
)
async def CompareAioaRuns(
    ctx: ToolContext,
    run_id_a: Annotated[str, "First AIOA run identifier"],
    created_at_a: Annotated[str, "ISO-8601 creation timestamp of the first run"],
    run_id_b: Annotated[str, "Second AIOA run identifier"],
    created_at_b: Annotated[str, "ISO-8601 creation timestamp of the second run"],
) -> Annotated[str, "Comparison result as JSON"]:
    """Compare two completed AIOA benchmark runs.

    Both runs must be of type 'aioa'. GEO runs are not supported in v1.
    Returns a structured diff of summaries, statuses, and targets.
    """
    run_id_a = _validate_run_id(run_id_a)
    run_id_b = _validate_run_id(run_id_b)
    created_at_a = _validate_iso_date(created_at_a, "created_at_a")
    created_at_b = _validate_iso_date(created_at_b, "created_at_b")
    settings = _settings_from_context(ctx)
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
    return json.dumps([r.model_dump(mode="json") for r in records])


@app.tool(
    requires_secrets=_REQUIRED_SECRETS,
    metadata=_AUDIT_METADATA,
)
async def RunGeoSiteAudit(
    ctx: ToolContext,
    target_url: Annotated[str, "URL to audit (e.g. 'https://arcade.dev')"],
    audit_mode: Annotated[
        AuditMode,
        "Depth of analysis: quick=~30s, standard=~60s, exhaustive=~90s",
    ] = AuditMode.EXHAUSTIVE,
    coverage_preset: Annotated[
        CoveragePreset,
        "Page budget: light=5, standard=15, deep=30, exhaustive=60 pages",
    ] = CoveragePreset.EXHAUSTIVE,
    discover_subdomains: Annotated[bool, "Discover subdomains from page links"] = True,
) -> Annotated[str, "Complete GEO audit report as JSON"]:
    """Run a complete single-site GEO audit and return the structured report."""
    del ctx
    target_url = _validate_url(target_url, "target_url")
    result = await run_geo_audit(
        target_url=target_url,
        audit_mode=audit_mode.value,
        coverage_preset=coverage_preset.value,
        discover_subdomains=discover_subdomains,
    )
    return json.dumps(result)


@app.tool(
    requires_secrets=_REQUIRED_SECRETS,
    metadata=_AUDIT_METADATA,
)
async def RunGeoCompare(
    ctx: ToolContext,
    target: Annotated[str, "Primary site to audit (e.g. 'arcade.dev')"],
    competitors: Annotated[str, "Competitor URLs, comma-separated or JSON array"],
    audit_mode: Annotated[
        AuditMode,
        "Depth of analysis: quick=~30s, standard=~60s, exhaustive=~90s",
    ] = AuditMode.EXHAUSTIVE,
    coverage_preset: Annotated[
        CoveragePreset,
        "Page budget: light=5, standard=15, deep=30, exhaustive=60 pages",
    ] = CoveragePreset.EXHAUSTIVE,
    discover_subdomains: Annotated[bool, "Discover subdomains from page links"] = True,
) -> Annotated[str, "Complete GEO comparison report as JSON"]:
    """Run a complete GEO competitive comparison for target vs competitors."""
    del ctx
    target = _validate_url(target, "target")
    competitor_list = _parse_urls(competitors)
    if not competitor_list:
        raise ToolExecutionError(
            "No valid competitor URLs provided in `competitors`.",
            developer_message=f"Received competitors={competitors!r} -> empty list.",
        )
    result = await run_geo_compare(
        target=target,
        competitors=competitor_list,
        audit_mode=audit_mode.value,
        coverage_preset=coverage_preset.value,
        discover_subdomains=discover_subdomains,
    )
    return json.dumps(result)


@app.tool(
    requires_secrets=_REQUIRED_SECRETS,
    metadata=_READ_METADATA,
)
async def SearchGeoReports(
    ctx: ToolContext,
    target: Annotated[str, "Primary site being audited (e.g. 'arcade.dev'). Empty = all."] = "",
    competitor: Annotated[str, "Filter runs that include this competitor URL. Empty = all."] = "",
    from_date: Annotated[str, "ISO-8601 start date inclusive (YYYY-MM-DD). Empty = no bound."] = "",
    to_date: Annotated[str, "ISO-8601 end date inclusive (YYYY-MM-DD). Empty = no bound."] = "",
    run_type: Annotated[
        GeoSearchRunType | None,
        "Run type filter: geo or geo_compare. None = both.",
    ] = None,
    limit: Annotated[int, "Max results (default 20)."] = 20,
) -> Annotated[str, "JSON array of matching RunRecord summaries, newest first"]:
    """Search GEO audit reports by target, competitor, date range, or run type.

    Returns geo and geo_compare runs matching all supplied filters, newest first.
    Omit a filter (or pass an empty string) to match all values for that field.
    """
    limit = _clamp(limit, 1, 100)
    settings = _settings_from_context(ctx)
    client = GitHubClient(settings)
    rt = run_type.value if run_type is not None else ""
    return await _search_geo_reports(client, target, competitor, from_date, to_date, rt, limit)


if __name__ == "__main__":
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    app.run(transport=transport, host="127.0.0.1", port=8001)
