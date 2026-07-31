"""httpx response event-hook: detect an HTTP 429 (rate-limited) response."""

import httpx

from artifactsmmo_cli.ai.constants import ERROR_CODE_RATE_LIMITED
from artifactsmmo_cli.rate_limited_error import RateLimitedError


def detect_rate_limited_response(response: httpx.Response) -> None:
    """Raise RateLimitedError when the API returns HTTP 429.

    Installed as an httpx ``response`` event-hook (alongside
    `maintenance_detector.detect_maintenance_response`), this fires for
    every request this process makes, before the generated OpenAPI client
    parses the body. That generated client's `_parse_response` only
    recognizes status codes the OpenAPI spec documents per endpoint; 429 is
    undocumented for every endpoint this project calls (action and data
    alike), so with `raise_on_unexpected_status=False` (client_manager.py)
    `sync()` would otherwise silently collapse a 429 to `None`, discarding
    both the status code and the headers `Retry-After` lives in. This hook
    is the only point in the request lifecycle that still holds the raw
    `httpx.Response`, so it is the one place 429 can actually be detected.
    """
    if response.status_code == ERROR_CODE_RATE_LIMITED:
        raise RateLimitedError(response.headers)
