"""
Cache Manager

This module manages game data caching using the existing yaml_data.py pattern.
It stores items, monsters, maps, resources, and NPCs using Pydantic models
for validation and maintains cache freshness for optimal performance.

The CacheManager reduces API calls by maintaining local copies of game data
while ensuring data integrity through Pydantic validation.
"""

import os
import shutil
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel

from ..lib.yaml_data import YamlData
from .api_client import APIClientWrapper


class CacheMetadata(BaseModel):
    """Metadata for cache management"""
    last_updated: datetime
    cache_version: str
    data_sources: dict[str, str]

    def is_stale(self, max_age_hours: int = 24) -> bool:
        """Check if cache data is stale.
        
        Parameters:
            max_age_hours: Maximum age in hours before cache is considered stale
            
        Return values:
            Boolean indicating whether cache data exceeds maximum age
            
        This method determines if cached data needs refreshing by comparing
        the last update time against the specified maximum age threshold,
        ensuring optimal balance between performance and data freshness.
        """
        age_limit = timedelta(hours=max_age_hours)
        current_time = datetime.now()
        age = current_time - self.last_updated
        return age > age_limit


class CacheManager:
    """Manages game data caching using yaml_data.py with Pydantic validation"""

    def __init__(self, api_client: APIClientWrapper, cache_dir: str = "data"):
        """Initialize CacheManager with API client and cache directory.
        
        Parameters:
            api_client: API client wrapper for fetching game data
            cache_dir: Directory path for storing cached YAML data files
            
        Return values:
            None (constructor)
            
        This constructor initializes the CacheManager with the API client
        for data fetching and sets up the cache directory structure for
        organized game data storage using the yaml_data.py pattern.
        """
        self._api_client = api_client
        self.cache_dir = cache_dir
        self.metadata_file = f"{cache_dir}/metadata.yaml"

    def _update_metadata(self, data_type: str) -> None:
        """Update metadata after caching data."""
        metadata = self.get_cache_metadata()
        metadata.last_updated = datetime.now()
        metadata.data_sources[data_type] = f"{self.cache_dir}/{data_type}.yaml"

        os.makedirs(self.cache_dir, exist_ok=True)
        yaml_data = YamlData(self.metadata_file)
        yaml_data.save(data=metadata.model_dump())

    async def refresh_all_cache(self) -> bool:
        """Refresh all cached game data from API.
        
        Parameters:
            None
            
        Return values:
            Boolean indicating whether all cache refresh operations succeeded
            
        This method updates all cached game data by fetching fresh information
        from the API including items, monsters, maps, resources, and NPCs,
        ensuring the AI player has current data for decision making.
        """
        try:
            await self.get_all_items(force_refresh=True)
            await self.get_all_monsters(force_refresh=True)
            await self.get_all_maps(force_refresh=True)
            await self.get_all_resources(force_refresh=True)
            await self.get_all_npcs(force_refresh=True)
            return True
        except Exception:
            return False

    async def get_all_items(self, force_refresh: bool = False) -> list['ItemSchema']:
        """Get all game items with caching.
        
        Parameters:
            force_refresh: Whether to bypass cache and fetch fresh data from API
            
        Return values:
            List of ItemSchema objects representing all available game items
            
        This method retrieves all game items either from cache or fresh from
        the API, providing the complete item database needed for crafting,
        trading, and equipment planning in the AI player system.
        """
        data_type = "items"

        if not force_refresh and self.is_cache_valid(data_type):
            cached_data = self.load_cache_data(data_type)
            if cached_data is not None:
                return cached_data

        fresh_data = await self._api_client.get_all_items()
        self.save_cache_data(data_type, fresh_data)
        self._update_metadata(data_type)
        return fresh_data

    async def get_all_monsters(self, force_refresh: bool = False) -> list['MonsterSchema']:
        """Get all monsters with caching.
        
        Parameters:
            force_refresh: Whether to bypass cache and fetch fresh data from API
            
        Return values:
            List of MonsterSchema objects representing all available monsters
            
        This method retrieves all monster data either from cache or fresh from
        the API, providing combat target information including levels, locations,
        and rewards for strategic combat planning.
        """
        data_type = "monsters"

        if not force_refresh and self.is_cache_valid(data_type):
            cached_data = self.load_cache_data(data_type)
            if cached_data is not None:
                return cached_data

        fresh_data = await self._api_client.get_all_monsters()
        self.save_cache_data(data_type, fresh_data)
        self._update_metadata(data_type)
        return fresh_data

    async def get_all_maps(self, force_refresh: bool = False) -> list['MapSchema']:
        """Get all maps with caching.
        
        Parameters:
            force_refresh: Whether to bypass cache and fetch fresh data from API
            
        Return values:
            List of MapSchema objects representing all game map information
            
        This method retrieves all map data either from cache or fresh from
        the API, providing location information, boundaries, and content
        data essential for pathfinding and exploration planning.
        """
        data_type = "maps"

        if not force_refresh and self.is_cache_valid(data_type):
            cached_data = self.load_cache_data(data_type)
            if cached_data is not None:
                return cached_data

        fresh_data = await self._api_client.get_all_maps()
        self.save_cache_data(data_type, fresh_data)
        self._update_metadata(data_type)
        return fresh_data

    async def get_all_resources(self, force_refresh: bool = False) -> list['ResourceSchema']:
        """Get all resources with caching.
        
        Parameters:
            force_refresh: Whether to bypass cache and fetch fresh data from API
            
        Return values:
            List of ResourceSchema objects representing all gatherable resources
            
        This method retrieves all resource data either from cache or fresh from
        the API, providing gathering location, skill requirements, and resource
        availability information for efficient collection planning.
        """
        data_type = "resources"

        if not force_refresh and self.is_cache_valid(data_type):
            cached_data = self.load_cache_data(data_type)
            if cached_data is not None:
                return cached_data

        fresh_data = await self._api_client.get_all_resources()
        self.save_cache_data(data_type, fresh_data)
        self._update_metadata(data_type)
        return fresh_data

    async def get_all_npcs(self, force_refresh: bool = False) -> list['NPCSchema']:
        """Get all NPCs with caching.
        
        Parameters:
            force_refresh: Whether to bypass cache and fetch fresh data from API
            
        Return values:
            List of NPCSchema objects representing all non-player characters
            
        This method retrieves all NPC data either from cache or fresh from
        the API, providing trader locations, available items, and services
        for economic planning and resource management.
        """
        data_type = "npcs"

        if not force_refresh and self.is_cache_valid(data_type):
            cached_data = self.load_cache_data(data_type)
            if cached_data is not None:
                return cached_data

        fresh_data = await self._api_client.get_all_npcs()
        self.save_cache_data(data_type, fresh_data)
        self._update_metadata(data_type)
        return fresh_data

    def save_cache_data(self, data_type: str, data: list[Any]) -> None:
        """Save data to YAML cache with Pydantic serialization.
        
        Parameters:
            data_type: String identifier for the type of data being cached
            data: List of data objects to serialize and save to cache
            
        Return values:
            None (writes to cache file)
            
        This method serializes game data using Pydantic models and saves it
        to YAML cache files using the yaml_data.py pattern, ensuring data
        integrity and enabling fast subsequent access.
        """
        cache_file = f"{self.cache_dir}/{data_type}.yaml"

        serialized_data = []
        for item in data:
            if hasattr(item, 'model_dump'):
                serialized_data.append(item.model_dump())
            elif hasattr(item, 'dict'):
                serialized_data.append(item.dict())
            else:
                serialized_data.append(item)

        self._save_yaml_data(cache_file, serialized_data)

    def load_cache_data(self, data_type: str) -> list[Any] | None:
        """Load data from YAML cache with Pydantic deserialization.
        
        Parameters:
            data_type: String identifier for the type of data to load from cache
            
        Return values:
            List of deserialized data objects, or None if cache doesn't exist
            
        This method loads and deserializes game data from YAML cache files
        using Pydantic validation, providing fast access to previously cached
        game information without requiring API calls.
        """
        cache_file = f"{self.cache_dir}/{data_type}.yaml"
        try:
            yaml_data = YamlData(cache_file)
            if yaml_data.data and "data" in yaml_data.data:
                return yaml_data.data["data"]
            return None
        except Exception:
            return None

    def is_cache_valid(self, data_type: str) -> bool:
        """Check if cached data is still valid.
        
        Parameters:
            data_type: String identifier for the type of cached data to validate
            
        Return values:
            Boolean indicating whether cached data is still within validity period
            
        This method validates cached data freshness by checking timestamps
        and age thresholds to determine if cached data can be used or if
        fresh data should be fetched from the API.
        """
        try:
            metadata = self.get_cache_metadata()
            if data_type not in metadata.data_sources:
                return False
            return not metadata.is_stale()
        except Exception:
            return False

    def get_cache_metadata(self) -> CacheMetadata:
        """Get cache metadata and freshness information.
        
        Parameters:
            None
            
        Return values:
            CacheMetadata object containing timestamps, sizes, and validity information
            
        This method retrieves comprehensive metadata about cached data including
        last update times, data sizes, and freshness status for monitoring
        and managing cache performance and validity.
        """
        try:
            yaml_data = YamlData(self.metadata_file)
            if yaml_data.data and "data" in yaml_data.data:
                return CacheMetadata(**yaml_data.data["data"])
        except Exception:
            pass

        return CacheMetadata(
            last_updated=datetime.now(),
            cache_version="1.0.0",
            data_sources={}
        )

    def clear_cache(self, data_type: str | None = None) -> None:
        """Clear specific or all cached data.
        
        Parameters:
            data_type: Optional specific data type to clear, or None to clear all cache
            
        Return values:
            None (modifies cache files)
            
        This method removes cached data either for a specific data type or
        all cached data if no type is specified, forcing fresh data retrieval
        from the API on subsequent requests.
        """
        if data_type is None:
            data_types = ["items", "monsters", "maps", "resources", "npcs"]
            for dt in data_types:
                cache_file = f"{self.cache_dir}/{dt}.yaml"
                if os.path.exists(cache_file):
                    os.remove(cache_file)

            if os.path.exists(self.metadata_file):
                os.remove(self.metadata_file)
        else:
            cache_file = f"{self.cache_dir}/{data_type}.yaml"
            if os.path.exists(cache_file):
                os.remove(cache_file)

    async def cache_game_data(self, data_type: str) -> None:
        """Cache specific game data type from API."""
        if data_type == "items":
            await self.get_all_items(force_refresh=True)
        elif data_type == "monsters":
            await self.get_all_monsters(force_refresh=True)
        elif data_type == "maps":
            await self.get_all_maps(force_refresh=True)
        elif data_type == "resources":
            await self.get_all_resources(force_refresh=True)
        elif data_type == "npcs":
            await self.get_all_npcs(force_refresh=True)
        else:
            raise ValueError(f"Unknown game data type: {data_type}")

    async def cache_character_data(self, character_name: str) -> None:
        """Cache character data from API."""
        character = await self._api_client.get_character(character_name)
        character_dict = character.model_dump() if hasattr(character, 'model_dump') else character.dict()

        cache_file = f"{self.cache_dir}/characters/{character_name}/data.yaml"
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        yaml_data = YamlData(cache_file)
        yaml_data.save(data=character_dict)

    def load_character_state(self, character_name: str) -> dict[str, Any] | None:
        """Load character state from cache."""
        cache_file = f"{self.cache_dir}/characters/{character_name}/state.yaml"
        try:
            yaml_data = YamlData(cache_file)
            if yaml_data.data and "data" in yaml_data.data:
                return yaml_data.data["data"]
            return None
        except Exception:
            return None

    def save_character_state(self, character_name: str, character_state: dict[str, Any]) -> None:
        """Save character state to cache."""
        cache_file = f"{self.cache_dir}/characters/{character_name}/state.yaml"
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        yaml_data = YamlData(cache_file)
        yaml_data.save(data=character_state)

    def get_cached_game_data(self, data_type: str) -> list[Any] | None:
        """Get cached game data of specific type."""
        return self.load_cache_data(data_type)

    def is_cache_fresh(self, data_type: str, max_age_hours: int = 24) -> bool:
        """Check if cache is fresh."""
        return self.is_cache_valid(data_type)

    async def refresh_cache(self, data_types: list[str] | None = None, force: bool = False) -> None:
        """Refresh cache with optional data type filtering."""
        if data_types is None:
            data_types = ["items", "monsters", "maps", "resources", "npcs"]

        for data_type in data_types:
            if force or not self.is_cache_fresh(data_type):
                await self.cache_game_data(data_type)

    def clear_character_cache(self, character_name: str) -> None:
        """Clear character-specific cache."""
        cache_dir = f"{self.cache_dir}/characters/{character_name}"
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)

    def get_cache_statistics(self) -> dict[str, Any]:
        """Get cache statistics."""
        stats = {
            "total_size": 0,
            "data_types": {}
        }

        data_types = ["items", "monsters", "maps", "resources", "npcs"]
        for data_type in data_types:
            cache_file = f"{self.cache_dir}/{data_type}.yaml"
            if os.path.exists(cache_file):
                size = os.path.getsize(cache_file)
                stats["total_size"] += size
                stats["data_types"][data_type] = {
                    "size": size,
                    "exists": True
                }
            else:
                stats["data_types"][data_type] = {
                    "size": 0,
                    "exists": False
                }

        return stats

    def validate_cached_data(self, data_type: str, data: list[Any] | None) -> bool:
        """Validate cached data structure."""
        if data is None:
            return False

        if not isinstance(data, list):
            return False

        if len(data) == 0:
            return True

        required_fields = {
            "items": ["code", "name"],
            "monsters": ["code", "name"],
            "maps": ["name"],
            "resources": ["code", "name"],
            "npcs": ["code", "name"]
        }

        if data_type not in required_fields:
            return False

        for item in data:
            if not isinstance(item, dict):
                return False
            for field in required_fields[data_type]:
                if field not in item:
                    return False

        return True

    def validate_character_state_data(self, data: dict[str, Any]) -> bool:
        """Validate character state data structure."""
        if not isinstance(data, dict):
            return False

        required_fields = ["character_level", "hp_current", "current_x", "current_y"]
        for field in required_fields:
            if field not in data:
                return False

            if field in ["character_level", "hp_current", "current_x", "current_y"]:
                if not isinstance(data[field], int) or data[field] < 0:
                    return False

        if "cooldown_ready" in data and not isinstance(data["cooldown_ready"], bool):
            return False

        return True

    def _save_yaml_data(self, file_path: str, data: Any) -> None:
        """Internal method to save YAML data."""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        yaml_data = YamlData(file_path)
        yaml_data.save(data=data)

    def _load_yaml_data(self, file_path: str) -> Any | None:
        """Internal method to load YAML data."""
        try:
            yaml_data = YamlData(file_path)
            if yaml_data.data and "data" in yaml_data.data:
                return yaml_data.data["data"]
            return None
        except Exception:
            return None

    def _get_cache_timestamp(self, file_path: str) -> datetime | None:
        """Get cache file timestamp."""
        if os.path.exists(file_path):
            timestamp = os.path.getmtime(file_path)
            return datetime.fromtimestamp(timestamp)
        return None

    def _get_cache_size(self, file_path: str) -> int:
        """Get cache file size."""
        if os.path.exists(file_path):
            return os.path.getsize(file_path)
        return 0

    def _delete_cache_file(self, file_path: str) -> None:
        """Delete cache file."""
        if os.path.exists(file_path):
            os.remove(file_path)

    def _delete_cache_directory(self, dir_path: str) -> None:
        """Delete cache directory."""
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
