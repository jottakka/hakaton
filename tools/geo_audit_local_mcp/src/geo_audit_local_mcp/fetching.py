"""HTTP fetch helpers with consistent response normalization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

import httpx

from .models import ArtifactCheck, ArtifactStatus

DEFAULT_TIMEOUT = 15.0
USER_AGENT = "geo-audit-local-mcp/0.1 (deterministic evidence collector)"

# Artifact checks fetch up to 4 KB — enough for any robots.txt with many
# Disallow blocks before the Sitemap: declarations.
ARTIFACT_MAX_BODY = 4096


@dataclass
class FetchResult:
    url: str
    status_code: Optional[int]
    final_url: Optional[str]
    body: Optional[str]
    error: Optional[str]

    @property
    def is_ok(self) -> bool:
        return self.status_code is not None and 200 <= self.status_code < 300

    @property
    def is_redirect(self) -> bool:
        return self.status_code is not None and 300 <= self.status_code < 400


def _page_client() -> httpx.AsyncClient:
    """Client for full page fetches — follows redirects."""
    return httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )


def _artifact_client() -> httpx.AsyncClient:
    """Client for artifact checks — does NOT follow redirects so that
    3xx responses surface explicitly as ArtifactStatus.REDIRECT."""
    return httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=False,
        headers={"User-Agent": USER_AGENT},
    )


async def _fetch(client_factory, url: str, max_body: int) -> FetchResult:
    try:
        async with client_factory() as client:
            resp = await client.get(url)
            body = resp.text[:max_body] if resp.text else None
            # httpx normalises the final URL even without redirects
            final_url = str(resp.url) if str(resp.url) != url else None
            if resp.is_redirect and resp.headers.get("location"):
                final_url = urljoin(url, resp.headers["location"])
            return FetchResult(
                url=url,
                status_code=resp.status_code,
                final_url=final_url,
                body=body,
                error=None,
            )
    except httpx.TimeoutException:
        return FetchResult(url=url, status_code=None, final_url=None, body=None, error="timeout")
    except httpx.ConnectError as e:
        return FetchResult(url=url, status_code=None, final_url=None, body=None, error=f"connect_error: {e}")
    except httpx.HTTPError as e:
        return FetchResult(url=url, status_code=None, final_url=None, body=None, error=f"http_error: {e}")


async def fetch_url(url: str, max_body: int = 500_000) -> FetchResult:
    return await _fetch(_page_client, url, max_body)


async def check_artifact(url: str) -> ArtifactCheck:
    result = await _fetch(_artifact_client, url, ARTIFACT_MAX_BODY)

    if result.error:
        return ArtifactCheck(
            url=url,
            status=ArtifactStatus.ERROR,
            http_status=None,
            error_detail=result.error,
        )
    if result.status_code == 200:
        return ArtifactCheck(
            url=url,
            status=ArtifactStatus.FOUND,
            http_status=200,
            # Store the full fetched body so robots.txt sitemap declarations
            # at any position in the file are always captured.
            content_snippet=result.body,
        )
    if result.is_redirect:
        return ArtifactCheck(
            url=url,
            status=ArtifactStatus.REDIRECT,
            http_status=result.status_code,
            redirect_target=result.final_url,
        )
    return ArtifactCheck(
        url=url,
        status=ArtifactStatus.NOT_FOUND,
        http_status=result.status_code,
    )


async def fetch_page(url: str) -> FetchResult:
    return await _fetch(_page_client, url, 500_000)
