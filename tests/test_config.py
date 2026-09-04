"""Unit tests for configuration module."""

import os

import pytest

from inspirehep_mcp.config import (
    Settings,
    _env_bool,
    _env_float,
    _env_int,
    _env_list,
    _env_str,
)


class TestEnvHelpers:
    def test_env_float_default(self):
        assert _env_float("NONEXISTENT_KEY_12345", 3.14) == 3.14

    def test_env_float_from_env(self, monkeypatch):
        monkeypatch.setenv("TEST_FLOAT", "2.5")
        assert _env_float("TEST_FLOAT", 0.0) == 2.5

    def test_env_int_default(self):
        assert _env_int("NONEXISTENT_KEY_12345", 42) == 42

    def test_env_int_from_env(self, monkeypatch):
        monkeypatch.setenv("TEST_INT", "100")
        assert _env_int("TEST_INT", 0) == 100

    def test_env_bool_default(self):
        assert _env_bool("NONEXISTENT_KEY_12345", False) is False
        assert _env_bool("NONEXISTENT_KEY_12345", True) is True

    def test_env_bool_truthy(self, monkeypatch):
        for val in ("1", "true", "True", "TRUE", "yes", "Yes"):
            monkeypatch.setenv("TEST_BOOL", val)
            assert _env_bool("TEST_BOOL", False) is True

    def test_env_bool_falsy(self, monkeypatch):
        for val in ("0", "false", "no", "anything"):
            monkeypatch.setenv("TEST_BOOL", val)
            assert _env_bool("TEST_BOOL", True) is False

    def test_env_str_default(self):
        assert _env_str("NONEXISTENT_KEY_12345", "default") == "default"

    def test_env_str_from_env(self, monkeypatch):
        monkeypatch.setenv("TEST_STR", "custom")
        assert _env_str("TEST_STR", "default") == "custom"

    def test_env_list(self, monkeypatch):
        monkeypatch.setenv("TEST_LIST", "example.org, api.example.org:443, ")
        assert _env_list("TEST_LIST") == ["example.org", "api.example.org:443"]

    def test_env_list_default(self):
        assert _env_list("NONEXISTENT_KEY_12345", ("localhost:*",)) == [
            "localhost:*"
        ]


