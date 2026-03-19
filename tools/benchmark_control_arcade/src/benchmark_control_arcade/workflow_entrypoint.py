"""Workflow entrypoint for benchmark runs.

This module is invoked by the GitHub Actions workflow as:

    python -m benchmark_control_arcade.workflow_entrypoint <run_id> <run_type> <run_spec_json>

It orchestrates the full lifecycle of a single benchmark run:
1. Load Settings and create GitHubClient.
2. Update run.json status to "running".
3. Parse RunSpec from run_spec_json.
4. Route to aioa_runner or geo_runner based on run_type.
5. Update run.json to "completed" with summary and artifacts.
6. On any exception: update run.json to "failed" with error message.

Errors are always caught and recorded — this process must never exit non-zero
while leaving run.json in "running" state.
"""

import asyncio
import base64
import logging
import re
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from benchmark_control_arcade.config import Settings
from benchmark_control_arcade.github_client import GitHubClient
from benchmark_control_arcade.history_layout import build_run_layout
from benchmark_control_arcade.run_models import RunArtifact, RunSpec, RunStatus, RunType

logger = logging.getLogger(__name__)

_RUN_ID_RE = re.compile(r"^run-(\d{14})-")

try:
    from benchmark_control_arcade import aioa_runner, geo_compare_runner, geo_runner
except ModuleNotFoundError:
    async def _missing(*_args, **_kwargs):
        raise ModuleNotFoundError("Runner dependencies are not available in this environment.")

    aioa_runner = SimpleNamespace(run_aioa_benchmark=_missing, _is_placeholder=True)  # type: ignore[assignment]
    geo_compare_runner = SimpleNamespace(  # type: ignore[assignment]
        run_geo_compare_benchmark=_missing, _is_placeholder=True
    )
    geo_runner = SimpleNamespace(run_geo_benchmark=_missing, _is_placeholder=True)  # type: ignore[assignment]


def _parse_created_at_from_run_id(run_id: str) -> datetime | None:
    """Parse the creation datetime encoded in a run_id.

    Expected format: ``run-YYYYMMDDHHMMSS-<hex>``

    Returns None when the run_id doesn't match the expected format so callers
    can fall back to ``datetime.now()``.
    """
    m = _RUN_ID_RE.match(run_id)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None


