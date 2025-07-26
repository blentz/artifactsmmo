"""
Tests for test_state package __init__.py utilities

This module tests the shared test utilities provided by the test_state
package, including mock data creators and helper functions.
"""


from src.ai_player.state.game_state import ActionResult, CooldownInfo, GameState
from tests.test_ai_player.test_state import (
    create_mock_action_result,
    create_mock_character_state,
    create_mock_cooldown_info,
)


class TestCreateMockCharacterState:
    """Test create_mock_character_state utility function"""

    def test_creates_default_state(self):
        """Test that default character state is created correctly"""
        state = create_mock_character_state()

        # Verify essential state values
        assert state[GameState.CHARACTER_LEVEL] == 1
        assert state[GameState.CHARACTER_XP] == 0
        assert state[GameState.CHARACTER_GOLD] == 0
        assert state[GameState.HP_CURRENT] == 100
        assert state[GameState.HP_MAX] == 100
        assert state[GameState.CURRENT_X] == 0
        assert state[GameState.CURRENT_Y] == 0

        # Verify skills default to level 1
        assert state[GameState.MINING_LEVEL] == 1
        assert state[GameState.WOODCUTTING_LEVEL] == 1
        assert state[GameState.FISHING_LEVEL] == 1
        assert state[GameState.WEAPONCRAFTING_LEVEL] == 1
        assert state[GameState.GEARCRAFTING_LEVEL] == 1
        assert state[GameState.JEWELRYCRAFTING_LEVEL] == 1
        assert state[GameState.COOKING_LEVEL] == 1
        assert state[GameState.ALCHEMY_LEVEL] == 1

        # Verify equipment slots default to None
        assert state[GameState.WEAPON_EQUIPPED] is None
        assert state[GameState.TOOL_EQUIPPED] is None
        assert state[GameState.HELMET_EQUIPPED] is None
        assert state[GameState.BODY_ARMOR_EQUIPPED] is None

        # Verify calculated states
        assert state[GameState.INVENTORY_SPACE_AVAILABLE] == 20
        assert state[GameState.INVENTORY_FULL] is False
        assert state[GameState.COOLDOWN_READY] is True
        assert state[GameState.CAN_FIGHT] is True
        assert state[GameState.CAN_GATHER] is True
        assert state[GameState.CAN_CRAFT] is True

    def test_override_with_gamestate_enum(self):
        """Test overriding state values using GameState enum keys"""
        state = create_mock_character_state(
            **{
                GameState.CHARACTER_LEVEL: 10,
                GameState.CHARACTER_GOLD: 500,
                GameState.CURRENT_X: 25,
                GameState.CURRENT_Y: 30,
                GameState.MINING_LEVEL: 5
            }
        )

        # Verify overridden values
        assert state[GameState.CHARACTER_LEVEL] == 10
        assert state[GameState.CHARACTER_GOLD] == 500
        assert state[GameState.CURRENT_X] == 25
        assert state[GameState.CURRENT_Y] == 30
        assert state[GameState.MINING_LEVEL] == 5

        # Verify non-overridden values remain default
        assert state[GameState.CHARACTER_XP] == 0
        assert state[GameState.HP_CURRENT] == 100

    def test_override_with_string_keys(self):
        """Test overriding state values using string keys"""
        state = create_mock_character_state(
            character_level=15,
            current_x=50,
            mining_level=8
        )

        # Verify string keys are converted to GameState enum
        assert state[GameState.CHARACTER_LEVEL] == 15
        assert state[GameState.CURRENT_X] == 50
        assert state[GameState.MINING_LEVEL] == 8

    def test_override_with_mixed_keys(self):
        """Test overriding with both enum and string keys"""
        state = create_mock_character_state(
            character_level=20,  # string key
            **{GameState.CURRENT_X: 100}  # enum key
        )

        assert state[GameState.CHARACTER_LEVEL] == 20
        assert state[GameState.CURRENT_X] == 100

    def test_override_with_direct_enum_key(self):
        """Test overriding using direct GameState enum keys (non-string)"""
        # This test specifically targets line 113 in the else clause
        overrides = {GameState.CHARACTER_LEVEL: 25}
        state = create_mock_character_state(**overrides)

        assert state[GameState.CHARACTER_LEVEL] == 25

    def test_complete_state_coverage(self):
        """Test that all expected GameState enum values are in default state"""
        state = create_mock_character_state()

        # Test that all key state categories are present
        character_states = [
            GameState.CHARACTER_LEVEL, GameState.CHARACTER_XP, GameState.CHARACTER_GOLD,
            GameState.HP_CURRENT, GameState.HP_MAX
        ]
        for state_key in character_states:
            assert state_key in state

        position_states = [GameState.CURRENT_X, GameState.CURRENT_Y]
        for state_key in position_states:
            assert state_key in state

        skill_states = [
            GameState.MINING_LEVEL, GameState.WOODCUTTING_LEVEL, GameState.FISHING_LEVEL,
            GameState.WEAPONCRAFTING_LEVEL, GameState.GEARCRAFTING_LEVEL,
            GameState.JEWELRYCRAFTING_LEVEL, GameState.COOKING_LEVEL, GameState.ALCHEMY_LEVEL
        ]
        for state_key in skill_states:
            assert state_key in state

    def test_boolean_state_handling(self):
        """Test handling of boolean state values"""
        state = create_mock_character_state(
            inventory_full=True,
            cooldown_ready=False,
            can_fight=False
        )

        assert state[GameState.INVENTORY_FULL] is True
        assert state[GameState.COOLDOWN_READY] is False
        assert state[GameState.CAN_FIGHT] is False


