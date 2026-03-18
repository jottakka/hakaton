"""Typed JSON contracts for deterministic GEO audit tools."""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import AnyHttpUrl, BaseModel, Field

CoveragePreset = Literal["light", "standard", "deep", "exhaustive"]
CandidateSource = Literal[
    "target",
    "root",
    "sitemap",
    "llms",
    "nav",
    "footer",
    "path_cluster",
    "redirect",
    "manual",
]


class ArtifactStatus(str, Enum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    REDIRECT = "redirect"
    ERROR = "error"


class ArtifactCheck(BaseModel):
    url: str
    status: ArtifactStatus
    http_status: Optional[int] = None
    redirect_target: Optional[str] = None
    content_snippet: Optional[str] = Field(
        default=None,
        description="Full fetched body (up to 4 KB) when status is found",
    )
    error_detail: Optional[str] = Field(
        default=None,
        description="Error message when status is error (e.g. timeout, connect_error)",
    )


class DomainArtifacts(BaseModel):
    domain: str
    robots_txt: ArtifactCheck
    sitemap_xml: ArtifactCheck
    declared_sitemaps: list[str] = Field(default_factory=list)
    llms_txt: ArtifactCheck
    llms_full_txt: ArtifactCheck


class OpenGraphTags(BaseModel):
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_type: Optional[str] = None
    og_image: Optional[str] = None


class JsonLdEntry(BaseModel):
    types: list[str] = Field(default_factory=list)
    raw_snippet: Optional[str] = Field(
        default=None,
        description="First 300 chars of the JSON-LD block",
    )


class HeadingItem(BaseModel):
    level: int
    text: str


class PageMetadata(BaseModel):
    url: str
    http_status: Optional[int] = None
    title: Optional[str] = None
    meta_description: Optional[str] = None
    canonical: Optional[str] = None
    open_graph: OpenGraphTags = Field(default_factory=OpenGraphTags)
    json_ld_entries: list[JsonLdEntry] = Field(default_factory=list)
    headings: list[HeadingItem] = Field(default_factory=list)
    h1_text: Optional[str] = None
    title_h1_match: Optional[bool] = None
    title_h1_similarity: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
    )
    first_200_words: Optional[str] = None
    is_sampled: bool = Field(
        default=False,
        description="True when this page was auto-sampled as a related page, not explicitly requested",
    )


class CandidatePage(BaseModel):
    url: AnyHttpUrl
    source: CandidateSource
    section_key: Optional[str] = None
    subdomain_key: Optional[str] = None
    selection_reason: Optional[str] = None
    selected: bool = False


class CoverageSummary(BaseModel):
    preset: CoveragePreset
    representative_page_budget: int = Field(ge=0)
    selected_page_count: int = Field(ge=0)
    section_budget: int = Field(ge=0)
    section_count: int = Field(ge=0)
    extra_subdomain_budget: int = Field(ge=0)
    subdomain_count: int = Field(ge=0)
    truncated: bool = False


class CollectGeoEvidenceResult(BaseModel):
    """Structured JSON output from CollectGeoEvidence."""

    target_urls: list[str]
    discovered_domains: list[str] = Field(default_factory=list)
    domain_artifacts: list[DomainArtifacts] = Field(default_factory=list)
    pages: list[PageMetadata] = Field(default_factory=list)
    candidate_pages: list[CandidatePage] = Field(default_factory=list)
    coverage_summary: Optional[CoverageSummary] = None
    warnings: list[str] = Field(default_factory=list)


class Severity(str, Enum):
    HARD_CONTRADICTION = "hard_contradiction"
    UNSUPPORTED = "unsupported"
    MISSING_FACT = "missing_fact"


class ValidationFinding(BaseModel):
    severity: Severity
    category: str
    detail: str
    evidence_key: Optional[str] = Field(
        default=None,
        description="JSON path or key in evidence that supports this finding",
    )


class ConfidenceDowngrade(BaseModel):
    claim: str
    reason: str
    suggested_confidence: str = "low"


class ValidateGeoAuditClaimsResult(BaseModel):
    """Structured JSON output from ValidateGeoAuditClaims."""

    contradictions: list[ValidationFinding] = Field(default_factory=list)
    unsupported_claims: list[ValidationFinding] = Field(default_factory=list)
    missing_high_signal_facts: list[ValidationFinding] = Field(default_factory=list)
    confidence_downgrades: list[ConfidenceDowngrade] = Field(default_factory=list)
    total_findings: int = 0
    pass_: bool = Field(default=True, alias="pass")

    model_config = {"populate_by_name": True}
