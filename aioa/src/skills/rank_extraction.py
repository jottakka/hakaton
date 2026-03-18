"""Rank Extraction — Extract where each competitor's domain appears in SERP results."""

from __future__ import annotations

from typing import Any

# Map company names to known domain fragments for matching
_DOMAIN_HINTS: dict[str, list[str]] = {
    "Arcade": ["arcade.dev", "arcade-ai", "arcadeai"],
    "Composio": ["composio.dev", "composio"],
    "Workato": ["workato.com", "workato"],
    "Teleport": ["goteleport.com", "teleport"],
    "Kong": ["konghq.com", "kong"],
    "Mulesoft": ["mulesoft.com", "mulesoft"],
    "MintMCP": ["mintmcp", "mint-mcp"],
    "Merge": ["merge.dev", "merge"],
}


def _url_matches_company(url: str, company: str) -> bool:
    """Check if a URL belongs to a given company based on domain hints."""
    url_lower = url.lower()
    hints = _DOMAIN_HINTS.get(company, [company.lower()])
    return any(hint in url_lower for hint in hints)


def extract_rankings(
    search_results: list[dict[str, Any]],
    target: str,
    competitors: list[str],
) -> dict[str, Any]:
    """
    Extract where each company's domain appears in search results.

    Args:
        search_results: List of {position, title, url, snippet} dicts.
        target: The target company name.
        competitors: List of competitor names.

    Returns:
        {
            "Arcade": {"position": 3, "url": "https://arcade.dev/...", "snippet": "..."},
            "Composio": {"position": 1, "url": "https://composio.dev/...", "snippet": "..."},
            "Workato": {"position": None, "url": None, "snippet": None},
            ...
        }
    """
    all_companies = [target] + competitors
    rankings: dict[str, Any] = {}

    for company in all_companies:
        found = False
        for result in search_results:
            url = result.get("url", "")
            title = result.get("title", "")
            # Match by URL domain or by company name appearing in the title
            if _url_matches_company(url, company) or company.lower() in title.lower():
                rankings[company] = {
                    "position": result["position"],
                    "url": url,
                    "snippet": result.get("snippet", ""),
                }
                found = True
                break  # Take first (highest) match
        if not found:
            rankings[company] = {
                "position": None,
                "url": None,
                "snippet": None,
            }

    return rankings
