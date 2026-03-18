"""Tests for pipeline orchestration and wiring."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from src.input_layer import CompetitorConfig
from src.pipeline import run_ad_hoc_query, run_full_pipeline


@asynccontextmanager
async def _fake_mcp_session():
    yield None


class FakeStore:
    def __init__(self) -> None:
        self.initialized = False
        self.run_id = "run-123"
        self.runs: list[tuple[str, str, dict]] = []
        self.model_saves: list[dict] = []
        self.search_saves: list[dict] = []
        self.analysis_saves: list[dict] = []

    async def init(self) -> None:
        self.initialized = True

    async def create_run(self, prompt_set_id: str, term_set_id: str, competitor_config: dict, run_id: str | None = None) -> str:
        self.runs.append((prompt_set_id, term_set_id, competitor_config))
        return self.run_id

    async def save_model_result(
        self,
        run_id: str,
        prompt_id: str,
        prompt_text: str,
        model: str,
        raw_response: str,
        latency_ms: int | None = None,
    ) -> str:
        self.model_saves.append(
            {
                "run_id": run_id,
                "prompt_id": prompt_id,
                "prompt_text": prompt_text,
                "model": model,
                "raw_response": raw_response,
                "latency_ms": latency_ms,
            }
        )
        return f"m-{len(self.model_saves)}"

    async def save_search_result(
        self,
        run_id: str,
        term_id: str,
        query: str,
        engine: str,
        results: list[dict],
        status: str = "ok",
        error: str | None = None,
    ) -> str:
        self.search_saves.append(
            {
                "run_id": run_id,
                "term_id": term_id,
                "query": query,
                "engine": engine,
                "results": results,
                "status": status,
                "error": error,
            }
        )
        return f"s-{len(self.search_saves)}"

    async def save_analysis_result(self, run_id: str, analysis: dict) -> str:
        self.analysis_saves.append({"run_id": run_id, "analysis": analysis})
        return "a-1"


@pytest.mark.asyncio
async def test_run_full_pipeline_wires_layers(monkeypatch, tmp_path: Path):
    store = FakeStore()
    competitors = CompetitorConfig(target="Arcade", competitors=["Composio"])

    prompt_calls: list[tuple[str, str]] = []
    term_calls: list[tuple[str, str]] = []
    captured_orchestrator: dict = {}
    report_paths: list[Path] = []
    summary_payloads: list[dict] = []

    async def fake_models(prompt_id: str, prompt_text: str) -> list[dict]:
        prompt_calls.append((prompt_id, prompt_text))
        return [
            {
                "model": "openai",
                "prompt_id": prompt_id,
                "raw_response": f"response for {prompt_id}",
                "latency_ms": 111,
            }
        ]

    async def fake_searches(term_id: str, query: str, *, session=None) -> list[dict]:
        term_calls.append((term_id, query))
        return [
            {
                "engine": "google",
                "term_id": term_id,
                "results": [{"position": 1, "title": "Arcade", "url": "https://arcade.dev", "snippet": "..."}],
                "status": "ok",
                "error": None,
            }
        ]

    async def fake_orchestrator(**kwargs):
        captured_orchestrator.update(kwargs)
        return {"summary": {"arcade_avg_aio_score": 80}}

    def fake_write_json_report(analysis: dict, output_path: str | Path):
        report_paths.append(Path(output_path))
        return Path(output_path)

    def fake_print_summary(analysis: dict):
        summary_payloads.append(analysis)

    monkeypatch.setattr("src.pipeline.run_all_models", fake_models)
    monkeypatch.setattr("src.pipeline.run_all_searches", fake_searches)
    monkeypatch.setattr("src.pipeline.mcp_session", _fake_mcp_session)
    monkeypatch.setattr("src.pipeline.run_orchestrator", fake_orchestrator)
    monkeypatch.setattr("src.pipeline.write_json_report", fake_write_json_report)
    monkeypatch.setattr("src.pipeline.print_summary", fake_print_summary)

    from src.input_layer import Prompt, PromptSet, SearchTerm, TermSet

    prompt_set = PromptSet(
        prompt_set_id="p-set",
        prompts=[Prompt(id="p001", text="prompt 1"), Prompt(id="p002", text="prompt 2")],
    )
    term_set = TermSet(
        term_set_id="t-set",
        terms=[SearchTerm(id="s001", query="query 1"), SearchTerm(id="s002", query="query 2")],
    )

    analysis = await run_full_pipeline(
        prompt_set=prompt_set,
        term_set=term_set,
        competitors=competitors,
        output_dir=tmp_path,
        store=store,
    )

    assert store.initialized is True
    assert len(store.runs) == 1
    # AIO model layer is skipped in current SEO-only mode
    assert len(prompt_calls) == 0
    assert len(term_calls) == 2
    assert len(store.model_saves) == 0
    assert len(store.search_saves) == 2
    assert len(store.analysis_saves) == 1
    assert captured_orchestrator["run_id"] == store.run_id
    assert len(captured_orchestrator["model_results"]) == 0
    assert len(captured_orchestrator["search_results"]) == 2
    assert report_paths and report_paths[0].name == "report_run-123.json"
    assert summary_payloads and summary_payloads[0] == analysis


@pytest.mark.asyncio
async def test_run_full_pipeline_marks_seo_only_mode(monkeypatch, tmp_path: Path):
    """When model_results is empty, the analysis must carry run_mode='seo_only'
    and arcade_avg_aio_score must be None."""
    import json

    store = FakeStore()
    competitors = CompetitorConfig(target="Arcade", competitors=["Composio"])

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    async def fake_searches(term_id: str, query: str, *, session=None) -> list[dict]:
        return [
            {
                "engine": "google",
                "term_id": term_id,
                "results": [
                    {"position": 1, "title": "Arcade docs", "url": "https://arcade.dev", "snippet": "..."},
                    {"position": 2, "title": "Composio docs", "url": "https://composio.dev", "snippet": "..."},
                ],
                "status": "ok",
                "error": None,
            }
        ]

    obs_json = json.dumps({"observations": {"adhoc_s1": "Arcade ranked #1."}})
    synth_json = json.dumps({
        "summary": {
            "arcade_avg_aio_score": None,
            "arcade_avg_seo_score": 55,
            "top_competitor": "Composio",
            "biggest_gap": "adhoc_s1",
        },
        "gap_recommendations": {},
    })

    class _FakeAnthropicClient:
        def __init__(self, **kwargs):
            self.messages = self

        async def create(self, **kwargs):
            system = kwargs.get("system", "")
            text = obs_json if "observation" in system.lower() else synth_json
            return type("R", (), {"content": [type("B", (), {"text": text})()]})()

    monkeypatch.setattr("src.orchestrator.anthropic.AsyncAnthropic", _FakeAnthropicClient)
    monkeypatch.setattr("src.pipeline.run_all_searches", fake_searches)
    monkeypatch.setattr("src.pipeline.mcp_session", _fake_mcp_session)

    from src.input_layer import SearchTerm, TermSet

    term_set = TermSet(
        term_set_id="t-set",
        terms=[SearchTerm(id="adhoc_s1", query="best mcp gateway")],
    )
    from src.input_layer import PromptSet
    prompt_set = PromptSet(prompt_set_id="p-set", prompts=[])

    analysis = await run_full_pipeline(
        prompt_set=prompt_set,
        term_set=term_set,
        competitors=competitors,
        output_dir=tmp_path,
        store=store,
    )

    assert analysis["run_mode"] == "seo_only"
    assert analysis["summary"]["arcade_avg_aio_score"] is None


@pytest.mark.asyncio
async def test_run_ad_hoc_query_builds_sets_and_delegates(monkeypatch):
    captured: dict = {}

    async def fake_run_full_pipeline(prompt_set, term_set, competitors, output_dir, store=None):
        captured["prompt_set"] = prompt_set
        captured["term_set"] = term_set
        captured["competitors"] = competitors
        captured["output_dir"] = output_dir
        captured["store"] = store
        return {"ok": True}

    monkeypatch.setattr("src.pipeline.run_full_pipeline", fake_run_full_pipeline)

    competitors = CompetitorConfig(target="Arcade", competitors=["Composio"])
    fake_store = object()
    result = await run_ad_hoc_query(
        query="Best MCP gateway?",
        competitors=competitors,
        output_dir="custom-out",
        store=fake_store,
    )

    assert result == {"ok": True}
    assert captured["prompt_set"].prompt_set_id == "adhoc"
    assert captured["term_set"].term_set_id == "adhoc"
    assert captured["prompt_set"].prompts[0].expected_winner == "Arcade"
    assert captured["term_set"].terms[0].expected_winner == "Arcade"
    assert captured["output_dir"] == "custom-out"
    assert captured["store"] is fake_store
