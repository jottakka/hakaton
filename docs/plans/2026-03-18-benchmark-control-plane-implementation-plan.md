# Benchmark Control Plane Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a private Arcade-hosted MCP control plane that can trigger AIOA and GEO benchmark runs through GitHub Actions, retrieve historical reports and artifacts, and enforce repo-wide lint/test/merge quality gates.

**Architecture:** Keep `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/geo_audit_arcade` focused on deterministic GEO evidence and validation only. Add a new private Arcade server at `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade` that owns triggering, status, history, and comparisons. `StartRun` writes an initial queued run record to a dedicated data branch, dispatches a GitHub Actions workflow, and read-only tools retrieve run state from that branch. AIOA remains deterministic Python code; GEO automation uses repo-owned prompt assets plus the Python `claude-agent-sdk` instead of relying on `~/.claude/skills`.

**Tech Stack:** Python 3.11+, `uv`, `arcade-mcp-server`, `httpx`, `pydantic`, `pydantic-settings`, `claude-agent-sdk`, `tenacity`, `pytest`, `pytest-asyncio`, `pytest-cov`, `respx`, `ruff`, `pre-commit`, GitHub Actions, project-scoped `.mcp.json`

---

## Working Rules

- Use `@superpowers:test-driven-development` for every Python behavior change in this plan. Configuration-only files like workflow YAML, `.gitignore`, and `.env.example` are the only exception.
- Use `@superpowers:verification-before-completion` before marking any task done.
- After Task 2, after the parallel window (Tasks 4-6), after Task 7, and at the end, request review before proceeding.
- Do not add any production dependency on `~/.claude/skills/geo-site-audit/SKILL.md`. Treat that file as reference material only. Runtime prompt assets must live inside this repo.
- Avoid overmocking. Prefer:
  - real temp directories and real JSON/SQLite stores
  - `respx` at the HTTP boundary instead of patching internal helpers
  - real Pydantic model parsing instead of fake dicts
  - thin boundary fakes only for external systems like GitHub and Claude Agent SDK
- Never log secrets. `.env` files are local-only and must never be committed.
- The current workspace snapshot is not a git repo. Execute this plan in a real git-tracked clone or worktree of the repo before committing.
- Keep the first version simple:
  - one control repo
  - one data branch
  - one `StartRun` tool
  - same-type comparisons only
  - no global manifest file if per-run directories are sufficient

## Key Decisions

- **Control plane tool split:** use one execution tool (`StartRun`) and multiple retrieval tools (`GetRunStatus`, `ListRuns`, `GetRunReport`, `GetRunArtifacts`, `CompareAioaRuns`).
- **Run registry:** do not start with a shared mutable manifest. Each run gets its own directory and canonical `run.json`. `ListRuns` reads run records from the data branch.
- **History storage:** store historical artifacts in a dedicated git data branch, not GitHub Actions artifacts.
- **Execution backend:** GitHub Actions, not AWS.
- **GEO automation:** use `claude-agent-sdk` with repo-owned prompt assets and deployed MCP servers. Do not depend on interactive slash skills.
- **Security boundary:** the Arcade MCP server only needs GitHub dispatch/read-write secrets. Benchmark execution secrets stay in GitHub Actions secrets.

## Out of Scope

- Replacing AIOA storage with Postgres in this first implementation
- Cross-type comparisons between AIOA and GEO runs
- Automatic issue creation in Linear from benchmark findings
- Rewriting the existing deterministic `GeoAudit` server into the new control plane
- Replacing GitHub Actions with Claude Code on the web as the primary execution backend

## Parallel Execution Model

### Implementation parallelism

- **Foundation is sequential:** Tasks 1-3.
- **Parallel window A:** Tasks 4, 5, and 6 may be implemented in parallel after Task 3 is approved.
- **Integration is sequential again:** Tasks 7-9 depend on the results of the parallel window.

### Runtime parallelism

- Multiple benchmark runs may execute in parallel because each run writes to a unique path in the data branch:
  - `runs/YYYY/MM/DD/<run_id>/run.json`
  - `runs/YYYY/MM/DD/<run_id>/artifacts/...`
