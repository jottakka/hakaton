# Implementation Prompt: Unified MCP Server + Output Improvements

> Copy-paste this entire prompt into a new Cursor session to execute the plan.

---

## Context

Read the implementation plan at `docs/handoffs/2026-03-19-server-merge-and-output-improvements.md` first. It has 4 phases, exact file paths, code examples, and success criteria.

The Ghost benchmark platform currently has two MCP servers that need to be merged into one, with output improvements and agent loop removal.

## What was already done (do NOT redo)

In the previous session, these improvements were already applied to the codebase:

1. **Enums** added: `AuditMode`, `CoveragePreset` in `geo_audit_arcade/models.py`; `ReportFormat`, `GeoSearchRunType` in `benchmark_control_arcade/run_models.py`. Tool signatures updated from `Literal` to enum types.
2. **ToolMetadata** added to all `@app.tool` decorators in both `server.py` files.
3. **ToolExecutionError** replaced all `{"error": ...}` dict returns. Input validation helpers added: `_validate_url()`, `_validate_run_id()`, `_validate_iso_date()`, `_clamp()`.
4. **Inline imports** moved to top of file in `extraction.py` and `github_client.py`.
5. **Public API** `client.get_file_content()` added to `GitHubClient`; `history.py` updated to use it.
6. **Tests updated** — 65 geo + 85 benchmark tests pass. Ruff clean.
7. **SKILL.md** updated with `GetLatestRun`, `ListRuns` filters, corrected defaults, 10 workflows.

## What to implement now (4 phases)

### Phase 1: Merge GEO tools into benchmark_control_arcade

1. Edit `tools/benchmark_control_arcade/pyproject.toml`:
   - Add `"anthropic>=0.40.0,<1.0.0"`, `"beautifulsoup4"`, `"lxml"` to dependencies
   - Add `geo-audit-arcade = { path = "../geo_audit_arcade", editable = true }` under `[tool.uv.sources]`

2. Edit `tools/benchmark_control_arcade/src/benchmark_control_arcade/server.py`:
   - Import `AuditMode`, `CoveragePreset` from `geo_audit_arcade.models`
   - Import `run_geo_audit` from `geo_audit_arcade.tools.run_geo_audit`
   - Import `run_geo_compare` from `geo_audit_arcade.tools.run_geo_compare`
   - Copy URL validation helper `_validate_url()` from `geo_audit_arcade/server.py` (or import it)
   - Add `_AUDIT_METADATA` (read-only, WEB_SCRAPING, idempotent)
   - Register `RunGeoSiteAudit` and `RunGeoCompare` on the `app` with `ctx: ToolContext` as first param
   - Bump version to `"0.2.0"`

3. Add tests for the new GEO tools in `tests/test_server.py`.

4. Run validation:
   ```
   cd tools/benchmark_control_arcade && uv sync && uv run pytest tests/test_server.py -x -q && uv run ruff check .
   ```

### Phase 2: Replace agent loop with direct calls

1. Rewrite `geo_runner.py`:
   - Remove `claude_agent_sdk` imports, MCP config, prompt loading, JSON extraction
   - Import `run_geo_audit` from `geo_audit_arcade.tools.run_geo_audit`
   - Import `Publisher` from `benchmark_control_arcade.publisher`
   - Call `run_geo_audit()` directly with params from `spec.options`
   - Use `Publisher` to write `report.md` and `report.json`
   - Return `{run_id, artifacts, summary}` matching `geo_compare_runner` pattern

2. Rewrite `geo_compare_runner.py`:
   - Same pattern: replace agent loop with `run_geo_compare()` direct call
   - Keep existing Publisher usage and summary construction

3. Edit `config.py`:
   - Remove `geo_audit_mcp_url` and `geo_analyzer_mcp_url` fields

4. Move GEO prompts to `prompts/archived/`:
   - `geo_site_audit_system.md`, `geo_site_audit_output_schema.json`
   - `geo_compare_system.md`, `geo_compare_output_schema.json`

5. Rewrite tests:
   - `test_geo_runner.py` — mock `run_geo_audit`, not `claude_agent_sdk`
   - `test_geo_compare_runner.py` — mock `run_geo_compare`, not `claude_agent_sdk`
   - `test_config.py` — remove tests for `geo_audit_mcp_url`

6. Run validation:
   ```
   cd tools/benchmark_control_arcade && uv run pytest tests/ -q --ignore=tests/test_aioa_runner.py && uv run ruff check .
   ```

### Phase 3: Output improvements

1. Fix redundant JSON serialization in `server.py`:
   - Replace `json.dumps([json.loads(r.model_dump_json()) for r in records])` with `json.dumps([r.model_dump(mode="json") for r in records])` everywhere

2. Standardize JSON formatting:
   - Change GEO tools from `json.dumps(result, indent=2)` to `json.dumps(result)` (no indent)

3. Add `run_timestamp` field to GEO audit outputs:
   - In `run_geo_audit.py`: add `result["run_timestamp"] = datetime.now(UTC).isoformat()` after LLM response
   - In `run_geo_compare.py`: same

4. Enrich `compare.py` output with `elapsed_seconds_a/b` and `artifacts_a/b`

5. Update all affected tests.

### Phase 4: Finalize

1. Update SKILL.md — unified gateway, deprecate `geoaudit`
2. Update AGENTS.md — add learned fact about merge
3. Final `ruff format .` + `ruff check .` from each package root
4. Final `pytest` run across both packages

## Quality check procedure (run after EACH phase)

Use the Task tool to dispatch 4 parallel subagents:

**Subagent 1 — lint (shell):**
```
Run ruff format and ruff check on both tools/geo_audit_arcade and tools/benchmark_control_arcade. Report any errors.
```

**Subagent 2 — tests (shell):**
```
Run pytest on both packages:
- cd tools/geo_audit_arcade && uv run pytest tests/ -q
- cd tools/benchmark_control_arcade && uv run pytest tests/ -q --ignore=tests/test_aioa_runner.py
Report pass/fail counts.
```

**Subagent 3 — code-reviewer:**
```
Review all files changed in this phase against the monorepo toolkit conventions:
1. All tools have ToolMetadata
2. All constrained params use Enums (not Literal)
3. All validation uses ToolExecutionError (not error dict returns)
4. No inline imports
5. No _private API usage from external modules
6. All JSON serialization uses model_dump(mode="json") not json.loads(model_dump_json())
```

**Subagent 4 — pattern-recognition-specialist:**
```
Verify consistency across all tool definitions in both server.py files:
1. Every tool has requires_secrets
2. Every tool has metadata
3. Return type annotations are Annotated[str, "description"]
4. ctx: ToolContext is the first param on every benchmark tool
5. Enum defaults use enum values (not strings)
```

## Skills to use

- Invoke `verification-before-completion` before claiming any phase is done
- Invoke `systematic-debugging` if any test fails unexpectedly
- Invoke `review-and-ship` after Phase 4 for final review
- Invoke `new-branch-and-pr` to create the PR

## Do NOT

- Do NOT commit `.env` files
- Do NOT add `from __future__ import annotations` to any `server.py` file (breaks Arcade tool introspection)
- Do NOT remove `geo_audit_arcade` as a standalone package — it remains a library
- Do NOT change the `geoaudit` Arcade gateway yet — just deprecate in docs
- Do NOT run `arcade deploy` — that is a manual operator action
