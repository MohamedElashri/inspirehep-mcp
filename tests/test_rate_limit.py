"""Tests for bounded per-client Streamable HTTP rate limiting."""

import json

import pytest

from inspirehep_mcp.rate_limit import RateLimitMiddleware, RequestBodyLimitMiddleware


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


async def ok_app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


async def request(app, *, client="192.0.2.1", path="/mcp", headers=()):
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await app(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": list(headers),
            "client": (client, 12345),
        },
        receive,
        send,
    )
    return messages


@pytest.mark.asyncio
async def test_burst_is_enforced_and_refills():
    clock = Clock()
    app = RateLimitMiddleware(
        ok_app, requests_per_minute=60, burst=2, clock=clock
    )

    assert (await request(app))[0]["status"] == 200
    assert (await request(app))[0]["status"] == 200

    limited = await request(app)
    assert limited[0]["status"] == 429
    assert (b"retry-after", b"1") in limited[0]["headers"]
    assert json.loads(limited[1]["body"]) == {
        "error": "rate_limit_exceeded",
        "retry_after_seconds": 1,
    }

    clock.now = 1.0
    assert (await request(app))[0]["status"] == 200


@pytest.mark.asyncio
async def test_clients_have_independent_buckets():
    app = RateLimitMiddleware(ok_app, requests_per_minute=1, burst=1)

    assert (await request(app, client="192.0.2.1"))[0]["status"] == 200
    assert (await request(app, client="192.0.2.1"))[0]["status"] == 429
    assert (await request(app, client="192.0.2.2"))[0]["status"] == 200


@pytest.mark.asyncio
async def test_health_path_is_not_limited():
    app = RateLimitMiddleware(ok_app, requests_per_minute=1, burst=1)

    assert (await request(app, path="/health"))[0]["status"] == 200
    assert (await request(app, path="/health"))[0]["status"] == 200


@pytest.mark.asyncio
async def test_zero_disables_rate_limit():
    app = RateLimitMiddleware(ok_app, requests_per_minute=0, burst=1)

    for _ in range(3):
        assert (await request(app))[0]["status"] == 200


@pytest.mark.asyncio
async def test_proxy_header_trust_is_explicit():
    forwarded = ((b"x-forwarded-for", b"198.51.100.1"),)
    untrusted_app = RateLimitMiddleware(ok_app, requests_per_minute=1, burst=1)

    assert (await request(untrusted_app, headers=forwarded))[0]["status"] == 200
    assert (
        await request(
            untrusted_app,
            headers=((b"x-forwarded-for", b"198.51.100.2"),),
        )
    )[0]["status"] == 429

    app = RateLimitMiddleware(
        ok_app, requests_per_minute=1, burst=1, trust_proxy_headers=True
    )

    assert (await request(app, headers=forwarded))[0]["status"] == 200
    assert (await request(app, headers=forwarded))[0]["status"] == 429
    assert (
        await request(
            app, headers=((b"x-forwarded-for", b"198.51.100.2, 10.0.0.1"),)
        )
    )[0]["status"] == 200


@pytest.mark.asyncio
async def test_client_bucket_storage_is_bounded_lru():
    app = RateLimitMiddleware(
        ok_app, requests_per_minute=60, burst=1, max_clients=2
    )

    await request(app, client="192.0.2.1")
    await request(app, client="192.0.2.2")
    await request(app, client="192.0.2.1")
    await request(app, client="192.0.2.3")

    assert list(app._buckets) == ["192.0.2.1", "192.0.2.3"]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"requests_per_minute": -1}, "requests_per_minute"),
        ({"requests_per_minute": float("nan")}, "requests_per_minute"),
        ({"burst": 0}, "burst"),
        ({"max_clients": 0}, "max_clients"),
    ],
)
def test_invalid_configuration(kwargs, message):
    with pytest.raises(ValueError, match=message):
        RateLimitMiddleware(ok_app, **kwargs)


@pytest.mark.asyncio
async def test_declared_oversized_body_is_rejected_before_downstream():
    called = False

    async def downstream(scope, receive, send):
        nonlocal called
        called = True

    app = RequestBodyLimitMiddleware(downstream, max_body_size=4)
    messages = await request(
        app,
        headers=((b"content-length", b"5"),),
    )

    assert messages[0]["status"] == 413
    assert json.loads(messages[1]["body"])["max_body_bytes"] == 4
    assert called is False


@pytest.mark.asyncio
async def test_streamed_oversized_body_is_rejected():
    chunks = [
        {"type": "http.request", "body": b"abc", "more_body": True},
        {"type": "http.request", "body": b"de", "more_body": False},
    ]
    messages = []

    async def reading_app(scope, receive, send):
        while (await receive()).get("more_body", False):
            pass
        await send({"type": "http.response.start", "status": 200, "headers": []})

    async def receive():
        return chunks.pop(0)

    async def send(message):
        messages.append(message)

    app = RequestBodyLimitMiddleware(reading_app, max_body_size=4)
    await app(
        {
            "type": "http",
            "method": "POST",
            "path": "/mcp",
            "headers": [],
            "client": ("192.0.2.1", 12345),
        },
        receive,
        send,
    )

    assert messages[0]["status"] == 413


@pytest.mark.asyncio
async def test_body_limit_bypasses_other_paths_and_can_be_disabled():
    app = RequestBodyLimitMiddleware(ok_app, max_body_size=1)
    assert (await request(app, path="/health"))[0]["status"] == 200

    disabled = RequestBodyLimitMiddleware(ok_app, max_body_size=0)
    assert (
        await request(disabled, headers=((b"content-length", b"1000"),))
    )[0]["status"] == 200


def test_body_limit_rejects_negative_configuration():
    with pytest.raises(ValueError, match="max_body_size"):
        RequestBodyLimitMiddleware(ok_app, max_body_size=-1)