- Do not use one global workflow concurrency group. Use per-run concurrency keyed by `run_id`.
- Data-branch writes must `git pull --rebase` before push, and each run must only mutate its own directory plus the exact file it owns.

### Review and fixer loop

For each task:

1. Implementer subagent completes the task and runs the required verifications.
2. Spec reviewer checks compliance with this plan.
3. Code quality reviewer checks simplicity, tests, and maintainability.
4. If either reviewer finds issues, spawn a dedicated fixer subagent with the exact findings.
5. Re-run the same reviewer until the task is approved.

For Tasks 4-6:

- run implementers in parallel
- run reviewers in parallel after all three implementers return
- spawn fixers only for the specific failing task
- do not merge the outputs conceptually until all three tasks are approved

---

## Task 1: Establish repo-wide quality, secret, and developer guardrails

### Files

- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/.gitignore`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/.env.example`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/.pre-commit-config.yaml`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/.github/workflows/ci.yml`
- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/pyproject.toml`
- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/geo_audit_arcade/pyproject.toml`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/pyproject.toml`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/docs/ops/local-development.md`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/docs/ops/github-setup.md`

### Why first

Everything else in this plan depends on consistent quality tooling, consistent dev dependencies, and clear secret handling.

### Step 1: Create the root ignore and local secret template

Add a root `.gitignore` with at least:

- `.env`
- `.venv/`
- `.pytest_cache/`
- `.ruff_cache/`
- `.mypy_cache/`
- `runs/`
- temporary benchmark workdirs

Create a root `.env.example` with grouped sections for:

```dotenv
# GitHub control-plane secrets
GITHUB_TOKEN=
GITHUB_OWNER=
GITHUB_REPO=
GITHUB_DATA_BRANCH=benchmark-data
GITHUB_RUN_WORKFLOW=run-benchmark.yml

# Benchmark execution secrets (used by GitHub Actions, also useful locally)
ANTHROPIC_API_KEY=
ARCADE_API_KEY=
ARCADE_USER_ID=
MCP_SERVER_URL=https://api.arcade.dev/mcp/AIO

# Remote MCP endpoints for Claude / Geo automation
GEO_AUDIT_MCP_URL=
GEO_ANALYZER_MCP_URL=
```

### Step 2: Add repo-wide code quality hooks

Create `.pre-commit-config.yaml` with:

- `ruff-format`
- `ruff-check`
- `check-yaml`
- `end-of-file-fixer`
- `trailing-whitespace`
- `detect-secrets`

Use local hooks or package-specific commands so each Python package is checked with its own `uv` environment.

### Step 3: Align Python package dev dependencies

Update `aioa/pyproject.toml` to add:

- `ruff`
- `pytest-cov`
- `respx`

Also add a minimal Ruff config and `tool.pytest.ini_options` if missing.

Update `tools/geo_audit_arcade/pyproject.toml` to add:

- `pytest-cov`
- `respx` only if needed for HTTP-boundary tests

Create `tools/benchmark_control_arcade/pyproject.toml` with:

- runtime: `arcade-mcp-server`, `httpx`, `pydantic`, `pydantic-settings`, `tenacity`, `claude-agent-sdk`
- dev: `pytest`, `pytest-asyncio`, `pytest-cov`, `respx`, `ruff`

### Step 4: Add CI for lint and tests

Create `.github/workflows/ci.yml` with jobs for:

- `aioa`
- `geo_audit_arcade`
- `benchmark_control_arcade`
- `pre-commit`

Each job should:

1. checkout
2. install `uv`
3. sync dependencies for the target package
4. run Ruff
5. run pytest

### Step 5: Document local setup and branch protection

In `docs/ops/local-development.md`, document:

- `uv` install
- `pre-commit install`
- how to create `.env` from `.env.example`
- package-specific test/lint commands

In `docs/ops/github-setup.md`, document:

- required GitHub secrets
- required status checks for merge
- required branch protection settings
- required data-branch creation

### Step 6: Verify the baseline

Run:

- `uv sync --project /Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa --group dev`
- `uv sync --project /Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/geo_audit_arcade --extra dev`
- `uv sync --project /Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade --group dev`
- `pre-commit run --all-files`

Expected:

- the repo has a working pre-commit configuration
- all YAML files parse
- Ruff runs cleanly or reports only real issues to fix later

### Step 7: Commit

If working in a git checkout:

```bash
git add .gitignore .env.example .pre-commit-config.yaml .github/workflows/ci.yml aioa/pyproject.toml tools/geo_audit_arcade/pyproject.toml tools/benchmark_control_arcade/pyproject.toml docs/ops/local-development.md docs/ops/github-setup.md
git commit -m "chore: add repo quality and ops guardrails"
```

---

## Task 2: Scaffold the BenchmarkControl Arcade server and typed settings

### Files

- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/src/benchmark_control_arcade/__init__.py`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/src/benchmark_control_arcade/server.py`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/src/benchmark_control_arcade/config.py`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/tests/test_server.py`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/tests/test_config.py`

