"""Bounded exploration preset helpers."""

from __future__ import annotations

from typing import TypedDict
from urllib.parse import urlsplit, urlunsplit

from .models import CandidatePage, CoveragePreset, CoverageSummary


class PresetConfig(TypedDict):
    pages: int
    sections: int
    subdomains: int
    per_lane_cap: int


PRESET_CONFIG: dict[CoveragePreset, PresetConfig] = {
    "light": {"pages": 4, "sections": 2, "subdomains": 1, "per_lane_cap": 2},
    "standard": {"pages": 8, "sections": 4, "subdomains": 2, "per_lane_cap": 3},
    "deep": {"pages": 12, "sections": 6, "subdomains": 3, "per_lane_cap": 4},
    "exhaustive": {"pages": 18, "sections": 8, "subdomains": 4, "per_lane_cap": 6},
}

REQUIRED_SOURCES = {"target", "root"}
SOURCE_PRIORITY = {
    "target": 8,
    "root": 7,
    "sitemap": 6,
    "llms": 5,
    "nav": 4,
    "footer": 3,
    "path_cluster": 2,
    "redirect": 1,
    "manual": 0,
}


def get_preset_config(preset: CoveragePreset) -> PresetConfig:
    """Return a copy of the bounded config for *preset*."""

    return dict(PRESET_CONFIG[preset])


def normalize_candidate_url(url: str) -> str:
    """Normalize a candidate URL for deduplication."""

    split = urlsplit(url)
    path = split.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((split.scheme, split.netloc, path, "", ""))


def infer_section_key(url: str) -> str | None:
    """Infer a coarse section key from the first path segment."""

    path = urlsplit(url).path.strip("/")
    if not path:
        return None
    return path.split("/", 1)[0]


def infer_subdomain_key(url: str) -> str | None:
    """Use the hostname as the stable subdomain key."""

    return urlsplit(url).hostname


def select_candidate_pages(
    candidate_pages: list[CandidatePage],
    preset: CoveragePreset,
    *,
    page_budget_override: int | None = None,
) -> tuple[list[CandidatePage], CoverageSummary]:
    """Select a bounded representative set while preserving coverage diversity."""

    config = get_preset_config(preset)
    page_budget = config["pages"]
    if page_budget_override is not None:
        page_budget = max(0, min(page_budget, page_budget_override))

    required_candidates: list[CandidatePage] = []
    exploratory_candidates: list[CandidatePage] = []
    for candidate in candidate_pages:
        if candidate.source in REQUIRED_SOURCES:
            required_candidates.append(candidate.model_copy(update={"selected": True}))
        else:
            exploratory_candidates.append(candidate.model_copy(update={"selected": False}))

    seen_sections: set[str] = set()
    seen_subdomains: set[str] = set()
    selected_indices: list[int] = []
    remaining: list[tuple[int, CandidatePage]] = list(enumerate(exploratory_candidates))

    while remaining and len(selected_indices) < page_budget:
        ranked = sorted(
            remaining,
            key=lambda item: _candidate_rank(
                item[0],
                item[1],
                seen_sections=seen_sections,
                seen_subdomains=seen_subdomains,
                section_budget=config["sections"],
                subdomain_budget=config["subdomains"],
            ),
            reverse=True,
        )
        index, candidate = ranked[0]
        selected_indices.append(index)
        if candidate.section_key and len(seen_sections) < config["sections"]:
            seen_sections.add(candidate.section_key)
        if candidate.subdomain_key and len(seen_subdomains) < config["subdomains"]:
            seen_subdomains.add(candidate.subdomain_key)
        remaining = [item for item in remaining if item[0] != index]

    selected_index_set = set(selected_indices)
    updated_exploratory = [
        candidate.model_copy(update={"selected": index in selected_index_set})
        for index, candidate in enumerate(exploratory_candidates)
    ]

    summary = CoverageSummary(
        preset=preset,
        representative_page_budget=page_budget,
        selected_page_count=len(selected_indices),
        section_budget=config["sections"],
        section_count=len(seen_sections),
        extra_subdomain_budget=config["subdomains"],
        subdomain_count=len(seen_subdomains),
        truncated=len(exploratory_candidates) > len(selected_indices),
    )
    return required_candidates + updated_exploratory, summary


def _candidate_rank(
    index: int,
    candidate: CandidatePage,
    *,
    seen_sections: set[str],
    seen_subdomains: set[str],
    section_budget: int,
    subdomain_budget: int,
) -> tuple[int, int, int, int]:
    new_section = int(
        candidate.section_key is not None
        and candidate.section_key not in seen_sections
        and len(seen_sections) < section_budget
    )
    new_subdomain = int(
        candidate.subdomain_key is not None
        and candidate.subdomain_key not in seen_subdomains
        and len(seen_subdomains) < subdomain_budget
    )
    source_score = SOURCE_PRIORITY[candidate.source]
    return (new_section, new_subdomain, source_score, -index)
