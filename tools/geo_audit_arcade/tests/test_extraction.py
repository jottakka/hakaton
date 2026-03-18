"""Tests for HTML extraction helpers — verifying they work under the arcade package."""

from geo_audit_arcade.extraction import (
    compare_title_h1,
    extract_canonical,
    extract_first_200_words,
    extract_h1,
    extract_headings,
    extract_json_ld,
    extract_meta_description,
    extract_open_graph,
    extract_title,
    parse_html,
    parse_llms_urls,
    parse_robots_sitemaps,
    parse_sitemap_urls,
)


class TestExtractTitle:
    def test_basic(self):
        soup = parse_html("<html><head><title>Hello World</title></head></html>")
        assert extract_title(soup) == "Hello World"

    def test_no_title(self):
        soup = parse_html("<html><head></head></html>")
        assert extract_title(soup) is None


class TestExtractMetaDescription:
    def test_basic(self):
        html = '<html><head><meta name="description" content="A test page"></head></html>'
        soup = parse_html(html)
        assert extract_meta_description(soup) == "A test page"

    def test_missing(self):
        soup = parse_html("<html><head></head></html>")
        assert extract_meta_description(soup) is None


class TestExtractCanonical:
    def test_basic(self):
        html = '<html><head><link rel="canonical" href="https://example.com/page"></head></html>'
        soup = parse_html(html)
        assert extract_canonical(soup) == "https://example.com/page"


class TestExtractOpenGraph:
    def test_basic(self):
        html = (
            "<html><head>"
            '<meta property="og:title" content="OG Title">'
            '<meta property="og:description" content="OG Desc">'
            "</head></html>"
        )
        og = extract_open_graph(parse_html(html))
        assert og.og_title == "OG Title"
        assert og.og_description == "OG Desc"


class TestExtractJsonLd:
    def test_basic(self):
        html = (
            "<html><body>"
            '<script type="application/ld+json">{"@type": "Organization", "name": "Test"}</script>'
            "</body></html>"
        )
        entries = extract_json_ld(parse_html(html))
        assert len(entries) == 1
        assert "Organization" in entries[0].types

    def test_no_jsonld(self):
        soup = parse_html("<html><body><p>Hello</p></body></html>")
        assert extract_json_ld(soup) == []


class TestExtractHeadings:
    def test_extracts_all_levels(self):
        html = "<html><body><h1>Title</h1><h2>Sub</h2><h3>Deep</h3></body></html>"
        headings = extract_headings(parse_html(html))
        assert len(headings) == 3
        assert headings[0].level == 1
        assert headings[0].text == "Title"


class TestExtractH1:
    def test_basic(self):
        soup = parse_html("<html><body><h1>My Page</h1></body></html>")
        assert extract_h1(soup) == "My Page"

    def test_no_h1(self):
        soup = parse_html("<html><body><h2>Not H1</h2></body></html>")
        assert extract_h1(soup) is None


class TestCompareTitleH1:
    def test_exact_match(self):
        match, sim = compare_title_h1("Hello World", "Hello World")
        assert match is True
        assert sim == 1.0

    def test_mismatch(self):
        match, sim = compare_title_h1("Hello", "Goodbye")
        assert match is False
        assert sim is not None and sim < 1.0

    def test_none_inputs(self):
        match, sim = compare_title_h1(None, "Hello")
        assert match is None
        assert sim is None


class TestExtractFirst200Words:
    def test_basic(self):
        html = "<html><body><p>" + " ".join(f"word{i}" for i in range(300)) + "</p></body></html>"
        result = extract_first_200_words(parse_html(html))
        assert result is not None
        assert len(result.split()) == 200

    def test_no_body(self):
        soup = parse_html("<html><head></head></html>")
        assert extract_first_200_words(soup) is None


class TestParseRobotsSitemaps:
    def test_basic(self):
        robots = "User-agent: *\nDisallow: /admin\nSitemap: https://example.com/sitemap.xml\n"
        result = parse_robots_sitemaps(robots)
        assert result == ["https://example.com/sitemap.xml"]

    def test_multiple(self):
        robots = "Sitemap: https://a.com/s1.xml\nSitemap: https://a.com/s2.xml\n"
        result = parse_robots_sitemaps(robots)
        assert len(result) == 2


class TestParseSitemapUrls:
    def test_basic(self):
        xml = "<urlset><url><loc>https://example.com/page1</loc></url></urlset>"
        result = parse_sitemap_urls(xml)
        assert result == ["https://example.com/page1"]


class TestParseLlmsUrls:
    def test_basic(self):
        text = "Check out https://example.com/docs and https://example.com/api"
        result = parse_llms_urls(text)
        assert len(result) == 2
        assert "https://example.com/docs" in result
