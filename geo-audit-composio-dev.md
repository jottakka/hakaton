# GEO Audit: composio.dev

## Executive Summary
- **Overall score: 59/100** — just below the recommended threshold
- **Confidence: High** (all primary artifacts directly verified; minor uncertainty on JS-rendered homepage content)
- **LLM retrievability: Moderate.** The docs subdomain is well-instrumented for machine-readable access, but the primary marketing domain is extraction-hostile: no `llms.txt`, no JSON-LD, no FAQ, and a tagline-first homepage. Case studies and selected blog posts are genuinely citation-worthy, but they are buried behind a structurally weak surface layer.
- **Arcade priority: Add `llms.txt` to arcade.dev marketing domain and a homepage FAQ block — Composio's missing versions of these are Arcade's current advantage; consolidating that lead is low-effort and high-leverage.**

---

## Scope

**Targets:**
- https://composio.dev (primary)
- https://docs.composio.dev
- https://composio.dev/case-studies
- https://composio.dev/pricing
- https://composio.dev/enterprise
- https://composio.dev/blog (+ selected posts)
- https://composio.dev/content

**Site artifacts inspected:**

| Artifact | URL | Status |
|---|---|---|
| robots.txt (main) | composio.dev/robots.txt | 200 ✅ |
| sitemap.xml (main) | composio.dev/sitemap.xml | 200 ✅ (500+ entries) |
| sitemap-index.xml (main) | composio.dev/sitemap-index.xml | 404 ❌ |
| llms.txt (main) | composio.dev/llms.txt | 404 ❌ |
| llms-full.txt (main) | composio.dev/llms-full.txt | 404 ❌ |
| robots.txt (docs) | docs.composio.dev/robots.txt | 200 ✅ |
| sitemap.xml (docs) | docs.composio.dev/sitemap.xml | 200 ✅ (1,000+ entries) |
| llms.txt (docs) | docs.composio.dev/llms.txt | 200 ✅ (156 links, spec-compliant) |
| llms-full.txt (docs) | docs.composio.dev/llms-full.txt | 200 ✅ |

**Arcade benchmarks used:**
- https://www.arcade.dev/ (marketing homepage baseline)
- https://docs.arcade.dev/en/resources/integrations (integration catalog baseline)
- https://www.arcade.dev/llms.txt (machine-readable artifact baseline)

---

## Scorecard

| Lever | Score | Confidence | Why |
|---|---:|---|---|
| Content structure and extractability | 12/25 | Medium-High | Homepage is tagline-only with no answer-first content; no site-wide FAQ; blog posts have strong structure but they are minority surface area |
| Entity authority | 14/25 | High | Brand naming is clean and consistent; trust signals (SOC2, ISO 27001, $29M Series A) are surfaced; zero JSON-LD anywhere; no author attribution on content |
| Technical accessibility | 16/25 | High | Crawlability is excellent; docs `llms.txt` is spec-compliant; marketing domain missing `llms.txt`; no canonical tags; no JSON-LD; JS rendering risk on primary site |
| Citation-worthiness | 17/25 | Medium-High | 9 case studies with named executives and specific metrics are citation-ready; original frameworks and SDK tables are quotable; homepage and most product pages have no concrete extractable facts |
| **Total** | **59/100** | **High** | |

---

## Lever 1: Content Structure and Extractability — 12/25

| Sub-check | Score | Rationale |
|---|---:|---|
| Opening answer clarity | 2/5 | Homepage hero is *"Your agent decides what to do. We handle the rest."* — a tagline, not an answer. Blog posts open with narrative, not the solution. Neither delivers a direct, LLM-extractable answer in the first ~200 words. |
| Standalone sections | 3/5 | Case studies page is strong: each company gets its own discrete block with a named customer, a metric, and a quote. Blog sections (e.g., "Narrow Scope Principle") are self-contained H2/H3 blocks. Homepage sections are too vague to stand alone. |
| Heading hierarchy | 3/5 | Field guide blog post has clean H1 → H2 → H3 nesting. Homepage headings are fragmented marketing slogans (*"Search that thinks," "Tools that learn," "Auth that works"*) with no semantic hierarchy an LLM can follow. |
| Structured formatting | 3/5 | Field guide has TL;DR + FAQ block — both strong signals. Case studies have implicit table structure. Homepage has no FAQ, no tables, no TL;DR. Structured formatting is isolated to blog content. |
| Signal-to-noise ratio | 1/5 | Homepage is JavaScript-heavy and dominated by marketing slogans. Headings like *"ComposioFOR YOU"* and *"ComposioPLATFORM"* are rendering artifacts. Hero section produces near-zero extractable content. |

