# GEO Audit Parallel Exploration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade `geo-site-audit` so it performs a bounded parallel-swarm exploration pass before scoring, with user-selectable coverage presets and better discovery of representative pages, sections, subdomains, and site artifacts.

**Architecture:** Add an explicit exploration contract to the `geo-site-audit` skill package, centered on four cheap discovery missions: architecture, content, proof, and technical. Keep the current scoring and issue workflow, but move it after a new merged evidence-pack stage. When the local deterministic MCP server exists, extend `CollectGeoEvidence` so it can build a larger, source-tagged candidate pool and apply the same bounded coverage presets as the prompt-level swarm. This keeps exploration more thorough without turning the workflow into an unbounded crawl.

**Tech Stack:** Claude skill markdown package, Markdown reference docs, optional local MCP server under `tools/geo_audit_local_mcp/`, fixture-driven acceptance docs, readonly validation pass, `pytest` for deterministic tool tests

---

## Task 1: Write the exploration acceptance cases first

### Files for Task 1

- Create: `/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/acceptance-cases.md`
- Create: `/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/exploration-presets.md`

### Step 1: Create the two files

Add the files with one-line placeholders so neither file is empty while the package is being updated.

### Step 2: Author four acceptance scenarios in `acceptance-cases.md`

Write four scenario sections with:

- prompt
- expected coverage preset
- expected exploration lanes
- expected candidate sources
- expected bounds
- what the workflow must not do

Use these four scenarios:

- one deep page with no coverage specified, which should default to `exhaustive`
- one homepage or docs hub with explicit `light` coverage
- one comparison audit with explicit `standard` coverage
- one subdomain-heavy site where root, docs, and blog artifacts must be checked independently

### Step 3: Make the expected failures explicit

Each scenario should explicitly say the workflow must not:

- sample only the first few DOM-order links
- ignore sitemap or `llms.txt` candidates when available
- silently ignore the requested coverage preset
- turn `exhaustive` into a full-site crawl

### Step 4: Verify the authored "tests" exist

Run: `rg -n "Scenario|must not|coverage preset" "/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/acceptance-cases.md"`

Expected: matches for all four scenario sections and their failure rules.

### Done When for Task 1

- exploration behavior has concrete authored acceptance cases
- later prompt and tool edits can be checked against those cases instead of vague intent

---

## Task 2: Define the bounded coverage presets and swarm contract

### Files for Task 2

- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/exploration-presets.md`

### Step 1: Define the four presets as a table

Document these exact bounded defaults:

| Preset | Representative page budget | Section budget | Extra subdomain budget | Per-lane candidate return cap |
| ------ | -------------------------- | -------------- | ---------------------- | ----------------------------- |
| `light` | 4 | 2 | 1 | 2 |
| `standard` | 8 | 4 | 2 | 3 |
| `deep` | 12 | 6 | 3 | 4 |
| `exhaustive` | 18 | 8 | 4 | 6 |

Important:

- these counts are in addition to the target URL, site root, and required artifact checks
- `exhaustive` is still bounded
- all presets use the same four discovery missions; only the breadth changes

### Step 2: Define the candidate-source priority order

Document this order:

1. target URL
2. site root or nearest hub
3. declared sitemap URLs from `robots.txt`
4. standard `/sitemap.xml` or sitemap index
5. `llms.txt` and `llms-full.txt`
6. internal navigation and footer links
7. path-cluster representatives
8. redirect targets and discovered subdomains

### Step 3: Define the four discovery missions

Document these responsibilities:

- `architecture`: major sections, hubs, path clusters, representative pages
- `content`: answer-like pages, FAQs, comparisons, listicles, strong extractable passages
- `proof`: data-rich pages, pages with citations, named entities, trust or credibility signals
- `technical`: artifacts, metadata, JSON-LD, canonicals, crawl or rendering risks

### Step 4: Define the orchestrator merge rules

Require the orchestrator to:

- deduplicate by normalized URL
- preserve candidate source attribution
- preserve section and subdomain tags
- prefer broader section coverage over repeated pages from the same cluster
- stop only after the preset budget is filled or no materially new sections remain

### Step 5: Verify the contract is concrete

Run: `rg -n "light|standard|deep|exhaustive|architecture|content|proof|technical" "/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/exploration-presets.md"`

Expected: matches for all four presets and all four missions.

### Done When for Task 2

- the preset behavior is numeric, bounded, and unambiguous
- the swarm missions and merge rules are explicit enough to implement

---

## Task 3: Rewrite the main `geo-site-audit` workflow around the exploration swarm

### Files for Task 3

- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/SKILL.md`

