"""
Game Data Module

Provides API integration and game data management for the AI player system.
Includes API client wrapper, game state caching, and cooldown management
for interaction with the ArtifactsMMO game server.
"""

from .api_client import (
    APIClientWrapper,
    CooldownManager,
    TokenConfig,
)
from .cache_manager import (
    CacheManager,
    CacheMetadata,
)

__all__ = [
    "TokenConfig",
    "APIClientWrapper",
    "CooldownManager",
    "CacheMetadata",
    "CacheManager",
]

__version__ = "2.0.0"
