# Arcade Page Ranking Check Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the first internal Claude skill for Arcade page authors and developers that reviews one local page source file, scores ranking-oriented quality, identifies must-fix blockers, and suggests specific improvements before publish.

**Architecture:** Create a new Claude skill package at `~/.claude/skills/arcade-page-ranking-check/`. Keep v1 source-file-first and page-first: inspect one page file plus the nearest adjacent metadata and layout context, then score six ranking levers and return blockers plus suggestions. Reuse the general packaging patterns from `geo-site-audit`, but do not reuse its live-site audit behavior, competitor framing, or Linear workflow.

**Tech Stack:** Claude skill markdown package, Markdown docs, local fixture files for validation, optional readonly subagent validation

---

### Task 1: Scaffold the skill package

**Files:**
- Create: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/SKILL.md`
- Create: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/README.md`
- Create: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/QUICKREF.md`
- Create: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/rubric.md`
- Create: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/examples.md`
- Create: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/source-patterns.md`
- Create: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/acceptance-cases.md`

**Step 1: Create the folder**

Create the skill directory and the seven files listed above.

**Step 2: Add minimal placeholders**

Each file should start with a one-line placeholder so nothing is empty while the package is being assembled.

**Step 3: Confirm the package layout exists**

Run: `ls "/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check"`

Expected: all seven files are present.

**Done when:**
- the skill has a dedicated folder
- the package shape matches the brainstorm

---

### Task 2: Write the acceptance cases first

**Files:**
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/acceptance-cases.md`
- Create: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/fixtures/missing-metadata-page.mdx`
- Create: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/fixtures/weak-structure-page.mdx`
- Create: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/fixtures/inherited-metadata-page.tsx`
- Create: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/fixtures/inherited-metadata-layout.tsx`
- Create: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/fixtures/strong-page.mdx`

**Step 1: Create fixture pages**

Create small local fixture files that represent the common page-review situations the skill must handle:
- missing metadata
- weak opening structure
- inherited metadata from layout
- a reasonably strong page

**Step 2: Write acceptance cases against those fixtures**

For each fixture, write:
- the prompt to run
- the expected score shape
- the expected blockers
- the expected suggestions
- what the skill must not do

**Step 3: Include at least these acceptance expectations**

- a page with no meaningful title or description produces a metadata blocker
- a page with weak opening clarity produces a structure blocker or high-priority suggestion
- a page with inherited metadata does not get falsely flagged as missing title or description if the nearby layout provides it
- a strong page still receives bounded suggestions instead of generic nitpicks
- the skill does not turn into a live-site audit or competitor-analysis flow

**Done when:**
- the skill has concrete “tests” before the docs are written
- later validation can be done against explicit expected behavior

---

### Task 3: Define the rubric and output contract

**Files:**
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/rubric.md`
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/README.md`

**Step 1: Define the six ranking levers**

Document these as the first-class review categories:
- metadata
- content structure
- schema
- crawlability and discovery
- internal linking
- keyword or query targeting

**Step 2: Give each lever clear anchors**

Use a `0-5` scale for each lever with plain-English anchors, then normalize the total score into `/100` for easier reading.

**Step 3: Define blocker rules**

Document what qualifies as a must-fix blocker, for example:
- missing or clearly weak page title
- missing or clearly weak meta description
- no clear H1 or broken heading structure
- no clear primary topic or query target
- missing canonical or OG basics when the page framework expects local metadata support
- no schema on page types where schema is clearly warranted

**Step 4: Define the required report shape**

The output should always include:
- summary
- scorecard
- must-fix blockers
- high-value suggestions
- assumptions or unresolved context

**Done when:**
- the rubric is specific enough to guide implementation
- the output shape is stable enough for future pipeline integration

---

### Task 4: Write the source-file inspection guide

**Files:**
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/source-patterns.md`

**Step 1: Document primary page file patterns**

Include the common local file patterns the skill should check first, such as:
- `page.mdx`
- `page.tsx`
- `page.jsx`
- `index.mdx`
- `index.tsx`

**Step 2: Document local metadata sources**

Explain how the skill should look for:
- frontmatter
- `metadata` export
- `generateMetadata`
- nearby `layout.*` files
- shared SEO helper components when obvious

**Step 3: Document local schema and linking cues**

Explain how the skill should inspect:
- inline JSON-LD
- schema helper components
- link clusters
- nearby navigation or index references when obvious

**Step 4: Document scope boundaries**

Make the file explicitly say:
- v1 is source-file-first
- do not require a local preview
- do not fetch live URLs by default
- if the user wants a live-page audit, that is a separate workflow

