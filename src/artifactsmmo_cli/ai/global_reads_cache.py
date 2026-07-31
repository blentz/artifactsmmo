"""GlobalReadsCache: TTL memo over account-global (non-per-character) API reads."""

import time
from collections.abc import Callable
from typing import Any


class GlobalReadsCache:
    """Short-TTL memo for reads that are identical for every character.

    `active_events` and `raids` are account-global, but `_fetch_world_state`
    re-reads both every cycle. With five characters that is ten redundant
    data-bucket requests per cycle-round, which alone breaches the 2000/hour
    per-IP data ceiling at peak. Both change on a minutes-to-hours timescale,
    so a 60s TTL costs nothing semantically.

    A failed fetch is NOT cached: the exception propagates to the caller (which
    already has retry/backoff around these reads) and the next call re-fetches.
    """

    def __init__(
        self,
        ttl_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._entries: dict[str, tuple[float, Any]] = {}

    def get_or_fetch(self, key: str, fetch: Callable[[], Any]) -> Any:
        now = self._clock()
        entry = self._entries.get(key)
        if entry is not None and now - entry[0] < self._ttl:
            return entry[1]
        value = fetch()
        self._entries[key] = (now, value)
        return value
