"""Score Calculation — Normalize mention + rank data into 0-100 scores."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "scoring_matrix.json"
_matrix: dict[str, Any] | None = None


def _load_matrix() -> dict[str, Any]:
    global _matrix
    if _matrix is None:
        _matrix = json.loads(_CONFIG_PATH.read_text())
    return _matrix


def load_scoring_matrix(path: str | Path | None = None) -> dict[str, Any]:
    """Load the scoring matrix, optionally from a custom path (useful for tests)."""
    if path is not None:
        return json.loads(Path(path).read_text())
    return _load_matrix()


def calculate_aio_score(mention_data: dict[str, Any], matrix: dict[str, Any] | None = None) -> int:
    """
    Calculate a 0-100 AIO visibility score from mention detection data.
    Weights are read from the scoring matrix config.
    """
    m = (matrix or _load_matrix())["aio"]

    if not mention_data.get("mentioned"):
        return 0

    score = m["base_mentioned"]

    position = mention_data.get("position")
    score += m["position"].get(position, 0)

    sentiment = mention_data.get("sentiment")
    score += m["sentiment"].get(sentiment, 0)

    return min(score, m["max_score"])


def calculate_seo_score(rank_data: dict[str, Any], matrix: dict[str, Any] | None = None) -> int:
    """
    Calculate a 0-100 SEO visibility score from rank extraction data.
    Uses the position_scores array from the scoring matrix (steeper drop-off).
    """
    m = (matrix or _load_matrix())["seo"]
    position_scores: list[int] = m["position_scores"]

    position = rank_data.get("position")
    if position is None or position < 1:
        return m["not_found"]

    idx = position - 1
    if idx < len(position_scores):
        return position_scores[idx]
    return m["not_found"]


def calculate_scores_for_prompt(
    mentions_by_model: dict[str, dict[str, Any]],
    target: str,
    competitors: list[str],
    matrix: dict[str, Any] | None = None,
) -> dict[str, dict[str, int]]:
    """
    Calculate AIO scores for all companies across all models for a single prompt.

    Returns:
        {
            "by_model": {"openai": {"Arcade": 85, "Composio": 40, ...}, ...},
            "aggregate": {"Arcade": 78, "Composio": 42, ...}
        }
    """
    mat = matrix or _load_matrix()
    all_companies = [target] + competitors
    by_model: dict[str, dict[str, int]] = {}
    totals: dict[str, list[int]] = {c: [] for c in all_companies}

    for model_name, mentions in mentions_by_model.items():
        by_model[model_name] = {}
        for company in all_companies:
            company_mention = mentions.get(company, {"mentioned": False})
            score = calculate_aio_score(company_mention, matrix=mat)
            by_model[model_name][company] = score
            totals[company].append(score)

    aggregate = {}
    for company in all_companies:
        scores = totals[company]
        aggregate[company] = round(sum(scores) / max(len(scores), 1))

    return {"by_model": by_model, "aggregate": aggregate}


def calculate_scores_for_term(
    rankings_by_engine: dict[str, dict[str, Any]],
    target: str,
    competitors: list[str],
    matrix: dict[str, Any] | None = None,
) -> dict[str, dict[str, int]]:
    """
    Calculate SEO scores for all companies across all engines for a single term.

    Returns:
        {
            "by_engine": {"google": {"Arcade": 60, ...}, ...},
            "aggregate": {"Arcade": 55, ...}
        }
    """
    mat = matrix or _load_matrix()
    all_companies = [target] + competitors
    by_engine: dict[str, dict[str, int]] = {}
    totals: dict[str, list[int]] = {c: [] for c in all_companies}

    for engine_name, rankings in rankings_by_engine.items():
        by_engine[engine_name] = {}
        for company in all_companies:
            company_rank = rankings.get(company, {"position": None})
            score = calculate_seo_score(company_rank, matrix=mat)
            by_engine[engine_name][company] = score
            totals[company].append(score)

    aggregate = {}
    for company in all_companies:
        scores = totals[company]
        aggregate[company] = round(sum(scores) / max(len(scores), 1))

    return {"by_engine": by_engine, "aggregate": aggregate}
