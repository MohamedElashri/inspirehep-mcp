"""InspireHEP API client with rate limiting, caching, and error handling."""

import asyncio
import logging
import time
from typing import Any

import httpx

from .cache import TTLCache, SQLiteCache, create_cache
from .config import settings
from .errors import APIError, NotFoundError, RateLimitError

logger = logging.getLogger(__name__)

# Default fields to request for literature searches (keeps payloads small)
_LITERATURE_FIELDS = ",".join(
    [
        "titles",
        "authors.full_name",
        "authors.affiliations",
        "abstracts",
        "arxiv_eprints",
        "dois",
        "publication_info",
        "collaborations",
        "citation_count",
        "earliest_date",
        "legacy_creation_date",
    ]
)


class InspireHEPClient:
    """Async HTTP client for the InspireHEP API.

    Features:
    - Automatic rate limiting (token-bucket, configurable)
    - In-memory or persistent (SQLite) cache for GET requests
    - Structured error handling
    - Request timing instrumentation
    """

    def __init__(
        self,
        *,
        requests_per_second: float | None = None,
        cache_ttl: float | None = None,
        cache_max_size: int | None = None,
        cache_persistent: bool | None = None,
        cache_db_path: str | None = None,
        timeout: float | None = None,
        api_base_url: str | None = None,
    ) -> None:
        rps = requests_per_second if requests_per_second is not None else settings.requests_per_second
        self._rate_interval = 1.0 / rps
        self._last_request_time: float = 0.0
        self._rate_lock = asyncio.Lock()

        self._cache = create_cache(
            persistent=cache_persistent if cache_persistent is not None else settings.cache_persistent,
            db_path=cache_db_path or settings.cache_db_path,
            ttl_seconds=cache_ttl if cache_ttl is not None else settings.cache_ttl,
            max_size=cache_max_size if cache_max_size is not None else settings.cache_max_size,
        )

        self._timeout = timeout if timeout is not None else settings.api_timeout
        self._base_url = api_base_url or settings.api_base_url
        self._client: httpx.AsyncClient | None = None

        # Request timing stats
        self._total_requests = 0
        self._total_request_time = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "inspirehep-mcp/0.1.0",
                },
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    async def _wait_for_rate_limit(self) -> None:
        async with self._rate_lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < self._rate_interval:
                await asyncio.sleep(self._rate_interval - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()

    # ------------------------------------------------------------------
    # Core request
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Make an HTTP request to the InspireHEP API."""
        # Build cache key from path + sorted params
        cache_key = f"{method}:{path}:{sorted((params or {}).items())}"

        if use_cache and method == "GET":
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug("Cache hit: %s", cache_key)
                return cached

        await self._wait_for_rate_limit()

        client = await self._get_client()
        t0 = time.monotonic()
        try:
            response = await client.request(method, path, params=params)
        except httpx.TimeoutException as exc:
            raise APIError(
                "Request timed out",
                details=f"The InspireHEP API did not respond within {self._timeout}s. "
                f"Try again later or use a cached result. Path: {path}",
            ) from exc
        except httpx.HTTPError as exc:
            raise APIError(
                "HTTP request failed",
                details=f"Could not connect to InspireHEP API: {exc}. "
                "Check your network connection.",
            ) from exc
        finally:
            elapsed = time.monotonic() - t0
            self._total_requests += 1
            self._total_request_time += elapsed

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                retry_after=float(retry_after) if retry_after else None
            )

        if response.status_code == 404:
            raise NotFoundError("resource", path)

        if response.status_code >= 400:
            raise APIError(
                "API request failed",
                status_code=response.status_code,
                details=response.text[:500],
            )

        data: dict[str, Any] = response.json()

        if use_cache and method == "GET":
            self._cache.set(cache_key, data)

        return data

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    async def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Perform a cached GET request."""
        return await self._request("GET", path, params=params, use_cache=use_cache)

    async def get_text(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Perform a GET request and return the raw response text.

        Used for non-JSON endpoints like BibTeX and LaTeX formats.
        Uses Accept: */* to avoid the default JSON Accept header.
        """
        cache_key = f"GET_TEXT:{path}:{sorted((params or {}).items())}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        await self._wait_for_rate_limit()

        client = await self._get_client()
        try:
            response = await client.request(
                "GET", path, params=params, headers={"Accept": "*/*"}
            )
        except httpx.TimeoutException as exc:
            raise APIError("Request timed out", details=str(exc)) from exc
        except httpx.HTTPError as exc:
            raise APIError("HTTP request failed", details=str(exc)) from exc

        if response.status_code == 404:
            raise NotFoundError("resource", path)
        if response.status_code >= 400:
            raise APIError(
                "API request failed",
                status_code=response.status_code,
                details=response.text[:500],
            )

        text = response.text
        self._cache.set(cache_key, text)
        return text

    # ------------------------------------------------------------------
    # Literature endpoints
    # ------------------------------------------------------------------

    async def search_literature(
        self,
        query: str,
        *,
        sort: str = "bestmatch",
        size: int = 10,
        page: int = 1,
        fields: str | None = None,
    ) -> dict[str, Any]:
        """Search the literature index.

        Returns the raw API response dict containing 'hits' etc.
        """
        params: dict[str, Any] = {
            "q": query,
            "sort": sort,
            "size": min(size, 100),
            "page": page,
            "fields": fields or _LITERATURE_FIELDS,
        }
        return await self.get("/literature", params=params)

    async def get_literature_record(
        self,
        record_id: str,
        *,
        fields: str | None = None,
    ) -> dict[str, Any]:
        """Fetch a single literature record by Inspire ID."""
        params: dict[str, Any] = {}
        if fields:
            params["fields"] = fields
        return await self.get(f"/literature/{record_id}", params=params)

    async def get_literature_by_arxiv(
        self,
        arxiv_id: str,
        *,
        fields: str | None = None,
    ) -> dict[str, Any]:
        """Fetch a literature record by arXiv ID."""
        params: dict[str, Any] = {}
        if fields:
            params["fields"] = fields
        return await self.get(f"/arxiv/{arxiv_id}", params=params)

    async def get_literature_by_doi(
        self,
        doi: str,
        *,
        fields: str | None = None,
    ) -> dict[str, Any]:
        """Fetch a literature record by DOI."""
        params: dict[str, Any] = {}
        if fields:
            params["fields"] = fields
        return await self.get(f"/doi/{doi}", params=params)

    # ------------------------------------------------------------------
    # Author endpoints
    # ------------------------------------------------------------------

    async def search_authors(
        self,
        query: str,
        *,
        size: int = 10,
    ) -> dict[str, Any]:
        """Search the authors index."""
        params: dict[str, Any] = {
            "q": query,
            "size": min(size, 100),
        }
        return await self.get("/authors", params=params)

    # ------------------------------------------------------------------
    # Cache diagnostics
    # ------------------------------------------------------------------

    @property
    def cache_stats(self) -> dict[str, Any]:
        return self._cache.stats

    @property
    def request_stats(self) -> dict[str, Any]:
        avg = (self._total_request_time / self._total_requests) if self._total_requests else 0.0
        return {
            "total_requests": self._total_requests,
            "total_request_time_seconds": round(self._total_request_time, 3),
            "average_request_time_seconds": round(avg, 3),
        }

    @property
    def full_stats(self) -> dict[str, Any]:
        return {
            "cache": self.cache_stats,
            "requests": self.request_stats,
        }
