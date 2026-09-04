"""Tests for native server startup and the HTTP health endpoint."""

import json

import pytest

from inspirehep_mcp import __version__, server
from inspirehep_mcp.rate_limit import RateLimitMiddleware, RequestBodyLimitMiddleware


def test_main_defaults_to_stdio(monkeypatch):
    calls = []
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: calls.append(kwargs))

    server.main([])

    assert calls == [{"transport": "stdio"}]


def test_main_configures_streamable_http(monkeypatch):
    app_calls = []
    run_calls = []

    async def downstream(scope, receive, send):
        pass

    def make_app(**kwargs):
        app_calls.append(kwargs)
        return downstream

    monkeypatch.setattr(server.mcp, "streamable_http_app", make_app)
    monkeypatch.setattr(
        server.uvicorn,
        "run",
        lambda app, **kwargs: run_calls.append((app, kwargs)),
    )

    server.main(
        [
            "--transport",
            "streamable-http",
            "--host",
            "0.0.0.0",
            "--port",
            "9000",
            "--path",
            "/endpoint",
            "--rate-limit",
            "90",
            "--rate-limit-burst",
            "12",
            "--max-body-size",
            "4096",
            "--max-concurrency",
            "25",
            "--timeout-keep-alive",
            "3",
            "--trust-proxy-headers",
        ]
    )

    app_call = app_calls[0]
    assert app_call["host"] == "0.0.0.0"
    assert app_call["streamable_http_path"] == "/endpoint"
    assert app_call["stateless_http"] is True
    assert app_call["json_response"] is True
    assert app_call["transport_security"].enable_dns_rebinding_protection is True
    assert app_call["transport_security"].allowed_hosts == [
        "127.0.0.1:*",
        "localhost:*",
    ]

    app, run_kwargs = run_calls[0]
    assert isinstance(app, RateLimitMiddleware)
    assert app.requests_per_minute == 90
    assert app.burst == 12
    assert app.path == "/endpoint"
    assert app.trust_proxy_headers is True
    assert isinstance(app.app, RequestBodyLimitMiddleware)
    assert app.app.max_body_size == 4096
    assert app.app.path == "/endpoint"
    assert run_kwargs == {
        "host": "0.0.0.0",
        "port": 9000,
        "log_level": "info",
        "proxy_headers": False,
        "limit_concurrency": 25,
        "timeout_keep_alive": 3,
    }


def test_path_must_be_absolute():
    with pytest.raises(SystemExit):
        server._parse_args(["--path", "mcp"])


def test_port_must_be_valid():
    with pytest.raises(SystemExit):
        server._parse_args(["--port", "70000"])


@pytest.mark.parametrize("value", ["-1", "nan", "inf"])
def test_rate_limit_must_be_valid(value):
    with pytest.raises(SystemExit):
        server._parse_args(["--rate-limit", value])


def test_rate_limit_burst_must_be_positive():
    with pytest.raises(SystemExit):
        server._parse_args(["--rate-limit-burst", "0"])


@pytest.mark.parametrize(
    "args",
    [
        ["--max-body-size", "-1"],
        ["--max-concurrency", "0"],
        ["--timeout-keep-alive", "-1"],
    ],
)
def test_http_resource_limits_must_be_valid(args):
    with pytest.raises(SystemExit):
        server._parse_args(args)


def test_invalid_transport_from_environment_default(monkeypatch):
    monkeypatch.setattr(server.settings, "transport", "invalid")
    with pytest.raises(SystemExit):
        server._parse_args([])


@pytest.mark.asyncio
async def test_health_check():
    response = await server.health_check(None)
    assert response.status_code == 200
    assert json.loads(response.body) == {
        "status": "ok",
        "service": "inspirehep-mcp",
        "version": __version__,
    }
