"""Output Layer — Report generation (JSON file + human-readable summary)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json_report(analysis: dict[str, Any], output_path: str | Path) -> Path:
    """Write the full analysis to a JSON file and return the path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def print_summary(analysis: dict[str, Any]) -> None:
    """Print a human-readable summary of the analysis to stdout."""
    run_id = analysis.get("run_id", "unknown")
    generated_at = analysis.get("generated_at", "unknown")
    summary = analysis.get("summary", {})

    run_mode = analysis.get("run_mode", "full")
    mode_label = "SEO-only" if run_mode == "seo_only" else "Full"

    print("\n" + "=" * 70)
    print(f"  AIO ANALYZER — Competitive Visibility Report")
    print(f"  Run ID:     {run_id}")
    print(f"  Generated:  {generated_at}")
    print(f"  Run Mode:  {mode_label}")
    print("=" * 70)

    if summary:
        aio_score = summary.get("arcade_avg_aio_score")
        if aio_score is not None:
            print(f"\n  Arcade Avg AIO Score:  {aio_score}/100")
        print(f"\n  Arcade Avg SEO Score:  {summary.get('arcade_avg_seo_score', 'N/A')}/100")
        print(f"  Top Competitor:        {summary.get('top_competitor', 'N/A')}")
        print(f"  Biggest Gap:           {summary.get('biggest_gap', 'N/A')}")

    # AIO results summary
    aio_results = analysis.get("aio_results", [])
    if aio_results:
        print(f"\n{'─' * 70}")
        print(f"  AIO Results ({len(aio_results)} prompts)")
        print(f"{'─' * 70}")
        for r in aio_results:
            prompt_text = r.get("prompt_text", r.get("text", ""))
            agg = r.get("aggregate_score", {})
            print(f"\n  [{r.get('prompt_id', '?')}] {prompt_text}")
            if agg:
                sorted_scores = sorted(agg.items(), key=lambda x: x[1], reverse=True)
                for company, score in sorted_scores:
                    bar = _bar(score)
                    print(f"    {company:<20} {bar} {score}")
            obs = r.get("observations", "")
            if obs:
                print(f"    >> {obs}")

    # SEO results summary
    seo_results = analysis.get("seo_results", [])
    if seo_results:
        print(f"\n{'─' * 70}")
        print(f"  SEO Results ({len(seo_results)} terms)")
        print(f"{'─' * 70}")
        for r in seo_results:
            query = r.get("query", r.get("text", ""))
            agg = r.get("aggregate_score") or {}
            status = r.get("status", "ok")
            print(f"\n  [{r.get('term_id', '?')}] {query}")
            if status == "failed":
                engines = r.get("failed_engines", [])
                print(f"    FAILED — engines: {', '.join(engines) if engines else 'unknown'}")
            elif agg:
                sorted_scores = sorted(agg.items(), key=lambda x: x[1], reverse=True)
                for company, score in sorted_scores:
                    bar = _bar(score)
                    print(f"    {company:<20} {bar} {score}")
            obs = r.get("observations", "")
            if obs:
                print(f"    >> {obs}")

    # Search collection warnings
    failed_terms = [r for r in seo_results if r.get("status") == "failed"]
    partial_terms = [r for r in seo_results if r.get("status") == "partial"]
    if failed_terms or partial_terms:
        print(f"\n{'─' * 70}")
        print(f"  ⚠ Incomplete Search Collection")
        print(f"{'─' * 70}")
        if failed_terms:
            print(f"    {len(failed_terms)} term(s) fully failed (excluded from scoring)")
        if partial_terms:
            print(f"    {len(partial_terms)} term(s) partially failed (scored with available engines)")

    # Gap report
    gaps = analysis.get("gap_report", [])
    if gaps:
        print(f"\n{'─' * 70}")
        print(f"  Gap Report ({len(gaps)} gaps identified)")
        print(f"{'─' * 70}")
        for g in gaps:
            print(f"\n  [{g.get('id', '?')}] {g.get('text', '')}")
            print(f"    Type: {g.get('type', '?')} | Expected: {g.get('expected', '?')} | Actual Winner: {g.get('actual_winner', '?')}")
            print(f"    Arcade Score: {g.get('arcade_score', '?')} | Winner Score: {g.get('winner_score', '?')}")
            rec = g.get("recommendation", "")
            if rec:
                print(f"    Recommendation: {rec}")

    # Handle parse errors or raw text fallback
    if "parse_error" in analysis:
        print(f"\n  WARNING: {analysis['parse_error']}")
        raw = analysis.get("raw_analysis_text", "")
        if raw:
            print(f"\n  Raw orchestrator output:\n  {raw[:500]}")

    print("\n" + "=" * 70 + "\n")


def _bar(score: int | None, width: int = 20) -> str:
    """Create a simple ASCII bar chart segment."""
    score = score or 0
    filled = round(score / 100 * width)
    return "[" + "#" * filled + "." * (width - filled) + "]"
