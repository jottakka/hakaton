# AIOA Review Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `aioa` honest and safe in its current SEO-only state, prevent failed search collection from corrupting benchmark scores, and remove false-positive company attribution in both mention detection and rank extraction.

**Architecture:** Do not re-enable the full AIO model fan-out in this handoff. Treat the current product as SEO-only, make that mode explicit in code/output/docs, and ensure missing AIO data stays missing instead of turning into zeros. Carry search-engine failure state from collection through storage and analysis so partial runs are visible and excluded from averages. Tighten company matching by using boundary-aware mention matching and hostname-based SERP attribution.

**Tech Stack:** Python 3.11+, `uv`, `pytest`, `pytest-asyncio`, existing `src/` pipeline/orchestrator/store modules, JSON + SQLite stores, Markdown docs in `README.md`

---

## Working Rules

- Use `@superpowers:test-driven-development` for every code change in this plan.
- Use `@superpowers:verification-before-completion` before marking any task done.
- Request `@superpowers:code-reviewer` after Task 2 and again after Task 6.
- This workspace snapshot is not currently a git repo. If you do this work in a git-tracked clone, commit after each task. If not, skip the commit step and keep a written progress log in this file.
- Keep the scope narrow. The goal is to fix correctness and honesty, not to redesign the whole product.

## Out of Scope

- Re-enabling multi-model AIO fan-out in `src/models.py`
- Changing the competitor set or scoring matrix contents
- Redesigning the CLI UX beyond making current behavior explicit

---

## Task 1: Make the current SEO-only runtime explicit

### Files for Task 1

- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/src/pipeline.py`
- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/src/orchestrator.py`
- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/src/output.py`
- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/README.md`
- Test: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/tests/test_pipeline.py`
- Test: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/tests/test_orchestrator.py`
- Test: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/tests/test_output.py`

### Why this task is first

Right now the code silently skips AIO work while the docs still promise it. Fix that first so every later change is built on honest behavior.

### Step 1: Write the failing pipeline test

Add a new test in `tests/test_pipeline.py` that proves the final analysis is marked SEO-only when `model_results` is empty.

Use a test like this:

```python
@pytest.mark.asyncio
async def test_run_full_pipeline_marks_seo_only_mode(monkeypatch, tmp_path):
    # Arrange the same fake store and fake search path used by the existing pipeline tests.
    # Force zero model results and one successful search result.
    analysis = await run_full_pipeline(...)
    assert analysis["run_mode"] == "seo_only"
    assert analysis["summary"]["arcade_avg_aio_score"] is None
```

### Step 2: Write the failing orchestrator and output tests

Add one test in `tests/test_orchestrator.py` and one in `tests/test_output.py`.

Use shapes like these:

```python
@pytest.mark.asyncio
async def test_run_orchestrator_sets_null_aio_score_when_no_model_results(monkeypatch):
    analysis = await run_orchestrator(
        run_id="test-run",
        model_results=[],
        search_results=[...],
        competitor_config={"target": "Arcade", "competitors": ["Composio"]},
        prompts=[],
        terms=[...],
    )
    assert analysis["run_mode"] == "seo_only"
    assert analysis["summary"]["arcade_avg_aio_score"] is None
```

```python
def test_print_summary_shows_seo_only_mode(capsys):
    print_summary(
        {
            "run_id": "run-1",
            "generated_at": "2026-03-18T00:00:00Z",
            "run_mode": "seo_only",
            "summary": {
                "arcade_avg_aio_score": None,
                "arcade_avg_seo_score": 55,
                "top_competitor": "Composio",
                "biggest_gap": "s001",
            },
            "aio_results": [],
            "seo_results": [],
            "gap_report": [],
        }
    )
    out = capsys.readouterr().out
    assert "Run Mode:  SEO-only" in out
    assert "Arcade Avg AIO Score" not in out
