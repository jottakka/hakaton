#!/usr/bin/env python3
"""Arcade MCP server for GEO audits.

User-facing tools (what users call — one call does everything):
  - RunGeoSiteAudit  — single-site: collect → Claude analysis → validate → report
  - RunGeoCompare    — multi-site:  collect all → Claude comparison → validate → report

Internally these call collect_geo_evidence() and validate_claims() as plain
Python functions. Those are implementation details, not exposed as MCP tools.
"""

import json
import re
import sys
from typing import Annotated

from arcade_mcp_server import MCPApp

from geo_audit_arcade.tools.run_geo_audit import run_geo_audit
from geo_audit_arcade.tools.run_geo_compare import run_geo_compare

app = MCPApp(
    name="GeoAudit",
    version="0.3.0",
    instructions=(
        "GEO audit server. "
        "RunGeoSiteAudit audits a single site end-to-end: collects evidence, "
        "analyses with Claude, validates claims, returns the full report. "
        "RunGeoCompare does the same for a target vs competitors side by side."
    ),
    log_level="DEBUG",
)


def _parse_urls(raw: str) -> list[str]:
    """Parse URLs from a string -- newline-separated, comma-separated, or JSON array."""
    raw = raw.strip()
    if raw.startswith("["):
        try:
            return [u.strip() for u in json.loads(raw) if u.strip()]
        except (json.JSONDecodeError, TypeError):
            pass
    parts = re.split(r"[\n,]+", raw)
    return [p.strip() for p in parts if p.strip()]


@app.tool(requires_secrets=["ANTHROPIC_API_KEY"])
async def RunGeoSiteAudit(
    target_url: Annotated[str, "URL to audit (e.g. 'https://arcade.dev')"],
    audit_mode: Annotated[str, "exhaustive (default), standard, or quick"] = "exhaustive",
    coverage_preset: Annotated[str, "light, standard, deep, or exhaustive"] = "exhaustive",
    discover_subdomains: Annotated[bool, "Discover subdomains from page links"] = True,
) -> Annotated[str, "Complete GEO audit report as JSON"]:
    """Run a full GEO site audit — evidence collection, analysis, and validation.

    One call does everything: fetches deterministic evidence via HTTP, sends it
    to Claude for scoring and report generation, then validates the draft
    against the evidence. Returns the complete structured audit report.
    """
    result = await run_geo_audit(
        target_url=target_url,
        audit_mode=audit_mode,
        coverage_preset=coverage_preset,
        discover_subdomains=discover_subdomains,
    )
    return json.dumps(result, indent=2)


@app.tool(requires_secrets=["ANTHROPIC_API_KEY"])
async def RunGeoCompare(
    target: Annotated[str, "Primary site to audit (e.g. 'arcade.dev')"],
    competitors: Annotated[str, "Competitor URLs, comma-separated or JSON array"],
    audit_mode: Annotated[str, "exhaustive (default), standard, or quick"] = "exhaustive",
    coverage_preset: Annotated[str, "light, standard, deep, or exhaustive"] = "exhaustive",
    discover_subdomains: Annotated[bool, "Discover subdomains from page links"] = True,
) -> Annotated[str, "Complete GEO comparison report as JSON"]:
    """Run a full GEO competitive comparison — all sites audited side by side.

    One call does everything: fetches deterministic evidence for all URLs in
    one batch, sends it to Claude for per-site scoring and comparison, then
    validates draft claims against the evidence. Returns the complete
    structured comparison report.
    """
    competitor_list = _parse_urls(competitors)
    if not competitor_list:
        return json.dumps({"error": "No valid competitor URLs provided"})
    result = await run_geo_compare(
        target=target,
        competitors=competitor_list,
        audit_mode=audit_mode,
        coverage_preset=coverage_preset,
        discover_subdomains=discover_subdomains,
    )
    return json.dumps(result, indent=2)


if __name__ == "__main__":
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    app.run(transport=transport, host="127.0.0.1", port=8000)
