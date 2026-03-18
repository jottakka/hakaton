"""Tests for pure extraction helpers using HTML fixtures."""

from pathlib import Path
from urllib.parse import urlparse

import pytest

from geo_audit_local_mcp.extraction import (
    compare_title_h1,
    extract_canonical,
    extract_domains_from_links,
    extract_first_200_words,
    extract_h1,
    extract_headings,
    extract_internal_links,
    extract_json_ld,
    extract_meta_description,
    extract_open_graph,
    extract_title,
    parse_html,
    parse_robots_sitemaps,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def homepage_soup():
    html = (FIXTURES / "homepage.html").read_text()
    return parse_html(html)


@pytest.fixture
def jsonld_soup():
    html = (FIXTURES / "with-jsonld.html").read_text()
    return parse_html(html)


@pytest.fixture
def no_metadata_soup():
    html = (FIXTURES / "no-metadata.html").read_text()
    return parse_html(html)


class TestTitleExtraction:
    def test_extracts_title(self, homepage_soup):
        assert extract_title(homepage_soup) == "Acme Platform - Build AI Agents Fast"

    def test_no_title(self, no_metadata_soup):
        assert extract_title(no_metadata_soup) is None


class TestMetaDescription:
    def test_extracts_description(self, homepage_soup):
        desc = extract_meta_description(homepage_soup)
        assert desc is not None
        assert "build, deploy, and manage AI agents" in desc

    def test_no_description(self, no_metadata_soup):
        assert extract_meta_description(no_metadata_soup) is None


class TestCanonical:
    def test_extracts_canonical(self, homepage_soup):
        assert extract_canonical(homepage_soup) == "https://www.acme.dev/"

    def test_no_canonical(self, no_metadata_soup):
        assert extract_canonical(no_metadata_soup) is None


class TestOpenGraph:
    def test_extracts_og_tags(self, homepage_soup):
        og = extract_open_graph(homepage_soup)
        assert og.og_title == "Acme Platform"
        assert og.og_description == "Build AI agents with Acme"
        assert og.og_type == "website"
        assert og.og_image == "https://www.acme.dev/og-image.png"

    def test_no_og_tags(self, no_metadata_soup):
        og = extract_open_graph(no_metadata_soup)
        assert og.og_title is None
        assert og.og_description is None


class TestHeadings:
    def test_extracts_headings(self, homepage_soup):
        headings = extract_headings(homepage_soup)
        h1s = [h for h in headings if h.level == 1]
        h2s = [h for h in headings if h.level == 2]
        h3s = [h for h in headings if h.level == 3]
        assert len(h1s) == 1
        assert h1s[0].text == "Build AI Agents Fast"
        assert len(h2s) == 3
        assert len(h3s) == 1

    def test_no_headings(self, no_metadata_soup):
        headings = extract_headings(no_metadata_soup)
        assert headings == []


class TestH1:
    def test_extracts_h1(self, homepage_soup):
        assert extract_h1(homepage_soup) == "Build AI Agents Fast"

    def test_no_h1(self, no_metadata_soup):
        assert extract_h1(no_metadata_soup) is None


class TestJsonLd:
    def test_extracts_json_ld_types(self, jsonld_soup):
        entries = extract_json_ld(jsonld_soup)
        assert len(entries) == 2
        all_types = []
        for e in entries:
            all_types.extend(e.types)
        assert "Organization" in all_types
        assert "SoftwareApplication" in all_types

    def test_no_json_ld(self, homepage_soup):
        entries = extract_json_ld(homepage_soup)
        assert entries == []

    def test_snippet_present(self, jsonld_soup):
        entries = extract_json_ld(jsonld_soup)
        assert entries[0].raw_snippet is not None
        assert "@context" in entries[0].raw_snippet


class TestTitleH1Comparison:
    def test_matching(self):
        match, sim = compare_title_h1("Hello World", "Hello World")
        assert match is True
        assert sim == 1.0

    def test_different(self):
        match, sim = compare_title_h1(
            "Acme Platform - Build AI Agents Fast",
            "Build AI Agents Fast",
        )
        assert match is False
        assert sim is not None
        assert 0.5 < sim < 1.0

    def test_none_inputs(self):
        match, sim = compare_title_h1(None, "Hello")
        assert match is None
        assert sim is None

    def test_case_insensitive(self):
        match, sim = compare_title_h1("HELLO", "hello")
        assert match is True
        assert sim == 1.0


class TestFirst200Words:
    def test_extracts_words(self, homepage_soup):
        text = extract_first_200_words(homepage_soup)
        assert text is not None
        words = text.split()
        assert len(words) <= 200
        assert "Acme" in text

    def test_no_body(self):
        soup = parse_html("<html><head></head></html>")
        assert extract_first_200_words(soup) is None

    def test_strips_scripts(self, homepage_soup):
        text = extract_first_200_words(homepage_soup)
        assert text is not None
        assert "<script" not in text


class TestDomainDiscovery:
    def test_discovers_subdomains(self, homepage_soup):
        domains = extract_domains_from_links(homepage_soup, "acme.dev")
        assert "docs.acme.dev" in domains
        assert "blog.acme.dev" in domains
        assert "www.acme.dev" in domains
        assert "api.acme.dev" in domains


class TestInternalLinks:
    def test_returns_same_origin_urls(self):
        html = (FIXTURES / "hub-page.html").read_text()
        soup = parse_html(html)
        links = extract_internal_links(soup, "https://docs.acme.dev/")
        for link in links:
            assert urlparse(link).netloc == "docs.acme.dev"

    def test_excludes_base_url(self):
        html = (FIXTURES / "hub-page.html").read_text()
        soup = parse_html(html)
        links = extract_internal_links(soup, "https://docs.acme.dev/")
        assert "https://docs.acme.dev" not in links

    def test_excludes_utility_paths(self):
        html = (FIXTURES / "hub-page.html").read_text()
        soup = parse_html(html)
        links = extract_internal_links(soup, "https://docs.acme.dev/")
        link_set = set(links)
        assert "https://docs.acme.dev/sitemap.xml" not in link_set
        assert "https://docs.acme.dev/robots.txt" not in link_set
        assert "https://docs.acme.dev/assets/logo.png" not in link_set

    def test_excludes_external_links(self):
        html = (FIXTURES / "hub-page.html").read_text()
        soup = parse_html(html)
        links = extract_internal_links(soup, "https://docs.acme.dev/")
        assert not any("github.com" in link for link in links)

    def test_deduplicates(self):
        """quickstart appears in nav AND main — should appear once."""
        html = (FIXTURES / "hub-page.html").read_text()
        soup = parse_html(html)
        links = extract_internal_links(soup, "https://docs.acme.dev/")
        quickstart_count = sum(1 for lnk in links if lnk.endswith("/quickstart"))
        assert quickstart_count == 1

    def test_priority_ordering(self):
        """Nav/main links appear before footer links."""
        html = (FIXTURES / "hub-page.html").read_text()
        soup = parse_html(html)
        links = extract_internal_links(soup, "https://docs.acme.dev/")
        quickstart_idx = next((i for i, lnk in enumerate(links) if "/quickstart" in lnk), None)
        changelog_idx = next((i for i, lnk in enumerate(links) if "/changelog" in lnk), None)
        assert quickstart_idx is not None
        assert changelog_idx is not None
        assert quickstart_idx < changelog_idx

    def test_does_not_mutate_soup(self):
        """extract_internal_links must not remove any tags from the soup."""
        html = (FIXTURES / "hub-page.html").read_text()
        soup = parse_html(html)
        extract_internal_links(soup, "https://docs.acme.dev/")
        assert extract_title(soup) == "Acme Docs - Home"

    def test_resolves_relative_hrefs(self):
        """Relative hrefs like /guide are resolved to absolute URLs."""
        html = """<html><body>
            <nav><a href="/guide">Guide</a><a href="/reference">Reference</a></nav>
        </body></html>"""
        soup = parse_html(html)
        links = extract_internal_links(soup, "https://docs.acme.dev/")
        assert "https://docs.acme.dev/guide" in links
        assert "https://docs.acme.dev/reference" in links


class TestRobotsSitemapParsing:
    def test_parses_sitemaps(self):
        robots = (FIXTURES / "robots.txt").read_text()
        sitemaps = parse_robots_sitemaps(robots)
        assert len(sitemaps) == 2
        assert "https://www.acme.dev/sitemap.xml" in sitemaps
        assert "https://www.acme.dev/sitemap-blog.xml" in sitemaps

    def test_empty_robots(self):
        assert parse_robots_sitemaps("") == []

    def test_case_insensitive(self):
        sitemaps = parse_robots_sitemaps("SITEMAP: https://x.com/sitemap.xml")
        assert len(sitemaps) == 1
