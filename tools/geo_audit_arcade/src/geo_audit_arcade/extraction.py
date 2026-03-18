"""Pure-Python HTML extraction helpers. No side effects, no network."""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher

from bs4 import BeautifulSoup, Tag

from .models import HeadingItem, JsonLdEntry, OpenGraphTags


def parse_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def extract_title(soup: BeautifulSoup) -> str | None:
    tag = soup.find("title")
    if tag and tag.string:
        return tag.string.strip()
    return None


def extract_meta_description(soup: BeautifulSoup) -> str | None:
    tag = soup.find("meta", attrs={"name": "description"})
    if isinstance(tag, Tag) and tag.get("content"):
        return str(tag["content"]).strip()
    return None


def extract_canonical(soup: BeautifulSoup) -> str | None:
    tag = soup.find("link", attrs={"rel": "canonical"})
    if isinstance(tag, Tag) and tag.get("href"):
        return str(tag["href"]).strip()
    return None


def extract_open_graph(soup: BeautifulSoup) -> OpenGraphTags:
    def _og(prop: str) -> str | None:
        tag = soup.find("meta", attrs={"property": f"og:{prop}"})
        if isinstance(tag, Tag) and tag.get("content"):
            return str(tag["content"]).strip()
        return None

    return OpenGraphTags(
        og_title=_og("title"),
        og_description=_og("description"),
        og_type=_og("type"),
        og_image=_og("image"),
    )


def extract_headings(soup: BeautifulSoup) -> list[HeadingItem]:
    """Return headings in document order (not grouped by level)."""
    items: list[HeadingItem] = []
    for tag in soup.find_all(re.compile(r"^h[1-6]$")):
        text = tag.get_text(separator=" ", strip=True)
        if text:
            items.append(HeadingItem(level=int(tag.name[1]), text=text))
    return items


def extract_h1(soup: BeautifulSoup) -> str | None:
    tag = soup.find("h1")
    if tag:
        text = tag.get_text(separator=" ", strip=True)
        return text if text else None
    return None


def extract_json_ld(soup: BeautifulSoup) -> list[JsonLdEntry]:
    entries: list[JsonLdEntry] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        types = _extract_types(data)
        snippet = raw.strip()[:300]
        entries.append(JsonLdEntry(types=types, raw_snippet=snippet))
    return entries


def _extract_types(data: object) -> list[str]:
    types: list[str] = []
    if isinstance(data, dict):
        t = data.get("@type")
        if isinstance(t, str):
            types.append(t)
        elif isinstance(t, list):
            types.extend(str(x) for x in t)
        graph = data.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                types.extend(_extract_types(item))
    elif isinstance(data, list):
        for item in data:
            types.extend(_extract_types(item))
    return types


def compare_title_h1(
    title: str | None, h1: str | None
) -> tuple[bool | None, float | None]:
    """Return (exact_match, similarity_ratio) for title vs H1."""
    if title is None or h1 is None:
        return None, None
    norm_title = _normalize_text(title)
    norm_h1 = _normalize_text(h1)
    exact = norm_title == norm_h1
    ratio = SequenceMatcher(None, norm_title, norm_h1).ratio()
    return exact, round(ratio, 3)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def extract_first_200_words(soup: BeautifulSoup) -> str | None:
    """Extract first ~200 words of visible text from the body.

    Does NOT mutate the soup — uses NavigableString traversal with parent filtering.
    """
    from bs4 import NavigableString

    body = soup.find("body")
    if not body:
        return None

    excluded = {"script", "style", "noscript", "nav", "footer", "header"}
    texts: list[str] = []
    for element in body.descendants:
        if not isinstance(element, NavigableString):
            continue
        if any(getattr(p, "name", None) in excluded for p in element.parents):
            continue
        text = str(element).strip()
        if text:
            texts.append(text)

    words = " ".join(texts).split()
    if not words:
        return None
    return " ".join(words[:200])


