"""Configuration management for InspireHEP MCP server.

Settings are loaded from environment variables with sensible defaults.
All env vars are prefixed with ``INSPIREHEP_`` except the conventional
hosting-platform ``PORT`` fallback.
"""

import os
from collections.abc import Sequence


def _env_float(key: str, default: float) -> float:
    val = os.environ.get(key)
    return float(val) if val is not None else default


def _env_int(key: str, default: int) -> int:
    val = os.environ.get(key)
    return int(val) if val is not None else default


def _env_bool(key: str, default: bool) -> bool:
    val = os.environ.get(key)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes")


def _env_str(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_list(key: str, default: Sequence[str] = ()) -> list[str]:
    val = os.environ.get(key)
    if val is None:
        return list(default)
    return [item.strip() for item in val.split(",") if item.strip()]


class Settings:
    """Centralised configuration for the MCP server."""

    def __init__(self) -> None:
        # API
        self.api_base_url = _env_str(
            "INSPIREHEP_API_BASE_URL", "https://inspirehep.net/api"
        )
        self.api_timeout = _env_float("INSPIREHEP_API_TIMEOUT", 30.0)
        self.requests_per_second = _env_float(
            "INSPIREHEP_REQUESTS_PER_SECOND", 1.5
        )
        self.upstream_max_pending = _env_int(
            "INSPIREHEP_UPSTREAM_MAX_PENDING", 32
        )

        # Cache — in-memory
        self.cache_ttl = _env_float("INSPIREHEP_CACHE_TTL", 86400.0)
        self.cache_max_size = _env_int("INSPIREHEP_CACHE_MAX_SIZE", 512)

        # Cache — persistent (SQLite)
        self.cache_persistent = _env_bool("INSPIREHEP_CACHE_PERSISTENT", False)
        self.cache_db_path = _env_str(
            "INSPIREHEP_CACHE_DB_PATH", "inspirehep_cache.db"
        )

        # Server and Streamable HTTP transport. PORT is supported as a fallback
        # for hosting providers that inject it automatically.
        self.transport = _env_str("INSPIREHEP_TRANSPORT", "stdio")
        self.host = _env_str("INSPIREHEP_HOST", "127.0.0.1")
        self.port = _env_int("INSPIREHEP_PORT", _env_int("PORT", 8000))
        self.http_path = _env_str("INSPIREHEP_HTTP_PATH", "/mcp")
        self.http_stateless = _env_bool("INSPIREHEP_HTTP_STATELESS", True)
        self.http_json_response = _env_bool(
            "INSPIREHEP_HTTP_JSON_RESPONSE", True
        )
        self.http_rate_limit = _env_float("INSPIREHEP_HTTP_RATE_LIMIT", 60.0)
        self.http_rate_limit_burst = _env_int(
            "INSPIREHEP_HTTP_RATE_LIMIT_BURST", 20
        )
        self.http_rate_limit_max_clients = _env_int(
            "INSPIREHEP_HTTP_RATE_LIMIT_MAX_CLIENTS", 10_000
        )
        self.http_max_body_size = _env_int(
            "INSPIREHEP_HTTP_MAX_BODY_SIZE", 262_144
        )
        self.http_max_concurrency = _env_int(
            "INSPIREHEP_HTTP_MAX_CONCURRENCY", 100
        )
        self.http_keep_alive_timeout = _env_int(
            "INSPIREHEP_HTTP_KEEP_ALIVE_TIMEOUT", 5
        )
        self.trust_proxy_headers = _env_bool(
            "INSPIREHEP_TRUST_PROXY_HEADERS", False
        )

        # Tool input and output safety limits.
        self.max_input_length = _env_int("INSPIREHEP_MAX_INPUT_LENGTH", 2_048)
        self.max_identifier_length = _env_int(
            "INSPIREHEP_MAX_IDENTIFIER_LENGTH", 512
        )
        self.max_response_bytes = _env_int(
            "INSPIREHEP_MAX_RESPONSE_BYTES", 1_048_576
        )
        self.max_references = _env_int("INSPIREHEP_MAX_REFERENCES", 250)
        self.max_figures = _env_int("INSPIREHEP_MAX_FIGURES", 100)

        positive_limits = {
            "INSPIREHEP_UPSTREAM_MAX_PENDING": self.upstream_max_pending,
            "INSPIREHEP_HTTP_MAX_CONCURRENCY": self.http_max_concurrency,
            "INSPIREHEP_MAX_INPUT_LENGTH": self.max_input_length,
            "INSPIREHEP_MAX_IDENTIFIER_LENGTH": self.max_identifier_length,
            "INSPIREHEP_MAX_RESPONSE_BYTES": self.max_response_bytes,
            "INSPIREHEP_MAX_REFERENCES": self.max_references,
            "INSPIREHEP_MAX_FIGURES": self.max_figures,
        }
        for name, value in positive_limits.items():
            if value < 1:
                raise ValueError(f"{name} must be at least 1")
        if self.http_max_body_size < 0:
            raise ValueError("INSPIREHEP_HTTP_MAX_BODY_SIZE must be non-negative")
        if self.http_keep_alive_timeout < 0:
            raise ValueError(
                "INSPIREHEP_HTTP_KEEP_ALIVE_TIMEOUT must be non-negative"
            )

        # MCP requires Origin validation for Streamable HTTP. Host validation
        # also protects locally-bound servers against DNS rebinding. Remote
        # deployments should explicitly add their public hostname.
        self.dns_rebinding_protection = _env_bool(
            "INSPIREHEP_DNS_REBINDING_PROTECTION", True
        )
        self.allowed_hosts = _env_list(
            "INSPIREHEP_ALLOWED_HOSTS", ("127.0.0.1:*", "localhost:*")
        )
        self.allowed_origins = _env_list("INSPIREHEP_ALLOWED_ORIGINS")

        # Logging
        self.log_level = _env_str("INSPIREHEP_LOG_LEVEL", "INFO")


# Singleton
settings = Settings()
