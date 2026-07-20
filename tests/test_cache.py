import time

from cache import TTLCache


def test_get_or_set_calls_factory_once_on_miss():
    cache = TTLCache(ttl_seconds=60)
    calls = []

    def factory():
        calls.append(1)
        return "value"

    assert cache.get_or_set("k", factory) == "value"
    assert cache.get_or_set("k", factory) == "value"
    assert len(calls) == 1


def test_get_returns_missing_sentinel_on_miss():
    cache = TTLCache(ttl_seconds=60)
    assert cache.get("nope") is TTLCache.MISSING


def test_entry_expires_after_ttl():
    cache = TTLCache(ttl_seconds=0.05)
    cache.set("k", "v")
    assert cache.get("k") == "v"
    time.sleep(0.08)
    assert cache.get("k") is TTLCache.MISSING


def test_maxsize_evicts_oldest_entry():
    cache = TTLCache(ttl_seconds=60, maxsize=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)  # should evict "a", the earliest-expiring entry
    assert cache.get("a") is TTLCache.MISSING
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_maxsize_not_exceeded_when_updating_existing_key():
    cache = TTLCache(ttl_seconds=60, maxsize=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("a", 99)  # update, not an insert — must not evict "b"
    assert cache.get("a") == 99
    assert cache.get("b") == 2
