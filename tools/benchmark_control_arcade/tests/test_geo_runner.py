"""Tests for GEO benchmark direct-call runner."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from benchmark_control_arcade.run_models import RunSpec, RunType


def test_geo_runner_rejects_wrong_run_type(tmp_path):
    from benchmark_control_arcade.geo_runner import run_geo_benchmark

    spec = RunSpec(run_type=RunType.aioa, target="composio.dev")
    with pytest.raises(ValueError, match="run_type=geo"):
        asyncio.run(run_geo_benchmark(spec, "run-20260318120000-abc12345", tmp_path))


def test_geo_runner_direct_call_writes_artifacts_and_summary(tmp_path):
    fake_result = {
        "target_url": "https://composio.dev",
        "overall_score": 81,
        "report_markdown": "# GEO Audit\n\nResult",
    }

    with patch(
        "benchmark_control_arcade.geo_runner.run_geo_audit",
        new=AsyncMock(return_value=fake_result),
    ) as mock_run:
        from benchmark_control_arcade.geo_runner import run_geo_benchmark

        spec = RunSpec(run_type=RunType.geo, target="composio.dev")
        result = asyncio.run(run_geo_benchmark(spec, "run-20260318120000-abc12345", tmp_path))

    mock_run.assert_awaited_once()
    assert result["run_id"] == "run-20260318120000-abc12345"
    assert result["summary"] == {"target": "composio.dev", "overall_score": 81}
    assert len(result["artifacts"]) == 2
    assert "report.md" in [p.split("/")[-1] for p in result["artifacts"]]
    assert "report.json" in [p.split("/")[-1] for p in result["artifacts"]]


def test_geo_runner_forwards_options_to_library(tmp_path):
    with patch(
        "benchmark_control_arcade.geo_runner.run_geo_audit",
        new=AsyncMock(return_value={"overall_score": 50, "report_markdown": ""}),
    ) as mock_run:
        from benchmark_control_arcade.geo_runner import run_geo_benchmark

        spec = RunSpec(
            run_type=RunType.geo,
            target="composio.dev",
            options={
                "audit_mode": "quick",
                "coverage_preset": "light",
                "discover_subdomains": False,
            },
        )
        asyncio.run(run_geo_benchmark(spec, "run-20260318120000-abc12345", tmp_path))

    assert mock_run.await_args.kwargs == {
        "target_url": "composio.dev",
        "audit_mode": "quick",
        "coverage_preset": "light",
        "discover_subdomains": False,
    }
