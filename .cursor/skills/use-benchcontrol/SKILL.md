---
name: use-benchcontrol
description: >-
  Use the benchcontrol MCP gateway to run AIOA and GEO benchmarks, retrieve
  results, and search history. Activate when the user asks to audit a site,
  run a benchmark, get the latest results, compare runs, or search past reports.
---

# Using the benchcontrol gateway

**Gateway:** `https://api.arcade.dev/mcp/benchcontrol`  
**All benchmark operations go through this single gateway.**

---

## Which tool to call

```
What do you need?
│
├─ Instant GEO audit (no tracking)      → BenchmarkControl_RunGeoSiteAudit
├─ Instant GEO comparison (no tracking) → BenchmarkControl_RunGeoCompare
├─ Track a run + store in data branch   → BenchmarkControl_StartRun
├─ Check if a tracked run is done       → BenchmarkControl_GetRunStatus
├─ Get the latest result for a site     → BenchmarkControl_GetLatestRun
├─ Read a run's full report             → BenchmarkControl_GetRunReport
├─ List/filter recent runs              → BenchmarkControl_ListRuns
├─ Search GEO history                   → BenchmarkControl_SearchGeoReports
├─ Compare two AIOA runs                → BenchmarkControl_CompareAioaRuns
└─ Browse a run's raw files             → BenchmarkControl_GetRunArtifacts
```

---

## Instant GEO audit (seconds, not stored)

```
BenchmarkControl_RunGeoSiteAudit(
  target_url="https://arcade.dev",
  audit_mode="standard",        # quick | standard | exhaustive
  coverage_preset="standard",   # light(5p) | standard(15p) | deep(30p) | exhaustive(60p)
  discover_subdomains=true
)
```

Returns a 0–100 score across 4 levers. Use `audit_mode="quick"` for a fast check,
`"exhaustive"` for a thorough audit.

```
BenchmarkControl_RunGeoCompare(
  target="arcade.dev",
  competitors="composio.dev, merge.dev",
  audit_mode="standard",
  coverage_preset="standard"
)
```

Returns a side-by-side scorecard with `overall_winner` and `winner_per_lever`.

---

## Tracked benchmark (stored in benchmark-data branch)

**Step 1 — queue:**
```
BenchmarkControl_StartRun(
  run_type="aioa",          # aioa | geo | geo_compare
  target="arcade.dev",
  options_json='{"competitors":["Composio","Zapier"]}'
)
```
Returns `run_id`, `created_at`, and `estimated_wait_seconds`.

**Step 2 — poll until done:**
```
BenchmarkControl_GetRunStatus(run_id=<id>, created_at=<timestamp>)
```
Status: `queued → running → completed | failed`

**Step 3 — read:**
```
BenchmarkControl_GetRunReport(run_id=<id>, created_at=<timestamp>, fmt="json")
```

**Shortcut — skip steps 2–3 for the latest run:**
```
BenchmarkControl_GetLatestRun(
  run_type="aioa",
  target="arcade.dev",
  status="completed",
  include_report=true       # embeds the full report — no extra call needed
)
```

---

## History & comparison

```
# List runs with filters (all params optional)
BenchmarkControl_ListRuns(
  run_type="aioa",           # aioa | geo | geo_compare
  target="arcade.dev",
  from_date="2026-03-01",    # YYYY-MM-DD
  to_date="2026-03-31",
  limit=10
)

# Search GEO reports
BenchmarkControl_SearchGeoReports(
  target="arcade.dev",
  competitor="composio.dev",
  from_date="2026-03-01",
  run_type="geo"             # geo | geo_compare | empty = both
)

# Diff two AIOA runs
BenchmarkControl_CompareAioaRuns(
  run_id_a="<older_id>", created_at_a="<timestamp>",
  run_id_b="<newer_id>", created_at_b="<timestamp>"
)
```

---

## Run types at a glance

| `run_type` | What it measures | Duration |
|---|---|---|
| `aioa` | Google Search rankings for your target vs competitors | ~90s |
| `geo` | Single-site GEO score (robots, sitemap, llms.txt, schema) | ~12 min |
| `geo_compare` | Multi-site GEO comparison | ~15–20 min |

---

## Notes

- `audit_mode` and `coverage_preset` are independent — mix freely.
- `estimated_wait_seconds` is the rolling average of the last 20 completed runs of the same type; `null` when no history exists yet.
- All tracked results are stored on the `benchmark-data` branch: `runs/YYYY/MM/DD/<run_id>/`.
- AIOA currently runs in `seo_only` mode — `arcade_avg_aio_score` is always `null`.
- For AIOA `options_json`, prompt/term IDs come from `aioa/config/prompts_v1.json` and `terms_v1.json` in this repo.