### Step 1: Add coverage selection to the quick-start and clarification flow

Update the top of the file so the workflow:

- defaults to `exhaustive`
- lets the user ask for `light`, `standard`, `deep`, or `exhaustive`
- asks for coverage only when the user's intent or budget sensitivity is unclear

Add a fifth ambiguity question:

- `Which coverage preset should be used: light, standard, deep, or exhaustive?`

### Step 2: Replace the current "Smart Discovery" section

Replace the old shallow sibling-sampling guidance with:

- required candidate sources from `exploration-presets.md`
- the four mission model
- the bounded preset table summary
- a rule that the workflow always explores more than one page when the target is a hub, homepage, section, comparison input, or cross-subdomain surface

### Step 3: Split the workflow into explicit phases

Update the workflow phases to this shape:

1. assess scope and requested coverage
2. build the initial evidence pack
3. run the parallel exploration swarm
4. verify and merge the evidence pack
5. run lever scoring agents
6. normalize scores
7. synthesize for Arcade
8. validate hard claims
9. optionally create or draft issues

### Step 4: Update the orchestration section

Change the recommended topology so the first parallel stage is the exploration swarm using cheaper models:

- architecture discovery agent
- content discovery agent
- proof discovery agent
- technical discovery agent

Then explicitly state that scoring agents run after the orchestrator merges the exploration outputs.

### Step 5: Add the new reference files

Add these to the reference-file list:

- `exploration-presets.md`
- `acceptance-cases.md`

### Step 6: Verify the prompt surface changed

Run:

- `rg -n "exhaustive|light|standard|deep" "/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/SKILL.md"`
- `rg -n "architecture discovery agent|content discovery agent|proof discovery agent|technical discovery agent" "/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/SKILL.md"`

Expected: matches for all preset names and the four exploration agents.

### Done When for Task 3

- the main skill now clearly runs exploration before scoring
- coverage presets are first-class behavior, not a vague add-on

---

## Task 4: Rewrite the subagent prompt templates for the parallel swarm

### Files for Task 4

- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/subagent-prompts.md`

### Step 1: Replace the single discovery agent with four discovery prompts

Author dedicated prompt templates for:

- `Architecture Discovery Agent`
- `Content Discovery Agent`
- `Proof Discovery Agent`
- `Technical Discovery Agent`

Each prompt must include:

- target URLs
- audit mode
- coverage preset
- Arcade baselines
- deterministic evidence, if available
- a hard return cap based on the selected preset

### Step 2: Keep scoring prompts, but move them after merge

Update the content/citation and entity/technical scoring prompts so they consume:

- the merged evidence pack
- the selected representative pages
- the orchestrator's coverage summary

Do not let scoring agents perform their own freeform discovery.

### Step 3: Add a merge contract for the orchestrator

Require the orchestrator to produce:

- normalized candidate list
- selected representative page list
- source attribution by URL
- section coverage summary
- subdomain coverage summary
- truncation warnings when the preset budget clipped the pool

### Step 4: Add explicit preset placeholders

Use a single placeholder such as `<coverage preset>` in every relevant prompt so the preset is always carried into the subagents instead of being implied.

### Step 5: Verify the prompt file structure

Run: `rg -n "Architecture Discovery Agent|Content Discovery Agent|Proof Discovery Agent|Technical Discovery Agent|coverage preset" "/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/subagent-prompts.md"`

Expected: matches for all new discovery prompts and the preset placeholder.

### Done When for Task 4

- the swarm is implementable from `subagent-prompts.md` alone
- the scoring layer is clearly downstream from discovery

---

## Task 5: Extend the deterministic data model for coverage-aware exploration

### Files for Task 5

- Modify: `tools/geo_audit_local_mcp/src/geo_audit_local_mcp/models.py`
- Modify: `tools/geo_audit_local_mcp/tests/test_models.py`
- Create: `tools/geo_audit_local_mcp/src/geo_audit_local_mcp/selection.py`
- Create: `tools/geo_audit_local_mcp/tests/test_selection.py`

### Step 1: Write the failing tests first

Author tests for:

- accepted `coverage_preset` values: `light`, `standard`, `deep`, `exhaustive`
- candidate pages carrying source attribution
- coverage summaries carrying section and subdomain counts
- monotonic preset bounds where `light < standard < deep < exhaustive`

### Step 2: Add the core exploration models

Add at least these shapes:

```python
CoveragePreset = Literal["light", "standard", "deep", "exhaustive"]

class CandidatePage(BaseModel):
    url: AnyHttpUrl
    source: Literal["target", "root", "sitemap", "llms", "nav", "footer", "path_cluster", "redirect", "manual"]
    section_key: str | None = None
    subdomain_key: str | None = None
    selection_reason: str | None = None
    selected: bool = False

