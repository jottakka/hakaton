"""Tests for the FastMCP app wrappers."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from geo_audit_local_mcp.app import CollectGeoEvidence


class _FakeResult:
    def model_dump_json(self, indent=2):
        return json.dumps({"ok": True, "indent": indent})


@pytest.mark.asyncio
async def test_collect_geo_evidence_wrapper_passes_coverage_preset():
    with patch(
        "geo_audit_local_mcp.app.collect_geo_evidence",
        new=AsyncMock(return_value=_FakeResult()),
    ) as mock_collect:
        response = await CollectGeoEvidence(
            target_urls="https://example.com",
            coverage_preset="deep",
            max_related_pages=1,
        )

    mock_collect.assert_awaited_once_with(
        target_urls=["https://example.com"],
        coverage_preset="deep",
        discover_subdomains=True,
        max_related_pages=1,
    )
    assert json.loads(response) == {"ok": True, "indent": 2}
