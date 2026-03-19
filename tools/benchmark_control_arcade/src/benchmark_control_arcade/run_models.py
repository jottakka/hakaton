"""Canonical run contract for BenchmarkControl.

All benchmark runs — AIOA or GEO — share these types. A RunRecord is the
single source of truth written to and read from the data branch.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RunType(StrEnum):
    """The class of benchmark being run."""

    aioa = "aioa"
    geo = "geo"
    geo_compare = "geo_compare"


class RunStatus(StrEnum):
    """Lifecycle state of a benchmark run."""

    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class RunSpec(BaseModel):
    """Input specification for a benchmark run.

    Validated at StartRun time. Passed as-is to the execution workflow.
    """

    run_type: RunType
    target: str
    # Optional overrides — None means "use workflow defaults"
    options: dict[str, Any] = Field(default_factory=dict)


class RunArtifact(BaseModel):
    """Reference to a file produced by a benchmark run."""

    name: str
    path: str
    content_type: str = "application/octet-stream"


class RunRecord(BaseModel):
    """Canonical per-run record written to the data branch as run.json.

    The only mutable state in the system. Updated by the execution workflow
    as the run transitions through its lifecycle.
    """

    run_id: str
    run_type: RunType
    status: RunStatus = RunStatus.queued
    created_at: datetime
    updated_at: datetime

    # GitHub context
    repo: str  # "owner/repo"
    workflow_name: str
    data_branch: str

    # Run input
    spec: RunSpec

    # Run output (populated by the execution workflow)
    artifacts: list[RunArtifact] = Field(default_factory=list)
    summary: dict[str, Any] | None = None
    error: str | None = None
    elapsed_seconds: float | None = Field(
        default=None,
        description="Wall-clock seconds from run start to completion or failure.",
    )
