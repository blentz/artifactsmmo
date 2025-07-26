"""
Tests for tests/test_game_data/__init__.py test utilities

Tests the test utilities and fixtures provided by the game_data test module
to ensure proper functionality and 100% code coverage.
"""

from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

import pytest

from tests.test_game_data import (
    GameDataTestUtils,
    GameDataTestFixtures,
    APIClientWrapper,
    CooldownManager,
    TokenConfig,
    CacheManager,
    CacheMetadata,
    APIResponseFixtures,
    GameDataFixtures,
    ErrorResponseFixtures,
)


class TestGameDataTestUtils:
    """Test GameDataTestUtils functionality"""

    def test_create_mock_token_config_default(self):
        """Test creating mock TokenConfig with default token"""
        token_config = GameDataTestUtils.create_mock_token_config()
        
        assert isinstance(token_config, TokenConfig)
        assert len(token_config.token) == 32
        assert token_config.token == "a" * 32

    def test_create_mock_token_config_custom(self):
        """Test creating mock TokenConfig with custom token"""
        custom_token = "b" * 32
        token_config = GameDataTestUtils.create_mock_token_config(custom_token)
        
        assert isinstance(token_config, TokenConfig)
        assert token_config.token == custom_token

    def test_create_mock_api_client_authenticated(self):
        """Test creating authenticated mock API client"""
        mock_client = GameDataTestUtils.create_mock_api_client(authenticated=True)
        
        assert mock_client.is_authenticated is True
        assert mock_client.token_config is not None
        assert isinstance(mock_client.token_config, TokenConfig)
        assert hasattr(mock_client, 'cooldown_manager')

    def test_create_mock_api_client_unauthenticated(self):
        """Test creating unauthenticated mock API client"""
        mock_client = GameDataTestUtils.create_mock_api_client(authenticated=False)
        
        assert mock_client.is_authenticated is False
        assert mock_client.token_config is None
        assert hasattr(mock_client, 'cooldown_manager')

    def test_create_mock_cache_metadata_default(self):
        """Test creating mock cache metadata with defaults"""
        metadata = GameDataTestUtils.create_mock_cache_metadata()
        
        assert isinstance(metadata, CacheMetadata)
        assert isinstance(metadata.last_updated, datetime)
        assert metadata.cache_version == "1.0.0"
        assert metadata.data_sources == {}

    def test_create_mock_cache_metadata_custom(self):
        """Test creating mock cache metadata with custom values"""
        custom_time = datetime.now() - timedelta(hours=5)
        custom_version = "2.1.0"
        custom_sources = {"test": "data"}
        
        metadata = GameDataTestUtils.create_mock_cache_metadata(
            last_updated=custom_time,
            cache_version=custom_version,
            data_sources=custom_sources
        )
        
        assert metadata.last_updated == custom_time
        assert metadata.cache_version == custom_version
        assert metadata.data_sources == custom_sources

    def test_create_mock_cache_manager_default(self):
        """Test creating mock cache manager with defaults"""
        mock_cache = GameDataTestUtils.create_mock_cache_manager()
        
        assert mock_cache.cache_dir == "/tmp/test_cache"
        assert mock_cache.has_cached_data() is True
        assert hasattr(mock_cache, 'metadata')

    def test_create_mock_cache_manager_custom(self):
        """Test creating mock cache manager with custom values"""
        custom_dir = "/custom/cache/path"
        mock_cache = GameDataTestUtils.create_mock_cache_manager(
            cache_dir=custom_dir,
            has_cached_data=False
        )
        
        assert mock_cache.cache_dir == custom_dir
        assert mock_cache.has_cached_data() is False

    def test_create_mock_cooldown_manager_default(self):
        """Test creating mock cooldown manager with defaults"""
        mock_cooldown = GameDataTestUtils.create_mock_cooldown_manager()
        
        assert mock_cooldown.has_active_cooldowns() is False
        assert mock_cooldown.get_cooldown_remaining() == 0.0
        assert hasattr(mock_cooldown, 'update_cooldown')
        assert hasattr(mock_cooldown, 'wait_for_cooldown')

    def test_create_mock_cooldown_manager_custom(self):
        """Test creating mock cooldown manager with custom values"""
        mock_cooldown = GameDataTestUtils.create_mock_cooldown_manager(
            has_active_cooldowns=True,
            cooldown_remaining=30.5
        )
        
        assert mock_cooldown.has_active_cooldowns() is True
        assert mock_cooldown.get_cooldown_remaining() == 30.5


