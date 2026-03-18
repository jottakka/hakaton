"""Tests for storage backends — JsonFileStore and SqliteStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.stores.json_store import JsonFileStore
from src.stores.sqlite_store import SqliteStore


# ---------------------------------------------------------------------------
# Shared test suite — runs against both backends
# ---------------------------------------------------------------------------

async def _run_store_tests(store) -> None:
    """Exercise all store methods. Called by both backend test functions."""
    await store.init()

    # create_run
    run_id = await store.create_run(
        prompt_set_id="v1",
        term_set_id="v1",
        competitor_config={"target": "Arcade", "competitors": ["Composio"]},
    )
    assert run_id is not None

    # get_run
    run = await store.get_run(run_id)
    assert run is not None
    assert run["prompt_set_id"] == "v1"
    assert run["term_set_id"] == "v1"

    # get nonexistent run
    missing = await store.get_run("nonexistent-id")
    assert missing is None

    # save model results
    await store.save_model_result(
        run_id=run_id,
        prompt_id="p001",
        prompt_text="Test prompt",
        model="openai",
        raw_response="Arcade is great.",
        latency_ms=500,
    )
    await store.save_model_result(
        run_id=run_id,
        prompt_id="p001",
        prompt_text="Test prompt",
        model="anthropic",
        raw_response="Arcade is solid.",
        latency_ms=600,
    )

    model_results = await store.get_model_results_for_run(run_id)
    assert len(model_results) == 2
    assert {r["model"] for r in model_results} == {"openai", "anthropic"}

    # save search results
    await store.save_search_result(
        run_id=run_id,
        term_id="s001",
        query="best MCP runtime",
        engine="google",
        results=[{"position": 1, "title": "Arcade", "url": "https://arcade.dev", "snippet": "..."}],
    )

    search_results = await store.get_search_results_for_run(run_id)
    assert len(search_results) == 1
    assert search_results[0]["engine"] == "google"

    # save search result with status/error fields
    await store.save_search_result(
        run_id=run_id,
        term_id="s002",
        query="mcp auth",
        engine="google",
        results=[],
        status="failed",
        error="boom",
    )
    search_results2 = await store.get_search_results_for_run(run_id)
    assert len(search_results2) == 2
    failed = [r for r in search_results2 if r.get("status") == "failed" or r.get("term_id") == "s002"]
    assert len(failed) == 1
    assert failed[0]["status"] == "failed"
    assert failed[0]["error"] == "boom"

    # save analysis result
    result_id = await store.save_analysis_result(
        run_id=run_id,
        analysis={"summary": {"arcade_avg_aio_score": 75}},
    )
    assert result_id is not None


# ---------------------------------------------------------------------------
# JsonFileStore tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_json_store(tmp_path: Path):
    store = JsonFileStore(workspace=tmp_path)
    await _run_store_tests(store)


@pytest.mark.asyncio
async def test_json_store_creates_run_dir(tmp_path: Path):
    store = JsonFileStore(workspace=tmp_path)
    await store.init()
    run_id = await store.create_run("v1", "v1", {"target": "Arcade", "competitors": []})
    run_dir = tmp_path / "runs" / run_id
    assert run_dir.exists()
    assert (run_dir / "run.json").exists()


@pytest.mark.asyncio
async def test_json_store_model_results_are_separate_files(tmp_path: Path):
    store = JsonFileStore(workspace=tmp_path)
    await store.init()
    run_id = await store.create_run("v1", "v1", {"target": "Arcade", "competitors": []})

    id1 = await store.save_model_result(run_id, "p001", "prompt", "openai", "response A")
    id2 = await store.save_model_result(run_id, "p001", "prompt", "gemini", "response B")

    results_dir = tmp_path / "runs" / run_id / "model_results"
    files = list(results_dir.glob("*.json"))
    assert len(files) == 2
    file_names = {f.stem for f in files}
    assert id1 in file_names
    assert id2 in file_names


# ---------------------------------------------------------------------------
# SqliteStore tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sqlite_store(tmp_path: Path):
    store = SqliteStore(db_path=tmp_path / "test.db")
    await _run_store_tests(store)


@pytest.mark.asyncio
async def test_sqlite_store_creates_db_file(tmp_path: Path):
    db_path = tmp_path / "test.db"
    store = SqliteStore(db_path=db_path)
    await store.init()
    assert db_path.exists()


# ---------------------------------------------------------------------------
# External run_id tests — both backends
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_json_store_accepts_external_run_id(tmp_path: Path):
    """When a run_id is provided, json_store must use it verbatim."""
    store = JsonFileStore(workspace=tmp_path)
    await store.init()
    ext_id = "bench-run-abc-123"
    returned_id = await store.create_run(
        prompt_set_id="v1",
        term_set_id="v1",
        competitor_config={"target": "Arcade", "competitors": []},
        run_id=ext_id,
    )
    assert returned_id == ext_id
    run_dir = tmp_path / "runs" / ext_id
    assert run_dir.exists()
    run = await store.get_run(ext_id)
    assert run is not None
    assert run["id"] == ext_id


@pytest.mark.asyncio
async def test_json_store_auto_generates_id_when_none(tmp_path: Path):
    """When run_id is omitted, json_store must still auto-generate a UUID."""
    import uuid
    store = JsonFileStore(workspace=tmp_path)
    await store.init()
    returned_id = await store.create_run(
        prompt_set_id="v1",
        term_set_id="v1",
        competitor_config={"target": "Arcade", "competitors": []},
    )
    # Should be a valid UUID
    uuid.UUID(returned_id)  # raises if not a valid UUID
    run = await store.get_run(returned_id)
    assert run is not None


@pytest.mark.asyncio
async def test_sqlite_store_accepts_external_run_id(tmp_path: Path):
    """When a run_id is provided, sqlite_store must use it verbatim."""
    store = SqliteStore(db_path=tmp_path / "test.db")
    await store.init()
    ext_id = "bench-run-sqlite-456"
    returned_id = await store.create_run(
        prompt_set_id="v1",
        term_set_id="v1",
        competitor_config={"target": "Arcade", "competitors": []},
        run_id=ext_id,
    )
    assert returned_id == ext_id
    run = await store.get_run(ext_id)
    assert run is not None
    assert run["id"] == ext_id


@pytest.mark.asyncio
async def test_sqlite_store_auto_generates_id_when_none(tmp_path: Path):
    """When run_id is omitted, sqlite_store must still auto-generate a UUID."""
    import uuid
    store = SqliteStore(db_path=tmp_path / "test.db")
    await store.init()
    returned_id = await store.create_run(
        prompt_set_id="v1",
        term_set_id="v1",
        competitor_config={"target": "Arcade", "competitors": []},
    )
    uuid.UUID(returned_id)
    run = await store.get_run(returned_id)
    assert run is not None
