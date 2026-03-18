"""Input Layer — Load and validate config files (competitors, prompts, terms)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CompetitorConfig(BaseModel):
    """Target company plus the list of competitors to track."""

    target: str
    competitors: list[str]

    @property
    def all_companies(self) -> list[str]:
        """Return target + competitors as a single list."""
        return [self.target] + self.competitors


class Prompt(BaseModel):
    """A single model prompt for AIO benchmarking."""

    id: str
    text: str
    category: str = ""
    expected_winner: str = "Arcade"
    notes: str | None = None


class PromptSet(BaseModel):
    """A versioned set of prompts."""

    prompt_set_id: str
    created_at: str = ""
    prompts: list[Prompt] = Field(default_factory=list)


class SearchTerm(BaseModel):
    """A single search term for SEO benchmarking."""

    id: str
    query: str
    category: str = ""
    expected_winner: str = "Arcade"
    notes: str | None = None


class TermSet(BaseModel):
    """A versioned set of search terms."""

    term_set_id: str
    created_at: str = ""
    terms: list[SearchTerm] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def load_competitors(path: str | Path = "config/competitors.json") -> CompetitorConfig:
    """Load and validate the competitor config file."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return CompetitorConfig.model_validate(raw)


def load_prompts(path: str | Path = "config/prompts_v1.json") -> PromptSet:
    """Load and validate a prompt set file."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return PromptSet.model_validate(raw)


def load_terms(path: str | Path = "config/terms_v1.json") -> TermSet:
    """Load and validate a term set file."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return TermSet.model_validate(raw)
