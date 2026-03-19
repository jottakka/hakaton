# Implementation Plan: Unified MCP Server + Output Improvements

**Date:** 2026-03-19
**Repo:** `ArcadeAI/ghost` · `main` branch
**Estimated effort:** 4 phases, ~2–3 hours total with parallel subagent execution

---

## Problem statement

The Ghost benchmark platform has **two MCP servers** (`geo_audit_arcade`, `benchmark_control_arcade`) that should be **one**. The GEO runners use `claude-agent-sdk` for an unnecessary agent loop when the GEO logic is already a plain Python function. Tool outputs are inconsistent, and the comparison tool is sparse.

## Goals

1. **Merge** `geo_audit_arcade` tools into `benchmark_control_arcade` → one server, one gateway
2. **Replace agent loop** in `geo_runner.py` / `geo_compare_runner.py` with direct Python calls
3. **Standardize outputs** across all tools (consistent serialization, pagination metadata, timestamps)
4. **Enrich CompareAioaRuns** with elapsed time and artifact links
5. **100% test coverage** on all changed code
6. **Zero ruff errors**, all existing tests still passing

---

## Phase 1: Merge GEO tools into benchmark_control_arcade

### 1.1 Add geo-audit-arcade as a dependency

**File:** `tools/benchmark_control_arcade/pyproject.toml`

```toml
dependencies = [
    # existing...
    "anthropic>=0.40.0,<1.0.0",
    "beautifulsoup4",
    "lxml",
]

[tool.uv.sources]
aio-analyzer = { path = "../../aioa", editable = true }
geo-audit-arcade = { path = "../geo_audit_arcade", editable = true }
```

### 1.2 Register GEO tools on the benchcontrol MCPApp

**File:** `tools/benchmark_control_arcade/src/benchmark_control_arcade/server.py`

Add two new tools that import and delegate to the geo_audit_arcade functions:

```python
from geo_audit_arcade.models import AuditMode, CoveragePreset
from geo_audit_arcade.tools.run_geo_audit import run_geo_audit
from geo_audit_arcade.tools.run_geo_compare import run_geo_compare

# _validate_url() already exists in the file

@app.tool(
    requires_secrets=_REQUIRED_SECRETS,
    metadata=_AUDIT_METADATA,  # new: read-only, WEB_SCRAPING
)
async def RunGeoSiteAudit(
    ctx: ToolContext,  # unused but required by Arcade for secret injection
    target_url: Annotated[str, "URL to audit (e.g. 'https://arcade.dev')"],
    audit_mode: Annotated[AuditMode, "..."] = AuditMode.EXHAUSTIVE,
    coverage_preset: Annotated[CoveragePreset, "..."] = CoveragePreset.EXHAUSTIVE,
    discover_subdomains: Annotated[bool, "..."] = True,
) -> Annotated[str, "Complete GEO audit report as JSON"]:
    ...
```

Duplicate the existing GEO server tool wrappers but add `ctx: ToolContext` as the first param (Arcade requires it for secret injection).

### 1.3 Update MCPApp metadata

```python
app = MCPApp(
    name="BenchmarkControl",
    version="0.2.0",  # bump
    instructions=(
        "Control plane for AIOA and GEO benchmark runs. "
        "Use RunGeoSiteAudit and RunGeoCompare for instant GEO audits. "
        "Use StartRun, GetRunStatus, ListRuns, GetLatestRun, GetRunReport, "
        "GetRunArtifacts, CompareAioaRuns, SearchGeoReports for tracked runs."
    ),
)
```

### 1.4 Validation

- [ ] `uv sync` resolves without conflicts
- [ ] `uv run pytest tests/test_server.py -x` passes
- [ ] `uv run ruff check .` → 0 errors
- [ ] New GEO tools appear in tool listing

---

## Phase 2: Replace agent loop with direct calls

### 2.1 Rewrite geo_runner.py

**Before:** 204 lines, `claude-agent-sdk` query loop, MCP HTTP round-trip, JSON extraction from LLM text.

**After:** ~40 lines, direct function call.

```python
"""GEO benchmark runner — direct Python call, no agent loop."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from geo_audit_arcade.tools.run_geo_audit import run_geo_audit

from benchmark_control_arcade.publisher import Publisher
from benchmark_control_arcade.run_models import RunSpec, RunType

_RUN_ID_RE = re.compile(r"^run-(\d{14})-")


def _parse_created_at(run_id: str) -> datetime:
    m = _RUN_ID_RE.match(run_id)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=UTC)
        except ValueError:
            pass
    return datetime.now(tz=UTC)


async def run_geo_benchmark(
    spec: RunSpec, run_id: str, output_dir: Path
) -> dict[str, Any]:
    if spec.run_type is not RunType.geo:
        raise ValueError(f"Expected run_type=geo, got {spec.run_type}")

    result = await run_geo_audit(
        target_url=spec.target,
        audit_mode=spec.options.get("audit_mode", "exhaustive"),
        coverage_preset=spec.options.get("coverage_preset", "exhaustive"),
        discover_subdomains=spec.options.get("discover_subdomains", True),
    )

    created_at = _parse_created_at(run_id)
    pub = Publisher(run_id, created_at, output_dir)
    report_md_abs = pub.write_report_md(result.get("report_markdown", ""))
    report_json_abs = pub.write_report_json(result)

    return {
        "run_id": run_id,
        "artifacts": [
            str(report_md_abs.relative_to(output_dir)),
            str(report_json_abs.relative_to(output_dir)),
        ],
        "summary": {
            "target": spec.target,
            "overall_score": result.get("overall_score"),
        },
    }
```

