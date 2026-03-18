"""Tests for orchestrator batching, merging, scoring, and synthesis."""

from __future__ import annotations

import json

import pytest

from src.orchestrator import (
    batch_items,
    merge_subagent_results,
    run_orchestrator,
    run_subagent,
)

# ---------------------------------------------------------------------------
# batch_items
# ---------------------------------------------------------------------------


def test_batch_items_splits_prompts_and_terms():
    prompts = [{"id": f"p{i:03d}", "text": f"prompt {i}"} for i in range(1, 6)]
    terms = [{"id": f"s{i:03d}", "query": f"term {i}"} for i in range(1, 4)]
    model_results = [
        {"prompt_id": "p001", "model": "a", "raw_response": "resp a1"},
        {"prompt_id": "p001", "model": "b", "raw_response": "resp b1"},
        {"prompt_id": "p003", "model": "a", "raw_response": "resp a3"},
    ]
    search_results = [
        {
            "term_id": "s001",
            "engine": "google",
            "results": [{"position": 1, "title": "x", "url": "u"}],
        },
        {"term_id": "s002", "engine": "google", "results": []},
    ]

    batches = batch_items(prompts, model_results, terms, search_results, batch_size=3)

    all_prompt_ids = []
    all_term_ids = []
    all_mr_count = 0
    all_sr_count = 0
    for b in batches:
        all_prompt_ids.extend(p["id"] for p in b["prompts"])
        all_term_ids.extend(t["id"] for t in b["terms"])
        all_mr_count += len(b["model_results"])
        all_sr_count += len(b["search_results"])

    assert sorted(all_prompt_ids) == ["p001", "p002", "p003", "p004", "p005"]
    assert sorted(all_term_ids) == ["s001", "s002", "s003"]
    assert all_mr_count == 3
    assert all_sr_count == 2


def test_batch_items_empty_inputs():
    batches = batch_items([], [], [], [])
    assert batches == []


def test_batch_items_associates_results_correctly():
    prompts = [{"id": "p001"}, {"id": "p002"}]
    model_results = [
        {"prompt_id": "p001", "model": "m1", "raw_response": "r1"},
        {"prompt_id": "p002", "model": "m1", "raw_response": "r2"},
    ]
    batches = batch_items(prompts, model_results, [], [], batch_size=1)

    assert len(batches) == 2
    assert batches[0]["model_results"][0]["prompt_id"] == "p001"
    assert batches[1]["model_results"][0]["prompt_id"] == "p002"


# ---------------------------------------------------------------------------
# run_subagent (with mocked LLM)
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, text: str):
        self.content = [type("Block", (), {"text": text})()]


class _FakeMessages:
    def __init__(self, text: str):
        self._text = text

    async def create(self, **kwargs):
        return _FakeResponse(self._text)


class _FakeAnthropicClient:
    def __init__(self, text: str):
        self.messages = _FakeMessages(text)