**Done when:**
- future agents know where to look in local source files
- the skill does not drift into the wrong audit surface

---

### Task 5: Write the main `SKILL.md`

**Files:**
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/SKILL.md`

**Step 1: Add frontmatter**

Use:
- `name: arcade-page-ranking-check`
- a description that clearly says it is for reviewing a local Arcade page source file for ranking-oriented gaps before publish

**Step 2: Write the quick-start workflow**

The quick-start should instruct the agent to:
- resolve the target page file
- inspect the nearest metadata and layout context
- build an evidence pack from local source
- score the six ranking levers
- return blockers and suggestions

**Step 3: Add clear “when not to use this” rules**

Include at least:
- not for live deployed page audits
- not for keyword research
- not for competitor comparison
- not for project-wide audits

**Step 4: Add the page-review workflow**

The workflow should explicitly cover:
- target resolution
- adjacent file inspection
- evidence collection
- score normalization
- blocker generation
- suggestion generation
- assumption handling when metadata is inherited or unclear

**Step 5: Add the required output template**

Keep it concise and stable. It should include:
- page summary
- scorecard
- must-fix blockers
- high-value suggestions
- assumptions

**Done when:**
- the main skill can be invoked directly and followed without needing the other files first

---

### Task 6: Write the supporting docs

**Files:**
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/README.md`
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/QUICKREF.md`
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/examples.md`

**Step 1: Write the README**

Cover:
- what the skill is for
- install path
- how to invoke it
- what inputs to give
- what outputs to expect
- what it does not cover

**Step 2: Write the quick reference**

Keep it to:
- invocation examples
- the six ranking levers
- blocker philosophy
- output structure

**Step 3: Write example prompts**

Include examples for:
- a single `page.mdx`
- a single `page.tsx`
- a page with inherited metadata
- a page with weak opening clarity

**Step 4: Keep the package focused**

Do not add project-mode instructions here. Mention the future sibling skill only briefly.

**Done when:**
- the package is usable without reading `SKILL.md` line by line
- examples reflect the real acceptance cases

---

### Task 7: Validate the skill against the acceptance cases

**Files:**
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/acceptance-cases.md`
- Modify as needed: all skill package files above

**Step 1: Run the skill mentally or with a readonly agent against each fixture prompt**

Check whether the expected blockers and suggestions appear.

**Step 2: Record mismatches**

For each mismatch, note:
- what the skill produced
- what the acceptance case expected
- whether the problem is rubric ambiguity, workflow ambiguity, or example ambiguity

**Step 3: Tighten the docs**

Fix the smallest thing that makes the behavior clearer:
- unclear rubric language
- missing inherited-metadata guidance
- vague blocker definition
- too-broad suggestions

**Step 4: Re-run the acceptance pass**

Repeat until the package behaves consistently on the fixtures.

**Done when:**
- the skill passes the authored acceptance cases
- the docs no longer encourage vague, generic SEO advice

---

### Task 8: Final cleanup and export-readiness pass

**Files:**
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/SKILL.md`
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/README.md`
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/QUICKREF.md`
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/rubric.md`
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/examples.md`
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/source-patterns.md`
- Modify: `/Users/franciscojuniodelimaliberal/.claude/skills/arcade-page-ranking-check/acceptance-cases.md`

**Step 1: Remove environment-specific wording**

Make sure the skill stays exportable and Claude-oriented, not tied to Cursor-only assumptions.

**Step 2: Remove scope creep**

Make sure the docs do not quietly introduce:
- project-mode review
- live URL review
- competitor analysis
- ranking promises

**Step 3: Add one brief note about the sibling skill**

Mention that `arcade-project-ranking-check` is planned next, but do not pull its behavior into this package.

**Step 4: Do one last quality pass**

Check for:
- repeated language
- vague wording like “consider” or “maybe” where a firmer instruction is possible
- output sections that do not match the rubric

**Done when:**
- the package is sharp, narrow, and exportable
- it is ready to serve as the base for later project-skill work

---

## Notes For The Implementer

- Keep this first skill page-first. Do not start building the project skill inside the same folder.
- Source-file inspection matters more than framework completeness in v1. Handle the common local patterns well instead of trying to support every possible build system.
- Prefer clear blockers over a long noisy suggestion list.
- If local evidence is incomplete because metadata is inherited or hidden in shared code, say so explicitly instead of hallucinating certainty.
- If a user gives a live URL instead of local files, the skill should redirect them to a more appropriate workflow rather than trying to do everything.
