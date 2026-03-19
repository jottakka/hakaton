"""Tests for history helpers (report and artifact retrieval)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from benchmark_control_arcade.run_models import (
    RunArtifact,
    RunRecord,
    RunSpec,
    RunStatus,
    RunType,
)


def _make_record(run_id: str = "run-abc", run_type: RunType = RunType.aioa) -> RunRecord:
    now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=UTC)
    return RunRecord(
        run_id=run_id,
        run_type=run_type,
        status=RunStatus.completed,
        created_at=now,
        updated_at=now,
        repo="acme/benchmarks",
        workflow_name="run-benchmark.yml",
        data_branch="benchmark-data",
        spec=RunSpec(run_type=run_type, target="composio.dev"),
        artifacts=[
            RunArtifact(name="report.json", path="runs/2026/03/18/run-abc/report.json"),
            RunArtifact(name="report.md", path="runs/2026/03/18/run-abc/report.md"),
        ],
        summary={"score": 87},
    )


class TestFetchRunReport:
    @pytest.mark.asyncio
    async def test_fetch_run_report_md_calls_correct_path(self):
        from benchmark_control_arcade.history import fetch_run_report

        record = _make_record()
        client = MagicMock()
        client.get_file_content = AsyncMock(return_value="# My Report")

        result = await fetch_run_report(client, record.run_id, record.created_at, fmt="md")

        assert result == "# My Report"
        call_path = client.get_file_content.call_args[0][0]
        assert call_path.endswith("report.md")

    @pytest.mark.asyncio
    async def test_fetch_run_report_json_calls_correct_path(self):
        from benchmark_control_arcade.history import fetch_run_report

        record = _make_record()
        payload = json.dumps({"score": 87})
        client = MagicMock()
        client.get_file_content = AsyncMock(return_value=payload)

        result = await fetch_run_report(client, record.run_id, record.created_at, fmt="json")

        assert '"score"' in result
        call_path = client.get_file_content.call_args[0][0]
        assert call_path.endswith("report.json")

    @pytest.mark.asyncio
    async def test_fetch_run_report_falls_back_to_artifact_on_404(self):
        """When canonical report.json returns 404, fall back to artifacts/report_<id>.json."""
        from benchmark_control_arcade.github_client import GitHubHTTPError
        from benchmark_control_arcade.history import fetch_run_report

        record = _make_record()
        artifact_content = json.dumps({"run_id": record.run_id, "score": 62})

        def _side_effect(path: str) -> str:
            if path.endswith("report.json") and "artifacts" not in path:
                raise GitHubHTTPError(404, "Not Found")
            return artifact_content

        client = MagicMock()
        client.get_file_content = AsyncMock(side_effect=_side_effect)

        result = await fetch_run_report(client, record.run_id, record.created_at, fmt="json")

        assert result == artifact_content
        # Second call should target the artifact path
        calls = [c[0][0] for c in client.get_file_content.call_args_list]
        assert any("artifacts" in p and record.run_id in p for p in calls)

    @pytest.mark.asyncio
    async def test_fetch_run_report_reraises_non_404_errors(self):
        """Non-404 HTTP errors must propagate, not be swallowed."""
        from benchmark_control_arcade.github_client import GitHubHTTPError
        from benchmark_control_arcade.history import fetch_run_report

        record = _make_record()
        client = MagicMock()
        client.get_file_content = AsyncMock(
            side_effect=GitHubHTTPError(500, "Internal Server Error")
        )

        with pytest.raises(GitHubHTTPError):
            await fetch_run_report(client, record.run_id, record.created_at, fmt="json")


class TestFetchRunArtifacts:
    @pytest.mark.asyncio
    async def test_fetch_run_artifacts_returns_record_artifacts(self):
        from benchmark_control_arcade.history import fetch_run_artifacts

        record = _make_record()
        client = MagicMock()
        client.get_run_record = AsyncMock(return_value=record)

        artifacts = await fetch_run_artifacts(client, record.run_id, record.created_at)

        assert len(artifacts) == 2
        assert artifacts[0].name == "report.json"
        client.get_run_record.assert_awaited_once_with(record.run_id, record.created_at)

    @pytest.mark.asyncio
    async def test_fetch_run_artifacts_returns_empty_list_when_no_artifacts(self):
        from benchmark_control_arcade.history import fetch_run_artifacts

        record = _make_record()
        record_no_artifacts = record.model_copy(update={"artifacts": []})
        client = MagicMock()
        client.get_run_record = AsyncMock(return_value=record_no_artifacts)

        artifacts = await fetch_run_artifacts(client, record.run_id, record.created_at)

        assert artifacts == []
