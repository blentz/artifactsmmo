"""
YAML Data Management Module

Provides a unified interface for YAML-based data persistence with support for
complex API objects and enum serialization. Used throughout the system for
configuration, state management, and learned data storage.
"""

import logging
import os.path
from enum import Enum

from yaml import SafeDumper, safe_dump, safe_load


def enum_representer(dumper, data):
    """
    Custom YAML representer for Enum objects.
    
    Converts enum objects to their string values for YAML serialization,
    preventing serialization errors when API enums are stored in YAML files.
    
    Args:
        dumper: YAML dumper instance
        data: Enum object to represent
        
    Returns:
        YAML string representation of the enum value
    """
    return dumper.represent_str(str(data.value))


# Register the enum representer for all Enum subclasses with SafeDumper
SafeDumper.add_representer(Enum, enum_representer)

# Also try to handle specific API enum types that might get imported
try:
    from artifactsmmo_api_client.models.map_content_type import MapContentType
    SafeDumper.add_representer(MapContentType, enum_representer)
except ImportError:
    pass

try:
    from artifactsmmo_api_client.models.item_type import ItemType
    SafeDumper.add_representer(ItemType, enum_representer)
except ImportError:
    pass

try:
    from artifactsmmo_api_client.models.action_type import ActionType
    SafeDumper.add_representer(ActionType, enum_representer)
except ImportError:
    pass


class YamlData:
    """
    Base class for YAML-based data persistence and management.
    
    Provides a standardized interface for loading, saving, and manipulating
    YAML data files throughout the system. Handles complex API objects,
    enums, and nested data structures with automatic serialization.
    
    Features:
    - Automatic file creation if missing
    - Safe YAML loading/saving with error handling
    - Support for API enums and complex objects
    - Data validation and cleanup utilities
    - Logging integration for debugging
    """

    data = None
    filename = None
    _log = None

    def __init__(self, filename="data.yaml"):
        """
        Initialize YAML data manager.
        
        Args:
            filename: Path to YAML file for data storage
        """
        self._log = logging.getLogger()
        self.filename = filename
        self.data = {} if self.data is None else self.data
        
        # Load the YAML and extract just the 'data' portion if it exists
        loaded = self.load() or {}
        if 'data' in loaded:
            self.data.update(loaded['data'])
        else:
            self.data.update(loaded)
        self._log.debug(f"YamlData({self.filename}): {self.data}")

    def __repr__(self):
        return f"YamlData({self.filename}): {self.data}"

    def __iter__(self):
        yield "data", self.data

    def __getitem__(self, key):
        """
        Dictionary-style access to data.
        
        Args:
            key: Data key to retrieve
            
        Returns:
            Value associated with key
        """
        return self.data[key]

    def _load_yaml(self, filename):
        """
        Load YAML data from file with error handling.
        
        Creates the file if it doesn't exist, handles corrupted files,
        and provides fallback to empty dictionary on load errors.
        
        Args:
            filename: Path to YAML file to load
            
        Returns:
            dict: Loaded data or empty dict if file missing/corrupted
        """
        doc = {}
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
