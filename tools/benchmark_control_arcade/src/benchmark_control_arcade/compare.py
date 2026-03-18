"""Comparison helpers for benchmark runs.

v1 supports AIOA-only comparisons. Cross-type comparisons are out of scope.
"""

from __future__ import annotations

from typing import Any

from benchmark_control_arcade.run_models import RunRecord, RunType


def compare_aioa_runs(record_a: RunRecord, record_b: RunRecord) -> dict[str, Any]:
    """Return a structured comparison of two completed AIOA runs.

    Raises:
        ValueError: If either record is not of run_type "aioa".
    """
    for record in (record_a, record_b):
        if record.run_type != RunType.aioa:
            raise ValueError(
                f"CompareAioaRuns only supports aioa runs; "
                f"run {record.run_id!r} has type {record.run_type.value!r}"
            )

    return {
        "run_id_a": record_a.run_id,
        "run_id_b": record_b.run_id,
        "target_a": record_a.spec.target,
        "target_b": record_b.spec.target,
        "status_a": record_a.status.value,
        "status_b": record_b.status.value,
        "summary_a": record_a.summary,
        "summary_b": record_b.summary,
        "created_at_a": record_a.created_at.isoformat(),
        "created_at_b": record_b.created_at.isoformat(),
    }