### Why now

The rest of the implementation needs a real home, a real server, and a single source of truth for environment/config validation.

### Step 1: Write the failing server and config tests

Add tests like:

```python
def test_app_loads_with_expected_name_and_version():
    from benchmark_control_arcade.server import app
    assert app.name == "BenchmarkControl"
    assert app.version == "0.1.0"
```

```python
def test_settings_require_github_repo_context(monkeypatch):
    monkeypatch.delenv("GITHUB_OWNER", raising=False)
    monkeypatch.delenv("GITHUB_REPO", raising=False)
    with pytest.raises(ValidationError):
        Settings()
```

```python
def test_settings_default_data_branch(monkeypatch):
    monkeypatch.setenv("GITHUB_OWNER", "acme")
    monkeypatch.setenv("GITHUB_REPO", "benchmarks")
    monkeypatch.setenv("GITHUB_TOKEN", "test")
    assert Settings().github_data_branch == "benchmark-data"
```

### Step 2: Run the tests and confirm they fail

Run:

`uv run --project /Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade pytest tests/test_server.py tests/test_config.py -q`

Expected:

- import errors because the package does not exist yet
- config validation tests fail because `Settings` does not exist

### Step 3: Implement minimal package and settings

Create:

- `server.py` with `MCPApp(name="BenchmarkControl", version="0.1.0", ...)`
- `config.py` with a `Settings` model using `pydantic-settings`

Do not implement tool behavior yet. It is fine for tool functions to raise `NotImplementedError` in this task if the app imports cleanly and the settings model validates.

### Step 4: Re-run the tests

Run:

`uv run --project /Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade pytest tests/test_server.py tests/test_config.py -q`

Expected:

- both tests pass
- the new package imports without side effects

### Step 5: Request review

Request review on this task before moving on. The reviewer should confirm:

- package layout matches the existing `tools/geo_audit_arcade` pattern
- settings are typed and fail fast
- no business logic leaked into the server skeleton

### Step 6: Commit

```bash
git add tools/benchmark_control_arcade
git commit -m "feat: scaffold benchmark control arcade server"
```

---

## Task 3: Define the canonical run contract and per-run storage layout

### Files

- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/src/benchmark_control_arcade/run_models.py`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/src/benchmark_control_arcade/history_layout.py`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/tests/test_run_models.py`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/tests/test_history_layout.py`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/run-specs/examples/composio-full.json`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/run-specs/examples/composio-geo.json`

### Why now

Tasks 4-6 all depend on a stable run schema and storage contract. Do not start GitHub, AIOA, or GEO integration before this task is approved.

### Step 1: Write the failing schema and layout tests

Add tests like:

```python
def test_run_spec_requires_run_type_and_target():
    with pytest.raises(ValidationError):
        RunSpec.model_validate({"target": "composio.dev"})
```

```python
def test_run_directory_is_date_partitioned():
    ts = datetime(2026, 3, 18, tzinfo=timezone.utc)
    path = run_directory("run-123", ts)
    assert path.as_posix().endswith("runs/2026/03/18/run-123")
```

