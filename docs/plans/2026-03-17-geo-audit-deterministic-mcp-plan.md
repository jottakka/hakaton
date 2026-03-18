# GEO Audit Deterministic MCP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local deterministic MCP server for `geo-site-audit` that provides `CollectGeoEvidence` and `ValidateGeoAuditClaims`, then wire the skill docs to use those tools whenever available.

**Architecture:** Create a small Python package under `tools/geo_audit_local_mcp/` using Arcade's MCP framework. Prefer the higher-level Arcade MCP app path first and only drop to the low-level `MCPServer` API if the app abstraction blocks a real requirement. Keep shared logic in pure Python modules for fetching, extraction, and validation, and expose only two workflow-oriented MCP tools. The `geo-site-audit` skill should treat tool output as hard evidence but still own synthesis and scoring.

**Tech Stack:** Python 3.12, `uv`, `arcade-mcp-server>=1.4.0,<2.0.0`, `httpx`, `beautifulsoup4`, `lxml`, `pydantic`, `pytest`

---

### Task 1: Scaffold the local MCP package

**Files:**
- Create: `tools/geo_audit_local_mcp/pyproject.toml`
- Create: `tools/geo_audit_local_mcp/README.md`
- Create: `tools/geo_audit_local_mcp/src/geo_audit_local_mcp/__init__.py`
- Create: `tools/geo_audit_local_mcp/src/geo_audit_local_mcp/app.py`
- Create: `tools/geo_audit_local_mcp/tests/__init__.py`

**Step 1: Create the package layout**

Create the `tools/geo_audit_local_mcp/` directory tree with `src/` and `tests/`.

**Step 2: Add project metadata and dependencies**

Write `pyproject.toml` with:
- runtime dependencies:
  - `arcade-mcp-server>=1.4.0,<2.0.0`
  - `httpx`
  - `beautifulsoup4`
  - `lxml`
  - `pydantic`
- dev dependencies:
  - `pytest`
  - `pytest-asyncio`

**Step 3: Install dependencies**

Run: `cd tools/geo_audit_local_mcp && uv sync`

Expected: environment created successfully and lockfile generated.

**Step 4: Add a minimal app bootstrap**

Write `src/geo_audit_local_mcp/app.py` with the smallest runnable Arcade MCP app bootstrap.

Important:
- start with the higher-level Arcade MCP app abstraction
- only switch to direct `arcade_mcp_server.server.MCPServer` usage if you hit a real limitation

**Step 5: Smoke-test imports**

Run: `cd tools/geo_audit_local_mcp && uv run python -c "from geo_audit_local_mcp.app import app; print(type(app).__name__)"`

Expected: prints the app object type without import errors.

**Done when:**
- package installs cleanly
- app bootstrap imports cleanly

---

### Task 2: Define deterministic JSON contracts first

**Files:**
- Create: `tools/geo_audit_local_mcp/src/geo_audit_local_mcp/models.py`
- Create: `tools/geo_audit_local_mcp/tests/test_models.py`

**Step 1: Write the failing tests for the two main payloads**

Create tests for:
- `CollectGeoEvidenceResult`
- `ValidateGeoAuditClaimsResult`

The tests should assert:
- required fields exist
- nested structures validate
- optional fields default predictably

**Step 2: Model the evidence result**

Include fields for:
- requested URLs
- discovered domains and subdomains
- artifact checks by domain
- page metadata by URL
- JSON-LD types
- heading extraction
- first-200-word extraction
- warnings and limitations

**Step 3: Model the validation result**

Include fields for:
- contradictions
- unsupported claims
- missing high-signal facts
- confidence downgrade suggestions
- pass/fail summary

**Step 4: Run model tests**

Run: `cd tools/geo_audit_local_mcp && uv run pytest tests/test_models.py -q`

Expected: PASS

**Done when:**
- both tool outputs have stable, typed JSON contracts
- no implementation work starts before the shapes are fixed

---

### Task 3: Build shared fetch and extraction primitives

**Files:**
- Create: `tools/geo_audit_local_mcp/src/geo_audit_local_mcp/fetching.py`
- Create: `tools/geo_audit_local_mcp/src/geo_audit_local_mcp/extraction.py`
- Create: `tools/geo_audit_local_mcp/tests/fixtures/homepage.html`
- Create: `tools/geo_audit_local_mcp/tests/fixtures/with-jsonld.html`
- Create: `tools/geo_audit_local_mcp/tests/test_extraction.py`

