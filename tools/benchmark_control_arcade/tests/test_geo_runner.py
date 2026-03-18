"""Tests for the GEO benchmark runner.

TDD: these tests are written first and drive the implementation in geo_runner.py.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Prompt asset tests
# ---------------------------------------------------------------------------


def test_geo_prompt_requires_collect_before_validate():
    from benchmark_control_arcade.geo_runner import build_geo_system_prompt

    prompt = build_geo_system_prompt()
    assert "CollectGeoEvidence" in prompt
    assert "ValidateGeoAuditClaims" in prompt
    assert prompt.index("CollectGeoEvidence") < prompt.index("ValidateGeoAuditClaims")


def test_geo_prompt_does_not_reference_home_skills():
    from benchmark_control_arcade.geo_runner import build_geo_system_prompt

    prompt = build_geo_system_prompt()
    assert "~/.claude" not in prompt
    assert "/skills/" not in prompt


def test_geo_prompt_mentions_exhaustive_default():
    from benchmark_control_arcade.geo_runner import build_geo_system_prompt

    prompt = build_geo_system_prompt()
    assert "exhaustive" in prompt.lower()


def test_geo_prompt_mentions_structured_output():
    from benchmark_control_arcade.geo_runner import build_geo_system_prompt

    prompt = build_geo_system_prompt()
    # Must tell agent to produce structured output matching the schema
    assert "structured" in prompt.lower() or "json" in prompt.lower()


# ---------------------------------------------------------------------------
# Runner validation tests
# ---------------------------------------------------------------------------


def test_geo_runner_requires_mcp_url_setting(monkeypatch):
    monkeypatch.setenv("GITHUB_OWNER", "acme")
    monkeypatch.setenv("GITHUB_REPO", "benchmarks")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    # geo_audit_mcp_url NOT set → should raise ValueError
    monkeypatch.delenv("GEO_AUDIT_MCP_URL", raising=False)

    from benchmark_control_arcade.geo_runner import run_geo_benchmark
    from benchmark_control_arcade.run_models import RunSpec, RunType

    spec = RunSpec(run_type=RunType.geo, target="composio.dev")
    with pytest.raises(ValueError, match="geo_audit_mcp_url"):
        asyncio.run(run_geo_benchmark(spec, "run-123", Path("/tmp/test")))


# ---------------------------------------------------------------------------
# SDK boundary tests
# ---------------------------------------------------------------------------


def _make_mock_result_message(text: str) -> MagicMock:
    """Build a minimal fake ResultMessage with a text content block."""
    block = MagicMock()
    block.type = "text"
    block.text = text

    msg = MagicMock()
    msg.__class__.__name__ = "ResultMessage"
    type(msg).__name__ = "ResultMessage"
    msg.content = [block]
    return msg


def test_geo_runner_builds_structured_output_request(monkeypatch, tmp_path):
    """The runner must pass the system prompt and schema to the SDK query call."""
    monkeypatch.setenv("GITHUB_OWNER", "acme")
    monkeypatch.setenv("GITHUB_REPO", "benchmarks")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("GEO_AUDIT_MCP_URL", "https://geo-audit.example.com/mcp")

    # Minimal valid GEO result JSON
    fake_result_json = json.dumps(
        {
            "target_url": "https://composio.dev",
            "overall_score": 72,
            "claims": [],
            "evidence": [],
            "report_markdown": "# GEO Audit\n\nTest report.",
        }
    )

    fake_result_msg = _make_mock_result_message(fake_result_json)

    captured: dict = {}

    async def fake_query(*, prompt, options=None, transport=None):
        captured["prompt"] = prompt
        captured["options"] = options
        # Yield the fake result message
        yield fake_result_msg

    with patch("benchmark_control_arcade.geo_runner.query", new=fake_query):
        from benchmark_control_arcade.geo_runner import run_geo_benchmark
        from benchmark_control_arcade.run_models import RunSpec, RunType

        spec = RunSpec(run_type=RunType.geo, target="composio.dev")
        result = asyncio.run(run_geo_benchmark(spec, "run-abc", tmp_path))

    # System prompt must be set
    assert captured["options"] is not None
    assert captured["options"].system_prompt is not None
    assert "CollectGeoEvidence" in captured["options"].system_prompt

    # The user prompt must name the target
    assert "composio.dev" in captured["prompt"]

    # The MCP server must be configured
    mcp_servers = captured["options"].mcp_servers
    assert isinstance(mcp_servers, dict)
    assert len(mcp_servers) >= 1
    # At least one server URL must match what we set
    urls = [v.get("url", "") for v in mcp_servers.values() if isinstance(v, dict)]
    assert any("geo-audit.example.com" in u for u in urls)

    # Result must contain both machine-readable JSON and report_markdown
    assert "overall_score" in result
    assert "report_markdown" in result


def test_geo_runner_writes_no_files_itself(monkeypatch, tmp_path):
    """The runner must NOT write files; the caller is responsible."""
    monkeypatch.setenv("GITHUB_OWNER", "acme")
    monkeypatch.setenv("GITHUB_REPO", "benchmarks")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("GEO_AUDIT_MCP_URL", "https://geo-audit.example.com/mcp")

    fake_result_json = json.dumps(
        {
            "target_url": "https://composio.dev",
            "overall_score": 80,
            "claims": [],
            "evidence": [],
            "report_markdown": "# Report",
        }
    )

    fake_result_msg = _make_mock_result_message(fake_result_json)

    async def fake_query(*, prompt, options=None, transport=None):
        yield fake_result_msg

    with patch("benchmark_control_arcade.geo_runner.query", new=fake_query):
        from benchmark_control_arcade.geo_runner import run_geo_benchmark
        from benchmark_control_arcade.run_models import RunSpec, RunType

        spec = RunSpec(run_type=RunType.geo, target="composio.dev")
        asyncio.run(run_geo_benchmark(spec, "run-xyz", tmp_path))

    # tmp_path must still be empty — runner writes nothing
    written = list(tmp_path.iterdir())
    assert written == [], f"Runner unexpectedly wrote files: {written}"