```

### Step 3: Run the focused tests and confirm they fail

Run:

`uv run pytest tests/test_pipeline.py tests/test_orchestrator.py tests/test_output.py -q`

Expected:

- the new tests fail because `run_mode` does not exist yet
- the orchestrator fallback still returns `0` instead of `None` for missing AIO
- the output summary does not show an explicit runtime mode

### Step 4: Implement the minimal runtime-mode plumbing

Make these exact changes:

- In `src/orchestrator.py`, derive `run_mode` from the incoming raw data:
  - `"full"` when `model_results` is non-empty
  - `"seo_only"` when `model_results` is empty
- In `src/orchestrator.py`, ensure every summary path uses `None` for missing AIO scores instead of `0`
- In `src/pipeline.py`, keep the skip behavior for now, but make the comment and log line explicit that this run mode is intentionally `seo_only`
- In `src/output.py`, print a new line near the report header:
  - `Run Mode:  SEO-only` when `analysis["run_mode"] == "seo_only"`
  - `Run Mode:  Full` otherwise

### Step 5: Update the README so it matches reality

In `README.md`, change the product description and usage sections so they say:

- the current shipped runtime is SEO-only
- the AIO model layer exists as scaffolding but is not active in this version
- the `query` command currently runs the search/orchestrator path, not live AIO model fan-out

Do not promise 4 active LLMs anywhere in the "What It Does" or "Usage" sections after this edit.

### Step 6: Re-run the focused tests and the nearby regression tests

Run:

- `uv run pytest tests/test_pipeline.py tests/test_orchestrator.py tests/test_output.py -q`

Expected:

- all tests in those files pass
- the new summary behavior omits AIO score output when AIO data is missing

### Step 7: Optional checkpoint commit

If working in a git checkout, commit with:

`git commit -am "fix: make seo-only runtime explicit"`

### Done When for Task 1

- the product no longer silently pretends AIO ran when it did not
- `summary["arcade_avg_aio_score"]` is `None` in SEO-only runs
- terminal output clearly shows the run mode
- README.md no longer overpromises current functionality

---

## Task 2: Preserve search failures instead of turning them into zero scores

### Files for Task 2

- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/src/search.py`
- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/src/pipeline.py`
- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/src/orchestrator.py`
- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/src/store.py`
- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/src/stores/json_store.py`
- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/src/stores/sqlite_store.py`
- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/src/output.py`
- Test: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/tests/test_search.py`
- Test: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/tests/test_pipeline.py`
- Test: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/tests/test_orchestrator.py`
- Test: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/tests/test_store.py`
- Test: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/tests/test_output.py`

### Why this task matters

This is the most dangerous data-integrity bug in the review. A collection outage should never become a real benchmark score.

### Step 1: Write the failing search-layer tests

Add tests in `tests/test_search.py` for these two behaviors:

```python
@pytest.mark.asyncio
async def test_run_all_searches_returns_failed_engine_records(monkeypatch):
    async def engine_ok(query: str):
        return [{"position": 1, "title": query, "url": "ok", "snippet": ""}]

    async def engine_fail(query: str):
        raise RuntimeError("boom")

    monkeypatch.setattr("src.search._ENGINES", {"ok": engine_ok, "bad": engine_fail})
    results = await run_all_searches("s001", "q")

    assert {item["engine"] for item in results} == {"ok", "bad"}
    assert next(item for item in results if item["engine"] == "ok")["status"] == "ok"
    assert next(item for item in results if item["engine"] == "bad")["status"] == "failed"
```

```python
@pytest.mark.asyncio
async def test_run_all_searches_keeps_error_text_for_failed_engine(monkeypatch):
    ...
    failed = next(item for item in results if item["engine"] == "bad")
    assert failed["error"] == "boom"
    assert failed["results"] == []
```

### Step 2: Write the failing orchestrator/store tests

Add tests that prove failed search records are stored and excluded from scoring:

```python
def test_merge_subagent_results_excludes_failed_seo_items_from_comparison():
    outputs = [
        {
            "aio_results": [],
            "seo_results": [
                {
                    "term_id": "s001",
                    "query": "mcp gateway",
                    "status": "failed",
                    "aggregate_score": None,
                    "failed_engines": ["google"],
                }
            ],
            "observations": {},
        }
    ]
    merged = merge_subagent_results(outputs, "Arcade", ["Composio"])
    assert merged["comparison_matrix"]["seo_avg_scores"]["Arcade"] is None
    assert merged["gap_report"] == []
