"""Tests for deterministic claim validation."""

import pytest

from geo_audit_local_mcp.models import (
    ArtifactCheck,
    ArtifactStatus,
    CollectGeoEvidenceResult,
    DomainArtifacts,
    JsonLdEntry,
    PageMetadata,
    Severity,
)
from geo_audit_local_mcp.validation import validate_claims


def _artifact(status, url="https://example.com/robots.txt"):
    return ArtifactCheck(url=url, status=status, http_status=200 if status == ArtifactStatus.FOUND else 404)


def _evidence(
    domain="example.com",
    robots=ArtifactStatus.FOUND,
    sitemap=ArtifactStatus.FOUND,
    llms=ArtifactStatus.NOT_FOUND,
    llms_full=ArtifactStatus.NOT_FOUND,
    declared_sitemaps=None,
    pages=None,
):
    return CollectGeoEvidenceResult(
        target_urls=["https://example.com"],
        discovered_domains=[domain],
        domain_artifacts=[
            DomainArtifacts(
                domain=domain,
                robots_txt=_artifact(robots, f"https://{domain}/robots.txt"),
                sitemap_xml=_artifact(sitemap, f"https://{domain}/sitemap.xml"),
                declared_sitemaps=declared_sitemaps or [],
                llms_txt=_artifact(llms, f"https://{domain}/llms.txt"),
                llms_full_txt=_artifact(llms_full, f"https://{domain}/llms-full.txt"),
            ),
        ],
        pages=pages or [],
    )


class TestArtifactContradictions:
    def test_catches_false_not_found(self):
        evidence = _evidence(robots=ArtifactStatus.FOUND)
        draft = "The robots.txt is not found on example.com."
        result = validate_claims(draft, evidence)
        assert len(result.contradictions) >= 1
        assert result.contradictions[0].category == "artifact_existence"
        assert result.pass_ is False

    def test_catches_false_found(self):
        evidence = _evidence(llms=ArtifactStatus.NOT_FOUND)
        draft = "llms.txt is present at the root domain."
        result = validate_claims(draft, evidence)
        assert len(result.contradictions) >= 1
        assert "llms.txt" in result.contradictions[0].detail

    def test_no_contradiction_when_correct(self):
        evidence = _evidence(robots=ArtifactStatus.FOUND, llms=ArtifactStatus.NOT_FOUND)
        draft = "robots.txt is present. No llms.txt was found on this domain."
        result = validate_claims(draft, evidence)
        contradictions = [f for f in result.contradictions if f.category == "artifact_existence"]
        assert len(contradictions) == 0

    def test_sitemap_contradiction(self):
        evidence = _evidence(sitemap=ArtifactStatus.NOT_FOUND)
        draft = "sitemap.xml exists and contains 500 URLs."
        result = validate_claims(draft, evidence)
        assert any("sitemap.xml" in c.detail for c in result.contradictions)

    def test_catches_parenthetical_absent(self):
        """Freeform: 'llms.txt (absent on Composio)' should fire when llms.txt is FOUND."""
        evidence = _evidence(llms=ArtifactStatus.FOUND)
        draft = "site artifacts: robots.txt present. llms.txt (absent on composio; present on arcade)"
        result = validate_claims(draft, evidence)
        assert any("llms.txt" in c.detail for c in result.contradictions)

    def test_catches_colon_absent(self):
        """Freeform: 'robots.txt: absent' should fire when robots.txt is FOUND."""
        evidence = _evidence(robots=ArtifactStatus.FOUND)
        draft = "robots.txt: absent — not crawlable."
        result = validate_claims(draft, evidence)
        assert any("robots.txt" in c.detail for c in result.contradictions)

    def test_no_freeform_false_positive(self):
        """'llms.txt (present on composio)' must not fire as NOT_FOUND contradiction."""
        evidence = _evidence(llms=ArtifactStatus.NOT_FOUND)
        draft = "llms.txt (present on composio); robots.txt also found."
        result = validate_claims(draft, evidence)
        # Should flag llms.txt as a contradiction (draft says present, evidence says not found)
        llms_contradictions = [
            c for c in result.contradictions
            if "llms.txt" in c.detail
        ]
        assert len(llms_contradictions) == 1


