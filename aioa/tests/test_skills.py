"""Tests for skills helper logic used in analysis."""

from __future__ import annotations

from src.skills.competitor_comparison import build_comparison_matrix
from src.skills.gap_analysis import find_gaps
from src.skills.mention_detection import detect_mentions
from src.skills.rank_extraction import extract_rankings
from src.skills.score_calculation import (
    calculate_aio_score,
    calculate_scores_for_prompt,
    calculate_scores_for_term,
    calculate_seo_score,
)


def test_detect_mentions_finds_target_and_competitor():
    text = "Arcade is a leading MCP gateway. Composio is also strong."
    mentions = detect_mentions(text, "Arcade", ["Composio", "Kong"])
    assert mentions["Arcade"]["mentioned"] is True
    assert mentions["Composio"]["mentioned"] is True
    assert mentions["Kong"]["mentioned"] is False
    assert mentions["Arcade"]["position"] in {"first", "early"}


def test_detect_mentions_does_not_match_company_inside_larger_word():
    """'Merge' must not match inside the word 'merge' when it appears as a common verb."""
    text = "We should merge configs before deploy."
    mentions = detect_mentions(text, "Arcade", ["Merge"])
    assert mentions["Merge"]["mentioned"] is False


def test_detect_mentions_handles_punctuation_around_company_name():
    """Company names adjacent to punctuation should still be detected."""
    text = "Arcade, Composio, and Merge are all mentioned here."
    mentions = detect_mentions(text, "Arcade", ["Composio", "Merge"])
    assert mentions["Merge"]["mentioned"] is True
    assert mentions["Composio"]["mentioned"] is True


def test_detect_mentions_case_sensitive_proper_noun():
    """Company names use case-sensitive matching because they are proper nouns.
    'Arcade' matches 'Arcade' but not 'arcade' when used as a common noun."""
    text = "Visit Arcade for the best tools. The arcade down the street is fun."
    mentions = detect_mentions(text, "Arcade", [])
    assert mentions["Arcade"]["mentioned"] is True
    assert mentions["Arcade"]["position"] == "first"


def test_extract_rankings_matches_by_url_and_title():
    results = [
        {"position": 1, "title": "Composio docs", "url": "https://composio.dev/docs", "snippet": "..."},
        {"position": 2, "title": "Best MCP gateway Arcade", "url": "https://example.com/blog", "snippet": "..."},
    ]
    rankings = extract_rankings(results, "Arcade", ["Composio", "Kong"])
    assert rankings["Composio"]["position"] == 1
    assert rankings["Arcade"]["position"] == 2
    assert rankings["Kong"]["position"] is None


def test_calculate_aio_score_and_seo_score():
    assert calculate_aio_score({"mentioned": False}) == 0
    assert calculate_aio_score({"mentioned": True, "position": "first", "sentiment": "positive"}) == 90
    assert calculate_seo_score({"position": None}) == 0
    assert calculate_seo_score({"position": 1}) == 100
    # Steep curve: pos 3 = 60 (from config [100, 80, 60, 40, 30, 20, 15, 10, 5, 2])
    assert calculate_seo_score({"position": 3}) == 60


def test_calculate_scores_for_prompt_aggregates_across_models():
    mentions_by_model = {
        "openai": {
            "Arcade": {"mentioned": True, "position": "first", "sentiment": "positive"},
            "Composio": {"mentioned": True, "position": "middle", "sentiment": "neutral"},
        },
        "gemini": {
            "Arcade": {"mentioned": True, "position": "early", "sentiment": "neutral"},
            "Composio": {"mentioned": False},
        },
    }
    scores = calculate_scores_for_prompt(mentions_by_model, "Arcade", ["Composio"])
    assert set(scores) == {"by_model", "aggregate"}
    assert scores["by_model"]["openai"]["Arcade"] == 90
    assert scores["aggregate"]["Arcade"] > scores["aggregate"]["Composio"]


def test_calculate_scores_for_term_aggregates_across_engines():
    rankings_by_engine = {
        "google": {
            "Arcade": {"position": 2},
            "Composio": {"position": 1},
        },
        "bing": {
            "Arcade": {"position": 1},
            "Composio": {"position": 4},
        },
    }
    scores = calculate_scores_for_term(rankings_by_engine, "Arcade", ["Composio"])
    assert set(scores) == {"by_engine", "aggregate"}
    # Steep curve: pos 2 = 80, pos 4 = 40
    assert scores["by_engine"]["google"]["Arcade"] == 80
    assert scores["by_engine"]["bing"]["Composio"] == 40


def test_find_gaps_flags_expected_target_losses():
    gaps = find_gaps(
        [
            {
                "id": "p001",
                "type": "aio",
                "text": "best mcp gateway",
                "expected_winner": "Arcade",
                "aggregate": {"Arcade": 30, "Composio": 88},
            },
            {
                "id": "s001",
                "type": "seo",
                "text": "mcp auth",
                "expected_winner": "Composio",
                "aggregate": {"Arcade": 60, "Composio": 70},
            },
        ],
        target="Arcade",
    )
    assert len(gaps) == 1
    assert gaps[0]["id"] == "p001"
    assert "AIO gap" in gaps[0]["recommendation"]


def test_build_comparison_matrix_returns_rankings():
    matrix = build_comparison_matrix(
        aio_aggregates=[{"Arcade": 70, "Composio": 60}, {"Arcade": 80, "Composio": 40}],
        seo_aggregates=[{"Arcade": 30, "Composio": 90}],
        target="Arcade",
        competitors=["Composio"],
    )
    assert matrix["aio_avg_scores"]["Arcade"] == 75
    assert matrix["seo_avg_scores"]["Composio"] == 90
    assert matrix["head_to_head"]["Arcade_vs_Composio"]["seo"]["winner"] == "Composio"
    assert matrix["rankings"]["aio"][0] == "Arcade"

