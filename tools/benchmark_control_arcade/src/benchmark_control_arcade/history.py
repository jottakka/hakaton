"""Helpers for retrieving run reports and artifacts from the data branch."""

from __future__ import annotations

from datetime import datetime

from benchmark_control_arcade.github_client import GitHubClient, _decode
from benchmark_control_arcade.history_layout import build_run_layout
from benchmark_control_arcade.run_models import RunArtifact


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
