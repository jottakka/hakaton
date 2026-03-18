"""Tests for publisher.Publisher.

Uses real temp directories for all file writes (not mocks).
Validates:
- write_report_md writes into the canonical run layout directory.
- write_report_json writes into the canonical run layout directory.
- write_artifact returns a RunArtifact with a correct relative path.
- artifacts() returns all registered artifacts.
- Publisher only writes within the run's own directory (never outside).
- Canonical paths match history_layout.build_run_layout expectations.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from benchmark_control_arcade.history_layout import build_run_layout
from benchmark_control_arcade.run_models import RunArtifact

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RUN_ID = "run-pub-test-001"
CREATED_AT = datetime(2026, 3, 18, 12, 0, 0, tzinfo=UTC)


def make_publisher(tmp_path: Path):
    from benchmark_control_arcade.publisher import Publisher

    return Publisher(run_id=RUN_ID, created_at=CREATED_AT, output_dir=tmp_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_write_report_md_creates_file_in_canonical_location(tmp_path: Path):
    """write_report_md must write report.md inside the canonical run dir."""
    pub = make_publisher(tmp_path)
    content = "# My Report\n\nHello."

    result_path = pub.write_report_md(content)

    expected_layout = build_run_layout(RUN_ID, CREATED_AT)
    expected_abs = tmp_path / expected_layout.report_md

    assert result_path == expected_abs
    assert result_path.exists()
    assert result_path.read_text() == content


def test_write_report_json_creates_file_in_canonical_location(tmp_path: Path):
    """write_report_json must write report.json inside the canonical run dir."""
    pub = make_publisher(tmp_path)
    data = {"score": 42, "items": ["a", "b"]}

    result_path = pub.write_report_json(data)

    expected_layout = build_run_layout(RUN_ID, CREATED_AT)
    expected_abs = tmp_path / expected_layout.report_json

    assert result_path == expected_abs
    assert result_path.exists()
    parsed = json.loads(result_path.read_text())
    assert parsed == data


def test_write_artifact_returns_run_artifact_with_relative_path(tmp_path: Path):
    """write_artifact must return a RunArtifact whose path is relative to output_dir."""
    pub = make_publisher(tmp_path)
    content = b"binary content here"
    artifact_name = "results.bin"

    artifact = pub.write_artifact(artifact_name, content)

    assert isinstance(artifact, RunArtifact)
    assert artifact.name == artifact_name

    # path must be relative (not absolute)
    artifact_path = Path(artifact.path)
    assert not artifact_path.is_absolute(), (
        f"artifact path should be relative, got: {artifact.path}"
    )

    # the file must actually exist on disk
    abs_path = tmp_path / artifact_path
    assert abs_path.exists()
    assert abs_path.read_bytes() == content


def test_write_artifact_is_inside_run_directory(tmp_path: Path):
    """Artifact must land inside the canonical run directory, not outside it."""
    pub = make_publisher(tmp_path)
    artifact = pub.write_artifact("output.json", b"{}")

    artifact_abs = tmp_path / artifact.path

    layout = build_run_layout(RUN_ID, CREATED_AT)
    run_dir_abs = tmp_path / layout.run_dir

    # The artifact must be a descendant of run_dir
    assert str(artifact_abs).startswith(str(run_dir_abs)), (
        f"Artifact {artifact_abs} is outside run dir {run_dir_abs}"
    )


def test_artifacts_returns_all_registered_artifacts(tmp_path: Path):
    """artifacts() must return all artifacts registered via write_artifact."""
    pub = make_publisher(tmp_path)

    _art1 = pub.write_artifact("file1.json", b'{"a": 1}')
    _art2 = pub.write_artifact("file2.bin", b"\x00\x01\x02")

    result = pub.artifacts()

    assert len(result) == 2
    names = {a.name for a in result}
    assert names == {"file1.json", "file2.bin"}


def test_publisher_does_not_write_outside_run_directory(tmp_path: Path):
    """Publisher must never write files outside its own run directory."""
    pub = make_publisher(tmp_path)

    pub.write_report_md("# test")
    pub.write_report_json({"x": 1})
    pub.write_artifact("extra.bin", b"data")

    layout = build_run_layout(RUN_ID, CREATED_AT)
    run_dir_abs = tmp_path / layout.run_dir

    all_written: list[Path] = []
    for p in tmp_path.rglob("*"):
        if p.is_file():
            all_written.append(p)

    for written_file in all_written:
        assert str(written_file).startswith(str(run_dir_abs)), (
            f"Publisher wrote a file outside its run directory: {written_file}"
        )


def test_write_report_md_creates_parent_dirs_automatically(tmp_path: Path):
    """write_report_md must create intermediate dirs if they don't exist."""
    pub = make_publisher(tmp_path)
    # output_dir is fresh, no subdirs exist yet
    result = pub.write_report_md("hello")
    assert result.exists()


def test_write_artifact_content_type_defaults_to_octet_stream(tmp_path: Path):
    """Default content_type on RunArtifact should be application/octet-stream."""
    pub = make_publisher(tmp_path)
    artifact = pub.write_artifact("blob.bin", b"data")
    assert artifact.content_type == "application/octet-stream"


def test_write_artifact_accepts_custom_content_type(tmp_path: Path):
    """write_artifact must accept and propagate a custom content_type."""
    pub = make_publisher(tmp_path)
    artifact = pub.write_artifact("report.json", b"{}", content_type="application/json")
    assert artifact.content_type == "application/json"
