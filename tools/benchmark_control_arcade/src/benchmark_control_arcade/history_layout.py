"""Per-run storage layout for the data branch.

Each run gets its own directory. There is no global manifest.
The layout is:

    runs/YYYY/MM/DD/<run_id>/run.json
    runs/YYYY/MM/DD/<run_id>/report.json
    runs/YYYY/MM/DD/<run_id>/report.md
    runs/YYYY/MM/DD/<run_id>/artifacts/...

All helpers are pure functions that return Path objects relative to the
data-branch root. Callers are responsible for reading/writing the files.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


def run_directory(run_id: str, created_at: datetime) -> Path:
    """Return the per-run directory path (relative to data-branch root)."""
    return (
        Path("runs")
        / f"{created_at.year:04d}"
        / f"{created_at.month:02d}"
        / f"{created_at.day:02d}"
        / run_id
    )


@dataclass(frozen=True)
class RunLayout:
    """All canonical paths for a single run."""

    run_dir: Path
    run_json: Path
    report_json: Path
    report_md: Path
    artifacts_dir: Path


def build_run_layout(run_id: str, created_at: datetime) -> RunLayout:
    """Return the full layout for a run."""
    run_dir = run_directory(run_id, created_at)
    return RunLayout(
        run_dir=run_dir,
        run_json=run_dir / "run.json",
        report_json=run_dir / "report.json",
        report_md=run_dir / "report.md",
        artifacts_dir=run_dir / "artifacts",
    )
