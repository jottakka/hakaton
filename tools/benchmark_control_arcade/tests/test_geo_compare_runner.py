"""Tests for GEO compare direct-call runner."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from benchmark_control_arcade.run_models import RunSpec, RunType


def _fake_compare_result(target: str = "arcade.dev", competitors: list[str] | None = None) -> dict:
    if competitors is None:
        competitors = ["composio.dev"]
    return {
        "target": target,
        "competitors": competitors,
        "run_date": "2026-03-18",
        "audits": [
            {"url": target, "overall_score": 80},
            *[{"url": c, "overall_score": 70} for c in competitors],
        ],
        "winner_per_lever": {"content_structure": target},
        "overall_winner": target,
        "report_markdown": "# GEO Comparison",
    }


def test_geo_compare_runner_rejects_wrong_run_type(tmp_path):
    from benchmark_control_arcade.geo_compare_runner import run_geo_compare_benchmark

    spec = RunSpec(run_type=RunType.geo, target="arcade.dev")
    with pytest.raises(ValueError, match="run_type=geo_compare"):
        asyncio.run(run_geo_compare_benchmark(spec, "run-20260318120000-abc12345", tmp_path))


def test_geo_compare_runner_direct_call_writes_artifacts_and_summary(tmp_path):
    with patch(
        "benchmark_control_arcade.geo_compare_runner.run_geo_compare",
        new=AsyncMock(return_value=_fake_compare_result("arcade.dev", ["composio.dev"])),
    ) as mock_run:
        from benchmark_control_arcade.geo_compare_runner import run_geo_compare_benchmark

        spec = RunSpec(
            run_type=RunType.geo_compare,
            target="arcade.dev",
            options={"competitors": ["composio.dev"]},
        )
        result = asyncio.run(
            run_geo_compare_benchmark(spec, "run-20260318120000-abc12345", tmp_path)
        )

    mock_run.assert_awaited_once()
    assert result["summary"]["target"] == "arcade.dev"
    assert result["summary"]["competitors"] == ["composio.dev"]
    assert result["summary"]["overall_winner"] == "arcade.dev"
    assert len(result["artifacts"]) == 2


def test_geo_compare_runner_forwards_options_to_library(tmp_path):
    with patch(
        "benchmark_control_arcade.geo_compare_runner.run_geo_compare",
        new=AsyncMock(return_value=_fake_compare_result("arcade.dev", ["composio.dev"])),
    ) as mock_run:
        from benchmark_control_arcade.geo_compare_runner import run_geo_compare_benchmark

        spec = RunSpec(
            run_type=RunType.geo_compare,
            target="arcade.dev",
            options={
                "competitors": ["composio.dev"],
                "audit_mode": "quick",
                "coverage_preset": "light",
                "discover_subdomains": False,
            },
        )
        asyncio.run(run_geo_compare_benchmark(spec, "run-20260318120000-abc12345", tmp_path))

    assert mock_run.await_args.kwargs == {
        "target": "arcade.dev",
        "competitors": ["composio.dev"],
        "audit_mode": "quick",
        "coverage_preset": "light",
        "discover_subdomains": False,
    }