---

## Lever 2: Entity Authority — 14/25

| Sub-check | Score | Rationale |
|---|---:|---|
| Clear entity naming | 5/5 | "Composio" is unambiguous. OG title, og:site_name, and all subdomains reinforce the brand consistently. Product category — integration platform for AI agents — is clear from meta description. |
| Attribution and provenance | 1/5 | No author bylines on marketing pages. Docs llms.txt attributed only to "Composio Documentation" with no named maintainer. /authors page exists in sitemap but attribution is not surfaced at content level. |
| Structured entity markup | 0/5 | No JSON-LD detected on the homepage — no Organization, Product, SoftwareApplication, or BreadcrumbList schema. Knowledge graph systems have zero machine-readable entity signals. |
| Naming consistency | 4/5 | "Composio" used consistently across title tags, OG tags, subdomain naming, and docs. One deduction: homepage title tag is a tagline without the brand name; OG title mitigates this but not ideal. |
| Trust signals | 4/5 | SOC2 and ISO 27001:2022 on homepage. Dedicated trust.composio.dev (Vanta-hosted). $29M Series A in blog. Missing: no update dates on docs, no source citations linking to third-party coverage. |

---

## Lever 3: Technical Accessibility — 16/25

| Sub-check | Score | Rationale |
|---|---:|---|
| Crawlability | 5/5 | Permissive robots.txt on both domains. No disallow rules. All core pages indexable. No crawl traps or authentication walls on public content. |
| Discovery artifacts | 3/5 | Present but incomplete across domains. robots.txt and sitemap.xml present on both composio.dev and docs.composio.dev. sitemap-index.xml returns 404. No cross-subdomain sitemap consolidation. Arcade uses sitemap-index.xml — better pattern. |
| Canonicalization and metadata | 3/5 | Titles and meta descriptions are meaningful. OG and Twitter cards are complete. Canonical URL tags not explicitly declared — a gap for Next.js where URL parameters can produce duplicates. No lastmod in sitemap. |
| Machine-readable access | 3/5 | **Strong on docs subdomain:** docs.composio.dev/llms.txt is spec-compliant with 156 links and pointer to llms-full.txt. **Absent on primary domain:** composio.dev/llms.txt returns 404. Arcade's marketing llms.txt is live — a direct competitive gap. |
| Rendering and performance | 2/5 | Next.js with React Server Components introduces rendering risk for LLM crawlers that don't execute JavaScript. No static HTML fallbacks or .md variants on marketing domain. Docs subdomain mitigates via .md endpoint pattern. |

---

## Lever 4: Citation-Worthiness — 17/25

| Sub-check | Score | Rationale |
|---|---:|---|
| Concrete facts | 5/5 | Exceptional specific claims: *"$4.2M in enterprise deals," "380 engineering hours saved," "67% faster integration (6 weeks → 2 weeks)," "90% GTM reduction," "~$20K/month savings," "40,000 lines of TypeScript," "3,288 test cases."* |
| Unique data | 4/5 | Field guide's 5-principle framework is original. Self-improving AI system metrics (65/102 PRs merged in 8 days) are unique. Case study data is proprietary customer outcomes. Slight deduction: no benchmarks or academic-style datasets. |
| Evidence and sourcing | 4/5 | Customer outcomes attributed to named executives with titles (Nirman Dave CEO at Zams; Burca Paul Founder/CEO at Assista; Keith Fearon Head of Growth at 11x). SOC2/ISO certifications cited. No external links to third-party sources for verification. |
| Reusable passages | 3/5 | Field guide TL;DR and template (*"Tool to [action]. Use when [situation]"*) are directly citable. Customer quotes are strong candidates. Many passages require surrounding context — the Firecrawl failure story needs narrative frame to make sense. |
| Freshness and specificity | 1/5 | Blog content is dated and current (Sep 2025, Feb 2026). Homepage has no datestamps, no changelog, no version-specific content. SDK v3 terminology table is specific. Overall: blog is fresh; homepage is timeless in the wrong way. |

