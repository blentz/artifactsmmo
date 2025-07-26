""" yaml_data module """

import logging
import os.path
from collections.abc import Iterator
from typing import Any

from yaml import safe_dump, safe_load


class YamlData:
    """Data stored in YAML."""

    data: dict[str, Any] | None
    filename: str
    _log: logging.Logger

    def __init__(self, filename: str = "data.yaml") -> None:
        self._log = logging.getLogger()
        self.filename = filename
        self.data = self.load()
        self._log.debug(f"YamlData({self.filename}): {self.data}")

    def __repr__(self) -> str:
        return f"YamlData({self.filename}): {self.data}"

    def __iter__(self) -> Iterator[tuple[str, dict[str, Any] | None]]:
        yield "data", self.data

    def __getitem__(self, key: str) -> Any:
        return self.data[key]  # type: ignore

    def _load_yaml(self, filename: str) -> dict[str, Any]:
        doc: dict[str, Any] = {}
        if not os.path.exists(filename):
            self._log.debug(f"YamlData({filename}): file not found. creating...")
            self._save_yaml(doc)
            return doc

        with open(filename) as fn:
            self._log.debug(f"YamlData({filename}): file found. loading...")
            doc = safe_load(fn)
            if doc:
                return doc
            return {}

    def _save_yaml(self, data: dict[str, Any]) -> None:
        self._log.debug(f"YamlData({self.filename}): saving...")
        with open(self.filename, "w") as fn:
            safe_dump(data, fn)

    def load(self) -> dict[str, Any]:
        """public interface for loading data from disk"""
        return self._load_yaml(self.filename)

    def save(self, **kwargs: Any) -> None:
        """public interface for saving data to disk"""
        if not self.data or "data" not in self.data:
            self._save_yaml({"data": self.data, **kwargs})
        else:
            self._save_yaml({**self.data, **kwargs})