**Step 1: Write failing extractor tests**

Cover:
- title extraction
- meta description extraction
- canonical extraction
- Open Graph extraction
- heading extraction
- JSON-LD `@type` extraction
- title vs H1 comparison
- first-200-word extraction

**Step 2: Implement pure extraction helpers**

Keep these functions deterministic and side-effect free. No MCP logic here.

**Step 3: Implement fetch helpers**

Support:
- GET requests
- HEAD or lightweight status checks where useful
- timeout handling
- consistent response normalization for 200, 3xx, 4xx, and network errors

**Step 4: Run the extractor tests**

Run: `cd tools/geo_audit_local_mcp && uv run pytest tests/test_extraction.py -q`

Expected: PASS

**Done when:**
- extraction is testable without the MCP layer
- the helper layer can explain exactly how each hard fact was derived

---

### Task 4: Implement `CollectGeoEvidence`

**Files:**
- Create: `tools/geo_audit_local_mcp/src/geo_audit_local_mcp/tools/__init__.py`
- Create: `tools/geo_audit_local_mcp/src/geo_audit_local_mcp/tools/collect_geo_evidence.py`
- Create: `tools/geo_audit_local_mcp/tests/test_collect_geo_evidence.py`

**Step 1: Write the failing tool tests**

Test at least these behaviors:
- one URL returns page metadata plus domain artifact checks
- hub-style input can include sibling or child page sampling hints
- domain discovery records root plus discovered subdomains
- `robots.txt`, `sitemap.xml`, declared sitemap paths, `llms.txt`, and `llms-full.txt` are checked per domain

**Step 2: Implement the tool input shape**

Recommended input fields:
- `target_urls`
- `audit_mode`
- `max_related_pages`
- `discover_subdomains`
- `check_common_artifact_paths`

**Step 3: Implement the evidence collection workflow**

The tool should:
- normalize the input URLs
- fetch the requested pages
- discover additional domains or subdomains from nav, footer, and redirect targets
- check artifact paths on each discovered domain independently
- extract page-level metadata and structure
- return JSON using `CollectGeoEvidenceResult`

**Step 4: Keep the tool factual only**

Do not let this tool assign lever scores or make strategic recommendations.

**Step 5: Run the tool tests**

Run: `cd tools/geo_audit_local_mcp && uv run pytest tests/test_collect_geo_evidence.py -q`

Expected: PASS

**Done when:**
- the tool returns stable JSON
- the tool can prove hard facts like “artifact exists”, “artifact 404s”, and “JSON-LD types present”

---

### Task 5: Implement `ValidateGeoAuditClaims`

**Files:**
- Create: `tools/geo_audit_local_mcp/src/geo_audit_local_mcp/validation.py`
- Create: `tools/geo_audit_local_mcp/src/geo_audit_local_mcp/tools/validate_geo_audit_claims.py`
- Create: `tools/geo_audit_local_mcp/tests/test_validate_geo_audit_claims.py`

**Step 1: Write the failing validation tests**

Create draft report fixtures that intentionally contain:
- a false “not found” artifact claim
- a false “no JSON-LD” claim
- a false “title/H1 mismatch” claim
- omission of a high-signal fact like a broken sitemap or present `llms.txt`

**Step 2: Implement deterministic validation rules**

Start with explicit, checkable rules only:
- artifact contradiction checks
- JSON-LD presence contradictions
- missing high-signal fact checks
- optional title/H1 mismatch checks based on extracted similarity

**Step 3: Keep validation conservative**

If a claim is subjective, prefer “unsupported” or “review manually” over declaring a hard contradiction.

**Step 4: Run the validator tests**

Run: `cd tools/geo_audit_local_mcp && uv run pytest tests/test_validate_geo_audit_claims.py -q`

Expected: PASS

**Done when:**
- the validator catches deterministic contradictions
- the validator does not try to replace model judgment with rule-based scoring

---

### Task 6: Expose both tools through the local MCP app

**Files:**
- Modify: `tools/geo_audit_local_mcp/src/geo_audit_local_mcp/app.py`
- Modify: `tools/geo_audit_local_mcp/README.md`

**Step 1: Register `CollectGeoEvidence`**

Expose it with a clear, short description that says it collects deterministic GEO evidence for public URLs.

**Step 2: Register `ValidateGeoAuditClaims`**

Expose it with a description that says it checks a draft GEO audit against deterministic evidence JSON.

**Step 3: Add a local run command to the README**

