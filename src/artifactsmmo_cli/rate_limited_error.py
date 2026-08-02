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

    The "every existing retry loop absorbs it for free" premise holds only
    where such a loop EXISTS. `GameData.load` has none — its `_fetch_*`
    helpers call the generated client bare — so the startup game-data load
    carries the codebase's only OTHER `except RateLimitedError`, in
    `GameData.load` itself. The two are disjoint: `load`'s callers are all
    pre-loop startup (`GamePlayer._initialize`, `play._run_with_tui`,
    `MultiRun.run`), and nothing reachable from `_execute` calls it.
    """

    def __init__(self, headers: Mapping[str, str]) -> None:
        super().__init__("HTTP 429: rate limited")
        self.headers = headers
