# GEO Audit: docs.merge.dev/basics/mcp/

## Executive Summary
- **Overall score: 58/100** — just below the recommended threshold
- **Confidence: High** (CollectGeoEvidence ran; artifact status and page metadata verified deterministically)
- **LLM retrievability: Moderate.** The MCP page opens with a clear answer and has a coherent structure, but the docs subdomain lacks `llms.txt`, `robots.txt`, and JSON-LD. `help.merge.dev` has a strong `llms.txt`; `docs.merge.dev` does not.
- **Arcade priority:** Add `llms.txt` and `robots.txt` to docs.merge.dev — Arcade's docs subdomain exposes both; Merge's docs subdomain exposes neither. Low-effort, high-leverage.

---

## Scope

**Targets:**
- https://docs.merge.dev/basics/mcp/ (primary)

**Site artifacts inspected (deterministic, CollectGeoEvidence):**

| Artifact | docs.merge.dev | www.merge.dev | help.merge.dev |
|---|---|---|---|
| robots.txt | 404 ❌ | 200 ✅ | 200 ✅ |
| sitemap.xml | 200 ✅ (index) | 200 ✅ | 200 ✅ |
| llms.txt | 404 ❌ | 404 ❌ | 200 ✅ (spec-compliant) |
| llms-full.txt | 404 ❌ | 404 ❌ | 404 ❌ |

*Note: app.merge.dev and cdn.merge.dev return HTTP 200 for llms.txt/sitemap.xml but serve HTML (SPA fallback), not spec-compliant artifacts. Not counted as valid llms.txt.*

**Arcade benchmarks used:**
- https://docs.arcade.dev/en/get-started/setup/connect-arcade-docs (LLM-readable docs baseline)
- https://docs.arcade.dev/en/get-started/quickstarts/call-tool-agent (answer-first quickstart baseline)
- https://docs.arcade.dev/en/guides/audit-logs (structured guide baseline)

---

## Scorecard

| Lever | Score | Confidence | Why |
|---|---:|---|---|
| Content structure and extractability | 14/25 | High | Opening answer is clear; heading hierarchy jumps from H1 to H5/H6; no FAQ; structured setup steps present |
| Entity authority | 12/25 | High | "Merge" and "MCP" are clear; no JSON-LD; no author attribution; OG tags present |
| Technical accessibility | 12/25 | High | docs.merge.dev has no robots.txt, no llms.txt; sitemap present; canonical declared |
| Citation-worthiness | 20/25 | High | Concrete scope examples, env vars, SDK link; reusable setup steps; no datestamps |
| **Total** | **58/100** | **High** | |

---

## Lever 1: Content Structure and Extractability — 14/25

| Sub-check | Score | Rationale |
|---|---:|---|
| Opening answer clarity | 4/5 | First ~200 words: *"Merge offers an MCP server that integrates the Merge API with any LLM provider supporting the MCP protocol. This enables your AI agent to access hundreds of tools via a single MCP server."* — direct answer. |
| Standalone sections | 3/5 | Installation, MCP setup, Scopes, Environment variables are discrete. Example setups (Claude Desktop, Python client) are procedural but depend on surrounding context. |
| Heading hierarchy | 2/5 | H1 → H5 → H5 → H6. No H2/H3/H4. Jumps from top-level to example sub-headings. Weak semantic nesting. |
| Structured formatting | 3/5 | Numbered setup steps, bullet lists for prerequisites and env vars. No FAQ, no TL;DR, no tables. |
| Signal-to-noise ratio | 2/5 | Sidebar nav and footer add noise. Core content is extractable but mixed with navigation. |

---

## Lever 2: Entity Authority — 12/25

| Sub-check | Score | Rationale |
|---|---:|---|
| Clear entity naming | 5/5 | "Merge" and "Model Context Protocol (MCP)" are unambiguous. Title and H1 match. |
| Attribution and provenance | 1/5 | No author, no maintainer, no update date. Docs attribution absent. |
| Structured entity markup | 0/5 | `json_ld_entries: []` — no Organization, SoftwareApplication, Article, or BreadcrumbList. |
| Naming consistency | 3/5 | "Merge MCP" used consistently. Title omits "Merge" but H1 includes it. |
| Trust signals | 3/5 | Links to Merge MCP SDK (GitHub). Env vars and setup steps imply official docs. No SOC2/ISO or external citations. |

---

## Lever 3: Technical Accessibility — 12/25

| Sub-check | Score | Rationale |
|---|---:|---|
| Crawlability | 4/5 | Page returns 200. No robots.txt on docs.merge.dev means no explicit disallow; crawlers can reach content. |
| Discovery artifacts | 2/5 | docs.merge.dev: robots.txt 404, sitemap.xml 200. www.merge.dev has robots + sitemap. help.merge.dev has all three. docs subdomain is the target and lacks robots.txt. |
| Canonicalization and metadata | 4/5 | Canonical declared: `https://docs.merge.dev/basics/mcp/`. Title and OG tags present. Meta description null. |
| Machine-readable access | 1/5 | docs.merge.dev/llms.txt 404. docs.merge.dev/llms-full.txt 404. help.merge.dev has llms.txt; docs does not. Arcade docs have llms.txt. |
| Rendering and performance | 1/5 | Fetched HTML contains core content. Possible JS enhancement; no static fallback. |

---

## Lever 4: Citation-Worthiness — 20/25

