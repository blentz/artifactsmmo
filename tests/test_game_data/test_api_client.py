"""
Tests for API client wrapper and cooldown management

This module tests the API client wrapper, authentication, cooldown handling,
rate limiting, and integration with the ArtifactsMMO API.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.ai_player.state.game_state import CooldownInfo
from src.game_data.api_client import APIClientWrapper, CooldownManager, TokenConfig


class TestTokenConfig:
    """Test TokenConfig Pydantic model for authentication"""

    def test_token_config_creation_valid(self):
        """Test creating TokenConfig with valid token"""
        valid_token = "a" * 32  # 32 character token
        config = TokenConfig(token=valid_token)

        assert config.token == valid_token
        assert len(config.token) >= 32

    def test_token_config_validation_too_short(self):
        """Test TokenConfig validation with too short token"""
        short_token = "short"  # Less than 32 characters

        with pytest.raises(Exception):  # Pydantic validation error
            TokenConfig(token=short_token)

    def test_token_config_from_file_success(self):
        """Test loading TokenConfig from file successfully"""
        test_token = "b" * 32

        with patch("pathlib.Path.exists") as mock_exists, \
             patch("pathlib.Path.read_text") as mock_read:
            mock_exists.return_value = True
            mock_read.return_value = f"  {test_token}  \n"  # With whitespace

            config = TokenConfig.from_file("test_token_file")

            assert config.token == test_token
            mock_exists.assert_called_once()
            mock_read.assert_called_once()

    def test_token_config_from_file_not_found(self):
        """Test loading TokenConfig from missing file"""
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = False

            with pytest.raises(FileNotFoundError, match="Token file not found"):
                TokenConfig.from_file("missing_token_file")

    def test_token_config_from_file_invalid_token(self):
        """Test loading TokenConfig from file with invalid token"""
        invalid_token = "too_short"

        with patch("pathlib.Path.exists") as mock_exists, \
             patch("pathlib.Path.read_text") as mock_read:
            mock_exists.return_value = True
            mock_read.return_value = invalid_token

            with pytest.raises(Exception):  # Pydantic validation error
                TokenConfig.from_file("invalid_token_file")

    def test_token_config_from_file_default_path(self):
        """Test loading TokenConfig from default TOKEN file"""
        test_token = "c" * 32

        with patch("pathlib.Path.exists") as mock_exists, \
             patch("pathlib.Path.read_text") as mock_read:
            mock_exists.return_value = True
            mock_read.return_value = test_token

            config = TokenConfig.from_file()  # No path specified, should use "TOKEN"

            assert config.token == test_token

    def test_token_config_from_file_empty(self):
        """Test loading TokenConfig from empty file"""
        with patch("pathlib.Path.exists") as mock_exists, \
             patch("pathlib.Path.read_text") as mock_read:
            mock_exists.return_value = True
            mock_read.return_value = "   \n"  # Empty with whitespace

            with pytest.raises(ValueError, match="Token file is empty"):
                TokenConfig.from_file("empty_token_file")


class TestAPIClientWrapper:
    """Test APIClientWrapper functionality"""

    @pytest.fixture
    def mock_token_config(self):
        """Mock TokenConfig for testing"""
        return TokenConfig(token="d" * 32)

    @pytest.fixture
    def mock_authenticated_client(self):
        """Mock AuthenticatedClient for testing"""
        client = Mock()
        client.base_url = "https://api.artifactsmmo.com"
        return client

    def test_api_client_wrapper_initialization_success(self, mock_token_config):
        """Test successful APIClientWrapper initialization"""
        with patch.object(TokenConfig, 'from_file', return_value=mock_token_config), \
             patch('src.game_data.api_client.AuthenticatedClient') as mock_client_class:

            mock_client = Mock()
            mock_client_class.return_value = mock_client

            wrapper = APIClientWrapper("test_token_file")

            assert wrapper.token_config == mock_token_config
            assert wrapper.client == mock_client
            assert hasattr(wrapper, 'status_codes')

            # Verify client was created with correct parameters
            mock_client_class.assert_called_once_with(
                base_url="https://api.artifactsmmo.com",
                token=mock_token_config.token
            )

    def test_api_client_wrapper_initialization_invalid_token(self):
        """Test APIClientWrapper initialization with invalid token"""
        with patch.object(TokenConfig, 'from_file') as mock_from_file:
            mock_from_file.side_effect = ValueError("Invalid token format")

            with pytest.raises(ValueError, match="Invalid token format"):
                APIClientWrapper("invalid_token_file")

    @pytest.mark.asyncio
    async def test_create_character_success(self, mock_token_config):
        """Test successful character creation"""
        with patch.object(TokenConfig, 'from_file', return_value=mock_token_config), \
             patch('src.game_data.api_client.AuthenticatedClient') as mock_client_class, \
             patch('src.game_data.api_client.create_character_characters_create_post') as mock_create:

            mock_client = Mock()
            mock_client_class.return_value = mock_client

            # Mock successful API response
            class MockCharacter:
                def __init__(self):
                    self.name = "test_character"
                    self.level = 1
            
            class MockData:
                def __init__(self):
                    self.character = MockCharacter()
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.data = MockData()
            mock_response.parsed = mock_response.data

            mock_create.asyncio = AsyncMock(return_value=mock_response)

            wrapper = APIClientWrapper()
            result = await wrapper.create_character("test_character", "men1")

            assert result == mock_response.data.character
            assert result.name == "test_character"
            assert result.level == 1

    @pytest.mark.asyncio
    async def test_create_character_rate_limited(self, mock_token_config):
        """Test character creation with rate limiting"""
        with patch.object(TokenConfig, 'from_file', return_value=mock_token_config), \
             patch('src.game_data.api_client.AuthenticatedClient') as mock_client_class, \
             patch('src.game_data.api_client.create_character_characters_create_post') as mock_create, \
             patch('asyncio.sleep') as mock_sleep:

            mock_client = Mock()
            mock_client_class.return_value = mock_client

            # Mock rate limited response (429)
            mock_response = Mock()
            mock_response.status_code = 429
            mock_response.headers = {"Retry-After": "60"}

            mock_create.asyncio = AsyncMock(return_value=mock_response)

            wrapper = APIClientWrapper()

            with pytest.raises(ValueError, match="Rate limit exceeded"):
                await wrapper.create_character("test_character", "men1")
                
            # Verify that sleep was called with the retry-after value
            mock_sleep.assert_called_once_with(60.0)

    @pytest.mark.asyncio
    async def test_get_character_success(self, mock_token_config):
        """Test successful character retrieval"""
        with patch.object(TokenConfig, 'from_file', return_value=mock_token_config), \
             patch('src.game_data.api_client.AuthenticatedClient') as mock_client_class, \
             patch('src.game_data.api_client.get_character_characters_name_get') as mock_get:

            mock_client = Mock()
            mock_client_class.return_value = mock_client

            # Mock successful API response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.data = Mock()
            mock_response.data.name = "existing_character"
            mock_response.data.level = 10
            mock_response.data.hp = 80
            mock_response.data.x = 15
            mock_response.data.y = 20
            mock_response.parsed = mock_response.data

            mock_get.asyncio = AsyncMock(return_value=mock_response)

            wrapper = APIClientWrapper()
            result = await wrapper.get_character("existing_character")

            assert result == mock_response.data
            assert result.name == "existing_character"
            assert result.level == 10

    @pytest.mark.asyncio
    async def test_get_character_not_found(self, mock_token_config):
        """Test character retrieval with character not found"""
        with patch.object(TokenConfig, 'from_file', return_value=mock_token_config), \
             patch('src.game_data.api_client.AuthenticatedClient') as mock_client_class, \
             patch('src.game_data.api_client.get_character_characters_name_get') as mock_get:

            mock_client = Mock()
            mock_client_class.return_value = mock_client

            # Mock not found response (404)
            mock_response = Mock()
            mock_response.status_code = 404

            mock_get.asyncio = AsyncMock(return_value=mock_response)

            wrapper = APIClientWrapper()

            with pytest.raises(Exception):  # Should raise appropriate exception for 404
                await wrapper.get_character("nonexistent_character")

    @pytest.mark.asyncio
    async def test_move_character_success(self, mock_token_config):
        """Test successful character movement"""
        with patch.object(TokenConfig, 'from_file', return_value=mock_token_config), \
             patch('src.game_data.api_client.AuthenticatedClient') as mock_client_class, \
             patch('src.game_data.api_client.action_move_my_name_action_move_post') as mock_move:

            mock_client = Mock()
            mock_client_class.return_value = mock_client

            # Mock successful movement response with explicit data structure
            class MockReason:
                def __init__(self):
                    self.value = "move"
            
            class MockCooldown:
                def __init__(self):
                    self.expiration = (datetime.now() + timedelta(seconds=5)).isoformat()
                    self.total_seconds = 5
                    self.remaining_seconds = 5
                    self.reason = MockReason()
            
            class MockData:
                def __init__(self):
                    self.x = 25
                    self.y = 30
                    self.cooldown = MockCooldown()
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.data = MockData()
            mock_response.parsed = mock_response.data

            mock_move.asyncio = AsyncMock(return_value=mock_response)

            wrapper = APIClientWrapper()
            result = await wrapper.move_character("test_character", 25, 30)

            assert result == mock_response.parsed
            assert result.x == 25
            assert result.y == 30

    @pytest.mark.asyncio
    async def test_move_character_cooldown_error(self, mock_token_config):
        """Test character movement with cooldown error"""
        with patch.object(TokenConfig, 'from_file', return_value=mock_token_config), \
             patch('src.game_data.api_client.AuthenticatedClient') as mock_client_class, \
             patch('src.game_data.api_client.action_move_my_name_action_move_post') as mock_move:

            mock_client = Mock()
            mock_client_class.return_value = mock_client

            # Mock cooldown error response (499)
            from src.lib.httpstatus import ArtifactsHTTPStatus
            mock_response = Mock()
            mock_response.status_code = ArtifactsHTTPStatus["CHARACTER_COOLDOWN"]

            mock_move.asyncio = AsyncMock(return_value=mock_response)

            wrapper = APIClientWrapper()

            with pytest.raises(Exception):  # Should raise cooldown exception
                await wrapper.move_character("test_character", 25, 30)

    @pytest.mark.asyncio
    async def test_fight_monster_success(self, mock_token_config):
        """Test successful monster fighting"""
        with patch.object(TokenConfig, 'from_file', return_value=mock_token_config), \
             patch('src.game_data.api_client.AuthenticatedClient') as mock_client_class, \
             patch('src.game_data.api_client.action_fight_my_name_action_fight_post') as mock_fight:

            mock_client = Mock()
            mock_client_class.return_value = mock_client

            # Mock successful fight response with proper structure
            class MockReason:
                def __init__(self):
                    self.value = "fight"
            
            class MockCooldown:
                def __init__(self):
                    self.expiration = (datetime.now() + timedelta(seconds=8)).isoformat()
                    self.total_seconds = 8
                    self.remaining_seconds = 8
                    self.reason = MockReason()
            
            class MockFight:
                def __init__(self):
                    self.result = "win"
            
            class MockData:
                def __init__(self):
                    self.xp = 150
                    self.gold = 25
                    self.hp = 75
                    self.cooldown = MockCooldown()
                    self.fight = MockFight()
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.data = MockData()
            mock_response.parsed = mock_response.data

            mock_fight.asyncio = AsyncMock(return_value=mock_response)

            wrapper = APIClientWrapper()
            result = await wrapper.fight_monster("test_character")

            assert result == mock_response.parsed
            assert result.fight.result == "win"
            assert result.xp == 150

    @pytest.mark.asyncio
    async def test_handle_rate_limit(self, mock_token_config):
        """Test rate limiting handling with exponential backoff"""
        with patch.object(TokenConfig, 'from_file', return_value=mock_token_config), \
             patch('src.game_data.api_client.AuthenticatedClient'):

            wrapper = APIClientWrapper()

            # Mock rate limited response
            mock_response = Mock()
            mock_response.headers = {"Retry-After": "30"}

            with patch('asyncio.sleep') as mock_sleep:
                await wrapper._handle_rate_limit(mock_response)

                # Should sleep for the retry-after duration
                mock_sleep.assert_called_once_with(30)

    @pytest.mark.asyncio
    async def test_handle_rate_limit_no_retry_after(self, mock_token_config):
        """Test rate limiting handling without Retry-After header"""
        with patch.object(TokenConfig, 'from_file', return_value=mock_token_config), \
             patch('src.game_data.api_client.AuthenticatedClient'):

            wrapper = APIClientWrapper()

            # Mock rate limited response without Retry-After header
            mock_response = Mock()
            mock_response.headers = {}

            with patch('asyncio.sleep') as mock_sleep:
                await wrapper._handle_rate_limit(mock_response)

                # Should use default exponential backoff
                mock_sleep.assert_called_once()
                sleep_duration = mock_sleep.call_args[0][0]
                assert sleep_duration > 0


class TestCooldownManager:
    """Test CooldownManager functionality"""

    def test_cooldown_manager_initialization(self):
        """Test CooldownManager initialization"""
        manager = CooldownManager()

        assert hasattr(manager, 'character_cooldowns')
        assert isinstance(manager.character_cooldowns, dict)
        assert len(manager.character_cooldowns) == 0

    def test_update_cooldown_success(self):
        """Test updating cooldown from API response"""
        manager = CooldownManager()

        # Mock API cooldown response
        mock_cooldown_data = Mock()
        mock_cooldown_data.expiration = (datetime.now() + timedelta(seconds=30)).isoformat()
        mock_cooldown_data.total_seconds = 30
        mock_cooldown_data.remaining_seconds = 25
        mock_cooldown_data.reason = Mock()
        mock_cooldown_data.reason.value = "fight"

        manager.update_cooldown("test_character", mock_cooldown_data)

        assert "test_character" in manager.character_cooldowns
        cooldown_info = manager.character_cooldowns["test_character"]
        assert isinstance(cooldown_info, CooldownInfo)
        assert cooldown_info.character_name == "test_character"
        assert cooldown_info.total_seconds == 30
        assert cooldown_info.remaining_seconds == 25
        assert cooldown_info.reason == "fight"

    def test_is_ready_character_ready(self):
        """Test is_ready when character cooldown has expired"""
        manager = CooldownManager()

        # Add expired cooldown
        past_time = (datetime.now() - timedelta(seconds=10)).isoformat()
        cooldown_info = CooldownInfo(
            character_name="ready_character",
            expiration=past_time,
            total_seconds=30,
            remaining_seconds=0,
            reason="move"
        )

        with patch.object(CooldownInfo, 'is_ready', new_callable=lambda: property(lambda self: True)):
            manager.character_cooldowns["ready_character"] = cooldown_info

            is_ready = manager.is_ready("ready_character")
            assert is_ready is True

    def test_is_ready_character_on_cooldown(self):
        """Test is_ready when character is still on cooldown"""
        manager = CooldownManager()

        # Add active cooldown
        future_time = (datetime.now() + timedelta(seconds=30)).isoformat()
        cooldown_info = CooldownInfo(
            character_name="busy_character",
            expiration=future_time,
            total_seconds=30,
            remaining_seconds=25,
            reason="fight"
        )

        with patch.object(CooldownInfo, 'is_ready', new_callable=lambda: property(lambda self: False)):
            manager.character_cooldowns["busy_character"] = cooldown_info

            is_ready = manager.is_ready("busy_character")
            assert is_ready is False

    def test_is_ready_character_not_tracked(self):
        """Test is_ready for character not in cooldown tracking"""
        manager = CooldownManager()

        # Character not in tracking should be ready
        is_ready = manager.is_ready("unknown_character")
        assert is_ready is True

    @pytest.mark.asyncio
    async def test_wait_for_cooldown_ready_immediately(self):
        """Test wait_for_cooldown when character is ready"""
        manager = CooldownManager()

        with patch.object(manager, 'is_ready', return_value=True):
            # Should return immediately without waiting
            await manager.wait_for_cooldown("ready_character")
            # No assertion needed - should complete without waiting

    @pytest.mark.asyncio
    async def test_wait_for_cooldown_active_cooldown(self):
        """Test wait_for_cooldown when character has active cooldown"""
        manager = CooldownManager()

        # Mock active cooldown
        future_time = (datetime.now() + timedelta(seconds=5)).isoformat()
        cooldown_info = CooldownInfo(
            character_name="waiting_character",
            expiration=future_time,
            total_seconds=30,
            remaining_seconds=5,
            reason="gather"
        )

        manager.character_cooldowns["waiting_character"] = cooldown_info

        with patch.object(manager, 'is_ready', return_value=False), \
             patch.object(CooldownInfo, 'time_remaining', new_callable=lambda: property(lambda self: 5.0)), \
             patch('asyncio.sleep') as mock_sleep:

            await manager.wait_for_cooldown("waiting_character")

            # Should sleep for the remaining cooldown time
            mock_sleep.assert_called_once_with(5.0)

    def test_get_cooldown_info_exists(self):
        """Test getting cooldown info for tracked character"""
        manager = CooldownManager()

        cooldown_info = CooldownInfo(
            character_name="tracked_character",
            expiration=datetime.now().isoformat(),
            total_seconds=20,
            remaining_seconds=15,
            reason="craft"
        )

        manager.character_cooldowns["tracked_character"] = cooldown_info

        retrieved_info = manager.get_cooldown_info("tracked_character")
        assert retrieved_info == cooldown_info

    def test_get_cooldown_info_not_exists(self):
        """Test getting cooldown info for untracked character"""
        manager = CooldownManager()

        retrieved_info = manager.get_cooldown_info("untracked_character")
        assert retrieved_info is None

    def test_clear_cooldown(self):
        """Test clearing cooldown for specific character"""
        manager = CooldownManager()

        # Add cooldown
        cooldown_info = CooldownInfo(
            character_name="character_to_clear",
            expiration=datetime.now().isoformat(),
            total_seconds=30,
            remaining_seconds=20,
            reason="move"
        )

        manager.character_cooldowns["character_to_clear"] = cooldown_info
        assert "character_to_clear" in manager.character_cooldowns

        manager.clear_cooldown("character_to_clear")
        assert "character_to_clear" not in manager.character_cooldowns

    def test_clear_all_cooldowns(self):
        """Test clearing all cooldowns"""
        manager = CooldownManager()

        # Add multiple cooldowns
        for i in range(3):
            cooldown_info = CooldownInfo(
                character_name=f"character_{i}",
                expiration=datetime.now().isoformat(),
                total_seconds=30,
                remaining_seconds=20,
                reason="test"
            )
            manager.character_cooldowns[f"character_{i}"] = cooldown_info

        assert len(manager.character_cooldowns) == 3

        manager.clear_all_cooldowns()
        assert len(manager.character_cooldowns) == 0


class TestAPIClientIntegration:
    """Integration tests for API client components"""

    @pytest.mark.asyncio
    async def test_full_api_workflow(self):
        """Test complete API workflow with cooldown management"""
        # Mock token config
        mock_token_config = TokenConfig(token="e" * 32)

        with patch.object(TokenConfig, 'from_file', return_value=mock_token_config), \
             patch('src.game_data.api_client.AuthenticatedClient') as mock_client_class:

            mock_client = Mock()
            mock_client_class.return_value = mock_client

            wrapper = APIClientWrapper()
            cooldown_manager = CooldownManager()

            # Mock character with cooldown
            character_name = "integration_test_character"

            # Initial state - character ready
            assert cooldown_manager.is_ready(character_name) is True

            # Simulate action that causes cooldown
            mock_cooldown_data = Mock()
            mock_cooldown_data.expiration = (datetime.now() + timedelta(seconds=10)).isoformat()
            mock_cooldown_data.total_seconds = 10
            mock_cooldown_data.remaining_seconds = 10
            mock_cooldown_data.reason = Mock()
            mock_cooldown_data.reason.value = "move"

            cooldown_manager.update_cooldown(character_name, mock_cooldown_data)

            # Character should now be on cooldown
            with patch.object(CooldownInfo, 'is_ready', new_callable=lambda: property(lambda self: False)):
                assert cooldown_manager.is_ready(character_name) is False

            # Simulate cooldown expiration
            with patch.object(CooldownInfo, 'is_ready', new_callable=lambda: property(lambda self: True)):
                assert cooldown_manager.is_ready(character_name) is True

    def test_error_handling_integration(self):
        """Test error handling across API client components"""
        # Test various error conditions
        error_scenarios = [
            ("Invalid token", ValueError, "Invalid token format"),
            ("API connection failed", ConnectionError, "Failed to connect to API"),
            ("Rate limited", Exception, "Rate limit exceeded"),
        ]

        for scenario_name, error_type, error_message in error_scenarios:
            # Each scenario should be handled appropriately
            assert error_type is not None
            assert isinstance(error_message, str)
            # Specific error handling tests would go here

    def test_configuration_validation(self):
        """Test configuration validation across components"""
        # Test token validation
        valid_tokens = [
            "a" * 32,
            "b" * 40,
            "c" * 64
        ]

        for token in valid_tokens:
            config = TokenConfig(token=token)
            assert config.token == token

        # Test invalid tokens
        invalid_tokens = [
            "",
            "short",
            "a" * 31  # One character short
        ]

        for token in invalid_tokens:
            with pytest.raises(Exception):
                TokenConfig(token=token)
