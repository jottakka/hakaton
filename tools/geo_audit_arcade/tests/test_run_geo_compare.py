"""Tests for the RunGeoCompare pipeline (run_geo_compare)."""

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


def _fake_evidence(urls: list[str]) -> CollectGeoEvidenceResult:
    domain_artifacts = []
    pages = []
    for url in urls:
        domain = url.replace("https://", "").rstrip("/")
        domain_artifacts.append(
            DomainArtifacts(
                domain=domain,
                robots_txt=ArtifactCheck(
                    url=f"https://{domain}/robots.txt",
                    status=ArtifactStatus.FOUND,
                    http_status=200,
                ),
                sitemap_xml=ArtifactCheck(
                    url=f"https://{domain}/sitemap.xml",
                    status=ArtifactStatus.FOUND,
                    http_status=200,
                ),
                llms_txt=ArtifactCheck(
                    url=f"https://{domain}/llms.txt",
                    status=ArtifactStatus.NOT_FOUND,
                    http_status=404,
                ),
                llms_full_txt=ArtifactCheck(
                    url=f"https://{domain}/llms-full.txt",
                    status=ArtifactStatus.NOT_FOUND,
                    http_status=404,
                ),
            )
        )
        pages.append(PageMetadata(url=url, http_status=200, title=domain))
    return CollectGeoEvidenceResult(
        target_urls=urls,
        discovered_domains=[u.replace("https://", "").rstrip("/") for u in urls],
        domain_artifacts=domain_artifacts,
        pages=pages,
        coverage_summary=CoverageSummary(
            preset="exhaustive",
            representative_page_budget=10,
            selected_page_count=len(urls),
            section_budget=5,
            section_count=1,
            extra_subdomain_budget=3,
            subdomain_count=0,
        ),
    )


def _fake_compare_response(target: str, competitors: list[str]) -> MagicMock:
    all_urls = [target] + competitors
    audits = [
        {
            "url": url,
            "overall_score": 80 - i * 5,
            "lever_scores": {
                "content_structure": 20 - i,
                "entity_authority": 20 - i,
                "technical": 20 - i,
                "citation": 20 - i * 2,
            },
            "artifacts": {
                "robots_txt": "found",
                "sitemap_xml": "found",
                "llms_txt": "not_found",
                "llms_full_txt": "not_found",
            },
            "strengths": ["Good structure"],
            "weaknesses": ["No llms.txt"],
            "recommendations": ["Add llms.txt"],
        }
        for i, url in enumerate(all_urls)
    ]
    result_json = json.dumps(
        {
            "target": target,
            "competitors": competitors,
            "run_date": "2026-03-18",
            "audits": audits,
            "comparison_table": "| Site | Overall |\n|------|---------|",
            "winner_per_lever": {
                "content_structure": target,
                "entity_authority": target,
                "technical": target,
                "citation": target,
            },
            "overall_winner": target,
            "report_markdown": f"# Comparison\n\nWinner: {target}",
        }
    )
    block = MagicMock()
    block.text = result_json
    msg = MagicMock()
    msg.content = [block]
    return msg


class TestRunGeoComparePipeline:
    @pytest.mark.asyncio
    async def test_collects_all_urls_in_one_batch(self):
        target = "https://arcade.dev"
        competitors = ["https://composio.dev"]
        all_urls = [target] + competitors
        evidence = _fake_evidence(all_urls)
        claude_msg = _fake_compare_response(target, competitors)

        with (
            patch(
                "geo_audit_arcade.tools.run_geo_compare.collect_geo_evidence",
                new=AsyncMock(return_value=evidence),
            ) as mock_collect,
            patch(
                "geo_audit_arcade.tools.run_geo_compare.anthropic.AsyncAnthropic",
            ) as mock_anthropic_cls,
        ):
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=claude_msg)
            mock_anthropic_cls.return_value = mock_client

            from geo_audit_arcade.tools.run_geo_compare import run_geo_compare

            await run_geo_compare(target=target, competitors=competitors)

        call_kwargs = mock_collect.call_args.kwargs
        assert set(call_kwargs["target_urls"]) == set(all_urls)

    @pytest.mark.asyncio
    async def test_returns_comparison_with_winner(self):
        target = "https://arcade.dev"
        competitors = ["https://composio.dev"]
        all_urls = [target] + competitors
        evidence = _fake_evidence(all_urls)
        claude_msg = _fake_compare_response(target, competitors)

        with (
            patch(
                "geo_audit_arcade.tools.run_geo_compare.collect_geo_evidence",
                new=AsyncMock(return_value=evidence),
            ),
            patch(
                "geo_audit_arcade.tools.run_geo_compare.anthropic.AsyncAnthropic",
            ) as mock_anthropic_cls,
        ):
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=claude_msg)
            mock_anthropic_cls.return_value = mock_client

            from geo_audit_arcade.tools.run_geo_compare import run_geo_compare

            result = await run_geo_compare(target=target, competitors=competitors)

        assert result["overall_winner"] == target
        assert result["target"] == target
        assert result["competitors"] == competitors
        assert "validation" in result

    @pytest.mark.asyncio
    async def test_passes_all_urls_in_user_message(self):
        target = "https://arcade.dev"
        competitors = ["https://composio.dev", "https://merge.dev"]
        all_urls = [target] + competitors
        evidence = _fake_evidence(all_urls)
        claude_msg = _fake_compare_response(target, competitors)

        with (
            patch(
                "geo_audit_arcade.tools.run_geo_compare.collect_geo_evidence",
                new=AsyncMock(return_value=evidence),
            ),
            patch(
                "geo_audit_arcade.tools.run_geo_compare.anthropic.AsyncAnthropic",
            ) as mock_anthropic_cls,
        ):
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=claude_msg)
            mock_anthropic_cls.return_value = mock_client

            from geo_audit_arcade.tools.run_geo_compare import run_geo_compare

            await run_geo_compare(target=target, competitors=competitors)

        call_kwargs = mock_client.messages.create.call_args.kwargs
        user_content = call_kwargs["messages"][0]["content"]
        assert "arcade.dev" in user_content
        assert "composio.dev" in user_content
        assert "merge.dev" in user_content

    @pytest.mark.asyncio
    async def test_validation_included_in_result(self):
        target = "https://arcade.dev"
        competitors = ["https://composio.dev"]
        all_urls = [target] + competitors
        evidence = _fake_evidence(all_urls)
        claude_msg = _fake_compare_response(target, competitors)

        with (
            patch(
                "geo_audit_arcade.tools.run_geo_compare.collect_geo_evidence",
                new=AsyncMock(return_value=evidence),
            ),
            patch(
                "geo_audit_arcade.tools.run_geo_compare.anthropic.AsyncAnthropic",
            ) as mock_anthropic_cls,
        ):
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=claude_msg)
            mock_anthropic_cls.return_value = mock_client

            from geo_audit_arcade.tools.run_geo_compare import run_geo_compare

            result = await run_geo_compare(target=target, competitors=competitors)

        v = result["validation"]
        assert "pass" in v
        assert "total_findings" in v
