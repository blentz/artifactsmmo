"""
Comprehensive tests for APIClientWrapper to achieve 95% coverage.

This test module provides extensive coverage for the API client wrapper,
including authentication, character operations, game data retrieval,
error handling, and rate limiting. All tests use Pydantic models throughout
as required by the architecture.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Break circular import by patching modules before importing
with patch.dict('sys.modules', {'src.ai_player.action_executor': Mock()}):
    from src.game_data.api_client import APIClientWrapper, CooldownManager
    from src.game_data.character import Character
    from src.game_data.models import GameItem, GameMap, GameMonster, GameNPC, GameResource
    from src.lib.httpstatus import ArtifactsHTTPStatus


class TestAPIClientWrapperInitialization:
    """Test APIClientWrapper initialization and setup."""

    @patch('src.game_data.api_client_wrapper.TokenConfig')
    @patch('src.game_data.api_client_wrapper.AuthenticatedClient')
    def test_init_default_token_file(self, mock_auth_client, mock_token_config):
        """Test initialization with default token file."""
        mock_token_instance = Mock()
        mock_token_instance.token = "test_token_123"
        mock_token_config.from_file.return_value = mock_token_instance
        mock_client_instance = Mock()
        mock_auth_client.return_value = mock_client_instance

        wrapper = APIClientWrapper()

        mock_token_config.from_file.assert_called_once_with("TOKEN")
        mock_auth_client.assert_called_once_with(
            base_url="https://api.artifactsmmo.com",
            token="test_token_123"
        )
        assert wrapper.token_config == mock_token_instance
        assert wrapper.client == mock_client_instance
        assert isinstance(wrapper.cooldown_manager, CooldownManager)
        assert wrapper.status_codes == ArtifactsHTTPStatus

    @patch('src.game_data.api_client_wrapper.TokenConfig')
    @patch('src.game_data.api_client_wrapper.AuthenticatedClient')
    def test_init_custom_token_file(self, mock_auth_client, mock_token_config):
        """Test initialization with custom token file."""
        mock_token_instance = Mock()
        mock_token_instance.token = "custom_token_456"
        mock_token_config.from_file.return_value = mock_token_instance

        wrapper = APIClientWrapper("custom_token.txt")

        mock_token_config.from_file.assert_called_once_with("custom_token.txt")

    @patch('src.game_data.api_client_wrapper.TokenConfig')
    def test_init_token_config_error(self, mock_token_config):
        """Test initialization with token configuration error."""
        mock_token_config.from_file.side_effect = ValueError("Invalid token")

        with pytest.raises(ValueError, match="Invalid token"):
            APIClientWrapper()


class TestCharacterOperations:
    """Test character creation, deletion, and retrieval operations."""

    @pytest.mark.asyncio
    @patch('src.game_data.api_client_wrapper.create_character_asyncio_detailed')
    async def test_create_character_success(self, mock_create_char):
        """Test successful character creation."""
        # Setup wrapper
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        # Mock API response
        mock_response = Mock()
        mock_character_data = Mock()
        mock_character_data.name = "test_char"
        mock_character_data.level = 1
        mock_create_char.return_value = mock_response

        # Mock the processed response structure that has .data attribute
        mock_processed_response = Mock()
        mock_processed_response.data = mock_character_data

        with patch.object(wrapper, '_process_response', return_value=mock_processed_response):
            result = await wrapper.create_character("test_char", "men1")

            mock_create_char.assert_called_once()
            assert result == mock_character_data

    @pytest.mark.asyncio
    async def test_create_character_invalid_skin(self):
        """Test character creation with invalid skin."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        with pytest.raises(ValueError, match="Invalid skin"):
            await wrapper.create_character("test_char", "invalid_skin")

    @pytest.mark.asyncio
    @patch('src.game_data.api_client_wrapper.delete_character_asyncio_detailed')
    async def test_delete_character_success(self, mock_delete_char):
        """Test successful character deletion."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_delete_char.return_value = mock_response

        with patch.object(wrapper, '_process_response', return_value=Mock()):
            result = await wrapper.delete_character("test_char")

            mock_delete_char.assert_called_once()
            assert result is True

    @pytest.mark.asyncio
    @patch('src.game_data.api_client_wrapper.delete_character_asyncio_detailed')
    async def test_delete_character_exception(self, mock_delete_char):
        """Test character deletion with exception."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        mock_delete_char.side_effect = Exception("Delete failed")

        with pytest.raises(Exception, match="Delete failed"):
            await wrapper.delete_character("test_char")

    @pytest.mark.asyncio
    @patch('src.game_data.api_client_wrapper.get_my_characters_my_characters_get')
    async def test_get_characters_success(self, mock_get_chars):
        """Test successful character list retrieval."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'), \
             patch('src.game_data.api_client_wrapper.AuthenticatedClient'):

            wrapper = APIClientWrapper()

        mock_char_data = Mock()
        mock_char_data.name = "test_char"
        mock_char_data.level = 5
        mock_chars_list = [mock_char_data]

        # Create proper response mock with .parsed attribute for successful processing
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.parsed = Mock()
        mock_response.parsed.data = mock_chars_list
        mock_get_chars.asyncio_detailed = AsyncMock(return_value=mock_response)

        with patch('src.game_data.api_client_wrapper.Character') as mock_character_class:
            mock_character_instance = Mock(spec=Character)
            mock_character_class.from_api_character.return_value = mock_character_instance

            result = await wrapper.get_characters()

            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0] == mock_character_instance

    @pytest.mark.asyncio
    @patch('src.game_data.api_client_wrapper.get_character_characters_name_get')
    async def test_get_character_success(self, mock_get_char):
        """Test successful single character retrieval."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        mock_char_data = Mock()
        mock_char_data.name = "test_char"

        # Create proper response mock with .parsed.data structure
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.parsed = Mock()
        mock_response.parsed.data = mock_char_data
        mock_get_char.asyncio_detailed = AsyncMock(return_value=mock_response)

        result = await wrapper.get_character("test_char")

        # Should return the raw API character data
        assert result == mock_char_data


