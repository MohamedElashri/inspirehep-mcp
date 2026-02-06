"""Simple in-memory TTL cache with LRU eviction."""

import time
from collections import OrderedDict
from typing import Any


class TTLCache:
    """Thread-unsafe, async-unaware in-memory cache with TTL and max-size eviction.

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
    def stats(self) -> dict[str, int]:
        return {
            "size": self.size,
            "hits": self._hits,
            "misses": self._misses,
            "max_size": self._max_size,
        }
