# Unified Benchcontrol Merge and Cleanup Design

**Date:** 2026-03-18
**Decision:** Approach B (phase-by-phase implementation with dead-code removal)

## Goal

Unify GEO audit tools into `benchmark_control_arcade`, remove obsolete agent-loop code paths, and standardize output shapes and serialization while keeping behavior stable and tests green.

## Scope

- Merge `RunGeoSiteAudit` and `RunGeoCompare` into `benchmark_control_arcade` server.
- Replace GEO benchmark runners with direct library calls to `geo_audit_arcade`.
- Remove dead code from old `claude-agent-sdk` orchestration path.
- Improve output consistency and enrich comparison responses.
- Update tests to validate the new architecture rather than legacy prompt/SDK behavior.

## Non-goals

- No `arcade deploy` in this session.
- No `.env` commits or secret handling changes.
- No migration/removal of the standalone `geo_audit_arcade` package (it remains a library dependency).

## Design

### 1) Unified server surface

`benchmark_control_arcade/server.py` becomes the single MCP surface for both run lifecycle and GEO instant audit tools.
New GEO tools are thin wrappers that:

- accept `ctx: ToolContext` first,
- validate URLs and competitor lists,
- delegate to `run_geo_audit()` / `run_geo_compare()`,
- return compact JSON strings like other benchcontrol tools.

### 2) Direct-call GEO runners

`geo_runner.py` and `geo_compare_runner.py` drop the SDK prompt loop and call the Python library directly.
Both runners:

- keep run-type guards,
- write artifacts through `Publisher`,
- return minimal `{run_id, artifacts, summary}` payloads.

This removes prompt/schema loading and fragile JSON extraction from LLM text at runner level.

### 3) Dead-code removal strategy

Remove only code made obsolete by the architecture change:

- SDK imports and helper functions in GEO runners,
- config fields that are no longer read by runtime code,
- tests tied only to prompt/SDK boundary contracts,
- redundant JSON serialization round-trips.

Prompt assets are archived rather than deleted.

### 4) Output consistency

- Replace `json.loads(model_dump_json())` with `model_dump(mode="json")`.
- Remove pretty-print return formatting (`indent=2`) for MCP tools.
- Add `run_timestamp` to GEO audit and compare results.
- Extend `CompareAioaRuns` output with elapsed time and artifacts for both compared runs.

## Validation

After each phase:

- targeted pytest for changed modules,
- `ruff check` on edited package,
- final full package checks before completion.

## Risks and mitigations

- Existing dirty workspace overlap: keep edits minimal and scoped to planned files.
- Test drift from old architecture: rewrite tests to assert direct-call behavior and output contracts.
- Hidden coupling: run targeted tests first, then broader suite to catch regressions.