```

Also extend `tests/test_store.py` so both stores round-trip `status` and `error` on search results.

### Step 3: Run the focused tests and confirm they fail

Run:

`uv run pytest tests/test_search.py tests/test_store.py tests/test_orchestrator.py tests/test_output.py -q`

Expected:

- new tests fail because search results do not carry `status` and `error`
- store backends do not persist those fields yet
- failed SEO items still flow into aggregate math

### Step 4: Add explicit status fields to search result records

Change the raw search result shape everywhere to this:

```python
{
    "engine": "google",
    "term_id": "s001",
    "results": [...],
    "timestamp": "...",
    "status": "ok",      # "ok" or "failed"
    "error": None,       # string when failed
}
```

Implementation rules:

- In `src/search.py`, always append one record per engine, even on failure
- On failure, store:
  - `status="failed"`
  - `results=[]`
  - `error=str(exc)`
- On success, store:
  - `status="ok"`
  - `error=None`

### Step 5: Widen the store interface and both backends

Update:

- `src/store.py`
- `src/stores/json_store.py`
- `src/stores/sqlite_store.py`

Specific changes:

- Widen `save_search_result(...)` to accept `status` and `error`
- Persist those fields in the JSON store file payload
- Add `status TEXT NOT NULL` and `error TEXT` to the SQLite `search_results` table
- Keep read-back shapes aligned across both backends

Important:

- Update `tests/test_store.py` first, then the protocol, then both store implementations
- Do not let the two backends return different key names for the same concept

### Step 6: Exclude failed terms from scoring and mark partial runs

In `src/orchestrator.py`:

- only score search records where `status == "ok"`
- derive per-term status:
  - `ok` when all engine records succeeded
  - `partial` when at least one engine failed and at least one succeeded
  - `failed` when no engine records succeeded
- for failed terms:
  - set `aggregate_score = None`
  - attach `failed_engines`
  - do not include the term in comparison averages
  - do not include the term in gap analysis

In `src/output.py`:

- print a warning section when any term is `partial` or `failed`
- show counts, not a wall of raw exception text

### Step 7: Re-run focused tests, then broader regression tests

Run:

- `uv run pytest tests/test_search.py tests/test_store.py tests/test_pipeline.py tests/test_orchestrator.py tests/test_output.py -q`
- `uv run pytest tests/test_skills.py -q`

Expected:

- all tests pass
- failed engine records are preserved
- incomplete SEO data no longer produces fake zero scores

### Step 8: Optional checkpoint commit

If working in a git checkout, commit with:

`git commit -am "fix: preserve search failures in scoring"`

### Done When for Task 2

- engine failures are visible in stored raw data
- failed terms are marked failed or partial, not scored as zero
- comparison and gap logic ignore failed terms
- the output warns when a run is incomplete

---

## Task 3: Fix mention detection so common words do not count as brand mentions

### Files for Task 3

- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/src/skills/mention_detection.py`
- Test: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/tests/test_skills.py`

### Why this task matters

The current helper claims whole-word matching but actually uses substring matching. That will poison AIO scoring if the AIO layer is turned back on later.

### Step 1: Add the failing regression tests

Add these tests to `tests/test_skills.py`:

```python
def test_detect_mentions_does_not_match_company_inside_larger_word():
    text = "We should merge configs before deploy."
    mentions = detect_mentions(text, "Arcade", ["Merge"])
    assert mentions["Merge"]["mentioned"] is False
```

```python
def test_detect_mentions_handles_punctuation_around_company_name():
    text = "Arcade, Composio, and Merge are all mentioned here."
    mentions = detect_mentions(text, "Arcade", ["Composio", "Merge"])
    assert mentions["Merge"]["mentioned"] is True
    assert mentions["Composio"]["mentioned"] is True
```

### Step 2: Run the focused tests and confirm they fail

Run:

`uv run pytest tests/test_skills.py -q`

Expected:

- the false-positive test fails because `Merge` is matched inside `merge`

### Step 3: Replace raw substring logic with one shared match helper

In `src/skills/mention_detection.py`, add a helper that returns the first regex match object for a company name using boundaries.

Use an implementation shape like this:

```python
def _find_company_match(text: str, company: str) -> re.Match[str] | None:
    pattern = re.compile(rf"(?<!\\w){re.escape(company)}(?!\\w)", re.IGNORECASE)
    return pattern.search(text)
