"""Retry-After parsing with an exponential fallback."""

from artifactsmmo_cli.utils.retry_after import retry_after_seconds


def test_a_numeric_retry_after_header_is_honored():
    assert retry_after_seconds({"Retry-After": "12"}, attempt=0) == 12.0


def test_the_header_is_matched_case_insensitively():
    assert retry_after_seconds({"retry-after": "3"}, attempt=0) == 3.0


def test_a_missing_header_falls_back_to_exponential_backoff():
    """The API documents 429 but promises no Retry-After header."""
    assert [retry_after_seconds({}, attempt=n) for n in range(3)] == [1.0, 2.0, 4.0]


def test_an_unparseable_header_falls_back_to_backoff():
    assert retry_after_seconds({"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}, attempt=1) == 2.0


def test_the_fallback_is_capped():
    assert retry_after_seconds({}, attempt=20) <= 60.0