class TestCreateMockActionResult:
    """Test create_mock_action_result utility function"""

    def test_creates_default_success_result(self):
        """Test creating default successful action result"""
        result = create_mock_action_result()

        assert result.success is True
        assert result.message == "Action completed successfully"
        assert result.state_changes == {}
        assert result.cooldown_seconds == 0

    def test_creates_failure_result(self):
        """Test creating failure action result"""
        result = create_mock_action_result(
            success=False,
            message="Action failed due to insufficient resources",
            cooldown_seconds=30
        )

        assert result.success is False
        assert result.message == "Action failed due to insufficient resources"
        assert result.cooldown_seconds == 30

    def test_creates_result_with_state_changes(self):
        """Test creating action result with state changes"""
        state_changes = {
            GameState.CHARACTER_LEVEL: 2,
            GameState.CHARACTER_XP: 100,
            GameState.CURRENT_X: 10
        }

        result = create_mock_action_result(
            success=True,
            message="Level up achieved",
            state_changes=state_changes,
            cooldown_seconds=5
        )

        assert result.success is True
        assert result.message == "Level up achieved"
        assert result.state_changes == state_changes
        assert result.cooldown_seconds == 5

    def test_state_changes_none_handling(self):
        """Test that None state_changes defaults to empty dict"""
        result = create_mock_action_result(state_changes=None)
        assert result.state_changes == {}

    def test_is_action_result_instance(self):
        """Test that created object is proper ActionResult instance"""
        result = create_mock_action_result()
        assert isinstance(result, ActionResult)


class TestCreateMockCooldownInfo:
    """Test create_mock_cooldown_info utility function"""

    def test_creates_default_cooldown(self):
        """Test creating default cooldown info"""
        cooldown = create_mock_cooldown_info()

        assert cooldown.character_name == "test_character"
        assert cooldown.expiration == "2024-01-01T00:00:00Z"
        assert cooldown.total_seconds == 60
        assert cooldown.remaining_seconds == 0
        assert cooldown.reason == "Test cooldown"

    def test_creates_custom_cooldown(self):
        """Test creating custom cooldown info"""
        cooldown = create_mock_cooldown_info(
            character_name="my_character",
            expiration="2024-12-31T23:59:59Z",
            total_seconds=120,
            remaining_seconds=45,
            reason="Combat cooldown"
        )

        assert cooldown.character_name == "my_character"
        assert cooldown.expiration == "2024-12-31T23:59:59Z"
        assert cooldown.total_seconds == 120
        assert cooldown.remaining_seconds == 45
        assert cooldown.reason == "Combat cooldown"

    def test_is_cooldown_info_instance(self):
        """Test that created object is proper CooldownInfo instance"""
        cooldown = create_mock_cooldown_info()
        assert isinstance(cooldown, CooldownInfo)

    def test_cooldown_has_expected_properties(self):
        """Test that cooldown has expected properties available"""
        cooldown = create_mock_cooldown_info(remaining_seconds=30)

        # These properties should be available from CooldownInfo model
        assert hasattr(cooldown, 'is_ready')
        assert hasattr(cooldown, 'time_remaining')


class TestModuleExports:
    """Test module __all__ exports"""

    def test_all_functions_exported(self):
        """Test that all utility functions are properly exported"""
        from tests.test_ai_player.test_state import __all__

        expected_exports = [
            "create_mock_character_state",
            "create_mock_action_result",
            "create_mock_cooldown_info",
        ]

        assert set(__all__) == set(expected_exports)

    def test_functions_importable(self):
        """Test that all exported functions can be imported"""
        # These imports should work without error
        from tests.test_ai_player.test_state import (
            create_mock_action_result,
            create_mock_character_state,
            create_mock_cooldown_info,
        )

        # Verify they are callable
        assert callable(create_mock_character_state)
        assert callable(create_mock_action_result)
        assert callable(create_mock_cooldown_info)


class TestIntegrationUsage:
    """Test realistic usage scenarios for the utility functions"""

    def test_state_utility_integration(self):
        """Test using utilities together in realistic test scenarios"""
        # Create a character state for a mid-level character
        state = create_mock_character_state(
            character_level=10,
            character_gold=1000,
            mining_level=5,
            current_x=25,
            current_y=30,
            cooldown_ready=False
        )

        # Create corresponding action result for mining
        mining_result = create_mock_action_result(
            success=True,
            message="Successfully mined iron ore",
            state_changes={
                GameState.MINING_XP: state[GameState.MINING_XP] + 50,
                GameState.CHARACTER_XP: state[GameState.CHARACTER_XP] + 25
            },
            cooldown_seconds=10
        )

        # Create cooldown info for the mining action
        cooldown = create_mock_cooldown_info(
            character_name="test_miner",
            total_seconds=10,
            remaining_seconds=10,
            reason="Mining cooldown"
        )

        # Verify they work together properly
        assert state[GameState.CHARACTER_LEVEL] == 10
        assert mining_result.success is True
        assert mining_result.cooldown_seconds == cooldown.total_seconds

    def test_utilities_provide_valid_objects(self):
        """Test that utilities create objects that pass validation"""
        # Create objects using utilities
        state = create_mock_character_state()
        result = create_mock_action_result()
        cooldown = create_mock_cooldown_info()

        # Test that they have expected attributes and types
        assert isinstance(state, dict)
        assert all(isinstance(k, GameState) for k in state.keys())

        assert isinstance(result, ActionResult)
        assert hasattr(result, 'success')
        assert hasattr(result, 'message')
        assert hasattr(result, 'state_changes')
        assert hasattr(result, 'cooldown_seconds')

        assert isinstance(cooldown, CooldownInfo)
        assert hasattr(cooldown, 'character_name')
        assert hasattr(cooldown, 'expiration')
        assert hasattr(cooldown, 'is_ready')
