"""Tests for the per-run storage layout helpers."""

from datetime import datetime, timezone
from pathlib import Path


class TestRunDirectory:
    def test_path_is_date_partitioned(self):
        from benchmark_control_arcade.history_layout import run_directory

        ts = datetime(2026, 3, 18, tzinfo=timezone.utc)
        path = run_directory("run-123", ts)
        assert path.as_posix().endswith("runs/2026/03/18/run-123")

    def test_path_contains_run_id(self):
        from benchmark_control_arcade.history_layout import run_directory

        ts = datetime(2026, 1, 5, tzinfo=timezone.utc)
        path = run_directory("my-special-run", ts)
        assert "my-special-run" in path.as_posix()

    def test_month_and_day_zero_padded(self):
        from benchmark_control_arcade.history_layout import run_directory

        ts = datetime(2026, 1, 5, tzinfo=timezone.utc)
        path = run_directory("run-x", ts)
        assert "/2026/01/05/" in path.as_posix()

    def test_returns_path_object(self):
        from benchmark_control_arcade.history_layout import run_directory

        ts = datetime(2026, 3, 18, tzinfo=timezone.utc)
        assert isinstance(run_directory("run-1", ts), Path)


class TestBuildRunLayout:
    def test_run_json_is_named_run_json(self):
        from benchmark_control_arcade.history_layout import build_run_layout

        ts = datetime(2026, 3, 18, tzinfo=timezone.utc)
        layout = build_run_layout("run-123", ts)
        assert layout.run_json.name == "run.json"

    def test_no_manifest_in_any_path(self):
        from benchmark_control_arcade.history_layout import build_run_layout

        ts = datetime(2026, 3, 18, tzinfo=timezone.utc)
        layout = build_run_layout("run-123", ts)
        for path in (layout.run_json, layout.report_json, layout.report_md, layout.artifacts_dir):
            assert "manifest" not in path.as_posix(), f"Unexpected 'manifest' in {path}"

    def test_all_paths_under_same_run_dir(self):
        from benchmark_control_arcade.history_layout import build_run_layout

        ts = datetime(2026, 3, 18, tzinfo=timezone.utc)
        layout = build_run_layout("run-abc", ts)
        run_dir = layout.run_json.parent
        assert layout.report_json.parent == run_dir
        assert layout.report_md.parent == run_dir
        assert layout.artifacts_dir.parent == run_dir

    def test_artifacts_dir_named_artifacts(self):
        from benchmark_control_arcade.history_layout import build_run_layout

        ts = datetime(2026, 3, 18, tzinfo=timezone.utc)
        layout = build_run_layout("run-abc", ts)
        assert layout.artifacts_dir.name == "artifacts"

    def test_report_json_named_report_json(self):
        from benchmark_control_arcade.history_layout import build_run_layout

        ts = datetime(2026, 3, 18, tzinfo=timezone.utc)
        layout = build_run_layout("run-abc", ts)
        assert layout.report_json.name == "report.json"

    def test_report_md_named_report_md(self):
        from benchmark_control_arcade.history_layout import build_run_layout

        ts = datetime(2026, 3, 18, tzinfo=timezone.utc)
        layout = build_run_layout("run-abc", ts)
        assert layout.report_md.name == "report.md"

    def test_is_manifest_free_and_self_contained(self):
        """Canonical layout requirement from the plan."""
        from benchmark_control_arcade.history_layout import build_run_layout

        ts = datetime(2026, 3, 18, tzinfo=timezone.utc)
        layout = build_run_layout("run-123", ts)
        assert layout.run_json.name == "run.json"
        assert "manifest" not in layout.run_json.as_posix()
