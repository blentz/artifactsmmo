"""
Game data component tests

Tests for API client integration, cooldown management, cache management,
and game data synchronization with the ArtifactsMMO API.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, Mock

import pytest

from src.game_data.api_client import APIClientWrapper, CooldownManager, TokenConfig
from src.game_data.cache_manager import CacheManager, CacheMetadata
from tests.fixtures.api_responses import APIResponseFixtures, ErrorResponseFixtures, GameDataFixtures


class GameDataTestUtils:
    """Test utilities specific to game_data component testing"""

    @staticmethod
    def create_mock_token_config(token: str | None = None) -> TokenConfig:
        """Create a mock TokenConfig for testing"""
        if token is None:
            token = "a" * 32  # Valid 32-character token
        return TokenConfig(token=token)

    @staticmethod
    def create_mock_api_client(authenticated: bool = True) -> Mock:
        """Create a mock APIClientWrapper for testing"""
        mock_client = Mock(spec=APIClientWrapper)
        mock_client.is_authenticated = authenticated
        mock_client.token_config = GameDataTestUtils.create_mock_token_config() if authenticated else None
        mock_client.cooldown_manager = Mock(spec=CooldownManager)
        return mock_client

    @staticmethod
    def create_mock_cache_metadata(
        last_updated: datetime | None = None,
        cache_version: str = "1.0.0",
        data_sources: dict[str, Any] | None = None
    ) -> CacheMetadata:
        """Create mock cache metadata for testing"""
        if last_updated is None:
            last_updated = datetime.now()
        if data_sources is None:
            data_sources = {}

        return CacheMetadata(
            last_updated=last_updated,
            cache_version=cache_version,
            data_sources=data_sources
        )

    @staticmethod
    def create_mock_cache_manager(
        cache_dir: str | None = None,
        has_cached_data: bool = True
    ) -> Mock:
        """Create a mock CacheManager for testing"""
        mock_cache = Mock(spec=CacheManager)
        mock_cache.cache_dir = cache_dir or "/tmp/test_cache"
        mock_cache.has_cached_data = Mock(return_value=has_cached_data)
        mock_cache.metadata = GameDataTestUtils.create_mock_cache_metadata()
        return mock_cache

    @staticmethod
    def create_mock_cooldown_manager(
        has_active_cooldowns: bool = False,
        cooldown_remaining: float = 0.0
    ) -> Mock:
        """Create a mock CooldownManager for testing"""
        mock_cooldown = Mock(spec=CooldownManager)
        mock_cooldown.has_active_cooldowns = Mock(return_value=has_active_cooldowns)
        mock_cooldown.get_cooldown_remaining = Mock(return_value=cooldown_remaining)
        mock_cooldown.update_cooldown = Mock()
        mock_cooldown.wait_for_cooldown = AsyncMock()
        return mock_cooldown


class GameDataTestFixtures:
    """Test fixtures specific to game_data component"""

    @staticmethod
    def get_test_character_data() -> dict[str, Any]:
        """Get standardized test character data"""
        response_mock = APIResponseFixtures.get_character_response("test_char", level=5)
        # Extract the character data from the mock response
        return {
            "name": "test_char",
            "level": 5,
            "xp": 1250,
            "max_xp": 1500,
            "gold": 500,
            "hp": 100,
            "max_hp": 120,
            "x": 15,
            "y": 20,
            "cooldown": 0,
            "cooldown_expiration": None,
            "server": "1",
            "account": "test_account",
            "skin": "men1"
        }

    @staticmethod
    def get_test_game_data() -> list[dict[str, Any]]:
        """Get standardized test game data"""
        return GameDataFixtures.get_items_data()

    @staticmethod
    def get_test_error_response() -> Mock:
        """Get standardized test error response"""
        return ErrorResponseFixtures.get_rate_limit_error()

    @staticmethod
    def get_expired_cache_metadata() -> CacheMetadata:
        """Get cache metadata that is expired for testing"""
        return GameDataTestUtils.create_mock_cache_metadata(
            last_updated=datetime.now() - timedelta(hours=25)
        )

    @staticmethod
    def get_fresh_cache_metadata() -> CacheMetadata:
        """Get cache metadata that is fresh for testing"""
        return GameDataTestUtils.create_mock_cache_metadata(
            last_updated=datetime.now() - timedelta(hours=1)
        )


# Export test utilities and fixtures for use in test modules
__all__ = [
    "GameDataTestUtils",
    "GameDataTestFixtures",
    # Re-export common testing imports
    "Mock",
    "AsyncMock",
    "pytest",
    "datetime",
    "timedelta",
    # Re-export game_data components for testing
    "APIClientWrapper",
    "CooldownManager",
    "TokenConfig",
    "CacheManager",
    "CacheMetadata",
    # Re-export fixtures
    "APIResponseFixtures",
    "GameDataFixtures",
    "ErrorResponseFixtures",
]
