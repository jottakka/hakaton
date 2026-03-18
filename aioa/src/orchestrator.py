"""Orchestration Layer — Batched parallel subagents with deterministic scoring.

Architecture:
    1. batch_items()          — partition prompts/terms into ~20-item batches
    2. run_subagent()         — score each batch (deterministic) + get LLM observations
    3. merge_subagent_results — combine all batches into unified scored report
    4. run_synthesis()        — single LLM call for narrative summary + recommendations
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any

import anthropic
from dotenv import load_dotenv

from src.skills.competitor_comparison import build_comparison_matrix
from src.skills.gap_analysis import find_gaps
from src.skills.mention_detection import detect_mentions
from src.skills.rank_extraction import extract_rankings
from src.skills.score_calculation import (
    calculate_aio_score,
    calculate_seo_score,
    load_scoring_matrix,
)

load_dotenv()

_SUBAGENT_MODEL = "claude-sonnet-4-6"
_SYNTHESIS_MODEL = "claude-sonnet-4-6"
_BATCH_SIZE = 20


def _extract_results(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize the results key across live pipeline records ('results')
    and store-loaded records ('results_json')."""
    raw = record.get("results", record.get("results_json", []))
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = []
    return raw if isinstance(raw, list) else []


# ---------------------------------------------------------------------------
# Batching
# ---------------------------------------------------------------------------


def batch_items(
    prompts: list[dict[str, Any]],
    model_results: list[dict[str, Any]],
    terms: list[dict[str, Any]],
    search_results: list[dict[str, Any]],
    batch_size: int = _BATCH_SIZE,
) -> list[dict[str, Any]]:
    """Split prompts and terms into batches, each with its associated raw results.

    Returns a list of batch dicts:
        {
            "prompts": [...],
            "model_results": [...],   # only results for prompts in this batch
            "terms": [...],
            "search_results": [...],  # only results for terms in this batch
        }
    """
    model_by_prompt: dict[str, list[dict]] = {}
    for mr in model_results:
        model_by_prompt.setdefault(mr["prompt_id"], []).append(mr)

    search_by_term: dict[str, list[dict]] = {}
    for sr in search_results:
        search_by_term.setdefault(sr["term_id"], []).append(sr)

    prompt_batches: list[tuple[list, list]] = []
    for i in range(0, len(prompts), batch_size):
        bp = prompts[i : i + batch_size]
        bm = []
        for p in bp:
            bm.extend(model_by_prompt.get(p["id"], []))
        prompt_batches.append((bp, bm))

    term_batches: list[tuple[list, list]] = []
    for i in range(0, len(terms), batch_size):
        bt = terms[i : i + batch_size]
        bs = []
        for t in bt:
            bs.extend(search_by_term.get(t["id"], []))
        term_batches.append((bt, bs))

    batches: list[dict[str, Any]] = []
    max_len = max(len(prompt_batches), len(term_batches))
    for i in range(max_len):
        bp, bm = prompt_batches[i] if i < len(prompt_batches) else ([], [])
        bt, bs = term_batches[i] if i < len(term_batches) else ([], [])
        batches.append(
            {
                "prompts": bp,
                "model_results": bm,
                "terms": bt,
                "search_results": bs,
            }
        )

    return batches


# ---------------------------------------------------------------------------
# Subagent — deterministic scoring + LLM observations
# ---------------------------------------------------------------------------

SUBAGENT_SYSTEM = """\
You are a competitive intelligence analyst. You will be given:
1. Scored mention data for LLM responses (which companies were mentioned, where, sentiment).
2. Scored ranking data for search results (which companies appeared and at what position).
3. The raw LLM response text (truncated).

For each prompt or search term, write a brief 1-2 sentence observation summarizing:
- Which companies were mentioned or ranked and how.
- Any notable patterns (e.g., a company being recommended first, or being absent despite relevance).

Return ONLY valid JSON matching this schema (no markdown fences):
{
  "observations": {
    "<prompt_id or term_id>": "<observation text>"
  }
}
"""


async def run_subagent(
    batch: dict[str, Any],
    target: str,
    competitors: list[str],
    matrix: dict[str, Any],
) -> dict[str, Any]:
    """Process a single batch: deterministic scoring + LLM observations.

    Returns:
        {
            "aio_results": [{prompt_id, by_model, aggregate, ...}, ...],
            "seo_results": [{term_id, by_engine, aggregate, ...}, ...],
            "observations": {id: text, ...},
        }
    """
    aio_results = _score_aio_batch(batch, target, competitors, matrix)
    seo_results = _score_seo_batch(batch, target, competitors, matrix)

    observations = await _get_observations(batch, aio_results, seo_results, target, competitors)

    return {
        "aio_results": aio_results,
        "seo_results": seo_results,
        "observations": observations,
    }