async def run_workflow(run_id: str, run_type: str, run_spec_json: str) -> None:
    """Run the full benchmark lifecycle for a single run.

    Parameters
    ----------
    run_id:
        The unique identifier for this run. Must already exist on the data
        branch (created by the control plane before dispatching the workflow).
    run_type:
        Either "aioa" or "geo".
    run_spec_json:
        JSON string that can be parsed into a RunSpec.
    """
    settings = Settings()  # type: ignore[call-arg]
    client = GitHubClient(settings)

    # ------------------------------------------------------------------
    # Fetch the existing RunRecord so we have created_at for layout paths.
    # ------------------------------------------------------------------
    # The run_id encodes the creation timestamp (run-YYYYMMDDHHMMSS-<hex>),
    # so parse it directly rather than using datetime.now().  This prevents
    # a date mismatch when the workflow starts just after UTC midnight — the
    # data-branch path was written under the *queued* date, not the current
    # date, so we must look in the same directory.
    fallback_now = _parse_created_at_from_run_id(run_id) or datetime.now(tz=UTC)

    try:
        record = await client.get_run_record(run_id, fallback_now)
        created_at = record.created_at
    except Exception:
        # Can't fetch: use fallback_now. The update_run_record calls below
        # will also use fallback_now — they may fail too, but we try anyway.
        logger.warning(
            "Could not fetch initial run record for %s; using current time as created_at",
            run_id,
            exc_info=True,
        )
        created_at = fallback_now
        record = None  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Transition to "running"
    # ------------------------------------------------------------------
    try:
        if record is not None:
            running_record = record.model_copy(
                update={
                    "status": RunStatus.running,
                    "updated_at": datetime.now(tz=UTC),
                }
            )
            await client.update_run_record(running_record)
        else:
            # No pre-existing record (workflow was dispatched directly, not via
            # StartRun). Create the record from scratch so subsequent
            # update_run_record calls have a file to GET-then-PUT against.
            from benchmark_control_arcade.run_models import RunRecord

            spec_for_record = RunSpec.model_validate_json(run_spec_json)
            running_record = RunRecord(
                run_id=run_id,
                run_type=RunType(run_type),
                status=RunStatus.running,
                created_at=created_at,
                updated_at=datetime.now(tz=UTC),
                repo=f"{settings.github_owner}/{settings.github_repo}",
                workflow_name=settings.github_run_workflow,
                data_branch=settings.github_data_branch,
                spec=spec_for_record,
            )
            await client.create_initial_run_record(running_record)
    except Exception:
        logger.error("Failed to update run record to 'running' for %s", run_id, exc_info=True)
        # Do not return here — continue and try to run anyway, then fail.

    # ------------------------------------------------------------------
    # Execute the benchmark
    # ------------------------------------------------------------------
    run_start = datetime.now(tz=UTC)
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_dir = Path(tmp_dir)
        try:
            spec = RunSpec.model_validate_json(run_spec_json)
            rtype = RunType(run_type)
            global aioa_runner, geo_compare_runner, geo_runner
            if (
                rtype == RunType.aioa
                and getattr(aioa_runner, "_is_placeholder", False)
                and getattr(aioa_runner, "run_aioa_benchmark", None) is _missing
            ):
                from benchmark_control_arcade import aioa_runner as _aioa_runner

                aioa_runner = _aioa_runner
            if (
                rtype == RunType.geo
                and getattr(geo_runner, "_is_placeholder", False)
                and getattr(geo_runner, "run_geo_benchmark", None) is _missing
            ):
                from benchmark_control_arcade import geo_runner as _geo_runner

                geo_runner = _geo_runner
            if (
                rtype == RunType.geo_compare
                and getattr(geo_compare_runner, "_is_placeholder", False)
                and getattr(geo_compare_runner, "run_geo_compare_benchmark", None) is _missing
            ):
                from benchmark_control_arcade import geo_compare_runner as _geo_compare_runner

                geo_compare_runner = _geo_compare_runner

            if rtype == RunType.aioa:
                result = await aioa_runner.run_aioa_benchmark(spec, run_id, output_dir)
            elif rtype == RunType.geo:
                result = await geo_runner.run_geo_benchmark(spec, run_id, output_dir)
            elif rtype == RunType.geo_compare:
                result = await geo_compare_runner.run_geo_compare_benchmark(
                    spec, run_id, output_dir
                )
            else:
                raise ValueError(f"Unknown run_type: {run_type!r}")

            # ------------------------------------------------------------------
            # Upload artifacts to the data branch, then transition to "completed"
            # ------------------------------------------------------------------
            layout = build_run_layout(run_id, created_at)
            artifacts: list[RunArtifact] = []
            for artifact_rel_path in result.get("artifacts", []):
                local_path = output_dir / artifact_rel_path
                if not local_path.is_file():
                    logger.warning("Artifact not found on disk, skipping: %s", local_path)
                    continue
                artifact_name = local_path.name
                github_path = str(layout.artifacts_dir / artifact_name)
                content_b64 = base64.b64encode(local_path.read_bytes()).decode()
                try:
                    await client._put_file(
                        github_path,
                        content_b64,
                        f"chore: upload artifact {artifact_name} for run {run_id}",
                    )
                    artifacts.append(RunArtifact(name=artifact_name, path=github_path))
                except Exception:
                    logger.warning(
                        "Failed to upload artifact %s for run %s",
                        artifact_name,
                        run_id,
                        exc_info=True,
                    )

            summary = result.get("summary") or {k: v for k, v in result.items() if k != "run_id"}
            elapsed = (datetime.now(tz=UTC) - run_start).total_seconds()

            if running_record is not None:
                completed_record = running_record.model_copy(
                    update={
                        "status": RunStatus.completed,
                        "updated_at": datetime.now(tz=UTC),
                        "artifacts": artifacts,
                        "summary": summary,
                        "error": None,
                        "elapsed_seconds": elapsed,
                    }
                )
            else:
                from benchmark_control_arcade.run_models import RunRecord

                completed_record = RunRecord(
                    run_id=run_id,
                    run_type=rtype,
                    status=RunStatus.completed,
                    created_at=created_at,
                    updated_at=datetime.now(tz=UTC),
                    repo=f"{settings.github_owner}/{settings.github_repo}",
                    workflow_name=settings.github_run_workflow,
                    data_branch=settings.github_data_branch,
                    spec=spec,
                    artifacts=artifacts,
                    summary=summary,
                    elapsed_seconds=elapsed,
                )
            await client.update_run_record(completed_record)
            logger.info("Run %s completed successfully", run_id)

        except Exception as exc:
            logger.error("Run %s failed: %s", run_id, exc, exc_info=True)

            # ------------------------------------------------------------------
            # Transition to "failed" — must not re-raise
            # ------------------------------------------------------------------
            try:
                if running_record is not None:
                    failed_record = running_record.model_copy(
                        update={
                            "status": RunStatus.failed,
                            "updated_at": datetime.now(tz=UTC),
                            "error": str(exc),
                        }
                    )
                else:
                    from benchmark_control_arcade.run_models import RunRecord

                    failed_record = RunRecord(
                        run_id=run_id,
                        run_type=RunType(run_type)
                        if run_type in RunType._value2member_map_
                        else RunType.aioa,
                        status=RunStatus.failed,
                        created_at=created_at,
                        updated_at=datetime.now(tz=UTC),
                        repo=f"{settings.github_owner}/{settings.github_repo}",
                        workflow_name=settings.github_run_workflow,
                        data_branch=settings.github_data_branch,
                        spec=RunSpec(
                            run_type=RunType(run_type)
                            if run_type in RunType._value2member_map_
                            else RunType.aioa,
                            target="unknown",
                        ),
                        error=str(exc),
                    )
                await client.update_run_record(failed_record)
            except Exception:
                logger.error(
                    "Failed to update run record to 'failed' for %s", run_id, exc_info=True
                )


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(
            "Usage: python -m benchmark_control_arcade.workflow_entrypoint"
            " <run_id> <run_type> <run_spec_json>",
            file=sys.stderr,
        )
        sys.exit(1)

    _, run_id_arg, run_type_arg, run_spec_json_arg = sys.argv
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_workflow(run_id_arg, run_type_arg, run_spec_json_arg))
