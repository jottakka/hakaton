"""Tests for GitHubClient — uses respx at the HTTP boundary.

All tests use real Pydantic models and real JSON. No unittest.mock.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime

import pytest
import respx
from httpx import Response

from benchmark_control_arcade.config import Settings
from benchmark_control_arcade.run_models import RunRecord, RunSpec, RunStatus, RunType

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASE_URL = "https://api.github.com"


def make_settings() -> Settings:
    return Settings(
        github_owner="acme",
        github_repo="benchmarks",
        github_token="ghp_fake_token",
        github_data_branch="benchmark-data",
        github_run_workflow="run-benchmark.yml",
    )


def make_record(
    run_id: str = "run-123",
    status: RunStatus = RunStatus.queued,
) -> RunRecord:
    now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=UTC)
    return RunRecord(
        run_id=run_id,
        run_type=RunType.aioa,
        status=status,
        created_at=now,
        updated_at=now,
        repo="acme/benchmarks",
        workflow_name="run-benchmark.yml",
        data_branch="benchmark-data",
        spec=RunSpec(run_type=RunType.aioa, target="gpt-4o"),
    )


def _b64(record: RunRecord) -> str:
    return base64.b64encode(record.model_dump_json().encode()).decode()


# ---------------------------------------------------------------------------
# 1. create_initial_run_record writes queued status
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_create_initial_run_record_writes_queued_status() -> None:
    from benchmark_control_arcade.github_client import GitHubClient

    settings = make_settings()
    record = make_record(status=RunStatus.queued)

    # Expected path: runs/2026/03/18/run-123/run.json
    path = "runs/2026/03/18/run-123/run.json"
    url = f"{BASE_URL}/repos/acme/benchmarks/contents/{path}"

    put_route = respx.put(url).mock(return_value=Response(201, json={"content": {"sha": "abc123"}}))

    client = GitHubClient(settings)
    await client.create_initial_run_record(record)

    assert put_route.called
    request = put_route.calls[0].request
    body = json.loads(request.content)
    content_decoded = base64.b64decode(body["content"]).decode()
    payload = json.loads(content_decoded)
    assert payload["status"] == "queued"
    assert payload["run_id"] == "run-123"
    assert body["branch"] == "benchmark-data"


# ---------------------------------------------------------------------------
# 2. update_run_record writes updated status
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_update_run_record_writes_updated_status() -> None:
    from benchmark_control_arcade.github_client import GitHubClient

    settings = make_settings()
    record = make_record(status=RunStatus.completed)

    path = "runs/2026/03/18/run-123/run.json"
    get_url = f"{BASE_URL}/repos/acme/benchmarks/contents/{path}"
    put_url = f"{BASE_URL}/repos/acme/benchmarks/contents/{path}"

    # GET must return a sha for the update PUT
    respx.get(get_url).mock(
        return_value=Response(
            200,
            json={
                "sha": "existing-sha",
                "content": _b64(make_record()),
                "encoding": "base64",
            },
        )
    )
    put_route = respx.put(put_url).mock(
        return_value=Response(200, json={"content": {"sha": "new-sha"}})
    )

    client = GitHubClient(settings)
    await client.update_run_record(record)

    assert put_route.called
    body = json.loads(put_route.calls[0].request.content)
    content_decoded = base64.b64decode(body["content"]).decode()
    payload = json.loads(content_decoded)
    assert payload["status"] == "completed"
    assert body["sha"] == "existing-sha"


# ---------------------------------------------------------------------------
# 3. dispatch_workflow uses run_id input
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_dispatch_workflow_uses_run_id_input() -> None:
    from benchmark_control_arcade.github_client import GitHubClient

    settings = make_settings()

    dispatch_url = (
        f"{BASE_URL}/repos/acme/benchmarks/actions/workflows/run-benchmark.yml/dispatches"
    )
    dispatch_route = respx.post(dispatch_url).mock(return_value=Response(204))

    client = GitHubClient(settings)
    await client.dispatch_workflow(
        run_id="run-123",
        run_type="aioa",
        run_spec_json='{"run_type": "aioa", "target": "gpt-4o", "options": {}}',
    )

    assert dispatch_route.called
    body = json.loads(dispatch_route.calls[0].request.content)
    assert body["ref"] == "main"
    assert body["inputs"]["run_id"] == "run-123"
    assert body["inputs"]["run_type"] == "aioa"


# ---------------------------------------------------------------------------
# 4. get_run_record parses response
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_get_run_record_parses_response() -> None:
    from benchmark_control_arcade.github_client import GitHubClient

    settings = make_settings()
    original = make_record(run_id="run-123")

    path = "runs/2026/03/18/run-123/run.json"
    get_url = f"{BASE_URL}/repos/acme/benchmarks/contents/{path}"

    respx.get(get_url).mock(
        return_value=Response(
            200,
            json={
                "sha": "abc123",
                "content": _b64(original),
                "encoding": "base64",
            },
        )
    )

    client = GitHubClient(settings)
    result = await client.get_run_record(
        run_id="run-123",
        created_at=datetime(2026, 3, 18, 12, 0, 0, tzinfo=UTC),
    )

    assert isinstance(result, RunRecord)
    assert result.run_id == "run-123"
    assert result.status == RunStatus.queued
    assert result.run_type == RunType.aioa


# ---------------------------------------------------------------------------
# 5. list_run_records returns newest first
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_list_run_records_returns_newest_first() -> None:
    from benchmark_control_arcade.github_client import GitHubClient

    settings = make_settings()

    older_dt = datetime(2026, 3, 17, 10, 0, 0, tzinfo=UTC)
    newer_dt = datetime(2026, 3, 18, 12, 0, 0, tzinfo=UTC)

    older_record = RunRecord(
        run_id="run-older",
        run_type=RunType.geo,
        status=RunStatus.completed,
        created_at=older_dt,
        updated_at=older_dt,
        repo="acme/benchmarks",
        workflow_name="run-benchmark.yml",
        data_branch="benchmark-data",
        spec=RunSpec(run_type=RunType.geo, target="bing"),
    )
    newer_record = RunRecord(
        run_id="run-newer",
        run_type=RunType.aioa,
        status=RunStatus.running,
        created_at=newer_dt,
        updated_at=newer_dt,
        repo="acme/benchmarks",
        workflow_name="run-benchmark.yml",
        data_branch="benchmark-data",
        spec=RunSpec(run_type=RunType.aioa, target="gpt-4o"),
    )

    tree_url = f"{BASE_URL}/repos/acme/benchmarks/git/trees/benchmark-data"
    respx.get(tree_url, params={"recursive": "1"}).mock(
        return_value=Response(
            200,
            json={
                "tree": [
                    {
                        "path": "runs/2026/03/17/run-older/run.json",
                        "type": "blob",
                        "sha": "sha-older",
                    },
                    {
                        "path": "runs/2026/03/18/run-newer/run.json",
                        "type": "blob",
                        "sha": "sha-newer",
                    },
                ]
            },
        )
    )

    older_content_url = (
        f"{BASE_URL}/repos/acme/benchmarks/contents/runs/2026/03/17/run-older/run.json"
    )
    newer_content_url = (
        f"{BASE_URL}/repos/acme/benchmarks/contents/runs/2026/03/18/run-newer/run.json"
    )

    respx.get(older_content_url).mock(
        return_value=Response(
            200,
            json={
                "sha": "sha-older",
                "content": base64.b64encode(older_record.model_dump_json().encode()).decode(),
                "encoding": "base64",
            },
        )
    )
    respx.get(newer_content_url).mock(
        return_value=Response(
            200,
            json={
                "sha": "sha-newer",
                "content": base64.b64encode(newer_record.model_dump_json().encode()).decode(),
                "encoding": "base64",
            },
        )
    )

    client = GitHubClient(settings)
    records = await client.list_run_records(limit=20)

    assert len(records) == 2
    # Newest first
    assert records[0].run_id == "run-newer"
    assert records[1].run_id == "run-older"


# ---------------------------------------------------------------------------
# 6. create_run_record is called BEFORE dispatch_workflow
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_create_run_record_before_dispatch() -> None:
    """Assert that the run record is written to the data branch before
    the workflow is dispatched. We track call order via a shared list."""

    from benchmark_control_arcade.github_client import GitHubClient

    settings = make_settings()
    record = make_record()

    call_order: list[str] = []

    path = "runs/2026/03/18/run-123/run.json"
    put_url = f"{BASE_URL}/repos/acme/benchmarks/contents/{path}"
    dispatch_url = (
        f"{BASE_URL}/repos/acme/benchmarks/actions/workflows/run-benchmark.yml/dispatches"
    )

    def put_side_effect(request):  # noqa: ANN001
        call_order.append("create")
        return Response(201, json={"content": {"sha": "abc"}})

    def dispatch_side_effect(request):  # noqa: ANN001
        call_order.append("dispatch")
        return Response(204)

    respx.put(put_url).mock(side_effect=put_side_effect)
    respx.post(dispatch_url).mock(side_effect=dispatch_side_effect)

    client = GitHubClient(settings)
    spec_json = record.spec.model_dump_json()
    await client.create_initial_run_record(record)
    await client.dispatch_workflow(
        run_id=record.run_id,
        run_type=record.run_type.value,
        run_spec_json=spec_json,
    )

    assert call_order == ["create", "dispatch"], (
        f"Expected create before dispatch but got: {call_order}"
    )
