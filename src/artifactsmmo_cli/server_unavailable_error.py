"""Raised when the API returns a non-JSON HTML page (server down / maintenance)."""


class ServerUnavailableError(RuntimeError):
    """The game API returned an HTML page where JSON was expected.

    Carries the human-readable text extracted from that page and the request
    URL so a single top-level handler can show the user what the server said
    and exit cleanly. A RuntimeError (not a ValueError) so the per-command
    ``except (ValueError, ...)`` handlers do not swallow it.
    """

    def __init__(self, message: str, url: str) -> None:
        super().__init__(message)
        self.page_text = message
        self.url = url
