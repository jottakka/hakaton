"""Tests for workflow_entrypoint.run_workflow.

Strategy:
- Patch aioa_runner and geo_runner at module boundaries.
- Use real Pydantic models and real Settings.
- Verify status transitions: queued -> running -> completed/failed.
- Verify routing: run_type="aioa" -> aioa_runner, run_type="geo" -> geo_runner.
- Verify graceful error handling: runner failure -> failed (no re-raise).
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from benchmark_control_arcade.run_models import RunRecord, RunSpec, RunStatus, RunType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings():
    from benchmark_control_arcade.config import Settings

    return Settings(
        github_owner="acme",
        github_repo="benchmarks",
        github_token="ghp_fake",
        github_data_branch="benchmark-data",
        github_run_workflow="run-benchmark.yml",
    )


def _make_record(run_id: str, run_type: RunType, status: RunStatus = RunStatus.queued) -> RunRecord:
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
    )


def _aioa_spec_json() -> str:
    return json.dumps({"run_type": "aioa", "target": "composio.dev", "options": {}})


def _geo_spec_json() -> str:
    return json.dumps({"run_type": "geo", "target": "composio.dev", "options": {}})


# ---------------------------------------------------------------------------
# Tests: routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_workflow_routes_to_aioa_runner():
    """run_type='aioa' must call aioa_runner.run_aioa_benchmark."""
    run_id = "run-aioa-001"
    spec_json = _aioa_spec_json()

    initial_record = _make_record(run_id, RunType.aioa, RunStatus.queued)
    aioa_result = {
        "run_id": run_id,
        "artifacts": [],
        "summary": {"score": 42},
    }

    mock_settings = _make_settings()
    mock_client = AsyncMock()
    mock_client.get_run_record = AsyncMock(return_value=initial_record)
    mock_client.update_run_record = AsyncMock()

    with (
        patch(
            "benchmark_control_arcade.workflow_entrypoint.Settings",
            return_value=mock_settings,
        ),
        patch(
            "benchmark_control_arcade.workflow_entrypoint.GitHubClient",
            return_value=mock_client,
        ),
        patch(
            "benchmark_control_arcade.workflow_entrypoint.aioa_runner.run_aioa_benchmark",
            new_callable=AsyncMock,
            return_value=aioa_result,
        ) as mock_aioa,
        patch(
            "benchmark_control_arcade.workflow_entrypoint.geo_runner.run_geo_benchmark",
            new_callable=AsyncMock,
        ) as mock_geo,
    ):
        from benchmark_control_arcade.workflow_entrypoint import run_workflow

        await run_workflow(run_id, "aioa", spec_json)

    mock_aioa.assert_awaited_once()
    mock_geo.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_workflow_routes_to_geo_runner():
    """run_type='geo' must call geo_runner.run_geo_benchmark."""
    run_id = "run-geo-001"
    spec_json = _geo_spec_json()

    initial_record = _make_record(run_id, RunType.geo, RunStatus.queued)
    geo_result = {
        "overall_score": 85,
        "report_markdown": "## GEO Report",
    }

    mock_settings = _make_settings()
    mock_client = AsyncMock()
    mock_client.get_run_record = AsyncMock(return_value=initial_record)
    mock_client.update_run_record = AsyncMock()

    with (
        patch(
            "benchmark_control_arcade.workflow_entrypoint.Settings",
            return_value=mock_settings,
        ),
        patch(
            "benchmark_control_arcade.workflow_entrypoint.GitHubClient",
            return_value=mock_client,
        ),
        patch(
            "benchmark_control_arcade.workflow_entrypoint.aioa_runner.run_aioa_benchmark",
            new_callable=AsyncMock,
        ) as mock_aioa,
        patch(
            "benchmark_control_arcade.workflow_entrypoint.geo_runner.run_geo_benchmark",
            new_callable=AsyncMock,
            return_value=geo_result,
        ) as mock_geo,
    ):
        from benchmark_control_arcade.workflow_entrypoint import run_workflow

        await run_workflow(run_id, "geo", spec_json)

    mock_geo.assert_awaited_once()
    mock_aioa.assert_not_awaited()


# ---------------------------------------------------------------------------
# Tests: status transitions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_workflow_transitions_to_completed_on_success():
    """On runner success, run.json must be updated to 'completed'."""
    run_id = "run-success-001"
    spec_json = _aioa_spec_json()

    initial_record = _make_record(run_id, RunType.aioa, RunStatus.queued)
    aioa_result = {
        "run_id": run_id,
        "artifacts": ["path/to/artifact.json"],
        "summary": {"score": 99},
    }

    mock_settings = _make_settings()
    mock_client = AsyncMock()
    mock_client.get_run_record = AsyncMock(return_value=initial_record)
    mock_client.update_run_record = AsyncMock()

    recorded_statuses = []

    async def capture_update(record: RunRecord):
        recorded_statuses.append(record.status)

    mock_client.update_run_record.side_effect = capture_update

    with (
        patch(
            "benchmark_control_arcade.workflow_entrypoint.Settings",
            return_value=mock_settings,
        ),
        patch(
            "benchmark_control_arcade.workflow_entrypoint.GitHubClient",
            return_value=mock_client,
        ),
        patch(
            "benchmark_control_arcade.workflow_entrypoint.aioa_runner.run_aioa_benchmark",
            new_callable=AsyncMock,
            return_value=aioa_result,
        ),
    ):
        from benchmark_control_arcade.workflow_entrypoint import run_workflow

        await run_workflow(run_id, "aioa", spec_json)

    # Must have at least two updates: running, then completed
    assert RunStatus.running in recorded_statuses
    assert RunStatus.completed in recorded_statuses
    # running comes before completed
    running_idx = recorded_statuses.index(RunStatus.running)
    completed_idx = recorded_statuses.index(RunStatus.completed)
    assert running_idx < completed_idx


@pytest.mark.asyncio
async def test_run_workflow_transitions_to_failed_on_runner_error():
    """On runner failure, run.json must be updated to 'failed' (no re-raise)."""
    run_id = "run-fail-001"
    spec_json = _aioa_spec_json()

    initial_record = _make_record(run_id, RunType.aioa, RunStatus.queued)

    mock_settings = _make_settings()
    mock_client = AsyncMock()
    mock_client.get_run_record = AsyncMock(return_value=initial_record)
    mock_client.update_run_record = AsyncMock()

    recorded_statuses = []
    recorded_errors = []

    async def capture_update(record: RunRecord):
        recorded_statuses.append(record.status)
        if record.error:
            recorded_errors.append(record.error)

    mock_client.update_run_record.side_effect = capture_update

    with (
        patch(
            "benchmark_control_arcade.workflow_entrypoint.Settings",
            return_value=mock_settings,
        ),
        patch(
            "benchmark_control_arcade.workflow_entrypoint.GitHubClient",
            return_value=mock_client,
        ),
        patch(
            "benchmark_control_arcade.workflow_entrypoint.aioa_runner.run_aioa_benchmark",
            new_callable=AsyncMock,
            side_effect=RuntimeError("pipeline exploded"),
        ),
    ):
        from benchmark_control_arcade.workflow_entrypoint import run_workflow

        # Must NOT raise — workflow_entrypoint catches errors gracefully
        await run_workflow(run_id, "aioa", spec_json)

    assert RunStatus.failed in recorded_statuses
    assert any("pipeline exploded" in e for e in recorded_errors)


@pytest.mark.asyncio
async def test_run_workflow_running_before_failed():
    """Status must transition queued -> running -> failed (in that order)."""
    run_id = "run-order-001"
    spec_json = _aioa_spec_json()

    initial_record = _make_record(run_id, RunType.aioa, RunStatus.queued)

    mock_settings = _make_settings()
    mock_client = AsyncMock()
    mock_client.get_run_record = AsyncMock(return_value=initial_record)

    recorded_statuses = []

    async def capture_update(record: RunRecord):
        recorded_statuses.append(record.status)

    mock_client.update_run_record.side_effect = capture_update

    with (
        patch(
            "benchmark_control_arcade.workflow_entrypoint.Settings",
            return_value=mock_settings,
        ),
        patch(
            "benchmark_control_arcade.workflow_entrypoint.GitHubClient",
            return_value=mock_client,
        ),
        patch(
            "benchmark_control_arcade.workflow_entrypoint.aioa_runner.run_aioa_benchmark",
            new_callable=AsyncMock,
            side_effect=ValueError("bad spec"),
        ),
    ):
        from benchmark_control_arcade.workflow_entrypoint import run_workflow

        await run_workflow(run_id, "aioa", spec_json)

    assert recorded_statuses[0] == RunStatus.running
    assert recorded_statuses[-1] == RunStatus.failed


# ---------------------------------------------------------------------------
# Tests: __main__ entrypoint
# ---------------------------------------------------------------------------


def test_module_has_main_block():
    """workflow_entrypoint.py must be runnable as __main__."""
    import importlib.util
    import pathlib

    path = (
        pathlib.Path(__file__).parent.parent
        / "src"
        / "benchmark_control_arcade"
        / "workflow_entrypoint.py"
    )
    source = path.read_text()
    assert 'if __name__ == "__main__"' in source, (
        "workflow_entrypoint.py must have a __main__ block for `python -m` invocation"
    )
