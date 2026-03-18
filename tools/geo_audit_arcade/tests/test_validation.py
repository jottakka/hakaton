"""Tests for claim validation against evidence."""

from geo_audit_arcade.models import (
    ArtifactCheck,
    ArtifactStatus,
    CollectGeoEvidenceResult,
    DomainArtifacts,
    JsonLdEntry,
    PageMetadata,
    Severity,
)
from geo_audit_arcade.validation import validate_claims


def _make_artifact(status: ArtifactStatus, url: str = "https://example.com/robots.txt"):
    return ArtifactCheck(
        url=url, status=status, http_status=200 if status == ArtifactStatus.FOUND else 404
    )


def _make_domain_artifacts(domain: str = "example.com", **overrides):
    defaults = {
        "domain": domain,
        "robots_txt": _make_artifact(ArtifactStatus.FOUND, f"https://{domain}/robots.txt"),
        "sitemap_xml": _make_artifact(ArtifactStatus.FOUND, f"https://{domain}/sitemap.xml"),
        "llms_txt": _make_artifact(ArtifactStatus.NOT_FOUND, f"https://{domain}/llms.txt"),
        "llms_full_txt": _make_artifact(
            ArtifactStatus.NOT_FOUND, f"https://{domain}/llms-full.txt"
        ),
    }
    defaults.update(overrides)
    return DomainArtifacts(**defaults)


def _make_evidence(**overrides):
    defaults = {
        "target_urls": ["https://example.com"],
        "domain_artifacts": [_make_domain_artifacts()],
        "pages": [],
    }
    defaults.update(overrides)
    return CollectGeoEvidenceResult(**defaults)


class TestArtifactContradictions:
    def test_no_contradiction_when_consistent(self):
        evidence = _make_evidence()
        draft = "The robots.txt is present on example.com."
        result = validate_claims(draft, evidence)
        contradictions = [f for f in result.contradictions if f.category == "artifact_existence"]
        assert len(contradictions) == 0

    def test_contradiction_when_artifact_found_but_draft_says_missing(self):
        evidence = _make_evidence()
        draft = "robots.txt is not found on example.com."
        result = validate_claims(draft, evidence)
        assert any(
            f.severity == Severity.HARD_CONTRADICTION and "robots.txt" in f.detail
            for f in result.contradictions
        )
        assert result.pass_ is False

    def test_contradiction_when_artifact_missing_but_draft_says_present(self):
        evidence = _make_evidence(
            domain_artifacts=[
                _make_domain_artifacts(
                    robots_txt=_make_artifact(
                        ArtifactStatus.NOT_FOUND, "https://example.com/robots.txt"
                    ),
                )
            ]
        )
        draft = "The site has robots.txt available."
        result = validate_claims(draft, evidence)
        assert any(
            f.severity == Severity.HARD_CONTRADICTION and "robots.txt" in f.detail
            for f in result.contradictions
        )

    def test_llms_txt_not_confused_with_llms_full_txt(self):
        evidence = _make_evidence(
            domain_artifacts=[
                _make_domain_artifacts(
                    llms_txt=_make_artifact(ArtifactStatus.FOUND, "https://example.com/llms.txt"),
                    llms_full_txt=_make_artifact(
                        ArtifactStatus.NOT_FOUND, "https://example.com/llms-full.txt"
                    ),
                )
            ]
        )
        draft = "llms-full.txt is present on example.com. llms.txt is not found."
        result = validate_claims(draft, evidence)
        # Should find contradictions for both: llms.txt IS found but draft says not, llms-full.txt NOT found but draft says present
        assert len(result.contradictions) == 2


class TestJsonLdContradictions:
    def test_no_contradiction_when_consistent(self):
        page = PageMetadata(
            url="https://example.com",
            json_ld_entries=[JsonLdEntry(types=["Organization"])],
        )
        evidence = _make_evidence(pages=[page])
        draft = "JSON-LD includes Organization schema."
        result = validate_claims(draft, evidence)
        jsonld_contradictions = [
            f for f in result.contradictions if f.category == "json_ld_presence"
        ]
        assert len(jsonld_contradictions) == 0

    def test_contradiction_when_jsonld_found_but_draft_says_none(self):
        page = PageMetadata(
            url="https://example.com",
            json_ld_entries=[JsonLdEntry(types=["Organization"])],
        )
        evidence = _make_evidence(pages=[page])
        draft = "No JSON-LD was found on the page."
        result = validate_claims(draft, evidence)
        assert any(
            f.severity == Severity.HARD_CONTRADICTION and "json_ld" in f.category
            for f in result.contradictions
        )


class TestTitleH1Contradictions:
    def test_no_finding_when_consistent(self):
        page = PageMetadata(
            url="https://example.com",
            title="My Page",
            h1_text="My Page",
            title_h1_match=True,
            title_h1_similarity=1.0,
        )
        evidence = _make_evidence(pages=[page])
        draft = "The title and H1 match on example.com."
        result = validate_claims(draft, evidence)
        assert all(f.category != "title_h1_comparison" for f in result.unsupported_claims)

    def test_unsupported_when_match_but_draft_says_mismatch(self):
        page = PageMetadata(
            url="https://example.com",
            title="My Page",
            h1_text="My Page",
            title_h1_match=True,
            title_h1_similarity=1.0,
        )
        evidence = _make_evidence(pages=[page])
        draft = "The title and H1 mismatch on the page."
        result = validate_claims(draft, evidence)
        assert any(
            f.severity == Severity.UNSUPPORTED and "title_h1" in f.category
            for f in result.unsupported_claims
        )


class TestMissingHighSignalFacts:
    def test_missing_llms_txt_mention(self):
        evidence = _make_evidence(
            domain_artifacts=[
                _make_domain_artifacts(
                    llms_txt=_make_artifact(ArtifactStatus.FOUND, "https://example.com/llms.txt"),
                )
            ]
        )
        draft = "The site has good SEO practices."
        result = validate_claims(draft, evidence)
        assert any(
            f.severity == Severity.MISSING_FACT and "llms.txt" in f.detail
            for f in result.missing_high_signal_facts
        )

    def test_no_missing_when_mentioned(self):
        evidence = _make_evidence(
            domain_artifacts=[
                _make_domain_artifacts(
                    llms_txt=_make_artifact(ArtifactStatus.FOUND, "https://example.com/llms.txt"),
                )
            ]
        )
        draft = "The llms.txt file is present and contains useful information."
        result = validate_claims(draft, evidence)
        assert all(
            "llms.txt" not in f.detail or f.severity != Severity.MISSING_FACT
            for f in result.missing_high_signal_facts
        )


class TestPassFlag:
    def test_passes_when_no_contradictions(self):
        evidence = _make_evidence()
        draft = "The site exists."
        result = validate_claims(draft, evidence)
        assert result.pass_ is True

    def test_fails_when_contradictions_exist(self):
        evidence = _make_evidence()
        draft = "robots.txt is not found on example.com."
        result = validate_claims(draft, evidence)
        assert result.pass_ is False
        assert result.total_findings > 0
