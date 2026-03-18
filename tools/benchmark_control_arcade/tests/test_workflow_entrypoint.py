"""Tests for workflow_entrypoint.run_workflow.

Strategy:
- Patch aioa_runner and geo_runner at module boundaries.
- Use real Pydantic models and real Settings.
- Verify status transitions: queued -> running -> completed/failed.
- Verify routing: run_type="aioa" -> aioa_runner, run_type="geo" -> geo_runner.
- Verify graceful error handling: runner failure -> failed (no re-raise).
"""

import json
from datetime import UTC, datetime
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
    now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=UTC)
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


def _geo_compare_spec_json() -> str:
    return json.dumps(
        {
            "run_type": "geo_compare",
            "target": "arcade.dev",
            "options": {"competitors": ["composio.dev"]},
        }
    )


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


@pytest.mark.asyncio
async def test_run_workflow_routes_to_geo_compare_runner():
    """run_type='geo_compare' must call geo_compare_runner.run_geo_compare_benchmark."""
    run_id = "run-geo-compare-001"
    spec_json = _geo_compare_spec_json()

    initial_record = _make_record(run_id, RunType.geo_compare, RunStatus.queued)
    geo_compare_result = {
        "run_id": run_id,
        "artifacts": [],
        "summary": {
            "target": "arcade.dev",
            "competitors": ["composio.dev"],
            "overall_winner": "arcade.dev",
        },
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
        ) as mock_geo,
        patch(
            "benchmark_control_arcade.workflow_entrypoint.geo_compare_runner.run_geo_compare_benchmark",
            new_callable=AsyncMock,
            return_value=geo_compare_result,
        ) as mock_geo_compare,
    ):
        from benchmark_control_arcade.workflow_entrypoint import run_workflow

        await run_workflow(run_id, "geo_compare", spec_json)

    mock_geo_compare.assert_awaited_once()
    mock_geo.assert_not_awaited()
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


# ---------------------------------------------------------------------------
# Tests: Issue 1 — created_at date drift near midnight
# ---------------------------------------------------------------------------


def test_parse_created_at_from_run_id_extracts_date():
    """_parse_created_at_from_run_id returns the UTC datetime encoded in the run_id."""
    from benchmark_control_arcade.workflow_entrypoint import _parse_created_at_from_run_id

    result = _parse_created_at_from_run_id("run-20200101235900-abc12345")
    assert result is not None
    assert result.year == 2020
    assert result.month == 1
    assert result.day == 1
    assert result.hour == 23
    assert result.minute == 59
    assert result.second == 0


def test_parse_created_at_from_run_id_returns_none_for_unknown_format():
    """_parse_created_at_from_run_id returns None for non-standard run_ids."""
    from benchmark_control_arcade.workflow_entrypoint import _parse_created_at_from_run_id

    assert _parse_created_at_from_run_id("custom-id-without-timestamp") is None
    assert _parse_created_at_from_run_id("run-notadate-abc12345") is None
    assert _parse_created_at_from_run_id("") is None


