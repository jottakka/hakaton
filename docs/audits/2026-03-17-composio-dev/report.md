# GEO Audit: composio.dev

## Executive Summary

- Overall score: `64/100`
- Confidence: `medium`
- Short answer: Composio is meaningfully easier for LLMs to discover and use than its older surface suggested. The root site now has a live `llms.txt`, the docs subdomain has both `llms.txt` and `llms-full.txt`, and the checked docs routes expose real `.md` endpoints. The biggest gaps are still structural: the homepage is noisy, marketing pages lack richer page-level schema, and machine-readable artifact quality is uneven across secondary subdomains.
- Arcade priority: tighten machine-readable delivery and page-level schema on `https://docs.arcade.dev/en/resources/integrations` and `https://docs.arcade.dev/en/get-started/quickstarts/call-tool-agent`, because Composio currently has the stronger docs-side LLM surface.

## Scope

- Targets: `https://composio.dev/`, `https://docs.composio.dev/`
- Audit mode: `site-slice`
- Coverage preset: `exhaustive`
- Evidence method: local deterministic GEO evidence collection plus bounded page inspection
- Coverage summary: `18` selected representative pages across `4` selected subdomains; candidate pool truncated at the preset budget
- Arcade baselines used:
  - `https://www.arcade.dev/`
  - `https://www.arcade.dev/pricing`
  - `https://docs.arcade.dev/en/resources/integrations`
  - `https://docs.arcade.dev/en/get-started/quickstarts/call-tool-agent`

### Site Artifacts Inspected

- `https://composio.dev/robots.txt` -> `200`
- `https://composio.dev/sitemap.xml` -> `200`
- `https://composio.dev/llms.txt` -> `200`
- `https://composio.dev/llms-full.txt` -> `404`
- `https://docs.composio.dev/robots.txt` -> `200`
- `https://docs.composio.dev/sitemap.xml` -> `200`
- `https://docs.composio.dev/llms.txt` -> `200`
- `https://docs.composio.dev/llms-full.txt` -> `200`
- Checked docs markdown endpoints:
  - `https://docs.composio.dev/docs/common-faq.md` -> `200`
  - `https://docs.composio.dev/docs/native-tools-vs-mcp.md` -> `200`
- Discovered subdomain artifacts also checked on: `platform.composio.dev`, `mcp.composio.dev`, `trust.composio.dev`, `directory.composio.dev`, `app.composio.dev`, `chat.composio.dev`, `dub.composio.dev`, `rube.composio.dev`
- Notable subdomain gaps:
  - `https://mcp.composio.dev/llms.txt` and `https://mcp.composio.dev/llms-full.txt` returned `500`
  - `https://mcp.composio.dev/robots.txt` declares both `https://mcp.composio.dev/sitemap.xml` and `https://mcp.composio.dev/server-sitemap-index.xml`
  - `https://directory.composio.dev/robots.txt` and `https://directory.composio.dev/llms.txt` were missing
  - `platform.composio.dev` and `trust.composio.dev` expose `llms` endpoints that exist as HTML placeholder pages rather than clean text artifacts

## Scorecard

| Lever | Score | Confidence | Why |
| --- | ---: | --- | --- |
| Content structure and extractability | 13/25 | medium | Pricing and enterprise pages answer their job quickly, but the homepage is noisier and heading structure is uneven. |
| Entity authority | 17/25 | medium | Docs pages carry basic `Organization` and `WebSite` schema, and trust signals are strong, but marketing pages are still light on richer entity markup and provenance. |
| Technical accessibility | 19/25 | medium | Root and docs artifacts are strong, docs-side markdown delivery is real, but quality drops on some secondary subdomains. |
| Data-rich citation-worthiness | 15/25 | medium | Pricing and enterprise pages are concrete and quotable, though many claims remain self-asserted rather than source-backed. |

## Strengths

- `https://composio.dev/llms.txt` is live and useful. It gives the marketing root a real machine-readable entry point instead of forcing crawlers to infer the product only from homepage HTML.
- `https://docs.composio.dev/llms.txt`, `https://docs.composio.dev/llms-full.txt`, `https://docs.composio.dev/docs/common-faq.md`, and `https://docs.composio.dev/docs/native-tools-vs-mcp.md` create a strong docs-side retrieval surface for agents.
- `https://composio.dev/pricing` is the best citation asset in the bounded slice. The plan names, tool-call quotas, monthly prices, and overage rates are directly quotable.
- `https://composio.dev/enterprise` turns trust language into labeled blocks around security, governance, observability, infrastructure, reliability, and flexibility, which makes retrieval cleaner than vague enterprise copy.
- The main site and docs sitemaps are coherent and include the key high-value routes inspected here, including pricing, enterprise, FAQ, and comparison-style docs pages.

## Weaknesses

- `https://composio.dev/` still spends too much of the first screen on demo UI and slogan-heavy framing. It is materially better than a blank marketing shell, but it is still noisier than an ideal answer-first homepage.
- `https://composio.dev/enterprise` has duplicated H1 text and skip-level heading structure, which makes chunking less reliable for retrieval systems.
- Composio's page-level schema is incomplete. The sampled marketing pages carry no observed JSON-LD, while the sampled docs pages mostly expose only generic `Organization` and `WebSite` types rather than stronger page-specific types like `FAQPage` or `TechArticle`.
- Artifact quality is inconsistent across the broader Composio surface. Some subdomains have real machine-readable support, but others return redirects, `500`s, or placeholder HTML at `llms` paths.
- Many of the strongest claims in the bounded marketing slice are specific but self-asserted. The evidence set did not surface much third-party corroboration or linked proof on the inspected pages.

## Arcade Opportunities

- Arcade URL: `https://docs.arcade.dev/en/resources/integrations`
  Gap: Composio currently has stronger docs-side machine readability because the checked Composio doc routes expose real `.md` endpoints, while the comparable Arcade route checked here does not.
  Suggested change: publish a stable markdown version, add canonical and page-level schema, and add short capability blurbs plus tier definitions for each integration class.
  Why it matters: this is one of Arcade's highest-value retrieval pages, and it should be directly consumable by both humans and agents.

- Arcade URL: `https://docs.arcade.dev/en/get-started/quickstarts/call-tool-agent`
  Gap: the page structure is good, but the checked markdown variant returns `404`, and the opening capture is nav-heavy rather than answer-first.
  Suggested change: add a stable markdown endpoint, a short TL;DR or "What you'll build" summary, and page-level `TechArticle` or `BreadcrumbList` schema.
  Why it matters: flagship quickstarts are common citation targets in agent comparisons.

- Arcade URL: `https://www.arcade.dev/`
  Gap: Composio now has a live marketing-root `llms.txt`, while Arcade's homepage still leans more on broad positioning than a compact, factual answer block.
  Suggested change: add a tighter answer-first paragraph under the hero, include 2-3 concrete proof points, and ship richer page-level `Organization` plus product schema alongside the existing `llms.txt`.
  Why it matters: this improves both entity resolution and direct answer quality for brand-level prompts.

- Arcade URL: `https://www.arcade.dev/pricing`
  Gap: the page is data-rich, but a machine-friendly comparison artifact would still be stronger than plan-card prose alone.
  Suggested change: add an HTML comparison table and `Product` or `Offer` schema for plan structure.
  Why it matters: pricing is a high-frequency retrieval and citation surface.

## Optional Issue Plan

- Not requested.
