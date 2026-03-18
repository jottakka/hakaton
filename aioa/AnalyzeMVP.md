# Bucket 1 — Tool Pipeline Specification

> **Owners:** Tyler, Jonnel
> **Status:** MVP — Architecture & Logic
> **Date:** March 17, 2026

---

## 1. Overview

### What This Is
An **AI & Search Visibility Benchmarking Tool** — a pipeline that measures how **Arcade** ranks against competitors across both AI-generated answers (AIO) and traditional search results (SEO).

### What It Does
1. Takes a set of **model prompts** and **search engine terms** as input
2. Runs prompts through **3 LLM APIs** (OpenAI GPT, Google Gemini, Anthropic Claude) to assess AI Overview positioning
3. Runs search terms through **2 Search APIs** (Google, Bing) to assess SEO positioning
4. Stores all raw results in a **persistent data store**
5. An **orchestrator agent** parses the results and produces **scores + observations** comparing Arcade vs. competitors for each prompt/term

### Why It Matters
- **Point-in-time competitive positioning:** How visible is Arcade when users ask AI or search engines about relevant topics?
- **Longitudinal tracking:** Run the same prompt sets over time to measure whether visibility is improving or declining
- **Ad-hoc querying:** "How does Arcade rank for MCP Runtime?" → instant competitive snapshot
- **Gap identification:** Surface prompts/terms where Arcade should rank but doesn't

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────┐
│  01 — INPUT LAYER                                       │
│  Prompt Library + Search Term Library + Competitor List  │
└──────────────────────────┬──────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
┌──────────────────────┐  ┌──────────────────────┐
│  02a — MODEL LAYER   │  │  02b — SEARCH LAYER  │
│  • OpenAI GPT        │  │  • Google Search API  │
│  • Google Gemini     │  │  • Bing Search API    │
│  • Anthropic Claude  │  │                       │
└──────────┬───────────┘  └──────────┬────────────┘
           │                         │
           └────────────┬────────────┘
                        ▼
┌─────────────────────────────────────────────────────────┐
│  03 — PERSISTENCE LAYER                                 │
│  • Model Response Store (raw LLM outputs)               │
│  • Search Result Store (raw SERP data)                  │
│  SQLite for MVP → upgrade path to Postgres/Supabase     │
└──────────────────────────┬──────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────┐
│  04 — ORCHESTRATION LAYER                               │
│  • Skills: scoring logic, competitor detection,         │
│    mention analysis, rank extraction                    │
│  • Orchestrator Agent (Claude-powered): ingests stored  │
│    results, applies skills, produces structured output  │
└──────────────────────────┬──────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────┐
│  05 — OUTPUT LAYER                                      │
│  • Per-prompt scores (Arcade vs. each competitor)       │
│  • Observations & gap analysis                          │
│  • Summary report (JSON + human-readable)               │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Input Schema

### 3.1 Competitor List
A flat list of company/product names the orchestrator will look for in results.

```json
{
  "target": "Arcade",
  "competitors": [
    "TODO — Tyler to provide"
  ]
}
```

> **Action item:** Tyler to supply the full competitor list.

### 3.2 Model Prompts (AIO)
Prompts sent verbatim to each LLM. Designed to simulate how a real user would ask an AI assistant about topics where Arcade should appear.

```json
{
  "prompt_set_id": "v1",
  "created_at": "2026-03-17",
  "prompts": [
    {
      "id": "p001",
      "text": "TODO — Tyler to provide",
      "category": "e.g. mcp_runtime | auth | tooling | general",
      "expected_winner": "Arcade",
      "notes": "optional context"
    }
  ]
}
```

> **Action item:** Tyler to supply the initial prompt list.

### 3.3 Search Terms (SEO)
Exact queries sent to Google and Bing search APIs.

```json
{
  "term_set_id": "v1",
  "created_at": "2026-03-17",
  "terms": [
    {
      "id": "s001",
      "query": "TODO — Tyler to provide",
      "category": "e.g. mcp_runtime | auth | tooling | general",
      "expected_winner": "Arcade",
      "notes": "optional context"
    }
  ]
}
```

> **Action item:** Tyler to supply the initial search term list.

---

## 4. Processing Layer — Implementation Details

### 4.1 Model Layer (AIO)

For each prompt, call all three LLM APIs and store the raw response.

```python
# Pseudocode — actual implementation in Claude Code

async def run_model_prompt(prompt: str, model: str) -> dict:
    """
    Send prompt to a single LLM and return structured result.
    
    Models:
      - "openai"    → GPT-4o (or latest) via OpenAI API
      - "gemini"    → Gemini 2.5 Pro via Google AI API
      - "anthropic" → Claude Sonnet 4 via Anthropic API
    
    Returns:
      {
        "model": "openai",
        "prompt_id": "p001",
        "raw_response": "...",
        "timestamp": "2026-03-17T12:00:00Z",
        "latency_ms": 1230
      }
    """
    pass

async def run_all_models(prompt: dict) -> list[dict]:
    """Fan out prompt to all 3 models concurrently."""
    return await asyncio.gather(
        run_model_prompt(prompt["text"], "openai"),
        run_model_prompt(prompt["text"], "gemini"),
        run_model_prompt(prompt["text"], "anthropic"),
    )
```