def _score_aio_batch(
    batch: dict[str, Any],
    target: str,
    competitors: list[str],
    matrix: dict[str, Any],
) -> list[dict[str, Any]]:
    """Run mention detection + AIO scoring for all prompts in the batch."""
    model_by_prompt: dict[str, list[dict]] = {}
    for mr in batch["model_results"]:
        model_by_prompt.setdefault(mr["prompt_id"], []).append(mr)

    results = []
    for prompt in batch["prompts"]:
        pid = prompt["id"]
        prompt_models = model_by_prompt.get(pid, [])

        mentions_by_model: dict[str, dict[str, Any]] = {}
        by_model_scores: dict[str, dict[str, int]] = {}

        for mr in prompt_models:
            model_name = mr["model"]
            mentions = detect_mentions(mr["raw_response"], target, competitors)
            mentions_by_model[model_name] = mentions
            by_model_scores[model_name] = {
                company: calculate_aio_score(m, matrix=matrix) for company, m in mentions.items()
            }

        all_companies = [target] + competitors
        aggregate: dict[str, int] = {}
        for company in all_companies:
            scores = [by_model_scores[m].get(company, 0) for m in by_model_scores]
            aggregate[company] = round(sum(scores) / max(len(scores), 1)) if scores else 0

        results.append(
            {
                "prompt_id": pid,
                "prompt_text": prompt.get("text", ""),
                "category": prompt.get("category", ""),
                "expected_winner": prompt.get("expected_winner", target),
                "by_model": {
                    model_name: {
                        "mentions": mentions_by_model.get(model_name, {}),
                        "scores": by_model_scores.get(model_name, {}),
                    }
                    for model_name in by_model_scores
                },
                "aggregate_score": aggregate,
            }
        )

    return results


def _score_seo_batch(
    batch: dict[str, Any],
    target: str,
    competitors: list[str],
    matrix: dict[str, Any],
) -> list[dict[str, Any]]:
    """Run rank extraction + SEO scoring for all terms in the batch."""
    search_by_term: dict[str, list[dict]] = {}
    for sr in batch["search_results"]:
        search_by_term.setdefault(sr["term_id"], []).append(sr)

    results = []
    for term in batch["terms"]:
        tid = term["id"]
        term_searches = search_by_term.get(tid, [])

        ok_searches = [sr for sr in term_searches if sr.get("status", "ok") == "ok"]
        failed_engines = [sr["engine"] for sr in term_searches if sr.get("status") == "failed"]

        if not ok_searches and failed_engines:
            term_status = "failed"
        elif failed_engines:
            term_status = "partial"
        else:
            term_status = "ok"

        if term_status == "failed":
            results.append(
                {
                    "term_id": tid,
                    "query": term.get("query", ""),
                    "category": term.get("category", ""),
                    "expected_winner": term.get("expected_winner", target),
                    "by_engine": {},
                    "aggregate_score": None,
                    "status": "failed",
                    "failed_engines": failed_engines,
                }
            )
            continue

        rankings_by_engine: dict[str, dict[str, Any]] = {}
        by_engine_scores: dict[str, dict[str, int]] = {}

        for sr in ok_searches:
            engine = sr["engine"]
            raw_results = _extract_results(sr)

            rankings = extract_rankings(raw_results, target, competitors)
            rankings_by_engine[engine] = rankings
            by_engine_scores[engine] = {
                company: calculate_seo_score(r, matrix=matrix) for company, r in rankings.items()
            }

        all_companies = [target] + competitors
        aggregate: dict[str, int] = {}
        for company in all_companies:
            scores = [by_engine_scores[e].get(company, 0) for e in by_engine_scores]
            aggregate[company] = round(sum(scores) / max(len(scores), 1)) if scores else 0

        result_entry: dict[str, Any] = {
            "term_id": tid,
            "query": term.get("query", ""),
            "category": term.get("category", ""),
            "expected_winner": term.get("expected_winner", target),
            "by_engine": {
                engine: {
                    "rankings": rankings_by_engine.get(engine, {}),
                    "scores": by_engine_scores.get(engine, {}),
                }
                for engine in by_engine_scores
            },
            "aggregate_score": aggregate,
            "status": term_status,
        }
        if failed_engines:
            result_entry["failed_engines"] = failed_engines
        results.append(result_entry)

    return results


