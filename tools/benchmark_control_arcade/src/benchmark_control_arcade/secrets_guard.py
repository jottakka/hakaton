"""Utilities for preventing secret leakage in outbound content.

Usage:
    from benchmark_control_arcade.secrets_guard import assert_no_secrets
    assert_no_secrets(response_text, settings)
"""

from __future__ import annotations

from benchmark_control_arcade.config import Settings


def assert_no_secrets(text: str, settings: Settings) -> None:
    """Raise ValueError if any known secret value appears in *text*.

    Only call this at output boundaries (MCP response bodies, log lines).
    Never call it inside hot loops on large blobs.
    """
    token = settings.github_token.get_secret_value()
    if token and token in text:
        raise ValueError(
            "secret value found in outbound content — refusing to emit"
        )
