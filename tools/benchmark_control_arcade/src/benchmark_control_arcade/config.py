"""Typed settings for the BenchmarkControl Arcade server.

All required values come from environment variables (or a .env file at the
repo root). The server fails fast on startup if required fields are missing.
"""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """BenchmarkControl runtime configuration.

    Required:
        github_owner: GitHub org or username that owns the benchmarks repo.
        github_repo: Repository name.
        github_token: PAT with repo + workflow scopes. Never logged.

    Optional with defaults:
        github_data_branch: Branch that stores historical run records.
        github_run_workflow: Workflow file dispatched by StartRun.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required GitHub context
    github_owner: str
    github_repo: str
    github_token: SecretStr

    # Defaults that match .env.example
    github_data_branch: str = "benchmark-data"
    github_run_workflow: str = "run-benchmark.yml"
