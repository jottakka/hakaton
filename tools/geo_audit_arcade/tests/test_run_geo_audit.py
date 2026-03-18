"""Tests for the RunGeoSiteAudit pipeline (run_geo_audit)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from geo_audit_arcade.models import (
    ArtifactCheck,
    ArtifactStatus,
    CollectGeoEvidenceResult,
    CoverageSummary,
    DomainArtifacts,
    PageMetadata,
)


def _fake_evidence() -> CollectGeoEvidenceResult:
    return CollectGeoEvidenceResult(
        target_urls=["https://arcade.dev"],
        discovered_domains=["arcade.dev"],
        domain_artifacts=[
            DomainArtifacts(
                domain="arcade.dev",
                robots_txt=ArtifactCheck(
                    url="https://arcade.dev/robots.txt",
                    status=ArtifactStatus.FOUND,
                    http_status=200,
                ),
                sitemap_xml=ArtifactCheck(
                    url="https://arcade.dev/sitemap.xml",
                    status=ArtifactStatus.FOUND,
                    http_status=200,
                ),
                llms_txt=ArtifactCheck(
                    url="https://arcade.dev/llms.txt",
                    status=ArtifactStatus.NOT_FOUND,
                    http_status=404,
                ),
                llms_full_txt=ArtifactCheck(
                    url="https://arcade.dev/llms-full.txt",
                    status=ArtifactStatus.NOT_FOUND,
                    http_status=404,
                ),
            ),
        ],
        pages=[
            PageMetadata(url="https://arcade.dev", http_status=200, title="Arcade"),
        ],
        coverage_summary=CoverageSummary(
            preset="exhaustive",
            representative_page_budget=10,
            selected_page_count=1,
            section_budget=5,
            section_count=1,
            extra_subdomain_budget=3,
            subdomain_count=0,
        ),
    )


def _fake_claude_response(target_url: str = "https://arcade.dev") -> MagicMock:
    """Build a mock Anthropic message response."""
    result_json = json.dumps(
        {
            "target_url": target_url,
            "overall_score": 72,
            "claims": [
                {
                    "lever": 1,
                    "lever_name": "Content structure",
                    "score": 18,
                    "strengths": ["Clear headings"],
                    "weaknesses": ["No FAQ"],
                    "confidence": "high",
                    "recommendations": ["Add FAQ"],
                }
            ],
            "evidence": [{"url": target_url, "type": "page", "summary": "Homepage"}],
            "report_markdown": f"# GEO Audit: {target_url}\n\nOverall: 72/100",
        }
    )
    block = MagicMock()
    block.text = result_json
    msg = MagicMock()
    msg.content = [block]
    return msg


class TestRunGeoAuditPipeline:
    @pytest.mark.asyncio
    async def test_collects_evidence_then_calls_claude_then_validates(self):
        evidence = _fake_evidence()
        claude_msg = _fake_claude_response()

        with (
            patch(
                "geo_audit_arcade.tools.run_geo_audit.collect_geo_evidence",
                new=AsyncMock(return_value=evidence),
            ) as mock_collect,
            patch(
                "geo_audit_arcade.tools.run_geo_audit.anthropic.AsyncAnthropic",
            ) as mock_anthropic_cls,
        ):
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=claude_msg)
            mock_anthropic_cls.return_value = mock_client

            from geo_audit_arcade.tools.run_geo_audit import run_geo_audit

            result = await run_geo_audit(target_url="https://arcade.dev")

        mock_collect.assert_awaited_once()
        mock_client.messages.create.assert_awaited_once()
        assert result["target_url"] == "https://arcade.dev"
        assert result["overall_score"] == 72
        assert "validation" in result

    @pytest.mark.asyncio
    async def test_passes_evidence_in_user_message(self):
        evidence = _fake_evidence()
        claude_msg = _fake_claude_response()

        with (
            patch(
                "geo_audit_arcade.tools.run_geo_audit.collect_geo_evidence",
                new=AsyncMock(return_value=evidence),
            ),
            patch(
                "geo_audit_arcade.tools.run_geo_audit.anthropic.AsyncAnthropic",
            ) as mock_anthropic_cls,
        ):
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=claude_msg)
            mock_anthropic_cls.return_value = mock_client

            from geo_audit_arcade.tools.run_geo_audit import run_geo_audit

            await run_geo_audit(target_url="https://arcade.dev")

        call_kwargs = mock_client.messages.create.call_args.kwargs
        user_content = call_kwargs["messages"][0]["content"]
        assert "arcade.dev" in user_content
        assert "Evidence JSON" in user_content

    @pytest.mark.asyncio
    async def test_passes_options_to_evidence_collector(self):
        evidence = _fake_evidence()
        claude_msg = _fake_claude_response()

        with (
            patch(
                "geo_audit_arcade.tools.run_geo_audit.collect_geo_evidence",
                new=AsyncMock(return_value=evidence),
            ) as mock_collect,
            patch(
                "geo_audit_arcade.tools.run_geo_audit.anthropic.AsyncAnthropic",
            ) as mock_anthropic_cls,
        ):
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=claude_msg)
            mock_anthropic_cls.return_value = mock_client

            from geo_audit_arcade.tools.run_geo_audit import run_geo_audit

            await run_geo_audit(
                target_url="https://example.com",
                coverage_preset="light",
                discover_subdomains=False,
            )

        mock_collect.assert_awaited_once_with(
            target_urls=["https://example.com"],
            coverage_preset="light",
            discover_subdomains=False,
        )

    @pytest.mark.asyncio
    async def test_validation_included_in_result(self):
        evidence = _fake_evidence()
        claude_msg = _fake_claude_response()

        with (
            patch(
                "geo_audit_arcade.tools.run_geo_audit.collect_geo_evidence",
                new=AsyncMock(return_value=evidence),
            ),
            patch(
                "geo_audit_arcade.tools.run_geo_audit.anthropic.AsyncAnthropic",
            ) as mock_anthropic_cls,
        ):
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=claude_msg)
            mock_anthropic_cls.return_value = mock_client

            from geo_audit_arcade.tools.run_geo_audit import run_geo_audit

            result = await run_geo_audit(target_url="https://arcade.dev")

        v = result["validation"]
        assert "pass" in v
        assert "total_findings" in v
        assert "contradictions" in v