def extract_domains_from_links(soup: BeautifulSoup, base_domain: str) -> set[str]:
    """Find additional domains/subdomains from nav, footer, and general links."""
    from urllib.parse import urlparse

    domains: set[str] = set()
    for tag in soup.find_all("a", href=True):
        href = str(tag["href"])
        if not href.startswith("http"):
            continue
        parsed = urlparse(href)
        host = parsed.hostname
        if not host:
            continue
        if host == base_domain or host.endswith(f".{base_domain}"):
            domains.add(host)
    return domains


_UTILITY_PATH_PREFIXES = (
    "/robots.txt",
    "/sitemap",
    "/cdn-cgi/",
    "/wp-admin/",
    "/wp-login",
    "/login",
    "/logout",
    "/sign-in",
    "/sign-out",
    "/auth/",
    "/.well-known/",
    "/api/",
    "/_next/",
    "/__",
    "/static/",
    "/assets/",
    "/favicon",
    "/manifest.",
)

_UTILITY_PATH_EXTENSIONS = (
    ".xml",
    ".txt",
    ".json",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".css",
    ".js",
    ".woff",
    ".woff2",
)


def extract_internal_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    """Extract same-origin page URLs from soup, ordered by relevance zone.

    Prioritises links found in <nav>, <main>, and <article> elements.
    Skips utility paths (sitemap, robots, CDN, auth, static assets).
    Returns deduplicated absolute URLs, excluding the base URL itself.
    Does NOT mutate the soup.
    """
    from urllib.parse import urljoin, urlparse

    parsed_base = urlparse(base_url)
    origin = f"{parsed_base.scheme}://{parsed_base.netloc}"
    base_path = parsed_base.path.rstrip("/") or "/"

    seen: set[str] = set()
    priority_urls: list[str] = []
    other_urls: list[str] = []

    # High-relevance containers first, then everything else
    priority_containers = soup.find_all(["nav", "main", "article", "section"])
    priority_hrefs: set[str] = set()
    for container in priority_containers:
        for tag in container.find_all("a", href=True):
            priority_hrefs.add(str(tag["href"]))

    def _process(href: str, is_priority: bool) -> None:
        href = href.strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            return
        absolute = href if href.startswith("http") else urljoin(origin, href)
        parsed = urlparse(absolute)
        if f"{parsed.scheme}://{parsed.netloc}" != origin:
            return
        path = parsed.path.rstrip("/") or "/"
        if path == base_path:
            return
        # Strip fragment and query for dedup
        clean = f"{origin}{path}"
        if clean in seen:
            return
        path_lower = path.lower()
        if any(path_lower.startswith(p) for p in _UTILITY_PATH_PREFIXES):
            return
        if any(path_lower.endswith(e) for e in _UTILITY_PATH_EXTENSIONS):
            return
        seen.add(clean)
        if is_priority:
            priority_urls.append(clean)
        else:
            other_urls.append(clean)

    for tag in soup.find_all("a", href=True):
        href = str(tag["href"])
        _process(href, is_priority=(href in priority_hrefs))

    return priority_urls + other_urls


def parse_robots_sitemaps(robots_text: str) -> list[str]:
    """Extract Sitemap: URLs from robots.txt content."""
    sitemaps: list[str] = []
    for line in robots_text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("sitemap:"):
            url = stripped.split(":", 1)[1].strip()
            if url:
                sitemaps.append(url)
    return sitemaps


def parse_sitemap_urls(sitemap_xml: str) -> list[str]:
    """Extract URL candidates from sitemap XML content."""

    matches = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sitemap_xml, flags=re.IGNORECASE)
    return _dedupe_preserve_order(matches)


def parse_llms_urls(llms_text: str) -> list[str]:
    """Extract absolute URLs from llms.txt-style content."""

    matches = re.findall(r"https?://[^\s<>)\]]+", llms_text)
    return _dedupe_preserve_order(matches)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
