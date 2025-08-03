"""
Tests for StateManager class

This module tests the state synchronization, API integration,
and state management functionality of the StateManager class.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.ai_player.state.action_result import ActionResult
from src.ai_player.state.character_game_state import CharacterGameState
from src.ai_player.state.game_state import GameState
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
        # Equipment slots
        mock_character.weapon_slot = ""
        mock_character.rune_slot = ""
        mock_character.shield_slot = ""
        mock_character.helmet_slot = ""
        mock_character.body_armor_slot = ""
        mock_character.leg_armor_slot = ""
        mock_character.boots_slot = ""
        mock_character.ring1_slot = ""
        mock_character.ring2_slot = ""
        mock_character.amulet_slot = ""
        mock_character.artifact1_slot = ""
        mock_character.cooldown_expiration_utc = None

        client.get_character = AsyncMock(return_value=mock_character)
        client.get_character_logs = AsyncMock()
        mock_map = Mock()
        mock_map.content = Mock()
        mock_map.content.type = "safe"  # Safe location type
        client.get_map = AsyncMock(return_value=mock_map)
        client.cooldown_manager = Mock()
        client.cooldown_manager.update_from_character = Mock()
        client.cooldown_manager.is_ready = Mock(return_value=True)
        return client

    @pytest.fixture
    def mock_cache_manager(self):
        """Mock cache manager for testing"""
        cache = Mock()
        cache.save_character_state = Mock()
        cache.load_character_state = Mock()
        cache.load_nearby_maps = AsyncMock()
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

        assert isinstance(current_state, CharacterGameState)
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
            mock_character_state = CharacterGameState(
                name="test_character",
                level=5,
                xp=1000,
                gold=500,
                hp=80,
                max_hp=100,
                x=10,
                y=15,
                mining_level=1,
                mining_xp=0,
                woodcutting_level=1,
                woodcutting_xp=0,
                fishing_level=1,
                fishing_xp=0,
                weaponcrafting_level=1,
                weaponcrafting_xp=0,
                gearcrafting_level=1,
                gearcrafting_xp=0,
                jewelrycrafting_level=1,
                jewelrycrafting_xp=0,
                cooking_level=1,
                cooking_xp=0,
                alchemy_level=1,
                alchemy_xp=0,
                cooldown=0
            )
            mock_from_api.return_value = mock_character_state

            current_state = await state_manager.get_current_state()

            assert isinstance(current_state, CharacterGameState)
            mock_api_client.get_character.assert_called_once_with("test_character")
            # Verify from_api_character was called with the character data
            assert mock_from_api.called
            call_args = mock_from_api.call_args[0]
            assert call_args[0] == mock_character  # First arg should be the character

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
            mock_character_state.model_dump.return_value = {
                "name": "test_character",
                "level": 6,
                "xp": 1200,
                "hp": 85,
                "x": 25,
                "y": 30,
                "cooldown": 0,
                "cooldown_ready": True
            }
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

            assert isinstance(synced_state, Mock)  # Returns the mocked CharacterGameState
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

        # Initialize state first (as would happen in normal operation)
        # Mock get_cached_state to return a proper CharacterGameState
        with patch.object(state_manager, 'get_cached_state') as mock_get_cached:
            mock_get_cached.return_value = CharacterGameState(
                name="test_character",
                level=5, xp=800, gold=100, hp=80, max_hp=100,
                x=10, y=15,
                mining_level=1, mining_xp=0,
                woodcutting_level=1, woodcutting_xp=0,
                fishing_level=1, fishing_xp=0,
                weaponcrafting_level=1, weaponcrafting_xp=0,
                gearcrafting_level=1, gearcrafting_xp=0,
                jewelrycrafting_level=1, jewelrycrafting_xp=0,
                cooking_level=1, cooking_xp=0,
                alchemy_level=1, alchemy_xp=0,
                cooldown=0, cooldown_ready=True,
                can_fight=True, can_gather=True, can_craft=True,
                can_trade=True, can_move=True, can_rest=True,
                can_use_item=True, can_bank=True, can_gain_xp=True,
                xp_source_available=False, at_monster_location=False,
                at_resource_location=False, at_safe_location=True,
                safe_to_fight=True, hp_low=False, hp_critical=False,
                inventory_space_available=True, inventory_space_used=0,
                gained_xp=False
            )
            state_manager._cached_state = mock_get_cached.return_value

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

        # Initialize state first (as would happen in normal operation)
        with patch.object(state_manager, 'get_cached_state') as mock_get_cached:
            mock_get_cached.return_value = CharacterGameState(
                name="test_character",
                level=5, xp=800, gold=100, hp=80, max_hp=100,
                x=10, y=15,
                mining_level=1, mining_xp=0,
                woodcutting_level=1, woodcutting_xp=0,
                fishing_level=1, fishing_xp=0,
                weaponcrafting_level=1, weaponcrafting_xp=0,
                gearcrafting_level=1, gearcrafting_xp=0,
                jewelrycrafting_level=1, jewelrycrafting_xp=0,
                cooking_level=1, cooking_xp=0,
                alchemy_level=1, alchemy_xp=0,
                cooldown=0, cooldown_ready=True,
                can_fight=True, can_gather=True, can_craft=True,
                can_trade=True, can_move=True, can_rest=True,
                can_use_item=True, can_bank=True, can_gain_xp=True,
                xp_source_available=False, at_monster_location=False,
                at_resource_location=False, at_safe_location=True,
                safe_to_fight=True, hp_low=False, hp_critical=False,
                inventory_space_available=True, inventory_space_used=0,
                gained_xp=False
            )
            state_manager._cached_state = mock_get_cached.return_value

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

        # Initialize state first by calling get_current_state (which loads from cache)
        await state_manager.get_current_state()

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
            mock_character_state.model_dump.return_value = {
                "character_level": 7,
                "character_xp": 1500,
                "hp_current": 90,
                "current_x": 35,
                "current_y": 40,
                "cooldown_ready": True
            }
            mock_from_api.return_value = mock_character_state

            refreshed_state = await state_manager.refresh_state_from_api()

            assert refreshed_state == mock_character_state
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

            # Test exception propagation in _validate_state_rules following fail-fast principles
            invalid_state = Mock()
            invalid_state.get.side_effect = Exception("Mock exception")
            with pytest.raises(Exception, match="Mock exception"):
                state_manager._validate_state_rules(invalid_state)

    @pytest.mark.asyncio
    async def test_validate_state_consistency_cache_vs_api(self):
        """Test state consistency validation comparing cache vs API"""
        with patch('src.ai_player.state.state_manager.YamlData'):
            mock_api_client = AsyncMock()
            mock_cache_manager = AsyncMock()

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

    # Removed invalid tests that test scenarios without API data
    # The AI player must have API data to function - no fallbacks are valid
