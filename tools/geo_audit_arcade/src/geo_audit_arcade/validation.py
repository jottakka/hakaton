"""Deterministic claim validation against evidence JSON."""

from __future__ import annotations

import re

# Shared separator pattern: whitespace or short punctuation between an artifact
# name and a negation/positive keyword.  Catches parenthetical forms like
# "llms.txt (absent on Composio)" and colon forms like "robots.txt: missing".
_SEP = r"[\s()\[\]:,\-\u2013\u2014]{1,8}"

# Boundary-aware patterns for llms.txt vs llms-full.txt substring collision.
# "llms.txt" must not match as a substring of "llms-full.txt".
_LLMS_TXT_RE = re.compile(r"llms\.txt(?!-full)", re.IGNORECASE)
_LLMS_FULL_TXT_RE = re.compile(r"llms-full\.txt", re.IGNORECASE)

from .models import (
    ArtifactStatus,
    CollectGeoEvidenceResult,
    ConfidenceDowngrade,
    Severity,
    ValidateGeoAuditClaimsResult,
    ValidationFinding,
)


def validate_claims(
    draft_report: str,
    evidence: CollectGeoEvidenceResult,
) -> ValidateGeoAuditClaimsResult:
    findings: list[ValidationFinding] = []
    downgrades: list[ConfidenceDowngrade] = []

    findings.extend(_check_artifact_contradictions(draft_report, evidence))
    findings.extend(_check_json_ld_contradictions(draft_report, evidence))
    findings.extend(_check_title_h1_contradictions(draft_report, evidence))
    findings.extend(_check_missing_high_signal_facts(draft_report, evidence))

    contradictions = [f for f in findings if f.severity == Severity.HARD_CONTRADICTION]
    unsupported = [f for f in findings if f.severity == Severity.UNSUPPORTED]
    missing = [f for f in findings if f.severity == Severity.MISSING_FACT]

    for c in contradictions:
        downgrades.append(
            ConfidenceDowngrade(
                claim=c.detail,
                reason=f"Hard contradiction: {c.category}",
                suggested_confidence="low",
            )
        )

    total = len(findings)
    passed = len(contradictions) == 0

    return ValidateGeoAuditClaimsResult(
        contradictions=contradictions,
        unsupported_claims=unsupported,
        missing_high_signal_facts=missing,
        confidence_downgrades=downgrades,
        total_findings=total,
        **{"pass": passed},
    )


