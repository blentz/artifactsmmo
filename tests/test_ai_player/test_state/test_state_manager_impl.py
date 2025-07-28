"""
Tests for StateManager implementation

This module tests the actual implemented StateManager functionality with proper
API integration, GameState enum usage, and Pydantic validation.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.ai_player.state.game_state import ActionResult, CharacterGameState, CooldownInfo, GameState
from src.ai_player.state.state_manager import StateManager
from src.game_data.api_client import APIClientWrapper


class TestStateManagerImplementation:
    """Test actual StateManager implementation"""

    @pytest.fixture
    def mock_api_client(self):
        """Mock API client for testing"""
        client = Mock(spec=APIClientWrapper)
        client.get_character = AsyncMock()
        return client

    @pytest.fixture
    def mock_character_data(self):
        """Mock character data from API"""
        character = Mock()
        character.level = 5
        character.xp = 1000
        character.gold = 500
        character.hp = 80
        character.max_hp = 100
        character.x = 10
        character.y = 15
        character.cooldown = 0
        character.mining_level = 3
        character.mining_xp = 250
        character.woodcutting_level = 2
        character.woodcutting_xp = 150
        character.fishing_level = 1
        character.fishing_xp = 50
        character.weaponcrafting_level = 1
        character.weaponcrafting_xp = 0
        character.gearcrafting_level = 1
        character.gearcrafting_xp = 0
        character.jewelrycrafting_level = 1
        character.jewelrycrafting_xp = 0
        character.cooking_level = 1
        character.cooking_xp = 0
        character.alchemy_level = 1
        character.alchemy_xp = 0
        character.weapon_slot = "copper_sword"
        character.helmet_slot = ""
        character.body_armor_slot = ""
        character.leg_armor_slot = ""
        character.boots_slot = ""
        character.ring1_slot = ""
        character.ring2_slot = ""
        character.amulet_slot = ""
        character.task = ""
        character.task_progress = 0
        character.task_total = 0
        character.inventory_max_items = 20
        # Mock inventory attribute handling
        character.inventory = []
        return character

    @pytest.fixture
    def state_manager(self, mock_api_client):
        """Create StateManager instance for testing"""
        with patch('src.ai_player.state.state_manager.YamlData'):
            return StateManager("test_character", mock_api_client)

    def test_initialization(self, state_manager, mock_api_client):
        """Test StateManager initialization"""
        assert state_manager.character_name == "test_character"
        assert state_manager.api_client == mock_api_client
        assert state_manager._cached_state is None
        assert hasattr(state_manager, '_characters_cache')

    @pytest.mark.asyncio
    async def test_update_state_from_api(self, state_manager, mock_api_client, mock_character_data):
        """Test updating state from API"""
        mock_api_client.get_character.return_value = mock_character_data

        result = await state_manager.update_state_from_api()

        assert isinstance(result, CharacterGameState)
        assert result.level == 5
        assert result.hp == 80
        assert result.x == 10
        assert result.y == 15
        mock_api_client.get_character.assert_called_once_with("test_character")

    @pytest.mark.asyncio
    async def test_get_current_state(self, state_manager, mock_api_client, mock_character_data):
        """Test getting current state"""
        mock_api_client.get_character.return_value = mock_character_data

        with patch.object(GameState, 'validate_state_dict') as mock_validate:
            mock_validate.return_value = {
                GameState.CHARACTER_LEVEL: 5,
                GameState.HP_CURRENT: 80,
                GameState.CURRENT_X: 10,
                GameState.CURRENT_Y: 15,
                GameState.COOLDOWN_READY: True
            }

            result = await state_manager.get_current_state()

            assert isinstance(result, dict)
            assert result[GameState.CHARACTER_LEVEL] == 5
            assert result[GameState.HP_CURRENT] == 80
            assert result[GameState.COOLDOWN_READY] is True
            mock_validate.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_current_state_with_cache(self, state_manager):
        """Test getting current state when cache is available"""
        cached_state = {
            GameState.CHARACTER_LEVEL: 6,
            GameState.HP_CURRENT: 90
        }

        with patch.object(state_manager, 'load_state_from_cache', return_value=cached_state):
            result = await state_manager.get_current_state()

            assert result == cached_state
            assert state_manager._cached_state == cached_state

    def test_convert_api_to_goap_state(self, state_manager, mock_character_data):
        """Test converting API character to GOAP state"""
        result = state_manager.convert_api_to_goap_state(mock_character_data)

        assert isinstance(result, dict)
        assert result[GameState.CHARACTER_LEVEL] == 5
        assert result[GameState.HP_CURRENT] == 80
        assert result[GameState.HP_MAX] == 100
        assert result[GameState.CURRENT_X] == 10
        assert result[GameState.CURRENT_Y] == 15
        assert result[GameState.MINING_LEVEL] == 3
        assert result[GameState.COOLDOWN_READY] is True
        assert result[GameState.CAN_FIGHT] is True
        assert result[GameState.HP_LOW] is False  # 80 > 30% of 100
        assert result[GameState.SAFE_TO_FIGHT] is True  # 80 > 50% of 100

    def test_get_state_value(self, state_manager):
        """Test getting specific state value"""
        # Set up cached state
        state_manager._cached_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_CURRENT: 80
        }

        assert state_manager.get_state_value_sync(GameState.CHARACTER_LEVEL) == 5
        assert state_manager.get_state_value_sync(GameState.HP_CURRENT) == 80
        assert state_manager.get_state_value_sync(GameState.MINING_LEVEL) is None

    def test_get_state_value_no_cache(self, state_manager):
        """Test getting state value when no cache exists"""
        assert state_manager.get_state_value_sync(GameState.CHARACTER_LEVEL) is None

    def test_set_state_value(self, state_manager):
        """Test setting specific state value"""
        state_manager.set_state_value_sync(GameState.CHARACTER_LEVEL, 6)

        assert state_manager._cached_state[GameState.CHARACTER_LEVEL] == 6

    def test_set_state_value_no_initial_cache(self, state_manager):
        """Test setting state value when no cache exists"""
        state_manager.set_state_value_sync(GameState.HP_CURRENT, 90)

        assert state_manager._cached_state is not None
        assert state_manager._cached_state[GameState.HP_CURRENT] == 90

    def test_get_state_value_sync_no_cache(self, state_manager):
        """Test getting state value sync when no cache exists"""
        state_manager._cached_state = None
        result = state_manager.get_state_value_sync(GameState.CHARACTER_LEVEL)
        assert result is None

    def test_get_state_value_sync_with_cache(self, state_manager):
        """Test getting state value sync when cache exists"""
        state_manager._cached_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_CURRENT: 80
        }
        result = state_manager.get_state_value_sync(GameState.CHARACTER_LEVEL)
        assert result == 5

    def test_set_state_value_sync_no_initial_cache(self, state_manager):
        """Test setting state value sync when no cache exists"""
        state_manager._cached_state = None
        state_manager.set_state_value_sync(GameState.HP_CURRENT, 90)

        assert state_manager._cached_state is not None
        assert state_manager._cached_state[GameState.HP_CURRENT] == 90

    def test_get_state_diff(self, state_manager):
        """Test calculating state differences"""
        old_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_CURRENT: 80,
            GameState.CURRENT_X: 10
        }

        new_state = {
            GameState.CHARACTER_LEVEL: 6,  # Changed
            GameState.HP_CURRENT: 80,     # Same
            GameState.CURRENT_Y: 15       # New key, old key removed
        }

        diff = state_manager.get_state_diff(old_state, new_state)

        assert diff[GameState.CHARACTER_LEVEL] == 6  # Changed value
        assert diff[GameState.CURRENT_Y] == 15       # New value
        assert diff[GameState.CURRENT_X] is None     # Removed key
        assert GameState.HP_CURRENT not in diff     # Unchanged value

    def test_update_state_from_result(self, state_manager):
        """Test updating state from action result"""
        action_result = ActionResult(
            success=True,
            message="Action completed",
            state_changes={
                GameState.CURRENT_X: 20,
                GameState.HP_CURRENT: 75
            },
            cooldown_seconds=5
        )

        state_manager.update_state_from_result(action_result)

        assert state_manager._cached_state[GameState.CURRENT_X] == 20
        assert state_manager._cached_state[GameState.HP_CURRENT] == 75
        assert state_manager._cached_state[GameState.COOLDOWN_READY] is False
        assert state_manager._cached_state[GameState.CAN_FIGHT] is False

    def test_update_state_from_result_no_cooldown(self, state_manager):
        """Test updating state from action result with no cooldown"""
        action_result = ActionResult(
            success=True,
            message="Action completed",
            state_changes={
                GameState.CURRENT_X: 20
            },
            cooldown_seconds=0
        )

        state_manager.update_state_from_result(action_result)

        assert state_manager._cached_state[GameState.CURRENT_X] == 20
        # Should not set cooldown states when cooldown_seconds is 0
        assert GameState.COOLDOWN_READY not in state_manager._cached_state

    def test_get_cached_state_with_cache(self, state_manager):
        """Test getting cached state when cache exists"""
        state_manager._cached_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_CURRENT: 80
        }

        result = state_manager.get_cached_state()

        assert isinstance(result, dict)
        assert result[GameState.CHARACTER_LEVEL] == 5
        assert result[GameState.HP_CURRENT] == 80
        # Should return a copy, not the original
        assert result is not state_manager._cached_state

    def test_get_cached_state_no_cache(self, state_manager):
        """Test getting cached state when no cache exists"""
        with patch.object(state_manager, 'load_state_from_cache', return_value=None):
            result = state_manager.get_cached_state()
            assert result == {}

    def test_get_cached_state_loads_from_file(self, state_manager):
        """Test getting cached state loads from file cache"""
        file_cache_data = {
            GameState.CHARACTER_LEVEL: 3,
            GameState.HP_CURRENT: 60
        }

        with patch.object(state_manager, 'load_state_from_cache', return_value=file_cache_data):
            result = state_manager.get_cached_state()

            assert result == file_cache_data
            assert state_manager._cached_state == file_cache_data

    @pytest.mark.asyncio
    async def test_validate_state_consistency_matching(self, state_manager):
        """Test state consistency validation when states match"""
        state_manager._cached_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_CURRENT: 80,
            GameState.CURRENT_X: 10,
            GameState.CURRENT_Y: 15,
            GameState.CHARACTER_GOLD: 500,
            GameState.COOLDOWN_READY: True
        }

        # Mock get_current_state to return same values for critical keys
        with patch.object(state_manager, 'get_current_state', return_value=state_manager._cached_state):
            result = await state_manager.validate_state_consistency()
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_state_consistency_different(self, state_manager):
        """Test state consistency validation when states differ"""
        state_manager._cached_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_CURRENT: 80,
            GameState.CURRENT_X: 10,
            GameState.CURRENT_Y: 15,
            GameState.CHARACTER_GOLD: 500,
            GameState.COOLDOWN_READY: True
        }

        # Mock get_current_state to return different values
        fresh_state = state_manager._cached_state.copy()
        fresh_state[GameState.CHARACTER_LEVEL] = 6  # Different level

        with patch.object(state_manager, 'get_current_state', return_value=fresh_state):
            result = await state_manager.validate_state_consistency()
            assert result is False

    @pytest.mark.asyncio
    async def test_validate_state_consistency_no_cache(self, state_manager):
        """Test state consistency validation when no cache exists"""
        result = await state_manager.validate_state_consistency()
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_state_consistency_api_error(self, state_manager):
        """Test state consistency validation when API call fails"""
        state_manager._cached_state = {GameState.CHARACTER_LEVEL: 5}

        with patch.object(state_manager, 'get_current_state', side_effect=Exception("API error")):
            result = await state_manager.validate_state_consistency()
            assert result is False

    @pytest.mark.asyncio
    async def test_validate_state_consistency_with_provided_state_valid(self, state_manager):
        """Test state consistency validation with valid provided state"""
        valid_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_CURRENT: 80,
            GameState.HP_MAX: 100,
            GameState.MINING_LEVEL: 3,
            GameState.INVENTORY_SPACE_AVAILABLE: 10,
            GameState.INVENTORY_SPACE_USED: 5
        }
        
        result = await state_manager.validate_state_consistency(valid_state)
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_state_consistency_with_provided_state_invalid_hp(self, state_manager):
        """Test state consistency validation with invalid HP values"""
        invalid_state = {
            GameState.HP_CURRENT: 150,  # More than max
            GameState.HP_MAX: 100
        }
        
        result = await state_manager.validate_state_consistency(invalid_state)
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_state_consistency_with_provided_state_negative_level(self, state_manager):
        """Test state consistency validation with negative level"""
        invalid_state = {
            GameState.CHARACTER_LEVEL: -1  # Negative level
        }
        
        result = await state_manager.validate_state_consistency(invalid_state)
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_state_consistency_with_provided_state_negative_inventory(self, state_manager):
        """Test state consistency validation with negative inventory values"""
        invalid_state = {
            GameState.INVENTORY_SPACE_AVAILABLE: -5,  # Negative inventory
            GameState.INVENTORY_SPACE_USED: 10
        }
        
        result = await state_manager.validate_state_consistency(invalid_state)
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_state_consistency_with_provided_state_skill_level_too_high(self, state_manager):
        """Test state consistency validation with skill level too high"""
        invalid_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.MINING_LEVEL: 20  # Much higher than character level + buffer
        }
        
        result = await state_manager.validate_state_consistency(invalid_state)
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_state_consistency_with_provided_state_none(self, state_manager):
        """Test state consistency validation with None state"""
        result = await state_manager.validate_state_consistency(None)
        assert result is False

    def test_validate_state_rules_with_none_direct(self, state_manager):
        """Test _validate_state_rules method directly with None"""
        result = state_manager._validate_state_rules(None)
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_state_consistency_validation_exception(self, state_manager):
        """Test state consistency validation when validation raises exception"""
        # Use Mock() to simulate an object that will cause an exception in validation
        invalid_state = Mock()
        invalid_state.get = Mock(side_effect=Exception("Mock exception"))
        
        result = await state_manager.validate_state_consistency(invalid_state)
        assert result is False

    @pytest.mark.asyncio
    async def test_force_refresh(self, state_manager, mock_api_client, mock_character_data):
        """Test force refresh from API"""
        # Set up some cached state
        state_manager._cached_state = {GameState.CHARACTER_LEVEL: 4}

        mock_api_client.get_character.return_value = mock_character_data

        with patch.object(state_manager, 'save_state_to_cache') as mock_save:
            with patch.object(GameState, 'validate_state_dict') as mock_validate:
                mock_validate.return_value = {GameState.CHARACTER_LEVEL: 5}

                result = await state_manager.force_refresh()

                # Cache should be cleared and refreshed
                assert result == {GameState.CHARACTER_LEVEL: 5}
                mock_save.assert_called_once_with({GameState.CHARACTER_LEVEL: 5})

    def test_save_state_to_cache(self, state_manager):
        """Test saving state to cache"""
        # Set up the centralized cache data structure
        state_manager._characters_cache.data = {
            "data": [
                {
                    "name": "test_character",
                    "character_level": 3,
                    "hp_current": 75
                }
            ]
        }
        
        state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_CURRENT: 80
        }

        with patch.object(state_manager._characters_cache, 'save') as mock_save:
            state_manager.save_state_to_cache(state)

            # Verify the character data was updated
            characters = state_manager._characters_cache.data["data"]
            updated_char = next(c for c in characters if c["name"] == "test_character")
            assert updated_char["character_level"] == 5
            assert updated_char["hp_current"] == 80
            
            # Verify save was called
            mock_save.assert_called_once()

    def test_load_state_from_cache_success(self, state_manager):
        """Test loading state from cache successfully"""
        cache_data = {
            "character_level": 5,
            "hp_current": 80
        }

        state_manager._characters_cache.data = {
            "data": [
                {
                    "name": "test_character",
                    "character_level": 5,
                    "hp_current": 80
                }
            ]
        }

        with patch.object(GameState, 'validate_state_dict') as mock_validate:
            mock_validate.return_value = {
                GameState.CHARACTER_LEVEL: 5,
                GameState.HP_CURRENT: 80
            }

            result = state_manager.load_state_from_cache()

            assert result == {GameState.CHARACTER_LEVEL: 5, GameState.HP_CURRENT: 80}
            # validate_state_dict should be called with the character object
            expected_character = {"name": "test_character", "character_level": 5, "hp_current": 80}
            mock_validate.assert_called_once_with(expected_character)

    def test_load_state_from_cache_no_data(self, state_manager):
        """Test loading state from cache when no data exists"""
        state_manager._characters_cache.data = None

        result = state_manager.load_state_from_cache()
        assert result is None

    def test_load_state_from_cache_no_character_state(self, state_manager):
        """Test loading state from cache when data key missing"""
        state_manager._characters_cache.data = {"other_data": "value"}

        result = state_manager.load_state_from_cache()
        assert result is None

    def test_load_state_from_cache_invalid_data(self, state_manager):
        """Test loading state from cache with invalid data"""
        cache_data = {"invalid_key": "invalid_value"}
        state_manager._characters_cache.data = {
            "data": [
                {
                    "name": "test_character",
                    **cache_data
                }
            ]
        }

        with patch.object(GameState, 'validate_state_dict', side_effect=ValueError("Invalid key")):
            result = state_manager.load_state_from_cache()
            assert result is None

    def test_save_state_to_cache_with_centralized_yaml(self, state_manager):
        """Test saving state to centralized YAML cache"""
        # Set up the centralized cache data structure
        state_manager._characters_cache.data = {
            "data": [
                {
                    "name": "test_character",
                    "character_level": 3,
                    "hp_current": 75
                }
            ]
        }
        
        state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_CURRENT: 80
        }
        
        state_manager.save_state_to_cache(state)
        
        # Verify the character data was updated in place
        characters = state_manager._characters_cache.data["data"]
        updated_char = next(c for c in characters if c["name"] == "test_character")
        assert updated_char["character_level"] == 5
        assert updated_char["hp_current"] == 80
        
        # Verify save was called
        state_manager._characters_cache.save.assert_called_once()

    def test_load_state_from_cache_with_centralized_yaml(self, state_manager):
        """Test loading state from centralized YAML cache"""
        # Set up the centralized cache data structure
        state_manager._characters_cache.data = {
            "data": [
                {
                    "name": "test_character",
                    "character_level": 5,
                    "hp_current": 80
                }
            ]
        }
        
        with patch.object(GameState, 'validate_state_dict') as mock_validate:
            mock_validate.return_value = {
                GameState.CHARACTER_LEVEL: 5,
                GameState.HP_CURRENT: 80
            }
            
            result = state_manager.load_state_from_cache()
            
            assert result == {GameState.CHARACTER_LEVEL: 5, GameState.HP_CURRENT: 80}
            # Verify validation was called with the character object
            expected_character = {"name": "test_character", "character_level": 5, "hp_current": 80}
            mock_validate.assert_called_once_with(expected_character)

    def test_load_state_from_cache_no_character_found(self, state_manager):
        """Test loading state from cache when character not found"""
        # Set up cache with other characters but not test_character
        state_manager._characters_cache.data = {
            "data": [
                {
                    "name": "other_character",
                    "character_level": 5,
                    "hp_current": 80
                }
            ]
        }
        
        result = state_manager.load_state_from_cache()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_state_value(self, state_manager):
        """Test getting specific state value async"""
        state_manager._cached_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_CURRENT: 80
        }
        
        with patch.object(state_manager, 'get_current_state', return_value=state_manager._cached_state):
            result = await state_manager.get_state_value(GameState.CHARACTER_LEVEL)
            assert result == 5

    @pytest.mark.asyncio
    async def test_set_state_value(self, state_manager):
        """Test setting specific state value async"""
        with patch.object(state_manager, 'save_state_to_cache') as mock_save:
            await state_manager.set_state_value(GameState.CHARACTER_LEVEL, 6)
            
            assert state_manager._cached_state[GameState.CHARACTER_LEVEL] == 6
            mock_save.assert_called_once_with(state_manager._cached_state)

    @pytest.mark.asyncio
    async def test_set_state_value_no_initial_cache(self, state_manager):
        """Test setting state value when no cache exists async"""
        with patch.object(state_manager, 'save_state_to_cache') as mock_save:
            await state_manager.set_state_value(GameState.HP_CURRENT, 90)
            
            assert state_manager._cached_state is not None
            assert state_manager._cached_state[GameState.HP_CURRENT] == 90
            mock_save.assert_called_once_with(state_manager._cached_state)

    @pytest.mark.asyncio
    async def test_update_state(self, state_manager):
        """Test updating state with multiple changes"""
        state_changes = {
            GameState.CHARACTER_LEVEL: 6,
            GameState.HP_CURRENT: 85
        }
        
        with patch.object(state_manager, 'save_state_to_cache') as mock_save:
            await state_manager.update_state(state_changes)
            
            assert state_manager._cached_state[GameState.CHARACTER_LEVEL] == 6
            assert state_manager._cached_state[GameState.HP_CURRENT] == 85
            mock_save.assert_called_once_with(state_manager._cached_state)

    @pytest.mark.asyncio
    async def test_update_state_invalid_key(self, state_manager):
        """Test updating state with invalid key raises exception"""
        state_changes = {
            "invalid_key": 6  # String key instead of GameState enum
        }
        
        with pytest.raises(ValueError, match="Invalid state key"):
            await state_manager.update_state(state_changes)

    @pytest.mark.asyncio
    async def test_sync_with_api(self, state_manager, mock_api_client, mock_character_data):
        """Test synchronizing with API"""
        mock_api_client.get_character.return_value = mock_character_data
        
        with patch.object(state_manager, 'save_state_to_cache') as mock_save:
            with patch.object(GameState, 'validate_state_dict') as mock_validate:
                mock_validate.return_value = {GameState.CHARACTER_LEVEL: 5}
                
                result = await state_manager.sync_with_api()
                
                assert result == {GameState.CHARACTER_LEVEL: 5}
                assert state_manager._cached_state == {GameState.CHARACTER_LEVEL: 5}
                mock_save.assert_called_once_with({GameState.CHARACTER_LEVEL: 5})

    @pytest.mark.asyncio
    async def test_apply_action_result(self, state_manager):
        """Test applying action result"""
        action_result = ActionResult(
            success=True,
            message="Action completed",
            state_changes={
                GameState.CURRENT_X: 20,
                GameState.HP_CURRENT: 75
            },
            cooldown_seconds=5
        )
        
        with patch.object(state_manager, 'save_state_to_cache') as mock_save:
            await state_manager.apply_action_result(action_result)
            
            assert state_manager._cached_state[GameState.CURRENT_X] == 20
            assert state_manager._cached_state[GameState.HP_CURRENT] == 75
            assert state_manager._cached_state[GameState.COOLDOWN_READY] is False
            mock_save.assert_called_once_with(state_manager._cached_state)

    @pytest.mark.asyncio
    async def test_apply_action_result_no_cache(self, state_manager):
        """Test applying action result when cache is None"""
        state_manager._cached_state = None
        
        action_result = ActionResult(
            success=True,
            message="Action completed",
            state_changes={GameState.CURRENT_X: 20},
            cooldown_seconds=0
        )
        
        with patch.object(state_manager, 'save_state_to_cache'):
            await state_manager.apply_action_result(action_result)
            # Should not try to save when cache is None after update_state_from_result

    @pytest.mark.asyncio
    async def test_refresh_state_from_api(self, state_manager, mock_api_client, mock_character_data):
        """Test refresh state from API (alias for force_refresh)"""
        mock_api_client.get_character.return_value = mock_character_data
        
        with patch.object(state_manager, 'force_refresh') as mock_force_refresh:
            mock_force_refresh.return_value = {GameState.CHARACTER_LEVEL: 5}
            
            result = await state_manager.refresh_state_from_api()
            
            assert result == {GameState.CHARACTER_LEVEL: 5}
            mock_force_refresh.assert_called_once()


class TestCharacterGameState:
    """Test CharacterGameState model"""

    @pytest.fixture
    def mock_character_data(self):
        """Mock character data for testing"""
        character = Mock()
        character.level = 5
        character.xp = 1000
        character.gold = 500
        character.hp = 80
        character.max_hp = 100
        character.x = 10
        character.y = 15
        character.cooldown = 0
        character.mining_level = 3
        character.mining_xp = 250
        character.woodcutting_level = 2
        character.woodcutting_xp = 150
        character.fishing_level = 1
        character.fishing_xp = 50
        character.weaponcrafting_level = 1
        character.weaponcrafting_xp = 0
        character.gearcrafting_level = 1
        character.gearcrafting_xp = 0
        character.jewelrycrafting_level = 1
        character.jewelrycrafting_xp = 0
        character.cooking_level = 1
        character.cooking_xp = 0
        character.alchemy_level = 1
        character.alchemy_xp = 0
        return character

    def test_from_api_character(self, mock_character_data):
        """Test creating CharacterGameState from API character"""
        result = CharacterGameState.from_api_character(mock_character_data)

        assert isinstance(result, CharacterGameState)
        assert result.level == 5
        assert result.hp == 80
        assert result.max_hp == 100
        assert result.x == 10
        assert result.y == 15
        assert result.mining_level == 3
        assert result.cooldown == 0
        assert result.cooldown_ready is True

    def test_to_goap_state(self, mock_character_data):
        """Test converting CharacterGameState to GOAP state"""
        character_state = CharacterGameState.from_api_character(mock_character_data)
        result = character_state.to_goap_state()

        assert isinstance(result, dict)
        assert all(isinstance(key, str) for key in result.keys())
        assert result["character_level"] == 5
        assert result["hp_current"] == 80
        assert result["current_x"] == 10
        assert result["mining_level"] == 3

    def test_validation_constraints(self):
        """Test Pydantic validation constraints"""
        # Valid data should work
        valid_data = {
            "level": 5,
            "xp": 1000,
            "gold": 500,
            "hp": 80,
            "max_hp": 100,
            "x": 10,
            "y": 15,
            "mining_level": 3,
            "mining_xp": 250,
            "woodcutting_level": 2,
            "woodcutting_xp": 150,
            "fishing_level": 1,
            "fishing_xp": 50,
            "weaponcrafting_level": 1,
            "weaponcrafting_xp": 0,
            "gearcrafting_level": 1,
            "gearcrafting_xp": 0,
            "jewelrycrafting_level": 1,
            "jewelrycrafting_xp": 0,
            "cooking_level": 1,
            "cooking_xp": 0,
            "alchemy_level": 1,
            "alchemy_xp": 0,
            "cooldown": 0,
            "cooldown_ready": True
        }

        state = CharacterGameState(**valid_data)
        assert state.level == 5

        # Test validation constraints
        with pytest.raises(Exception):  # Should fail with level 0
            CharacterGameState(**{**valid_data, "level": 0})

        with pytest.raises(Exception):  # Should fail with negative HP
            CharacterGameState(**{**valid_data, "hp": -10})


class TestGameStateEnum:
    """Test GameState enum functionality"""

    def test_validate_state_dict_valid(self):
        """Test validating valid state dictionary"""
        state_dict = {
            "character_level": 5,
            "hp_current": 80,
            "current_x": 10
        }

        result = GameState.validate_state_dict(state_dict)

        assert isinstance(result, dict)
        assert GameState.CHARACTER_LEVEL in result
        assert GameState.HP_CURRENT in result
        assert GameState.CURRENT_X in result
        assert result[GameState.CHARACTER_LEVEL] == 5

    def test_validate_state_dict_invalid_key(self):
        """Test validating state dictionary with invalid key"""
        state_dict = {
            "character_level": 5,
            "invalid_key": 10
        }

        with pytest.raises(ValueError, match="Invalid GameState key"):
            GameState.validate_state_dict(state_dict)

    def test_to_goap_dict(self):
        """Test converting enum-keyed dict to string-keyed dict"""
        state_dict = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_CURRENT: 80,
            GameState.CURRENT_X: 10
        }

        result = GameState.to_goap_dict(state_dict)

        assert isinstance(result, dict)
        assert all(isinstance(key, str) for key in result.keys())
        assert result["character_level"] == 5
        assert result["hp_current"] == 80
        assert result["current_x"] == 10


class TestCooldownInfo:
    """Test CooldownInfo model and properties"""

    def test_is_ready_expired(self):
        """Test cooldown is ready when expired"""

        # Create cooldown that expired 10 seconds ago
        past_time = datetime.now() - timedelta(seconds=10)
        cooldown = CooldownInfo(
            character_name="test_char",
            expiration=past_time.isoformat(),
            total_seconds=30,
            remaining_seconds=0,
            reason="test"
        )

        assert cooldown.is_ready is True

    def test_is_ready_not_expired(self):
        """Test cooldown is not ready when not expired"""

        # Create cooldown that expires in 10 seconds
        future_time = datetime.now() + timedelta(seconds=10)
        cooldown = CooldownInfo(
            character_name="test_char",
            expiration=future_time.isoformat(),
            total_seconds=30,
            remaining_seconds=10,
            reason="test"
        )

        assert cooldown.is_ready is False

    def test_is_ready_invalid_format_fallback(self):
        """Test cooldown uses remaining_seconds fallback for invalid expiration format"""
        cooldown = CooldownInfo(
            character_name="test_char",
            expiration="invalid_format",
            total_seconds=30,
            remaining_seconds=0,
            reason="test"
        )

        assert cooldown.is_ready is True

        cooldown_not_ready = CooldownInfo(
            character_name="test_char",
            expiration="invalid_format",
            total_seconds=30,
            remaining_seconds=10,
            reason="test"
        )

        assert cooldown_not_ready.is_ready is False

    def test_time_remaining_with_time(self):
        """Test time remaining calculation"""

        future_time = datetime.now() + timedelta(seconds=30)
        cooldown = CooldownInfo(
            character_name="test_char",
            expiration=future_time.isoformat(),
            total_seconds=30,
            remaining_seconds=30,
            reason="test"
        )

        remaining = cooldown.time_remaining
        # Should be around 30 seconds, allow some tolerance for execution time
        assert 29 <= remaining <= 31

    def test_time_remaining_expired(self):
        """Test time remaining when cooldown is expired"""

        past_time = datetime.now() - timedelta(seconds=10)
        cooldown = CooldownInfo(
            character_name="test_char",
            expiration=past_time.isoformat(),
            total_seconds=30,
            remaining_seconds=0,
            reason="test"
        )

        assert cooldown.time_remaining == 0.0

    def test_time_remaining_invalid_format_fallback(self):
        """Test time remaining uses remaining_seconds fallback for invalid expiration format"""
        cooldown = CooldownInfo(
            character_name="test_char",
            expiration="invalid_format",
            total_seconds=30,
            remaining_seconds=15,
            reason="test"
        )

        assert cooldown.time_remaining == 15.0
