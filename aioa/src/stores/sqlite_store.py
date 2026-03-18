"""SQLite Store — Phase 2 storage backend.

Drop-in replacement for JsonFileStore. Swap it in by passing
SqliteStore() to run_full_pipeline() when ready to migrate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiosqlite

from src.store import new_id, now_iso

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    prompt_set_id TEXT NOT NULL,
    term_set_id TEXT NOT NULL,
    competitor_config TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_results (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    prompt_id TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    model TEXT NOT NULL,
    raw_response TEXT NOT NULL,
    latency_ms INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS search_results (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    term_id TEXT NOT NULL,
    query TEXT NOT NULL,
    engine TEXT NOT NULL,
    results_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ok',
    error TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analysis_results (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    analysis_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class SqliteStore:
    """Stores all pipeline data in a SQLite database."""

    def __init__(self, db_path: str | Path = "data/pipeline.db") -> None:
        self.db_path = Path(db_path)

    async def _connect(self) -> aiosqlite.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        db = await aiosqlite.connect(str(self.db_path))
        db.row_factory = aiosqlite.Row
        return db

    async def init(self) -> None:
        db = await self._connect()
        try:
            await db.executescript(_SCHEMA_SQL)
            await db.commit()
        finally:
            await db.close()

    async def create_run(
        self,
        prompt_set_id: str,
        term_set_id: str,
        competitor_config: dict[str, Any],
        run_id: str | None = None,
    ) -> str:
        run_id = run_id if run_id is not None else new_id()
        db = await self._connect()
        try:
            await db.execute(
                "INSERT INTO runs (id, prompt_set_id, term_set_id, competitor_config, created_at) VALUES (?, ?, ?, ?, ?)",
                (run_id, prompt_set_id, term_set_id, json.dumps(competitor_config), now_iso()),
            )
            await db.commit()
        finally:
            await db.close()
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
        db = await self._connect()
        try:
            await db.execute(
                "INSERT INTO model_results (id, run_id, prompt_id, prompt_text, model, raw_response, latency_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    result_id,
                    run_id,
                    prompt_id,
                    prompt_text,
                    model,
                    raw_response,
                    latency_ms,
                    now_iso(),
                ),
            )
            await db.commit()
        finally:
            await db.close()
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
        db = await self._connect()
        try:
            await db.execute(
                "INSERT INTO search_results (id, run_id, term_id, query, engine, results_json, status, error, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    result_id,
                    run_id,
                    term_id,
                    query,
                    engine,
                    json.dumps(results),
                    status,
                    error,
                    now_iso(),
                ),
            )
            await db.commit()
        finally:
            await db.close()
        return result_id

    async def save_analysis_result(
        self,
        run_id: str,
        analysis: dict[str, Any],
    ) -> str:
        result_id = new_id()
        db = await self._connect()
        try:
            await db.execute(
                "INSERT INTO analysis_results (id, run_id, analysis_json, created_at) VALUES (?, ?, ?, ?)",
                (result_id, run_id, json.dumps(analysis), now_iso()),
            )
            await db.commit()
        finally:
            await db.close()
        return result_id

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        db = await self._connect()
        try:
            cursor = await db.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
        finally:
            await db.close()

    async def get_model_results_for_run(self, run_id: str) -> list[dict[str, Any]]:
        db = await self._connect()
        try:
            cursor = await db.execute(
                "SELECT * FROM model_results WHERE run_id = ? ORDER BY created_at", (run_id,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            await db.close()

    async def get_search_results_for_run(self, run_id: str) -> list[dict[str, Any]]:
        db = await self._connect()
        try:
            cursor = await db.execute(
                "SELECT * FROM search_results WHERE run_id = ? ORDER BY created_at", (run_id,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            await db.close()
