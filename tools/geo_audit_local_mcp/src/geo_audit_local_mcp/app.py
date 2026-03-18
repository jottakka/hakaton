"""Local deterministic MCP server for geo-site-audit.

Uses FastMCP (standard mcp library) so tool names are exposed exactly as
specified -- CollectGeoEvidence and ValidateGeoAuditClaims -- without the
namespace prefix that Arcade's MCPApp adds.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .tools.collect_geo_evidence import collect_geo_evidence
from .tools.validate_geo_audit_claims import validate_geo_audit_claims

app = FastMCP(
    name="geo-audit-local",
    instructions=(
        "Deterministic GEO evidence collection and claim validation for geo-site-audit. "
        "Call CollectGeoEvidence before scoring, then ValidateGeoAuditClaims before final output."
    ),
)


def _parse_urls(raw: str) -> list[str]:
    """Parse URLs from a string — newline-separated, comma-separated, or JSON array."""
    raw = raw.strip()
    if raw.startswith("["):
        try:
            return [u.strip() for u in json.loads(raw) if u.strip()]
        except (json.JSONDecodeError, TypeError):
            pass
    parts = re.split(r"[\n,]+", raw)
    return [p.strip() for p in parts if p.strip()]


@app.tool()
async def CollectGeoEvidence(
    target_urls: str,
    coverage_preset: str = "exhaustive",
    discover_subdomains: bool = True,
    max_related_pages: Optional[int] = None,
) -> str:
    """Collect deterministic GEO evidence for public URLs.

    Returns structured JSON with artifact checks (robots.txt, sitemap.xml,
    llms.txt, llms-full.txt), page metadata, JSON-LD types, heading extraction,
    title/H1 comparison, first-200-word extraction, subdomain discovery, and
    a bounded representative page set selected from the candidate pool.

    Args:
        target_urls: Public URLs to audit -- newline-separated, comma-separated,
            or a JSON array string (e.g. '["https://example.com/", "https://docs.example.com/"]').
        coverage_preset: One of light, standard, deep, or exhaustive.
        discover_subdomains: Discover additional subdomains from page links.
        max_related_pages: Deprecated legacy override for the representative
            page budget. Prefer coverage_preset instead.

    Call this before scoring on every audit. Treat its JSON as the hard-fact
    evidence pack for technical findings.
    """
    urls = _parse_urls(target_urls)
    if not urls:
        return json.dumps({"error": "No valid URLs provided"})
    result = await collect_geo_evidence(
        target_urls=urls,
        coverage_preset=coverage_preset,
        discover_subdomains=discover_subdomains,
        max_related_pages=max_related_pages,
    )
    return result.model_dump_json(indent=2)


@app.tool()
async def ValidateGeoAuditClaims(
    draft_report: str,
    evidence_json: str,
) -> str:
    """Validate a draft GEO audit against deterministic evidence.

    Checks for hard contradictions (artifact claimed missing when HTTP 200 was
    observed, JSON-LD claimed absent when types were found), unsupported claims
    (title/H1 mismatch that evidence disproves), and missing high-signal facts
    (llms.txt present but unmentioned).

    Args:
        draft_report: The full text of the draft GEO audit report.
        evidence_json: JSON string output from CollectGeoEvidence.

    Call this after drafting the report and before final output. Revise
    contradictions before responding. Keep final scoring model-driven.
    """
    try:
        evidence_dict = json.loads(evidence_json)
    except json.JSONDecodeError as exc:
        return json.dumps({"error": f"evidence_json is not valid JSON: {exc}"})
    result = await validate_geo_audit_claims(
        draft_report=draft_report,
        evidence_json=evidence_dict,
    )
    return result.model_dump_json(indent=2, by_alias=True)


def main() -> None:
    app.run(transport="stdio")


if __name__ == "__main__":
    main()
