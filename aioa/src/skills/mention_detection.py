"""Mention Detection — Analyze LLM response text for mentions of target + competitors."""

from __future__ import annotations

import re
from typing import Any


def _find_company_match(text: str, company: str) -> re.Match[str] | None:
    """Return the first boundary-aware match for a company name.

    Uses case-sensitive matching because company names are proper nouns.
    This prevents common words like 'merge' from triggering a false-positive
    match for the company 'Merge'.
    """
    pattern = re.compile(rf"(?<!\w){re.escape(company)}(?!\w)")
    return pattern.search(text)


def _find_mention_position(text: str, company: str) -> str | None:
    """Return rough position descriptor: 'first', 'early', 'middle', 'late', 'last'."""
    m = _find_company_match(text, company)
    if m is None:
        return None
    idx = m.start()
    ratio = idx / max(len(text), 1)
    if ratio < 0.1:
        return "first"
    elif ratio < 0.3:
        return "early"
    elif ratio < 0.6:
        return "middle"
    elif ratio < 0.85:
        return "late"
    else:
        return "last"


def _extract_context_snippet(text: str, company: str, window: int = 120) -> str:
    """Extract a snippet of text around the first mention of a company."""
    m = _find_company_match(text, company)
    if m is None:
        return ""
    idx = m.start()
    start = max(0, idx - window // 2)
    end = min(len(text), idx + len(company) + window // 2)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


def _estimate_sentiment(snippet: str, company: str) -> str:
    """
    Estimate sentiment of the mention context as positive/negative/neutral.
    Uses keyword heuristics. A real implementation could use an LLM call.
    """
    lower = snippet.lower()
    positive_signals = [
        "best",
        "leading",
        "powerful",
        "excellent",
        "recommended",
        "top",
        "innovative",
        "robust",
        "reliable",
        "popular",
        "strong",
        "great",
        "superior",
        "advanced",
        "comprehensive",
    ]
    negative_signals = [
        "limited",
        "lacks",
        "slow",
        "expensive",
        "complex",
        "difficult",
        "poor",
        "weakness",
        "drawback",
        "issue",
        "problem",
        "concern",
        "downside",
        "behind",
        "inferior",
    ]
    pos_count = sum(1 for w in positive_signals if w in lower)
    neg_count = sum(1 for w in negative_signals if w in lower)
    if pos_count > neg_count:
        return "positive"
    elif neg_count > pos_count:
        return "negative"
    return "neutral"


def detect_mentions(
    response_text: str,
    target: str,
    competitors: list[str],
) -> dict[str, Any]:
    """
    Analyze an LLM response for mentions of the target and each competitor.

    Returns:
        {
            "Arcade": {
                "mentioned": True,
                "position": "first",
                "sentiment": "positive",
                "context_snippet": "...Arcade is a leading..."
            },
            "Composio": {
                "mentioned": False,
                "position": None,
                "sentiment": None,
                "context_snippet": ""
            },
            ...
        }
    """
    all_companies = [target] + competitors
    mentions: dict[str, Any] = {}

    for company in all_companies:
        found = _find_company_match(response_text, company) is not None

        if found:
            position = _find_mention_position(response_text, company)
            snippet = _extract_context_snippet(response_text, company)
            sentiment = _estimate_sentiment(snippet, company)
        else:
            position = None
            snippet = ""
            sentiment = None

        mentions[company] = {
            "mentioned": found,
            "position": position,
            "sentiment": sentiment,
            "context_snippet": snippet,
        }

    return mentions