Document how to start the server in stdio mode for Cursor or Claude Code.

**Step 4: Smoke-test local tool exposure**

Run the local server and confirm the MCP client can see both tools.

Expected visible tools:
- `CollectGeoEvidence`
- `ValidateGeoAuditClaims`

**Done when:**
- the server starts cleanly
- both tools are visible to the client

---

### Task 7: Wire the local server into developer tooling

**Files:**
- Modify: `/Users/franciscojuniodelimaliberal/.cursor/mcp.json`
- Optionally modify: Claude Code local MCP config if needed in the target environment

**Step 1: Add a local MCP entry**

Use a clear server name such as `geo-audit-local`.

Recommended command pattern:
- command: the local `uv`
- args: run the local package in stdio mode from `tools/geo_audit_local_mcp`

**Step 2: Reload the client and verify the tool list**

Confirm the client sees:
- `CollectGeoEvidence`
- `ValidateGeoAuditClaims`

**Step 3: Keep `geo-analyzer` unchanged**

This local MCP server is for deterministic audit verification, not for Linear issue management. Do not mix those concerns.

**Done when:**
- the local MCP server is callable from the client
- deterministic tools and Linear tools remain clearly separated

---

### Task 8: Update the `geo-site-audit` skill docs to use the new tools

**Files:**
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/SKILL.md`
- Create: `/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/deterministic-tools.md`
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/README.md`
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/QUICKREF.md`
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/examples.md`
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/commands/geo-audit.md`

**Step 1: Document when to call `CollectGeoEvidence`**

The skill should say:
- call it before scoring on every audit when available
- treat its JSON as hard evidence for technical facts
- fill gaps manually only when the tool cannot determine something

**Step 2: Document when to call `ValidateGeoAuditClaims`**

The skill should say:
- call it after drafting the report and before final output
- revise contradictions or unsupported claims before responding
- keep final judgment model-driven

**Step 3: Document fallback behavior**

If the local MCP server is unavailable:
- continue with the current workflow
- lower confidence for technical findings that were not deterministically checked

**Step 4: Add one example for the deterministic path**

Show an example where the workflow uses both deterministic tools before final output.

**Done when:**
- future agents know exactly when and how to use the deterministic tools
- the skill stays environment-agnostic and tool-name driven

---

### Task 9: Run end-to-end verification on a real target

**Files:**
- Reuse: `geo-audit-composio-dev.md`
- Create if needed: `tools/geo_audit_local_mcp/tests/fixtures/composio-sample.json`

**Step 1: Run `CollectGeoEvidence` on Composio**

Use:
- `https://composio.dev/`
- `https://docs.composio.dev/`

Confirm the JSON captures:
- root and docs subdomains
- artifact checks per domain
- JSON-LD presence or absence
- title/H1 and opening-content extraction

**Step 2: Draft an audit using the current skill**

Use the deterministic JSON during the audit.

**Step 3: Run `ValidateGeoAuditClaims` against the draft**

Confirm it catches any contradictions or unsupported hard claims.

**Step 4: Fix any gaps in the tool logic before calling the implementation done**

**Step 5: Run the full test suite**

Run: `cd tools/geo_audit_local_mcp && uv run pytest -q`

Expected: PASS

**Done when:**
- the deterministic layer works on a real public site
- the skill uses it correctly
- the final audit is measurably more stable than the current LLM-only flow

---

### Task 10: Final cleanup and documentation review

**Files:**
- Modify: `tools/geo_audit_local_mcp/README.md`
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/README.md`

**Step 1: Remove stale wording**

Make sure docs do not promise label creation, strict-mode-only verification, or heuristic scoring that was not actually built.

**Step 2: Add exact startup instructions**

Document:
- how to run the local MCP server
- how to register it in Cursor
- how `geo-site-audit` behaves when it is available versus missing

**Step 3: Re-run one final smoke test**

Expected:
- tools visible
- skill docs aligned
- no contradictory instructions

**Done when:**
- a new engineer can set up the server and understand how the skill uses it without extra context

---

## Notes For The Implementer

- Keep the deterministic layer narrow. Do not build heuristic scoring in v1.
- Prefer fixture-driven unit tests over network-heavy tests.
- Use real network calls only for smoke tests.
- Treat “hard contradiction” and “unsupported claim” differently.
- Keep `geo-analyzer` responsibility limited to Linear workflows.
- Keep the local deterministic server responsibility limited to GEO evidence and validation.
