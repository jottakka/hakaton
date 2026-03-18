---
date: 2026-03-17
topic: geo-audit-deterministic-checks
---

# GEO Audit Deterministic Checks

## What We're Building

Add an always-on deterministic verification layer around the `geo-site-audit` workflow.

The deterministic layer should run through a small local MCP server built specifically for `geo-site-audit`, not as a general-purpose reusable web toolkit. The server should expose a small number of workflow-oriented tools rather than many tiny checks.

The purpose is to improve:

- consistency across repeated audit runs
- accuracy of hard technical claims
- traceability through machine-generated evidence artifacts

The LLM should still own synthesis, comparison, prioritization, and final scoring. The deterministic layer should own repeatable, machine-verifiable facts.

## Why This Approach

We considered three levels of rigor:

- evidence pack only
- evidence pack plus deterministic claim validator
- evidence pack plus validator plus heuristic score hints

The chosen direction is the middle option.

It strengthens the audit both before and after generation without turning the package into a brittle rules engine. This gives most of the value with much less maintenance than a heuristic scoring system.

We also decided the deterministic layer should run on every audit by default, not in a special strict mode. This makes the workflow more reliable without asking the user to remember a different invocation path.

## Key Decisions

- Use an always-on deterministic layer.
- Implement it as a local MCP server.
- Scope that server specifically to `geo-site-audit`.
- Expose bigger workflow tools, not many fine-grained utilities.
- Output deterministic results as structured JSON only.
- Keep scoring and synthesis model-driven.
- Add a post-generation deterministic claim validator.
- Do not implement heuristic score hints in the first version.
- If the local MCP server is unavailable, fall back gracefully to the current LLM-only path and lower confidence where appropriate.

## Proposed Tool Surface

- `CollectGeoEvidence`
  - Collect deterministic evidence for the audit target and selected sibling or child pages.
  - Return structured JSON covering:
    - HTTP status for `robots.txt`
    - HTTP status for `sitemap.xml`
    - sitemap URLs declared in `robots.txt`
    - `llms.txt` and `llms-full.txt` presence and status
    - title, meta description, canonical, Open Graph
    - heading extraction
    - JSON-LD presence and discovered `@type` values
    - title vs H1 comparison
    - first-200-words extraction

- `ValidateGeoAuditClaims`
  - Compare the draft audit output against the deterministic evidence JSON.
  - Return structured JSON covering:
    - contradictions
    - unsupported claims
    - missing high-signal facts
    - suggested confidence downgrades

## Expected Workflow

1. `geo-site-audit` starts by calling `CollectGeoEvidence`.
2. The model uses that JSON as the hard-fact evidence pack during scoring and synthesis.
3. The model drafts the normal GEO audit output.
4. The workflow calls `ValidateGeoAuditClaims` against the draft and evidence JSON.
5. If contradictions or unsupported claims are found, the model revises the audit before returning the final version.
6. If the local MCP server is unavailable, the workflow continues with the current LLM-only path and marks confidence more conservatively.

## Why Local MCP Is A Good Fit

Using a local MCP server keeps the deterministic layer callable as tools rather than as ad hoc scripts hidden inside the prompt flow.

That matches the intended Arcade MCP server model, where a local server can expose tools through normal MCP methods like tool listing and tool calls while remaining a low-level, controllable server surface. This is a good fit for a small, purpose-built verification layer rather than a standalone product surface.

## Resolved Questions

- Deterministic checks should improve consistency, accuracy, and traceability together.
- They should run on every audit by default.
- The first version should choose evidence collection plus claim validation, not full heuristic scoring.
- Results should be emitted as JSON, not Markdown.
- The local MCP server should be purpose-built for `geo-site-audit`.
- The tool surface should use bigger workflow tools with embedded check workflows.
- Fallback should be graceful rather than blocking the audit entirely.

## Open Questions

None currently.

## Next Steps

- Define the JSON schemas for `CollectGeoEvidence` and `ValidateGeoAuditClaims`
- Decide where evidence JSON should live during runs
- Decide how the skill prompt should require or prefer the deterministic tools
- Move to planning for implementation details
