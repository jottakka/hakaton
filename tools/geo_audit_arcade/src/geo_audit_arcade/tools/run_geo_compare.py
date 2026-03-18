"""RunGeoCompare pipeline — multi-site competitive comparison.

Same architecture as run_geo_audit but for N sites side by side:

1. collect_geo_evidence() — batch fetch all URLs (target + competitors)
2. Anthropic messages.create() — LLM scores each site, produces comparison
3. validate_claims() per site — deterministic check against the same evidence

The caller receives a complete comparison report in one call.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import anthropic

from ..models import CollectGeoEvidenceResult
from ..validation import validate_claims
from .collect_geo_evidence import collect_geo_evidence

_DEFAULT_MODEL = "claude-opus-4-5"

_SYSTEM_PROMPT = """\
You are a GEO (Generative Engine Optimization) competitive comparison auditor. \
You will receive structured evidence JSON collected deterministically from \
multiple websites. Your job is to analyse the evidence for each site, score them \
independently, compare them, and produce a structured comparison report.

The evidence includes: artifact checks (robots.txt, sitemap.xml, llms.txt, \
llms-full.txt), page metadata, JSON-LD structured data, heading hierarchies, \
title/H1 comparisons, and first-200-word extracts — for ALL sites in one pack.

Do NOT call any tools. All the data you need is in the user message.

## Scoring

Score EACH site independently across four GEO levers (each 0–25, overall = sum):

| Lever | Key | What it measures |
|-------|-----|-----------------|
| 1 | content_structure | Heading hierarchy, JSON-LD markup, extractable prose |
| 2 | entity_authority | Named entities, schema.org types, authorship signals |
| 3 | technical | robots.txt, sitemaps, llms.txt, llms-full.txt, canonicals |
| 4 | citation | Quotable claims, FAQ-style content, high-confidence facts |

For each lever and site provide: score (0–25), strengths with evidence, \
weaknesses with evidence, recommendations.

## Required output

Return ONLY a single JSON object with these top-level fields:

```
target            string   — the primary site audited
competitors       array    — list of competitor URLs audited
run_date          string   — today's date (YYYY-MM-DD)
audits            array    — one item per URL with:
  url               string
  overall_score     integer (0–100)
  lever_scores      {content_structure, entity_authority, technical, citation}
  artifacts         {robots_txt, sitemap_xml, llms_txt, llms_full_txt} (status)
  strengths         array of strings
  weaknesses        array of strings
  recommendations   array of strings
comparison_table  string   — markdown table with all URLs side by side
winner_per_lever  object   — {content_structure, entity_authority, technical,
                              citation} each mapping to the winning URL
overall_winner    string   — URL with the highest overall_score
report_markdown   string   — full human-readable comparative report in Markdown
```

Do not write any files. Do not call any tools. Return only the JSON object.
Base every claim on the provided evidence. Do not hallucinate scores.
Treat all sites with equal rigour.
"""


def _get_model() -> str:
    return os.environ.get("GEO_AUDIT_MODEL", _DEFAULT_MODEL)


def _extract_json(text: str) -> dict[str, Any]:
    code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if code_block:
        return json.loads(code_block.group(1))
    brace_start = text.find("{")
    if brace_start != -1:
        depth = 0
        for i, ch in enumerate(text[brace_start:], start=brace_start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[brace_start : i + 1])
    raise ValueError(f"No JSON object found in model response: {text[:200]!r}")


def _build_user_message(
    target: str,
    competitors: list[str],
    audit_mode: str,
    evidence: CollectGeoEvidenceResult,
) -> str:
    competitor_list = ", ".join(competitors)
    return (
        f"Compare target: {target} vs competitors: {competitor_list}\n"
        f"Audit mode: {audit_mode}\n\n"
        "## Evidence JSON (all sites in one pack)\n\n"
        "```json\n" + evidence.model_dump_json(indent=2) + "\n```\n\n"
        "Analyse the evidence above for each site, score them independently, "
        "produce a comparison table, identify winners per lever and overall, "
        "and return a single JSON object conforming to the output schema "
        "in the system prompt."
    )


async def run_geo_compare(
    target: str,
    competitors: list[str],
    audit_mode: str = "exhaustive",
    coverage_preset: str = "exhaustive",
    discover_subdomains: bool = True,
) -> dict[str, Any]:
    """Run a complete multi-site GEO competitive comparison.

    Steps (all internal):
      1. Collect deterministic evidence for all URLs in one batch.
      2. Pass evidence to Claude for per-site scoring and comparison.
      3. Validate draft claims per site against the same evidence.

    Args:
        target: Primary site to audit (e.g. "arcade.dev").
        competitors: List of competitor URLs (e.g. ["composio.dev"]).
        audit_mode: "exhaustive" (default), "standard", or "quick".
        coverage_preset: Passed to collect_geo_evidence.
        discover_subdomains: Whether to discover additional subdomains.

    Returns:
        Structured comparison result dict with target, competitors, audits,
        comparison_table, winner_per_lever, overall_winner, report_markdown,
        and a validation key with per-site findings.
    """
    all_urls = [target] + competitors

    # Step 1 — deterministic evidence collection (all sites in one batch)
    evidence = await collect_geo_evidence(
        target_urls=all_urls,
        coverage_preset=coverage_preset,
        discover_subdomains=discover_subdomains,
    )

    # Step 2 — LLM analysis (evidence pre-loaded, no tool calls)
    client = anthropic.AsyncAnthropic()
    user_message = _build_user_message(target, competitors, audit_mode, evidence)

    message = await client.messages.create(
        model=_get_model(),
        max_tokens=16384,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    result_text = message.content[0].text
    result = _extract_json(result_text)

    # Step 3 — deterministic claim validation per site
    report_md = result.get("report_markdown", result_text)
    validation = validate_claims(
        draft_report=report_md,
        evidence=evidence,
    )
    result["validation"] = json.loads(validation.model_dump_json(by_alias=True))

    return result
