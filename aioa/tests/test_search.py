"""Tests for search layer MCP adapters and dispatch."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.search import _run_mcp_search, run_all_searches, run_search


def _fake_tool_result(content_text: str, is_error: bool = False):
    """Build a mock CallToolResult with the given text payload."""
    block = MagicMock()
    block.text = content_text
    result = MagicMock()
    result.isError = is_error
    result.content = [block]
    return result


@pytest.mark.asyncio
async def test_run_mcp_search_parses_organic_results():
    serpapi_payload = json.dumps({
        "organic_results": [
            {"position": 1, "title": "Arcade", "link": "https://arcade.dev", "snippet": "one"},
            {"position": 2, "title": "Composio", "link": "https://composio.dev", "snippet": "two"},
        ]
    })
    fake_result = _fake_tool_result(serpapi_payload)

    fake_session = AsyncMock()
    fake_session.initialize = AsyncMock()
    fake_session.call_tool = AsyncMock(return_value=fake_result)
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=False)

    fake_transport = MagicMock()
    fake_transport.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock(), MagicMock()))
    fake_transport.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("src.search.streamable_http_client", return_value=fake_transport),
        patch("src.search.ClientSession", return_value=fake_session),
    ):
        results = await _run_mcp_search("test query")

    assert len(results) == 2
    assert results[0]["position"] == 1
    assert results[0]["url"] == "https://arcade.dev"
    assert results[0]["title"] == "Arcade"
    assert results[1]["position"] == 2
    assert results[1]["snippet"] == "two"

    fake_session.call_tool.assert_called_once_with(
        "GoogleSearch_Search",
        arguments={"query": "test query", "n_results": 10},
    )


@pytest.mark.asyncio
async def test_run_mcp_search_handles_flat_list():
    payload = json.dumps([
        {"position": 1, "title": "A", "url": "https://a.dev", "description": "desc a"},
    ])
    fake_result = _fake_tool_result(payload)

    fake_session = AsyncMock()
    fake_session.initialize = AsyncMock()
    fake_session.call_tool = AsyncMock(return_value=fake_result)
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=False)

    fake_transport = MagicMock()
    fake_transport.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock(), MagicMock()))
    fake_transport.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("src.search.streamable_http_client", return_value=fake_transport),
        patch("src.search.ClientSession", return_value=fake_session),
    ):
        results = await _run_mcp_search("test")

    assert len(results) == 1
    assert results[0]["url"] == "https://a.dev"
    assert results[0]["snippet"] == "desc a"


@pytest.mark.asyncio
async def test_run_mcp_search_raises_on_error():
    fake_result = _fake_tool_result("something went wrong", is_error=True)

    fake_session = AsyncMock()
    fake_session.initialize = AsyncMock()
    fake_session.call_tool = AsyncMock(return_value=fake_result)
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=False)

    fake_transport = MagicMock()
    fake_transport.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock(), MagicMock()))
    fake_transport.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("src.search.streamable_http_client", return_value=fake_transport),
        patch("src.search.ClientSession", return_value=fake_session),
    ):
        with pytest.raises(RuntimeError, match="MCP search failed"):
            await _run_mcp_search("test")


@pytest.mark.asyncio
async def test_run_search_dispatches_engine(monkeypatch):
    async def fake_engine(query: str):
        return [{"position": 1, "title": query, "url": "u", "snippet": "s"}]

    monkeypatch.setattr("src.search._ENGINES", {"x": fake_engine})
    result = await run_search("s001", "hello", "x")
    assert result["engine"] == "x"
    assert result["term_id"] == "s001"
    assert result["results"][0]["title"] == "hello"
    assert "timestamp" in result


@pytest.mark.asyncio
async def test_run_all_searches_fans_out(monkeypatch):
    async def engine_a(query: str):
        return [{"position": 1, "title": "A", "url": "a", "snippet": ""}]

    async def engine_b(query: str):
        return [{"position": 1, "title": "B", "url": "b", "snippet": ""}]

    monkeypatch.setattr("src.search._ENGINES", {"a": engine_a, "b": engine_b})
    results = await run_all_searches("s001", "q")
    by_engine = {r["engine"]: r for r in results}
    assert set(by_engine) == {"a", "b"}
    assert by_engine["a"]["results"][0]["title"] == "A"
    assert by_engine["b"]["results"][0]["title"] == "B"


@pytest.mark.asyncio
async def test_run_all_searches_returns_failed_engine_records(monkeypatch):
    """Failed engines must produce a record with status='failed', not be silently dropped."""
    async def engine_ok(query: str):
        return [{"position": 1, "title": query, "url": "ok", "snippet": ""}]

    async def engine_fail(query: str):
        raise RuntimeError("boom")

    monkeypatch.setattr("src.search._ENGINES", {"ok": engine_ok, "bad": engine_fail})
    results = await run_all_searches("s001", "q")

    assert {item["engine"] for item in results} == {"ok", "bad"}
    assert next(item for item in results if item["engine"] == "ok")["status"] == "ok"
    assert next(item for item in results if item["engine"] == "bad")["status"] == "failed"


@pytest.mark.asyncio
async def test_run_all_searches_keeps_error_text_for_failed_engine(monkeypatch):
    """Failed engine records must carry the error message and an empty results list."""
    async def engine_ok(query: str):
        return [{"position": 1, "title": query, "url": "ok", "snippet": ""}]

    async def engine_fail(query: str):
        raise RuntimeError("boom")

    monkeypatch.setattr("src.search._ENGINES", {"ok": engine_ok, "bad": engine_fail})
    results = await run_all_searches("s001", "q")

    failed = next(item for item in results if item["engine"] == "bad")
    assert failed["error"] == "boom"
    assert failed["results"] == []
