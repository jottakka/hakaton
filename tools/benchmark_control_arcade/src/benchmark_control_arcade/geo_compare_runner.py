"""GEO competitive comparison runner — direct Python call, no agent loop."""

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from geo_audit_arcade.tools.run_geo_compare import run_geo_compare

from benchmark_control_arcade.publisher import Publisher
from benchmark_control_arcade.run_models import RunSpec, RunType

_RUN_ID_RE = re.compile(r"^run-(\d{14})-")


def _parse_created_at_from_run_id(run_id: str) -> datetime | None:
    """Parse the UTC datetime encoded in a run_id (run-YYYYMMDDHHMMSS-<hex>)."""
    m = _RUN_ID_RE.match(run_id)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None


async def run_geo_compare_benchmark(spec: RunSpec, run_id: str, output_dir: Path) -> dict[str, Any]:
    if spec.run_type is not RunType.geo_compare:
        raise ValueError(f"Expected run_type=geo_compare, got {spec.run_type}")

    competitors: list[str] = spec.options.get("competitors", [])
    result = await run_geo_compare(
        target=spec.target,
        competitors=competitors,
        audit_mode=spec.options.get("audit_mode", "exhaustive"),
        coverage_preset=spec.options.get("coverage_preset", "exhaustive"),
        discover_subdomains=spec.options.get("discover_subdomains", True),
    )

    created_at = _parse_created_at_from_run_id(run_id) or datetime.now(tz=UTC)
    pub = Publisher(run_id, created_at, output_dir)

    report_md_abs = pub.write_report_md(result.get("report_markdown", ""))
    report_json_abs = pub.write_report_json(result)

    artifact_paths = [
        str(report_md_abs.relative_to(output_dir)),
        str(report_json_abs.relative_to(output_dir)),
    ]

    summary: dict[str, Any] = {
        "target": spec.target,
        "competitors": competitors,
        "run_date": created_at.date().isoformat(),
        "overall_winner": result.get("overall_winner"),
        "winner_per_lever": result.get("winner_per_lever", {}),
        "scores": {
            audit["url"]: audit.get("overall_score")
            for audit in result.get("audits", [])
            if isinstance(audit, dict)
        },
    }

    return {
        "run_id": run_id,
        "artifacts": artifact_paths,
        "summary": summary,
    }