**API Key Management:**
- Use environment variables: `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`
- MVP: `.env` file loaded via `python-dotenv`

### 4.2 Search Layer (SEO)

For each search term, query Google and Bing and store raw SERP results.

```python
async def run_search(query: str, engine: str) -> dict:
    """
    Run a search query against a single engine.
    
    Engines:
      - "google" → Google Custom Search JSON API
      - "bing"   → Bing Web Search API v7
    
    Returns:
      {
        "engine": "google",
        "term_id": "s001",
        "results": [
          {
            "position": 1,
            "title": "...",
            "url": "...",
            "snippet": "..."
          }
        ],
        "timestamp": "2026-03-17T12:00:00Z"
      }
    """
    pass

async def run_all_searches(term: dict) -> list[dict]:
    """Fan out term to all search engines concurrently."""
    return await asyncio.gather(
        run_search(term["query"], "google"),
        run_search(term["query"], "bing"),
    )
```

**API Key Management:**
- `GOOGLE_CSE_API_KEY`, `GOOGLE_CSE_CX` (Custom Search Engine ID)
- `BING_SEARCH_API_KEY`

---

## 5. Persistence Layer

### MVP: SQLite

Three core tables:

```sql
-- Run metadata (each execution of the pipeline)
CREATE TABLE runs (
    id TEXT PRIMARY KEY,           -- uuid
    prompt_set_id TEXT NOT NULL,
    term_set_id TEXT NOT NULL,
    competitor_config TEXT NOT NULL, -- JSON blob
    created_at TEXT NOT NULL        -- ISO 8601
);

-- Raw model responses
CREATE TABLE model_results (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    prompt_id TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    model TEXT NOT NULL,            -- openai | gemini | anthropic
    raw_response TEXT NOT NULL,
    latency_ms INTEGER,
    created_at TEXT NOT NULL
);

-- Raw search results
CREATE TABLE search_results (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    term_id TEXT NOT NULL,
    query TEXT NOT NULL,
    engine TEXT NOT NULL,           -- google | bing
    results_json TEXT NOT NULL,     -- JSON array of {position, title, url, snippet}
    created_at TEXT NOT NULL
);

-- Orchestrator analysis output
CREATE TABLE analysis_results (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    analysis_json TEXT NOT NULL,    -- full structured output from orchestrator
    created_at TEXT NOT NULL
);
```

**Upgrade path:** Phase 2 → Postgres or Supabase for multi-user access, better querying, and dashboarding.

---

## 6. Orchestration Layer

### 6.1 Skills

Skills are discrete analysis functions the orchestrator uses. Each skill takes raw stored data and returns structured observations.

| Skill | Input | Output |
|---|---|---|
| `mention_detection` | LLM response text + competitor list | Which companies were mentioned, in what context (positive/negative/neutral), position in response |
| `rank_extraction` | Search results + competitor list | Where each competitor's domain appears in SERP, position number |
| `score_calculation` | Mention + rank data | Normalized 0-100 score per competitor per prompt/term |
| `gap_analysis` | Scores + expected winners | Prompts/terms where Arcade should rank #1 but doesn't |
| `competitor_comparison` | All scores | Head-to-head comparison matrix |

### 6.2 Orchestrator Agent

A Claude-powered agent that ingests all stored results for a given run and produces the final analysis.

**System prompt sketch:**

```
You are a competitive intelligence analyst. You have been given:
1. Raw LLM responses to prompts about AI tooling / MCP / etc.
2. Raw search engine results for related queries.
3. A target company (Arcade) and a list of competitors.

For each prompt/term, analyze:
- Was the target mentioned? Where and how?
- Which competitors were mentioned? Where and how?
- Assign a visibility score (0-100) for each company.
- Flag any prompts/terms where the target was expected to rank #1 but didn't.

Return your analysis as structured JSON matching the output schema.
```

**Output schema:**

