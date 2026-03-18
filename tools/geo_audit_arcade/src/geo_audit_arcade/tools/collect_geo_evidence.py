"""CollectGeoEvidence tool: deterministic evidence collection for GEO audits."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from ..extraction import (
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
    parse_llms_urls,
    parse_robots_sitemaps,
    parse_sitemap_urls,
)
from ..fetching import check_artifact, fetch_page
from ..models import (
    ArtifactCheck,
    CandidatePage,
    CollectGeoEvidenceResult,
    CoveragePreset,
    DomainArtifacts,
    PageMetadata,
)
from ..selection import (
    SOURCE_PRIORITY,
    infer_section_key,
    infer_subdomain_key,
    normalize_candidate_url,
    select_candidate_pages,
)

# Common compound second-level domains that must not be treated as the
# registrable base. Extend as needed; this list covers the most common cases.
_COMPOUND_SLDS: frozenset[str] = frozenset(
    {
        "co.uk",
        "co.jp",
        "co.nz",
        "co.za",
        "co.in",
        "co.kr",
        "co.id",
        "co.il",
        "co.at",
        "co.th",
        "com.br",
        "com.au",
        "com.ar",
        "com.mx",
        "com.co",
        "com.sg",
        "com.my",
        "com.tr",
        "com.pe",
        "com.vn",
        "com.ph",
        "com.pk",
        "org.uk",
        "org.au",
        "org.nz",
        "net.uk",
        "net.au",
        "me.uk",
        "ltd.uk",
        "plc.uk",
        "gov.uk",
        "gov.au",
        "gov.br",
        "gov.in",
        "gov.sg",
        "edu.au",
        "edu.sg",
        "ac.uk",
        "ac.nz",
        "ac.jp",
        "ac.za",
    }
)


async def collect_geo_evidence(
    target_urls: list[str],
    audit_mode: str = "single-page",
    coverage_preset: CoveragePreset = "exhaustive",
    discover_subdomains: bool = True,
    max_related_pages: int | None = None,
) -> CollectGeoEvidenceResult:
    del audit_mode  # Reserved for future mode-specific collection tweaks.

    warnings: list[str] = []
    normalized_targets = [normalize_candidate_url(url) for url in target_urls]
    base_domains = {
        base
        for base in (_get_base_domain(urlparse(url).hostname or "") for url in normalized_targets)
        if base
    }
    discovered_domains: set[str] = {
        hostname for hostname in (urlparse(url).hostname for url in normalized_targets) if hostname
    }
    pages_by_url: dict[str, PageMetadata] = {}
    artifact_cache: dict[str, ArtifactCheck] = {}
    candidate_map: dict[str, CandidatePage] = {}

    def add_candidate(url: str, source: str, *, selection_reason: str | None = None) -> None:
        normalized = normalize_candidate_url(url)
        parsed = urlparse(normalized)
        hostname = parsed.hostname
        if not hostname:
            return
        base_domain = _get_base_domain(hostname)
        if base_domains and base_domain not in base_domains:
            return
        if discover_subdomains:
            discovered_domains.add(hostname)

        incoming = CandidatePage(
            url=normalized,
            source=source,
            section_key=infer_section_key(normalized),
            subdomain_key=infer_subdomain_key(normalized),
            selection_reason=selection_reason,
        )
        existing = candidate_map.get(normalized)
        if existing is None:
            candidate_map[normalized] = incoming
            return
        if SOURCE_PRIORITY[source] > SOURCE_PRIORITY[existing.source]:
            candidate_map[normalized] = incoming
            return
        if selection_reason and not existing.selection_reason:
            candidate_map[normalized] = existing.model_copy(
                update={"selection_reason": selection_reason},
            )

    for url in normalized_targets:
        add_candidate(url, "target", selection_reason="requested target")
        root_or_hub = _get_root_or_hub_url(url)
        if root_or_hub != url:
            add_candidate(
                root_or_hub,
                "root",
                selection_reason="site root or nearest hub",
            )

        result = await fetch_page(url)
        pages_by_url[url] = _build_page_metadata(
            url,
            result,
            warnings=warnings,
            is_sampled=False,
        )
        if result.is_ok and result.body:
            soup = parse_html(result.body)
            hostname = urlparse(url).hostname or ""
            base_domain = _get_base_domain(hostname)
            if discover_subdomains and base_domain:
                discovered_domains.update(extract_domains_from_links(soup, base_domain))
            _add_html_candidates(
                soup,
                page_url=url,
                base_domains=base_domains,
                add_candidate=add_candidate,
            )
        if result.final_url and result.final_url != url:
            add_candidate(result.final_url, "redirect", selection_reason="redirect target")

    domain_artifacts: list[DomainArtifacts] = []
    processed_domains: set[str] = set()
    while True:
        pending_domains = sorted(discovered_domains - processed_domains)
        if not pending_domains:
            break
        for domain in pending_domains:
            processed_domains.add(domain)
            artifacts = await _check_domain_artifacts(
                domain,
                artifact_cache=artifact_cache,
            )
            domain_artifacts.append(artifacts)
            await _add_artifact_candidates(
                artifacts,
                artifact_cache=artifact_cache,
                add_candidate=add_candidate,
            )

    candidate_pages, coverage_summary = select_candidate_pages(
        list(candidate_map.values()),
        coverage_preset,
        page_budget_override=max_related_pages,
    )

    for candidate in candidate_pages:
        url = str(candidate.url)
        if not candidate.selected or url in pages_by_url:
            continue
        result = await fetch_page(url)
        pages_by_url[url] = _build_page_metadata(
            url,
            result,
            warnings=warnings,
            is_sampled=True,
        )

    if max_related_pages is not None:
        warnings.append(
            "max_related_pages is deprecated; coverage_preset is the primary exploration control surface.",
        )
    if coverage_summary.truncated:
        warnings.append(
            "Candidate pool was truncated to the selected coverage preset budget.",
        )

    ordered_pages = [pages_by_url[url] for url in normalized_targets if url in pages_by_url]
    seen_pages = {page.url for page in ordered_pages}
    for candidate in candidate_pages:
        url = str(candidate.url)
        if not candidate.selected or url in seen_pages or url not in pages_by_url:
            continue
        ordered_pages.append(pages_by_url[url])
        seen_pages.add(url)

    return CollectGeoEvidenceResult(
        target_urls=normalized_targets,
        discovered_domains=sorted(discovered_domains),
        domain_artifacts=domain_artifacts,
        pages=ordered_pages,
        candidate_pages=candidate_pages,
        coverage_summary=coverage_summary,
        warnings=warnings,
    )


def _populate_page_metadata(page_meta: PageMetadata, soup: BeautifulSoup) -> None:
    """Fill all extracted fields on *page_meta* from a parsed BeautifulSoup tree."""

    page_meta.title = extract_title(soup)
    page_meta.meta_description = extract_meta_description(soup)
    page_meta.canonical = extract_canonical(soup)
    page_meta.open_graph = extract_open_graph(soup)
    page_meta.json_ld_entries = extract_json_ld(soup)
    page_meta.headings = extract_headings(soup)
    page_meta.h1_text = extract_h1(soup)
    match, similarity = compare_title_h1(page_meta.title, page_meta.h1_text)
    page_meta.title_h1_match = match
    page_meta.title_h1_similarity = similarity
    page_meta.first_200_words = extract_first_200_words(soup)


def _build_page_metadata(
    url: str,
    result,
    *,
    warnings: list[str],
    is_sampled: bool,
) -> PageMetadata:
    page_meta = PageMetadata(url=url, http_status=result.status_code, is_sampled=is_sampled)
    if result.is_ok and result.body:
        soup = parse_html(result.body)
        _populate_page_metadata(page_meta, soup)
        return page_meta

    label = "sampled page" if is_sampled else "page"
    warnings.append(
        f"Could not fetch {label} {url}: {result.error or f'HTTP {result.status_code}'}"
    )
    return page_meta


def _add_html_candidates(
    soup: BeautifulSoup,
    *,
    page_url: str,
    base_domains: set[str],
    add_candidate,
) -> None:
    for url in _extract_zone_links(soup, page_url, "nav", base_domains):
        add_candidate(url, "nav", selection_reason="navigation link")
    for url in _extract_zone_links(soup, page_url, "footer", base_domains):
        add_candidate(url, "footer", selection_reason="footer link")
    for url in extract_internal_links(soup, page_url):
        add_candidate(url, "path_cluster", selection_reason="internal path cluster")


def _extract_zone_links(
    soup: BeautifulSoup,
    page_url: str,
    zone: str,
    base_domains: set[str],
) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for container in soup.find_all(zone):
        for tag in container.find_all("a", href=True):
            if not isinstance(tag, Tag):
                continue
            href = str(tag["href"]).strip()
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            absolute = href if href.startswith("http") else urljoin(page_url, href)
            normalized = normalize_candidate_url(absolute)
            hostname = urlparse(normalized).hostname
            if not hostname:
                continue
            if base_domains and _get_base_domain(hostname) not in base_domains:
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            links.append(normalized)
    return links


async def _add_artifact_candidates(
    artifacts: DomainArtifacts,
    *,
    artifact_cache: dict[str, ArtifactCheck],
    add_candidate,
) -> None:
    if artifacts.sitemap_xml.content_snippet:
        for url in parse_sitemap_urls(artifacts.sitemap_xml.content_snippet):
            add_candidate(url, "sitemap", selection_reason="standard sitemap candidate")

    for sitemap_url in artifacts.declared_sitemaps:
        sitemap = await _cached_check_artifact(
            sitemap_url,
            artifact_cache=artifact_cache,
        )
        if sitemap.content_snippet:
            for url in parse_sitemap_urls(sitemap.content_snippet):
                add_candidate(url, "sitemap", selection_reason="declared sitemap candidate")

    for llms_artifact in (artifacts.llms_txt, artifacts.llms_full_txt):
        if llms_artifact.content_snippet:
            for url in parse_llms_urls(llms_artifact.content_snippet):
                add_candidate(url, "llms", selection_reason="llms discovery candidate")


async def _check_domain_artifacts(
    domain: str,
    *,
    artifact_cache: dict[str, ArtifactCheck],
) -> DomainArtifacts:
    base = f"https://{domain}"

    robots = await _cached_check_artifact(f"{base}/robots.txt", artifact_cache=artifact_cache)
    sitemap = await _cached_check_artifact(f"{base}/sitemap.xml", artifact_cache=artifact_cache)
    llms = await _cached_check_artifact(f"{base}/llms.txt", artifact_cache=artifact_cache)
    llms_full = await _cached_check_artifact(
        f"{base}/llms-full.txt",
        artifact_cache=artifact_cache,
    )

    declared_sitemaps: list[str] = []
    if robots.content_snippet:
        declared_sitemaps = parse_robots_sitemaps(robots.content_snippet)

    return DomainArtifacts(
        domain=domain,
        robots_txt=robots,
        sitemap_xml=sitemap,
        declared_sitemaps=declared_sitemaps,
        llms_txt=llms,
        llms_full_txt=llms_full,
    )


async def _cached_check_artifact(
    url: str,
    *,
    artifact_cache: dict[str, ArtifactCheck],
) -> ArtifactCheck:
    if url not in artifact_cache:
        artifact_cache[url] = await check_artifact(url)
    return artifact_cache[url]


def _get_root_or_hub_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        return normalize_candidate_url(url)
    first_segment = path.split("/", 1)[0]
    if "/" in path:
        return normalize_candidate_url(f"{parsed.scheme}://{parsed.netloc}/{first_segment}")
    return normalize_candidate_url(f"{parsed.scheme}://{parsed.netloc}/")


def _get_base_domain(hostname: str) -> str | None:
    """Return the registrable base domain, handling compound SLDs."""

    if not hostname:
        return None
    parts = hostname.split(".")
    if len(parts) < 2:
        return hostname
    last_two = f"{parts[-2]}.{parts[-1]}"
    if last_two in _COMPOUND_SLDS and len(parts) >= 3:
        return ".".join(parts[-3:])
    return last_two
