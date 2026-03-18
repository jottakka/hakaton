"""Security tests for AIOA — fail-fast API key checks and URL allowlist."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.search import _build_mcp_http_client, mcp_session


# ---------------------------------------------------------------------------
# ARCADE_API_KEY required before search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_arcade_api_key_required_before_search(monkeypatch):
    """With no ARCADE_API_KEY set, opening an mcp_session should raise EnvironmentError."""
    monkeypatch.delenv("ARCADE_API_KEY", raising=False)
    # Reload the module-level state by importing the guarded entry-point
    with pytest.raises(EnvironmentError, match="ARCADE_API_KEY"):
        async with mcp_session():
            pass  # should not reach here


@pytest.mark.asyncio
async def test_arcade_api_key_empty_string_is_rejected(monkeypatch):
    """An empty string ARCADE_API_KEY must also be rejected."""
    monkeypatch.setenv("ARCADE_API_KEY", "")
    with pytest.raises(EnvironmentError, match="ARCADE_API_KEY"):
        async with mcp_session():
            pass


@pytest.mark.asyncio
async def test_arcade_api_key_present_does_not_raise(monkeypatch):
    """A non-empty ARCADE_API_KEY must let the session proceed (up to the HTTP call)."""
    monkeypatch.setenv("ARCADE_API_KEY", "test-key-value")
    monkeypatch.setenv("MCP_SERVER_URL", "https://api.arcade.dev/mcp/AIO")

    fake_session = AsyncMock()
    fake_session.initialize = AsyncMock()
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=False)

    fake_transport = MagicMock()
    fake_transport.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock(), MagicMock()))
    fake_transport.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("src.search.streamable_http_client", return_value=fake_transport),
        patch("src.search.ClientSession", return_value=fake_session),
    ):
        async with mcp_session():
            pass  # must reach here without raising


# ---------------------------------------------------------------------------
# MCP_SERVER_URL allowlist
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_server_url_rejects_unknown_host(monkeypatch):
    """Setting MCP_SERVER_URL to an unlisted host must raise ValueError."""
    monkeypatch.setenv("ARCADE_API_KEY", "test-key-value")
    monkeypatch.setenv("MCP_SERVER_URL", "https://evil.example.com/mcp")
    with pytest.raises(ValueError, match="MCP_SERVER_URL"):
        async with mcp_session():
            pass


@pytest.mark.asyncio
async def test_mcp_server_url_rejects_http_scheme(monkeypatch):
    """Plain http:// must be rejected even for allowed hosts (requires HTTPS)."""
    monkeypatch.setenv("ARCADE_API_KEY", "test-key-value")
    monkeypatch.setenv("MCP_SERVER_URL", "http://api.arcade.dev/mcp/AIO")
    with pytest.raises(ValueError, match="MCP_SERVER_URL"):
        async with mcp_session():
            pass


@pytest.mark.asyncio
async def test_mcp_server_url_allows_default_arcade_host(monkeypatch):
    """The default Arcade host must pass the allowlist check."""
    monkeypatch.setenv("ARCADE_API_KEY", "test-key-value")
    monkeypatch.setenv("MCP_SERVER_URL", "https://api.arcade.dev/mcp/AIO")

    fake_session = AsyncMock()
    fake_session.initialize = AsyncMock()
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=False)

    fake_transport = MagicMock()
    fake_transport.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock(), MagicMock()))
    fake_transport.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("src.search.streamable_http_client", return_value=fake_transport),
        patch("src.search.ClientSession", return_value=fake_session),
    ):
        async with mcp_session():
            pass  # must not raise


# ---------------------------------------------------------------------------
# No secret value in error text
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_secret_value_in_error_text(monkeypatch):
    """If search raises, the exception message must not contain the API key value."""
    secret = "super-secret-key-do-not-leak"
    monkeypatch.setenv("ARCADE_API_KEY", secret)
    monkeypatch.setenv("MCP_SERVER_URL", "https://evil.example.com/mcp")

    try:
        async with mcp_session():
            pass
    except (ValueError, EnvironmentError) as exc:
        assert secret not in str(exc), f"API key leaked in error: {exc}"
    else:
        pytest.fail("Expected an exception but none was raised")