```python
def test_run_record_paths_are_manifest_free_and_self_contained():
    layout = build_run_layout("run-123", datetime(...))
    assert layout.run_json.name == "run.json"
    assert "manifest" not in layout.run_json.as_posix()
```

### Step 2: Run the tests and confirm they fail

Run:

`uv run --project /Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade pytest tests/test_run_models.py tests/test_history_layout.py -q`

Expected:

- models and layout helpers are missing

### Step 3: Implement the canonical models

Define at minimum:

- `RunType`: `aioa`, `geo`
- `RunStatus`: `queued`, `running`, `completed`, `failed`
- `RunSpec`
- `RunRecord`
- `RunArtifact`

`RunRecord` must include:

- `run_id`
- `run_type`
- `status`
- `created_at`
- `updated_at`
- `repo`
- `workflow_name`
- `data_branch`
- `spec`
- `artifacts`
- `summary`
- `error`

### Step 4: Implement the run layout helpers

Use a per-run layout with no shared manifest:

- `runs/YYYY/MM/DD/<run_id>/run.json`
- `runs/YYYY/MM/DD/<run_id>/report.json`
- `runs/YYYY/MM/DD/<run_id>/report.md`
- `runs/YYYY/MM/DD/<run_id>/artifacts/...`

### Step 5: Add example run specs

Create checked-in example specs for:

- one full AIOA run
- one GEO-only run

These example specs will later be reused by scheduled workflows and smoke tests.

### Step 6: Re-run the tests

Run:

`uv run --project /Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade pytest tests/test_run_models.py tests/test_history_layout.py -q`

Expected:

- the run contract is stable and explicit
- there is no mutable shared manifest requirement

### Step 7: Commit

```bash
git add tools/benchmark_control_arcade/src/benchmark_control_arcade/run_models.py tools/benchmark_control_arcade/src/benchmark_control_arcade/history_layout.py tools/benchmark_control_arcade/tests/test_run_models.py tools/benchmark_control_arcade/tests/test_history_layout.py run-specs/examples
git commit -m "feat: define benchmark run contract and storage layout"
```

---

## Parallel Window A

After Task 3 is reviewed and approved, run Tasks 4, 5, and 6 in parallel.

- Task 4 owner: GitHub integration and run registry
- Task 5 owner: AIOA compatibility and hardening
- Task 6 owner: GEO agent runner and prompt assets

Do not start Task 7 until all three tasks are reviewed and approved.

---

## Task 4: Build the GitHub integration and queued-run registry

### Files

- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/src/benchmark_control_arcade/github_client.py`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/tests/test_github_client.py`

### Step 1: Write the failing GitHub boundary tests

Use `respx` and real JSON payloads. Add tests for:

- creating an initial queued `run.json` in the data branch
- dispatching the benchmark workflow
- reading one `run.json`
- listing multiple `run.json` files from the data branch tree
- rejecting missing `GITHUB_TOKEN`

Use shapes like:

```python
@pytest.mark.asyncio
async def test_create_initial_run_record_writes_queued_status(respx_mock):
    ...
    assert payload["status"] == "queued"
```

```python
@pytest.mark.asyncio
async def test_dispatch_workflow_uses_run_id_input(respx_mock):
    ...
    assert request_json["inputs"]["run_id"] == "run-123"
```

### Step 2: Run the tests and confirm they fail

Run:

`uv run --project /Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade pytest tests/test_github_client.py -q`

Expected:

- client module does not exist yet

### Step 3: Implement the GitHub client

Implement a thin typed client around GitHub’s REST API with `httpx` and `tenacity`.

Capabilities:

- `create_initial_run_record(...)`
- `update_run_record(...)`
- `dispatch_workflow(...)`
- `get_run_record(...)`
- `list_run_records(...)`

Rules:

- write the queued run record before dispatching the workflow
- use `run_id` as the external identifier everywhere
- keep writes constrained to the data branch
- treat all GitHub HTTP as boundary code, not business logic

### Step 4: Re-run the tests

Run:

