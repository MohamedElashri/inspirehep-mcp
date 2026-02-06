"""Configuration management for InspireHEP MCP server.

Settings are loaded from environment variables with sensible defaults.
All env vars are prefixed with ``INSPIREHEP_``.
"""

import os


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


class Settings:
    """Centralised configuration for the MCP server."""

    # API
    api_base_url: str = _env_str("INSPIREHEP_API_BASE_URL", "https://inspirehep.net/api")
    api_timeout: float = _env_float("INSPIREHEP_API_TIMEOUT", 30.0)
    requests_per_second: float = _env_float("INSPIREHEP_REQUESTS_PER_SECOND", 1.5)

    # Cache — in-memory
    cache_ttl: float = _env_float("INSPIREHEP_CACHE_TTL", 86400.0)
    cache_max_size: int = _env_int("INSPIREHEP_CACHE_MAX_SIZE", 512)

    # Cache — persistent (SQLite)
    cache_persistent: bool = _env_bool("INSPIREHEP_CACHE_PERSISTENT", False)
    cache_db_path: str = _env_str("INSPIREHEP_CACHE_DB_PATH", "inspirehep_cache.db")

    # Logging
    log_level: str = _env_str("INSPIREHEP_LOG_LEVEL", "INFO")


# Singleton
settings = Settings()
