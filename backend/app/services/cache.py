"""Small in-memory cache with a time-to-live.

Open Food Facts allows 15 product reads per minute per IP, so repeat scans of the
same product must not each cost a request. The cache is per process; it is meant to
be replaced by a PostgreSQL product cache later.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Generic, TypeVar

V = TypeVar("V")


class TTLCache(Generic[V]):
    def __init__(
        self,
        ttl_seconds: float,
        max_entries: int = 1000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._entries: dict[str, tuple[float, V]] = {}
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self._ttl > 0 and self._max_entries > 0

    def get(self, key: str) -> V | None:
        if not self.enabled:
            return None
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if self._clock() >= expires_at:
                del self._entries[key]
                return None
            return value

    def set(self, key: str, value: V) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._entries.pop(key, None)  # re-inserting moves the key to the newest position
            while len(self._entries) >= self._max_entries:
                del self._entries[next(iter(self._entries))]  # oldest insertion
            self._entries[key] = (self._clock() + self._ttl, value)
