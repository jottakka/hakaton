# geo-audit-local-mcp

Local deterministic MCP server for `geo-site-audit` evidence collection and claim validation.

## What This Does

Exposes two MCP tools:

- **`CollectGeoEvidence`** — deterministic artifact checks (robots.txt, sitemap.xml, llms.txt, llms-full.txt), page metadata, JSON-LD type discovery, heading extraction, title/H1 comparison, first-200-word extraction, and cross-domain subdomain discovery.
- **`ValidateGeoAuditClaims`** — compares a draft GEO audit against the evidence JSON and reports hard contradictions, unsupported claims, missing high-signal facts, and confidence downgrades.

### Tool parameter notes

**`CollectGeoEvidence.target_urls`**: accepts URLs as newline-separated, comma-separated, or a JSON array string.

```
# Newline-separated (most readable)
https://composio.dev/
https://docs.composio.dev/

# Comma-separated
https://composio.dev/, https://docs.composio.dev/

# JSON array
["https://composio.dev/", "https://docs.composio.dev/"]
```

These tools improve consistency and accuracy of `geo-site-audit` without replacing the LLM-driven scoring and synthesis.

## Install

```bash
cd tools/geo_audit_local_mcp
uv sync
```

## Run the Server

### stdio mode (for Cursor / Claude Code)

```bash
cd tools/geo_audit_local_mcp
uv run geo-audit-local-mcp
```

Or equivalently:

```bash
cd tools/geo_audit_local_mcp
uv run python -m geo_audit_local_mcp.app
```

## Register in Cursor

Add to `~/.cursor/mcp.json` (use the absolute path to the package directory):

```json
{
  "mcpServers": {
    "geo-audit-local": {
      "command": "/path/to/your/uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/tools/geo_audit_local_mcp",
        "geo-audit-local-mcp"
      ],
      "env": {}
    }
  }
}
```

Find your `uv` path with `which uv`. The `--directory` value must be an absolute path — Cursor does not resolve relative paths from the workspace root.

## Register in Claude Code

Add to `.claude/settings.json` or the project-level MCP config (same requirement: absolute paths):

```json
{
  "mcpServers": {
    "geo-audit-local": {
      "command": "/path/to/your/uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/tools/geo_audit_local_mcp",
        "geo-audit-local-mcp"
      ],
      "env": {}
    }
  }
}
```

## Run Tests

```bash
cd tools/geo_audit_local_mcp
uv run pytest -q
```

## Architecture

```
src/geo_audit_local_mcp/
├── __init__.py
├── app.py            # MCP app bootstrap, tool registration
├── models.py         # Pydantic contracts for both tools
├── extraction.py     # Pure HTML extraction helpers
├── fetching.py       # HTTP fetch with consistent normalization
├── validation.py     # Deterministic claim validation logic
└── tools/
    ├── __init__.py
    ├── collect_geo_evidence.py
    └── validate_geo_audit_claims.py
```

## Relationship to Other Servers

- This server is **only** for deterministic GEO evidence and validation.
- `geo-analyzer` remains the gateway for Linear issue workflows.
- Do not mix these concerns.
