"""Store Protocol — defines the interface all storage backends must implement.

To swap backends, implement this Protocol and pass the new store to run_full_pipeline().

Current implementations:
  - JsonFileStore  (src/stores/json_store.py)  — MVP default, writes JSON files to disk
  - SqliteStore    (src/stores/sqlite_store.py) — Phase 2, SQLite database
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable


def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


@runtime_checkable
class StoreProtocol(Protocol):
    """Interface all storage backends must satisfy."""

    async def init(self) -> None:
        """Perform any one-time setup (create tables, directories, etc.)."""
        ...

    async def create_run(
        self,
        prompt_set_id: str,
        term_set_id: str,
        competitor_config: dict[str, Any],
        run_id: str | None = None,
    ) -> str:
        """Create a new pipeline run record and return its id.

        If *run_id* is provided it is used verbatim (external / controlled run).
        If omitted a new UUID is auto-generated (default backward-compatible behaviour).
        """
        ...

    async def save_model_result(
        self,
        run_id: str,
        prompt_id: str,
        prompt_text: str,
        model: str,
        raw_response: str,
        latency_ms: int | None = None,
    ) -> str:
        """Persist a single LLM response and return its id."""
        ...

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
        """Persist a single search engine result set and return its id."""
        ...

    async def save_analysis_result(
        self,
        run_id: str,
        analysis: dict[str, Any],
    ) -> str:
        """Persist the orchestrator analysis output and return its id."""
        ...

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Fetch run metadata by id. Returns None if not found."""
        ...

    async def get_model_results_for_run(self, run_id: str) -> list[dict[str, Any]]:
        """Fetch all model results for a given run."""
        ...

    async def get_search_results_for_run(self, run_id: str) -> list[dict[str, Any]]:
        """Fetch all search results for a given run."""
        ...