`uv run --project /Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade pytest tests/test_github_client.py -q`

Expected:

- the client can create, update, fetch, and list run records
- dispatch uses the workflow input contract

### Step 5: Review and fix loop

Request:

- `@superpowers:code-reviewer`
- `@security-sentinel`

If either finds issues, spawn a dedicated fixer subagent for this task only.

### Step 6: Commit

```bash
git add tools/benchmark_control_arcade/src/benchmark_control_arcade/github_client.py tools/benchmark_control_arcade/tests/test_github_client.py
git commit -m "feat: add github dispatch and run registry client"
```

---

## Task 5: Make AIOA compatible with external run IDs and secure automation

### Files

- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/src/store.py`
- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/src/stores/json_store.py`
- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/src/stores/sqlite_store.py`
- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/src/pipeline.py`
- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/src/search.py`
- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/tests/test_pipeline.py`
- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/tests/test_store.py`
- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/tests/test_search.py`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/tests/test_security.py`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/src/benchmark_control_arcade/aioa_runner.py`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/tests/test_aioa_runner.py`

### Step 1: Write the failing compatibility tests

Add tests that prove:

- `run_full_pipeline(..., run_id="run-123")` uses that run ID
- JSON and SQLite stores preserve the provided run ID
- `aioa_runner` emits artifacts into the canonical run directory

Example:

```python
@pytest.mark.asyncio
async def test_run_full_pipeline_accepts_external_run_id(tmp_path):
    analysis = await run_full_pipeline(..., output_dir=tmp_path, run_id="run-123")
    stored = json.loads((tmp_path / "runs" / "run-123" / "run.json").read_text())
    assert stored["id"] == "run-123"
```

### Step 2: Write the failing security tests

Add tests that prove:

- `ARCADE_API_KEY` is required before search execution
- `MCP_SERVER_URL` rejects unknown hosts
- no configured secret value is echoed into stdout/stderr

### Step 3: Run the focused tests and confirm they fail

Run:

`uv run --project /Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa pytest tests/test_pipeline.py tests/test_store.py tests/test_search.py tests/test_security.py -q`

Expected:

- the pipeline does not accept external run IDs yet
- security validation does not exist yet

### Step 4: Implement the minimal store and pipeline changes

Make these changes:

- widen `create_run(...)` to accept optional `run_id`
- plumb optional `run_id` through `run_full_pipeline(...)`
- keep backward compatibility when `run_id` is omitted
- keep current file shapes unless the control-plane contract requires one new field only

### Step 5: Harden the search configuration

In `aioa/src/search.py`:

- fail fast if `ARCADE_API_KEY` is missing
- validate `MCP_SERVER_URL` against an allowlist
- sanitize persisted error text
- stop relying on accidental `.env` discovery behavior; make the local config path explicit or clearly documented

### Step 6: Implement the AIOA runner adapter

`aioa_runner.py` should:

- accept a `RunSpec`
- call the existing AIOA programmatic pipeline
- pass the control-plane `run_id`
- assemble canonical artifacts for the data branch

Tests must use real temp directories and the real JSON store wherever possible.

### Step 7: Re-run focused tests and nearby regressions

Run:

- `uv run --project /Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa pytest tests/test_pipeline.py tests/test_store.py tests/test_search.py tests/test_security.py -q`
- `uv run --project /Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade pytest tests/test_aioa_runner.py -q`

Expected:

- external run IDs work
- security checks fail closed
- AIOA artifacts can be published under the canonical run path

### Step 8: Review and fix loop

Request:

- `@superpowers:code-reviewer`
- `@security-sentinel`

Fix all Important issues before leaving this task.

### Step 9: Commit

```bash
git add aioa tools/benchmark_control_arcade/src/benchmark_control_arcade/aioa_runner.py tools/benchmark_control_arcade/tests/test_aioa_runner.py
git commit -m "feat: adapt aioa for controlled runs and secure execution"
```

---

## Task 6: Convert GEO automation into repo-owned prompt assets and an Agent SDK runner

### Files

- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/CLAUDE.md`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/.mcp.json`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/prompts/geo_site_audit_system.md`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/prompts/geo_site_audit_output_schema.json`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/src/benchmark_control_arcade/geo_runner.py`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/tests/test_geo_runner.py`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/tests/fixtures/geo_evidence.json`

