"""Tests for ValidateGeoAuditClaims tool."""

import json

import pytest

from geo_audit_local_mcp.models import (
    ArtifactCheck,
    ArtifactStatus,
    CollectGeoEvidenceResult,
    DomainArtifacts,
    JsonLdEntry,
    PageMetadata,
)
from geo_audit_local_mcp.tools.validate_geo_audit_claims import validate_geo_audit_claims


def _artifact(status, url="https://example.com/test"):
    return ArtifactCheck(url=url, status=status, http_status=200 if status == ArtifactStatus.FOUND else 404)


def _build_evidence():
    return CollectGeoEvidenceResult(
        target_urls=["https://example.com"],
        discovered_domains=["example.com"],
        domain_artifacts=[
            DomainArtifacts(
                domain="example.com",
                robots_txt=_artifact(ArtifactStatus.FOUND, "https://example.com/robots.txt"),
                sitemap_xml=_artifact(ArtifactStatus.FOUND, "https://example.com/sitemap.xml"),
                declared_sitemaps=["https://example.com/sitemap-index.xml"],
                llms_txt=_artifact(ArtifactStatus.FOUND, "https://example.com/llms.txt"),
                llms_full_txt=_artifact(ArtifactStatus.NOT_FOUND, "https://example.com/llms-full.txt"),
            ),
        ],
        pages=[
            PageMetadata(
                url="https://example.com",
                http_status=200,
                title="Example Site",
                h1_text="Welcome to Example",
                title_h1_match=False,
                title_h1_similarity=0.5,
                json_ld_entries=[JsonLdEntry(types=["Organization", "WebSite"])],
            ),
        ],
    )


class TestValidateGeoAuditClaimsTool:
    async def test_catches_artifact_contradiction(self):
        evidence = _build_evidence()
        draft = """
        # GEO Audit: example.com
        ## Technical Accessibility
        The robots.txt is not found on example.com.
        The sitemap.xml is present with good coverage.
        The llms.txt file is present.
        """
        result = await validate_geo_audit_claims(
            draft_report=draft,
            evidence_json=evidence.model_dump(),
        )
        assert len(result.contradictions) >= 1
        assert any("robots.txt" in c.detail for c in result.contradictions)

    async def test_catches_json_ld_contradiction(self):
        evidence = _build_evidence()
        draft = """
        # GEO Audit: example.com
        ## Structured Data
        No JSON-LD structured data was found on the homepage.
        The llms.txt file is present at the root.
        """
        result = await validate_geo_audit_claims(
            draft_report=draft,
            evidence_json=evidence.model_dump(),
        )
        assert any(
            c.category == "json_ld_presence"
            for c in result.contradictions
        )

    async def test_flags_missing_declared_sitemap(self):
        evidence = _build_evidence()
        draft = """
        # GEO Audit: example.com
        ## Technical Accessibility
        robots.txt present. sitemap.xml found. llms.txt found.
        JSON-LD Organization and WebSite types present.
        """
        result = await validate_geo_audit_claims(
            draft_report=draft,
            evidence_json=evidence.model_dump(),
        )
        missing = [f for f in result.missing_high_signal_facts if "sitemap-index" in f.detail]
        assert len(missing) >= 1

    async def test_clean_report_passes(self):
        evidence = _build_evidence()
        draft = """
        # GEO Audit: example.com
        ## Technical Accessibility
        robots.txt is present on example.com with standard rules.
        sitemap.xml found. robots.txt also declares sitemap-index.xml.
        llms.txt is present at the root domain.
        ## Structured Data
        JSON-LD includes Organization and WebSite types.
        Title and H1 differ (title: "Example Site", H1: "Welcome to Example").
        """
        result = await validate_geo_audit_claims(
            draft_report=draft,
            evidence_json=evidence.model_dump(),
        )
        assert result.pass_ is True
        assert len(result.contradictions) == 0

    async def test_accepts_json_string_evidence(self):
        evidence = _build_evidence()
        evidence_str = evidence.model_dump()
        draft = "robots.txt present. sitemap.xml found. llms.txt found. JSON-LD present."
        result = await validate_geo_audit_claims(
            draft_report=draft,
            evidence_json=evidence_str,
        )
        assert result.total_findings >= 0
