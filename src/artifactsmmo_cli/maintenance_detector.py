"""httpx response event-hook: detect a server maintenance HTML page."""

import httpx

from artifactsmmo_cli.maintenance_page import extract_readable_text
from artifactsmmo_cli.server_unavailable_error import ServerUnavailableError


def detect_maintenance_response(response: httpx.Response) -> None:
    """Raise ServerUnavailableError when the API returns a text/html body.

    Installed as an httpx ``response`` event-hook, this fires before the
    generated client parses the body as JSON, so a non-JSON maintenance page
    surfaces as a clean typed error instead of a raw JSONDecodeError.
    """
    content_type = response.headers.get("content-type", "")
    if not content_type.lower().startswith("text/html"):
        return
    response.read()
    raise ServerUnavailableError(
        extract_readable_text(response.text), url=str(response.request.url)
    )
