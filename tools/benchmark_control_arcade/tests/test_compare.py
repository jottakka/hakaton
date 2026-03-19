"""Tests for the AIOA run comparison helper."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from benchmark_control_arcade.run_models import (
    RunRecord,
    RunSpec,
    RunStatus,
    RunType,
)


def _make_aioa_record(
    run_id: str = "run-a",
    target: str = "composio.dev",
    summary: dict | None = None,
) -> RunRecord:
    now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=UTC)
    return RunRecord(
        run_id=run_id,
        run_type=RunType.aioa,
        status=RunStatus.completed,
        created_at=now,
        updated_at=now,
        repo="acme/benchmarks",
        workflow_name="run-benchmark.yml",
        data_branch="benchmark-data",
        spec=RunSpec(run_type=RunType.aioa, target=target),
        summary=summary or {"score": 80},
    )


def _make_geo_record(run_id: str = "run-geo") -> RunRecord:
    now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=UTC)
    return RunRecord(
        run_id=run_id,
        run_type=RunType.geo,
        status=RunStatus.completed,
        created_at=now,
        updated_at=now,
        repo="acme/benchmarks",
        workflow_name="run-benchmark.yml",
        data_branch="benchmark-data",
        spec=RunSpec(run_type=RunType.geo, target="composio.dev"),
    )


class TestCompareAioaRuns:
    def test_returns_comparison_dict_with_both_run_ids(self):
        from benchmark_control_arcade.compare import compare_aioa_runs

        a = _make_aioa_record("run-a", summary={"score": 80})
        b = _make_aioa_record("run-b", summary={"score": 90})

        result = compare_aioa_runs(a, b)

        assert result["run_id_a"] == "run-a"
        assert result["run_id_b"] == "run-b"

    def test_includes_summaries_for_both_runs(self):
        from benchmark_control_arcade.compare import compare_aioa_runs

        a = _make_aioa_record("run-a", summary={"score": 80})
        b = _make_aioa_record("run-b", summary={"score": 90})

        result = compare_aioa_runs(a, b)

        assert result["summary_a"] == {"score": 80}
        assert result["summary_b"] == {"score": 90}

    def test_rejects_geo_run_as_first_argument(self):
        from benchmark_control_arcade.compare import compare_aioa_runs

        geo = _make_geo_record("run-geo")
        aioa = _make_aioa_record("run-a")

        with pytest.raises(ValueError, match="aioa"):
            compare_aioa_runs(geo, aioa)

    def test_rejects_geo_run_as_second_argument(self):
        from benchmark_control_arcade.compare import compare_aioa_runs

        aioa = _make_aioa_record("run-a")
        geo = _make_geo_record("run-geo")

        with pytest.raises(ValueError, match="aioa"):
            compare_aioa_runs(aioa, geo)

    def test_rejects_both_geo_runs(self):
        from benchmark_control_arcade.compare import compare_aioa_runs

        geo_a = _make_geo_record("run-geo-a")
        geo_b = _make_geo_record("run-geo-b")

        with pytest.raises(ValueError, match="aioa"):
            compare_aioa_runs(geo_a, geo_b)

    def test_result_includes_statuses(self):
        from benchmark_control_arcade.compare import compare_aioa_runs

        a = _make_aioa_record("run-a")
        b = _make_aioa_record("run-b")

        result = compare_aioa_runs(a, b)

        assert result["status_a"] == "completed"
        assert result["status_b"] == "completed"

    def test_result_includes_elapsed_and_artifacts(self):
        from benchmark_control_arcade.compare import compare_aioa_runs

        a = _make_aioa_record("run-a")
        b = _make_aioa_record("run-b")
        a.elapsed_seconds = 12.3
        b.elapsed_seconds = 45.6

        result = compare_aioa_runs(a, b)

        assert result["elapsed_seconds_a"] == 12.3
        assert result["elapsed_seconds_b"] == 45.6
        assert result["artifacts_a"] == []
        assert result["artifacts_b"] == []
