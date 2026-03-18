"""Tests for model layer API adapters and dispatch."""

from __future__ import annotations

import pytest

from src.models import (
    _run_anthropic,
    _run_openai,
    run_all_models,
    run_model_prompt,
)


@pytest.mark.asyncio
async def test_run_openai_returns_text_and_latency(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    class FakeCompletions:
        async def create(self, **kwargs):
            msg = type("Msg", (), {"content": "openai output"})()
            choice = type("Choice", (), {"message": msg})()
            return type("Resp", (), {"choices": [choice]})()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr("src.models.openai.AsyncOpenAI", lambda api_key: FakeClient())

    text, latency = await _run_openai("hello", "gpt-test")
    assert text == "openai output"
    assert isinstance(latency, int)
    assert latency >= 0


@pytest.mark.asyncio
async def test_run_anthropic_returns_text_and_latency(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")

    class FakeMessages:
        async def create(self, **kwargs):
            block = type("Block", (), {"text": "anthropic output"})()
            return type("Resp", (), {"content": [block]})()

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr("src.models.anthropic.AsyncAnthropic", lambda api_key: FakeClient())

    text, latency = await _run_anthropic("hello", "claude-test")
    assert text == "anthropic output"
    assert isinstance(latency, int)
    assert latency >= 0


@pytest.mark.asyncio
async def test_run_model_prompt_uses_runner(monkeypatch):
    async def fake_runner(prompt_text: str, model_id: str):
        assert model_id == "provider-test-id"
        return f"response:{prompt_text}", 42

    monkeypatch.setattr("src.models._RUNNERS", {"test-model": (fake_runner, "provider-test-id")})

    result = await run_model_prompt("p001", "prompt text", "test-model")
    assert result["model"] == "test-model"
    assert result["prompt_id"] == "p001"
    assert result["raw_response"] == "response:prompt text"
    assert result["latency_ms"] == 42
    assert "timestamp" in result


@pytest.mark.asyncio
async def test_run_all_models_fans_out(monkeypatch):
    async def runner_a(prompt_text: str, model_id: str):
        assert model_id == "model-a-id"
        return "A", 1

    async def runner_b(prompt_text: str, model_id: str):
        assert model_id == "model-b-id"
        return "B", 2

    monkeypatch.setattr(
        "src.models._RUNNERS",
        {"a": (runner_a, "model-a-id"), "b": (runner_b, "model-b-id")},
    )

    results = await run_all_models("p123", "hello")
    by_model = {r["model"]: r for r in results}
    assert set(by_model) == {"a", "b"}
    assert by_model["a"]["raw_response"] == "A"
    assert by_model["b"]["raw_response"] == "B"


@pytest.mark.asyncio
async def test_run_all_models_skips_failed_models(monkeypatch):
    async def runner_ok(prompt_text: str, model_id: str):
        return f"{model_id}:{prompt_text}", 5

    async def runner_fail(prompt_text: str, model_id: str):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "src.models._RUNNERS",
        {"ok": (runner_ok, "ok-id"), "bad": (runner_fail, "bad-id")},
    )

    results = await run_all_models("p123", "hello")

    assert results == [
        {
            "model": "ok",
            "prompt_id": "p123",
            "raw_response": "ok-id:hello",
            "timestamp": results[0]["timestamp"],
            "latency_ms": 5,
        }
    ]
