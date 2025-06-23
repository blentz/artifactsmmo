""" yaml_data module """

import logging
import os.path

from yaml import safe_load, safe_dump

class YamlData:
    """Data stored in YAML."""

    data = None
    filename = None
    _log = None

    def __init__(self, filename="data.yaml"):
        self._log = logging.getLogger()
        self.filename = filename
        self.data = {} if self.data is None else self.data
        self.data.update(self.load() or {})
        self._log.debug(f"YamlData({self.filename}): {self.data}")

    def __repr__(self):
        return f"YamlData({self.filename}): {self.data}"

    def __iter__(self):
        yield "data", self.data

    def __getitem__(self, key):
        return self.data[key]

    def _load_yaml(self, filename):
        doc = {}
        if not os.path.exists(filename):
            self._log.debug(f"YamlData({filename}): file not found. creating...")
            self._save_yaml(doc)
            return doc

        with open(filename, "r") as fn:
            self._log.debug(f"YamlData({filename}): file found. loading...")
            doc = safe_load(fn)
            if doc:
                return doc
            return {}

    def _save_yaml(self, data):
        self._log.debug(f"YamlData({self.filename}): saving...")
        with open(self.filename, "w") as fn:
            safe_dump(data, fn)

    def load(self):
        """public interface for loading data from disk"""
        return self._load_yaml(self.filename)

    def save(self, planners=None, **kwargs):
        """public interface for saving data to disk"""
        data = {"data": self.data}
        if planners is not None:
            data["planners"] = planners

        # Add any other kwargs
        data.update(kwargs)

        self._save_yaml(data)
