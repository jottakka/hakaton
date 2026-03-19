"""Typed settings for the BenchmarkControl Arcade server.

All required values come from environment variables (or a .env file at the
repo root). The server fails fast on startup if required fields are missing.
"""

from pydantic import SecretStr, field_validator
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

    Optional GEO runner settings:
        geo_audit_mcp_url: HTTP URL for the geo-audit MCP server. Required when
            run_type is "geo".
        geo_analyzer_mcp_url: HTTP URL for the geo-analyzer MCP server.
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

    # Defaults — not secrets, safe to hardcode
    github_data_branch: str = "benchmark-data"
    github_run_workflow: str = "run-benchmark.yml"

    # GEO runner MCP URLs — default to deployed Arcade gateways
    geo_audit_mcp_url: str = "https://api.arcade.dev/mcp/geoaudit"
    geo_analyzer_mcp_url: str | None = None

    @field_validator("github_token", mode="before")
    @classmethod
    def token_must_not_be_blank(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            raise ValueError("blank github_token is not allowed")
        return v
