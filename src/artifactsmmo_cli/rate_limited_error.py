"""Raised when the API throttles a request (HTTP 429)."""

from collections.abc import Mapping

import httpx


class RateLimitedError(httpx.HTTPError):
    """The game API rejected this request with HTTP 429 (Too Many Requests).

    A subclass of `httpx.HTTPError` — not `RuntimeError` — so every existing
    ``except httpx.HTTPError`` transient-retry loop already in this codebase
    (`GamePlayer._fetch_world_state`, `_fetch_active_events`, `_fetch_raids`,
    ...) treats a 429 as a transient condition to retry with zero new code,
    exactly as it already does for a timeout or connection reset. Carries
    the raw response headers so callers that want the `Retry-After` value
    can read it (see `artifactsmmo_cli.utils.retry_after.retry_after_seconds`);
    `GamePlayer._execute` adds ONE specific `except RateLimitedError` ahead
    of the generic `httpx.HTTPError` handling, for the action-dispatch path
    only, to honor that header (or fall back to capped backoff) and report a
    distinguishable cycle outcome instead of a bare network-error label.
    """

    def __init__(self, headers: Mapping[str, str]) -> None:
        super().__init__("HTTP 429: rate limited")
        self.headers = headers
