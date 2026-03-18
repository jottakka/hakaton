"""Tests for Pydantic model contracts."""

from geo_audit_local_mcp.models import (
    ArtifactCheck,
    ArtifactStatus,
    CandidatePage,
    CollectGeoEvidenceResult,
    ConfidenceDowngrade,
    CoverageSummary,
    DomainArtifacts,
    HeadingItem,
    JsonLdEntry,
    OpenGraphTags,
    PageMetadata,
    Severity,
    ValidateGeoAuditClaimsResult,
    ValidationFinding,
)


def _make_artifact(status=ArtifactStatus.NOT_FOUND):
    return ArtifactCheck(url="https://example.com/robots.txt", status=status)


def _make_domain_artifacts():
    return DomainArtifacts(
        domain="example.com",
        robots_txt=_make_artifact(ArtifactStatus.FOUND),
        sitemap_xml=_make_artifact(ArtifactStatus.NOT_FOUND),
        llms_txt=_make_artifact(ArtifactStatus.NOT_FOUND),
        llms_full_txt=_make_artifact(ArtifactStatus.NOT_FOUND),
    )


class TestCollectGeoEvidenceResult:
    def test_minimal_construction(self):
        result = CollectGeoEvidenceResult(target_urls=["https://example.com"])
        assert result.target_urls == ["https://example.com"]
        assert result.discovered_domains == []
        assert result.domain_artifacts == []
        assert result.pages == []
        assert result.warnings == []

    def test_full_construction(self):
        result = CollectGeoEvidenceResult(
            target_urls=["https://example.com"],
            discovered_domains=["example.com", "docs.example.com"],
            domain_artifacts=[_make_domain_artifacts()],
            pages=[
                PageMetadata(
                    url="https://example.com",
                    http_status=200,
                    title="Example",
                    meta_description="A site",
                    canonical="https://example.com/",
                    open_graph=OpenGraphTags(og_title="Example"),
                    json_ld_entries=[JsonLdEntry(types=["Organization"])],
                    headings=[HeadingItem(level=1, text="Welcome")],
                    h1_text="Welcome",
                    title_h1_match=False,
                    title_h1_similarity=0.65,
                    first_200_words="Welcome to Example.",
                ),
            ],
            warnings=["Could not fetch one page"],
        )
        assert len(result.discovered_domains) == 2
        assert result.pages[0].json_ld_entries[0].types == ["Organization"]
        assert result.pages[0].title_h1_similarity == 0.65

    def test_roundtrip_json(self):
        result = CollectGeoEvidenceResult(
            target_urls=["https://example.com"],
            domain_artifacts=[_make_domain_artifacts()],
        )
        dumped = result.model_dump_json()
        restored = CollectGeoEvidenceResult.model_validate_json(dumped)
        assert restored.target_urls == result.target_urls

    def test_threads_candidate_pages_and_coverage_summary(self):
        result = CollectGeoEvidenceResult(
            target_urls=["https://example.com/docs/auth"],
            candidate_pages=[
                CandidatePage(
                    url="https://example.com/docs",
                    source="root",
                    section_key="docs",
                    subdomain_key="www",
                    selection_reason="nearest hub",
                    selected=True,
                ),
            ],
            coverage_summary=CoverageSummary(
                preset="exhaustive",
                representative_page_budget=18,
                selected_page_count=1,
                section_budget=8,
                section_count=1,
                extra_subdomain_budget=4,
                subdomain_count=1,
            ),
        )
        assert result.candidate_pages[0].source == "root"
        assert result.coverage_summary is not None
        assert result.coverage_summary.preset == "exhaustive"


class TestExplorationModels:
    def test_candidate_page_carries_source_attribution(self):
        candidate = CandidatePage(
            url="https://docs.example.com/guides/auth",
            source="llms",
            section_key="guides",
            subdomain_key="docs",
            selection_reason="linked from llms.txt",
            selected=True,
        )
        assert str(candidate.url) == "https://docs.example.com/guides/auth"
        assert candidate.source == "llms"
        assert candidate.section_key == "guides"
        assert candidate.subdomain_key == "docs"
        assert candidate.selected is True

    def test_coverage_summary_tracks_section_and_subdomain_counts(self):
        summary = CoverageSummary(
            preset="deep",
            representative_page_budget=12,
            selected_page_count=7,
            section_budget=6,
            section_count=4,
            extra_subdomain_budget=3,
            subdomain_count=2,
            truncated=True,
        )
        assert summary.preset == "deep"
        assert summary.section_count == 4
        assert summary.subdomain_count == 2
        assert summary.truncated is True

    def test_coverage_summary_accepts_only_known_presets(self):
        for preset in ("light", "standard", "deep", "exhaustive"):
            summary = CoverageSummary(
                preset=preset,
                representative_page_budget=1,
                selected_page_count=0,
                section_budget=1,
                section_count=0,
                extra_subdomain_budget=1,
                subdomain_count=0,
            )
            assert summary.preset == preset


class TestValidateGeoAuditClaimsResult:
    def test_empty_pass(self):
        result = ValidateGeoAuditClaimsResult(**{"pass": True})
        assert result.pass_ is True
        assert result.total_findings == 0
        assert result.contradictions == []

    def test_with_findings(self):
        result = ValidateGeoAuditClaimsResult(
            contradictions=[
                ValidationFinding(
                    severity=Severity.HARD_CONTRADICTION,
                    category="artifact_existence",
                    detail="robots.txt exists but draft says missing",
                ),
            ],
            unsupported_claims=[
                ValidationFinding(
                    severity=Severity.UNSUPPORTED,
                    category="title_h1_comparison",
                    detail="Title/H1 mismatch claimed but they match",
                ),
            ],
            missing_high_signal_facts=[
                ValidationFinding(
                    severity=Severity.MISSING_FACT,
                    category="missing_artifact_mention",
                    detail="llms.txt present but not mentioned",
                ),
            ],
            confidence_downgrades=[
                ConfidenceDowngrade(
                    claim="robots.txt missing",
                    reason="Hard contradiction",
                    suggested_confidence="low",
                ),
            ],
            total_findings=3,
            **{"pass": False},
        )
        assert result.pass_ is False
        assert result.total_findings == 3
        assert len(result.contradictions) == 1

    def test_json_alias(self):
        result = ValidateGeoAuditClaimsResult(**{"pass": True})
        dumped = result.model_dump(by_alias=True)
        assert "pass" in dumped
        assert dumped["pass"] is True


class TestArtifactCheck:
    def test_found_with_snippet(self):
        check = ArtifactCheck(
            url="https://example.com/robots.txt",
            status=ArtifactStatus.FOUND,
            http_status=200,
            content_snippet="User-agent: *\nAllow: /",
        )
        assert check.status == ArtifactStatus.FOUND
        assert check.content_snippet is not None

    def test_not_found(self):
        check = ArtifactCheck(
            url="https://example.com/llms.txt",
            status=ArtifactStatus.NOT_FOUND,
            http_status=404,
        )
        assert check.content_snippet is None


class TestPageMetadata:
    def test_defaults(self):
        page = PageMetadata(url="https://example.com")
        assert page.http_status is None
        assert page.title is None
        assert page.json_ld_entries == []
        assert page.headings == []
        assert page.title_h1_match is None
        assert page.is_sampled is False

    def test_sampled_flag(self):
        page = PageMetadata(url="https://example.com/guide", is_sampled=True)
        assert page.is_sampled is True
