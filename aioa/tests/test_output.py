"""Tests for report writing and terminal summary output."""

from __future__ import annotations

import json
from pathlib import Path

from src.output import _bar, print_summary, write_json_report


def test_write_json_report_creates_file(tmp_path: Path):
    analysis = {"run_id": "r1", "summary": {"arcade_avg_aio_score": 80}}
    output_path = tmp_path / "reports" / "report_r1.json"

    written = write_json_report(analysis, output_path)
    assert written == output_path
    assert output_path.exists()
    assert json.loads(output_path.read_text(encoding="utf-8"))["run_id"] == "r1"


def test_bar_renders_expected_width():
    assert _bar(0, width=10) == "[..........]"
    assert _bar(50, width=10) == "[#####.....]"
    assert _bar(100, width=10) == "[##########]"


def test_bar_handles_none_score():
    assert _bar(None, width=10) == "[..........]"


def test_print_summary_outputs_sections(capsys):
    analysis = {
        "run_id": "run-1",
        "generated_at": "2026-03-17T12:00:00Z",
        "summary": {
            "arcade_avg_aio_score": 72,
            "arcade_avg_seo_score": 45,
            "top_competitor": "Composio",
            "biggest_gap": "p003",
        },
        "aio_results": [
            {
                "prompt_id": "p001",
                "prompt_text": "Which MCP gateway is best?",
                "aggregate_score": {"Arcade": 70, "Composio": 60},
                "observations": "Arcade often appears first.",
            }
        ],
        "seo_results": [
            {
                "term_id": "s001",
                "query": "best mcp gateway",
                "aggregate_score": {"Arcade": 40, "Composio": 80},
                "observations": "Composio ranks above Arcade.",
            }
        ],
        "gap_report": [
            {
                "id": "s001",
                "type": "seo",
                "text": "best mcp gateway",
                "expected": "Arcade",
                "actual_winner": "Composio",
                "arcade_score": 40,
                "winner_score": 80,
                "recommendation": "Improve SEO content.",
            }
        ],
    }
    print_summary(analysis)
    out = capsys.readouterr().out
    assert "AIO ANALYZER" in out
    assert "AIO Results (1 prompts)" in out
    assert "SEO Results (1 terms)" in out
    assert "Gap Report (1 gaps identified)" in out
    assert "Composio" in out


def test_print_summary_shows_seo_only_mode(capsys):
    print_summary(
        {
            "run_id": "run-1",
            "generated_at": "2026-03-18T00:00:00Z",
            "run_mode": "seo_only",
            "summary": {
                "arcade_avg_aio_score": None,
                "arcade_avg_seo_score": 55,
                "top_competitor": "Composio",
                "biggest_gap": "s001",
            },
            "aio_results": [],
            "seo_results": [],
            "gap_report": [],
        }
    )
    out = capsys.readouterr().out
    assert "Run Mode:  SEO-only" in out
    assert "Arcade Avg AIO Score" not in out


def test_print_summary_warns_on_partial_search(capsys):
    """When any SEO term has status='partial' or 'failed', print a warning section."""
    print_summary(
        {
            "run_id": "run-3",
            "generated_at": "2026-03-18T00:00:00Z",
            "run_mode": "seo_only",
            "summary": {
                "arcade_avg_aio_score": None,
                "arcade_avg_seo_score": 55,
                "top_competitor": "Composio",
                "biggest_gap": "s001",
            },
            "aio_results": [],
            "seo_results": [
                {
                    "term_id": "s001",
                    "query": "mcp gateway",
                    "aggregate_score": {"Arcade": 80, "Composio": 60},
                    "status": "ok",
                },
                {
                    "term_id": "s002",
                    "query": "agent auth",
                    "aggregate_score": None,
                    "status": "failed",
                    "failed_engines": ["google"],
                },
            ],
            "gap_report": [],
        }
    )
    out = capsys.readouterr().out
    assert "Incomplete" in out or "incomplete" in out or "WARNING" in out or "failed" in out.lower()


def test_print_summary_parse_error_path(capsys):
    print_summary(
        {
            "run_id": "run-2",
            "generated_at": "now",
            "parse_error": "Orchestrator response was not valid JSON",
            "raw_analysis_text": "raw text from orchestrator",
        }
    )
    out = capsys.readouterr().out
    assert "WARNING: Orchestrator response was not valid JSON" in out
    assert "raw text from orchestrator" in out
