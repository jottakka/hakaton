"""Gap Analysis — Compare scores against expected winners, flag gaps."""

from __future__ import annotations

from typing import Any


def find_gaps(
    scored_items: list[dict[str, Any]],
    target: str,
) -> list[dict[str, Any]]:
    """
    Identify items where the target was expected to win but didn't.

    Args:
        scored_items: List of dicts, each containing:
            - "id": prompt or term id
            - "type": "aio" or "seo"
            - "text": prompt text or search query
            - "expected_winner": company name
            - "aggregate": dict of {company: score}

    Returns:
        List of gap report entries:
        [
            {
                "id": "p003",
                "type": "aio",
                "text": "What is the best MCP runtime?",
                "expected": "Arcade",
                "actual_winner": "CompetitorX",
                "arcade_score": 30,
                "winner_score": 88,
                "gap_size": 58,
                "recommendation": "..."
            }
        ]
    """
    gaps: list[dict[str, Any]] = []

    for item in scored_items:
        expected = item.get("expected_winner", target)
        aggregate = item.get("aggregate", {})

        if not aggregate:
            continue

        # Find the actual winner (highest score)
        actual_winner = max(aggregate, key=lambda k: aggregate[k])
        winner_score = aggregate[actual_winner]
        target_score = aggregate.get(target, 0)

        # Only flag as a gap if the expected winner is the target and it didn't win
        if expected == target and actual_winner != target and winner_score > target_score:
            gap_size = winner_score - target_score
            recommendation = _generate_recommendation(
                item_type=item.get("type", "unknown"),
                text=item.get("text", ""),
                actual_winner=actual_winner,
                target=target,
                gap_size=gap_size,
            )
            gaps.append({
                "id": item["id"],
                "type": item.get("type", "unknown"),
                "text": item.get("text", ""),
                "expected": target,
                "actual_winner": actual_winner,
                "arcade_score": target_score,
                "winner_score": winner_score,
                "gap_size": gap_size,
                "recommendation": recommendation,
            })

    # Sort by gap size descending (biggest gaps first)
    gaps.sort(key=lambda g: g["gap_size"], reverse=True)
    return gaps


def _generate_recommendation(
    item_type: str,
    text: str,
    actual_winner: str,
    target: str,
    gap_size: int,
) -> str:
    """Generate a human-readable recommendation for closing a gap."""
    severity = "critical" if gap_size >= 50 else "moderate" if gap_size >= 25 else "minor"

    if item_type == "aio":
        return (
            f"{severity.title()} AIO gap: {actual_winner} outscores {target} by {gap_size} points "
            f"for \"{text}\". Consider creating more content and documentation around this topic "
            f"to improve AI model awareness of {target}."
        )
    elif item_type == "seo":
        return (
            f"{severity.title()} SEO gap: {actual_winner} outranks {target} by {gap_size} points "
            f"for \"{text}\". Consider targeted SEO content, backlink building, and landing page "
            f"optimization for this query."
        )
    else:
        return (
            f"{severity.title()} gap: {actual_winner} leads {target} by {gap_size} points "
            f"for \"{text}\"."
        )
