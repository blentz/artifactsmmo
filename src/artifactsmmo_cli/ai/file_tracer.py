"""FileTracer: JSONL file tracer — one record per line, appended in order."""

import json
from typing import IO

from artifactsmmo_cli.ai.tracer import Tracer


class FileTracer(Tracer):
    """JSONL file tracer — one record per line, appended in order."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._fp: IO[str] | None = open(path, "a", encoding="utf-8")

    def write_cycle(self, record: dict[str, object]) -> None:
        if self._fp is None:
            return
        self._fp.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")
        self._fp.flush()

    def close(self) -> None:
        if self._fp is not None:
            self._fp.close()
            self._fp = None