---

## Strengths

### 1. Case studies are the single best citation asset on the site
Nine structured customer stories, each with named executives, specific titles, quantified outcomes, and direct quotes:

> *"11x added $4.2M in enterprise deals and saved 380 engineering hours"* — Keith Fearon, Head of Growth, 11x

> *"We couldn't be more happier when we found Composio. It reduced our go-to-market time by over six months"* — Burca Paul, Founder/CEO, Assista AI

> *"Implementing the Gmail integration took less than a day. It just worked"* — Ryan Yu, Founder, Extra Thursday

These are attribution-rich and independently verifiable. No equivalent depth exists on Arcade's site currently.

### 2. docs.composio.dev/llms.txt is live and well-structured
Confirmed present with H1, blockquote summary, 13 organized sections, 156 links, and explicit pointer to `llms-full.txt`. The documentation also advertises a `.md` suffix pattern for machine-readable page fetching. This is a legitimate, spec-compliant LLM accessibility implementation.

### 3. The field-guide blog post demonstrates ideal content structure
`/blog/how-to-build-great-tools-for-ai-agents-a-field-guide` has a TL;DR, clean H2→H3 nesting, and a 4-question FAQ block — all three structural signals LLMs weight. The proprietary description template (*"Tool to [action]. Use when [situation]"*) is directly extractable.

### 4. Crawl infrastructure is permissive and coherent
Both domains have correctly configured `robots.txt` pointing to their respective sitemaps. No crawl blocks, no authentication walls on public content, no disallow rules. Sitemap has priority weighting and covers all core sections.

### 5. Brand entity naming is unambiguous and consistent
"Composio" is distinctive, non-generic, and used identically across title tags, OG metadata, subdomain names, and documentation. Meta description is specific and category-defining: *"Just-in-time tool calls, secure delegated auth, sandboxed environments, and parallel execution across 1,000+ apps."*

---

## Weaknesses

### 1. Homepage is answer-absent (Lever 1 — 2/5)
The hero delivers *"Your agent decides what to do. We handle the rest."* — a tagline with zero extractable information about what Composio is, who it is for, or how it works. Section headings like *"Search that thinks," "Tools that learn," "Auth that works"* are poetic but semantically empty. An LLM querying "what is Composio?" would find nothing citable in the first 200 words.

### 2. No FAQ anywhere on the site except one blog post (Lever 1 — 3/5 site avg)
FAQ sections are among the highest-weighted structural signals for LLM extractability because they mirror the query-answer format. The only FAQ block on the entire site is inside a single blog post. All top-funnel product pages — homepage, pricing, enterprise — have none.

### 3. Zero JSON-LD structured data on the primary domain (Lever 2 — 0/5)
No `Organization`, `SoftwareApplication`, `Product`, or `BreadcrumbList` schema anywhere on composio.dev. This is the highest-impact technical gap: knowledge graph systems and LLMs that rely on structured entity declarations cannot reliably classify Composio as an organization or product. The Next.js stack makes this straightforward to add.

### 4. No llms.txt on the marketing domain (Lever 3 — 3/5)
`composio.dev/llms.txt` returns 404. Arcade's marketing domain exposes a well-formed `llms.txt` with a mission statement, capability summary, and curated links. Composio forces LLMs inferring brand-level context to work from JS-rendered HTML alone — the domain where brand queries actually land.

### 5. No canonical tags declared on any page (Lever 3 — 3/5)
No `<link rel="canonical">` is present in homepage metadata. For a Next.js app where URL parameters and trailing slashes can produce duplicates, this is a de-duplication risk. LLMs that weight canonical signals have no authoritative URL to anchor the entity to.

### 6. Integration scale advantage is structurally invisible (Lever 4)
Composio claims 1,000+ integrations but surfaces this only as hero copy. Arcade's integration catalog at `docs.arcade.dev/en/resources/integrations` is a structured, tiered registry (Arcade Optimized / Verified / Community) with named entries and categories — parseable by LLMs. Composio's 7× scale advantage is not structured for retrieval.

---

## Arcade Opportunities

### Opportunity 1 — Maintain the `llms.txt` lead on the marketing domain

