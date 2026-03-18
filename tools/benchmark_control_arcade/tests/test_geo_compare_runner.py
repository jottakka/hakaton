"""Tests for the GEO competitive comparison runner."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Prompt asset tests
# ---------------------------------------------------------------------------


def test_geo_compare_prompt_requires_collect_before_validate():
    from benchmark_control_arcade.geo_compare_runner import build_geo_compare_system_prompt

    prompt = build_geo_compare_system_prompt()
    assert "CollectGeoEvidence" in prompt
    assert "ValidateGeoAuditClaims" in prompt
    assert prompt.index("CollectGeoEvidence") < prompt.index("ValidateGeoAuditClaims")


def test_geo_compare_prompt_does_not_reference_home_skills():
    from benchmark_control_arcade.geo_compare_runner import build_geo_compare_system_prompt

    prompt = build_geo_compare_system_prompt()
    assert "~/.claude" not in prompt
    assert "/skills/" not in prompt


def test_geo_compare_prompt_mentions_comparison():
    from benchmark_control_arcade.geo_compare_runner import build_geo_compare_system_prompt

    prompt = build_geo_compare_system_prompt()
    lower = prompt.lower()
    assert "comparison" in lower or "compare" in lower or "competitive" in lower


def test_geo_compare_prompt_mentions_structured_output():
    from benchmark_control_arcade.geo_compare_runner import build_geo_compare_system_prompt

    prompt = build_geo_compare_system_prompt()
    lower = prompt.lower()
    assert "structured" in lower or "json" in lower


def test_geo_compare_prompt_references_schema():
    from benchmark_control_arcade.geo_compare_runner import build_geo_compare_system_prompt

    prompt = build_geo_compare_system_prompt()
    assert "geo_compare_output_schema" in prompt


# ---------------------------------------------------------------------------
# Runner validation tests
# ---------------------------------------------------------------------------


def test_geo_compare_runner_requires_mcp_url_setting(monkeypatch):
    monkeypatch.setenv("GITHUB_OWNER", "acme")
    monkeypatch.setenv("GITHUB_REPO", "benchmarks")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.delenv("GEO_AUDIT_MCP_URL", raising=False)

    from benchmark_control_arcade.geo_compare_runner import run_geo_compare_benchmark
    from benchmark_control_arcade.run_models import RunSpec, RunType

    spec = RunSpec(run_type=RunType.geo_compare, target="arcade.dev")
    with pytest.raises(ValueError, match="geo_audit_mcp_url"):
        asyncio.run(run_geo_compare_benchmark(spec, "run-123", Path("/tmp/test")))


def test_geo_compare_runner_rejects_wrong_run_type(monkeypatch):
    monkeypatch.setenv("GITHUB_OWNER", "acme")
    monkeypatch.setenv("GITHUB_REPO", "benchmarks")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("GEO_AUDIT_MCP_URL", "https://geo-audit.example.com/mcp")

    from benchmark_control_arcade.geo_compare_runner import run_geo_compare_benchmark
    from benchmark_control_arcade.run_models import RunSpec, RunType

    spec = RunSpec(run_type=RunType.geo, target="arcade.dev")
    with pytest.raises(ValueError, match="geo_compare"):
        asyncio.run(run_geo_compare_benchmark(spec, "run-123", Path("/tmp/test")))


# ---------------------------------------------------------------------------
# SDK boundary tests
# ---------------------------------------------------------------------------


def _make_mock_result_message(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text

    msg = MagicMock()
    msg.__class__.__name__ = "ResultMessage"
    type(msg).__name__ = "ResultMessage"
    msg.content = [block]
    return msg


def _fake_compare_result(
    target: str = "arcade.dev",
    competitors: list[str] | None = None,
) -> dict:
    if competitors is None:
        competitors = ["composio.dev"]
    all_urls = [target] + competitors
    audits = [
        {
            "url": url,
            "overall_score": 80 if url == target else 70,
            "lever_scores": {
                "content_structure": 20 if url == target else 18,
                "entity_authority": 20 if url == target else 17,
                "technical": 20 if url == target else 18,
                "citation": 20 if url == target else 17,
            },
            "artifacts": {
                "robots_txt": "found",
                "sitemap_xml": "found",
                "llms_txt": "found",
                "llms_full_txt": "not_found",
            },
            "strengths": ["Strong JSON-LD"],
            "weaknesses": ["Missing llms-full.txt"],
            "recommendations": ["Add llms-full.txt"],
        }
        for url in all_urls
    ]
    return {
        "target": target,
        "competitors": competitors,
        "run_date": "2026-03-18",
        "audits": audits,
        "comparison_table": "| Site | Overall |\n|------|---------|",
        "winner_per_lever": {
            "content_structure": target,
            "entity_authority": target,
            "technical": target,
            "citation": target,
        },
        "overall_winner": target,
        "report_markdown": f"# GEO Comparison\n\nWinner: {target}",
    }


def test_geo_compare_runner_passes_all_urls_in_prompt(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_OWNER", "acme")
    monkeypatch.setenv("GITHUB_REPO", "benchmarks")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("GEO_AUDIT_MCP_URL", "https://geo-audit.example.com/mcp")

    result_data = _fake_compare_result("arcade.dev", ["composio.dev", "merge.dev"])
    fake_msg = _make_mock_result_message(json.dumps(result_data))

    captured: dict = {}

    async def fake_query(*, prompt, options=None, transport=None):
        captured["prompt"] = prompt
        captured["options"] = options
        yield fake_msg

    with patch("benchmark_control_arcade.geo_compare_runner.query", new=fake_query):
        from benchmark_control_arcade.geo_compare_runner import run_geo_compare_benchmark
        from benchmark_control_arcade.run_models import RunSpec, RunType

        spec = RunSpec(
            run_type=RunType.geo_compare,
            target="arcade.dev",
            options={"competitors": ["composio.dev", "merge.dev"]},
        )
        asyncio.run(run_geo_compare_benchmark(spec, "run-20260318120000-abc12345", tmp_path))

    # Target and all competitors must appear in the user prompt
    assert "arcade.dev" in captured["prompt"]
    assert "composio.dev" in captured["prompt"]
    assert "merge.dev" in captured["prompt"]


def test_geo_compare_runner_summary_has_competitors(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_OWNER", "acme")
    monkeypatch.setenv("GITHUB_REPO", "benchmarks")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("GEO_AUDIT_MCP_URL", "https://geo-audit.example.com/mcp")

    competitors = ["composio.dev", "merge.dev"]
    result_data = _fake_compare_result("arcade.dev", competitors)
    fake_msg = _make_mock_result_message(json.dumps(result_data))

    async def fake_query(*, prompt, options=None, transport=None):
        yield fake_msg

    with patch("benchmark_control_arcade.geo_compare_runner.query", new=fake_query):
        from benchmark_control_arcade.geo_compare_runner import run_geo_compare_benchmark
        from benchmark_control_arcade.run_models import RunSpec, RunType

        spec = RunSpec(
            run_type=RunType.geo_compare,
            target="arcade.dev",
            options={"competitors": competitors},
        )
        result = asyncio.run(
            run_geo_compare_benchmark(spec, "run-20260318120000-abc12345", tmp_path)
        )

    assert "summary" in result
    assert result["summary"]["competitors"] == competitors


def test_geo_compare_runner_summary_has_overall_winner(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_OWNER", "acme")
    monkeypatch.setenv("GITHUB_REPO", "benchmarks")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("GEO_AUDIT_MCP_URL", "https://geo-audit.example.com/mcp")

    result_data = _fake_compare_result("arcade.dev", ["composio.dev"])
    fake_msg = _make_mock_result_message(json.dumps(result_data))

    async def fake_query(*, prompt, options=None, transport=None):
        yield fake_msg

    with patch("benchmark_control_arcade.geo_compare_runner.query", new=fake_query):
        from benchmark_control_arcade.geo_compare_runner import run_geo_compare_benchmark
        from benchmark_control_arcade.run_models import RunSpec, RunType

        spec = RunSpec(
            run_type=RunType.geo_compare,
            target="arcade.dev",
            options={"competitors": ["composio.dev"]},
        )
        result = asyncio.run(
            run_geo_compare_benchmark(spec, "run-20260318120000-abc12345", tmp_path)
        )

    assert result["summary"]["overall_winner"] == "arcade.dev"


def test_geo_compare_runner_writes_report_files(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_OWNER", "acme")
    monkeypatch.setenv("GITHUB_REPO", "benchmarks")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("GEO_AUDIT_MCP_URL", "https://geo-audit.example.com/mcp")

    result_data = _fake_compare_result("arcade.dev", ["composio.dev"])
    fake_msg = _make_mock_result_message(json.dumps(result_data))

    async def fake_query(*, prompt, options=None, transport=None):
        yield fake_msg

    with patch("benchmark_control_arcade.geo_compare_runner.query", new=fake_query):
        from benchmark_control_arcade.geo_compare_runner import run_geo_compare_benchmark
        from benchmark_control_arcade.run_models import RunSpec, RunType

        spec = RunSpec(
            run_type=RunType.geo_compare,
            target="arcade.dev",
            options={"competitors": ["composio.dev"]},
        )
        asyncio.run(run_geo_compare_benchmark(spec, "run-20260318120000-abc12345", tmp_path))

    # Publisher must have written files under output_dir
    written = list(tmp_path.rglob("*"))
    filenames = [f.name for f in written if f.is_file()]
    assert "report.md" in filenames
    assert "report.json" in filenames


def test_geo_compare_runner_returns_artifact_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_OWNER", "acme")
    monkeypatch.setenv("GITHUB_REPO", "benchmarks")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("GEO_AUDIT_MCP_URL", "https://geo-audit.example.com/mcp")

    result_data = _fake_compare_result("arcade.dev", ["composio.dev"])
    fake_msg = _make_mock_result_message(json.dumps(result_data))

    async def fake_query(*, prompt, options=None, transport=None):
        yield fake_msg

    with patch("benchmark_control_arcade.geo_compare_runner.query", new=fake_query):
        from benchmark_control_arcade.geo_compare_runner import run_geo_compare_benchmark
        from benchmark_control_arcade.run_models import RunSpec, RunType

        spec = RunSpec(
            run_type=RunType.geo_compare,
            target="arcade.dev",
            options={"competitors": ["composio.dev"]},
        )
        result = asyncio.run(
            run_geo_compare_benchmark(spec, "run-20260318120000-abc12345", tmp_path)
        )

    assert "artifacts" in result
    assert len(result["artifacts"]) == 2
    artifact_names = [Path(p).name for p in result["artifacts"]]
    assert "report.md" in artifact_names
    assert "report.json" in artifact_names

    # Paths must be relative (not absolute)
    for path_str in result["artifacts"]:
        assert not Path(path_str).is_absolute()
