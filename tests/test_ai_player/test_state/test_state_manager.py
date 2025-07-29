"""
Tests for StateManager class

This module tests the state synchronization, API integration,
and state management functionality of the StateManager class.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.ai_player.state.game_state import ActionResult, CharacterGameState, GameState
from src.ai_player.state.state_manager import StateManager


class TestStateManager:
    """Test StateManager functionality"""

    @pytest.fixture
    def mock_api_client(self):
        """Mock API client for testing"""
        client = Mock()
        
        # Create a mock character with all required fields
        mock_character = Mock()
        mock_character.name = "test_character"
        mock_character.level = 5
        mock_character.xp = 1000
        mock_character.gold = 500
        mock_character.hp = 80
        mock_character.max_hp = 100
        mock_character.x = 10
        mock_character.y = 15
        mock_character.cooldown = 0
        mock_character.mining_level = 1
        mock_character.mining_xp = 0
        mock_character.woodcutting_level = 1
        mock_character.woodcutting_xp = 0
        mock_character.fishing_level = 1
        mock_character.fishing_xp = 0
        mock_character.weaponcrafting_level = 1
        mock_character.weaponcrafting_xp = 0
        mock_character.gearcrafting_level = 1
        mock_character.gearcrafting_xp = 0
        mock_character.jewelrycrafting_level = 1
        mock_character.jewelrycrafting_xp = 0
        mock_character.cooking_level = 1
        mock_character.cooking_xp = 0
        mock_character.alchemy_level = 1
        mock_character.alchemy_xp = 0
        
        client.get_character = AsyncMock(return_value=mock_character)
        client.get_character_logs = AsyncMock()
        return client

    @pytest.fixture
    def mock_cache_manager(self):
        """Mock cache manager for testing"""
        cache = Mock()
        cache.save_character_state = Mock()
        cache.load_character_state = Mock()
        return cache

    @pytest.fixture
    def state_manager(self, mock_api_client, mock_cache_manager):
        """Create StateManager instance for testing"""
        with patch('src.ai_player.state.state_manager.YamlData') as mock_yaml:
            # Configure mock to have proper data structure
            mock_yaml_instance = Mock()
            mock_yaml_instance.data = {
                'data': [
                    {
                        'name': 'test_character',
                        'character_level': 5,
                        'hp_current': 80,
                        'current_x': 10,
                        'current_y': 15,
                        'cooldown_ready': True
                    }
                ]
            }
            mock_yaml_instance.save = Mock()
            mock_yaml.return_value = mock_yaml_instance
            return StateManager("test_character", mock_api_client, mock_cache_manager)

    def test_state_manager_initialization(self, state_manager):
        """Test StateManager initialization"""
        assert state_manager.character_name == "test_character"
        assert hasattr(state_manager, 'get_current_state')
        assert hasattr(state_manager, 'update_state')
        assert hasattr(state_manager, 'sync_with_api')

    @pytest.mark.asyncio
    async def test_get_current_state_from_cache(self, state_manager, mock_cache_manager):
        """Test getting current state from cache when available"""
        # The state should be loaded from the YAML cache data we configured in the fixture
        current_state = await state_manager.get_current_state()

        assert isinstance(current_state, dict)
        # Verify the state contains the expected GameState enum keys
        assert GameState.CHARACTER_LEVEL in current_state
        assert GameState.HP_CURRENT in current_state
        assert GameState.CURRENT_X in current_state
        assert GameState.CURRENT_Y in current_state
        # Verify we got valid numeric values
        assert isinstance(current_state[GameState.CHARACTER_LEVEL], int)
        assert isinstance(current_state[GameState.HP_CURRENT], int)

    @pytest.mark.asyncio
    async def test_get_current_state_from_api_fallback(self, state_manager, mock_api_client, mock_cache_manager):
        """Test getting current state from API when cache is unavailable"""
        # Mock cache miss
        mock_cache_manager.load_character_state.return_value = None

        # Mock API character response
        mock_character = Mock()
        mock_character.level = 5
        mock_character.xp = 1000
        mock_character.gold = 500
        mock_character.hp = 80
        mock_character.max_hp = 100
        mock_character.x = 10
        mock_character.y = 15
        mock_character.cooldown = 0
        mock_character.mining_level = 3
        mock_character.woodcutting_level = 2
        mock_character.fishing_level = 1
        mock_character.weaponcrafting_level = 1
        mock_character.gearcrafting_level = 1
        mock_character.jewelrycrafting_level = 1
        mock_character.cooking_level = 1
        mock_character.alchemy_level = 1
        mock_character.weapon_slot = "copper_sword"
        mock_character.inventory = ["item1", "item2"]
        mock_character.inventory_max_items = 20

        mock_api_client.get_character.return_value = mock_character

        with patch.object(CharacterGameState, 'from_api_character') as mock_from_api:
            mock_character_state = Mock()
            mock_character_state.to_goap_state.return_value = {
                "character_level": 5,
                "hp_current": 80,
                "current_x": 10,
                "current_y": 15,
                "cooldown_ready": 1
            }
            mock_from_api.return_value = mock_character_state

            current_state = await state_manager.get_current_state()

            assert isinstance(current_state, dict)
            mock_api_client.get_character.assert_called_once_with("test_character")
            mock_from_api.assert_called_once_with(mock_character)

    @pytest.mark.asyncio
    async def test_update_state_with_changes(self, state_manager, mock_cache_manager):
        """Test updating state with specific changes"""
        state_changes = {
            GameState.HP_CURRENT: 90,
            GameState.CURRENT_X: 20,
            GameState.COOLDOWN_READY: False
        }

        await state_manager.update_state(state_changes)

        # Verify that state changes are applied and cached
        # The state manager should call save() on the YAML cache instance
        state_manager._characters_cache.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_state_invalid_enum_keys(self, state_manager):
        """Test updating state with invalid GameState enum keys"""
        invalid_changes = {
            "invalid_key": 42,
            GameState.HP_CURRENT: 90
        }

        with pytest.raises(ValueError, match="Invalid state key"):
            await state_manager.update_state(invalid_changes)

    @pytest.mark.asyncio
    async def test_sync_with_api_success(self, state_manager, mock_api_client, mock_cache_manager):
        """Test successful API synchronization"""
        # Mock API character response
        mock_character = Mock()
        mock_character.level = 6
        mock_character.xp = 1200
        mock_character.hp = 85
        mock_character.max_hp = 105
        mock_character.x = 25
        mock_character.y = 30
        mock_character.cooldown = 5
        mock_character.mining_level = 4
        mock_character.woodcutting_level = 3
        mock_character.fishing_level = 2
        mock_character.weaponcrafting_level = 1
        mock_character.gearcrafting_level = 1
        mock_character.jewelrycrafting_level = 1
        mock_character.cooking_level = 1
        mock_character.alchemy_level = 1
        mock_character.weapon_slot = "iron_sword"
        mock_character.inventory = ["item1", "item2", "item3"]
        mock_character.inventory_max_items = 20

        mock_api_client.get_character.return_value = mock_character

        with patch.object(CharacterGameState, 'from_api_character') as mock_from_api:
            mock_character_state = Mock()
            mock_character_state.to_goap_state.return_value = {
                "character_level": 6,
                "character_xp": 1200,
                "hp_current": 85,
                "current_x": 25,
                "current_y": 30,
                "cooldown_ready": 0
            }
            mock_from_api.return_value = mock_character_state

            synced_state = await state_manager.sync_with_api()

            assert isinstance(synced_state, dict)
            mock_api_client.get_character.assert_called_once_with("test_character")
            state_manager._characters_cache.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_with_api_failure(self, state_manager, mock_api_client):
        """Test API synchronization failure handling"""
        mock_api_client.get_character.side_effect = Exception("API connection failed")

        with pytest.raises(Exception, match="API connection failed"):
            await state_manager.sync_with_api()

    @pytest.mark.asyncio
    async def test_validate_state_consistency_valid(self, state_manager):
        """Test state consistency validation with valid state"""
        valid_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_CURRENT: 80,
            GameState.HP_MAX: 100,
            GameState.CURRENT_X: 10,
            GameState.CURRENT_Y: 15
        }

        is_consistent = await state_manager.validate_state_consistency(valid_state)
        assert isinstance(is_consistent, bool)

    @pytest.mark.asyncio
    async def test_validate_state_consistency_invalid_hp(self, state_manager):
        """Test state consistency validation with invalid HP values"""
        invalid_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_CURRENT: 120,  # HP higher than max
            GameState.HP_MAX: 100,
            GameState.CURRENT_X: 10,
            GameState.CURRENT_Y: 15
        }

        is_consistent = await state_manager.validate_state_consistency(invalid_state)
        assert is_consistent is False

    @pytest.mark.asyncio
    async def test_validate_state_consistency_negative_values(self, state_manager):
        """Test state consistency validation with negative values"""
        invalid_state = {
            GameState.CHARACTER_LEVEL: -1,  # Negative level
            GameState.HP_CURRENT: -10,     # Negative HP
            GameState.CURRENT_X: 10,
            GameState.CURRENT_Y: 15
        }

        is_consistent = await state_manager.validate_state_consistency(invalid_state)
        assert is_consistent is False

    @pytest.mark.asyncio
    async def test_apply_action_result_success(self, state_manager, mock_cache_manager):
        """Test applying action result with state changes"""

        action_result = ActionResult(
            success=True,
            message="Action completed successfully",
            state_changes={
                GameState.CURRENT_X: 25,
                GameState.CURRENT_Y: 30,
                GameState.HP_CURRENT: 95,
                GameState.COOLDOWN_READY: False
            },
            cooldown_seconds=5
        )

        await state_manager.apply_action_result(action_result)

        # Verify that state changes are applied
        state_manager._characters_cache.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_action_result_failure(self, state_manager, mock_cache_manager):
        """Test applying failed action result (no state changes)"""

        action_result = ActionResult(
            success=False,
            message="Action failed",
            state_changes={},
            cooldown_seconds=30
        )

        await state_manager.apply_action_result(action_result)

        # Failed actions should not trigger state changes
        # but may still update cooldown information
        state_manager._characters_cache.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_state_value_exists(self, state_manager):
        """Test getting specific state value that exists"""
        # Mock current state
        with patch.object(state_manager, 'get_current_state') as mock_get_state:
            mock_get_state.return_value = {
                GameState.CHARACTER_LEVEL: 5,
                GameState.HP_CURRENT: 80,
                GameState.COOLDOWN_READY: True
            }

            level = await state_manager.get_state_value(GameState.CHARACTER_LEVEL)
            assert level == 5

            hp = await state_manager.get_state_value(GameState.HP_CURRENT)
            assert hp == 80

            cooldown_ready = await state_manager.get_state_value(GameState.COOLDOWN_READY)
            assert cooldown_ready is True

    @pytest.mark.asyncio
    async def test_get_state_value_missing(self, state_manager):
        """Test getting specific state value that doesn't exist"""
        # Mock current state with missing value
        with patch.object(state_manager, 'get_current_state') as mock_get_state:
            mock_get_state.return_value = {
                GameState.CHARACTER_LEVEL: 5,
                GameState.HP_CURRENT: 80
            }

            # Missing state should return None or default value
            missing_value = await state_manager.get_state_value(GameState.MINING_LEVEL)
            assert missing_value is None

    @pytest.mark.asyncio
    async def test_set_state_value(self, state_manager, mock_cache_manager):
        """Test setting specific state value"""
        await state_manager.set_state_value(GameState.HP_CURRENT, 95)

        # Verify that state update is triggered
        state_manager._characters_cache.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_state_from_api(self, state_manager, mock_api_client, mock_cache_manager):
        """Test forced refresh of state from API"""
        # Mock API response
        mock_character = Mock()
        mock_character.level = 7
        mock_character.xp = 1500
        mock_character.hp = 90
        mock_character.max_hp = 110
        mock_character.x = 35
        mock_character.y = 40
        mock_character.cooldown = 0
        mock_character.mining_level = 5
        mock_character.woodcutting_level = 4
        mock_character.fishing_level = 3
        mock_character.weaponcrafting_level = 2
        mock_character.gearcrafting_level = 1
        mock_character.jewelrycrafting_level = 1
        mock_character.cooking_level = 1
        mock_character.alchemy_level = 1
        mock_character.weapon_slot = "steel_sword"
        mock_character.inventory = ["item1", "item2", "item3", "item4"]
        mock_character.inventory_max_items = 20

        mock_api_client.get_character.return_value = mock_character

        with patch.object(CharacterGameState, 'from_api_character') as mock_from_api:
            mock_character_state = Mock()
            mock_character_state.to_goap_state.return_value = {
                "character_level": 7,
                "character_xp": 1500,
                "hp_current": 90,
                "current_x": 35,
                "current_y": 40,
                "cooldown_ready": 1
            }
            mock_from_api.return_value = mock_character_state

            refreshed_state = await state_manager.refresh_state_from_api()

            assert isinstance(refreshed_state, dict)
            mock_api_client.get_character.assert_called_once_with("test_character")
            state_manager._characters_cache.save.assert_called_once()


