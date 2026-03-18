"""Core Pipeline — Reusable async functions for running the analysis pipeline.

These functions are called by main.py (CLI) and can be called by a future
FastAPI app without any changes.

The `store` parameter accepts any StoreProtocol-compatible backend:
    JsonFileStore  — MVP default, writes JSON files to disk
    SqliteStore    — Phase 2, swap in when ready
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.input_layer import CompetitorConfig, Prompt, PromptSet, SearchTerm, TermSet
from src.models import run_all_models
from src.orchestrator import run_orchestrator
from src.output import print_summary, write_json_report
from src.search import mcp_session, run_all_searches
from src.store import StoreProtocol
from src.stores.json_store import JsonFileStore


def _default_store(output_dir: str | Path) -> JsonFileStore:
    return JsonFileStore(workspace=Path(output_dir))


async def run_full_pipeline(
    prompt_set: PromptSet,
    term_set: TermSet,
    competitors: CompetitorConfig,
    output_dir: str | Path = "data",
    store: StoreProtocol | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """
    Execute the full benchmarking pipeline:
    1. Initialize store
    2. Create a run record
    3. Fan out to all LLMs for each prompt (concurrently)
    4. Fan out to all search engines for each term (concurrently)
    5. Store all raw results
    6. Run orchestrator analysis
    7. Store and output analysis

    If *run_id* is provided it is used verbatim (external / controlled run).
    If omitted a new UUID is auto-generated (default backward-compatible behaviour).

    Returns the final analysis dict.
    """
    s: StoreProtocol = store or _default_store(output_dir)
    await s.init()

    run_id = await s.create_run(
        prompt_set_id=prompt_set.prompt_set_id,
        term_set_id=term_set.term_set_id,
        competitor_config=competitors.model_dump(),
        run_id=run_id,
    )
    print(f"[pipeline] Run created: {run_id}")

    # --- Model Layer (AIO) — intentionally disabled in SEO-only mode ---
    flat_model_results: list[dict[str, Any]] = []
    print("[pipeline] Run mode: seo_only — AIO model layer is disabled in this version")

    # --- Search Layer (SEO) ---
    # One MCP session is shared across all search terms to avoid repeated
    # connect/disconnect overhead and noisy SDK termination warnings.
    print(f"[pipeline] Running {len(term_set.terms)} terms across 1 search engine...")
    flat_search_results: list[dict[str, Any]] = []
    async with mcp_session() as session:
        for term in term_set.terms:
            try:
                results = await _run_and_store_searches(s, run_id, term, session=session)
                flat_search_results.extend(results)
            except Exception as exc:
                print(f"[pipeline] WARN term {term.id} failed entirely: {exc}")
    print(f"[pipeline] Collected {len(flat_search_results)} search results.")

    # --- Orchestrator ---
    print("[pipeline] Running orchestrator analysis...")
    analysis = await run_orchestrator(
        run_id=run_id,
        model_results=flat_model_results,
        search_results=flat_search_results,
        competitor_config=competitors.model_dump(),
        prompts=[p.model_dump() for p in prompt_set.prompts],
        terms=[t.model_dump() for t in term_set.terms],
    )

    # --- Persist & Output ---
    await s.save_analysis_result(run_id, analysis)

    report_path = Path(output_dir) / f"report_{run_id}.json"
    write_json_report(analysis, report_path)
    print(f"[pipeline] Report written to {report_path}")
    print_summary(analysis)

    return analysis


async def run_ad_hoc_query(
    query: str,
    competitors: CompetitorConfig,
    output_dir: str | Path = "data",
    store: StoreProtocol | None = None,
) -> dict[str, Any]:
    """
    Run an ad-hoc query as both a prompt and search term.
    Useful for quick competitive snapshots.
    """
    prompt_set = PromptSet(
        prompt_set_id="adhoc",
        created_at=datetime.now(UTC).isoformat(),
        prompts=[
            Prompt(id="adhoc_p1", text=query, category="adhoc", expected_winner=competitors.target)
        ],
    )
    term_set = TermSet(
        term_set_id="adhoc",
        created_at=datetime.now(UTC).isoformat(),
        terms=[
            SearchTerm(
                id="adhoc_s1", query=query, category="adhoc", expected_winner=competitors.target
            )
        ],
    )
    return await run_full_pipeline(prompt_set, term_set, competitors, output_dir, store=store)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


async def _run_and_store_models(
    store: StoreProtocol, run_id: str, prompt: Prompt
) -> list[dict[str, Any]]:
    results = await run_all_models(prompt.id, prompt.text)
    for r in results:
        await store.save_model_result(
            run_id=run_id,
            prompt_id=r["prompt_id"],
            prompt_text=prompt.text,
            model=r["model"],
            raw_response=r["raw_response"],
            latency_ms=r.get("latency_ms"),
        )
    return results


async def _run_and_store_searches(
    store: StoreProtocol,
    run_id: str,
    term: SearchTerm,
    *,
    session: Any = None,
) -> list[dict[str, Any]]:
    results = await run_all_searches(term.id, term.query, session=session)
    for r in results:
        await store.save_search_result(
            run_id=run_id,
            term_id=r["term_id"],
            query=term.query,
            engine=r["engine"],
            results=r["results"],
            status=r.get("status", "ok"),
            error=r.get("error"),
        )
    return results
