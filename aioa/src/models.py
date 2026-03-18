"""Model Layer — LLM API integrations for AIO benchmarking."""

from __future__ import annotations

import asyncio
import os
import time
from datetime import UTC, datetime
from typing import Any

import anthropic
import openai
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Individual model runners
# ---------------------------------------------------------------------------


async def _run_openai(prompt_text: str, model_id: str) -> tuple[str, int]:
    """Call an OpenAI model and return (response_text, latency_ms)."""
    client = openai.AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    start = time.perf_counter()
    response = await client.chat.completions.create(
        model=model_id,
        messages=[{"role": "user", "content": prompt_text}],
        max_completion_tokens=2048,
    )
    latency_ms = int((time.perf_counter() - start) * 1000)
    text = response.choices[0].message.content or ""
    return text, latency_ms


async def _run_anthropic(prompt_text: str, model_id: str) -> tuple[str, int]:
    """Call an Anthropic Claude model and return (response_text, latency_ms)."""
    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    start = time.perf_counter()
    response = await client.messages.create(
        model=model_id,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt_text}],
    )
    latency_ms = int((time.perf_counter() - start) * 1000)
    text = response.content[0].text if response.content else ""
    return text, latency_ms


# ---------------------------------------------------------------------------
# Dispatcher — each key maps to (runner_function, api_model_id)
# ---------------------------------------------------------------------------

_RUNNERS: dict[str, tuple[Any, str]] = {
    "openai-gpt4o": (_run_openai, "gpt-4o"),
    "openai-gpt4o-mini": (_run_openai, "gpt-4o-mini"),
    "anthropic-sonnet": (_run_anthropic, "claude-sonnet-4-5"),
    "anthropic-opus": (_run_anthropic, "claude-opus-4-5"),
}


async def run_model_prompt(prompt_id: str, prompt_text: str, model: str) -> dict[str, Any]:
    """
    Send a prompt to a single LLM and return a structured result dict.

    Returns:
        {
            "model": "openai-gpt54-pro",
            "prompt_id": "p001",
            "raw_response": "...",
            "timestamp": "2026-03-17T12:00:00+00:00",
            "latency_ms": 1230
        }
    """
    runner_fn, model_id = _RUNNERS[model]
    raw_response, latency_ms = await runner_fn(prompt_text, model_id)
    return {
        "model": model,
        "prompt_id": prompt_id,
        "raw_response": raw_response,
        "timestamp": datetime.now(UTC).isoformat(),
        "latency_ms": latency_ms,
    }


async def run_all_models(prompt_id: str, prompt_text: str) -> list[dict[str, Any]]:
    """Fan out a prompt to all 4 LLMs concurrently.

    Individual model failures are caught and logged; the run continues with
    whichever models succeeded.
    """
    outcomes = await asyncio.gather(
        *[run_model_prompt(prompt_id, prompt_text, m) for m in _RUNNERS],
        return_exceptions=True,
    )
    results = []
    for model_name, outcome in zip(_RUNNERS, outcomes, strict=True):
        if isinstance(outcome, BaseException):
            print(f"[models] WARN {model_name}/{prompt_id} failed: {outcome}")
        else:
            results.append(outcome)
    return results