class TestSettings:
    def test_defaults(self, monkeypatch):
        for key in tuple(os.environ):
            if key.startswith("INSPIREHEP_"):
                monkeypatch.delenv(key)
        monkeypatch.delenv("PORT", raising=False)

        s = Settings()
        assert s.api_base_url == "https://inspirehep.net/api"
        assert s.api_timeout == 30.0
        assert s.requests_per_second == 1.5
        assert s.upstream_max_pending == 32
        assert s.cache_ttl == 86400.0
        assert s.cache_max_size == 512
        assert s.cache_persistent is False
        assert s.cache_db_path == "inspirehep_cache.db"
        assert s.transport == "stdio"
        assert s.host == "127.0.0.1"
        assert s.port == 8000
        assert s.http_path == "/mcp"
        assert s.http_stateless is True
        assert s.http_json_response is True
        assert s.http_rate_limit == 60.0
        assert s.http_rate_limit_burst == 20
        assert s.http_rate_limit_max_clients == 10_000
        assert s.http_max_body_size == 262_144
        assert s.http_max_concurrency == 100
        assert s.http_keep_alive_timeout == 5
        assert s.trust_proxy_headers is False
        assert s.max_input_length == 2_048
        assert s.max_identifier_length == 512
        assert s.max_response_bytes == 1_048_576
        assert s.max_references == 250
        assert s.max_figures == 100
        assert s.dns_rebinding_protection is True
        assert s.allowed_hosts == ["127.0.0.1:*", "localhost:*"]
        assert s.allowed_origins == []
        assert s.log_level == "INFO"

    def test_http_environment(self, monkeypatch):
        monkeypatch.setenv("INSPIREHEP_TRANSPORT", "streamable-http")
        monkeypatch.setenv("INSPIREHEP_HOST", "0.0.0.0")
        monkeypatch.setenv("INSPIREHEP_PORT", "9000")
        monkeypatch.setenv("INSPIREHEP_HTTP_PATH", "/custom-mcp")
        monkeypatch.setenv("INSPIREHEP_HTTP_STATELESS", "false")
        monkeypatch.setenv("INSPIREHEP_HTTP_JSON_RESPONSE", "false")
        monkeypatch.setenv("INSPIREHEP_HTTP_RATE_LIMIT", "120")
        monkeypatch.setenv("INSPIREHEP_HTTP_RATE_LIMIT_BURST", "30")
        monkeypatch.setenv("INSPIREHEP_HTTP_RATE_LIMIT_MAX_CLIENTS", "500")
        monkeypatch.setenv("INSPIREHEP_HTTP_MAX_BODY_SIZE", "4096")
        monkeypatch.setenv("INSPIREHEP_HTTP_MAX_CONCURRENCY", "25")
        monkeypatch.setenv("INSPIREHEP_HTTP_KEEP_ALIVE_TIMEOUT", "3")
        monkeypatch.setenv("INSPIREHEP_UPSTREAM_MAX_PENDING", "12")
        monkeypatch.setenv("INSPIREHEP_MAX_INPUT_LENGTH", "1000")
        monkeypatch.setenv("INSPIREHEP_MAX_IDENTIFIER_LENGTH", "200")
        monkeypatch.setenv("INSPIREHEP_MAX_RESPONSE_BYTES", "500000")
        monkeypatch.setenv("INSPIREHEP_MAX_REFERENCES", "50")
        monkeypatch.setenv("INSPIREHEP_MAX_FIGURES", "25")
        monkeypatch.setenv("INSPIREHEP_TRUST_PROXY_HEADERS", "true")
        monkeypatch.setenv("INSPIREHEP_ALLOWED_HOSTS", "mcp.example.org")
        monkeypatch.setenv("INSPIREHEP_ALLOWED_ORIGINS", "https://example.org")

        s = Settings()

        assert s.transport == "streamable-http"
        assert s.host == "0.0.0.0"
        assert s.port == 9000
        assert s.http_path == "/custom-mcp"
        assert s.http_stateless is False
        assert s.http_json_response is False
        assert s.http_rate_limit == 120.0
        assert s.http_rate_limit_burst == 30
        assert s.http_rate_limit_max_clients == 500
        assert s.http_max_body_size == 4096
        assert s.http_max_concurrency == 25
        assert s.http_keep_alive_timeout == 3
        assert s.upstream_max_pending == 12
        assert s.trust_proxy_headers is True
        assert s.max_input_length == 1000
        assert s.max_identifier_length == 200
        assert s.max_response_bytes == 500000
        assert s.max_references == 50
        assert s.max_figures == 25
        assert s.allowed_hosts == ["mcp.example.org"]
        assert s.allowed_origins == ["https://example.org"]

    def test_platform_port_fallback(self, monkeypatch):
        monkeypatch.delenv("INSPIREHEP_PORT", raising=False)
        monkeypatch.setenv("PORT", "8080")
        assert Settings().port == 8080

    @pytest.mark.parametrize(
        "name",
        [
            "INSPIREHEP_UPSTREAM_MAX_PENDING",
            "INSPIREHEP_HTTP_MAX_CONCURRENCY",
            "INSPIREHEP_MAX_INPUT_LENGTH",
            "INSPIREHEP_MAX_IDENTIFIER_LENGTH",
            "INSPIREHEP_MAX_RESPONSE_BYTES",
            "INSPIREHEP_MAX_REFERENCES",
            "INSPIREHEP_MAX_FIGURES",
        ],
    )
    def test_positive_safety_limits(self, monkeypatch, name):
        monkeypatch.setenv(name, "0")
        with pytest.raises(ValueError, match=name):
            Settings()
