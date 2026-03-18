"""Tests for the BenchmarkControl Arcade MCP server entry point and tools."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from benchmark_control_arcade.run_models import (
    RunArtifact,
    RunRecord,
    RunSpec,
    RunStatus,
    RunType,
)


def _make_record(
    run_id: str = "run-test",
    run_type: RunType = RunType.aioa,
    status: RunStatus = RunStatus.queued,
) -> RunRecord:
    now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
    return RunRecord(
        run_id=run_id,
        run_type=run_type,
        status=status,
        created_at=now,
        updated_at=now,
        repo="acme/benchmarks",
        workflow_name="run-benchmark.yml",
        data_branch="benchmark-data",
        spec=RunSpec(run_type=run_type, target="composio.dev"),
        summary={"score": 85} if status == RunStatus.completed else None,
    )


class TestAppLoads:
    def test_app_loads_with_expected_name_and_version(self):
        from benchmark_control_arcade.server import app

        assert app.name == "BenchmarkControl"
        assert app.version == "0.1.0"

    def test_app_has_instructions(self):
        from benchmark_control_arcade.server import app

        assert app.instructions is not None
        assert len(app.instructions) > 0


class TestStartRun:
    @pytest.mark.asyncio
    async def test_start_run_creates_queued_record_and_dispatches(self, monkeypatch):
        monkeypatch.setenv("GITHUB_OWNER", "acme")
        monkeypatch.setenv("GITHUB_REPO", "benchmarks")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

        mock_client = MagicMock()
        mock_client.create_initial_run_record = AsyncMock()
        mock_client.dispatch_workflow = AsyncMock()

        from benchmark_control_arcade.server import _start_run
        from benchmark_control_arcade.config import Settings

        settings = Settings()
        record = await _start_run(settings, mock_client, "aioa", "composio.dev", "{}")

        assert record.status == RunStatus.queued
        assert record.run_type == RunType.aioa
        assert record.spec.target == "composio.dev"
        mock_client.create_initial_run_record.assert_awaited_once()
        mock_client.dispatch_workflow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_run_writes_record_before_dispatch(self, monkeypatch):
        """create_initial_run_record must be called before dispatch_workflow."""
        monkeypatch.setenv("GITHUB_OWNER", "acme")
        monkeypatch.setenv("GITHUB_REPO", "benchmarks")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

        call_order: list[str] = []
        mock_client = MagicMock()
        mock_client.create_initial_run_record = AsyncMock(
            side_effect=lambda *_: call_order.append("create")
        )
        mock_client.dispatch_workflow = AsyncMock(
            side_effect=lambda *_: call_order.append("dispatch")
        )

        from benchmark_control_arcade.server import _start_run
        from benchmark_control_arcade.config import Settings

        settings = Settings()
        await _start_run(settings, mock_client, "aioa", "composio.dev", "{}")

        assert call_order == ["create", "dispatch"]

    @pytest.mark.asyncio
    async def test_start_run_run_id_passed_to_dispatch(self, monkeypatch):
        monkeypatch.setenv("GITHUB_OWNER", "acme")
        monkeypatch.setenv("GITHUB_REPO", "benchmarks")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

        mock_client = MagicMock()
        mock_client.create_initial_run_record = AsyncMock()
        mock_client.dispatch_workflow = AsyncMock()

        from benchmark_control_arcade.server import _start_run
        from benchmark_control_arcade.config import Settings

        settings = Settings()
        record = await _start_run(settings, mock_client, "aioa", "composio.dev", "{}")

        dispatch_args = mock_client.dispatch_workflow.call_args[0]
        assert dispatch_args[0] == record.run_id


class TestGetRunStatus:
    @pytest.mark.asyncio
    async def test_get_run_status_returns_parsed_record(self, monkeypatch):
        monkeypatch.setenv("GITHUB_OWNER", "acme")
        monkeypatch.setenv("GITHUB_REPO", "benchmarks")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

        record = _make_record("run-abc", status=RunStatus.completed)
        mock_client = MagicMock()
        mock_client.get_run_record = AsyncMock(return_value=record)

        from benchmark_control_arcade.server import _get_run_status
        from benchmark_control_arcade.config import Settings

        settings = Settings()
        result = await _get_run_status(mock_client, "run-abc", record.created_at.isoformat())

        parsed = json.loads(result)
        assert parsed["run_id"] == "run-abc"
        assert parsed["status"] == "completed"


class TestListRuns:
    @pytest.mark.asyncio
    async def test_list_runs_returns_newest_first(self, monkeypatch):
        monkeypatch.setenv("GITHUB_OWNER", "acme")
        monkeypatch.setenv("GITHUB_REPO", "benchmarks")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

        records = [_make_record(f"run-{i}") for i in range(3)]
        mock_client = MagicMock()
        mock_client.list_run_records = AsyncMock(return_value=records)

        from benchmark_control_arcade.server import _list_runs
        from benchmark_control_arcade.config import Settings

        settings = Settings()
        result = await _list_runs(mock_client, limit=10)

        parsed = json.loads(result)
        assert len(parsed) == 3
        assert parsed[0]["run_id"] == "run-0"


class TestGetRunReport:
    @pytest.mark.asyncio
    async def test_get_run_report_returns_content(self, monkeypatch):
        monkeypatch.setenv("GITHUB_OWNER", "acme")
        monkeypatch.setenv("GITHUB_REPO", "benchmarks")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

        record = _make_record("run-abc", status=RunStatus.completed)

        with patch(
            "benchmark_control_arcade.server.fetch_run_report",
            new=AsyncMock(return_value="# Report"),
        ):
            from benchmark_control_arcade.server import _get_run_report
            from benchmark_control_arcade.config import Settings

            mock_client = MagicMock()
            settings = Settings()
            result = await _get_run_report(mock_client, "run-abc", record.created_at.isoformat())

        assert result == "# Report"


class TestGetRunArtifacts:
    @pytest.mark.asyncio
    async def test_get_run_artifacts_returns_artifact_list(self, monkeypatch):
        monkeypatch.setenv("GITHUB_OWNER", "acme")
        monkeypatch.setenv("GITHUB_REPO", "benchmarks")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

        record = _make_record("run-abc", status=RunStatus.completed)
        artifacts = [
            RunArtifact(name="report.json", path="runs/2026/03/18/run-abc/report.json"),
        ]

        with patch(
            "benchmark_control_arcade.server.fetch_run_artifacts",
            new=AsyncMock(return_value=artifacts),
        ):
            from benchmark_control_arcade.server import _get_run_artifacts
            from benchmark_control_arcade.config import Settings

            mock_client = MagicMock()
            settings = Settings()
            result = await _get_run_artifacts(mock_client, "run-abc", record.created_at.isoformat())

        parsed = json.loads(result)
        assert len(parsed) == 1
        assert parsed[0]["name"] == "report.json"


class TestCompareAioaRuns:
    @pytest.mark.asyncio
    async def test_compare_aioa_runs_rejects_geo_run(self, monkeypatch):
        monkeypatch.setenv("GITHUB_OWNER", "acme")
        monkeypatch.setenv("GITHUB_REPO", "benchmarks")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        aioa_record = _make_record("run-aioa")
        geo_record = _make_record("run-geo", run_type=RunType.geo)

        mock_client = MagicMock()
        mock_client.get_run_record = AsyncMock(side_effect=[aioa_record, geo_record])

        from benchmark_control_arcade.server import _compare_aioa_runs

        with pytest.raises(ValueError, match="aioa"):
            await _compare_aioa_runs(
                mock_client,
                "run-aioa", now.isoformat(),
                "run-geo", now.isoformat(),
            )

    @pytest.mark.asyncio
    async def test_compare_aioa_runs_returns_comparison(self, monkeypatch):
        monkeypatch.setenv("GITHUB_OWNER", "acme")
        monkeypatch.setenv("GITHUB_REPO", "benchmarks")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        record_a = _make_record("run-a", status=RunStatus.completed)
        record_b = _make_record("run-b", status=RunStatus.completed)

        mock_client = MagicMock()
        mock_client.get_run_record = AsyncMock(side_effect=[record_a, record_b])

        from benchmark_control_arcade.server import _compare_aioa_runs

        result = await _compare_aioa_runs(
            mock_client,
            "run-a", now.isoformat(),
            "run-b", now.isoformat(),
        )

        parsed = json.loads(result)
        assert parsed["run_id_a"] == "run-a"
        assert parsed["run_id_b"] == "run-b"
