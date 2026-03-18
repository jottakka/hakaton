---
date: 2026-03-17
topic: arcade-page-ranking-skills
---

# Arcade Page Ranking Skills

## What We're Building

Create a pair of Claude skills for internal Arcade page quality review during local development.

The skills are meant for people building or writing pages before publish. They should inspect local source files, identify what is missing or weak for search performance, and return practical suggestions that help improve ranking-oriented signals.

The output should be useful in chat for a human, but structured enough that it can later be plugged into a pipeline or automated content-review workflow.

## Why This Approach

We considered three directions:

- one page-first skill with project review later
- one unified skill with page mode and project mode
- two separate skills for page review and project review

The chosen direction is to split the workflows into separate skills.

This keeps each skill easier to understand and easier to invoke correctly. Page review and project review have overlapping rubrics, but they serve different scopes and failure modes. Splitting them should reduce noisy output and make future pipeline integration easier because each skill can have a tighter contract.

For sequencing, the page skill should be implemented first. It is the smaller, more frequent workflow and the best place to prove the rubric, output shape, and author experience before expanding into section or project review.

## Recommended Skill Set

### 1. `arcade-page-ranking-check`

Use this for one page or one local source file at a time.

Primary users:

- developers building a page
- content authors editing one page
- reviewers checking a single page before publish

Expected output:

- scorecard
- must-fix blockers
- broader suggestion list
- rationale tied to the checked page

### 2. `arcade-project-ranking-check`

Use this for a page project, page family, section, or group of related local files.

Primary users:

- developers working on a docs section
- marketers or writers updating a content cluster
- reviewers checking section-level consistency, coverage, and internal linking

Expected output:

- project-level scorecard
- section blockers
- cross-page pattern gaps
- broader project suggestions

This should be the second skill, after the page skill is working well and the shared rubric has been validated in real author workflows.

## Key Decisions

- Focus on local development first, not live deployed pages.
- Inspect source files first, not preview URLs.
- Keep the skills Arcade-focused rather than generic across any company.
- Optimize for human-readable output that is also structured enough for later pipeline use.
- Include both a scorecard and a small blocker list, not suggestions only.
- Explicitly score these ranking levers:
  - metadata
  - content structure
  - schema
  - crawlability and discovery
  - internal linking
  - keyword or query targeting
- Keep the two skills separate instead of using one overloaded dual-mode skill.
- Implement `arcade-page-ranking-check` first and treat `arcade-project-ranking-check` as the next sibling skill.

## Shared Rubric Direction

Both skills should evaluate the same core ranking dimensions, but at different scopes.

Page-level emphasis:

- title quality
- meta description quality
- canonical and OG basics
- H1 to H3 structure
- opening clarity
- schema presence
- link context inside the page
- topic or query clarity

Project-level emphasis:

- consistency across related pages
- internal link coverage
- missing navigational context
- duplicated or competing page topics
- section-level crawl or discovery gaps
- repeated template problems

## What These Skills Should Not Be

- not a full SEO platform
- not a keyword research engine
- not a live ranking tracker
- not a generic competitor-analysis skill
- not a GEO or LLM visibility audit clone

They should help Arcade teams improve ranking-oriented page quality before publish.

## Likely Package Shape

Keep the skills in separate folders so each one stays focused.

Suggested names:

- `arcade-page-ranking-check`
- `arcade-project-ranking-check`

Each skill can follow the same packaging pattern:

- `SKILL.md`
- `README.md`
- `QUICKREF.md`
- `rubric.md`
- `examples.md`

## Resolved Questions

- The skills are for Arcade pages.
- They should be used during local development.
- They should inspect source files first.
- They should return both a scorecard and a blocker list plus broader suggestions.
- They should check metadata, structure, schema, crawlability, internal linking, and keyword or topic clarity.
- They should be structured enough to plug into future pipelines.
- They should be split into separate page and project skills.

## Open Questions

None currently.

## Next Steps

- define the shared rubric shape
- write a concrete implementation plan for `arcade-page-ranking-check`
- reuse the validated rubric and output shape later for `arcade-project-ranking-check`
