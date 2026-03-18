"""Tests for the BenchmarkControl Arcade MCP server entry point."""

import pytest


class TestAppLoads:
    def test_app_loads_with_expected_name_and_version(self):
        from benchmark_control_arcade.server import app

        assert app.name == "BenchmarkControl"
        assert app.version == "0.1.0"

    def test_app_has_instructions(self):
        from benchmark_control_arcade.server import app

        assert app.instructions is not None
        assert len(app.instructions) > 0
