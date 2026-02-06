"""In-memory TTL cache with LRU eviction and optional SQLite persistence."""

import json
import logging
import sqlite3
import time
from collections import OrderedDict
from typing import Any

logger = logging.getLogger(__name__)


class TTLCache:
    """In-memory cache with TTL and max-size eviction.

    Good enough for a single-process MCP server. Keys are strings,
    values are arbitrary objects.
    """

    def __init__(self, ttl_seconds: float = 86400, max_size: int = 512) -> None:
        self._ttl = ttl_seconds
        self._max_size = max_size
        # OrderedDict gives us LRU ordering for free
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str) -> Any | None:
        """Return cached value or None if missing / expired."""
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None

        ts, value = entry
        if time.monotonic() - ts > self._ttl:
            # Expired – evict
            del self._store[key]
            self._misses += 1
            return None

        # Move to end (most-recently used)
        self._store.move_to_end(key)
        self._hits += 1
        return value

    def set(self, key: str, value: Any) -> None:
        """Store a value, evicting the oldest entry if at capacity."""
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (time.monotonic(), value)
        # Evict LRU entries if over capacity
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)
            self._evictions += 1

    def invalidate(self, key: str) -> None:
        """Remove a specific key from the cache."""
        self._store.pop(key, None)

    def clear(self) -> None:
        """Remove all entries."""
        self._store.clear()

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        return len(self._store)

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return (self._hits / total * 100) if total > 0 else 0.0

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "backend": "memory",
            "size": self.size,
            "max_size": self._max_size,
            "ttl_seconds": self._ttl,
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "hit_rate_percent": round(self.hit_rate, 1),
        }


class SQLiteCache:
    """Persistent cache backed by SQLite with TTL expiration.

    Values are JSON-serialised. Falls back gracefully if the DB
    is unavailable (logs a warning and acts as a no-op cache).
    """

    def __init__(
        self,
        db_path: str = "inspirehep_cache.db",
        ttl_seconds: float = 86400,
        max_size: int = 2048,
    ) -> None:
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._db: sqlite3.Connection | None = None

        try:
            self._db = sqlite3.connect(db_path, check_same_thread=False)
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    ts    REAL NOT NULL
                )
                """
            )
            self._db.execute("CREATE INDEX IF NOT EXISTS idx_cache_ts ON cache(ts)")
            self._db.commit()
            logger.info("SQLite cache opened: %s", db_path)
        except sqlite3.Error as exc:
            logger.warning("Failed to open SQLite cache at %s: %s", db_path, exc)
            self._db = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str) -> Any | None:
        if self._db is None:
            self._misses += 1
            return None
        try:
            row = self._db.execute(
                "SELECT value, ts FROM cache WHERE key = ?", (key,)
            ).fetchone()
        except sqlite3.Error:
            self._misses += 1
            return None

        if row is None:
            self._misses += 1
            return None

        value_str, ts = row
        if time.time() - ts > self._ttl:
            # Expired
            try:
                self._db.execute("DELETE FROM cache WHERE key = ?", (key,))
                self._db.commit()
            except sqlite3.Error:
                pass
            self._misses += 1
            return None

        self._hits += 1
        try:
            return json.loads(value_str)
        except (json.JSONDecodeError, TypeError):
            return value_str

    def set(self, key: str, value: Any) -> None:
        if self._db is None:
            return
        try:
            value_str = json.dumps(value) if not isinstance(value, str) else value
            self._db.execute(
                "INSERT OR REPLACE INTO cache (key, value, ts) VALUES (?, ?, ?)",
                (key, value_str, time.time()),
            )
            self._db.commit()
            self._enforce_max_size()
        except (sqlite3.Error, TypeError) as exc:
            logger.debug("SQLite cache set failed: %s", exc)

    def invalidate(self, key: str) -> None:
        if self._db is None:
            return
        try:
            self._db.execute("DELETE FROM cache WHERE key = ?", (key,))
            self._db.commit()
        except sqlite3.Error:
            pass

    def clear(self) -> None:
        if self._db is None:
            return
        try:
            self._db.execute("DELETE FROM cache")
            self._db.commit()
        except sqlite3.Error:
            pass

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _enforce_max_size(self) -> None:
        """Evict oldest entries if over capacity."""
        if self._db is None:
            return
        try:
            count = self._db.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            if count > self._max_size:
                excess = count - self._max_size
                self._db.execute(
                    "DELETE FROM cache WHERE key IN "
                    "(SELECT key FROM cache ORDER BY ts ASC LIMIT ?)",
                    (excess,),
                )
                self._db.commit()
                self._evictions += excess
        except sqlite3.Error:
            pass

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        if self._db is None:
            return 0
        try:
            return self._db.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
        except sqlite3.Error:
            return 0

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return (self._hits / total * 100) if total > 0 else 0.0

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "backend": "sqlite",
            "size": self.size,
            "max_size": self._max_size,
            "ttl_seconds": self._ttl,
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "hit_rate_percent": round(self.hit_rate, 1),
        }


def create_cache(
    *,
    persistent: bool = False,
    db_path: str = "inspirehep_cache.db",
    ttl_seconds: float = 86400,
    max_size: int = 512,
) -> TTLCache | SQLiteCache:
    """Factory function to create the appropriate cache backend."""
    if persistent:
        return SQLiteCache(db_path=db_path, ttl_seconds=ttl_seconds, max_size=max_size)
    return TTLCache(ttl_seconds=ttl_seconds, max_size=max_size)
