"""Search Layer — MCP-powered Google Search via Arcade."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

load_dotenv()

# Suppress the harmless "Session termination failed: 202" warning from the SDK.
logging.getLogger("mcp.client.streamable_http").setLevel(logging.ERROR)

# ---------------------------------------------------------------------------
# Security constants
# ---------------------------------------------------------------------------

_ALLOWED_MCP_HOSTS: frozenset[str] = frozenset({
    "api.arcade.dev",
    "localhost",
    "127.0.0.1",
})

_MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "https://api.arcade.dev/mcp/aio")


def _validate_mcp_server_url(url: str) -> None:
    """Raise ValueError if *url* is not an approved HTTPS endpoint."""
    from urllib.parse import urlparse  # noqa: PLC0415

    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(
            f"MCP_SERVER_URL must use https:// scheme (got scheme={parsed.scheme!r}). "
            "Only HTTPS connections to approved hosts are permitted."
        )
    if parsed.hostname not in _ALLOWED_MCP_HOSTS:
        raise ValueError(
            f"MCP_SERVER_URL host is not on the approved allowlist "
            f"(host={parsed.hostname!r}). "
            f"Allowed hosts: {sorted(_ALLOWED_MCP_HOSTS)}"
        )


# ---------------------------------------------------------------------------
# MCP session management
# ---------------------------------------------------------------------------


def _build_mcp_http_client() -> httpx.AsyncClient:
    """Build an httpx client with Arcade auth headers when available."""
    headers: dict[str, str] = {}
    api_key = os.environ.get("ARCADE_API_KEY", "")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    user_id = os.environ.get("ARCADE_USER_ID", "")
    if user_id:
        headers["Arcade-User-ID"] = user_id
    return httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(60.0))


@asynccontextmanager
async def mcp_session() -> AsyncIterator[ClientSession]:
    """Open a single MCP session that can be reused for many tool calls.

    Raises EnvironmentError if ARCADE_API_KEY is not set or empty.
    Raises ValueError if MCP_SERVER_URL is not on the approved allowlist.
    """
    api_key = os.environ.get("ARCADE_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "ARCADE_API_KEY is required but not set. "
            "Set the ARCADE_API_KEY environment variable before running searches."
        )
    mcp_server_url = os.environ.get("MCP_SERVER_URL", _MCP_SERVER_URL)
    _validate_mcp_server_url(mcp_server_url)
    http_client = _build_mcp_http_client()
    async with (
        streamable_http_client(mcp_server_url, http_client=http_client) as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        yield session


# ---------------------------------------------------------------------------
# MCP search runner
# ---------------------------------------------------------------------------


def _parse_search_response(tool_result: Any) -> list[dict[str, Any]]:
    """Parse a CallToolResult into a list of {position, title, url, snippet} dicts."""
    if tool_result.isError:
        raise RuntimeError(f"MCP search failed: {tool_result.content}")

    raw: Any = tool_result.content[0].text if tool_result.content else "[]"
    try:
        data = json.loads(raw)
        while isinstance(data, str):
            data = json.loads(data)
    except (json.JSONDecodeError, TypeError):
        data = []

    if isinstance(data, dict):
        items = data.get("organic_results", data.get("results", []))
    elif isinstance(data, list):
        items = data
    else:
        items = []

    results: list[dict[str, Any]] = []
    for i, item in enumerate(items, start=1):
        results.append(
            {
                "position": item.get("position", i),
                "title": item.get("title", ""),
                "url": item.get("link", item.get("url", "")),
                "snippet": item.get("snippet", item.get("description", "")),
            }
        )
    return results


async def _run_mcp_search(query: str, num_results: int = 10) -> list[dict[str, Any]]:
    """One-shot search: opens its own MCP session. Used when no shared session is available."""
    async with mcp_session() as session:
        tool_result = await session.call_tool(
            "GoogleSearch_Search",
            arguments={"query": query, "n_results": num_results},
        )
    return _parse_search_response(tool_result)


async def _run_mcp_search_with_session(
    session: ClientSession,
    query: str,
    num_results: int = 10,
) -> list[dict[str, Any]]:
    """Search using an already-open MCP session (no extra connect/disconnect)."""
    tool_result = await session.call_tool(
        "GoogleSearch_Search",
        arguments={"query": query, "n_results": num_results},
    )
    return _parse_search_response(tool_result)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_ENGINES = {
    "google": _run_mcp_search,
}


async def run_search(
    term_id: str,
    query: str,
    engine: str,
    *,
    session: ClientSession | None = None,
) -> dict[str, Any]:
    """
    Run a search query against a single engine.

    Returns:
        {
            "engine": "google",
            "term_id": "s001",
            "results": [{position, title, url, snippet}],
            "timestamp": "2026-03-17T12:00:00+00:00"
        }
    """
    if session is not None and engine == "google":
        results = await _run_mcp_search_with_session(session, query)
    else:
        runner = _ENGINES[engine]
        results = await runner(query)
    return {
        "engine": engine,
        "term_id": term_id,
        "results": results,
        "timestamp": datetime.now(UTC).isoformat(),
        "status": "ok",
        "error": None,
    }


async def run_all_searches(
    term_id: str,
    query: str,
    *,
    session: ClientSession | None = None,
) -> list[dict[str, Any]]:
    """Fan out a search term to all engines.

    Individual engine failures are caught and logged; the run continues with
    whichever engines succeeded.
    """
    results = []
    for engine_name in _ENGINES:
        try:
            outcome = await run_search(term_id, query, engine_name, session=session)
            results.append(outcome)
        except Exception as exc:
            print(f"[search] WARN {engine_name}/{term_id} failed: {exc}")
            results.append(
                {
                    "engine": engine_name,
                    "term_id": term_id,
                    "results": [],
                    "timestamp": datetime.now(UTC).isoformat(),
                    "status": "failed",
                    "error": str(exc),
                }
            )
    return results
