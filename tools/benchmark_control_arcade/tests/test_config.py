"""Tests for BenchmarkControl typed settings."""

import pytest
from pydantic import ValidationError


class TestSettings:
    def test_settings_require_github_owner(self, monkeypatch):
        monkeypatch.delenv("GITHUB_OWNER", raising=False)
        monkeypatch.delenv("GITHUB_REPO", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        from benchmark_control_arcade.config import Settings

        with pytest.raises(ValidationError):
            Settings(_env_file=None)

    def test_settings_require_github_repo(self, monkeypatch):
        monkeypatch.setenv("GITHUB_OWNER", "acme")
        monkeypatch.delenv("GITHUB_REPO", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        from benchmark_control_arcade.config import Settings

        with pytest.raises(ValidationError):
            Settings(_env_file=None)

    def test_settings_require_github_token(self, monkeypatch):
        monkeypatch.setenv("GITHUB_OWNER", "acme")
        monkeypatch.setenv("GITHUB_REPO", "benchmarks")
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        from benchmark_control_arcade.config import Settings

        with pytest.raises(ValidationError):
            Settings(_env_file=None)

    def test_settings_default_data_branch(self, monkeypatch):
        monkeypatch.setenv("GITHUB_OWNER", "acme")
        monkeypatch.setenv("GITHUB_REPO", "benchmarks")
        monkeypatch.setenv("GITHUB_TOKEN", "test-token")
        from benchmark_control_arcade.config import Settings

        settings = Settings()
        assert settings.github_data_branch == "benchmark-data"

    def test_settings_default_run_workflow(self, monkeypatch):
        monkeypatch.setenv("GITHUB_OWNER", "acme")
        monkeypatch.setenv("GITHUB_REPO", "benchmarks")
        monkeypatch.setenv("GITHUB_TOKEN", "test-token")
        from benchmark_control_arcade.config import Settings

        settings = Settings()
        assert settings.github_run_workflow == "run-benchmark.yml"

    def test_settings_can_override_data_branch(self, monkeypatch):
        monkeypatch.setenv("GITHUB_OWNER", "acme")
        monkeypatch.setenv("GITHUB_REPO", "benchmarks")
        monkeypatch.setenv("GITHUB_TOKEN", "test-token")
        monkeypatch.setenv("GITHUB_DATA_BRANCH", "custom-data")
        from benchmark_control_arcade.config import Settings

        settings = Settings()
        assert settings.github_data_branch == "custom-data"

    def test_settings_token_not_logged(self, monkeypatch):
        """Ensure the token value is not exposed via str() or repr()."""
        monkeypatch.setenv("GITHUB_OWNER", "acme")
        monkeypatch.setenv("GITHUB_REPO", "benchmarks")
        monkeypatch.setenv("GITHUB_TOKEN", "super-secret-token-value")
        from benchmark_control_arcade.config import Settings

        s = Settings()
        assert "super-secret-token-value" not in str(s)
        assert "super-secret-token-value" not in repr(s)
