"""Tests for CollectGeoEvidence tool using mocked network calls."""

from pathlib import Path
from unittest.mock import patch

import pytest

from geo_audit_local_mcp.fetching import FetchResult
from geo_audit_local_mcp.models import ArtifactCheck, ArtifactStatus
from geo_audit_local_mcp.tools.collect_geo_evidence import (
    _get_base_domain,
    collect_geo_evidence,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_fetch_result(url, html_file=None, status=200, error=None):
    body = None
    if html_file and not error:
        body = (FIXTURES / html_file).read_text()
    return FetchResult(
        url=url,
        status_code=status if not error else None,
        final_url=None,
        body=body,
        error=error,
    )


def _mock_artifact_found(url):
    return ArtifactCheck(
        url=url,
        status=ArtifactStatus.FOUND,
        http_status=200,
        content_snippet="User-agent: *\nAllow: /",
    )


def _mock_artifact_not_found(url):
    return ArtifactCheck(
        url=url,
        status=ArtifactStatus.NOT_FOUND,
        http_status=404,
    )


@pytest.fixture
def mock_network():
    """Patch fetch_page and check_artifact to avoid real network calls."""
    with (
        patch("geo_audit_local_mcp.tools.collect_geo_evidence.fetch_page") as mock_fetch,
        patch("geo_audit_local_mcp.tools.collect_geo_evidence.check_artifact") as mock_check,
    ):
        yield mock_fetch, mock_check


class TestCollectGeoEvidence:
    @pytest.mark.asyncio
    async def test_single_url_returns_page_metadata(self, mock_network):
        mock_fetch, mock_check = mock_network
        mock_fetch.return_value = _mock_fetch_result(
            "https://www.acme.dev/", "homepage.html",
        )
        mock_check.side_effect = lambda url: (
            _mock_artifact_found(url) if "robots.txt" in url
            else _mock_artifact_not_found(url)
        )

        result = await collect_geo_evidence(
            ["https://www.acme.dev/"], max_related_pages=0,
        )

        assert result.target_urls == ["https://www.acme.dev/"]
        assert len(result.pages) == 1
        assert result.pages[0].title == "Acme Platform - Build AI Agents Fast"
        assert result.pages[0].h1_text == "Build AI Agents Fast"
        assert result.pages[0].meta_description is not None
        assert result.pages[0].canonical == "https://www.acme.dev/"
        assert result.pages[0].is_sampled is False

    @pytest.mark.asyncio
    async def test_discovers_subdomains(self, mock_network):
        mock_fetch, mock_check = mock_network
        mock_fetch.return_value = _mock_fetch_result(
            "https://www.acme.dev/", "homepage.html",
        )
        mock_check.side_effect = lambda url: _mock_artifact_not_found(url)

        result = await collect_geo_evidence(["https://www.acme.dev/"], max_related_pages=0)

        assert "docs.acme.dev" in result.discovered_domains
        assert "blog.acme.dev" in result.discovered_domains

    @pytest.mark.asyncio
    async def test_checks_artifacts_per_domain(self, mock_network):
        mock_fetch, mock_check = mock_network
        mock_fetch.return_value = _mock_fetch_result(
            "https://www.acme.dev/", "homepage.html",
        )
        mock_check.side_effect = lambda url: _mock_artifact_not_found(url)

        result = await collect_geo_evidence(["https://www.acme.dev/"], max_related_pages=0)

        domains_checked = {da.domain for da in result.domain_artifacts}
        assert "www.acme.dev" in domains_checked
        assert "docs.acme.dev" in domains_checked

    @pytest.mark.asyncio
    async def test_handles_fetch_error(self, mock_network):
        mock_fetch, mock_check = mock_network
        mock_fetch.return_value = _mock_fetch_result(
            "https://broken.dev/", error="timeout",
        )
        mock_check.side_effect = lambda url: _mock_artifact_not_found(url)

        result = await collect_geo_evidence(["https://broken.dev/"])

        assert len(result.warnings) > 0
        assert "broken.dev" in result.warnings[0]

    @pytest.mark.asyncio
    async def test_json_ld_extraction(self, mock_network):
        mock_fetch, mock_check = mock_network
        mock_fetch.return_value = _mock_fetch_result(
            "https://www.acme.dev/", "with-jsonld.html",
        )
        mock_check.side_effect = lambda url: _mock_artifact_not_found(url)

        result = await collect_geo_evidence(["https://www.acme.dev/"], max_related_pages=0)

        page = result.pages[0]
        assert len(page.json_ld_entries) == 2
        all_types = []
        for e in page.json_ld_entries:
            all_types.extend(e.types)
        assert "Organization" in all_types
        assert "SoftwareApplication" in all_types

    @pytest.mark.asyncio
    async def test_title_h1_comparison(self, mock_network):
        mock_fetch, mock_check = mock_network
        mock_fetch.return_value = _mock_fetch_result(
            "https://www.acme.dev/", "homepage.html",
        )
        mock_check.side_effect = lambda url: _mock_artifact_not_found(url)

        result = await collect_geo_evidence(["https://www.acme.dev/"], max_related_pages=0)

        page = result.pages[0]
        assert page.title_h1_match is False
        assert page.title_h1_similarity is not None
        assert 0.5 < page.title_h1_similarity < 1.0


class TestRelatedPageSampling:
    @pytest.mark.asyncio
    async def test_samples_related_pages(self, mock_network):
        """When max_related_pages > 0, the tool fetches same-origin links."""
        mock_fetch, mock_check = mock_network
        from pathlib import Path as _Path

        hub_html = (_Path(__file__).parent / "fixtures" / "hub-page.html").read_text()
        quickstart_html = (_Path(__file__).parent / "fixtures" / "with-jsonld.html").read_text()

        def fetch_side_effect(url):
            if "quickstart" in url:
                return FetchResult(url=url, status_code=200, final_url=None, body=quickstart_html, error=None)
            return FetchResult(url=url, status_code=200, final_url=None, body=hub_html, error=None)

        mock_fetch.side_effect = fetch_side_effect
        mock_check.side_effect = lambda url: _mock_artifact_not_found(url)

        result = await collect_geo_evidence(
            ["https://docs.acme.dev/"],
            max_related_pages=1,
        )

        # More than the 1 target page should be in pages
        assert len(result.pages) > 1
        sampled = [p for p in result.pages if p.is_sampled]
        assert len(sampled) == 1
        assert sampled[0].url.startswith("https://docs.acme.dev/")

    @pytest.mark.asyncio
    async def test_sampled_pages_marked(self, mock_network):
        """Target pages have is_sampled=False; auto-sampled have is_sampled=True."""
        mock_fetch, mock_check = mock_network
        from pathlib import Path as _Path

        hub_html = (_Path(__file__).parent / "fixtures" / "hub-page.html").read_text()
        other_html = (_Path(__file__).parent / "fixtures" / "no-metadata.html").read_text()

        def fetch_side_effect(url):
            if url == "https://docs.acme.dev/":
                return FetchResult(url=url, status_code=200, final_url=None, body=hub_html, error=None)
            return FetchResult(url=url, status_code=200, final_url=None, body=other_html, error=None)

        mock_fetch.side_effect = fetch_side_effect
        mock_check.side_effect = lambda url: _mock_artifact_not_found(url)

        result = await collect_geo_evidence(
            ["https://docs.acme.dev/"],
            max_related_pages=2,
        )

        target_pages = [p for p in result.pages if not p.is_sampled]
        sampled_pages = [p for p in result.pages if p.is_sampled]
        assert len(target_pages) == 1
        assert target_pages[0].url == "https://docs.acme.dev/"
        assert len(sampled_pages) <= 2

    @pytest.mark.asyncio
    async def test_no_sampling_when_max_zero(self, mock_network):
        """max_related_pages=0 disables sampling entirely."""
        mock_fetch, mock_check = mock_network

        mock_fetch.return_value = _mock_fetch_result("https://docs.acme.dev/", "hub-page.html")
        mock_check.side_effect = lambda url: _mock_artifact_not_found(url)

        result = await collect_geo_evidence(
            ["https://docs.acme.dev/"],
            max_related_pages=0,
        )

        assert all(not p.is_sampled for p in result.pages)
        assert len(result.pages) == 1

    @pytest.mark.asyncio
    async def test_does_not_refetch_target_url(self, mock_network):
        """A page that appears as both a target and a related link is only fetched once."""
        mock_fetch, mock_check = mock_network
        from pathlib import Path as _Path

        hub_html = (_Path(__file__).parent / "fixtures" / "hub-page.html").read_text()
        mock_fetch.return_value = FetchResult(
            url="https://docs.acme.dev/", status_code=200, final_url=None, body=hub_html, error=None
        )
        mock_check.side_effect = lambda url: _mock_artifact_not_found(url)

        result = await collect_geo_evidence(
            ["https://docs.acme.dev/"],
            max_related_pages=3,
        )

        # The target URL itself must not appear twice in pages
        target_urls_in_pages = [p.url for p in result.pages if p.url == "https://docs.acme.dev/"]
        assert len(target_urls_in_pages) <= 1


class TestCoverageAwareCollection:
    @pytest.mark.asyncio
    async def test_declared_sitemaps_and_llms_urls_become_candidates(self, mock_network):
        mock_fetch, mock_check = mock_network
        mock_fetch.return_value = _mock_fetch_result(
            "https://www.acme.dev/", "homepage.html",
        )

        robots_body = (FIXTURES / "robots-with-sitemap.txt").read_text()
        sitemap_body = (FIXTURES / "sample-sitemap.xml").read_text()
        llms_body = (FIXTURES / "sample-llms.txt").read_text()

        def check_side_effect(url):
            if url == "https://www.acme.dev/robots.txt":
                return ArtifactCheck(
                    url=url,
                    status=ArtifactStatus.FOUND,
                    http_status=200,
                    content_snippet=robots_body,
                )
            if url == "https://www.acme.dev/sample-sitemap.xml":
                return ArtifactCheck(
                    url=url,
                    status=ArtifactStatus.FOUND,
                    http_status=200,
                    content_snippet=sitemap_body,
                )
            if url == "https://www.acme.dev/llms.txt":
                return ArtifactCheck(
                    url=url,
                    status=ArtifactStatus.FOUND,
                    http_status=200,
                    content_snippet=llms_body,
                )
            return _mock_artifact_not_found(url)

        mock_check.side_effect = check_side_effect

        result = await collect_geo_evidence(["https://www.acme.dev/"])

        by_url = {str(candidate.url): candidate for candidate in result.candidate_pages}
        assert by_url["https://docs.acme.dev/quickstart"].source == "sitemap"
        assert by_url["https://blog.acme.dev/launch"].source in {"sitemap", "llms"}

    @pytest.mark.asyncio
    async def test_nav_footer_and_subdomain_links_become_candidates_with_tags(self, mock_network):
        mock_fetch, mock_check = mock_network
        mock_fetch.return_value = _mock_fetch_result(
            "https://www.acme.dev/", "homepage.html",
        )
        mock_check.side_effect = lambda url: _mock_artifact_not_found(url)

        result = await collect_geo_evidence(
            ["https://www.acme.dev/"],
            coverage_preset="light",
        )

        by_url = {str(candidate.url): candidate for candidate in result.candidate_pages}
        assert by_url["https://www.acme.dev/pricing"].source == "nav"
        assert by_url["https://www.acme.dev/terms"].source == "footer"
        assert by_url["https://docs.acme.dev/"].subdomain_key == "docs.acme.dev"

    @pytest.mark.asyncio
    async def test_selected_representatives_respect_requested_preset_bounds(self, mock_network):
        mock_fetch, mock_check = mock_network
        mock_fetch.return_value = _mock_fetch_result(
            "https://www.acme.dev/", "homepage.html",
        )

        robots_body = (FIXTURES / "robots-with-sitemap.txt").read_text()
        sitemap_body = (FIXTURES / "sample-sitemap.xml").read_text()
        llms_body = (FIXTURES / "sample-llms.txt").read_text()

        def check_side_effect(url):
            if url == "https://www.acme.dev/robots.txt":
                return ArtifactCheck(
                    url=url,
                    status=ArtifactStatus.FOUND,
                    http_status=200,
                    content_snippet=robots_body,
                )
            if url in {"https://www.acme.dev/sample-sitemap.xml", "https://www.acme.dev/sitemap.xml"}:
                return ArtifactCheck(
                    url=url,
                    status=ArtifactStatus.FOUND,
                    http_status=200,
                    content_snippet=sitemap_body,
                )
            if url == "https://www.acme.dev/llms.txt":
                return ArtifactCheck(
                    url=url,
                    status=ArtifactStatus.FOUND,
                    http_status=200,
                    content_snippet=llms_body,
                )
            return _mock_artifact_not_found(url)

        mock_check.side_effect = check_side_effect

        result = await collect_geo_evidence(
            ["https://www.acme.dev/"],
            coverage_preset="light",
        )

        assert result.coverage_summary is not None
        assert result.coverage_summary.preset == "light"
        assert result.coverage_summary.representative_page_budget == 4
        assert result.coverage_summary.selected_page_count <= 4

        selected_representatives = [
            candidate
            for candidate in result.candidate_pages
            if candidate.selected and candidate.source not in {"target", "root"}
        ]
        assert len(selected_representatives) == result.coverage_summary.selected_page_count
        assert len(selected_representatives) <= 4

    @pytest.mark.asyncio
    async def test_truncation_warning_when_pool_exceeds_budget(self, mock_network):
        mock_fetch, mock_check = mock_network
        mock_fetch.return_value = _mock_fetch_result(
            "https://www.acme.dev/", "homepage.html",
        )

        robots_body = (FIXTURES / "robots-with-sitemap.txt").read_text()
        sitemap_body = (FIXTURES / "sample-sitemap.xml").read_text()
        llms_body = (FIXTURES / "sample-llms.txt").read_text()

        def check_side_effect(url):
            if url == "https://www.acme.dev/robots.txt":
                return ArtifactCheck(
                    url=url,
                    status=ArtifactStatus.FOUND,
                    http_status=200,
                    content_snippet=robots_body,
                )
            if url in {"https://www.acme.dev/sample-sitemap.xml", "https://www.acme.dev/sitemap.xml"}:
                return ArtifactCheck(
                    url=url,
                    status=ArtifactStatus.FOUND,
                    http_status=200,
                    content_snippet=sitemap_body,
                )
            if url == "https://www.acme.dev/llms.txt":
                return ArtifactCheck(
                    url=url,
                    status=ArtifactStatus.FOUND,
                    http_status=200,
                    content_snippet=llms_body,
                )
            return _mock_artifact_not_found(url)

        mock_check.side_effect = check_side_effect

        result = await collect_geo_evidence(
            ["https://www.acme.dev/"],
            coverage_preset="light",
        )

        assert result.coverage_summary is not None
        assert result.coverage_summary.truncated is True
        assert any("truncat" in warning.lower() for warning in result.warnings)


class TestGetBaseDomain:
    def test_simple_domain(self):
        assert _get_base_domain("example.com") == "example.com"

    def test_subdomain(self):
        assert _get_base_domain("docs.example.com") == "example.com"

    def test_deep_subdomain(self):
        assert _get_base_domain("a.b.example.com") == "example.com"

    def test_empty(self):
        assert _get_base_domain("") is None

    # Compound TLD cases — must return 3-level domain, not the SLD alone
    def test_co_uk(self):
        assert _get_base_domain("www.bbc.co.uk") == "bbc.co.uk"

    def test_co_uk_subdomain(self):
        assert _get_base_domain("news.bbc.co.uk") == "bbc.co.uk"

    def test_com_br(self):
        assert _get_base_domain("www.uol.com.br") == "uol.com.br"

    def test_com_au(self):
        assert _get_base_domain("docs.example.com.au") == "example.com.au"

    def test_plain_co_uk_not_treated_as_sld(self):
        """co.uk alone (no registered name) should return co.uk, not crash."""
        result = _get_base_domain("co.uk")
        assert result == "co.uk"
