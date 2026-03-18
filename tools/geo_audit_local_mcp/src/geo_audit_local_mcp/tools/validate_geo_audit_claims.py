"""ValidateGeoAuditClaims tool: compare draft audit against evidence JSON."""

from __future__ import annotations

from ..models import CollectGeoEvidenceResult, ValidateGeoAuditClaimsResult
from ..validation import validate_claims


async def validate_geo_audit_claims(
    draft_report: str,
    evidence_json: dict,
) -> ValidateGeoAuditClaimsResult:
    evidence = CollectGeoEvidenceResult.model_validate(evidence_json)
    return validate_claims(draft_report, evidence)