- **Arcade URL:** https://www.arcade.dev/llms.txt
- **Gap:** Composio's marketing domain has no `llms.txt` (404). Arcade's is live. This is Arcade's clearest current technical advantage.
- **Suggested change:** Ensure `arcade.dev/llms.txt` stays current and is expanded with more specific capability language, product descriptions, and links to integration catalog pages. Add a pointer from `arcade.dev/llms.txt` to `docs.arcade.dev/llms.txt` to create a federated discovery path.
- **Why it matters:** When an LLM is asked "what is Arcade?" or "how do Arcade and Composio compare?", the brand-level `llms.txt` is the most direct path to a curated, accurate answer. Composio cannot compete on this dimension until they ship their own.

### Opportunity 2 — Add a homepage FAQ block to Arcade

- **Arcade URL:** https://www.arcade.dev/
- **Gap:** Neither site has a homepage FAQ. Both are weak. Composio has no plans to add one (no signal in their content). Arcade can move first.
- **Suggested change:** Add a 5–8 question FAQ section to the bottom of `arcade.dev`, covering: what Arcade is, how it differs from direct API calls, what MCP means, what frameworks are supported, and how pricing works. Mirror the answer-first format Arcade already uses in the hero.
- **Why it matters:** FAQ sections directly mirror LLM prompt formats. A homepage FAQ makes Arcade's product definition independently extractable without requiring a crawler to fetch the docs.

### Opportunity 3 — Add JSON-LD Organization + SoftwareApplication schema

- **Arcade URL:** https://www.arcade.dev/
- **Gap:** Composio has no JSON-LD (confirmed 0/5). This is an opportunity to differentiate on a check where the competitor scores zero.
- **Suggested change:** Add a JSON-LD block with `@type: Organization`, `name: "Arcade"`, `url`, `description`, `sameAs` (LinkedIn, GitHub, Crunchbase), and a nested `SoftwareApplication`. Add `BreadcrumbList` on interior pages.
- **Why it matters:** The only reliable path to knowledge graph entity resolution. If Arcade adds this before Composio, it creates a structural advantage that persists in LLM training data and retrieval systems.

### Opportunity 4 — Strengthen the integration catalog's structural advantage

- **Arcade URL:** https://docs.arcade.dev/en/resources/integrations
- **Gap:** Arcade's tiered catalog (Arcade Optimized / Verified / Community) is structurally better than Composio's "1,000+ apps" hero claim. But Arcade has 141 entries vs. Composio's 1,000+. Composio will eventually build a structured catalog; Arcade should raise the bar on quality.
- **Suggested change:** Add a short paragraph at the top explaining tier definitions and how integrations are qualified. Add a per-integration summary line describing what actions each integration supports. This makes each entry independently citable.
- **Why it matters:** When an LLM is asked "which AI agent platforms support Salesforce?", a structured catalog with per-entry descriptions will outrank a quantity claim without structure every time.

### Opportunity 5 — Build case study depth comparable to Composio

- **Arcade URL:** https://www.arcade.dev/ (currently: named logos + one Harrison Chase quote)
- **Gap:** Composio has 9 case studies with named executives, specific metrics ($4.2M, 380 hours, 67% faster), and multi-paragraph narratives. Arcade has 5 named logos and one attributed quote on the homepage.
- **Suggested change:** Publish 3–5 customer case studies with the same formula: named customer, named executive with title, one specific quantified outcome, one direct quote. A dedicated `/case-studies` page with a summary table would be directly citable by LLMs answering "which companies use Arcade?"
- **Why it matters:** LLMs surfaced with Composio case study data will cite Composio as the incumbent integration solution. Arcade needs attributable, quantified proof to compete on citation-worthiness. This is the largest gap Composio holds over Arcade.

---

## Optional Issue Plan

Candidate issue titles for Arcade (not created — recommendations only):

1. `[GEO] Add homepage FAQ block to arcade.dev` — Lever 1 / Content structure
2. `[GEO] Add JSON-LD Organization + SoftwareApplication schema to arcade.dev homepage` — Lever 2 / Entity authority
3. `[GEO] Ensure arcade.dev/llms.txt stays current and links to docs llms.txt` — Lever 3 / Machine-readable access
4. `[GEO] Add per-entry descriptions to docs.arcade.dev/en/resources/integrations` — Lever 4 / Citation-worthiness
5. `[GEO] Publish 3-5 case studies with named customers, executives, and quantified outcomes` — Lever 4 / Citation-worthiness
