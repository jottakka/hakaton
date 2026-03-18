"""Tests for the canonical benchmark run contract (RunSpec, RunRecord, etc.)."""

from datetime import UTC

import pytest
from pydantic import ValidationError


class TestRunType:
    def test_valid_aioa_type(self):
        from benchmark_control_arcade.run_models import RunType

        assert RunType.aioa == "aioa"

    def test_valid_geo_type(self):
        from benchmark_control_arcade.run_models import RunType

        assert RunType.geo == "geo"

    def test_valid_geo_compare_type(self):
        from benchmark_control_arcade.run_models import RunType

        assert RunType.geo_compare == "geo_compare"

    def test_geo_compare_spec_roundtrip(self):
        from benchmark_control_arcade.run_models import RunSpec, RunType

        spec = RunSpec.model_validate(
            {
                "run_type": "geo_compare",
                "target": "arcade.dev",
                "options": {"competitors": ["composio.dev"]},
            }
        )
        assert spec.run_type == RunType.geo_compare
        assert spec.options["competitors"] == ["composio.dev"]
        # Roundtrip through JSON
        spec2 = RunSpec.model_validate_json(spec.model_dump_json())
        assert spec2.run_type == RunType.geo_compare


class TestRunStatus:
    def test_all_statuses_present(self):
        from benchmark_control_arcade.run_models import RunStatus

        assert RunStatus.queued == "queued"
        assert RunStatus.running == "running"
        assert RunStatus.completed == "completed"
        assert RunStatus.failed == "failed"


class TestRunSpec:
    def test_requires_run_type(self):
        with pytest.raises(ValidationError):
            from benchmark_control_arcade.run_models import RunSpec

            RunSpec.model_validate({"target": "composio.dev"})

    def test_requires_target(self):
        with pytest.raises(ValidationError):
            from benchmark_control_arcade.run_models import RunSpec

            RunSpec.model_validate({"run_type": "aioa"})

    def test_valid_minimal_spec(self):
        from benchmark_control_arcade.run_models import RunSpec, RunType

        spec = RunSpec.model_validate({"run_type": "aioa", "target": "composio.dev"})
        assert spec.run_type == RunType.aioa
        assert spec.target == "composio.dev"

    def test_valid_geo_spec(self):
        from benchmark_control_arcade.run_models import RunSpec, RunType

        spec = RunSpec.model_validate({"run_type": "geo", "target": "composio.dev"})
        assert spec.run_type == RunType.geo

    def test_rejects_unknown_run_type(self):
        with pytest.raises(ValidationError):
            from benchmark_control_arcade.run_models import RunSpec

            RunSpec.model_validate({"run_type": "unknown", "target": "composio.dev"})


class TestRunRecord:
    def test_required_fields(self):
        """RunRecord must have all required fields from the plan."""
        from benchmark_control_arcade.run_models import RunRecord

        fields = RunRecord.model_fields
        required = {
            "run_id",
            "run_type",
            "status",
            "created_at",
            "updated_at",
            "repo",
            "workflow_name",
            "data_branch",
            "spec",
        }
        for f in required:
            assert f in fields, f"Missing required field: {f}"

    def test_optional_fields_present(self):
        """artifacts, summary, error are optional (None by default)."""
        from benchmark_control_arcade.run_models import RunRecord

        fields = RunRecord.model_fields
        for f in ("artifacts", "summary", "error"):
            assert f in fields, f"Missing optional field: {f}"

    def test_default_status_is_queued(self):
        from datetime import datetime

        from benchmark_control_arcade.run_models import RunRecord, RunSpec, RunType

        spec = RunSpec(run_type=RunType.aioa, target="example.com")
        now = datetime.now(tz=UTC)
        record = RunRecord(
            run_id="run-001",
            run_type=RunType.aioa,
            created_at=now,
            updated_at=now,
            repo="acme/benchmarks",
            workflow_name="run-benchmark.yml",
            data_branch="benchmark-data",
            spec=spec,
        )
        assert record.status.value == "queued"

    def test_round_trip_json(self):
        from datetime import datetime

        from benchmark_control_arcade.run_models import RunRecord, RunSpec, RunType

        spec = RunSpec(run_type=RunType.geo, target="example.com")
        now = datetime.now(tz=UTC)
        record = RunRecord(
            run_id="run-geo-42",
            run_type=RunType.geo,
            created_at=now,
            updated_at=now,
            repo="acme/benchmarks",
            workflow_name="run-benchmark.yml",
            data_branch="benchmark-data",
            spec=spec,
        )
        json_str = record.model_dump_json()
        restored = RunRecord.model_validate_json(json_str)
        assert restored.run_id == "run-geo-42"
        assert restored.run_type == RunType.geo


class TestRunArtifact:
    def test_requires_name_and_path(self):
        with pytest.raises(ValidationError):
            from benchmark_control_arcade.run_models import RunArtifact

            RunArtifact.model_validate({"name": "report"})

    def test_valid_artifact(self):
        from benchmark_control_arcade.run_models import RunArtifact

        artifact = RunArtifact(name="report.json", path="runs/2026/03/18/run-1/report.json")
        assert artifact.name == "report.json"
