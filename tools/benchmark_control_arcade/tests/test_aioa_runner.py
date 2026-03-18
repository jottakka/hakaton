"""Tests for aioa_runner — bridges benchmark_control_arcade with the AIOA pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark_control_arcade.aioa_runner import run_aioa_benchmark
from benchmark_control_arcade.run_models import RunSpec, RunType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_spec(target: str = "Arcade", **options) -> RunSpec:
    return RunSpec(run_type=RunType.aioa, target=target, options=options)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_aioa_benchmark_returns_run_id(tmp_path: Path, monkeypatch):
    """The returned dict must include the exact run_id that was passed in."""
    run_id = "bench-test-run-001"
    spec = _make_spec()

    async def fake_pipeline(prompt_set, term_set, competitors, output_dir, store, run_id):
        return {
            "run_mode": "seo_only",
            "summary": {"arcade_avg_aio_score": None, "arcade_avg_seo_score": 72},
            "gap_recommendations": {},
        }

    monkeypatch.setattr(
        "benchmark_control_arcade.aioa_runner.run_full_pipeline",
        fake_pipeline,
    )

    result = await run_aioa_benchmark(spec=spec, run_id=run_id, output_dir=tmp_path)
    assert result["run_id"] == run_id


@pytest.mark.asyncio
async def test_run_aioa_benchmark_writes_output_under_run_id_dir(tmp_path: Path, monkeypatch):
    """Artifacts must be written under output_dir / run_id /."""
    run_id = "bench-test-run-002"
    spec = _make_spec()

    async def fake_pipeline(prompt_set, term_set, competitors, output_dir, store, run_id):
        # Simulate pipeline writing a run.json via the real JsonFileStore
        run_dir = Path(output_dir) / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run.json").write_text(json.dumps({"id": run_id}))
        return {"run_mode": "seo_only", "summary": {}, "gap_recommendations": {}}

    monkeypatch.setattr(
        "benchmark_control_arcade.aioa_runner.run_full_pipeline",
        fake_pipeline,
    )

    result = await run_aioa_benchmark(spec=spec, run_id=run_id, output_dir=tmp_path)

    # output_dir / run_id should exist
    run_output_dir = tmp_path / run_id
    assert run_output_dir.exists(), f"Expected output dir at {run_output_dir}"


@pytest.mark.asyncio
async def test_run_aioa_benchmark_returns_artifacts_list(tmp_path: Path, monkeypatch):
    """The returned dict must include an 'artifacts' list."""
    run_id = "bench-test-run-003"
    spec = _make_spec()

    async def fake_pipeline(prompt_set, term_set, competitors, output_dir, store, run_id):
        return {"run_mode": "seo_only", "summary": {}, "gap_recommendations": {}}

    monkeypatch.setattr(
        "benchmark_control_arcade.aioa_runner.run_full_pipeline",
        fake_pipeline,
    )

    result = await run_aioa_benchmark(spec=spec, run_id=run_id, output_dir=tmp_path)
    assert "artifacts" in result
    assert isinstance(result["artifacts"], list)


@pytest.mark.asyncio
async def test_run_aioa_benchmark_returns_summary(tmp_path: Path, monkeypatch):
    """The returned dict must include a 'summary' dict with key metrics."""
    run_id = "bench-test-run-004"
    spec = _make_spec(target="Arcade")

    expected_summary = {"arcade_avg_aio_score": None, "arcade_avg_seo_score": 85}

    async def fake_pipeline(prompt_set, term_set, competitors, output_dir, store, run_id):
        return {
            "run_mode": "seo_only",
            "summary": expected_summary,
            "gap_recommendations": {},
        }

    monkeypatch.setattr(
        "benchmark_control_arcade.aioa_runner.run_full_pipeline",
        fake_pipeline,
    )

    result = await run_aioa_benchmark(spec=spec, run_id=run_id, output_dir=tmp_path)
    assert "summary" in result
    assert result["summary"] == expected_summary


@pytest.mark.asyncio
async def test_run_aioa_benchmark_uses_real_json_store(tmp_path: Path, monkeypatch):
    """The runner must wire up a real JsonFileStore so files actually land on disk."""
    run_id = "bench-test-run-005"
    spec = _make_spec()
    captured: dict = {}

    async def fake_pipeline(prompt_set, term_set, competitors, output_dir, store, run_id):
        captured["store_type"] = type(store).__name__
        captured["run_id"] = run_id
        # Use the real store so run.json is written
        await store.init()
        await store.create_run(
            prompt_set_id=prompt_set.prompt_set_id,
            term_set_id=term_set.term_set_id,
            competitor_config=competitors.model_dump(),
            run_id=run_id,
        )
        return {"run_mode": "seo_only", "summary": {}, "gap_recommendations": {}}

    monkeypatch.setattr(
        "benchmark_control_arcade.aioa_runner.run_full_pipeline",
        fake_pipeline,
    )

    await run_aioa_benchmark(spec=spec, run_id=run_id, output_dir=tmp_path)

    assert captured["store_type"] == "JsonFileStore"
    assert captured["run_id"] == run_id

    # run.json must have been created in the per-run output subdir
    run_json = tmp_path / run_id / "runs" / run_id / "run.json"
    assert run_json.exists(), f"Expected run.json at {run_json}"


@pytest.mark.asyncio
async def test_run_aioa_benchmark_respects_spec_target(tmp_path: Path, monkeypatch):
    """The CompetitorConfig must use the target from the RunSpec."""
    run_id = "bench-test-run-006"
    spec = _make_spec(target="MyCompany")
    captured: dict = {}

    async def fake_pipeline(prompt_set, term_set, competitors, output_dir, store, run_id):
        captured["target"] = competitors.target
        return {"run_mode": "seo_only", "summary": {}, "gap_recommendations": {}}

    monkeypatch.setattr(
        "benchmark_control_arcade.aioa_runner.run_full_pipeline",
        fake_pipeline,
    )

    await run_aioa_benchmark(spec=spec, run_id=run_id, output_dir=tmp_path)
    assert captured["target"] == "MyCompany"
