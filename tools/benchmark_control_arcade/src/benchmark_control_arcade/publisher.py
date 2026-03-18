"""Publisher — the single authority over the on-disk run layout.

Writes all output files into the canonical per-run directory produced by
history_layout.build_run_layout(). Nothing outside the run's own directory
is ever touched.
"""

import json
from datetime import datetime
from pathlib import Path

from benchmark_control_arcade.history_layout import build_run_layout
from benchmark_control_arcade.run_models import RunArtifact


class Publisher:
    """Writes run artifacts and reports into the canonical run directory.

    The constructor receives the run identity (run_id + created_at) and the
    root *output_dir* that acts as the data-branch root. All writes go into:

        output_dir / runs / YYYY / MM / DD / <run_id> / ...

    The Publisher is the ONLY code that knows the exact on-disk layout.
    Callers receive back Path objects and RunArtifact records; they never
    construct paths themselves.
    """

    def __init__(self, run_id: str, created_at: datetime, output_dir: Path) -> None:
        self._run_id = run_id
        self._created_at = created_at
        self._output_dir = Path(output_dir)
        self._layout = build_run_layout(run_id, created_at)
        self._artifacts: list[RunArtifact] = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _abs(self, rel: Path) -> Path:
        """Resolve a layout-relative path to an absolute path under output_dir."""
        return self._output_dir / rel

    def _ensure_parent(self, abs_path: Path) -> None:
        abs_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write_report_md(self, content: str) -> Path:
        """Write *content* as the canonical report.md for this run.

        Returns the absolute path to the written file.
        """
        abs_path = self._abs(self._layout.report_md)
        self._ensure_parent(abs_path)
        abs_path.write_text(content, encoding="utf-8")
        return abs_path

    def write_report_json(self, content: dict) -> Path:
        """Write *content* (a dict) as the canonical report.json for this run.

        Returns the absolute path to the written file.
        """
        abs_path = self._abs(self._layout.report_json)
        self._ensure_parent(abs_path)
        abs_path.write_text(json.dumps(content, indent=2), encoding="utf-8")
        return abs_path

    def write_artifact(
        self,
        name: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> RunArtifact:
        """Write *content* as a named artifact inside this run's artifacts dir.

        Returns a RunArtifact whose *path* is relative to *output_dir*.
        The artifact is also registered and will be included in artifacts().
        """
        artifacts_abs = self._abs(self._layout.artifacts_dir)
        artifacts_abs.mkdir(parents=True, exist_ok=True)

        file_abs = artifacts_abs / name
        file_abs.write_bytes(content)

        rel_path = file_abs.relative_to(self._output_dir)
        artifact = RunArtifact(
            name=name,
            path=str(rel_path),
            content_type=content_type,
        )
        self._artifacts.append(artifact)
        return artifact

    def artifacts(self) -> list[RunArtifact]:
        """Return all RunArtifacts registered via write_artifact."""
        return list(self._artifacts)
