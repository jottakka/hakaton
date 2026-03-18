"""Tests for the input layer — config loading and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.input_layer import (
    CompetitorConfig,
    Prompt,
    PromptSet,
    SearchTerm,
    TermSet,
    load_competitors,
    load_prompts,
    load_terms,
)


class TestCompetitorConfig:
    def test_basic_creation(self):
        config = CompetitorConfig(target="Arcade", competitors=["Composio", "Kong"])
        assert config.target == "Arcade"
        assert len(config.competitors) == 2

    def test_all_companies(self):
        config = CompetitorConfig(target="Arcade", competitors=["Composio", "Kong"])
        assert config.all_companies == ["Arcade", "Composio", "Kong"]

    def test_empty_competitors(self):
        config = CompetitorConfig(target="Arcade", competitors=[])
        assert config.all_companies == ["Arcade"]


class TestPromptModels:
    def test_prompt_creation(self):
        p = Prompt(id="p001", text="Test prompt", category="general")
        assert p.id == "p001"
        assert p.expected_winner == "Arcade"  # default

    def test_prompt_set(self):
        ps = PromptSet(
            prompt_set_id="v1",
            prompts=[
                Prompt(id="p001", text="Test", category="general"),
                Prompt(id="p002", text="Test 2", category="mcp_runtime"),
            ],
        )
        assert len(ps.prompts) == 2
        assert ps.prompt_set_id == "v1"

    def test_empty_prompt_set(self):
        ps = PromptSet(prompt_set_id="empty")
        assert ps.prompts == []


class TestTermModels:
    def test_term_creation(self):
        t = SearchTerm(id="s001", query="best MCP runtime")
        assert t.id == "s001"
        assert t.expected_winner == "Arcade"

    def test_term_set(self):
        ts = TermSet(
            term_set_id="v1",
            terms=[SearchTerm(id="s001", query="test query")],
        )
        assert len(ts.terms) == 1


class TestLoadFunctions:
    def test_load_competitors(self, tmp_path: Path):
        data = {"target": "Arcade", "competitors": ["Composio", "Workato"]}
        path = tmp_path / "competitors.json"
        path.write_text(json.dumps(data))
        config = load_competitors(path)
        assert config.target == "Arcade"
        assert "Composio" in config.competitors

    def test_load_prompts(self, tmp_path: Path):
        data = {
            "prompt_set_id": "test",
            "created_at": "2026-03-17",
            "prompts": [
                {"id": "p001", "text": "Hello", "category": "general"},
            ],
        }
        path = tmp_path / "prompts.json"
        path.write_text(json.dumps(data))
        ps = load_prompts(path)
        assert ps.prompt_set_id == "test"
        assert len(ps.prompts) == 1

    def test_load_terms(self, tmp_path: Path):
        data = {
            "term_set_id": "test",
            "created_at": "2026-03-17",
            "terms": [
                {"id": "s001", "query": "test search", "category": "general"},
            ],
        }
        path = tmp_path / "terms.json"
        path.write_text(json.dumps(data))
        ts = load_terms(path)
        assert ts.term_set_id == "test"
        assert len(ts.terms) == 1

    def test_load_competitors_invalid(self, tmp_path: Path):
        path = tmp_path / "bad.json"
        path.write_text('{"bad": "data"}')
        with pytest.raises((ValueError, KeyError)):
            load_competitors(path)
