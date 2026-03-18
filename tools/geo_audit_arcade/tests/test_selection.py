"""Tests for bounded exploration preset selection."""

from geo_audit_arcade.models import CandidatePage
from geo_audit_arcade.selection import (
    infer_section_key,
    infer_subdomain_key,
    normalize_candidate_url,
    select_candidate_pages,
)


class TestNormalizeCandidateUrl:
    def test_strips_trailing_slash(self):
        assert normalize_candidate_url("https://example.com/page/") == "https://example.com/page"

    def test_keeps_root_slash(self):
        assert normalize_candidate_url("https://example.com/") == "https://example.com/"

    def test_strips_query_and_fragment(self):
        assert (
            normalize_candidate_url("https://example.com/page?q=1#top")
            == "https://example.com/page"
        )


class TestInferSectionKey:
    def test_root_returns_none(self):
        assert infer_section_key("https://example.com/") is None

    def test_first_segment(self):
        assert infer_section_key("https://example.com/docs/api") == "docs"


class TestInferSubdomainKey:
    def test_basic(self):
        assert infer_subdomain_key("https://docs.example.com/page") == "docs.example.com"


class TestSelectCandidatePages:
    def _make_candidate(self, url: str, source: str, **kwargs):
        return CandidatePage(
            url=url,
            source=source,
            section_key=infer_section_key(url),
            subdomain_key=infer_subdomain_key(url),
            **kwargs,
        )

    def test_targets_always_selected(self):
        candidates = [
            self._make_candidate("https://example.com/", "target"),
            self._make_candidate("https://example.com/blog", "nav"),
        ]
        selected, summary = select_candidate_pages(candidates, "light")
        target_candidates = [c for c in selected if c.source == "target"]
        assert len(target_candidates) == 1
        assert target_candidates[0].selected is True

    def test_respects_page_budget(self):
        candidates = [
            self._make_candidate(f"https://example.com/page{i}", "nav") for i in range(20)
        ]
        selected, summary = select_candidate_pages(candidates, "light")
        selected_count = sum(1 for c in selected if c.selected)
        assert selected_count <= summary.representative_page_budget

    def test_presets_increase_budget(self):
        candidates = [self._make_candidate(f"https://example.com/p{i}", "nav") for i in range(50)]
        _, light_summary = select_candidate_pages(candidates, "light")
        _, exhaustive_summary = select_candidate_pages(candidates, "exhaustive")
        assert (
            exhaustive_summary.representative_page_budget > light_summary.representative_page_budget
        )

    def test_diversifies_sections(self):
        candidates = [
            self._make_candidate("https://example.com/docs/page1", "nav"),
            self._make_candidate("https://example.com/blog/post1", "nav"),
            self._make_candidate("https://example.com/docs/page2", "nav"),
            self._make_candidate("https://example.com/pricing", "nav"),
        ]
        selected, summary = select_candidate_pages(candidates, "standard")
        selected_sections = {c.section_key for c in selected if c.selected}
        assert len(selected_sections) >= 2
