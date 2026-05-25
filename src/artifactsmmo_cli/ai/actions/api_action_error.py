"""Structured error for API error responses."""


class ApiActionError(RuntimeError):
    """API returned an error response; carries the HTTP/game status code."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"HTTP {code}: {message}")
