# Run Specs

Run specs are JSON files that define the inputs for a single benchmark run.

## Directory layout

```
run-specs/
  examples/              # reference specs — not executed automatically
    composio-full.json       # full AIOA run against composio.dev
    composio-geo.json        # GEO-only run against composio.dev
    arcade-geo-compare.json  # GEO competitive comparison: arcade.dev vs competitors
  scheduled/             # specs executed daily by scheduled-benchmarks.yml
    composio-full.json       # daily AIOA run
```

## Spec format

```json
{
  "run_type": "aioa",
  "target": "composio.dev",
  "options": {}
}
```

| Field | Required | Values | Description |
|-------|----------|--------|-------------|
| `run_type` | yes | `"aioa"`, `"geo"`, or `"geo_compare"` | Which benchmark to run |
| `target` | yes | URL or identifier | The primary site to benchmark |
| `options` | no | `{}` | Runner-specific overrides |

### `geo_compare` options

```json
{
  "run_type": "geo_compare",
  "target": "arcade.dev",
  "options": {
    "competitors": ["composio.dev", "merge.dev"],
    "audit_mode": "standard",
    "coverage_preset": "standard",
    "discover_subdomains": false
  }
}
```

| Option | Default | Description |
|--------|---------|-------------|
| `competitors` | `[]` | List of competitor URLs to audit alongside the target |
| `audit_mode` | `"exhaustive"` | `"exhaustive"`, `"standard"`, or `"quick"` |
| `coverage_preset` | `"exhaustive"` | Passed to `CollectGeoEvidence` |
| `discover_subdomains` | `true` | Whether to discover additional subdomains |

## Adding a new scheduled run

1. Copy an example spec:

   ```bash
   cp run-specs/examples/composio-full.json run-specs/scheduled/my-target-full.json
   ```

2. Edit `run_type`, `target`, and any `options`.

3. Commit and push to `main`. The new spec takes effect on the next scheduled trigger (`scheduled-benchmarks.yml` runs daily at 06:00 UTC).

## Triggering a run manually

Use the `StartRun` MCP tool from the BenchmarkControl server, or trigger
`.github/workflows/run-benchmark.yml` directly via GitHub Actions → Run workflow,
passing `run_id`, `run_type`, and `run_spec_json` as inputs.

## Searching historical GEO reports

Use the `SearchGeoReports` MCP tool from the BenchmarkControl server to retrieve
past GEO and GEO compare runs:

| Parameter | Description |
|-----------|-------------|
| `target` | Filter by the primary site (e.g. `"arcade.dev"`). Empty = all. |
| `competitor` | Filter runs that include this competitor URL. Empty = all. |
| `from_date` | ISO-8601 start date inclusive (e.g. `"2026-01-01"`). Empty = no lower bound. |
| `to_date` | ISO-8601 end date inclusive (e.g. `"2026-12-31"`). Empty = no upper bound. |
| `run_type` | `"geo"`, `"geo_compare"`, or empty for both. |
| `limit` | Maximum number of results (default 20). |

Returns a JSON array of `RunRecord` objects, newest first.