def _check_artifact_contradictions(
    draft: str,
    evidence: CollectGeoEvidenceResult,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    draft_lower = draft.lower()

    for da in evidence.domain_artifacts:
        domain = da.domain

        findings.extend(
            _check_single_artifact(
                draft_lower,
                domain,
                "robots.txt",
                da.robots_txt.status,
            )
        )
        findings.extend(
            _check_single_artifact(
                draft_lower,
                domain,
                "sitemap.xml",
                da.sitemap_xml.status,
            )
        )
        findings.extend(
            _check_single_artifact(
                draft_lower,
                domain,
                "llms.txt",
                da.llms_txt.status,
            )
        )
        findings.extend(
            _check_single_artifact(
                draft_lower,
                domain,
                "llms-full.txt",
                da.llms_full_txt.status,
            )
        )

    return findings


def _check_single_artifact(
    draft_lower: str,
    domain: str,
    artifact_name: str,
    actual_status: ArtifactStatus,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    a = re.escape(artifact_name)

    # Patterns that assert the artifact is NOT present
    not_found_patterns = [
        rf"{a}\s+(?:is|was|are)?\s*not\s+found",
        rf"{a}\s+(?:is|was)\s+(?:absent|missing)",
        rf"{a}\s+returns?\s+404",
        rf"no\s+{a}\b",
        # Freeform: allows "(absent", ": absent", "—absent", etc.
        rf"{a}{_SEP}(?:absent|missing|not found|404)\b",
    ]
    # Patterns that assert the artifact IS present — require unambiguous positive
    # predicate so negated sentences ("No llms.txt was found") don't match.
    found_patterns = [
        rf"{a}\s+(?:is|was)\s+(?:present|available|accessible)\b",
        rf"{a}\s+(?:exists|exist)\b",
        rf"(?:has|have|found|includes?|contains?)\s+{a}\b",
        rf"{a}\s+(?:returns?|returned)\s+(?:200|http\s*200)\b",
        # Freeform positive: "llms.txt (present on …)"
        rf"{a}{_SEP}(?:present|available|accessible)\b",
    ]

    draft_claims_not_found = any(re.search(p, draft_lower) for p in not_found_patterns)
    draft_claims_found = any(re.search(p, draft_lower) for p in found_patterns)

    if actual_status == ArtifactStatus.FOUND and draft_claims_not_found:
        findings.append(
            ValidationFinding(
                severity=Severity.HARD_CONTRADICTION,
                category="artifact_existence",
                detail=f"Draft says {artifact_name} is not found on {domain}, but evidence shows HTTP 200",
                evidence_key=f"domain_artifacts.{domain}.{artifact_name}",
            )
        )
    elif actual_status == ArtifactStatus.NOT_FOUND and draft_claims_found:
        findings.append(
            ValidationFinding(
                severity=Severity.HARD_CONTRADICTION,
                category="artifact_existence",
                detail=f"Draft says {artifact_name} exists on {domain}, but evidence shows it was not found",
                evidence_key=f"domain_artifacts.{domain}.{artifact_name}",
            )
        )

    return findings


def _check_json_ld_contradictions(
    draft: str,
    evidence: CollectGeoEvidenceResult,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    draft_lower = draft.lower()

    for page in evidence.pages:
        has_json_ld = len(page.json_ld_entries) > 0
        all_types = []
        for entry in page.json_ld_entries:
            all_types.extend(entry.types)

        no_jsonld_patterns = [
            r"no\s+json-ld\b",
            r"zero\s+json-ld\b",
            r"no\s+structured\s+data\b",
            r"json-ld\s+(?:is|was)\s+(?:absent|missing|not found)\b",
            r"json-ld\s+not\s+found\b",
            r"without\s+json-ld\b",
            r"lacks?\s+(?:json-ld|structured data)\b",
            # Freeform: "JSON-LD (absent", "structured data: missing", etc.
            rf"json-ld{_SEP}(?:absent|missing|not found)\b",
            rf"structured\s+data{_SEP}(?:absent|missing|not found)\b",
        ]
        # Require unambiguous positive predicate — avoid "found" since it appears in
        # "No JSON-LD found" (negated context)
        has_jsonld_patterns = [
            r"json-ld\s+(?:is|was)\s+(?:present|available)\b",
            r"(?:has|have|includes?|contains?)\s+json-ld\b",
            r"json-ld\s+(?:types?|schema|markup)\s+(?:present|detected)\b",
            r"json-ld\s+includes?\s+",
        ]

        draft_claims_no_jsonld = any(re.search(p, draft_lower) for p in no_jsonld_patterns)
        draft_claims_has_jsonld = any(re.search(p, draft_lower) for p in has_jsonld_patterns)

        if has_json_ld and draft_claims_no_jsonld:
            findings.append(
                ValidationFinding(
                    severity=Severity.HARD_CONTRADICTION,
                    category="json_ld_presence",
                    detail=f"Draft says no JSON-LD on {page.url}, but evidence found types: {all_types}",
                    evidence_key=f"pages.{page.url}.json_ld_entries",
                )
            )
        elif not has_json_ld and draft_claims_has_jsonld:
            findings.append(
                ValidationFinding(
                    severity=Severity.HARD_CONTRADICTION,
                    category="json_ld_presence",
                    detail=f"Draft says JSON-LD present on {page.url}, but evidence found none",
                    evidence_key=f"pages.{page.url}.json_ld_entries",
                )
            )

    return findings


def _check_title_h1_contradictions(
    draft: str,
    evidence: CollectGeoEvidenceResult,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    draft_lower = draft.lower()

    for page in evidence.pages:
        if page.title_h1_match is None:
            continue

        mismatch_patterns = [
            r"title.*h1.*mismatch",
            r"title.*h1.*differ",
            r"title.*h1.*different",
            r"h1.*title.*mismatch",
        ]
        match_patterns = [
            r"title.*h1.*match",
            r"title.*h1.*align",
            r"title.*h1.*consistent",
        ]

        draft_claims_mismatch = any(re.search(p, draft_lower) for p in mismatch_patterns)
        draft_claims_match = any(re.search(p, draft_lower) for p in match_patterns)

        if page.title_h1_match and draft_claims_mismatch:
            findings.append(
                ValidationFinding(
                    severity=Severity.UNSUPPORTED,
                    category="title_h1_comparison",
                    detail=f"Draft claims title/H1 mismatch on {page.url}, but they match (similarity={page.title_h1_similarity})",
                    evidence_key=f"pages.{page.url}.title_h1_match",
                )
            )
        elif not page.title_h1_match and draft_claims_match:
            findings.append(
                ValidationFinding(
                    severity=Severity.UNSUPPORTED,
                    category="title_h1_comparison",
                    detail=f"Draft claims title/H1 match on {page.url}, but they differ (similarity={page.title_h1_similarity})",
                    evidence_key=f"pages.{page.url}.title_h1_match",
                )
            )

    return findings


def _check_missing_high_signal_facts(
    draft: str,
    evidence: CollectGeoEvidenceResult,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    draft_lower = draft.lower()

    for da in evidence.domain_artifacts:
        # Use boundary-aware regex so "llms.txt" does not match as a substring
        # of "llms-full.txt" and vice-versa.
        if da.llms_txt.status == ArtifactStatus.FOUND and not _LLMS_TXT_RE.search(draft_lower):
            findings.append(
                ValidationFinding(
                    severity=Severity.MISSING_FACT,
                    category="missing_artifact_mention",
                    detail=f"llms.txt is present on {da.domain} but not mentioned in the draft",
                    evidence_key=f"domain_artifacts.{da.domain}.llms_txt",
                )
            )
        if da.llms_full_txt.status == ArtifactStatus.FOUND and not _LLMS_FULL_TXT_RE.search(
            draft_lower
        ):
            findings.append(
                ValidationFinding(
                    severity=Severity.MISSING_FACT,
                    category="missing_artifact_mention",
                    detail=f"llms-full.txt is present on {da.domain} but not mentioned in the draft",
                    evidence_key=f"domain_artifacts.{da.domain}.llms_full_txt",
                )
            )

        if da.declared_sitemaps:
            for sitemap_url in da.declared_sitemaps:
                if "/sitemap.xml" not in sitemap_url:
                    base_path = sitemap_url.split("/")[-1] if "/" in sitemap_url else sitemap_url
                    if (
                        base_path.lower() not in draft_lower
                        and "declared sitemap" not in draft_lower
                    ):
                        findings.append(
                            ValidationFinding(
                                severity=Severity.MISSING_FACT,
                                category="missing_declared_sitemap",
                                detail=f"robots.txt on {da.domain} declares sitemap at {sitemap_url} but draft does not mention it",
                                evidence_key=f"domain_artifacts.{da.domain}.declared_sitemaps",
                            )
                        )

    for page in evidence.pages:
        if page.json_ld_entries:
            all_types = []
            for entry in page.json_ld_entries:
                all_types.extend(entry.types)
            if all_types and "json-ld" not in draft_lower and "@type" not in draft_lower:
                findings.append(
                    ValidationFinding(
                        severity=Severity.MISSING_FACT,
                        category="missing_json_ld_mention",
                        detail=f"JSON-LD types {all_types} found on {page.url} but not mentioned",
                        evidence_key=f"pages.{page.url}.json_ld_entries",
                    )
                )

    return findings