### 2.2 Rewrite geo_compare_runner.py

Same pattern. Replace ~234-line agent loop with ~50-line direct call to `run_geo_compare()`. Keep the Publisher write logic and summary construction.

### 2.3 Clean up config.py

Remove `geo_audit_mcp_url` and `geo_analyzer_mcp_url` fields from `Settings`. They are no longer needed since GEO runners call Python functions directly.

### 2.4 Archive prompts

Move (don't delete) to `prompts/archived/`:
- `geo_site_audit_system.md`
- `geo_site_audit_output_schema.json`
- `geo_compare_system.md`
- `geo_compare_output_schema.json`

### 2.5 Validation

- [ ] `uv run pytest tests/test_geo_runner.py tests/test_geo_compare_runner.py -x` passes
- [ ] No imports of `claude_agent_sdk` remain in GEO runner files
- [ ] `Settings()` no longer offers `geo_audit_mcp_url`

---

## Phase 3: Output improvements

### 3.1 Fix redundant JSON serialization

**Files:** `server.py` (ListRuns, SearchGeoReports, StartRun)

Replace:
```python
json.dumps([json.loads(r.model_dump_json()) for r in records])
```
With:
```python
json.dumps([r.model_dump(mode="json") for r in records])
```

This eliminates a pointless serialize → deserialize → serialize round-trip.

### 3.2 Standardize JSON formatting

All tools should use `json.dumps(result)` (no indent). GEO tools currently use `indent=2` — change to no indent for consistency with benchcontrol tools.

### 3.3 Add timestamp to GEO audit outputs

**File:** `geo_audit_arcade/tools/run_geo_audit.py`

After the LLM response is parsed, add:
```python
result["run_timestamp"] = datetime.now(UTC).isoformat()
```

Same in `run_geo_compare.py`.

### 3.4 Enrich CompareAioaRuns output

**File:** `benchmark_control_arcade/compare.py`

Add these fields to the comparison dict:
```python
return {
    # existing fields...
    "elapsed_seconds_a": record_a.elapsed_seconds,
    "elapsed_seconds_b": record_b.elapsed_seconds,
    "artifacts_a": [a.model_dump() for a in record_a.artifacts],
    "artifacts_b": [a.model_dump() for a in record_b.artifacts],
}
```

### 3.5 Validation

- [ ] All outputs are valid JSON
- [ ] No `indent=2` in any MCP tool return
- [ ] CompareAioaRuns includes elapsed time and artifacts
- [ ] Existing tests updated to match new output shapes

---

## Phase 4: Finalize and ship

### 4.1 Update SKILL.md

- Change decision tree: remove separate `geoaudit` gateway references, show one gateway
- Update gateway table: show `benchcontrol` with all tools (GEO + benchmark)
- Add note: `geoaudit` gateway is deprecated; use `benchcontrol`
- Update "Code patterns" section

### 4.2 Update AGENTS.md

Add learned fact:
```
- GEO audit tools (`RunGeoSiteAudit`, `RunGeoCompare`) are now registered on the `benchcontrol` gateway alongside all benchmark tools. The standalone `geoaudit` gateway is deprecated. GEO runners call `run_geo_audit()` / `run_geo_compare()` directly — no agent loop or MCP round-trip.
```

### 4.3 Update cloud MCP descriptors

After `arcade deploy`, the new descriptors should include:
- `RunGeoSiteAudit` and `RunGeoCompare` on `benchcontrol`
- `GetLatestRun` with all params (currently missing from cloud)
- `ListRuns` with all filter params (currently only `limit` in cloud)

### 4.4 Final validation

- [ ] `ruff format .` from each package root
- [ ] `ruff check .` → 0 errors in both packages
- [ ] `pytest tests/` → all pass in both packages
- [ ] No `import _decode` or `client._get_file` references
- [ ] No `claude_agent_sdk` imports in GEO runner files
- [ ] SKILL.md is consistent with actual tool surface

---

## Quality check strategy (parallel subagent execution)

### Phase gate: after each phase, run all 4 checks in parallel

```
┌─────────────────────────────────────────────────────────────┐
│                    Phase N complete                          │
│                          │                                  │
│    ┌─────────┬───────────┼───────────┬──────────┐           │
│    ▼         ▼           ▼           ▼          ▼           │
│  [lint]   [tests]   [code-review] [pattern]  [security]    │
│    │         │           │           │          │           │
│    └─────────┴───────────┴───────────┴──────────┘           │
│                          │                                  │
│                    Merge to next phase                       │
└─────────────────────────────────────────────────────────────┘
```

**Subagent 1 — lint (shell subagent)**
```
cd tools/geo_audit_arcade && uv run ruff format . && uv run ruff check .
cd tools/benchmark_control_arcade && uv run ruff format . && uv run ruff check .
```

**Subagent 2 — tests (shell subagent)**
```
cd tools/geo_audit_arcade && uv run pytest tests/ -q
cd tools/benchmark_control_arcade && uv run pytest tests/ -q --ignore=tests/test_aioa_runner.py
```

**Subagent 3 — code-reviewer subagent**
Review all changed files against:
- Monorepo toolkit patterns (Enums, ToolMetadata, ToolExecutionError)
- No inline imports
- No `_private` API usage from external modules
- No `{"error": ...}` dict returns

**Subagent 4 — pattern-recognition-specialist subagent**
Check consistency:
- All tools have `ToolMetadata`
- All constrained params use Enums
- All validation uses `ToolExecutionError`
- All JSON serialization uses `model_dump(mode="json")` (not `json.loads(model_dump_json())`)

**Subagent 5 — security-sentinel subagent**
Verify:
- No secrets in tool outputs
- `secrets_guard.assert_no_secrets()` still covers all output boundaries
- No hardcoded API keys or tokens

### Skills to invoke during implementation

| Phase | Skill | Purpose |
|-------|-------|---------|
| All | `verification-before-completion` | Run tests + lint before claiming done |
| 1–2 | `systematic-debugging` | If merge introduces import errors or test failures |
| 3 | `code-simplicity-reviewer` | Ensure output standardization is minimal/clean |
| 4 | `review-and-ship` | Final review before PR |
| 4 | `new-branch-and-pr` | Create branch and open PR |

---

## Files changed (complete list)

| File | Change type | Phase |
|------|------------|-------|
| `tools/benchmark_control_arcade/pyproject.toml` | Edit: add geo deps | 1 |
| `tools/benchmark_control_arcade/src/benchmark_control_arcade/server.py` | Edit: add GEO tools, bump version | 1 |
| `tools/benchmark_control_arcade/src/benchmark_control_arcade/geo_runner.py` | Rewrite: direct call | 2 |
| `tools/benchmark_control_arcade/src/benchmark_control_arcade/geo_compare_runner.py` | Rewrite: direct call | 2 |
| `tools/benchmark_control_arcade/src/benchmark_control_arcade/config.py` | Edit: remove MCP URL fields | 2 |
| `tools/benchmark_control_arcade/prompts/` | Move to `archived/` | 2 |
| `tools/benchmark_control_arcade/src/benchmark_control_arcade/compare.py` | Edit: add fields | 3 |
| `tools/geo_audit_arcade/src/geo_audit_arcade/tools/run_geo_audit.py` | Edit: add timestamp | 3 |
| `tools/geo_audit_arcade/src/geo_audit_arcade/tools/run_geo_compare.py` | Edit: add timestamp | 3 |
| `tools/benchmark_control_arcade/tests/test_server.py` | Edit: add GEO tool tests | 1 |
| `tools/benchmark_control_arcade/tests/test_geo_runner.py` | Rewrite: test direct call | 2 |
| `tools/benchmark_control_arcade/tests/test_geo_compare_runner.py` | Rewrite: test direct call | 2 |
| `tools/benchmark_control_arcade/tests/test_compare.py` | Edit: test new fields | 3 |
| `~/.cursor/skills-cursor/ghost-benchmarks/SKILL.md` | Edit: unified gateway | 4 |
| `AGENTS.md` | Edit: add learned fact | 4 |

---

## Risks and mitigations

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| `geo-audit-arcade` path dep breaks uv resolve | Low | High | Test `uv sync` immediately after pyproject.toml change |
| GEO tool requires `ANTHROPIC_API_KEY` not present in benchcontrol context | Low | High | All tools already declare `ANTHROPIC_API_KEY` in `_REQUIRED_SECRETS` |
| Removing agent loop changes GEO output shape | Medium | Medium | Compare `run_geo_audit()` output vs old agent output; both use same inner function |
| `geo_runner` tests mock `claude_agent_sdk` — rewrite needed | High | Low | Tests become simpler since they just mock `run_geo_audit()` |
| Arcade gateway rename breaks existing callers | Medium | High | Keep `geoaudit` gateway alive temporarily; document deprecation |

---

## Success criteria

1. **One server** serves all tools (GEO + benchmark) on `benchcontrol` gateway
2. **No agent loop** for GEO runs — direct Python calls
3. **150+ tests pass** across both packages (65 geo + 85+ benchmark)
4. **Zero ruff errors** in both packages
5. **SKILL.md** accurately describes the unified tool surface
6. **CompareAioaRuns** includes elapsed time and artifact links
7. **All JSON output** uses consistent serialization (no `indent=2`, no redundant round-trips)