### Step 1: Write the failing GEO runner tests

Add tests that prove:

- the prompt builder includes the deterministic tool order from the existing GEO skill
- the runner refuses to depend on `~/.claude/skills`
- the runner builds a structured output request
- the runner requires the GeoAudit MCP URL setting

Example:

```python
def test_geo_prompt_requires_collect_before_validate():
    prompt = build_geo_system_prompt()
    assert "CollectGeoEvidence" in prompt
    assert "ValidateGeoAuditClaims" in prompt
    assert prompt.index("CollectGeoEvidence") < prompt.index("ValidateGeoAuditClaims")
```

### Step 2: Run the tests and confirm they fail

Run:

`uv run --project /Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade pytest tests/test_geo_runner.py -q`

Expected:

- GEO runner code and prompt assets do not exist yet

### Step 3: Create repo-owned Claude assets

Create:

- root `CLAUDE.md` with benchmark automation guardrails and output locations
- root `.mcp.json` with project-scoped remote HTTP MCP servers using env expansion
- repo-owned GEO prompt assets distilled from `~/.claude/skills/geo-site-audit/SKILL.md`

The prompt asset must preserve these rules:

- call `CollectGeoEvidence` before scoring
- call `ValidateGeoAuditClaims` before final output
- default to exhaustive unless spec says otherwise
- produce structured output that the Python runner can persist

### Step 4: Implement the GEO Agent SDK runner

Use `claude-agent-sdk` from Python, not an interactive slash command.

The runner should:

- construct a typed system prompt from repo-owned assets
- configure MCP servers explicitly from settings
- request structured output
- return both a machine-readable JSON summary and a markdown report body

Do not let the agent write files directly in the first version. The Python runner should write files after it receives the structured result.

### Step 5: Re-run the tests

Run:

- `uv run --project /Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade pytest tests/test_geo_runner.py -q`

Expected:

- the runner uses repo-owned assets
- there is no dependency on home-directory skill files

### Step 6: Review and fix loop

Request:

- `@superpowers:code-reviewer`
- `@architecture-strategist`

If they disagree about scope, preserve the simpler implementation.

### Step 7: Commit

```bash
git add CLAUDE.md .mcp.json tools/benchmark_control_arcade/prompts tools/benchmark_control_arcade/src/benchmark_control_arcade/geo_runner.py tools/benchmark_control_arcade/tests/test_geo_runner.py
git commit -m "feat: add repo-owned geo automation assets and runner"
```

---

## Parallel Window A Review Gate

Before starting Task 7:

1. Review Task 4, Task 5, and Task 6 outputs.
2. Confirm:
   - queued-run registry works without a shared manifest
   - AIOA can run under an externally supplied `run_id`
   - GEO automation is repo-owned and Agent SDK-based
3. If any task is not approved, spawn a fixer subagent for that task only.

Do not proceed until all three tasks are green.

---

## Task 7: Implement the BenchmarkControl MCP tools

### Files

- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/src/benchmark_control_arcade/server.py`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/src/benchmark_control_arcade/history.py`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/src/benchmark_control_arcade/compare.py`
- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/tests/test_server.py`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/tests/test_history.py`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/tests/test_compare.py`

### Tool surface for v1

- `StartRun`
- `GetRunStatus`
- `ListRuns`
- `GetRunReport`
- `GetRunArtifacts`
- `CompareAioaRuns`

### Step 1: Write the failing tool tests

Add tests that prove:

- `StartRun` writes a queued record and dispatches a workflow
- `GetRunStatus` returns a parsed `RunRecord`
- `ListRuns` returns recent runs sorted newest first
- `GetRunReport` returns the expected report content
- `GetRunArtifacts` lists artifact paths
- `CompareAioaRuns` rejects mixed run types

### Step 2: Run the tests and confirm they fail

Run:

