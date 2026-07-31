import httpx
import pytest

from artifactsmmo_cli.rate_limit_detector import detect_rate_limited_response
from artifactsmmo_cli.rate_limited_error import RateLimitedError

_REQ = httpx.Request("GET", "https://api.example.com/")


def _resp(status_code: int, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(status_code, headers=headers or {}, content=b"{}", request=_REQ)


def test_429_raises_rate_limited_error_carrying_the_headers():
    resp = _resp(429, {"Retry-After": "7"})
    with pytest.raises(RateLimitedError) as exc:
        detect_rate_limited_response(resp)
    assert exc.value.headers["Retry-After"] == "7"


def test_429_with_no_headers_still_raises():
    resp = _resp(429)
    with pytest.raises(RateLimitedError):
        detect_rate_limited_response(resp)


def test_a_200_response_is_a_noop():
    assert detect_rate_limited_response(_resp(200)) is None


def test_a_different_undocumented_status_is_not_mistaken_for_a_429():
    """This hook must not swallow every unrecognized status as a throttle —
    only 429 specifically."""
    assert detect_rate_limited_response(_resp(499)) is None


def test_rate_limited_error_is_an_httpx_http_error():
    """Deliberate: every existing `except httpx.HTTPError` transient-retry
    loop elsewhere in this codebase must absorb a 429 for free."""
    err = RateLimitedError({"Retry-After": "1"})
    assert isinstance(err, httpx.HTTPError)
    assert err.headers["Retry-After"] == "1"