@pytest.mark.asyncio
async def test_entrypoint_finds_run_when_queued_near_midnight():
    """Entrypoint must use the date embedded in run_id for get_run_record, not datetime.now().

    Scenario: a run is queued at 23:59 on Jan 1 2020.  The workflow picks it
    up just after midnight on Jan 2.  Without the fix, datetime.now() would
    produce a Jan 2 date, causing a 404 because the record lives under the
    Jan 1 path on the data branch.
    """
    # run_id encodes a historical date — clearly different from any "now"
    run_id = "run-20200101235900-abc12345"
    spec_json = _aioa_spec_json()

    queued_at = datetime(2020, 1, 1, 23, 59, 0, tzinfo=UTC)
    initial_record = RunRecord(
        run_id=run_id,
        run_type=RunType.aioa,
        status=RunStatus.queued,
        created_at=queued_at,
        updated_at=queued_at,
        repo="acme/benchmarks",
        workflow_name="run-benchmark.yml",
        data_branch="benchmark-data",
        spec=RunSpec(run_type=RunType.aioa, target="composio.dev"),
    )

    captured_created_at: list[datetime] = []

    async def capture_get_run_record(rid: str, created_at: datetime) -> RunRecord:
        captured_created_at.append(created_at)
        return initial_record

    mock_settings = _make_settings()
    mock_client = AsyncMock()
    mock_client.get_run_record = capture_get_run_record
    mock_client.update_run_record = AsyncMock()
    mock_client._put_file = AsyncMock(return_value={"content": {"sha": "abc"}})

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
            return_value={"run_id": run_id, "artifacts": [], "summary": {}},
        ),
    ):
        from benchmark_control_arcade.workflow_entrypoint import run_workflow

        await run_workflow(run_id, "aioa", spec_json)

    # get_run_record must have been called with the Jan 1 2020 date from the run_id,
    # not with today's date or the Jan 2 date that datetime.now() would return.
    assert len(captured_created_at) == 1
    assert captured_created_at[0].year == 2020
    assert captured_created_at[0].month == 1
    assert captured_created_at[0].day == 1


# ---------------------------------------------------------------------------
# Tests: Issue 2 — artifacts uploaded to data branch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_workflow_uploads_artifacts_to_data_branch():
    """After a successful run, each artifact file must be PUT to the data branch."""
    import tempfile
    from pathlib import Path

    run_id = "run-20260318120000-upload01"
    spec_json = _aioa_spec_json()

    initial_record = _make_record(run_id, RunType.aioa, RunStatus.queued)
    initial_record = initial_record.model_copy(
        update={"created_at": datetime(2026, 3, 18, 12, 0, 0, tzinfo=UTC)}
    )

    mock_settings = _make_settings()
    mock_client = AsyncMock()
    mock_client.get_run_record = AsyncMock(return_value=initial_record)
    mock_client.update_run_record = AsyncMock()
    mock_client._put_file = AsyncMock(return_value={"content": {"sha": "deadbeef"}})

    # Build a real temp directory with a fake artifact file so the entrypoint
    # can read it before uploading.
    with tempfile.TemporaryDirectory() as tmp_dir:
        artifact_rel = f"{run_id}/results.json"
        artifact_abs = Path(tmp_dir) / artifact_rel
        artifact_abs.parent.mkdir(parents=True, exist_ok=True)
        artifact_abs.write_text('{"score": 99}', encoding="utf-8")

        aioa_result = {
            "run_id": run_id,
            "artifacts": [artifact_rel],
            "summary": {"score": 99},
        }

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
            # Redirect the temp dir to our controlled directory
            patch("tempfile.TemporaryDirectory") as mock_tmpdir,
        ):
            mock_tmpdir.return_value.__enter__ = lambda s: tmp_dir
            mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)

            from benchmark_control_arcade.workflow_entrypoint import run_workflow

            await run_workflow(run_id, "aioa", spec_json)

    # _put_file must have been called at least once for the artifact upload.
    # (It may also be called for run record updates by higher-level methods,
    # so we check that at least one call targeted an artifacts/ path.)
    put_file_calls = mock_client._put_file.call_args_list
    artifact_uploads = [c for c in put_file_calls if "artifacts/" in str(c.args[0])]
    assert len(artifact_uploads) >= 1, (
        f"Expected at least one _put_file call for an artifact path, got calls: {put_file_calls}"
    )

    # The completed RunRecord must include the artifact with the data-branch path.
    update_calls = mock_client.update_run_record.call_args_list
    completed_call = next(
        (c for c in update_calls if c.args[0].status == RunStatus.completed),
        None,
    )
    assert completed_call is not None, "No completed RunRecord update was made"
    completed_record = completed_call.args[0]
    assert len(completed_record.artifacts) == 1
    assert "artifacts/" in completed_record.artifacts[0].path
    assert completed_record.artifacts[0].name == "results.json"
