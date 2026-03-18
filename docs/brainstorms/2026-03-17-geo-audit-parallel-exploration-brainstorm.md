---
date: 2026-03-17
topic: geo-audit-parallel-exploration
---

# GEO Audit Parallel Exploration

## What We're Building

Improve `geo-site-audit` so site exploration is much more thorough at discovering important pages, sections, and artifacts before scoring.

The exploration layer should stop depending mostly on shallow internal-link sampling and instead behave like a deliberate discovery pass that is trying to find what matters on a site. It should always run, but users should be able to choose how broad that pass becomes through simple named coverage presets.

## Why This Approach

We considered three directions:

- deterministic-first candidate discovery with one cheap ranking pass
- parallel-swarm exploration with multiple cheaper agents
- hybrid deterministic discovery plus targeted parallel agents

The chosen direction is the parallel-swarm approach.

This best matches the goal of "finding things" across sites that may hide important pages behind uneven navigation, weak hubs, or mixed subdomains. It also keeps the workflow easy to control: use cheaper models for exploration, then let the orchestrator merge and prioritize findings before final scoring.

## Key Decisions

- Replace the current single discovery lane with a parallel exploration swarm.
- Use cheaper models for exploration and keep the stronger synthesis step at the orchestrator and final audit layers.
- Run exploration on every audit, not only for broad or ambiguous targets.
- Let the user choose coverage with named presets only.
- Support these presets: `light`, `standard`, `deep`, and `exhaustive`.
- Default to `exhaustive` coverage when the user does not specify a preset.
- Keep every preset bounded. Even `exhaustive` should mean a much wider representative sweep, not an unbounded full-site crawl.
- Optimize the exploration layer for three failure modes: missed pages, bad representative samples, and shallow coverage across sections or subdomains.
- Keep the orchestrator responsible for deduplication, priority ranking, and deciding which findings actually influence the audit.

## Desired Exploration Shape

The swarm should explore the site through a few distinct discovery missions rather than one generic crawl.

Useful missions include:

- architecture discovery to identify major sections, hubs, and likely representative pages
- content discovery to find pages with strong answer-like structure, FAQs, comparisons, and list-style coverage
- proof discovery to find data-rich, source-heavy, or credibility-building pages
- technical discovery to find crawl, sitemap, schema, canonical, and AI-facing artifacts such as `llms.txt`

The point is not to fetch everything. The point is to make the search deliberately broad and better at surfacing the pages most likely to change the audit.

## Coverage Presets

- `light`: quick directional scan with limited discovery breadth
- `standard`: moderate coverage for routine checks
- `deep`: broad discovery for higher-confidence audits
- `exhaustive`: widest bounded sweep across sections, page types, and site signals

These presets should change exploration breadth without exposing a large set of low-level tuning knobs or implying a full crawl.

## Resolved Questions

- The exploration layer should be improved because the current flow can miss important pages, choose poor representatives, and stay too shallow across sections.
- Deeper exploration should run on every audit by default.
- The preferred overall direction is a parallel-swarm design rather than a deterministic-first or hybrid default.
- Users should be able to choose the level of coverage.
- Coverage control should use named presets only, not advanced controls.
- The default preset should be `exhaustive`.

## Open Questions

None currently.

## Next Steps

- define the missions in the swarm and what each one is responsible for finding
- decide what each coverage preset changes in practice
- define orchestration rules for merging, deduplicating, and prioritizing findings
- move to planning for implementation details
