#!/usr/bin/env python3
"""Arcade MCP server for GEO audits.

User-facing tools (what users call — one call does everything):
  - RunGeoSiteAudit  — single-site: collect → Claude analysis → validate → report
  - RunGeoCompare    — multi-site:  collect all → Claude comparison → validate → report

Internally these call collect_geo_evidence() and validate_claims() as plain
Python functions. Those are implementation details, not exposed as MCP tools.

Note: do NOT add ``from __future__ import annotations`` to this file.
arcade-mcp-server's @app.tool decorator uses inspect.signature() to read
parameter types at decoration time.  PEP 563 lazy annotations break that.
"""

import json
import re
import sys
from typing import Annotated

from arcade_mcp_server import MCPApp
from arcade_mcp_server.exceptions import ToolExecutionError
from arcade_mcp_server.metadata import (
    Behavior,
    Classification,
    Operation,
    ServiceDomain,
    ToolMetadata,
)

from geo_audit_arcade.models import AuditMode, CoveragePreset
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

_URL_RE = re.compile(r"^https?://[^\s/$.?#].\S*$", re.IGNORECASE)


def _validate_url(url: str, param_name: str = "target_url") -> str:
    """Normalise and validate a URL, raising ToolExecutionError on bad input."""
    url = url.strip()
    if not url:
        raise ToolExecutionError(f"`{param_name}` must not be empty.")
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    if not _URL_RE.match(url):
        raise ToolExecutionError(
            f"`{param_name}` is not a valid URL: {url!r}",
            developer_message=f"Received {url!r} which did not match URL pattern.",
        )
    return url


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


_AUDIT_METADATA = ToolMetadata(
    classification=Classification(
        service_domains=[ServiceDomain.WEB_SCRAPING],
    ),
    behavior=Behavior(
        operations=[Operation.READ],
        read_only=True,
        destructive=False,
        idempotent=True,
        open_world=True,
    ),
)


@app.tool(
    requires_secrets=["ANTHROPIC_API_KEY"],
    metadata=_AUDIT_METADATA,
)
async def RunGeoSiteAudit(
    target_url: Annotated[str, "URL to audit (e.g. 'https://arcade.dev')"],
    audit_mode: Annotated[
        AuditMode,
        "Depth of analysis: quick=~30s, standard=~60s, exhaustive=~90s",
    ] = AuditMode.EXHAUSTIVE,
    coverage_preset: Annotated[
        CoveragePreset,
        "Page budget: light=5, standard=15, deep=30, exhaustive=60 pages",
    ] = CoveragePreset.EXHAUSTIVE,
    discover_subdomains: Annotated[bool, "Discover subdomains from page links"] = True,
) -> Annotated[str, "Complete GEO audit report as JSON"]:
    """Run a full GEO site audit — evidence collection, analysis, and validation.

    One call does everything: fetches deterministic evidence via HTTP, sends it
    to Claude for scoring and report generation, then validates the draft
    against the evidence. Returns the complete structured audit report.
    """
    target_url = _validate_url(target_url, "target_url")
    result = await run_geo_audit(
        target_url=target_url,
        audit_mode=audit_mode.value,
        coverage_preset=coverage_preset.value,
        discover_subdomains=discover_subdomains,
    )
    return json.dumps(result)


@app.tool(
    requires_secrets=["ANTHROPIC_API_KEY"],
    metadata=_AUDIT_METADATA,
)
async def RunGeoCompare(
    target: Annotated[str, "Primary site to audit (e.g. 'arcade.dev')"],
    competitors: Annotated[str, "Competitor URLs, comma-separated or JSON array"],
    audit_mode: Annotated[
        AuditMode,
        "Depth of analysis: quick=~30s, standard=~60s, exhaustive=~90s",
    ] = AuditMode.EXHAUSTIVE,
    coverage_preset: Annotated[
        CoveragePreset,
        "Page budget: light=5, standard=15, deep=30, exhaustive=60 pages",
    ] = CoveragePreset.EXHAUSTIVE,
    discover_subdomains: Annotated[bool, "Discover subdomains from page links"] = True,
) -> Annotated[str, "Complete GEO comparison report as JSON"]:
    """Run a full GEO competitive comparison — all sites audited side by side.

    One call does everything: fetches deterministic evidence for all URLs in
    one batch, sends it to Claude for per-site scoring and comparison, then
    validates draft claims against the evidence. Returns the complete
    structured comparison report.
    """
    target = _validate_url(target, "target")
    competitor_list = _parse_urls(competitors)
    if not competitor_list:
        raise ToolExecutionError(
            "No valid competitor URLs provided in `competitors`.",
            developer_message=f"Received competitors={competitors!r} → empty list.",
        )
    result = await run_geo_compare(
        target=target,
        competitors=competitor_list,
        audit_mode=audit_mode.value,
        coverage_preset=coverage_preset.value,
        discover_subdomains=discover_subdomains,
    )
    return json.dumps(result)


if __name__ == "__main__":
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    app.run(transport=transport, host="127.0.0.1", port=8000)