```json
{
  "run_id": "...",
  "generated_at": "2026-03-17T12:00:00Z",
  "summary": {
    "arcade_avg_aio_score": 72,
    "arcade_avg_seo_score": 45,
    "top_competitor": "CompetitorX",
    "biggest_gap": "prompt p003 — MCP Runtime"
  },
  "aio_results": [
    {
      "prompt_id": "p001",
      "prompt_text": "...",
      "category": "mcp_runtime",
      "expected_winner": "Arcade",
      "by_model": {
        "openai": {
          "mentions": {
            "Arcade": { "mentioned": true, "position": "first", "sentiment": "positive", "context_snippet": "..." },
            "CompetitorX": { "mentioned": true, "position": "third", "sentiment": "neutral", "context_snippet": "..." }
          },
          "scores": { "Arcade": 85, "CompetitorX": 40 }
        },
        "gemini": { "..." : "..." },
        "anthropic": { "..." : "..." }
      },
      "aggregate_score": { "Arcade": 78, "CompetitorX": 42 },
      "observations": "Arcade is consistently mentioned first across models for this prompt..."
    }
  ],
  "seo_results": [
    {
      "term_id": "s001",
      "query": "...",
      "category": "mcp_runtime",
      "expected_winner": "Arcade",
      "by_engine": {
        "google": {
          "rankings": {
            "Arcade": { "position": 3, "url": "...", "snippet": "..." },
            "CompetitorX": { "position": 1, "url": "...", "snippet": "..." }
          },
          "scores": { "Arcade": 60, "CompetitorX": 90 }
        },
        "bing": { "..." : "..." }
      },
      "aggregate_score": { "Arcade": 55, "CompetitorX": 85 },
      "observations": "CompetitorX outranks Arcade on both engines..."
    }
  ],
  "gap_report": [
    {
      "id": "p003",
      "type": "aio",
      "text": "What is the best MCP runtime?",
      "expected": "Arcade",
      "actual_winner": "CompetitorX",
      "arcade_score": 30,
      "winner_score": 88,
      "recommendation": "..."
    }
  ]
}
```

---

## 7. Project Structure

```
bucket1-pipeline/
├── README.md
├── .env.example              # API key template
├── pyproject.toml             # dependencies
├── config/
│   ├── competitors.json       # target + competitor list
│   ├── prompts_v1.json        # model prompt set
│   └── terms_v1.json          # search term set
├── src/
│   ├── __init__.py
│   ├── main.py                # CLI entrypoint: run pipeline
│   ├── input_layer.py         # load & validate prompt/term configs
│   ├── models.py              # LLM API integrations (OpenAI, Gemini, Claude)
│   ├── search.py              # Search API integrations (Google, Bing)
│   ├── store.py               # SQLite persistence layer
│   ├── skills/
│   │   ├── __init__.py
│   │   ├── mention_detection.py
│   │   ├── rank_extraction.py
│   │   ├── score_calculation.py
│   │   ├── gap_analysis.py
│   │   └── competitor_comparison.py
│   ├── orchestrator.py        # Claude-powered orchestrator agent
│   └── output.py              # Report generation (JSON + summary)
├── data/
│   └── pipeline.db            # SQLite database (gitignored)
└── tests/
    ├── test_models.py
    ├── test_search.py
    ├── test_skills.py
    └── test_orchestrator.py
```

---

## 8. MVP Scope & Non-Goals

### In Scope (Phase 1 — MVP)
- [x] Input schema for prompts, terms, and competitors
- [ ] Async API calls to 3 LLMs + 2 search engines
- [ ] SQLite storage for raw results
- [ ] Orchestrator agent that scores and compares
- [ ] JSON report output
- [ ] CLI-driven: `python -m src.main run --prompts config/prompts_v1.json --terms config/terms_v1.json`
- [ ] Ad-hoc query: `python -m src.main query "MCP Runtime"`

### Out of Scope (Phase 2 — Productize)
- Web UI / dashboard
- Scheduled recurring runs (cron / cloud functions)
- Historical trend visualization
- Postgres / Supabase migration
- Multi-user access / auth
- CI/CD pipeline
- Notification system (Slack alerts when rankings change)

---

## 9. Dependencies

```
fastapi
uvicorn
httpx                  # async HTTP client for all API calls
python-dotenv          # .env loading
openai                 # OpenAI SDK
google-generativeai    # Gemini SDK
anthropic              # Anthropic SDK
pydantic               # data validation
aiosqlite              # async SQLite
```

---

## 10. Open Items

| # | Item | Owner | Status |
|---|---|---|---|
| 1 | Provide competitor list | Tyler | ⏳ Pending |
| 2 | Provide model prompt set (v1) | Tyler | ⏳ Pending |
| 3 | Provide search term set (v1) | Tyler | ⏳ Pending |
| 4 | Set up API keys (.env) | Tyler | ⏳ Pending |
| 5 | Review scoring methodology | Tyler + Jonnel | ⏳ Pending |

---

## 11. How to Use This Doc in Claude Code

Paste or reference this file at the start of a Claude Code session:

```bash
# In your project root
claude "Read BUCKET1_SPEC.md and scaffold the project structure. 
Start by implementing the input layer and persistence layer, 
then move to the processing layer (models + search). 
I'll provide the competitor list and prompt/term configs separately."
```

Once Tyler provides inputs, drop them into `config/` as JSON files matching the schemas in Section 3.