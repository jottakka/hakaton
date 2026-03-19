## Learned User Preferences
- When creating reusable skills or prompts, keep them environment-agnostic and avoid references to local-only tooling unless the user explicitly wants environment-specific guidance.
- For skills and prompts meant to be exported or reused outside Cursor, follow general Claude-style patterns instead of Cursor-specific assumptions.
- When asked to address open issues or follow-up tasks, plan and analyze first before writing any code or tests.
- Arcade deploy is a manual operator action — never trigger `arcade deploy` or `deploy-mcp-servers.yml` automatically from a CI push; only via `workflow_dispatch`.
- MCP tools that involve LLM analysis should be self-contained: one call receives the sites, fetches evidence internally, runs the analysis, validates, and returns the report. Do not expose separate tools for each step.

## Learned Workspace Facts
- The `geo-analyzer` MCP server in this workspace is an Arcade-backed **Linear issue management gateway** (create/update issues, list teams/projects/labels) — it is not a GEO audit tool despite the name.
- This workspace includes a local `geo-site-audit` workflow backed by deterministic GEO audit tools in `tools/geo_audit_arcade/` (Arcade MCPApp v0.3.0) and `tools/geo_audit_local_mcp/` (FastMCP). The v0.3.0 server exposes `RunGeoSiteAudit` and `RunGeoCompare` as public tools; `CollectGeoEvidence`/`ValidateGeoAuditClaims` are now internal implementation details.
- The canonical code repo is `ArcadeAI/ghost`; historical benchmark run records live on the `benchmark-data` orphan branch. The `geoaudit` and `benchcontrol` gateway slugs are the production cloud endpoints (`https://api.arcade.dev/mcp/geoaudit` and `https://api.arcade.dev/mcp/benchcontrol`).
- The `benchmark-control` Arcade MCP server (`tools/benchmark_control_arcade/`) reads GitHub credentials from `ToolContext.get_secret()` (not `os.environ`) when deployed to Arcade Cloud. Every `@app.tool` must declare `requires_secrets=["GITHUB_TOKEN", "GITHUB_OWNER", "GITHUB_REPO"]` or Arcade won't inject the secrets. The `_settings_from_context(ctx)` helper handles this with fallback to env vars for local dev.
- Arcade injects declared secrets into `ToolContext`, not `os.environ`. `pydantic_settings.BaseSettings` cannot see them. Tools must accept `ctx: ToolContext` as first param and call `ctx.get_secret(key)`.
- Arcade rejects secret names that don't follow its "prefixed ID format" (e.g. `GEO_AUDIT_MCP_URL`, `GITHUB_DATA_BRANCH` caused engine errors). Only truly secret values should be Arcade secrets; non-secret config must be hardcoded defaults in the `Settings` class.
- Arcade MCP servers auto-load credentials from `~/.arcade/credentials.yaml`; `ARCADE_API_KEY` is only required for the AIOA pipeline's direct `httpx` search calls, not for local MCP server startup.
- Arcade gateway slugs are case-sensitive and project-scoped: `https://api.arcade.dev/mcp/aio` (lowercase) is the working Google Search gateway for this workspace; it requires the API key from the ghost Arcade project.
- The AIOA pipeline currently runs in `seo_only` mode; the AIO model layer (LLM fan-out) is intentionally disabled. `arcade_avg_aio_score` is `None` in all pipeline output.
- `aioa/config/` (scoring_matrix.json, prompts_v1.json, terms_v1.json, competitors.json) must be committed to the repo — these files are required at runtime by the pipeline.
- GEO audit tools (`RunGeoSiteAudit`, `RunGeoCompare`) are registered on the `benchcontrol` server alongside benchmark lifecycle tools. GEO benchmark runners now call `run_geo_audit()` / `run_geo_compare()` directly (no claude-agent-sdk loop or MCP round-trip in runners).
- Run `ruff format .` from each package root (not a subdirectory) before committing; CI checks the full package and will fail if any file is missed. Also audit `ruff --fix` diffs carefully — it can silently remove security-critical code such as input validation guards.
- Module-level `os.environ.get()` calls are evaluated at import time; any env-var-dependent validation (API key checks, URL allowlist) must read from `os.environ` inside the function body so `monkeypatch.setenv` works correctly in tests.
