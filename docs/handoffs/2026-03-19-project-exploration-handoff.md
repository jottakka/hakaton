# Project Exploration Handoff: Ghost Benchmark Platform

**Repo:** `ArcadeAI/ghost` · `main` branch  
**Date:** 2026-03-19

---

## What this project is

An automated benchmark platform for measuring **AI visibility** — how well a company shows up in AI-generated answers and search results. It runs two types of audits:

- **AIOA** (AI Overview Analysis) — *"Do LLMs mention us when asked about our category?"*  
  Fans out competitive prompts to multiple LLMs + Google Search, scores mentions by position/sentiment.
- **GEO** (Generative Engine Optimization) — *"Is our website readable by AI systems?"*  
  Checks robots.txt, sitemap, llms.txt, JSON-LD, heading structure, citation quality. Returns a 0–100 score across 4 levers.

---

## How to explore the repo

### 1. Start with the docs
```
docs/
  plans/          — implementation plans for major features
  ops/            — GitHub setup, local development
  audits/         — example audit reports (composio-dev, merge-mcp)
  handoffs/       — this file and others
```

Read `docs/audits/2026-03-17-composio-dev/report.md` for a real example GEO report.  
Read `docs/plans/2026-03-18-benchmark-control-plane-implementation-plan.md` for the system design.

### 2. Understand the three tools

| Package | What it does | Where |
|---|---|---|
| `tools/geo_audit_arcade/` | MCP server: `RunGeoSiteAudit`, `RunGeoCompare` | Cloud: `api.arcade.dev/mcp/geoaudit` |
| `tools/benchmark_control_arcade/` | MCP server: `StartRun`, `ListRuns`, `GetRunReport`, etc. | Cloud: `api.arcade.dev/mcp/benchcontrol` |
| `aioa/` | AIOA pipeline: Google Search via Arcade + Claude orchestration | Runs in GitHub Actions |

### 3. Understand the data flow

```
User/Claude web
    ↓  StartRun(run_type, target, options)
benchmark-control (Arcade Cloud)
    ↓  dispatches GitHub Actions workflow
run-benchmark.yml (macos-latest runner)
    ↓  aioa_runner.py  OR  geo_runner.py
    ↓  writes artifacts to benchmark-data branch
benchmark-data branch (ArcadeAI/ghost)
    ↓  run.json + artifacts/report.json + artifacts/<uuid>.json
User retrieves results via:
    GetRunStatus / GetRunReport / ListRuns / SearchGeoReports
```

### 4. Understand the data branch

`benchmark-data` is an orphan branch — it has its own commit history separate from `main`. Every file write during a run creates one commit. Browse it at:

```
github.com/ArcadeAI/ghost/tree/benchmark-data/runs/
```

Structure per run:
```
runs/YYYY/MM/DD/<run_id>/
  run.json                    ← status, summary, elapsed_seconds
  artifacts/
    report_<run_id>.json      ← full structured report
    analysis.json             ← raw orchestrator output
    <uuid>.json × N           ← one per search query (AIOA only)
```

### 5. Understand what's currently active

- **AIOA runs in `seo_only` mode** — the LLM fan-out layer (models.py calling GPT-4o/Claude) is disabled. Only Google Search runs. `arcade_avg_aio_score` is always `null`.
- **GEO runs use `claude-opus-4-5`** on the macos runner via `claude-agent-sdk`. Takes ~12 minutes per run.
- **Scheduled runs** are defined in `run-specs/scheduled/` and fire daily at 06:00 UTC.

### 6. Key config files to know

| File | Purpose |
|---|---|
| `aioa/config/prompts_v1.json` | 56 competitive prompts across 15 categories |
| `aioa/config/terms_v1.json` | 75 search queries (SEO terms) |
| `aioa/config/competitors.json` | Default competitor list (Composio, Workato, etc.) |
| `aioa/config/scoring_matrix.json` | AIO/SEO score weights |
| `.env` (not committed) | Local API keys — see `.env.example` |

### 7. How to run things locally

**Trigger a benchmark via MCP (in Cursor or Claude web):**
```
StartRun(run_type="aioa", target="arcade.dev", options_json="{...}")
```

**Trigger via CLI:**
```bash
gh workflow run run-benchmark.yml \
  --repo ArcadeAI/ghost \
  --field run_id="run-$(date +%Y%m%d%H%M%S)-$(openssl rand -hex 4)" \
  --field run_type="aioa" \
  --field run_spec_json='{"run_type":"aioa","target":"arcade.dev","options":{}}'
```

**Run GEO audit locally (no CI needed):**
```python
from geo_audit_arcade.tools.run_geo_audit import run_geo_audit
result = await run_geo_audit(target_url="https://arcade.dev", audit_mode="quick")
```

---

## What still needs to be built

1. **`CompareGeoAudits` tool** — compare two GEO runs side by side (plan at `docs/plans/2026-03-18-geo-compare-tool-plan.md`)
2. **`geo_compare` run type** — `geo_compare_runner.py` exists but the full pipeline isn't wired into GitHub Actions yet
3. **AIO model layer** — currently disabled; needs re-enabling once models are stable
4. **`SearchGeoReports` date filtering** — basic implementation exists; could be improved with pagination

---

## Secrets reference (for setup)

| Where | Secrets needed |
|---|---|
| Arcade Cloud (ghost project) | `GITHUB_TOKEN`, `GITHUB_OWNER=ArcadeAI`, `GITHUB_REPO=ghost`, `ANTHROPIC_API_KEY` |
| GitHub Actions (ArcadeAI/ghost) | `BENCHMARK_GITHUB_TOKEN`, `ANTHROPIC_API_KEY`, `ARCADE_API_KEY`, `ARCADE_USER_ID`, `GEO_AUDIT_MCP_URL` |
| Local `.env` | All of the above + `OPENAI_API_KEY`, `MCP_SERVER_URL` |
| Cursor `~/.cursor/mcp.json` | `GITHUB_TOKEN`, `GITHUB_OWNER`, `GITHUB_REPO`, `ANTHROPIC_API_KEY`, `ARCADE_API_KEY` |
