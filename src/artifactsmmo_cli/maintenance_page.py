"""Extract human-readable text from an HTML page (e.g. a server maintenance page)."""

import re
from html.parser import HTMLParser


class _ReadableTextParser(HTMLParser):
    """Collect the <title> and visible text, skipping <script>/<style> data."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._in_title = False
        self._title_parts: list[str] = []
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        if self._in_title:
            self._title_parts.append(data)
        else:
            self._text_parts.append(data)

    def get_text(self) -> str:
        title = re.sub(r"\s+", " ", "".join(self._title_parts)).strip()
        body = re.sub(r"\s+", " ", "".join(self._text_parts)).strip()
        return "\n".join(part for part in (title, body) if part)


def extract_readable_text(html: str) -> str:
    """Return title + visible text from `html`; "" when there is none."""
    parser = _ReadableTextParser()
    parser.feed(html)
    parser.close()
    return parser.get_text()
