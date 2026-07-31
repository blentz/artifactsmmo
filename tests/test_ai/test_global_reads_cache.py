"""GlobalReadsCache: TTL memo over account-global API reads."""

import pytest

from artifactsmmo_cli.ai.global_reads_cache import GlobalReadsCache


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_second_call_within_ttl_does_not_refetch():
    clock = _Clock()
    cache = GlobalReadsCache(ttl_seconds=60.0, clock=clock)
    calls = []

    def fetch():
        calls.append(1)
        return {"dragon": "2026-07-30T12:00:00Z"}

    assert cache.get_or_fetch("events", fetch) == {"dragon": "2026-07-30T12:00:00Z"}
    clock.now = 59.0
    assert cache.get_or_fetch("events", fetch) == {"dragon": "2026-07-30T12:00:00Z"}
    assert len(calls) == 1


def test_call_after_ttl_refetches():
    clock = _Clock()
    cache = GlobalReadsCache(ttl_seconds=60.0, clock=clock)
    calls = []

    def fetch():
        calls.append(len(calls))
        return len(calls)

    cache.get_or_fetch("raids", fetch)
    clock.now = 60.0
    cache.get_or_fetch("raids", fetch)
    assert len(calls) == 2


def test_distinct_keys_are_cached_independently():
    cache = GlobalReadsCache(ttl_seconds=60.0, clock=_Clock())
    assert cache.get_or_fetch("events", lambda: "E") == "E"
    assert cache.get_or_fetch("raids", lambda: "R") == "R"
    assert cache.get_or_fetch("events", lambda: "OTHER") == "E"


def test_fetch_exception_is_not_cached():
    clock = _Clock()
    cache = GlobalReadsCache(ttl_seconds=60.0, clock=clock)

    def boom():
        raise RuntimeError("transport failed")

    with pytest.raises(RuntimeError):
        cache.get_or_fetch("events", boom)
    assert cache.get_or_fetch("events", lambda: "recovered") == "recovered"
