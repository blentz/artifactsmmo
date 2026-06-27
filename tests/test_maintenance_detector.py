import httpx
import pytest

from artifactsmmo_cli.maintenance_detector import detect_maintenance_response
from artifactsmmo_cli.server_unavailable_error import ServerUnavailableError

_REQ = httpx.Request("GET", "https://api.example.com/")


def _resp(content_type: str, body: bytes) -> httpx.Response:
    return httpx.Response(200, headers={"content-type": content_type}, content=body, request=_REQ)


def test_html_body_raises_with_extracted_text():
    resp = _resp("text/html", b"<title>Maintenance</title><body>Back soon</body>")
    with pytest.raises(ServerUnavailableError) as exc:
        detect_maintenance_response(resp)
    assert exc.value.page_text == "Maintenance\nBack soon"
    assert exc.value.url == "https://api.example.com/"


def test_html_with_charset_suffix_raises():
    resp = _resp("text/html; charset=utf-8", b"<body>Down</body>")
    with pytest.raises(ServerUnavailableError):
        detect_maintenance_response(resp)


def test_json_body_is_noop():
    resp = _resp("application/json", b'{"data": {"max_level": 50}}')
    assert detect_maintenance_response(resp) is None


def test_missing_content_type_is_noop():
    resp = httpx.Response(200, content=b'{"ok": true}', request=_REQ)
    assert detect_maintenance_response(resp) is None