class CoverageSummary(BaseModel):
    preset: CoveragePreset
    representative_page_budget: int
    selected_page_count: int
    section_budget: int
    section_count: int
    extra_subdomain_budget: int
    subdomain_count: int
    truncated: bool = False
```

Then thread those models into `CollectGeoEvidenceResult`.

### Step 3: Implement preset config helpers in `selection.py`

Create one bounded config map using the Task 2 values and expose a helper such as:

```python
PRESET_CONFIG = {
    "light": {"pages": 4, "sections": 2, "subdomains": 1, "per_lane_cap": 2},
    "standard": {"pages": 8, "sections": 4, "subdomains": 2, "per_lane_cap": 3},
    "deep": {"pages": 12, "sections": 6, "subdomains": 3, "per_lane_cap": 4},
    "exhaustive": {"pages": 18, "sections": 8, "subdomains": 4, "per_lane_cap": 6},
}
```

### Step 4: Run the model and selection tests

Run: `cd tools/geo_audit_local_mcp && uv run pytest tests/test_models.py tests/test_selection.py -q`

Expected: PASS

### Done When for Task 5

- the deterministic layer has a typed exploration contract
- the preset bounds live in one shared place instead of being duplicated in prompt text and Python logic

---

## Task 6: Make `CollectGeoEvidence` build a larger candidate pool, then bound it by preset

### Files for Task 6

- Modify: `tools/geo_audit_local_mcp/src/geo_audit_local_mcp/tools/collect_geo_evidence.py`
- Modify: `tools/geo_audit_local_mcp/src/geo_audit_local_mcp/fetching.py`
- Modify: `tools/geo_audit_local_mcp/tests/test_collect_geo_evidence.py`
- Create if needed: `tools/geo_audit_local_mcp/tests/fixtures/hub-page.html`
- Create if needed: `tools/geo_audit_local_mcp/tests/fixtures/robots-with-sitemap.txt`
- Create if needed: `tools/geo_audit_local_mcp/tests/fixtures/sample-sitemap.xml`
- Create if needed: `tools/geo_audit_local_mcp/tests/fixtures/sample-llms.txt`

### Step 1: Write failing collection tests

Cover at least these behaviors:

- declared sitemap URLs from `robots.txt` become candidates
- `llms.txt` URLs become candidates
- nav or footer links become candidates
- subdomain links become candidates with a subdomain tag
- the selected representative set respects the requested preset bounds
- the result includes a truncation warning when the pool is larger than the preset budget

### Step 2: Extend the tool input contract

Add `coverage_preset` to the tool input and default it to `exhaustive`.

Also keep the existing audit inputs such as:

- `target_urls`
- `audit_mode`
- `max_related_pages` only if still needed during migration

If `max_related_pages` is still present, deprecate it in the README and stop using it as the primary control surface.

### Step 3: Implement the candidate pool expansion

In `CollectGeoEvidence`, build candidates from:

- target URLs
- site root or nearest hub
- sitemap paths declared in `robots.txt`
- standard `/sitemap.xml`
- `llms.txt` and `llms-full.txt`
- normalized internal nav and footer links
- redirect targets
- section representatives inferred from path prefixes

Do not score here. Only collect and select.

### Step 4: Apply bounded selection from `selection.py`

Select representatives by:

- preserving source diversity
- preferring uncovered sections over repeated pages from the same cluster
- preserving some subdomain diversity before deepening one section
- marking dropped candidates as truncated rather than pretending they were never found

### Step 5: Run the collection tests

Run: `cd tools/geo_audit_local_mcp && uv run pytest tests/test_collect_geo_evidence.py -q`

Expected: PASS

### Done When for Task 6

- `CollectGeoEvidence` can feed the new swarm with a wider, more reliable candidate pool
- preset changes materially affect breadth without changing the rest of the audit workflow

---

## Task 7: Update the user-facing docs and command alias to expose coverage cleanly

### Files for Task 7

- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/README.md`
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/QUICKREF.md`
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/deterministic-tools.md`
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/examples.md`
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/commands/geo-audit.md`

### Step 1: Document the new control surface

Explain that users can request:

- `light coverage`
- `standard coverage`
- `deep coverage`
- `exhaustive coverage`

Also document that:

- the default is `exhaustive`
- presets are bounded exploration levels, not crawl-depth toggles
- deterministic tools should receive the same preset when available

### Step 2: Update the deterministic tool instructions

Make `deterministic-tools.md` say that `CollectGeoEvidence` should receive the selected coverage preset whenever the tool supports it.

