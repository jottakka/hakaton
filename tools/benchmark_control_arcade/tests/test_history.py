"""Tests for history helpers (report and artifact retrieval)."""

from __future__ import annotations

import base64
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
        content_b64 = base64.b64encode(b"# My Report").decode()
        client = MagicMock()
        client._get_file = AsyncMock(return_value={"content": content_b64, "sha": "abc"})

        result = await fetch_run_report(client, record.run_id, record.created_at, fmt="md")

        assert result == "# My Report"
        call_path = client._get_file.call_args[0][0]
        assert call_path.endswith("report.md")

    @pytest.mark.asyncio
    async def test_fetch_run_report_json_calls_correct_path(self):
        from benchmark_control_arcade.history import fetch_run_report

        record = _make_record()
        payload = json.dumps({"score": 87})
        content_b64 = base64.b64encode(payload.encode()).decode()
        client = MagicMock()
        client._get_file = AsyncMock(return_value={"content": content_b64, "sha": "abc"})

        result = await fetch_run_report(client, record.run_id, record.created_at, fmt="json")

        assert '"score"' in result
        call_path = client._get_file.call_args[0][0]
        assert call_path.endswith("report.json")


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