```

Then update all of these functions to use the same shared helper:

- `_find_mention_position(...)`
- `_extract_context_snippet(...)`
- `detect_mentions(...)`

Important:

- do not leave one helper on substring logic and another helper on boundary logic
- position and context must be derived from the same first match span

### Step 4: Re-run the focused tests

Run:

`uv run pytest tests/test_skills.py -q`

Expected:

- both new tests pass
- older mention-detection tests still pass

### Step 5: Run the nearby orchestrator regression tests

Run:

`uv run pytest tests/test_skills.py tests/test_orchestrator.py -q`

Expected:

- orchestrator tests still pass because mention shapes are unchanged

### Step 6: Optional checkpoint commit

If working in a git checkout, commit with:

`git commit -am "fix: use boundary-aware mention detection"`

### Done When for Task 3

- company mentions are matched as standalone names, not arbitrary substrings
- position and snippet extraction are based on the same real match
- common words like `merge` no longer trigger false brand mentions

---

## Task 4: Restrict rank attribution to company hostnames

### Files for Task 4

- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/src/skills/rank_extraction.py`
- Test: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/tests/test_skills.py`

### Why this task matters

Current SEO attribution can give credit to a company just because its name appears in a random page title. That makes the benchmark untrustworthy.

### Step 1: Replace the current title-based test with stricter domain tests

In `tests/test_skills.py`, replace the current permissive ranking test with these:

```python
def test_extract_rankings_matches_known_company_domain():
    results = [
        {"position": 1, "title": "Composio docs", "url": "https://composio.dev/docs", "snippet": "..."},
        {"position": 2, "title": "Arcade platform", "url": "https://arcade.dev/docs", "snippet": "..."},
    ]
    rankings = extract_rankings(results, "Arcade", ["Composio"])
    assert rankings["Composio"]["position"] == 1
    assert rankings["Arcade"]["position"] == 2
```

```python
def test_extract_rankings_does_not_credit_unrelated_domain_by_title_only():
    results = [
        {"position": 1, "title": "How to merge MCP configs", "url": "https://example.com/blog", "snippet": "..."},
    ]
    rankings = extract_rankings(results, "Arcade", ["Merge"])
    assert rankings["Merge"]["position"] is None
```

### Step 2: Run the focused tests and confirm they fail

Run:

`uv run pytest tests/test_skills.py -q`

Expected:

- the old implementation still credits title-only matches, so the new negative test fails

### Step 3: Change URL matching to inspect hostname only

In `src/skills/rank_extraction.py`:

- parse URLs with `urllib.parse.urlparse`
- extract and normalize the hostname
- strip leading `www.`
- match only against the hostname, not the full URL path and not the title text

Use rules like this:

- exact domain match should count
- subdomain of a known company domain should count
- unrelated domains should never count just because a company word appears in the title

Implementation hint:

```python
host = (urlparse(url).hostname or "").lower()
host = host.removeprefix("www.")
```

Then match against `_DOMAIN_HINTS` using the hostname only.

### Step 4: Re-run the focused tests

Run:

`uv run pytest tests/test_skills.py -q`

Expected:

- the new rank extraction tests pass
- the score-calculation tests in the same file still pass

### Step 5: Run the nearby orchestrator tests

Run:

`uv run pytest tests/test_skills.py tests/test_orchestrator.py -q`

Expected:

- orchestrator scoring still works with the stricter ranking helper

### Step 6: Optional checkpoint commit

If working in a git checkout, commit with:

`git commit -am "fix: use hostname-based rank attribution"`

### Done When for Task 4

- rank extraction only credits real company domains
- unrelated blog posts no longer count as brand rankings
- the helper behavior now matches the README statement "by domain"

---

## Task 5: Make comparison math preserve missing dimensions

### Files for Task 5

- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/src/skills/competitor_comparison.py`
- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/src/orchestrator.py`
- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/src/output.py`
- Test: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/tests/test_skills.py`
- Test: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/tests/test_orchestrator.py`
- Test: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/tests/test_output.py`

### Why this task matters

In the current SEO-only runtime, missing AIO data is being treated as zero. That distorts combined scores and can change winners.

### Step 1: Add the failing SEO-only comparison tests

Add these tests:

```python
def test_build_comparison_matrix_uses_available_dimensions_only():
    matrix = build_comparison_matrix(
        aio_aggregates=[],
        seo_aggregates=[{"Arcade": 80, "Composio": 60}],
        target="Arcade",
        competitors=["Composio"],
    )
    assert matrix["aio_avg_scores"]["Arcade"] is None
    assert matrix["combined_avg_scores"]["Arcade"] == 80
    assert matrix["combined_avg_scores"]["Composio"] == 60
```

```python
@pytest.mark.asyncio
async def test_run_orchestrator_keeps_null_aio_summary_in_seo_only_mode(monkeypatch):
    analysis = await run_orchestrator(
        run_id="test-run",
        model_results=[],
        search_results=[...],
        competitor_config={"target": "Arcade", "competitors": ["Composio"]},
        prompts=[],
        terms=[...],
    )
    assert analysis["summary"]["arcade_avg_aio_score"] is None
