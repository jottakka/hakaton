# Run Specs

Run specs are JSON files that define the inputs for a single benchmark run.

## Directory layout

```
run-specs/
  examples/          # reference specs — not executed automatically
    composio-full.json   # full AIOA run against composio.dev
    composio-geo.json    # GEO-only run against composio.dev
  scheduled/         # specs executed daily by scheduled-benchmarks.yml
    composio-full.json   # daily AIOA run
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
| `run_type` | yes | `"aioa"` or `"geo"` | Which benchmark to run |
| `target` | yes | URL or identifier | The site or product to benchmark |
| `options` | no | `{}` | Runner-specific overrides |

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