| Sub-check | Score | Rationale |
|---|---:|---|
| Concrete facts | 5/5 | Prerequisites (Python 3.10+, uv, Merge API key), scope format (`<category>.<common_model>:<permission>`), env vars (MERGE_API_KEY, MERGE_ACCOUNT_TOKEN, MERGE_TENANT). |
| Unique data | 4/5 | Merge-specific MCP setup, scope examples (ats.Candidate:read, hris.Employee:write). |
| Evidence and sourcing | 4/5 | SDK link to GitHub. No external citations for MCP spec. |
| Reusable passages | 4/5 | Setup steps, scope format, env var list are directly citable. |
| Freshness and specificity | 3/5 | No datestamps. Content feels current (MCP, Claude Desktop). |

---

## Strengths

### 1. Opening answer is answer-first
The first ~200 words state: *"Merge offers an MCP server that integrates the Merge API with any LLM provider supporting the MCP protocol. This enables your AI agent to access hundreds of tools via a single MCP server."* — directly answers "what is Merge MCP?"

### 2. Canonical and title/H1 alignment
Canonical URL declared. Title and H1 both "Model Context Protocol (MCP)" with 1.0 similarity.

### 3. Concrete, citable setup content
Prerequisites, scope format, env vars, and step-by-step setup (Claude Desktop, Python client) are specific and quotable.

### 4. help.merge.dev has llms.txt
The help subdomain exposes a spec-compliant llms.txt with structured sections and links — a positive pattern Merge could extend to docs.

### 5. Sitemap present on docs subdomain
docs.merge.dev/sitemap.xml returns 200 with sitemap index. Enables discovery of docs pages.

---

## Weaknesses

### 1. docs.merge.dev has no llms.txt (Lever 3 — 1/5)
docs.merge.dev/llms.txt returns 404. Arcade's docs.arcade.dev has llms.txt. LLMs querying "how does Merge MCP work?" land on docs; no machine-readable index.

### 2. docs.merge.dev has no robots.txt (Lever 3 — 2/5)
docs.merge.dev/robots.txt returns 404. Crawlers have no declared sitemap path or disallow rules for the docs subdomain.

### 3. No JSON-LD (Lever 2 — 0/5)
Zero structured data. No Article, TechArticle, or BreadcrumbList. Knowledge graphs and entity resolvers get no machine-readable signal.

### 4. Heading hierarchy jumps H1→H5 (Lever 1 — 2/5)
H1 "Model Context Protocol (MCP)" followed by H5 "Example Claude Desktop setup". No H2/H3/H4. Weak semantic structure for chunking.

### 5. No meta description (Lever 2/3)
meta_description is null. OG description exists; meta description would improve snippet quality.

---

## Arcade Opportunities

### Opportunity 1 — Maintain llms.txt on docs subdomain

- **Arcade URL:** https://docs.arcade.dev/llms.txt
- **Gap:** Merge's docs.merge.dev has no llms.txt (404). Arcade's docs subdomain has one.
- **Suggested change:** Ensure docs.arcade.dev/llms.txt stays current with key guides, quickstarts, and integration pages. Add pointer to llms-full.txt if applicable.
- **Why it matters:** When an LLM asks "how do I connect Arcade docs?" or "Merge MCP setup", the docs llms.txt is the primary machine-readable entry point. Merge cannot compete until they add one.

### Opportunity 2 — Add robots.txt to docs subdomain

- **Arcade URL:** https://docs.arcade.dev/robots.txt
- **Gap:** Merge's docs.merge.dev has no robots.txt. Arcade should verify docs.arcade.dev/robots.txt exists and references the sitemap.
- **Suggested change:** If missing, add robots.txt to docs.arcade.dev with Sitemap directive. If present, ensure it stays correct.
- **Why it matters:** Crawlers and LLM fetchers use robots.txt for discovery. Merge's gap is Arcade's chance to be more discoverable.

### Opportunity 3 — Add JSON-LD Article/TechArticle to docs pages

- **Arcade URL:** https://docs.arcade.dev/en/get-started/quickstarts/call-tool-agent
- **Gap:** Merge MCP page has no JSON-LD. Arcade can differentiate with Article or TechArticle schema.
- **Suggested change:** Add JSON-LD with @type: TechArticle, headline, description, author (or publisher), datePublished. Add BreadcrumbList for nav context.
- **Why it matters:** Entity resolution and rich snippets. Merge scores 0/5 here; Arcade can lead.

### Opportunity 4 — Strengthen heading hierarchy in guides

- **Arcade URL:** https://docs.arcade.dev/en/guides/audit-logs
- **Gap:** Merge's MCP page jumps H1→H5. Arcade should enforce H1→H2→H3 nesting.
- **Suggested change:** Audit Arcade guides for heading levels. Ensure no H5/H6 without intervening H2/H3/H4. Improves chunking and retrieval.
- **Why it matters:** Clean hierarchy improves section independence and LLM passage extraction.

### Opportunity 5 — Add meta description to docs pages

- **Arcade URL:** https://docs.arcade.dev/en/get-started/setup/connect-arcade-docs
- **Gap:** Merge MCP page has null meta description. OG description exists but meta is missing.
- **Suggested change:** Add unique meta description (155–160 chars) to each docs page. Improves SERP snippets and retrieval relevance.
- **Why it matters:** Meta description is a high-signal field for summarization and relevance.

---

## Optional Issue Plan

Candidate issue titles for Arcade (recommendations only):

1. `[GEO] Ensure docs.arcade.dev/llms.txt exists and links to key guides` — Lever 3
2. `[GEO] Add robots.txt to docs.arcade.dev with Sitemap directive` — Lever 3
3. `[GEO] Add TechArticle JSON-LD to docs quickstart and guide pages` — Lever 2
4. `[GEO] Audit docs heading hierarchy (H1→H2→H3) for chunking` — Lever 1
5. `[GEO] Add meta description to docs pages missing it` — Lever 2/3
