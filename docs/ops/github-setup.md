# GitHub Repository Setup

## Required GitHub Secrets

Set these in **Settings → Secrets and variables → Actions**:

### Secrets used by the BenchmarkControl Arcade MCP server

These run on the operator's machine (not in CI) but are good to document:

| Secret | Description |
|---|---|
| `GITHUB_TOKEN` | PAT with `repo` + `workflow` scopes |
| `GITHUB_OWNER` | Org or username |
| `GITHUB_REPO` | Repository name |

### Secrets used by benchmark execution workflows

| Secret | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude / Agent SDK calls |
| `ARCADE_API_KEY` | Arcade API key for AIO/GEO tool execution |
| `ARCADE_USER_ID` | Arcade user ID |

### Optional — remote MCP endpoint overrides

| Secret | Description |
|---|---|
| `GEO_AUDIT_MCP_URL` | Override for the deployed GeoAudit MCP server |
| `GEO_ANALYZER_MCP_URL` | Override for the GEO analyzer MCP server |

## Required Status Checks (Branch Protection)

Enable branch protection on `main` with these required status checks:

- `pre-commit`
- `aioa – lint + test`
- `geo_audit_arcade – lint + test`
- `benchmark_control_arcade – lint + test`

Settings:
- ✅ Require a pull request before merging
- ✅ Require status checks to pass before merging
- ✅ Require branches to be up to date before merging
- ✅ Do not allow bypassing the above settings

## Creating the Data Branch

The `benchmark-data` branch stores historical run records. It must be an
orphan branch so it has no code history:

```bash
git checkout --orphan benchmark-data
git rm -rf .
echo "# Benchmark run data" > README.md
git add README.md
git commit -m "chore: initialize benchmark data branch"
git push origin benchmark-data
```

Then create the `runs/` directory structure:

```bash
mkdir -p runs
git add runs/.gitkeep
git commit -m "chore: add runs directory"
git push origin benchmark-data
```

## Adding a New Scheduled Run Spec

1. Create a JSON file in `run-specs/scheduled/`:

```bash
cp run-specs/examples/composio-full.json run-specs/scheduled/my-target-full.json
# Edit to set target, run_type, and any overrides
```

2. The `scheduled-benchmarks.yml` workflow reads all `*.json` files in that
   directory and dispatches a run for each one on the configured cron schedule.

3. Commit and push — the new spec takes effect on the next scheduled trigger.
