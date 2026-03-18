"""Thin async GitHub REST client for the BenchmarkControl control plane.

Responsibilities:
- Write / read RunRecord JSON to the data branch via the Contents API.
- Dispatch the benchmark workflow via the Actions API.
- List historical run records by walking the git tree.

All HTTP is treated as a boundary: retried with tenacity on transient errors
(5xx / network faults). Business logic lives elsewhere.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_fixed

from benchmark_control_arcade.config import Settings
from benchmark_control_arcade.history_layout import build_run_layout
from benchmark_control_arcade.run_models import RunRecord

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"


def _is_transient(exc: BaseException) -> bool:
    """Return True for errors worth retrying (network issues, 5xx)."""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, GitHubHTTPError) and exc.status_code >= 500:
        return True
    return False


class GitHubHTTPError(Exception):
    """Raised when GitHub returns an unexpected HTTP status."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"GitHub HTTP {status_code}: {message}")
        self.status_code = status_code


def _raise_for_status(response: httpx.Response, context: str = "") -> None:
    if response.is_error:
        prefix = f"[{context}] " if context else ""
        raise GitHubHTTPError(
            response.status_code,
            f"{prefix}{response.text[:200]}",
        )


def _encode(content: str) -> str:
    """Base64-encode a UTF-8 string for the GitHub Contents API."""
    return base64.b64encode(content.encode()).decode()


def _decode(content_b64: str) -> str:
    """Decode base64 content returned by the GitHub Contents API."""
    # GitHub may include newlines in the base64 payload — strip them.
    return base64.b64decode(content_b64.replace("\n", "")).decode()


class GitHubClient:
    """Async GitHub client scoped to a single repository.

    All writes are restricted to *settings.github_data_branch*.
    Workflow dispatches always target ``ref="main"``.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._owner = settings.github_owner
        self._repo = settings.github_repo
        self._token = settings.github_token.get_secret_value()
        self._data_branch = settings.github_data_branch
        self._workflow = settings.github_run_workflow

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _contents_url(self, path: str) -> str:
        return f"{_GITHUB_API}/repos/{self._owner}/{self._repo}/contents/{path}"

    def _dispatch_url(self) -> str:
        return (
            f"{_GITHUB_API}/repos/{self._owner}/{self._repo}"
            f"/actions/workflows/{self._workflow}/dispatches"
        )

    def _tree_url(self) -> str:
        return (
            f"{_GITHUB_API}/repos/{self._owner}/{self._repo}"
            f"/git/trees/{self._data_branch}"
        )

    # ------------------------------------------------------------------
    # Low-level GET/PUT with retry
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception(_is_transient),
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        reraise=True,
    )
    async def _put_file(
        self, path: str, content_b64: str, message: str, sha: str | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "message": message,
            "content": content_b64,
            "branch": self._data_branch,
        }
        if sha is not None:
            payload["sha"] = sha

        async with httpx.AsyncClient() as client:
            response = await client.put(
                self._contents_url(path),
                headers=self._headers(),
                content=json.dumps(payload).encode(),
            )
        _raise_for_status(response, context=f"PUT {path}")
        return response.json()

    @retry(
        retry=retry_if_exception(_is_transient),
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        reraise=True,
    )
    async def _get_file(self, path: str) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self._contents_url(path),
                headers=self._headers(),
                params={"ref": self._data_branch},
            )
        _raise_for_status(response, context=f"GET {path}")
        return response.json()

    @retry(
        retry=retry_if_exception(_is_transient),
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        reraise=True,
    )
    async def _get_tree(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self._tree_url(),
                headers=self._headers(),
                params={"recursive": "1"},
            )
        _raise_for_status(response, context="GET tree")
        return response.json().get("tree", [])

    @retry(
        retry=retry_if_exception(_is_transient),
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        reraise=True,
    )
    async def _post_dispatch(self, payload: dict[str, Any]) -> None:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self._dispatch_url(),
                headers=self._headers(),
                content=json.dumps(payload).encode(),
            )
        _raise_for_status(response, context="POST dispatch")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_initial_run_record(self, record: RunRecord) -> None:
        """Write a new run record (status=queued) to the data branch.

        Must be called BEFORE dispatching the workflow so the record exists
        when the worker first polls for it.
        """
        layout = build_run_layout(record.run_id, record.created_at)
        path = str(layout.run_json)
        content_b64 = _encode(record.model_dump_json())
        message = f"chore: queue run {record.run_id}"
        await self._put_file(path, content_b64, message)
        logger.info("Created run record for %s at %s", record.run_id, path)

    async def update_run_record(self, record: RunRecord) -> None:
        """Overwrite an existing run record on the data branch.

        Reads the current SHA first (required by the GitHub Contents API for
        updates), then PUTs the new content.
        """
        layout = build_run_layout(record.run_id, record.created_at)
        path = str(layout.run_json)

        existing = await self._get_file(path)
        sha = existing["sha"]

        content_b64 = _encode(record.model_dump_json())
        message = f"chore: update run {record.run_id} status={record.status.value}"
        await self._put_file(path, content_b64, message, sha=sha)
        logger.info("Updated run record for %s (status=%s)", record.run_id, record.status)

    async def dispatch_workflow(
        self, run_id: str, run_type: str, run_spec_json: str
    ) -> None:
        """Dispatch the benchmark workflow with the given run inputs.

        The run record MUST already exist on the data branch before calling
        this method.
        """
        payload = {
            "ref": "main",
            "inputs": {
                "run_id": run_id,
                "run_type": run_type,
                "run_spec_json": run_spec_json,
            },
        }
        await self._post_dispatch(payload)
        logger.info("Dispatched workflow %s for run %s", self._workflow, run_id)

    async def get_run_record(self, run_id: str, created_at: datetime) -> RunRecord:
        """Fetch and parse the RunRecord for *run_id* from the data branch."""
        layout = build_run_layout(run_id, created_at)
        path = str(layout.run_json)
        data = await self._get_file(path)
        raw = _decode(data["content"])
        return RunRecord.model_validate_json(raw)

    async def list_run_records(self, limit: int = 20) -> list[RunRecord]:
        """Return up to *limit* run records, newest first.

        Uses the git-trees API to discover all run.json files, then fetches
        each one concurrently. Records are sorted by *created_at* descending.
        """
        import asyncio

        tree = await self._get_tree()
        run_json_paths = [
            item["path"]
            for item in tree
            if item.get("type") == "blob" and item["path"].endswith("/run.json")
        ]

        # Sort paths descending by path string (YYYY/MM/DD sorts lexicographically)
        run_json_paths.sort(reverse=True)
        run_json_paths = run_json_paths[:limit]

        async def _fetch_one(path: str) -> RunRecord | None:
            try:
                data = await self._get_file(path)
                raw = _decode(data["content"])
                return RunRecord.model_validate_json(raw)
            except Exception:
                logger.warning("Failed to parse run record at %s", path, exc_info=True)
                return None

        results = await asyncio.gather(*[_fetch_one(p) for p in run_json_paths])
        records = [r for r in results if r is not None]
        # Final sort by created_at descending (handles edge cases where path
        # sort and creation time differ).
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records