class TestJsonLdContradictions:
    def test_catches_false_no_jsonld(self):
        evidence = _evidence(pages=[
            PageMetadata(
                url="https://example.com",
                json_ld_entries=[JsonLdEntry(types=["Organization"])],
            ),
        ])
        draft = "The site has no JSON-LD structured data."
        result = validate_claims(draft, evidence)
        assert any(f.category == "json_ld_presence" for f in result.contradictions)

    def test_catches_false_has_jsonld(self):
        evidence = _evidence(pages=[
            PageMetadata(url="https://example.com", json_ld_entries=[]),
        ])
        draft = "JSON-LD is present on the homepage."
        result = validate_claims(draft, evidence)
        assert any(f.category == "json_ld_presence" for f in result.contradictions)

    def test_no_contradiction_when_correct(self):
        evidence = _evidence(pages=[
            PageMetadata(url="https://example.com", json_ld_entries=[]),
        ])
        draft = "No JSON-LD was found. The site lacks structured data entirely."
        result = validate_claims(draft, evidence)
        jsonld_contradictions = [f for f in result.contradictions if f.category == "json_ld_presence"]
        assert len(jsonld_contradictions) == 0


class TestTitleH1Contradictions:
    def test_catches_false_mismatch_claim(self):
        evidence = _evidence(pages=[
            PageMetadata(
                url="https://example.com",
                title="Hello World",
                h1_text="Hello World",
                title_h1_match=True,
                title_h1_similarity=1.0,
            ),
        ])
        draft = "There is a title / H1 mismatch on the homepage."
        result = validate_claims(draft, evidence)
        assert any(f.category == "title_h1_comparison" for f in result.unsupported_claims)

    def test_catches_false_match_claim(self):
        evidence = _evidence(pages=[
            PageMetadata(
                url="https://example.com",
                title="Go Beyond Chat",
                h1_text="Level Up Your Agents",
                title_h1_match=False,
                title_h1_similarity=0.2,
            ),
        ])
        draft = "Title and H1 match well and are consistent."
        result = validate_claims(draft, evidence)
        assert any(f.category == "title_h1_comparison" for f in result.unsupported_claims)


class TestMissingHighSignalFacts:
    def test_flags_missing_llms_txt(self):
        evidence = _evidence(llms=ArtifactStatus.FOUND)
        draft = "The site has good technical accessibility with a clean robots.txt."
        result = validate_claims(draft, evidence)
        assert any(
            f.severity == Severity.MISSING_FACT and "llms.txt" in f.detail
            for f in result.missing_high_signal_facts
        )

    def test_flags_missing_declared_sitemap(self):
        evidence = _evidence(
            declared_sitemaps=["https://example.com/sitemap-index.xml"],
        )
        draft = "sitemap.xml was found at the standard path."
        result = validate_claims(draft, evidence)
        assert any(
            "sitemap-index.xml" in f.detail
            for f in result.missing_high_signal_facts
        )

    def test_no_flag_when_mentioned(self):
        evidence = _evidence(llms=ArtifactStatus.FOUND)
        draft = "The llms.txt file is present and provides structured context."
        result = validate_claims(draft, evidence)
        llms_missing = [
            f for f in result.missing_high_signal_facts
            if "llms.txt" in f.detail and "llms-full.txt" not in f.detail
        ]
        assert len(llms_missing) == 0


class TestPassFailSummary:
    def test_pass_when_no_contradictions(self):
        evidence = _evidence()
        draft = "The site has decent technical accessibility."
        result = validate_claims(draft, evidence)
        assert result.pass_ is True

    def test_fail_when_contradiction_exists(self):
        evidence = _evidence(robots=ArtifactStatus.FOUND)
        draft = "robots.txt is not found."
        result = validate_claims(draft, evidence)
        assert result.pass_ is False

    def test_confidence_downgrades_for_contradictions(self):
        evidence = _evidence(robots=ArtifactStatus.FOUND)
        draft = "robots.txt is not found."
        result = validate_claims(draft, evidence)
        assert len(result.confidence_downgrades) > 0
        assert result.confidence_downgrades[0].suggested_confidence == "low"