async def _get_observations(
    batch: dict[str, Any],
    aio_results: list[dict[str, Any]],
    seo_results: list[dict[str, Any]],
    target: str,
    competitors: list[str],
) -> dict[str, str]:
    """Call Claude Opus to generate brief observations for each item in the batch."""
    sections = []

    sections.append(f"Target: {target}")
    sections.append(f"Competitors: {', '.join(competitors)}\n")

    _MAX_RESPONSE_CHARS = 800
    for aio in aio_results:
        pid = aio["prompt_id"]
        sections.append(f'### Prompt {pid}: "{aio["prompt_text"]}"')
        sections.append(f"Scores: {json.dumps(aio['aggregate_score'])}")
        for mr in batch["model_results"]:
            if mr["prompt_id"] == pid:
                text = mr["raw_response"][:_MAX_RESPONSE_CHARS]
                sections.append(f"[{mr['model']}]: {text}")
        sections.append("")

    for seo in seo_results:
        if seo.get("status") == "failed":
            continue
        tid = seo["term_id"]
        sections.append(f'### Term {tid}: "{seo["query"]}"')
        sections.append(f"Scores: {json.dumps(seo['aggregate_score'])}")
        for sr in batch["search_results"]:
            if sr["term_id"] == tid and sr.get("status", "ok") == "ok":
                raw = _extract_results(sr)
                top3 = [{"pos": r.get("position"), "title": r.get("title", "")} for r in raw[:3]]
                if top3:
                    sections.append(f"[{sr['engine']}] top3: {json.dumps(top3)}")
        sections.append("")

    user_message = "\n".join(sections)

    try:
        client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        response = await client.messages.create(
            model=_SUBAGENT_MODEL,
            max_tokens=4096,
            system=SUBAGENT_SYSTEM,
            messages=[{"role": "user", "content": user_message}],
        )
        raw_text = response.content[0].text if response.content else "{}"
        json_text = raw_text.strip()
        if json_text.startswith("```"):
            lines = json_text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            json_text = "\n".join(lines)
        parsed = json.loads(json_text)
        return parsed.get("observations", {})
    except Exception as exc:
        print(f"[orchestrator] WARN subagent observations failed: {exc}")
        return {}


# ---------------------------------------------------------------------------
# Merger — deterministic aggregation
# ---------------------------------------------------------------------------


def merge_subagent_results(
    subagent_outputs: list[dict[str, Any]],
    target: str,
    competitors: list[str],
) -> dict[str, Any]:
    """Merge all subagent outputs into a unified scored report.

    Returns the full analysis dict (everything except narrative summary).
    """
    all_aio: list[dict[str, Any]] = []
    all_seo: list[dict[str, Any]] = []
    all_observations: dict[str, str] = {}

    for output in subagent_outputs:
        all_aio.extend(output.get("aio_results", []))
        all_seo.extend(output.get("seo_results", []))
        all_observations.update(output.get("observations", {}))

    for item in all_aio:
        item["observations"] = all_observations.get(item["prompt_id"], "")
    for item in all_seo:
        item["observations"] = all_observations.get(item["term_id"], "")

    aio_aggregates = [item["aggregate_score"] for item in all_aio]
    seo_ok = [item for item in all_seo if item.get("status", "ok") != "failed"]
    seo_aggregates = [
        item["aggregate_score"] for item in seo_ok if item["aggregate_score"] is not None
    ]
    comparison = build_comparison_matrix(aio_aggregates, seo_aggregates, target, competitors)

    scored_items = []
    for item in all_aio:
        scored_items.append(
            {
                "id": item["prompt_id"],
                "type": "aio",
                "text": item.get("prompt_text", ""),
                "expected_winner": item.get("expected_winner", target),
                "aggregate": item["aggregate_score"],
            }
        )
    for item in seo_ok:
        scored_items.append(
            {
                "id": item["term_id"],
                "type": "seo",
                "text": item.get("query", ""),
                "expected_winner": item.get("expected_winner", target),
                "aggregate": item["aggregate_score"],
            }
        )

    gaps = find_gaps(scored_items, target)

    return {
        "aio_results": all_aio,
        "seo_results": all_seo,
        "gap_report": gaps,
        "comparison_matrix": comparison,
    }


