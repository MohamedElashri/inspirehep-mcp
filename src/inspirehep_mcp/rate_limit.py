"""Bounded per-client rate limiting for the Streamable HTTP endpoint."""

from __future__ import annotations

import json
import math
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from starlette.types import ASGIApp, Message, Receive, Scope, Send


@dataclass
class _Bucket:
    tokens: float
    updated_at: float


class _RequestBodyTooLarge(Exception):
    """Signal that a streamed request crossed its configured byte limit."""


class RequestBodyLimitMiddleware:
    """Reject oversized request bodies, including chunked bodies.

    A declared oversized ``Content-Length`` is rejected before reading. For
    requests without a trustworthy length, the ASGI receive stream is counted
    and aborted as soon as it crosses the limit.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_body_size: int = 262_144,
        path: str = "/mcp",
    ) -> None:
        if max_body_size < 0:
            raise ValueError("max_body_size must be non-negative")
        self.app = app
        self.max_body_size = max_body_size
        self.path = path

    @staticmethod
    def _content_length(scope: Scope) -> int | None:
        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length":
                try:
                    length = int(value)
                except ValueError:
                    return None
                return max(0, length)
        return None

    async def _reject(self, send: Send) -> None:
        body = json.dumps(
            {
                "error": "request_body_too_large",
                "max_body_bytes": self.max_body_size,
            }
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"cache-control", b"no-store"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            self.max_body_size == 0
            or scope["type"] != "http"
            or scope.get("path") != self.path
        ):
            await self.app(scope, receive, send)
            return

        declared_length = self._content_length(scope)
        if declared_length is not None and declared_length > self.max_body_size:
            await self._reject(send)
            return

        received = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body_size:
                    raise _RequestBodyTooLarge
            return message

        async def tracked_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except _RequestBodyTooLarge:
            if response_started:
                raise
            await self._reject(send)


class RateLimitMiddleware:
    """Apply a token-bucket limit to requests for one ASGI path.

    Buckets are keyed by the direct peer address unless proxy-header trust is
    explicitly enabled. The LRU bound prevents arbitrary client addresses from
    growing server memory without limit.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        requests_per_minute: float = 60.0,
        burst: int = 20,
        path: str = "/mcp",
        trust_proxy_headers: bool = False,
        max_clients: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not math.isfinite(requests_per_minute) or requests_per_minute < 0:
            raise ValueError("requests_per_minute must be finite and non-negative")
        if burst < 1:
            raise ValueError("burst must be at least 1")
        if max_clients < 1:
            raise ValueError("max_clients must be at least 1")

        self.app = app
        self.requests_per_minute = requests_per_minute
        self.burst = burst
        self.path = path
        self.trust_proxy_headers = trust_proxy_headers
        self.max_clients = max_clients
        self._clock = clock
        self._buckets: OrderedDict[str, _Bucket] = OrderedDict()

    def _client_key(self, scope: Scope) -> str:
        if self.trust_proxy_headers:
            for name, value in scope.get("headers", []):
                if name.lower() == b"x-forwarded-for":
                    forwarded = value.decode("latin-1").split(",", 1)[0].strip()
                    if forwarded:
                        return forwarded

        client = scope.get("client")
        return str(client[0]) if client else "unknown"

    def _consume(self, client_key: str) -> tuple[bool, int]:
        now = self._clock()
        bucket = self._buckets.get(client_key)
        if bucket is None:
            if len(self._buckets) >= self.max_clients:
                self._buckets.popitem(last=False)
            bucket = _Bucket(tokens=float(self.burst), updated_at=now)
            self._buckets[client_key] = bucket
        else:
            elapsed = max(0.0, now - bucket.updated_at)
            refill_rate = self.requests_per_minute / 60.0
            bucket.tokens = min(float(self.burst), bucket.tokens + elapsed * refill_rate)
            bucket.updated_at = now
            self._buckets.move_to_end(client_key)

        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            return True, 0

        refill_rate = self.requests_per_minute / 60.0
        retry_after = max(1, math.ceil((1.0 - bucket.tokens) / refill_rate))
        return False, retry_after

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            self.requests_per_minute == 0
            or scope["type"] != "http"
            or scope.get("path") != self.path
        ):
            await self.app(scope, receive, send)
            return

        allowed, retry_after = self._consume(self._client_key(scope))
        if allowed:
            await self.app(scope, receive, send)
            return

        body = json.dumps(
            {
                "error": "rate_limit_exceeded",
                "retry_after_seconds": retry_after,
            }
        ).encode()
        response_start: Message = {
            "type": "http.response.start",
            "status": 429,
            "headers": [
                (b"content-type", b"application/json"),
                (b"cache-control", b"no-store"),
                (b"retry-after", str(retry_after).encode("ascii")),
            ],
        }
        await send(response_start)
        await send({"type": "http.response.body", "body": body})