`uv run --project /Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade pytest tests/test_server.py tests/test_history.py tests/test_compare.py -q`

Expected:

- the tool handlers do not exist yet

### Step 3: Implement the tool handlers

Rules:

- `StartRun` accepts one `RunSpec`-shaped payload
- `StartRun` is the only write tool in v1
- read tools must be side-effect free
- `CompareAioaRuns` is AIOA-only for v1 and must return a clear error for GEO runs
- use `requires_secrets=["GITHUB_TOKEN"]` for write operations

### Step 4: Re-run the tests

Run:

`uv run --project /Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade pytest tests/test_server.py tests/test_history.py tests/test_compare.py -q`

Expected:

- the full MCP surface works against the GitHub client abstraction

### Step 5: Review and fix loop

Request:

- `@superpowers:code-reviewer`
- `@security-sentinel`

### Step 6: Commit

```bash
git add tools/benchmark_control_arcade/src/benchmark_control_arcade/server.py tools/benchmark_control_arcade/src/benchmark_control_arcade/history.py tools/benchmark_control_arcade/src/benchmark_control_arcade/compare.py tools/benchmark_control_arcade/tests/test_server.py tools/benchmark_control_arcade/tests/test_history.py tools/benchmark_control_arcade/tests/test_compare.py
git commit -m "feat: add benchmark control mcp tool surface"
```

---

## Task 8: Add workflow execution, publishing, and scheduled runs

### Files

- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/.github/workflows/run-benchmark.yml`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/.github/workflows/scheduled-benchmarks.yml`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/src/benchmark_control_arcade/workflow_entrypoint.py`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/src/benchmark_control_arcade/publisher.py`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/tests/test_workflow_entrypoint.py`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade/tests/test_publisher.py`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/run-specs/scheduled/composio-full.json`

### Step 1: Write the failing entrypoint and publisher tests

Add tests that prove:

- the entrypoint routes `run_type="aioa"` to the AIOA runner
- the entrypoint routes `run_type="geo"` to the GEO runner
- the publisher updates `run.json` status transitions correctly
- publisher writes into the canonical run directory only

### Step 2: Run the tests and confirm they fail

Run:

`uv run --project /Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade pytest tests/test_workflow_entrypoint.py tests/test_publisher.py -q`

Expected:

- entrypoint and publisher modules do not exist yet

### Step 3: Implement the entrypoint and publisher

The entrypoint should:

1. load the `RunSpec`
2. update `run.json` to `running`
3. call the correct runner
4. write artifacts
5. update `run.json` to `completed` or `failed`

The publisher should be the only code that knows the exact on-disk run layout.

### Step 4: Add the run workflow

`run-benchmark.yml` must support:

- `workflow_dispatch`
- inputs: `run_id`, `run_type`, `run_spec_json`
- checkout of the main code branch and the data branch
- dependency installation with `uv`
- execution of `workflow_entrypoint.py`
- commit and push to the data branch

Set the workflow `run-name` to include at least:

- `run_id`
- `run_type`
- target

### Step 5: Add the scheduled workflow

`scheduled-benchmarks.yml` should:

- trigger on a daily schedule
- load one or more checked-in run specs from `run-specs/scheduled/`
- call the same entrypoint path as the manual workflow

### Step 6: Re-run the tests and validate workflow syntax

Run:

- `uv run --project /Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade pytest tests/test_workflow_entrypoint.py tests/test_publisher.py -q`
- `pre-commit run check-yaml --all-files`

Expected:

- the entrypoint and publisher tests pass
- workflow YAML is valid

### Step 7: Request review

Request:

- `@superpowers:code-reviewer`
- `@architecture-strategist`
- `@security-sentinel`

### Step 8: Commit

```bash
git add .github/workflows/run-benchmark.yml .github/workflows/scheduled-benchmarks.yml tools/benchmark_control_arcade/src/benchmark_control_arcade/workflow_entrypoint.py tools/benchmark_control_arcade/src/benchmark_control_arcade/publisher.py tools/benchmark_control_arcade/tests/test_workflow_entrypoint.py tools/benchmark_control_arcade/tests/test_publisher.py run-specs/scheduled
git commit -m "feat: add benchmark execution workflows and publisher"
```

---

## Task 9: Final docs, merge gates, and end-to-end verification

### Files

- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/docs/ops/local-development.md`
- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/docs/ops/github-setup.md`
- Create: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/run-specs/README.md`
- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/README.md`
- Create or modify any package README files only if they are needed to explain local usage

### Step 1: Finish the ops and run-spec docs

Make sure the docs cover:

- how to configure local `.env`
- how to configure Arcade secrets for the private control-plane server
- how to configure GitHub secrets for execution
- how to create the data branch
- how to enable required status checks
- how to add a new scheduled run spec

### Step 2: Run the full automated test matrix

Run:

- `uv run --project /Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa pytest tests/ -q`
- `uv run --project /Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/geo_audit_arcade pytest tests/ -q`
- `uv run --project /Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/tools/benchmark_control_arcade pytest tests/ -q`
- `pre-commit run --all-files`

Expected:

- all package tests pass
- pre-commit passes

### Step 3: Run one safe local smoke test

Only if safe local secrets are configured:

1. start the control server locally with stdio or HTTP
2. call `StartRun` against a non-production test repository or a dry-run branch
3. confirm:
   - a queued run record is created
   - the workflow dispatch request is sent
   - `GetRunStatus` can retrieve the initial record

If safe credentials are not available, skip this step and document the skip explicitly.

### Step 4: Final review loop

Request:

- `@superpowers:code-reviewer`
- `@kieran-python-reviewer`
- `@security-sentinel`

Do not mark the plan complete until Important issues are fixed and re-reviewed.

### Step 5: Final commit

```bash
git add docs/ops run-specs aioa/README.md
git commit -m "docs: finalize benchmark control plane setup"
```

---

## Required Review / Fixer Protocol

After each task:

1. Implementer summarizes:
   - files changed
   - tests run
   - remaining risk
2. Spec reviewer checks plan compliance.
3. Code quality reviewer checks:
   - unnecessary complexity
   - test quality
   - secret handling
   - naming and file boundaries
4. If the reviewer finds issues:
   - spawn a dedicated fixer subagent
   - fix only the issues in that task
   - re-run focused tests
   - re-run the reviewer

For Tasks 4-6:

- collect all reviews first
- only then dispatch fixers in parallel
- do not start Task 7 until all three are approved

## Testing Strategy Notes

- **AIOA:** use real temp directories and real JSON/SQLite stores.
- **GitHub integration:** use `respx` at the HTTP boundary; do not patch request-building helpers.
- **Geo runner:** test prompt construction and structured-output contract with real prompt files; patch only the Agent SDK boundary.
- **MCP server tools:** call the real Python tool functions and use the GitHub client boundary abstraction.
- **Security checks:** add tests that assert secrets never appear in logs or saved artifacts.

## Risks to Watch

- `run_id` plumbing can break existing AIOA tests if stores and pipeline are updated inconsistently.
- data-branch pushes can race if the workflow edits anything outside the run’s own directory.
- `.mcp.json` and Agent SDK config can drift if two separate sources of MCP truth are created. Prefer one settings model that writes both.
- GEO automation can sprawl if the repo-owned prompt tries to reproduce the entire home-directory skill verbatim. Keep it focused on the production path.
- branch protection is a repo setting, not just a workflow file. Document it and verify it manually.

## Suggested Execution Order

1. Task 1
2. Task 2
3. Task 3
4. Tasks 4, 5, 6 in parallel
5. Task 7
6. Task 8
7. Task 9

## Handoff Notes for the Junior Engineer

- Keep the first version boring. If you feel tempted to add a second registry, a second dispatch path, or a generic comparison engine, stop.
- Preserve the boundary between deterministic GEO tools and orchestration/history tools.
- Treat the GitHub client and the Agent SDK as boundary dependencies. Test their contracts, not their internals.
- Use the smallest possible review/fix loop. Fix only what the reviewer found before moving on.
- If any step feels unclear, stop and ask instead of guessing.