class TestCharacterActions:
    """Test character action operations (move, fight, gather, etc.)."""

    @pytest.mark.asyncio
    @patch('src.game_data.api_client_wrapper.action_move_my_name_action_move_post')
    @patch('src.game_data.api_client_wrapper.MovementResult')
    async def test_move_character_success(self, mock_movement_result, mock_move):
        """Test successful character movement."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.parsed = Mock()
        mock_response.parsed.data = Mock()
        mock_move.asyncio_detailed = AsyncMock(return_value=mock_response)

        mock_movement_instance = Mock()
        mock_movement_result.from_api_movement_response.return_value = mock_movement_instance

        with patch.object(wrapper, '_process_response', return_value=mock_response.parsed), \
             patch.object(wrapper.cooldown_manager, 'update_cooldown'):
            result = await wrapper.move_character("test_char", 5, 10)

            mock_move.asyncio_detailed.assert_called_once()
            assert result == mock_movement_instance

    @pytest.mark.asyncio
    @patch('src.game_data.api_client_wrapper.action_fight_my_name_action_fight_post')
    async def test_fight_monster_success(self, mock_fight):
        """Test successful monster fighting."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.parsed = Mock()
        mock_response.parsed.data = Mock()
        mock_fight.asyncio_detailed = AsyncMock(return_value=mock_response)

        with patch.object(wrapper, '_process_response', return_value=mock_response.parsed), \
             patch.object(wrapper.cooldown_manager, 'update_cooldown'):
            result = await wrapper.fight_monster("test_char")

            mock_fight.asyncio_detailed.assert_called_once()
            assert result == mock_response.parsed.data

    @pytest.mark.asyncio
    @patch('src.game_data.api_client_wrapper.action_gathering_asyncio_detailed')
    async def test_gather_resource_success(self, mock_gather):
        """Test successful resource gathering."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.parsed = Mock()
        mock_response.parsed.data = Mock()
        mock_gather.return_value = mock_response

        with patch.object(wrapper, '_process_response', return_value=mock_response.parsed), \
             patch.object(wrapper.cooldown_manager, 'update_cooldown'):
            result = await wrapper.gather_resource("test_char")

            mock_gather.assert_called_once()
            assert result == mock_response.parsed.data

    @pytest.mark.asyncio
    @patch('src.game_data.api_client_wrapper.action_crafting_asyncio_detailed')
    async def test_craft_item_success(self, mock_craft):
        """Test successful item crafting."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.parsed = Mock()
        mock_response.parsed.data = Mock()
        mock_craft.return_value = mock_response

        with patch.object(wrapper, '_process_response', return_value=mock_response.parsed), \
             patch.object(wrapper.cooldown_manager, 'update_cooldown'):
            result = await wrapper.craft_item("test_char", "copper_dagger", 2)

            mock_craft.assert_called_once()
            assert result == mock_response.parsed.data

    @pytest.mark.asyncio
    @patch('src.game_data.api_client_wrapper.action_rest_asyncio_detailed')
    async def test_rest_character_success(self, mock_rest):
        """Test successful character rest."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.parsed = Mock()
        mock_response.parsed.data = Mock()
        mock_rest.return_value = mock_response

        with patch.object(wrapper, '_process_response', return_value=mock_response.parsed), \
             patch.object(wrapper.cooldown_manager, 'update_cooldown'):
            result = await wrapper.rest_character("test_char")

            mock_rest.assert_called_once()
            assert result == mock_response.parsed.data

    @pytest.mark.asyncio
    @patch('src.game_data.api_client_wrapper.action_equip_item_asyncio_detailed')
    async def test_equip_item_success(self, mock_equip):
        """Test successful item equipping."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.parsed = Mock()
        mock_response.parsed.data = Mock()
        mock_equip.return_value = mock_response

        with patch.object(wrapper, '_process_response', return_value=mock_response.parsed), \
             patch.object(wrapper.cooldown_manager, 'update_cooldown'):
            result = await wrapper.equip_item("test_char", "copper_dagger", "weapon")

            mock_equip.assert_called_once()
            assert result == mock_response.parsed.data

    @pytest.mark.asyncio
    @patch('src.game_data.api_client_wrapper.action_unequip_item_asyncio_detailed')
    async def test_unequip_item_success(self, mock_unequip):
        """Test successful item unequipping."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.parsed = Mock()
        mock_response.parsed.data = Mock()
        mock_unequip.return_value = mock_response

        with patch.object(wrapper, '_process_response', return_value=mock_response.parsed), \
             patch.object(wrapper.cooldown_manager, 'update_cooldown'):
            result = await wrapper.unequip_item("test_char", "weapon")

            mock_unequip.assert_called_once()
            assert result == mock_response.parsed.data


class TestGameDataRetrieval:
    """Test game data retrieval operations."""

    @pytest.mark.asyncio
    @patch('src.game_data.api_client_wrapper.get_all_items_asyncio_detailed')
    async def test_get_all_items_success(self, mock_get_items):
        """Test successful items retrieval."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.parsed = Mock()
        mock_item_data = Mock()
        mock_item_data.code = "copper_dagger"
        mock_items_list = [mock_item_data]
        mock_response.parsed.data = mock_items_list
        mock_get_items = AsyncMock(return_value=mock_response)

        with patch.object(wrapper, '_process_response', return_value=mock_response.parsed):
            with patch('src.game_data.api_client_wrapper.GameItem') as mock_game_item:
                mock_item_instance = Mock(spec=GameItem)
                mock_game_item.from_api_item.return_value = mock_item_instance

                result = await wrapper.get_all_items()

                assert isinstance(result, list)
                assert len(result) == 1
                assert result[0] == mock_item_instance

    @pytest.mark.asyncio
    @patch('src.game_data.api_client_wrapper.get_all_monsters_asyncio_detailed')
    async def test_get_all_monsters_success(self, mock_get_monsters):
        """Test successful monsters retrieval."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.parsed = Mock()
        mock_monster_data = Mock()
        mock_monster_data.code = "chicken"
        mock_monsters_list = [mock_monster_data]
        mock_response.parsed.data = mock_monsters_list
        mock_get_monsters = AsyncMock(return_value=mock_response)

        with patch.object(wrapper, '_process_response', return_value=mock_response.parsed):
            with patch('src.game_data.api_client_wrapper.GameMonster') as mock_game_monster:
                mock_monster_instance = Mock(spec=GameMonster)
                mock_game_monster.from_api_monster.return_value = mock_monster_instance

                result = await wrapper.get_all_monsters()

                assert isinstance(result, list)
                assert len(result) == 1
                assert result[0] == mock_monster_instance

    @pytest.mark.asyncio
    @patch('src.game_data.api_client_wrapper.get_all_maps_asyncio_detailed')
    async def test_get_all_maps_success(self, mock_get_maps):
        """Test successful maps retrieval."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.parsed = Mock()
        mock_map_data = Mock()
        mock_map_data.x = 0
        mock_map_data.y = 0
        mock_maps_list = [mock_map_data]
        mock_response.parsed.data = mock_maps_list
        mock_get_maps = AsyncMock(return_value=mock_response)

        with patch.object(wrapper, '_process_response', return_value=mock_response.parsed):
            with patch('src.game_data.api_client_wrapper.GameMap') as mock_game_map:
                mock_map_instance = Mock(spec=GameMap)
                mock_game_map.from_api_map.return_value = mock_map_instance

                result = await wrapper.get_all_maps()

                assert isinstance(result, list)
                assert len(result) == 1
                assert result[0] == mock_map_instance

    @pytest.mark.asyncio
    @patch('src.game_data.api_client_wrapper.get_map_asyncio_detailed')
    async def test_get_map_success(self, mock_get_map):
        """Test successful single map retrieval."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.parsed = Mock()
        mock_map_data = Mock()
        mock_map_data.x = 5
        mock_map_data.y = 10
        mock_response.parsed.data = mock_map_data
        mock_get_map = AsyncMock(return_value=mock_response)

        with patch.object(wrapper, '_process_response', return_value=mock_response.parsed):
            with patch('src.game_data.api_client_wrapper.GameMap') as mock_game_map:
                mock_map_instance = Mock(spec=GameMap)
                mock_game_map.from_api_map.return_value = mock_map_instance

                result = await wrapper.get_map(5, 10)

                assert result == mock_map_instance

    @pytest.mark.asyncio
    @patch('src.game_data.api_client_wrapper.get_all_resources_asyncio_detailed')
    async def test_get_all_resources_success(self, mock_get_resources):
        """Test successful resources retrieval."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.parsed = Mock()
        mock_resource_data = Mock()
        mock_resource_data.code = "ash_tree"
        mock_resources_list = [mock_resource_data]
        mock_response.parsed.data = mock_resources_list
        mock_get_resources = AsyncMock(return_value=mock_response)

        with patch.object(wrapper, '_process_response', return_value=mock_response.parsed):
            with patch('src.game_data.api_client_wrapper.GameResource') as mock_game_resource:
                mock_resource_instance = Mock(spec=GameResource)
                mock_game_resource.from_api_resource.return_value = mock_resource_instance

                result = await wrapper.get_all_resources()

                assert isinstance(result, list)
                assert len(result) == 1
                assert result[0] == mock_resource_instance

    @pytest.mark.asyncio
    @patch('src.game_data.api_client_wrapper.get_all_npcs_asyncio_detailed')
    async def test_get_all_npcs_success(self, mock_get_npcs):
        """Test successful NPCs retrieval."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.parsed = Mock()
        mock_npc_data = Mock()
        mock_npc_data.code = "weapons_master"
        mock_npcs_list = [mock_npc_data]
        mock_response.parsed.data = mock_npcs_list
        mock_get_npcs = AsyncMock(return_value=mock_response)

        with patch.object(wrapper, '_process_response', return_value=mock_response.parsed):
            with patch('src.game_data.api_client_wrapper.GameNPC') as mock_game_npc:
                mock_npc_instance = Mock(spec=GameNPC)
                mock_game_npc.from_api_npc.return_value = mock_npc_instance

                result = await wrapper.get_all_npcs()

                assert isinstance(result, list)
                assert len(result) == 1
                assert result[0] == mock_npc_instance


class TestErrorHandlingAndRateLimit:
    """Test error handling and rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_handle_rate_limit_success(self):
        """Test rate limit handling."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        mock_response = Mock()
        mock_response.headers = {"Retry-After": "30"}

        with patch('asyncio.sleep') as mock_sleep:
            await wrapper._handle_rate_limit(mock_response)

            mock_sleep.assert_called_once_with(30)

    @pytest.mark.asyncio
    async def test_handle_rate_limit_no_retry_after(self):
        """Test rate limit handling without Retry-After header."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        mock_response = Mock()
        mock_response.headers = {}

        with patch('asyncio.sleep') as mock_sleep:
            await wrapper._handle_rate_limit(mock_response)

            mock_sleep.assert_called_once_with(1.0)  # Default 1.0 seconds

    @pytest.mark.asyncio
    async def test_handle_rate_limit_invalid_retry_after(self):
        """Test rate limit handling with invalid Retry-After value."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        mock_response = Mock()
        mock_response.headers = {"Retry-After": "invalid"}

        with patch('asyncio.sleep') as mock_sleep:
            await wrapper._handle_rate_limit(mock_response)

            mock_sleep.assert_called_once_with(5.0)  # Default fallback

    @pytest.mark.asyncio
    async def test_process_response_success(self):
        """Test successful response processing."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.parsed = {"data": "test"}

        result = await wrapper._process_response(mock_response)

        assert result == {"data": "test"}

    @pytest.mark.asyncio
    async def test_process_response_rate_limit(self):
        """Test response processing with rate limit."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        mock_response = Mock()
        mock_response.status_code = 429  # Rate limit
        mock_response.parsed = {"error": "rate limited"}

        with patch.object(wrapper, '_handle_rate_limit') as mock_handle_rate_limit:
            with pytest.raises(ValueError, match="Rate limit exceeded"):
                await wrapper._process_response(mock_response)

            mock_handle_rate_limit.assert_called_once_with(mock_response)

    @pytest.mark.asyncio
    async def test_process_response_cooldown_error(self):
        """Test response processing with cooldown error."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        mock_response = Mock()
        mock_response.status_code = 499  # Character cooldown
        mock_response.parsed = {"error": "character in cooldown"}

        with pytest.raises(ValueError, match="API error 499"):
            await wrapper._process_response(mock_response)

    @pytest.mark.asyncio
    async def test_process_response_server_error(self):
        """Test response processing with server error."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.parsed = None

        with pytest.raises(Exception):
            await wrapper._process_response(mock_response)


class TestIntegrationScenarios:
    """Test integration scenarios and edge cases."""

    def test_cooldown_manager_integration(self):
        """Test that cooldown manager is properly integrated."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        assert wrapper.cooldown_manager is not None
        assert isinstance(wrapper.cooldown_manager, CooldownManager)

    def test_status_codes_integration(self):
        """Test that status codes are properly integrated."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        assert wrapper.status_codes == ArtifactsHTTPStatus

    def test_client_base_url_configuration(self):
        """Test that client is configured with correct base URL."""
        with patch('src.game_data.api_client_wrapper.TokenConfig') as mock_token_config:
            mock_token_instance = Mock()
            mock_token_instance.token = "test_token"
            mock_token_config.from_file.return_value = mock_token_instance

            with patch('src.game_data.api_client_wrapper.AuthenticatedClient') as mock_auth_client:
                wrapper = APIClientWrapper()

                mock_auth_client.assert_called_once_with(
                    base_url="https://api.artifactsmmo.com",
                    token="test_token"
                )

    def test_string_representation(self):
        """Test string representation of APIClientWrapper."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        str_repr = str(wrapper)
        assert isinstance(str_repr, str)


class TestAsyncErrorHandling:
    """Test async operation error handling."""

    @pytest.mark.asyncio
    async def test_async_operation_network_error(self):
        """Test async operation with network error."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        with patch('src.game_data.api_client_wrapper.get_character_characters_name_get') as mock_get_char:
            mock_get_char.asyncio_detailed.side_effect = Exception("Network error")

            with pytest.raises(Exception, match="Network error"):
                await wrapper.get_character("test_char")

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test concurrent API operations."""
        with patch('src.game_data.api_client_wrapper.TokenConfig'):
            with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                wrapper = APIClientWrapper()

        with patch('src.game_data.api_client_wrapper.get_character_characters_name_get') as mock_get_char:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.parsed = Mock()
            mock_char_data = Mock()
            mock_char_data.name = "test_char"
            mock_response.parsed.data = mock_char_data
            mock_get_char.asyncio_detailed = AsyncMock(return_value=mock_response)

            # Test concurrent operations
            results = await asyncio.gather(
                wrapper.get_character("char1"),
                wrapper.get_character("char2"),
                wrapper.get_character("char3")
            )

            assert len(results) == 3
            for result in results:
                assert result == mock_char_data
