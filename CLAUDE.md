# Benchmark Automation — Project Guardrails

## Overview

This repo contains the benchmark control plane for AIOA (AI Overview Audit) and GEO
(Generative Engine Optimization) benchmark runs. The control plane is exposed as an Arcade
MCP server (`benchmark-control-arcade`) and drives runs via the Claude Agent SDK.

## Output locations

All benchmark run artifacts must be written to the canonical layout under `runs/`:

```
runs/
  <run_id>/
    run.json          # RunRecord — machine-readable summary and status
    report.md         # Human-readable markdown report
    evidence.json     # Raw evidence collected during the run
    artifacts/        # Any additional files produced by the run
```

Historical run records are pushed to the `benchmark-data` branch of the configured GitHub repo.

## Rules

- **Do not commit `.env` files.** All secrets are supplied via environment variables or a
  `.env` file that is listed in `.gitignore`. Never stage or commit `.env`.
- **Do not write run artifacts outside the canonical `runs/` layout.** Agents must not write
  files directly; the Python runner writes all output after receiving the agent result.
- **Do not hard-code API keys or tokens.** Use the `Settings` class in
  `tools/benchmark_control_arcade/src/benchmark_control_arcade/config.py`.
- **Prompt assets live in the repo**, not in `~/.claude/skills/`. The canonical location is
  `tools/benchmark_control_arcade/prompts/`.

## Key packages

| Path | Purpose |
|------|---------|
| `tools/benchmark_control_arcade/` | MCP control plane server + Python runners |
| `tools/geo_audit_arcade/` | GEO audit Arcade toolkit |
| `aioa/` | AIOA pipeline |

## Environment variables

See `aioa/.env.example` for required variables. For GEO runs, also set:

- `GEO_AUDIT_MCP_URL` — HTTP URL of the geo-audit MCP server
- `GEO_ANALYZER_MCP_URL` — HTTP URL of the geo-analyzer MCP server (optional)
