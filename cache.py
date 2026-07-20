"""
ContextAR - In-memory TTL cache.

No Redis/diskcache dependency: this deploys as a single Railway service
(see README Deployment), so a process-local cache already gets full hit
value with zero extra infrastructure. If this ever moves to multiple
instances, hit rate degrades gracefully (each instance just misses more
often) rather than serving anything wrong.
"""

import threading
import time
from collections.abc import Callable, Hashable
from typing import TypeVar

T = TypeVar("T")


class TTLCache:
    """get_or_set() only — callers never need bare get/set, and this shape
    keeps the lock from being held during the (slow, network-bound) factory
    call."""

    def __init__(self, ttl_seconds: float, maxsize: int = 256):
        self._ttl = ttl_seconds
        self._maxsize = maxsize
        self._lock = threading.Lock()
        self._store: dict[Hashable, tuple[float, T]] = {}

    MISSING = object()

    def get(self, key: Hashable) -> T | object:
        """Returns the cached value, or the sentinel TTLCache.MISSING on a
        miss/expiry. Exposed (alongside set()) for callers that must not
        cache a failure result — get_or_set() would cache anything the
        factory returns, including a sentinel "failed" value."""
        now = time.monotonic()
        with self._lock:
            hit = self._store.get(key)
            if hit is not None and hit[0] > now:
                return hit[1]
        return self.MISSING

    def set(self, key: Hashable, value: T) -> None:
        now = time.monotonic()
        with self._lock:
            if len(self._store) >= self._maxsize and key not in self._store:
                oldest_key = min(self._store, key=lambda k: self._store[k][0])
                del self._store[oldest_key]
            self._store[key] = (now + self._ttl, value)

    def get_or_set(self, key: Hashable, factory: Callable[[], T]) -> T:
        cached = self.get(key)
        if cached is not self.MISSING:
            return cached
        value = factory()
        self.set(key, value)
        return value