Also state that if the tool is unavailable, the prompt-level swarm must still honor the preset.

### Step 3: Add concrete examples

Add at least these example prompts:

- one default `exhaustive` audit with no explicit preset
- one explicit `light coverage` audit
- one comparison audit with `standard coverage`
- one docs-hub audit with `deep coverage`

### Step 4: Keep the command alias simple

Do not invent CLI-style flags unless the command system already supports them.

Prefer natural-language modifiers in examples, for example:

- `/geo-audit https://example.com/docs/auth`
- `Use light coverage.`

### Step 5: Verify the docs mention the preset names

Run: `rg -n "light coverage|standard coverage|deep coverage|exhaustive coverage" "/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit"`

Expected: matches in the README, QUICKREF, examples, deterministic tools doc, and command alias.

### Done When for Task 7

- users can actually discover and request the coverage presets
- the docs do not imply hidden knobs or CLI parsing that does not exist

---

## Task 8: Validate the new exploration behavior against the acceptance cases

### Files for Task 8

- Modify as needed: `/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/acceptance-cases.md`
- Modify as needed: all files touched above

### Step 1: Run a readonly validation pass

Use a readonly review agent or a manual dry run against each scenario in `acceptance-cases.md`.

For each scenario, check:

- was the requested or default preset honored
- were sitemap, `llms.txt`, nav/footer, and subdomain sources considered where applicable
- did the workflow stay bounded
- did scoring wait for the merged evidence pack

### Step 2: Record mismatches in the acceptance doc

Under each scenario, add a short validation note:

- `Pass` if behavior matched
- `Mismatch` if the prompt package still leaves something ambiguous

Do not create a separate review file.

### Step 3: Tighten the smallest ambiguous instruction

Fix the smallest thing that resolves each mismatch:

- unclear preset wording
- weak candidate-source priority
- missing orchestrator merge rule
- scoring prompts still doing discovery

### Step 4: Re-run the validation pass

Repeat until all authored scenarios read as `Pass` or have one clearly tracked follow-up limitation.

### Done When for Task 8

- the package behaves consistently on the scenarios it claims to support
- exploration behavior is testable at the prompt level, not just in prose

---

## Task 9: Final cleanup and integration check

### Files for Task 9

- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/SKILL.md`
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/README.md`
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit/subagent-prompts.md`
- Modify if implemented: `tools/geo_audit_local_mcp/src/geo_audit_local_mcp/tools/collect_geo_evidence.py`

### Step 1: Remove stale wording from the old discovery model

Delete or rewrite any text that still implies:

- a single discovery agent owns exploration
- 1-3 sibling pages are the default sampling model
- exploration starts and ends with internal links
- coverage is implicit instead of user-selectable

### Step 2: Verify the deterministic and prompt layers agree

If the local MCP tool work was completed, confirm both layers use the same preset names and bounded budgets.

If the MCP work has not been completed yet, add one clear note in the docs that prompt-level swarm behavior still works without the deterministic tool.

### Step 3: Run the checks

Run:

- `rg -n "1-3 representative sibling|Discovery agent" "/Users/franciscojuniodelimaliberal/.claude/skills/geo-site-audit"`
- `cd tools/geo_audit_local_mcp && uv run pytest tests/test_models.py tests/test_selection.py tests/test_collect_geo_evidence.py -q`

Expected:

- the old shallow-discovery phrasing is gone or intentionally rewritten
- deterministic tests pass if the local package exists

### Step 4: Do the final quality pass

Before calling the work done, use `@superpowers:verification-before-completion`.

Check for:

- repeated or contradictory wording
- preset names that do not match exactly
- any place where `exhaustive` sounds unbounded
- any place where scoring agents can still free-crawl

### Done When for Task 9

- the skill package and deterministic layer tell the same story
- the new exploration model is bounded, testable, and exportable

---

## Notes For The Implementer

- This plan extends the deterministic local MCP path described in `docs/plans/2026-03-17-geo-audit-deterministic-mcp-plan.md`. If that package has not been built yet, fold Tasks 5 and 6 into the `CollectGeoEvidence` work from that plan instead of inventing a second collection path.
- Keep the change focused on exploration. Do not redesign the GEO rubric, Linear taxonomy, or final report shape unless an exploration requirement forces a small wording update.
- Preserve the current "evidence, not vibes" posture. A larger candidate pool should improve coverage, not encourage weaker claims.
- Keep `exhaustive` bounded. The user explicitly wants stronger exploration, not a crawler that runs forever.
- Preserve environment agnosticism. The docs should name behavior and tool contracts, not local-only assumptions.
