"""retry_after_seconds: how long to wait after an HTTP 429."""

from collections.abc import Mapping

BASE_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 60.0


def retry_after_seconds(headers: Mapping[str, str], attempt: int) -> float:
    """Seconds to wait before retrying a throttled request.

    The API documents 429 but does not promise a Retry-After header, so an
    absent or non-numeric header falls back to capped exponential backoff. The
    HTTP-date form of Retry-After is deliberately not parsed: the fallback is
    already correct behaviour, and a second parsing path would be a second
    level of error handling for one failure.
    """
    raw = next(
        (v for k, v in headers.items() if k.lower() == "retry-after"), None
    )
    if raw is not None and raw.strip().isdigit():
        return float(raw.strip())
    return float(min(BASE_BACKOFF_SECONDS * (2**attempt), MAX_BACKOFF_SECONDS))