class TestStateManagerIntegration:
    """Integration tests for StateManager with other components"""

    @pytest.mark.asyncio
    async def test_state_manager_with_real_game_state_enum(self):
        """Test StateManager integration with actual GameState enum"""
        with patch('src.ai_player.state.state_manager.YamlData'):
            mock_api_client = Mock()
            mock_cache_manager = Mock()

            state_manager = StateManager("integration_test_char", mock_api_client, mock_cache_manager)

            # Test that all GameState enum values can be used
            test_changes = {
                GameState.CHARACTER_LEVEL: 10,
                GameState.CHARACTER_XP: 2000,
                GameState.CHARACTER_GOLD: 1000,
                GameState.HP_CURRENT: 100,
                GameState.HP_MAX: 120,
                GameState.CURRENT_X: 50,
                GameState.CURRENT_Y: 60,
                GameState.MINING_LEVEL: 8,
                GameState.WOODCUTTING_LEVEL: 7,
                GameState.FISHING_LEVEL: 6,
                GameState.WEAPONCRAFTING_LEVEL: 5,
                GameState.GEARCRAFTING_LEVEL: 4,
                GameState.JEWELRYCRAFTING_LEVEL: 3,
                GameState.COOKING_LEVEL: 2,
                GameState.ALCHEMY_LEVEL: 1,
                GameState.WEAPON_EQUIPPED: "masterwork_sword",
                GameState.TOOL_EQUIPPED: "masterwork_pickaxe",
                GameState.INVENTORY_SPACE_AVAILABLE: 15,
                GameState.COOLDOWN_READY: True,
                GameState.CAN_FIGHT: True,
                GameState.CAN_GATHER: True,
                GameState.CAN_CRAFT: True
            }

            # Verify all state keys are valid GameState enum values
            for key in test_changes.keys():
                assert isinstance(key, GameState)
                assert isinstance(key.value, str)

            # Test state update with comprehensive state
            await state_manager.update_state(test_changes)

    @pytest.mark.asyncio
    async def test_state_validation_comprehensive(self):
        """Test comprehensive state validation logic"""
        with patch('src.ai_player.state.state_manager.YamlData'):
            mock_api_client = Mock()
            mock_cache_manager = Mock()

            state_manager = StateManager("validation_test_char", mock_api_client, mock_cache_manager)

            # Test various invalid state combinations
            invalid_states = [
                # HP inconsistencies
                {
                    GameState.HP_CURRENT: 150,
                    GameState.HP_MAX: 100
                },
                # Negative levels
                {
                    GameState.CHARACTER_LEVEL: -5,
                    GameState.MINING_LEVEL: -1
                },
                # Skill levels higher than character level + reasonable buffer
                {
                    GameState.CHARACTER_LEVEL: 5,
                    GameState.MINING_LEVEL: 50  # Unreasonably high
                },
                # Inventory inconsistencies
                {
                    GameState.INVENTORY_SPACE_AVAILABLE: -5,
                    GameState.INVENTORY_SPACE_USED: 25
                }
            ]

            for invalid_state in invalid_states:
                is_consistent = await state_manager.validate_state_consistency(invalid_state)
                assert is_consistent is False, f"State should be invalid: {invalid_state}"

            # Test valid state
            valid_state = {
                GameState.CHARACTER_LEVEL: 10,
                GameState.HP_CURRENT: 95,
                GameState.HP_MAX: 100,
                GameState.MINING_LEVEL: 8,
                GameState.INVENTORY_SPACE_AVAILABLE: 15,
                GameState.INVENTORY_SPACE_USED: 5,
                GameState.COOLDOWN_READY: True
            }

            is_consistent = await state_manager.validate_state_consistency(valid_state)
            assert is_consistent is True

            # Test None state validation (covers _validate_state_rules with None)
            is_consistent_none = state_manager._validate_state_rules(None)
            assert is_consistent_none is False

            # Test exception handling in _validate_state_rules
            invalid_state = Mock()
            invalid_state.get.side_effect = Exception("Mock exception")
            is_consistent_exception = state_manager._validate_state_rules(invalid_state)
            assert is_consistent_exception is False

    @pytest.mark.asyncio
    async def test_validate_state_consistency_cache_vs_api(self):
        """Test state consistency validation comparing cache vs API"""
        with patch('src.ai_player.state.state_manager.YamlData'):
            mock_api_client = Mock()
            mock_cache_manager = Mock()

            state_manager = StateManager("cache_api_test_char", mock_api_client, mock_cache_manager)

            # Set up initial cached state
            state_manager._cached_state = {
                GameState.CHARACTER_LEVEL: 5,
                GameState.HP_CURRENT: 80,
                GameState.CURRENT_X: 10,
                GameState.CURRENT_Y: 15,
                GameState.CHARACTER_GOLD: 100,
                GameState.COOLDOWN_READY: True
            }

            # Mock API response to match cached state
            mock_character = Mock()
            mock_character.level = 5
            mock_character.xp = 1000
            mock_character.gold = 100
            mock_character.hp = 80
            mock_character.max_hp = 100
            mock_character.x = 10
            mock_character.y = 15
            mock_character.cooldown = 0
            mock_character.mining_level = 3
            mock_character.woodcutting_level = 2
            mock_character.fishing_level = 1
            mock_character.weaponcrafting_level = 1
            mock_character.gearcrafting_level = 1
            mock_character.jewelrycrafting_level = 1
            mock_character.cooking_level = 1
            mock_character.alchemy_level = 1
            mock_character.weapon_slot = "copper_sword"
            mock_character.inventory = ["item1", "item2"]
            mock_character.inventory_max_items = 20

            mock_api_client.get_character.return_value = mock_character

            with patch.object(CharacterGameState, 'from_api_character') as mock_from_api:
                mock_character_state = Mock()
                mock_character_state.to_goap_state.return_value = {
                    "character_level": 5,
                    "hp_current": 80,
                    "current_x": 10,
                    "current_y": 15,
                    "character_gold": 100,
                    "cooldown_ready": 1
                }
                mock_from_api.return_value = mock_character_state

                # Test that cache vs API validation works when called with None
                is_consistent = await state_manager.validate_state_consistency(None)
                assert isinstance(is_consistent, bool)

    @pytest.mark.asyncio
    async def test_validate_cache_vs_api_no_cached_state(self):
        """Test _validate_cache_vs_api when no cached state exists"""
        with patch('src.ai_player.state.state_manager.YamlData'):
            mock_api_client = Mock()
            mock_cache_manager = Mock()

            state_manager = StateManager("no_cache_test_char", mock_api_client, mock_cache_manager)

            # Ensure no cached state
            state_manager._cached_state = None

            # This should return False since there's no cached state
            is_consistent = await state_manager._validate_cache_vs_api()
            assert is_consistent is False

    @pytest.mark.asyncio
    async def test_validate_cache_vs_api_api_failure(self):
        """Test _validate_cache_vs_api when API call fails"""
        with patch('src.ai_player.state.state_manager.YamlData'):
            mock_api_client = Mock()
            mock_cache_manager = Mock()

            state_manager = StateManager("api_fail_test_char", mock_api_client, mock_cache_manager)

            # Set up cached state
            state_manager._cached_state = {GameState.CHARACTER_LEVEL: 5}

            # Mock API failure
            mock_api_client.get_character.side_effect = Exception("API failed")

            # This should return False due to API failure
            is_consistent = await state_manager._validate_cache_vs_api()
            assert is_consistent is False

    def test_get_cached_state_no_cache_no_file(self):
        """Test get_cached_state when no cached state and no file cache"""
        with patch('src.ai_player.state.state_manager.YamlData'):
            mock_api_client = Mock()
            mock_cache_manager = Mock()
            mock_cache_manager.load_character_state.return_value = None

            state_manager = StateManager("no_cache_file_test_char", mock_api_client, mock_cache_manager)

            # Ensure no cached state
            state_manager._cached_state = None

            # Should return empty dict when no cache exists
            cached_state = state_manager.get_cached_state()
            assert cached_state == {}

    def test_load_state_from_cache_yaml_fallback(self):
        """Test load_state_from_cache using YamlData fallback"""
        with patch('src.ai_player.state.state_manager.YamlData') as mock_yaml_class:
            mock_yaml_instance = Mock()
            mock_yaml_instance.data = {
                'data': [
                    {
                        'name': 'yaml_test_char',
                        'character_level': 5,
                        'hp_current': 80
                    }
                ]
            }
            mock_yaml_class.return_value = mock_yaml_instance

            mock_api_client = Mock()

            # Create state manager without cache manager to use YamlData fallback
            state_manager = StateManager("yaml_test_char", mock_api_client, None)

            # Mock the validation to convert string keys to GameState enums
            with patch('src.ai_player.state.game_state.GameState.validate_state_dict') as mock_validate:
                mock_validate.side_effect = lambda x: {
                    GameState.CHARACTER_LEVEL: x.get('character_level', 1), 
                    GameState.HP_CURRENT: x.get('hp_current', 1)
                }
                
                cached_state = state_manager.load_state_from_cache()
                assert cached_state is not None
                assert GameState.CHARACTER_LEVEL in cached_state
                assert cached_state[GameState.CHARACTER_LEVEL] == 5
                assert cached_state[GameState.HP_CURRENT] == 80

    def test_load_state_from_cache_yaml_no_data(self):
        """Test load_state_from_cache with YamlData when no data exists"""
        with patch('src.ai_player.state.state_manager.YamlData') as mock_yaml_class:
            mock_yaml_instance = Mock()
            mock_yaml_instance.data = {}  # No data
            mock_yaml_class.return_value = mock_yaml_instance

            mock_api_client = Mock()

            state_manager = StateManager("yaml_no_data_test_char", mock_api_client, None)

            cached_state = state_manager.load_state_from_cache()
            assert cached_state is None

    def test_load_state_from_cache_yaml_invalid_data(self):
        """Test load_state_from_cache with invalid cached data"""
        with patch('src.ai_player.state.state_manager.YamlData') as mock_yaml_class:
            mock_yaml_instance = Mock()
            mock_yaml_instance.data = {
                'character_state': {
                    'invalid_key': 'invalid_value'  # Invalid GameState key
                }
            }
            mock_yaml_class.return_value = mock_yaml_instance

            mock_api_client = Mock()

            state_manager = StateManager("yaml_invalid_test_char", mock_api_client, None)

            # Should return None for invalid cached data
            cached_state = state_manager.load_state_from_cache()
            assert cached_state is None

    def test_save_state_to_cache_yaml_fallback(self):
        """Test save_state_to_cache using YamlData fallback"""
        with patch('src.ai_player.state.state_manager.YamlData') as mock_yaml_class:
            mock_yaml_instance = Mock()
            mock_yaml_instance.data = {
                'data': [
                    {
                        'name': 'yaml_save_test_char',
                        'character_level': 3,
                        'hp_current': 75
                    }
                ]
            }
            mock_yaml_instance.save = Mock()
            mock_yaml_class.return_value = mock_yaml_instance

            mock_api_client = Mock()

            # Create state manager without cache manager to use YamlData fallback
            state_manager = StateManager("yaml_save_test_char", mock_api_client, None)

            test_state = {
                GameState.CHARACTER_LEVEL: 5,
                GameState.HP_CURRENT: 80
            }

            state_manager.save_state_to_cache(test_state)

            # Verify YamlData save was called (updates character data in place)
            mock_yaml_instance.save.assert_called_once()
            # Verify the character data was updated in the mock data structure
            characters = mock_yaml_instance.data['data']
            updated_char = next(c for c in characters if c['name'] == 'yaml_save_test_char')
            assert updated_char['character_level'] == 5  # Updated from test_state
            assert updated_char['hp_current'] == 80       # Updated from test_state

    def test_convert_api_to_goap_state(self):
        """Test convert_api_to_goap_state method"""
        with patch('src.ai_player.state.state_manager.YamlData'):
            mock_api_client = Mock()
            mock_cache_manager = Mock()

            state_manager = StateManager("convert_test_char", mock_api_client, mock_cache_manager)

            # Create mock character with all necessary attributes
            mock_character = Mock()
            mock_character.level = 10
            mock_character.xp = 2000
            mock_character.gold = 1000
            mock_character.hp = 95
            mock_character.max_hp = 100
            mock_character.x = 25
            mock_character.y = 30
            mock_character.cooldown = 0
            mock_character.mining_level = 8
            mock_character.mining_xp = 5000
            mock_character.woodcutting_level = 7
            mock_character.woodcutting_xp = 4000
            mock_character.fishing_level = 6
            mock_character.fishing_xp = 3000
            mock_character.weaponcrafting_level = 5
            mock_character.weaponcrafting_xp = 2500
            mock_character.gearcrafting_level = 4
            mock_character.gearcrafting_xp = 2000
            mock_character.jewelrycrafting_level = 3
            mock_character.jewelrycrafting_xp = 1500
            mock_character.cooking_level = 2
            mock_character.cooking_xp = 1000
            mock_character.alchemy_level = 1
            mock_character.alchemy_xp = 500
            mock_character.weapon_slot = "steel_sword"
            mock_character.helmet_slot = "steel_helmet"
            mock_character.body_armor_slot = "steel_armor"
            mock_character.leg_armor_slot = "steel_pants"
            mock_character.boots_slot = "steel_boots"
            mock_character.ring1_slot = "ruby_ring"
            mock_character.ring2_slot = "sapphire_ring"
            mock_character.amulet_slot = "gold_amulet"
            mock_character.inventory = ["item1", "item2", "item3"]
            mock_character.inventory_max_items = 20
            mock_character.task = "gather_wood"
            mock_character.task_progress = 5
            mock_character.task_total = 10

            state_dict = state_manager.convert_api_to_goap_state(mock_character)

            # Verify all expected keys are present
            assert state_dict[GameState.CHARACTER_LEVEL] == 10
            assert state_dict[GameState.CHARACTER_XP] == 2000
            assert state_dict[GameState.CHARACTER_GOLD] == 1000
            assert state_dict[GameState.HP_CURRENT] == 95
            assert state_dict[GameState.HP_MAX] == 100
            assert state_dict[GameState.CURRENT_X] == 25
            assert state_dict[GameState.CURRENT_Y] == 30
            assert state_dict[GameState.MINING_LEVEL] == 8
            assert state_dict[GameState.MINING_XP] == 5000
            assert state_dict[GameState.WOODCUTTING_LEVEL] == 7
            assert state_dict[GameState.WEAPON_EQUIPPED] == "steel_sword"
            assert state_dict[GameState.HELMET_EQUIPPED] == "steel_helmet"
            assert state_dict[GameState.INVENTORY_SPACE_AVAILABLE] == 17  # 20 - 3
            assert state_dict[GameState.INVENTORY_SPACE_USED] == 3
            assert state_dict[GameState.INVENTORY_FULL] is False
            assert state_dict[GameState.ACTIVE_TASK] == "gather_wood"
            assert state_dict[GameState.TASK_PROGRESS] == 5
            assert state_dict[GameState.TASK_COMPLETED] is False
            assert state_dict[GameState.COOLDOWN_READY] is True
            assert state_dict[GameState.CAN_FIGHT] is True
            assert state_dict[GameState.CAN_GATHER] is True
            assert state_dict[GameState.HP_LOW] is False
            assert state_dict[GameState.HP_CRITICAL] is False
            assert state_dict[GameState.SAFE_TO_FIGHT] is True
            assert state_dict[GameState.IN_COMBAT] is False

    def test_get_state_diff(self):
        """Test get_state_diff method"""
        with patch('src.ai_player.state.state_manager.YamlData'):
            mock_api_client = Mock()
            mock_cache_manager = Mock()

            state_manager = StateManager("diff_test_char", mock_api_client, mock_cache_manager)

            old_state = {
                GameState.CHARACTER_LEVEL: 5,
                GameState.HP_CURRENT: 80,
                GameState.CURRENT_X: 10,
                GameState.CHARACTER_GOLD: 100
            }

            new_state = {
                GameState.CHARACTER_LEVEL: 6,  # Changed
                GameState.HP_CURRENT: 80,     # Same
                GameState.CURRENT_Y: 15,      # New key
                GameState.CHARACTER_GOLD: 150 # Changed
                # CURRENT_X removed
            }

            diff = state_manager.get_state_diff(old_state, new_state)

            # Should include changed and new values, plus None for removed keys
            assert diff[GameState.CHARACTER_LEVEL] == 6
            assert diff[GameState.CURRENT_Y] == 15
            assert diff[GameState.CHARACTER_GOLD] == 150
            assert diff[GameState.CURRENT_X] is None
            assert GameState.HP_CURRENT not in diff  # Unchanged values not in diff

    def test_get_state_value_sync(self):
        """Test get_state_value_sync method"""
        with patch('src.ai_player.state.state_manager.YamlData'):
            mock_api_client = Mock()
            mock_cache_manager = Mock()

            state_manager = StateManager("sync_get_test_char", mock_api_client, mock_cache_manager)

            # Test with no cached state
            value = state_manager.get_state_value_sync(GameState.CHARACTER_LEVEL)
            assert value is None

            # Test with cached state
            state_manager._cached_state = {
                GameState.CHARACTER_LEVEL: 8,
                GameState.HP_CURRENT: 90
            }

            level = state_manager.get_state_value_sync(GameState.CHARACTER_LEVEL)
            assert level == 8

            # Test missing key
            missing = state_manager.get_state_value_sync(GameState.MINING_LEVEL)
            assert missing is None

    def test_set_state_value_sync(self):
        """Test set_state_value_sync method"""
        with patch('src.ai_player.state.state_manager.YamlData'):
            mock_api_client = Mock()
            mock_cache_manager = Mock()

            state_manager = StateManager("sync_set_test_char", mock_api_client, mock_cache_manager)

            # Test setting value when no cached state
            state_manager.set_state_value_sync(GameState.CHARACTER_LEVEL, 10)
            assert state_manager._cached_state[GameState.CHARACTER_LEVEL] == 10

            # Test setting another value
            state_manager.set_state_value_sync(GameState.HP_CURRENT, 85)
            assert state_manager._cached_state[GameState.HP_CURRENT] == 85
            assert state_manager._cached_state[GameState.CHARACTER_LEVEL] == 10  # Previous value preserved

    def test_get_cached_state_with_file_cache_fallback(self):
        """Test get_cached_state when it loads from file cache"""
        with patch('src.ai_player.state.state_manager.YamlData') as mock_yaml_class:
            mock_yaml_instance = Mock()
            mock_yaml_instance.data = {
                'data': [
                    {
                        'name': 'file_cache_test_char',
                        'character_level': 8,
                        'hp_current': 90
                    }
                ]
            }
            mock_yaml_class.return_value = mock_yaml_instance
            
            mock_api_client = Mock()
            mock_cache_manager = Mock()

            state_manager = StateManager("file_cache_test_char", mock_api_client, mock_cache_manager)

            # Ensure no in-memory cached state
            state_manager._cached_state = None

            # Mock the validation to convert string keys to GameState enums  
            with patch('src.ai_player.state.game_state.GameState.validate_state_dict') as mock_validate:
                mock_validate.side_effect = lambda x: {
                    GameState.CHARACTER_LEVEL: x.get('character_level', 1), 
                    GameState.HP_CURRENT: x.get('hp_current', 1)
                }
                
                # Should load from file cache and set _cached_state
                cached_state = state_manager.get_cached_state()
                assert cached_state is not None
                assert GameState.CHARACTER_LEVEL in cached_state
                assert cached_state[GameState.CHARACTER_LEVEL] == 8
                assert state_manager._cached_state is not None  # Should be set after loading

    @pytest.mark.asyncio
    async def test_validate_cache_vs_api_with_state_mismatch(self):
        """Test _validate_cache_vs_api when cached and API state differ"""
        with patch('src.ai_player.state.state_manager.YamlData'):
            mock_api_client = Mock()
            mock_cache_manager = Mock()

            state_manager = StateManager("mismatch_test_char", mock_api_client, mock_cache_manager)

            # Set up cached state
            state_manager._cached_state = {
                GameState.CHARACTER_LEVEL: 5,
                GameState.HP_CURRENT: 80,
                GameState.CURRENT_X: 10,
                GameState.CURRENT_Y: 15,
                GameState.CHARACTER_GOLD: 100,
                GameState.COOLDOWN_READY: True
            }

            # Mock API response with different values
            mock_character = Mock()
            mock_character.level = 6  # Different level
            mock_character.xp = 1500
            mock_character.gold = 150  # Different gold
            mock_character.hp = 80
            mock_character.max_hp = 100
            mock_character.x = 10
            mock_character.y = 15
            mock_character.cooldown = 0
            mock_character.mining_level = 3
            mock_character.woodcutting_level = 2
            mock_character.fishing_level = 1
            mock_character.weaponcrafting_level = 1
            mock_character.gearcrafting_level = 1
            mock_character.jewelrycrafting_level = 1
            mock_character.cooking_level = 1
            mock_character.alchemy_level = 1
            mock_character.weapon_slot = "copper_sword"
            mock_character.inventory = ["item1", "item2"]
            mock_character.inventory_max_items = 20

            mock_api_client.get_character.return_value = mock_character

            with patch.object(CharacterGameState, 'from_api_character') as mock_from_api:
                mock_character_state = Mock()
                mock_character_state.to_goap_state.return_value = {
                    "character_level": 6,  # Different from cached
                    "hp_current": 80,
                    "current_x": 10,
                    "current_y": 15,
                    "character_gold": 150,  # Different from cached
                    "cooldown_ready": 1
                }
                mock_from_api.return_value = mock_character_state

                # Should return False due to state mismatch
                is_consistent = await state_manager._validate_cache_vs_api()
                assert is_consistent is False
