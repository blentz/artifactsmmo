"""JSONL tracing for the GOAP player loop."""

import json
from abc import ABC, abstractmethod
from typing import IO


class Tracer(ABC):
    """Write per-cycle records for postmortem analysis."""

    @abstractmethod
    def write_cycle(self, record: dict) -> None:
        """Write one cycle's record."""

    @abstractmethod
    def close(self) -> None:
        """Release any resources."""


class NullTracer(Tracer):
    """No-op tracer — used when tracing is disabled."""

    def write_cycle(self, record: dict) -> None:
        return

    def close(self) -> None:
        return


class FileTracer(Tracer):
    """JSONL file tracer — one record per line, appended in order."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._fp: IO[str] | None = open(path, "a", encoding="utf-8")

    def write_cycle(self, record: dict) -> None:
        if self._fp is None:
            return
        self._fp.write(json.dumps(record, default=str) + "\n")
        self._fp.flush()

    def close(self) -> None:
        if self._fp is not None:
            self._fp.close()
            self._fp = None
