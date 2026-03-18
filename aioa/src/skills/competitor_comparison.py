"""Competitor Comparison — Build head-to-head comparison matrix."""

from __future__ import annotations

from typing import Any


def build_comparison_matrix(
    aio_aggregates: list[dict[str, int]],
    seo_aggregates: list[dict[str, int]],
    target: str,
    competitors: list[str],
) -> dict[str, Any]:
    """
    Build a head-to-head comparison matrix across all prompts/terms.

    Args:
        aio_aggregates: List of aggregate score dicts from AIO analysis,
                        each is {company_name: score}.
        seo_aggregates: List of aggregate score dicts from SEO analysis,
                        each is {company_name: score}.
        target: Target company name.
        competitors: List of competitor names.

    Returns:
        {
            "companies": ["Arcade", "Composio", ...],
            "aio_avg_scores": {"Arcade": 72, "Composio": 65, ...},
            "seo_avg_scores": {"Arcade": 45, "Composio": 55, ...},
            "combined_avg_scores": {"Arcade": 58, "Composio": 60, ...},
            "head_to_head": {
                "Arcade_vs_Composio": {
                    "aio": {"Arcade": 72, "Composio": 65, "winner": "Arcade"},
                    "seo": {"Arcade": 45, "Composio": 55, "winner": "Composio"},
                    "combined": {"Arcade": 58, "Composio": 60, "winner": "Composio"},
                },
                ...
            },
            "rankings": {
                "aio": ["Arcade", "Composio", ...],
                "seo": ["Composio", "Arcade", ...],
                "combined": ["Composio", "Arcade", ...],
            }
        }
    """
    all_companies = [target] + competitors

    # Calculate average scores
    aio_avg = _average_scores(aio_aggregates, all_companies)
    seo_avg = _average_scores(seo_aggregates, all_companies)
    combined_avg: dict[str, int | None] = {}
    for company in all_companies:
        present = [s for s in [aio_avg.get(company), seo_avg.get(company)] if s is not None]
        combined_avg[company] = round(sum(present) / len(present)) if present else None

    # Build head-to-head matchups (target vs each competitor)
    head_to_head: dict[str, Any] = {}
    for comp in competitors:
        key = f"{target}_vs_{comp}"
        h2h: dict[str, Any] = {}

        for label, scores in [("aio", aio_avg), ("seo", seo_avg), ("combined", combined_avg)]:
            t_score = scores.get(target)
            c_score = scores.get(comp)
            if t_score is None and c_score is None:
                winner = None
            elif t_score is None:
                winner = comp
            elif c_score is None:
                winner = target
            else:
                winner = target if t_score >= c_score else comp
            h2h[label] = {target: t_score, comp: c_score, "winner": winner}

        head_to_head[key] = h2h

    def _sort_key(c: str, scores: dict[str, int | None]) -> int:
        v = scores.get(c)
        return v if v is not None else -1

    # Rankings by category
    rankings = {
        "aio": sorted(all_companies, key=lambda c: _sort_key(c, aio_avg), reverse=True),
        "seo": sorted(all_companies, key=lambda c: _sort_key(c, seo_avg), reverse=True),
        "combined": sorted(all_companies, key=lambda c: _sort_key(c, combined_avg), reverse=True),
    }

    return {
        "companies": all_companies,
        "aio_avg_scores": aio_avg,
        "seo_avg_scores": seo_avg,
        "combined_avg_scores": combined_avg,
        "head_to_head": head_to_head,
        "rankings": rankings,
    }


def _average_scores(
    score_dicts: list[dict[str, int]],
    companies: list[str],
) -> dict[str, int | None]:
    """Compute average score per company across multiple items.

    Returns None for a company when no scores are available.
    """
    if not score_dicts:
        return dict.fromkeys(companies)

    totals: dict[str, list[int]] = {c: [] for c in companies}
    for scores in score_dicts:
        if scores is None:
            continue
        for company in companies:
            if company in scores and scores[company] is not None:
                totals[company].append(scores[company])

    return {
        company: round(sum(vals) / len(vals)) if vals else None for company, vals in totals.items()
    }
