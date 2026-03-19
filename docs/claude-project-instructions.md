# Benchmark Platform — Instructions

You have access to the **benchcontrol** MCP gateway, which provides tools for running and retrieving AI/search visibility benchmarks.

**Gateway:** `https://api.arcade.dev/mcp/benchcontrol`

---

## Tools available

| Tool | Purpose |
|---|---|
| `BenchmarkControl_StartRun` | Queue a new benchmark run |
| `BenchmarkControl_GetRunStatus` | Poll a run's lifecycle |
| `BenchmarkControl_GetLatestRun` | Get the most recent run for a target |
| `BenchmarkControl_GetRunReport` | Fetch the full report |
| `BenchmarkControl_ListRuns` | List/filter recent runs |
| `BenchmarkControl_SearchGeoReports` | Search historical GEO audits |
| `BenchmarkControl_CompareAioaRuns` | Diff two AIOA runs |
| `BenchmarkControl_GetRunArtifacts` | List raw artifact files |

---

## Two benchmark types

**AIOA** (`run_type="aioa"`) — Measures how a site ranks in Google search for competitive queries.  
Returns SEO scores per query, which competitors appear, and a narrative gap analysis.  
Takes ~90 seconds.

**GEO** (`run_type="geo"` or `"geo_compare"`) — Audits how AI-readable a website is.  
Scores 4 levers: content structure, entity authority, technical signals (robots.txt, sitemap, llms.txt), citation quality.  
Returns a 0–100 score and markdown report.  
Takes ~12–20 minutes.

---

## Common workflows

### Get the latest result for a site (fastest)
```
BenchmarkControl_GetLatestRun(
  run_type="aioa",
  target="arcade.dev",
  status="completed",
  include_report=true
)
```
`include_report=true` embeds the full report — no extra call needed.

### Run a new AIOA benchmark
```
BenchmarkControl_StartRun(
  run_type="aioa",
  target="arcade.dev",
  options_json='{"competitors":["Composio","Zapier","Make"]}'
)
```
Returns `run_id` and `estimated_wait_seconds`. Then poll with `GetRunStatus` until `status="completed"`.

### Run a GEO audit (tracked, stored)
```
BenchmarkControl_StartRun(
  run_type="geo",
  target="arcade.dev",
  options_json='{}'
)
```

### List recent runs with filters
```
BenchmarkControl_ListRuns(
  run_type="aioa",
  target="arcade.dev",
  from_date="2026-03-01",
  limit=10
)
```

### Search GEO history
```
BenchmarkControl_SearchGeoReports(
  target="arcade.dev",
  run_type="geo",
  from_date="2026-03-01"
)
```

---

## Key facts

- `arcade_avg_aio_score` is always `null` — the LLM fan-out layer is currently disabled; only Google Search scoring runs.
- `estimated_wait_seconds` in `StartRun` response is based on rolling average of last 20 completed runs.
- All results are stored on the `benchmark-data` branch of the `ArcadeAI/ghost` GitHub repo.
- `options_json` for AIOA accepts `competitors` (list), `prompts` (list of `{id, text}`), and `terms` (list of `{id, query}`). Omit to use defaults.
