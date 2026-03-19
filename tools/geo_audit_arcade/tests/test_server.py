"""Tests for the GeoAudit Arcade MCP server — user-facing tools."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from arcade_mcp_server.exceptions import ToolExecutionError

from geo_audit_arcade.models import AuditMode, CoveragePreset


class TestServerImport:
    def test_app_loads(self):
        from geo_audit_arcade.server import app

        assert app.name == "GeoAudit"
        assert app.version == "0.3.0"

    def test_app_has_instructions(self):
        from geo_audit_arcade.server import app

        assert app.instructions is not None
        assert "RunGeoSiteAudit" in app.instructions
        assert "RunGeoCompare" in app.instructions


class TestRunGeoSiteAudit:
    @pytest.mark.asyncio
    async def test_calls_pipeline_and_returns_json(self):
        fake_result = {
            "target_url": "https://arcade.dev",
            "overall_score": 75,
            "report_markdown": "# Audit",
        }
        with patch(
            "geo_audit_arcade.server.run_geo_audit",
            new=AsyncMock(return_value=fake_result),
        ) as mock:
            from geo_audit_arcade.server import RunGeoSiteAudit

            result = await RunGeoSiteAudit(target_url="https://arcade.dev")

        mock.assert_awaited_once_with(
            target_url="https://arcade.dev",
            audit_mode="exhaustive",
            coverage_preset="exhaustive",
            discover_subdomains=True,
        )
        parsed = json.loads(result)
        assert parsed["target_url"] == "https://arcade.dev"
        assert parsed["overall_score"] == 75

    @pytest.mark.asyncio
    async def test_passes_custom_options(self):
        with patch(
            "geo_audit_arcade.server.run_geo_audit",
            new=AsyncMock(return_value={"target_url": "x"}),
        ) as mock:
            from geo_audit_arcade.server import RunGeoSiteAudit

            await RunGeoSiteAudit(
                target_url="https://example.com",
                audit_mode=AuditMode.QUICK,
                coverage_preset=CoveragePreset.LIGHT,
                discover_subdomains=False,
            )

        mock.assert_awaited_once_with(
            target_url="https://example.com",
            audit_mode="quick",
            coverage_preset="light",
            discover_subdomains=False,
        )

    @pytest.mark.asyncio
    async def test_validates_empty_url(self):
        from geo_audit_arcade.server import RunGeoSiteAudit

        with pytest.raises(ToolExecutionError, match="must not be empty"):
            await RunGeoSiteAudit(target_url="")

    @pytest.mark.asyncio
    async def test_auto_prefixes_https(self):
        with patch(
            "geo_audit_arcade.server.run_geo_audit",
            new=AsyncMock(return_value={}),
        ) as mock:
            from geo_audit_arcade.server import RunGeoSiteAudit

            await RunGeoSiteAudit(target_url="arcade.dev")

        mock.assert_awaited_once()
        assert mock.call_args.kwargs["target_url"] == "https://arcade.dev"


class TestRunGeoCompare:
    @pytest.mark.asyncio
    async def test_calls_pipeline_with_parsed_competitors(self):
        fake_result = {
            "target": "arcade.dev",
            "competitors": ["composio.dev"],
            "overall_winner": "arcade.dev",
        }
        with patch(
            "geo_audit_arcade.server.run_geo_compare",
            new=AsyncMock(return_value=fake_result),
        ) as mock:
            from geo_audit_arcade.server import RunGeoCompare

            result = await RunGeoCompare(
                target="arcade.dev",
                competitors="composio.dev, merge.dev",
            )

        mock.assert_awaited_once_with(
            target="https://arcade.dev",
            competitors=["composio.dev", "merge.dev"],
            audit_mode="exhaustive",
            coverage_preset="exhaustive",
            discover_subdomains=True,
        )
        parsed = json.loads(result)
        assert parsed["target"] == "arcade.dev"

    @pytest.mark.asyncio
    async def test_accepts_json_array_competitors(self):
        with patch(
            "geo_audit_arcade.server.run_geo_compare",
            new=AsyncMock(return_value={}),
        ) as mock:
            from geo_audit_arcade.server import RunGeoCompare

            await RunGeoCompare(
                target="arcade.dev",
                competitors='["composio.dev", "workato.com"]',
            )

        assert mock.call_args.kwargs["competitors"] == [
            "composio.dev",
            "workato.com",
        ]

    @pytest.mark.asyncio
    async def test_raises_on_empty_competitors(self):
        from geo_audit_arcade.server import RunGeoCompare

        with pytest.raises(ToolExecutionError, match="No valid competitor URLs"):
            await RunGeoCompare(target="arcade.dev", competitors="")


class TestUrlParsing:
    def test_newline_separated(self):
        from geo_audit_arcade.server import _parse_urls

        result = _parse_urls("https://a.com\nhttps://b.com\nhttps://c.com")
        assert result == ["https://a.com", "https://b.com", "https://c.com"]

    def test_comma_separated(self):
        from geo_audit_arcade.server import _parse_urls

        result = _parse_urls("https://a.com, https://b.com")
        assert result == ["https://a.com", "https://b.com"]

    def test_json_array(self):
        from geo_audit_arcade.server import _parse_urls

        result = _parse_urls('["https://a.com", "https://b.com"]')
        assert result == ["https://a.com", "https://b.com"]

    def test_single_url(self):
        from geo_audit_arcade.server import _parse_urls

        result = _parse_urls("https://example.com")
        assert result == ["https://example.com"]

    def test_empty_string(self):
        from geo_audit_arcade.server import _parse_urls

        result = _parse_urls("")
        assert result == []

    def test_whitespace_only(self):
        from geo_audit_arcade.server import _parse_urls

        result = _parse_urls("   \n  \n  ")
        assert result == []