@pytest.mark.asyncio
async def test_run_subagent_scores_and_observes(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    obs_json = json.dumps(
        {"observations": {"p001": "Arcade was mentioned first with positive sentiment."}}
    )
    client = _FakeAnthropicClient(obs_json)
    monkeypatch.setattr("src.orchestrator.anthropic.AsyncAnthropic", lambda api_key: client)

    from src.skills.score_calculation import load_scoring_matrix

    matrix = load_scoring_matrix()

    batch = {
        "prompts": [
            {
                "id": "p001",
                "text": "Best MCP gateway?",
                "category": "mcp",
                "expected_winner": "Arcade",
            }
        ],
        "model_results": [
            {
                "prompt_id": "p001",
                "model": "sonnet",
                "raw_response": "Arcade is the leading MCP gateway. Composio also offers tools.",
            },
        ],
        "terms": [],
        "search_results": [],
    }

    result = await run_subagent(batch, "Arcade", ["Composio"], matrix)

    assert len(result["aio_results"]) == 1
    aio = result["aio_results"][0]
    assert aio["prompt_id"] == "p001"
    assert aio["aggregate_score"]["Arcade"] > 0
    assert aio["aggregate_score"]["Composio"] > 0
    assert aio["aggregate_score"]["Arcade"] > aio["aggregate_score"]["Composio"]


# ---------------------------------------------------------------------------
# merge_subagent_results
# ---------------------------------------------------------------------------


def test_merge_subagent_results_combines_and_finds_gaps():
    outputs = [
        {
            "aio_results": [
                {
                    "prompt_id": "p001",
                    "prompt_text": "best gateway",
                    "expected_winner": "Arcade",
                    "aggregate_score": {"Arcade": 30, "Composio": 80},
                },
            ],
            "seo_results": [
                {
                    "term_id": "s001",
                    "query": "mcp gateway",
                    "expected_winner": "Arcade",
                    "aggregate_score": {"Arcade": 60, "Composio": 40},
                },
            ],
            "observations": {"p001": "Composio dominated.", "s001": "Arcade ranked well."},
        },
        {
            "aio_results": [
                {
                    "prompt_id": "p002",
                    "prompt_text": "agent auth",
                    "expected_winner": "Arcade",
                    "aggregate_score": {"Arcade": 90, "Composio": 0},
                },
            ],
            "seo_results": [],
            "observations": {"p002": "Arcade was the clear winner."},
        },
    ]

    merged = merge_subagent_results(outputs, "Arcade", ["Composio"])

    assert len(merged["aio_results"]) == 2
    assert len(merged["seo_results"]) == 1
    assert merged["aio_results"][0]["observations"] == "Composio dominated."
    assert merged["aio_results"][1]["observations"] == "Arcade was the clear winner."
    assert merged["seo_results"][0]["observations"] == "Arcade ranked well."

    assert "comparison_matrix" in merged
    assert "gap_report" in merged

    gap_ids = [g["id"] for g in merged["gap_report"]]
    assert "p001" in gap_ids


# ---------------------------------------------------------------------------
# run_orchestrator end-to-end (mocked LLM)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_orchestrator_end_to_end(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    call_count = 0

    class _MultiClient:
        def __init__(self, **kwargs):
            self.messages = self

        async def create(self, **kwargs):
            nonlocal call_count
            call_count += 1
            system = kwargs.get("system", "")
            if "observation" in system.lower():
                return _FakeResponse(json.dumps({"observations": {"p001": "obs"}}))
            else:
                return _FakeResponse(
                    json.dumps(
                        {
                            "summary": {
                                "arcade_avg_aio_score": 70,
                                "arcade_avg_seo_score": 60,
                                "top_competitor": "Composio",
                                "biggest_gap": "Arcade not mentioned enough",
                            },
                            "gap_recommendations": {},
                        }
                    )
                )

    monkeypatch.setattr("src.orchestrator.anthropic.AsyncAnthropic", _MultiClient)

    analysis = await run_orchestrator(
        run_id="test-run",
        model_results=[
            {"prompt_id": "p001", "model": "sonnet", "raw_response": "Arcade is great for MCP."},
        ],
        search_results=[],
        competitor_config={"target": "Arcade", "competitors": ["Composio"]},
        prompts=[
            {"id": "p001", "text": "Best MCP?", "category": "mcp", "expected_winner": "Arcade"}
        ],
        terms=[],
    )

    assert analysis["run_id"] == "test-run"
    assert "generated_at" in analysis
    assert "summary" in analysis
    assert "aio_results" in analysis
    assert "gap_report" in analysis
    assert "comparison_matrix" in analysis
    assert call_count >= 2


@pytest.mark.asyncio
async def test_run_orchestrator_sets_null_aio_score_when_no_model_results(monkeypatch):
    """In SEO-only mode (no model_results), run_mode must be 'seo_only'
    and arcade_avg_aio_score must be None."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    synth_json = json.dumps(
        {
            "summary": {
                "arcade_avg_aio_score": None,
                "arcade_avg_seo_score": 55,
                "top_competitor": "Composio",
                "biggest_gap": "s001",
            },
            "gap_recommendations": {},
        }
    )

    class _SEOOnlyClient:
        def __init__(self, **kwargs):
            self.messages = self

        async def create(self, **kwargs):
            system = kwargs.get("system", "")
            if "observation" in system.lower():
                return _FakeResponse(json.dumps({"observations": {"s001": "obs"}}))
            return _FakeResponse(synth_json)

    monkeypatch.setattr("src.orchestrator.anthropic.AsyncAnthropic", _SEOOnlyClient)

    analysis = await run_orchestrator(
        run_id="test-run",
        model_results=[],
        search_results=[
            {
                "engine": "google",
                "term_id": "s001",
                "results": [
                    {
                        "position": 1,
                        "title": "Arcade docs",
                        "url": "https://arcade.dev",
                        "snippet": "...",
                    },
                    {
                        "position": 3,
                        "title": "Composio docs",
                        "url": "https://composio.dev",
                        "snippet": "...",
                    },
                ],
            }
        ],
        competitor_config={"target": "Arcade", "competitors": ["Composio"]},
        prompts=[],
        terms=[
            {"id": "s001", "query": "mcp gateway", "category": "mcp", "expected_winner": "Arcade"}
        ],
    )

    assert analysis["run_mode"] == "seo_only"
    assert analysis["summary"]["arcade_avg_aio_score"] is None


def test_merge_subagent_results_excludes_failed_seo_items_from_comparison():
    """Failed SEO items (status='failed') must not contribute to comparison averages."""
    outputs = [
        {
            "aio_results": [],
            "seo_results": [
                {
                    "term_id": "s001",
                    "query": "mcp gateway",
                    "expected_winner": "Arcade",
                    "status": "failed",
                    "aggregate_score": None,
                    "failed_engines": ["google"],
                }
            ],
            "observations": {},
        }
    ]
    merged = merge_subagent_results(outputs, "Arcade", ["Composio"])
    assert merged["comparison_matrix"]["seo_avg_scores"]["Arcade"] is None
    assert merged["gap_report"] == []


@pytest.mark.asyncio
async def test_run_subagent_marks_partial_when_some_engines_fail(monkeypatch):
    """A term with one ok engine and one failed engine gets status='partial'
    and scores computed only from the ok engine."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    obs_json = json.dumps({"observations": {"s001": "partial obs"}})
    client = _FakeAnthropicClient(obs_json)
    monkeypatch.setattr("src.orchestrator.anthropic.AsyncAnthropic", lambda api_key: client)

    from src.skills.score_calculation import load_scoring_matrix

    matrix = load_scoring_matrix()

    batch = {
        "prompts": [],
        "model_results": [],
        "terms": [
            {"id": "s001", "query": "mcp gateway", "category": "mcp", "expected_winner": "Arcade"}
        ],
        "search_results": [
            {
                "engine": "google",
                "term_id": "s001",
                "results": [
                    {
                        "position": 1,
                        "title": "Arcade docs",
                        "url": "https://arcade.dev",
                        "snippet": "...",
                    },
                    {
                        "position": 3,
                        "title": "Composio docs",
                        "url": "https://composio.dev",
                        "snippet": "...",
                    },
                ],
                "status": "ok",
                "error": None,
            },
            {
                "engine": "bing",
                "term_id": "s001",
                "results": [],
                "status": "failed",
                "error": "timeout",
            },
        ],
    }

    result = await run_subagent(batch, "Arcade", ["Composio"], matrix)

    assert len(result["seo_results"]) == 1
    seo = result["seo_results"][0]
    assert seo["status"] == "partial"
    assert seo["failed_engines"] == ["bing"]
    assert seo["aggregate_score"] is not None
    assert seo["aggregate_score"]["Arcade"] > 0


@pytest.mark.asyncio
async def test_run_orchestrator_fallback_when_synthesis_fails(monkeypatch):
    """When the synthesis LLM call fails, the orchestrator must produce a
    well-formed analysis with a fallback summary instead of crashing."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    call_count = 0

    class _FailingSynthesisClient:
        def __init__(self, **kwargs):
            self.messages = self

        async def create(self, **kwargs):
            nonlocal call_count
            call_count += 1
            system = kwargs.get("system", "")
            if "observation" in system.lower():
                return _FakeResponse(json.dumps({"observations": {"s001": "obs"}}))
            raise RuntimeError("LLM service unavailable")

    monkeypatch.setattr("src.orchestrator.anthropic.AsyncAnthropic", _FailingSynthesisClient)

    analysis = await run_orchestrator(
        run_id="test-run",
        model_results=[],
        search_results=[
            {
                "engine": "google",
                "term_id": "s001",
                "results": [
                    {
                        "position": 1,
                        "title": "Arcade docs",
                        "url": "https://arcade.dev",
                        "snippet": "...",
                    },
                ],
                "status": "ok",
                "error": None,
            }
        ],
        competitor_config={"target": "Arcade", "competitors": ["Composio"]},
        prompts=[],
        terms=[
            {"id": "s001", "query": "mcp gateway", "category": "mcp", "expected_winner": "Arcade"}
        ],
    )

    assert analysis["run_id"] == "test-run"
    assert analysis["run_mode"] == "seo_only"
    assert "summary" in analysis
    assert analysis["summary"]["arcade_avg_aio_score"] is None
    assert isinstance(analysis["summary"]["arcade_avg_seo_score"], (int, float))
    assert "Synthesis failed" in analysis["summary"]["biggest_gap"]
