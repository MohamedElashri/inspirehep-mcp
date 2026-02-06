"""Unit tests for TTLCache and SQLiteCache."""

import os
import tempfile
import time

import pytest

from inspirehep_mcp.cache import TTLCache, SQLiteCache, create_cache


# ======================================================================
# TTLCache
# ======================================================================


class TestTTLCache:
    def test_set_and_get(self):
        cache = TTLCache()
        cache.set("k1", {"data": 1})
        assert cache.get("k1") == {"data": 1}

    def test_get_missing_returns_none(self):
        cache = TTLCache()
        assert cache.get("missing") is None

    def test_expiration(self):
        cache = TTLCache(ttl_seconds=0.05)
        cache.set("k1", "value")
        assert cache.get("k1") == "value"
        time.sleep(0.06)
        assert cache.get("k1") is None

    def test_lru_eviction(self):
        cache = TTLCache(max_size=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)  # should evict "a"
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_lru_access_order(self):
        cache = TTLCache(max_size=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.get("a")  # access "a" so "b" becomes LRU
        cache.set("c", 3)  # should evict "b"
        assert cache.get("a") == 1
        assert cache.get("b") is None
        assert cache.get("c") == 3

    def test_overwrite_existing_key(self):
        cache = TTLCache()
        cache.set("k1", "old")
        cache.set("k1", "new")
        assert cache.get("k1") == "new"
        assert cache.size == 1

    def test_invalidate(self):
        cache = TTLCache()
        cache.set("k1", "value")
        cache.invalidate("k1")
        assert cache.get("k1") is None

    def test_invalidate_missing_key(self):
        cache = TTLCache()
        cache.invalidate("missing")  # should not raise

    def test_clear(self):
        cache = TTLCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.size == 0
        assert cache.get("a") is None

    def test_stats(self):
        cache = TTLCache(ttl_seconds=3600, max_size=100)
        cache.set("k1", "v1")
        cache.get("k1")  # hit
        cache.get("missing")  # miss
        stats = cache.stats
        assert stats["backend"] == "memory"
        assert stats["size"] == 1
        assert stats["max_size"] == 100
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate_percent"] == 50.0

    def test_hit_rate_zero_requests(self):
        cache = TTLCache()
        assert cache.hit_rate == 0.0

    def test_eviction_counter(self):
        cache = TTLCache(max_size=1)
        cache.set("a", 1)
        cache.set("b", 2)  # evicts "a"
        assert cache.stats["evictions"] == 1


# ======================================================================
# SQLiteCache
# ======================================================================


class TestSQLiteCache:
    @pytest.fixture
    def db_path(self, tmp_path):
        return str(tmp_path / "test_cache.db")

    def test_set_and_get(self, db_path):
        cache = SQLiteCache(db_path=db_path)
        cache.set("k1", {"data": 1})
        assert cache.get("k1") == {"data": 1}

    def test_get_missing_returns_none(self, db_path):
        cache = SQLiteCache(db_path=db_path)
        assert cache.get("missing") is None

    def test_string_values(self, db_path):
        cache = SQLiteCache(db_path=db_path)
        cache.set("k1", "plain string")
        assert cache.get("k1") == "plain string"

    def test_expiration(self, db_path):
        cache = SQLiteCache(db_path=db_path, ttl_seconds=0.05)
        cache.set("k1", "value")
        assert cache.get("k1") == "value"
        time.sleep(0.06)
        assert cache.get("k1") is None

    def test_max_size_eviction(self, db_path):
        cache = SQLiteCache(db_path=db_path, max_size=2)
        cache.set("a", 1)
        time.sleep(0.01)
        cache.set("b", 2)
        time.sleep(0.01)
        cache.set("c", 3)  # should evict "a" (oldest)
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_overwrite_existing_key(self, db_path):
        cache = SQLiteCache(db_path=db_path)
        cache.set("k1", "old")
        cache.set("k1", "new")
        assert cache.get("k1") == "new"
        assert cache.size == 1

    def test_invalidate(self, db_path):
        cache = SQLiteCache(db_path=db_path)
        cache.set("k1", "value")
        cache.invalidate("k1")
        assert cache.get("k1") is None

    def test_clear(self, db_path):
        cache = SQLiteCache(db_path=db_path)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.size == 0

    def test_persistence_across_instances(self, db_path):
        cache1 = SQLiteCache(db_path=db_path)
        cache1.set("k1", {"persistent": True})

        cache2 = SQLiteCache(db_path=db_path)
        assert cache2.get("k1") == {"persistent": True}

    def test_stats(self, db_path):
        cache = SQLiteCache(db_path=db_path)
        cache.set("k1", "v1")
        cache.get("k1")  # hit
        cache.get("missing")  # miss
        stats = cache.stats
        assert stats["backend"] == "sqlite"
        assert stats["size"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    def test_graceful_fallback_bad_path(self):
        cache = SQLiteCache(db_path="/nonexistent/dir/cache.db")
        cache.set("k1", "v1")  # should not raise
        assert cache.get("k1") is None  # no-op
        assert cache.size == 0


# ======================================================================
# create_cache factory
# ======================================================================


class TestCreateCache:
    def test_default_memory(self):
        cache = create_cache()
        assert isinstance(cache, TTLCache)

    def test_persistent_sqlite(self, tmp_path):
        db_path = str(tmp_path / "factory_test.db")
        cache = create_cache(persistent=True, db_path=db_path)
        assert isinstance(cache, SQLiteCache)

    def test_custom_params(self):
        cache = create_cache(ttl_seconds=100, max_size=10)
        assert isinstance(cache, TTLCache)
        assert cache._ttl == 100
        assert cache._max_size == 10
