"""GEO benchmark runner — direct Python call, no agent loop."""

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from geo_audit_arcade.tools.run_geo_audit import run_geo_audit

from benchmark_control_arcade.publisher import Publisher
from benchmark_control_arcade.run_models import RunSpec, RunType

_RUN_ID_RE = re.compile(r"^run-(\d{14})-")


def _parse_created_at(run_id: str) -> datetime:
    match = _RUN_ID_RE.match(run_id)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d%H%M%S").replace(tzinfo=UTC)
        except ValueError:
            pass
    return datetime.now(tz=UTC)


async def run_geo_benchmark(spec: RunSpec, run_id: str, output_dir: Path) -> dict[str, Any]:
    if spec.run_type is not RunType.geo:
        raise ValueError(f"Expected run_type=geo, got {spec.run_type}")

    result = await run_geo_audit(
        target_url=spec.target,
        audit_mode=spec.options.get("audit_mode", "exhaustive"),
        coverage_preset=spec.options.get("coverage_preset", "exhaustive"),
        discover_subdomains=spec.options.get("discover_subdomains", True),
    )

    created_at = _parse_created_at(run_id)
    publisher = Publisher(run_id, created_at, output_dir)
    report_md_abs = publisher.write_report_md(result.get("report_markdown", ""))
    report_json_abs = publisher.write_report_json(result)

    return {
        "run_id": run_id,
        "artifacts": [
            str(report_md_abs.relative_to(output_dir)),
            str(report_json_abs.relative_to(output_dir)),
        ],
        "summary": {
            "target": spec.target,
            "overall_score": result.get("overall_score"),
        },
    }
