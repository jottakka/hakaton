"""JSON File Store — MVP storage backend.

Writes all pipeline data as JSON files under a configurable workspace directory.

Layout:
    {workspace}/
      runs/
        {run_id}/
          run.json                          # run metadata
          model_results/{result_id}.json    # one file per LLM response
          search_results/{result_id}.json   # one file per search engine result set
          analysis.json                     # orchestrator output

Each file is written once and never mutated, making concurrent writes safe
and the output trivially inspectable with any JSON viewer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.store import StoreProtocol, new_id, now_iso  # noqa: F401 — re-export for convenience


class JsonFileStore:
    """Stores all pipeline data as JSON files on disk."""

    def __init__(self, workspace: str | Path = "data") -> None:
        self.workspace = Path(workspace)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_dir(self, run_id: str) -> Path:
        return self.workspace / "runs" / run_id

    def _write(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _read(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    # StoreProtocol implementation
    # ------------------------------------------------------------------

    async def init(self) -> None:
        """Create the workspace directory if needed."""
        (self.workspace / "runs").mkdir(parents=True, exist_ok=True)

    async def create_run(
        self,
        prompt_set_id: str,
        term_set_id: str,
        competitor_config: dict[str, Any],
        run_id: str | None = None,
    ) -> str:
        run_id = run_id if run_id is not None else new_id()
        run_data = {
            "id": run_id,
            "prompt_set_id": prompt_set_id,
            "term_set_id": term_set_id,
            "competitor_config": competitor_config,
            "created_at": now_iso(),
        }
        self._write(self._run_dir(run_id) / "run.json", run_data)
        return run_id

    async def save_model_result(
        self,
        run_id: str,
        prompt_id: str,
        prompt_text: str,
        model: str,
        raw_response: str,
        latency_ms: int | None = None,
    ) -> str:
        result_id = new_id()
        data = {
            "id": result_id,
            "run_id": run_id,
            "prompt_id": prompt_id,
            "prompt_text": prompt_text,
            "model": model,
            "raw_response": raw_response,
            "latency_ms": latency_ms,
            "created_at": now_iso(),
        }
        self._write(self._run_dir(run_id) / "model_results" / f"{result_id}.json", data)
        return result_id

    async def save_search_result(
        self,
        run_id: str,
        term_id: str,
        query: str,
        engine: str,
        results: list[dict[str, Any]],
        status: str = "ok",
        error: str | None = None,
    ) -> str:
        result_id = new_id()
        data = {
            "id": result_id,
            "run_id": run_id,
            "term_id": term_id,
            "query": query,
            "engine": engine,
            "results_json": results,
            "status": status,
            "error": error,
            "created_at": now_iso(),
        }
        self._write(self._run_dir(run_id) / "search_results" / f"{result_id}.json", data)
        return result_id

    async def save_analysis_result(
        self,
        run_id: str,
        analysis: dict[str, Any],
    ) -> str:
        result_id = new_id()
        data = {
            "id": result_id,
            "run_id": run_id,
            "analysis_json": analysis,
            "created_at": now_iso(),
        }
        self._write(self._run_dir(run_id) / "analysis.json", data)
        return result_id

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self._read(self._run_dir(run_id) / "run.json")

    async def get_model_results_for_run(self, run_id: str) -> list[dict[str, Any]]:
        results_dir = self._run_dir(run_id) / "model_results"
        if not results_dir.exists():
            return []
        results = [
            json.loads(f.read_text(encoding="utf-8")) for f in sorted(results_dir.glob("*.json"))
        ]
        return results

    async def get_search_results_for_run(self, run_id: str) -> list[dict[str, Any]]:
        results_dir = self._run_dir(run_id) / "search_results"
        if not results_dir.exists():
            return []
        results = [
            json.loads(f.read_text(encoding="utf-8")) for f in sorted(results_dir.glob("*.json"))
        ]
        return results
