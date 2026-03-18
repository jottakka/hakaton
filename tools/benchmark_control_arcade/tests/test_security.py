"""Security tests for the BenchmarkControl control plane.

Enforces that:
- Required secrets are present and non-trivial before the server starts.
- Secret values never appear in serialized Settings output (str, repr, JSON).
- secrets_guard rejects known-bad patterns in outbound content.
"""

import json

import pytest
from pydantic import ValidationError


class TestSettingsSecretGuards:
    def test_whitespace_only_token_is_rejected(self, monkeypatch):
        monkeypatch.setenv("GITHUB_OWNER", "acme")
        monkeypatch.setenv("GITHUB_REPO", "benchmarks")
        monkeypatch.setenv("GITHUB_TOKEN", "   ")
        from benchmark_control_arcade.config import Settings

        with pytest.raises(ValidationError, match="blank"):
            Settings()

    def test_token_value_absent_from_str(self, monkeypatch):
        monkeypatch.setenv("GITHUB_OWNER", "acme")
        monkeypatch.setenv("GITHUB_REPO", "benchmarks")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_SUPERSECRET1234")
        from benchmark_control_arcade.config import Settings

        s = Settings()
        assert "ghp_SUPERSECRET1234" not in str(s)

    def test_token_value_absent_from_repr(self, monkeypatch):
        monkeypatch.setenv("GITHUB_OWNER", "acme")
        monkeypatch.setenv("GITHUB_REPO", "benchmarks")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_SUPERSECRET1234")
        from benchmark_control_arcade.config import Settings

        s = Settings()
        assert "ghp_SUPERSECRET1234" not in repr(s)

    def test_token_value_absent_from_model_dump(self, monkeypatch):
        """model_dump() must not leak the raw token value."""
        monkeypatch.setenv("GITHUB_OWNER", "acme")
        monkeypatch.setenv("GITHUB_REPO", "benchmarks")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_SUPERSECRET1234")
        from benchmark_control_arcade.config import Settings

        s = Settings()
        dumped = json.dumps(s.model_dump(), default=str)
        assert "ghp_SUPERSECRET1234" not in dumped

    def test_get_secret_value_returns_raw_token(self, monkeypatch):
        """Callers that explicitly request the secret value must get it."""
        monkeypatch.setenv("GITHUB_OWNER", "acme")
        monkeypatch.setenv("GITHUB_REPO", "benchmarks")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_REAL_TOKEN")
        from benchmark_control_arcade.config import Settings

        s = Settings()
        assert s.github_token.get_secret_value() == "ghp_REAL_TOKEN"


class TestSecretsGuard:
    """Tests for the secrets_guard helper that scans outbound content."""

    def test_raises_on_known_secret_in_text(self, monkeypatch):
        monkeypatch.setenv("GITHUB_OWNER", "acme")
        monkeypatch.setenv("GITHUB_REPO", "benchmarks")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_SENSITIVE")
        from benchmark_control_arcade.config import Settings
        from benchmark_control_arcade.secrets_guard import assert_no_secrets

        s = Settings()
        with pytest.raises(ValueError, match="secret"):
            assert_no_secrets("Error: token=ghp_SENSITIVE was rejected", s)

    def test_passes_when_no_secret_in_text(self, monkeypatch):
        monkeypatch.setenv("GITHUB_OWNER", "acme")
        monkeypatch.setenv("GITHUB_REPO", "benchmarks")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_SENSITIVE")
        from benchmark_control_arcade.config import Settings
        from benchmark_control_arcade.secrets_guard import assert_no_secrets

        s = Settings()
        assert_no_secrets("Run queued with id run-123", s)

    def test_passes_on_empty_string(self, monkeypatch):
        monkeypatch.setenv("GITHUB_OWNER", "acme")
        monkeypatch.setenv("GITHUB_REPO", "benchmarks")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_SENSITIVE")
        from benchmark_control_arcade.config import Settings
        from benchmark_control_arcade.secrets_guard import assert_no_secrets

        s = Settings()
        assert_no_secrets("", s)