class TestGameDataTestFixtures:
    """Test GameDataTestFixtures functionality"""

    def test_get_test_character_data(self):
        """Test getting standardized test character data"""
        char_data = GameDataTestFixtures.get_test_character_data()
        
        assert isinstance(char_data, dict)
        assert "name" in char_data
        assert "level" in char_data
        assert char_data["name"] == "test_char"
        assert char_data["level"] == 5

    def test_get_test_game_data(self):
        """Test getting standardized test game data"""
        game_data = GameDataTestFixtures.get_test_game_data()
        
        assert isinstance(game_data, list)
        assert len(game_data) > 0
        # This should return items data from GameDataFixtures

    def test_get_test_error_response(self):
        """Test getting standardized test error response"""
        error_response = GameDataTestFixtures.get_test_error_response()
        
        assert hasattr(error_response, 'status_code')
        assert error_response.status_code == 429
        # This should return rate limit error from ErrorResponseFixtures

    def test_get_expired_cache_metadata(self):
        """Test getting expired cache metadata"""
        metadata = GameDataTestFixtures.get_expired_cache_metadata()
        
        assert isinstance(metadata, CacheMetadata)
        # Should be older than 24 hours
        time_diff = datetime.now() - metadata.last_updated
        assert time_diff.total_seconds() > (24 * 3600)

    def test_get_fresh_cache_metadata(self):
        """Test getting fresh cache metadata"""
        metadata = GameDataTestFixtures.get_fresh_cache_metadata()
        
        assert isinstance(metadata, CacheMetadata)
        # Should be less than 24 hours old
        time_diff = datetime.now() - metadata.last_updated
        assert time_diff.total_seconds() < (24 * 3600)


class TestGameDataTestImports:
    """Test that all imports work correctly"""

    def test_test_utils_class_import(self):
        """Test GameDataTestUtils class import"""
        assert GameDataTestUtils is not None
        assert hasattr(GameDataTestUtils, 'create_mock_token_config')
        assert hasattr(GameDataTestUtils, 'create_mock_api_client')
        assert hasattr(GameDataTestUtils, 'create_mock_cache_metadata')
        assert hasattr(GameDataTestUtils, 'create_mock_cache_manager')
        assert hasattr(GameDataTestUtils, 'create_mock_cooldown_manager')

    def test_test_fixtures_class_import(self):
        """Test GameDataTestFixtures class import"""
        assert GameDataTestFixtures is not None
        assert hasattr(GameDataTestFixtures, 'get_test_character_data')
        assert hasattr(GameDataTestFixtures, 'get_test_game_data')
        assert hasattr(GameDataTestFixtures, 'get_test_error_response')
        assert hasattr(GameDataTestFixtures, 'get_expired_cache_metadata')
        assert hasattr(GameDataTestFixtures, 'get_fresh_cache_metadata')

    def test_game_data_components_import(self):
        """Test game_data component imports"""
        assert APIClientWrapper is not None
        assert CooldownManager is not None
        assert TokenConfig is not None
        assert CacheManager is not None
        assert CacheMetadata is not None

    def test_fixture_classes_import(self):
        """Test fixture classes import"""
        assert APIResponseFixtures is not None
        assert GameDataFixtures is not None
        assert ErrorResponseFixtures is not None

    def test_testing_utilities_import(self):
        """Test testing utilities import"""
        assert Mock is not None
        assert AsyncMock is not None
        assert pytest is not None
        assert datetime is not None
        assert timedelta is not None


class TestGameDataTestUtilsEdgeCases:
    """Test edge cases and error handling"""

    def test_create_mock_token_config_none_token(self):
        """Test creating mock token config with None token explicitly"""
        token_config = GameDataTestUtils.create_mock_token_config(None)
        
        assert isinstance(token_config, TokenConfig)
        assert len(token_config.token) == 32

    def test_create_mock_cache_metadata_none_values(self):
        """Test creating mock cache metadata with None values"""
        metadata = GameDataTestUtils.create_mock_cache_metadata(
            last_updated=None,
            data_sources=None
        )
        
        assert isinstance(metadata.last_updated, datetime)
        assert metadata.data_sources == {}

    def test_create_mock_cache_manager_none_cache_dir(self):
        """Test creating mock cache manager with None cache_dir"""
        mock_cache = GameDataTestUtils.create_mock_cache_manager(cache_dir=None)
        
        assert mock_cache.cache_dir == "/tmp/test_cache"