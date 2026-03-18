"""Helpers for retrieving run reports and artifacts from the data branch."""

from __future__ import annotations

from datetime import datetime

from benchmark_control_arcade.github_client import GitHubClient, _decode
from benchmark_control_arcade.history_layout import build_run_layout
from benchmark_control_arcade.run_models import RunArtifact, RunRecord, RunType


async def fetch_run_report(
    client: GitHubClient, run_id: str, created_at: datetime, fmt: str = "md"
) -> str:
    """Return the text content of the run report from the data branch.

    Args:
        client: An authenticated GitHubClient.
        run_id: The run identifier.
        created_at: When the run was created (used to locate its directory).
        fmt: "md" (default) for the Markdown report, "json" for the JSON report.
    """
    layout = build_run_layout(run_id, created_at)
    path = str(layout.report_md if fmt == "md" else layout.report_json)
    data = await client._get_file(path)
    return _decode(data["content"])


async def fetch_run_artifacts(
    client: GitHubClient, run_id: str, created_at: datetime
) -> list[RunArtifact]:
    """Return the list of artifacts recorded in the run's run.json."""
    record = await client.get_run_record(run_id, created_at)
    return record.artifacts


async def search_geo_reports(
    client: GitHubClient,
    target: str = "",
    competitor: str = "",
    from_date: str = "",
    to_date: str = "",
    run_type: str = "",
    limit: int = 20,
) -> list[RunRecord]:
    """Return GEO run records matching the given filters, newest first.

    Fetches up to 500 records from the data branch and filters in-memory.
    The YYYY/MM/DD path layout means the git-tree list already arrives sorted
    newest-first, so date-range filtering is O(n) with early termination.

    Args:
        client: An authenticated GitHubClient.
        target: Filter by spec.target — exact match, empty = all.
        competitor: Filter runs whose spec.options["competitors"] contains this value.
        from_date: ISO-8601 date string (YYYY-MM-DD), inclusive lower bound.
        to_date: ISO-8601 date string (YYYY-MM-DD), inclusive upper bound.
        run_type: "geo", "geo_compare", or "" for both.
        limit: Maximum number of records to return.
    """
    _geo_types = {RunType.geo, RunType.geo_compare}

    records = await client.list_run_records(limit=500)
    results: list[RunRecord] = []

    for record in records:
        if record.run_type not in _geo_types:
            continue

        if run_type and record.run_type.value != run_type:
            continue

        record_date = record.created_at.date().isoformat()
        if from_date and record_date < from_date:
            continue
        if to_date and record_date > to_date:
            continue

        if target and record.spec.target != target:
            continue

        if competitor:
            competitors = record.spec.options.get("competitors", [])
            if not isinstance(competitors, list) or competitor not in competitors:
                continue

        results.append(record)
        if len(results) >= limit:
            break

    return results