# ---------------------------------------------------------------------------
# Synthesis — LLM narrative from small scored payload
# ---------------------------------------------------------------------------

SYNTHESIS_SYSTEM = """\
You are a competitive intelligence analyst. You are given aggregated scoring data, a gap report, and a comparison matrix from a competitive SEO analysis (and optionally AIO/LLM analysis).

Write a concise JSON response with:
1. A summary object with overall insights.
2. A recommendation string for each gap.

If AIO data is not present, set arcade_avg_aio_score to null.

Return ONLY valid JSON (no markdown fences):
{
  "summary": {
    "arcade_avg_aio_score": <int or null>,
    "arcade_avg_seo_score": <int>,
    "top_competitor": "<name>",
    "biggest_gap": "<1-2 sentence description of the most critical gap>"
  },
  "gap_recommendations": {
    "<gap_id>": "<1-2 sentence actionable recommendation>"
  }
}
"""


async def run_synthesis(
    merged: dict[str, Any],
    target: str,
    competitors: list[str],
) -> dict[str, str]:
    """Final LLM call: generate narrative summary + recommendations from scored data."""
    comparison = merged.get("comparison_matrix", {})
    gaps = merged.get("gap_report", [])

    user_message_parts = [
        f"Target: {target}",
        f"Competitors: {', '.join(competitors)}\n",
        "## Comparison Matrix",
        json.dumps(comparison, indent=2),
        "\n## Gap Report",
        json.dumps(gaps, indent=2),
    ]
    user_message = "\n".join(user_message_parts)

    try:
        client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        response = await client.messages.create(
            model=_SYNTHESIS_MODEL,
            max_tokens=4096,
            system=SYNTHESIS_SYSTEM,
            messages=[{"role": "user", "content": user_message}],
        )
        raw_text = response.content[0].text if response.content else "{}"
        json_text = raw_text.strip()
        if json_text.startswith("```"):
            lines = json_text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            json_text = "\n".join(lines)
        return json.loads(json_text)
    except Exception as exc:
        print(f"[orchestrator] WARN synthesis failed: {exc}")
        aio_scores = comparison.get("aio_avg_scores", {})
        aio_fallback = aio_scores.get(target) if aio_scores.get(target) else None
        return {
            "summary": {
                "arcade_avg_aio_score": aio_fallback,
                "arcade_avg_seo_score": comparison.get("seo_avg_scores", {}).get(target, 0),
                "top_competitor": "",
                "biggest_gap": "Synthesis failed — see gap_report for details.",
            },
            "gap_recommendations": {},
        }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run_orchestrator(
    run_id: str,
    model_results: list[dict[str, Any]],
    search_results: list[dict[str, Any]],
    competitor_config: dict[str, Any],
    prompts: list[dict[str, Any]],
    terms: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Run the full orchestration pipeline:
    1. Batch items
    2. Run parallel subagents (deterministic scoring + LLM observations)
    3. Merge results deterministically
    4. Run LLM synthesis for narrative summary
    """
    target = competitor_config.get("target", "Arcade")
    competitors = competitor_config.get("competitors", [])
    matrix = load_scoring_matrix()

    run_mode = "seo_only" if not model_results else "full"

    batches = batch_items(prompts, model_results, terms, search_results)
    print(f"[orchestrator] Created {len(batches)} batches (mode={run_mode})")

    subagent_tasks = [run_subagent(batch, target, competitors, matrix) for batch in batches]
    subagent_outputs = await asyncio.gather(*subagent_tasks)
    print(f"[orchestrator] All {len(subagent_outputs)} subagents complete")

    merged = merge_subagent_results(list(subagent_outputs), target, competitors)

    synthesis = await run_synthesis(merged, target, competitors)
    print("[orchestrator] Synthesis complete")

    summary = synthesis.get("summary", {})
    gap_recs = synthesis.get("gap_recommendations", {})

    for gap in merged["gap_report"]:
        rec = gap_recs.get(gap["id"], "")
        if rec:
            gap["recommendation"] = rec

    if run_mode == "seo_only" and summary.get("arcade_avg_aio_score") is not None:
        summary["arcade_avg_aio_score"] = None

    analysis = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_mode": run_mode,
        "summary": summary,
        "aio_results": merged["aio_results"],
        "seo_results": merged["seo_results"],
        "gap_report": merged["gap_report"],
        "comparison_matrix": merged["comparison_matrix"],
    }

    return analysis
