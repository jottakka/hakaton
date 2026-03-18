"""Tests for coverage preset selection helpers."""

from geo_audit_local_mcp.selection import PRESET_CONFIG, get_preset_config


class TestPresetConfig:
    def test_exposes_all_named_presets(self):
        assert set(PRESET_CONFIG) == {"light", "standard", "deep", "exhaustive"}

    def test_returns_expected_bounded_values(self):
        assert get_preset_config("light") == {
            "pages": 4,
            "sections": 2,
            "subdomains": 1,
            "per_lane_cap": 2,
        }
        assert get_preset_config("standard") == {
            "pages": 8,
            "sections": 4,
            "subdomains": 2,
            "per_lane_cap": 3,
        }
        assert get_preset_config("deep") == {
            "pages": 12,
            "sections": 6,
            "subdomains": 3,
            "per_lane_cap": 4,
        }
        assert get_preset_config("exhaustive") == {
            "pages": 18,
            "sections": 8,
            "subdomains": 4,
            "per_lane_cap": 6,
        }

    def test_preset_bounds_are_monotonic(self):
        light = get_preset_config("light")
        standard = get_preset_config("standard")
        deep = get_preset_config("deep")
        exhaustive = get_preset_config("exhaustive")

        assert light["pages"] < standard["pages"] < deep["pages"] < exhaustive["pages"]
        assert (
            light["sections"]
            < standard["sections"]
            < deep["sections"]
            < exhaustive["sections"]
        )
        assert (
            light["subdomains"]
            < standard["subdomains"]
            < deep["subdomains"]
            < exhaustive["subdomains"]
        )
        assert (
            light["per_lane_cap"]
            < standard["per_lane_cap"]
            < deep["per_lane_cap"]
            < exhaustive["per_lane_cap"]
        )
