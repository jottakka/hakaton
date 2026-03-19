"""RunGeoSiteAudit pipeline — evidence collection + LLM analysis + claim validation.

The full audit happens in three deterministic-then-reasoning steps:

1. collect_geo_evidence()  — HTTP fetching, fully deterministic, no LLM
2. Anthropic messages.create() — LLM analysis with evidence pre-loaded in context
3. validate_claims()       — deterministic regex/fact check against the same evidence

The caller receives the complete structured report in one call.
No tool-call orchestration required on the caller's side.
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from typing import Any

import anthropic

from ..models import CollectGeoEvidenceResult
from ..validation import validate_claims
from .collect_geo_evidence import collect_geo_evidence

_DEFAULT_MODEL = "claude-sonnet-4-6"

_SYSTEM_PROMPT = """\
You are a GEO (Generative Engine Optimization) auditor. You will receive structured \
evidence JSON collected deterministically from a target website. Your job is to \
analyse this evidence and produce a structured audit report.

The evidence includes: artifact checks (robots.txt, sitemap.xml, llms.txt, \
llms-full.txt), page metadata, JSON-LD structured data, heading hierarchies, \
title/H1 comparisons, and first-200-word extracts.

Do NOT call any tools. All the data you need is in the user message.

## Scoring

Score the site across four GEO levers (each 0–25, overall = sum):

| Lever | Key | What it measures |
|-------|-----|-----------------|
| 1 | content_structure | Heading hierarchy, JSON-LD markup, extractable prose |
| 2 | entity_authority | Named entities, schema.org types, authorship signals |
| 3 | technical | robots.txt, sitemaps, llms.txt, llms-full.txt, canonicals |
| 4 | citation | Quotable claims, FAQ-style content, high-confidence facts |

For each lever provide: score (0–25), 3–5 strengths with evidence, 3–5 weaknesses \
with evidence, confidence (high/medium/low), concrete recommendations.

## Required output

Return ONLY a single JSON object with these top-level fields:

```
target_url      string   — the audited URL
overall_score   integer  — sum of lever scores (0–100)
claims          array    — one item per lever (lever, lever_name, score, strengths,
                           weaknesses, confidence, recommendations)
evidence        array    — summary of key evidence items used
report_markdown string   — full human-readable audit report in Markdown
```

Do not write any files. Do not call any tools. Return only the JSON object.
Base every claim on the provided evidence. Do not hallucinate scores or findings.
"""

_LEVER_NAMES = {
    1: "Content structure and extractability",
    2: "Entity authority",
    3: "Technical accessibility",
    4: "Citation-worthiness",
}


def _get_model() -> str:
    return os.environ.get("GEO_AUDIT_MODEL", _DEFAULT_MODEL)


def _extract_json(text: str) -> dict[str, Any]:
    """Extract a JSON object from the model response, tolerating markdown fences."""
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
    target_url: str, audit_mode: str, evidence: CollectGeoEvidenceResult
) -> str:
    return (
        f"Audit target: {target_url}\n"
        f"Audit mode: {audit_mode}\n\n"
        "## Evidence JSON\n\n"
        "```json\n" + evidence.model_dump_json(indent=2) + "\n```\n\n"
        "Analyse the evidence above and return a single JSON object conforming to "
        "the output schema in the system prompt."
    )


async def run_geo_audit(
    target_url: str,
    audit_mode: str = "exhaustive",
    coverage_preset: str = "exhaustive",
    discover_subdomains: bool = True,
) -> dict[str, Any]:
    """Run a complete single-site GEO audit.

    Steps (all internal, no tool calls needed from the caller):
      1. Collect deterministic evidence via HTTP.
      2. Pass evidence to Claude for scoring and report generation.
      3. Validate the draft report claims against the same evidence.

    Args:
        target_url: The site to audit (e.g. "https://arcade.dev").
        audit_mode: "exhaustive" (default), "standard", or "quick".
        coverage_preset: Passed to CollectGeoEvidence ("exhaustive", "deep",
            "standard", or "light").
        discover_subdomains: Whether to discover additional subdomains.

    Returns:
        Structured audit result dict with target_url, overall_score, claims,
        evidence, report_markdown, and a validation key with any findings.
    """
    # Step 1 — deterministic evidence collection
    evidence = await collect_geo_evidence(
        target_urls=[target_url],
        coverage_preset=coverage_preset,
        discover_subdomains=discover_subdomains,
    )

    # Step 2 — LLM analysis (evidence pre-loaded, no tool calls)
    client = anthropic.AsyncAnthropic()
    user_message = _build_user_message(target_url, audit_mode, evidence)

    message = await client.messages.create(
        model=_get_model(),
        max_tokens=8192,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    result_text = message.content[0].text
    result = _extract_json(result_text)

    # Step 3 — deterministic claim validation
    validation = validate_claims(
        draft_report=result.get("report_markdown", result_text),
        evidence=evidence,
    )
    result["validation"] = json.loads(validation.model_dump_json(by_alias=True))
    result["run_timestamp"] = datetime.now(UTC).isoformat()

    return result
