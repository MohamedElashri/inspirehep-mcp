"""Unit tests for configuration module."""

import os

import pytest

from inspirehep_mcp.config import Settings, _env_bool, _env_float, _env_int, _env_str


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


class TestSettings:
    def test_defaults(self):
        s = Settings()
        assert s.api_base_url == "https://inspirehep.net/api"
        assert s.api_timeout == 30.0
        assert s.requests_per_second == 1.5
        assert s.cache_ttl == 86400.0
        assert s.cache_max_size == 512
        assert s.cache_persistent is False
        assert s.cache_db_path == "inspirehep_cache.db"
        assert s.log_level == "INFO"