```

### Step 2: Run the focused tests and confirm they fail

Run:

`uv run pytest tests/test_skills.py tests/test_orchestrator.py tests/test_output.py -q`

Expected:

- `combined_avg_scores` still comes out halved because missing AIO is treated as zero

### Step 3: Change the averaging rules in `competitor_comparison.py`

Make these exact behavior changes:

- if a company has no AIO values, `aio_avg_scores[company] = None`
- if a company has no SEO values, `seo_avg_scores[company] = None`
- compute `combined_avg_scores` from only the dimensions that are present
- if neither dimension is present for a company, set `combined_avg_scores[company] = None`

Use an implementation shape like this:

```python
present_scores = [score for score in [aio_score, seo_score] if score is not None]
combined = round(sum(present_scores) / len(present_scores)) if present_scores else None
```

### Step 4: Make comparison outputs explicit when a dimension is missing

In `src/skills/competitor_comparison.py` and `src/orchestrator.py`:

- make `head_to_head["aio"]` use `winner=None` when AIO is absent
- make ranking lists skip dimensions where every company score is `None`
- keep the JSON schema stable enough that callers still find the same top-level keys

Do not invent a second comparison structure. Keep the current one and make the missing-data semantics clearer.

### Step 5: Re-run focused tests and the nearby output regression tests

Run:

- `uv run pytest tests/test_skills.py tests/test_orchestrator.py tests/test_output.py -q`

Expected:

- SEO-only runs keep full SEO scores in `combined_avg_scores`
- missing AIO stays `None`, not `0`

### Step 6: Optional checkpoint commit

If working in a git checkout, commit with:

`git commit -am "fix: preserve missing dimensions in comparison math"`

### Done When for Task 5

- combined scores no longer get cut in half during SEO-only runs
- missing AIO is represented as missing, not failure
- summary output remains consistent with SEO-only behavior

---

## Task 6: Final docs cleanup and regression verification

### Files for Task 6

- Modify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/README.md`
- Verify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/tests/test_pipeline.py`
- Verify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/tests/test_search.py`
- Verify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/tests/test_orchestrator.py`
- Verify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/tests/test_skills.py`
- Verify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/tests/test_store.py`
- Verify: `/Users/franciscojuniodelimaliberal/Documents/hackaton/hakaton/aioa/tests/test_output.py`

### Step 1: Finish the README cleanup

Make sure `README.md` also includes:

- `ARCADE_API_KEY`
- `ARCADE_USER_ID`
- the correct current test count, or better, remove the hard-coded test count entirely and say "the test suite should pass"
- no remaining claims that the current version runs 4 live LLMs

### Step 2: Run the full automated test suite

Run:

`uv run pytest tests/ -q`

Expected:

- all tests pass
- no test is still encoding the old title-only or silent-zero behavior

### Step 3: Run one optional manual smoke test only if safe credentials are available

Run:

`uv run python -m src.main query "best mcp gateway"`

Expected:

- the command completes successfully
- the generated analysis marks `run_mode` as `seo_only`
- the report does not show a fake AIO score
- if search collection partially fails, the output warns that the run is partial instead of showing all-zero SEO scores

If you do not have safe credentials, skip this step and note that it was not run.

### Step 4: Final review pass

Request `@superpowers:code-reviewer` on only the `aioa` folder again and verify that:

- there is no silent AIO overclaim left
- incomplete search collection is surfaced as partial or failed
- mention and rank helpers no longer use permissive substring matching
- comparison math preserves missing dimensions

### Step 5: Optional final checkpoint commit

If working in a git checkout, commit with:

`git commit -am "docs: align aioa behavior and verification"`

### Done When for Task 6

- README matches runtime behavior
- the full test suite passes
- the major review findings are closed
- any skipped manual smoke test is explicitly documented

---

## Suggested Implementation Order

1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5
6. Task 6

Do not jump ahead. Task 2 changes the meaning of SEO result records, so finish that before touching comparison math.

## Risks to Watch

- Updating the SQLite schema can break tests if you change write paths but forget read-back shape parity.
- Mention detection and snippet extraction must use the same matching rule, or tests will pass while snippets still point at false positives.
- Rank extraction will likely require replacing, not extending, the current title-based test because that test is asserting the buggy behavior.
- If you represent missing scores as `None`, make sure sorting logic never tries to compare `None` to `int`.

## Handoff Notes for the Junior Engineer

- Prefer the smallest behavior-preserving change that makes each new test pass.
- Do not restore the AIO model layer in this plan. That is a separate project.
- If you feel tempted to add a new abstraction, stop and ask whether a helper function inside the existing file is enough.
- After each task, write 2-3 sentences in your progress notes saying what changed, what tests you ran, and what still feels risky.
