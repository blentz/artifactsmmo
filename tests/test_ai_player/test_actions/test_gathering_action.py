"""
Tests for GatheringAction implementation

This module tests gathering action functionality including resource targeting,
tool validation, skill checks, and API integration for resource collection.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.ai_player.actions.base_action import BaseAction
from src.ai_player.actions.gathering_action import GatheringAction
from src.ai_player.state.game_state import ActionResult, GameState


class TestGatheringAction:
    """Test GatheringAction implementation"""

    def test_gathering_action_inheritance(self):
        """Test that GatheringAction properly inherits from BaseAction"""
        action = GatheringAction("copper")

        assert isinstance(action, BaseAction)
        assert hasattr(action, 'name')
        assert hasattr(action, 'cost')
        assert hasattr(action, 'get_preconditions')
        assert hasattr(action, 'get_effects')
        assert hasattr(action, 'execute')

    def test_gathering_action_initialization_with_resource(self):
        """Test GatheringAction initialization with resource target"""
        resource_type = "copper"
        mock_api_client = Mock()
        action = GatheringAction(resource_type, mock_api_client)

        assert action.resource_type == resource_type
        assert action.api_client == mock_api_client
        assert isinstance(action.name, str)
        assert resource_type in action.name

    def test_gathering_action_initialization_without_resource(self):
        """Test GatheringAction initialization without resource target"""
        action = GatheringAction()

        assert action.resource_type is None
        assert action.api_client is None
        assert action.name == "gather"

    def test_gathering_action_name_generation(self):
        """Test that gathering action generates unique names"""
        action1 = GatheringAction("copper")
        action2 = GatheringAction("iron")
        action3 = GatheringAction("copper")  # Same resource
        action4 = GatheringAction()  # No resource

        assert action1.name != action2.name
        assert action1.name == action3.name  # Same resource = same name
        assert action4.name == "gather"

        # Names should include resource for identification
        assert "copper" in action1.name
        assert "iron" in action2.name
        assert action1.name == "gather_copper"
        assert action2.name == "gather_iron"

    def test_gathering_action_cost(self):
        """Test gathering action cost property"""
        action = GatheringAction("wood")

        assert isinstance(action.cost, int)
        assert action.cost == 5

    def test_get_preconditions_without_resource(self):
        """Test preconditions for general gathering"""
        action = GatheringAction()
        preconditions = action.get_preconditions()

        # Verify preconditions structure
        assert isinstance(preconditions, dict)
        assert all(isinstance(key, GameState) for key in preconditions.keys())

        # Check required preconditions
        expected_keys = {
            GameState.COOLDOWN_READY,
            GameState.CAN_GATHER,
            GameState.AT_RESOURCE_LOCATION,
            GameState.INVENTORY_SPACE_AVAILABLE,
        }
        assert expected_keys.issubset(set(preconditions.keys()))
        assert all(value is True for value in preconditions.values())

    def test_get_preconditions_with_resource(self):
        """Test preconditions for specific resource gathering"""
        action = GatheringAction("iron")
        preconditions = action.get_preconditions()

        # Should include specific resource availability
        assert GameState.RESOURCE_AVAILABLE in preconditions
        assert preconditions[GameState.RESOURCE_AVAILABLE] is True

    def test_get_effects(self):
        """Test gathering action effects"""
        action = GatheringAction("logs")
        effects = action.get_effects()

        # Verify effects structure
        assert isinstance(effects, dict)
        assert all(isinstance(key, GameState) for key in effects.keys())

        # Check that cooldown is triggered
        assert effects[GameState.COOLDOWN_READY] is False

        # Check that other actions are disabled
        disabled_actions = [
            GameState.CAN_FIGHT,
            GameState.CAN_GATHER,
            GameState.CAN_CRAFT,
            GameState.CAN_TRADE,
            GameState.CAN_MOVE,
            GameState.CAN_REST,
            GameState.CAN_USE_ITEM,
            GameState.CAN_BANK,
        ]
        for action_state in disabled_actions:
            assert effects[action_state] is False

        # Check inventory usage
        assert effects[GameState.INVENTORY_SPACE_USED] == "+1"

    def test_has_required_tool_with_tool(self):
        """Test tool validation when tool is equipped"""
        action = GatheringAction("wood")
        current_state = {
            GameState.TOOL_EQUIPPED: "iron_axe"
        }

        assert action.has_required_tool(current_state) is True

    def test_has_required_tool_without_tool(self):
        """Test tool validation when no tool is equipped"""
        action = GatheringAction("wood")
        current_state = {
            GameState.TOOL_EQUIPPED: None
        }

        assert action.has_required_tool(current_state) is False

    def test_has_required_tool_missing_tool_state(self):
        """Test tool validation when tool state is missing"""
        action = GatheringAction("wood")
        current_state = {}

        assert action.has_required_tool(current_state) is False

    def test_has_sufficient_skill_with_adequate_skill(self):
        """Test skill validation with sufficient skill level"""
        action = GatheringAction("copper")
        current_state = {
            GameState.MINING_LEVEL: 5,
            GameState.WOODCUTTING_LEVEL: 3,
            GameState.FISHING_LEVEL: 2,
        }

        assert action.has_sufficient_skill(current_state) is True

    def test_has_sufficient_skill_with_inadequate_skill(self):
        """Test skill validation with insufficient skill level"""
        action = GatheringAction("copper")

        # Mock get_skill_requirement to return a higher level
        with patch.object(action, 'get_skill_requirement', return_value=10):
            current_state = {
                GameState.MINING_LEVEL: 5,
                GameState.WOODCUTTING_LEVEL: 3,
                GameState.FISHING_LEVEL: 2,
            }

            assert action.has_sufficient_skill(current_state) is False

    def test_has_sufficient_skill_missing_skill_states(self):
        """Test skill validation when skill states are missing"""
        action = GatheringAction("copper")
        current_state = {}

        # Should default to level 1 and pass
        assert action.has_sufficient_skill(current_state) is True

    def test_has_inventory_space_with_space(self):
        """Test inventory space check when space is available"""
        action = GatheringAction("fish")
        current_state = {
            GameState.INVENTORY_SPACE_AVAILABLE: True
        }

        assert action.has_inventory_space(current_state) is True

    def test_has_inventory_space_without_space(self):
        """Test inventory space check when space is not available"""
        action = GatheringAction("fish")
        current_state = {
            GameState.INVENTORY_SPACE_AVAILABLE: False
        }

        assert action.has_inventory_space(current_state) is False

    def test_has_inventory_space_calculated_from_usage(self):
        """Test inventory space calculation from usage values"""
        action = GatheringAction("fish")
        current_state = {
            GameState.INVENTORY_SPACE_USED: 50
        }

        # Should return True since 50 < 100 (default max)
        assert action.has_inventory_space(current_state) is True

    def test_has_inventory_space_full_inventory(self):
        """Test inventory space when inventory is full"""
        action = GatheringAction("fish")
        current_state = {
            GameState.INVENTORY_SPACE_USED: 100
        }

        # Should return False since 100 >= 100 (default max)
        assert action.has_inventory_space(current_state) is False

    def test_get_skill_requirement(self):
        """Test skill requirement retrieval"""
        action = GatheringAction("silver")

        assert isinstance(action.get_skill_requirement(), int)
        assert action.get_skill_requirement() == 1  # Default minimum

    def test_can_execute_with_all_preconditions_met(self):
        """Test can_execute when all preconditions are satisfied"""
        action = GatheringAction("wood")
        current_state = {
            GameState.COOLDOWN_READY: True,
            GameState.CAN_GATHER: True,
            GameState.AT_RESOURCE_LOCATION: True,
            GameState.INVENTORY_SPACE_AVAILABLE: True,
            GameState.RESOURCE_AVAILABLE: True,  # Required for specific resource
        }

        assert action.can_execute(current_state) is True

    def test_can_execute_with_missing_preconditions(self):
        """Test can_execute when preconditions are not met"""
        action = GatheringAction("wood")
        current_state = {
            GameState.COOLDOWN_READY: False,  # Not ready
            GameState.CAN_GATHER: True,
            GameState.AT_RESOURCE_LOCATION: True,
            GameState.INVENTORY_SPACE_AVAILABLE: True,
        }

        assert action.can_execute(current_state) is False

    def test_validate_preconditions(self):
        """Test validation of precondition keys"""
        action = GatheringAction("gold")

        assert action.validate_preconditions() is True

    def test_validate_effects(self):
        """Test validation of effect keys"""
        action = GatheringAction("stone")

        assert action.validate_effects() is True

    @pytest.mark.asyncio
    async def test_execute_without_api_client(self):
        """Test execute method when API client is not available"""
        action = GatheringAction("copper")
        current_state = {}

        result = await action.execute("test_character", current_state)

        assert isinstance(result, ActionResult)
        assert result.success is False
        assert "API client not available" in result.message
        assert result.state_changes == {}
        assert result.cooldown_seconds == 0

    @pytest.mark.asyncio
    async def test_execute_without_required_tool(self):
        """Test execute method when required tool is not equipped"""
        mock_api_client = Mock()
        action = GatheringAction("copper", mock_api_client)
        current_state = {
            GameState.TOOL_EQUIPPED: None
        }

        result = await action.execute("test_character", current_state)

        assert isinstance(result, ActionResult)
        assert result.success is False
        assert "Required tool not equipped" in result.message
        assert result.state_changes == {}
        assert result.cooldown_seconds == 0

    @pytest.mark.asyncio
    async def test_execute_with_insufficient_skill(self):
        """Test execute method when skill level is insufficient"""
        mock_api_client = Mock()
        action = GatheringAction("copper", mock_api_client)
        current_state = {
            GameState.TOOL_EQUIPPED: "iron_pickaxe",
            GameState.MINING_LEVEL: 1,
        }

        # Mock get_skill_requirement to return a higher level
        with patch.object(action, 'get_skill_requirement', return_value=10):
            result = await action.execute("test_character", current_state)

            assert isinstance(result, ActionResult)
            assert result.success is False
            assert "Insufficient skill level" in result.message
            assert result.state_changes == {}
            assert result.cooldown_seconds == 0

    @pytest.mark.asyncio
    async def test_execute_without_inventory_space(self):
        """Test execute method when inventory space is not available"""
        mock_api_client = Mock()
        action = GatheringAction("copper", mock_api_client)
        current_state = {
            GameState.TOOL_EQUIPPED: "iron_pickaxe",
            GameState.MINING_LEVEL: 5,
            GameState.INVENTORY_SPACE_AVAILABLE: False,
        }

        result = await action.execute("test_character", current_state)

        assert isinstance(result, ActionResult)
        assert result.success is False
        assert "No inventory space available" in result.message
        assert result.state_changes == {}
        assert result.cooldown_seconds == 0

    @pytest.mark.asyncio
    async def test_execute_successful_gathering(self):
        """Test successful gathering execution"""
        # Create mock API response
        mock_character = Mock()
        mock_character.xp = 1500
        mock_character.gold = 100
        mock_character.x = 5
        mock_character.y = 10
        mock_character.hp = 80
        mock_character.mining_xp = 250
        mock_character.mining_level = 3
        mock_character.woodcutting_xp = 150
        mock_character.woodcutting_level = 2
        mock_character.fishing_xp = 100
        mock_character.fishing_level = 2

        mock_cooldown = Mock()
        mock_cooldown.total_seconds = 30

        mock_details = Mock()
        mock_details.__str__ = Mock(return_value="copper ore x2")

        mock_data = Mock()
        mock_data.character = mock_character
        mock_data.cooldown = mock_cooldown
        mock_data.details = mock_details

        mock_result = Mock()
        mock_result.data = mock_data

        mock_api_client = AsyncMock()
        mock_api_client.gather_resource.return_value = mock_result

        action = GatheringAction("copper", mock_api_client)
        current_state = {
            GameState.TOOL_EQUIPPED: "iron_pickaxe",
            GameState.MINING_LEVEL: 5,
            GameState.INVENTORY_SPACE_AVAILABLE: True,
        }

        result = await action.execute("test_character", current_state)

        # Verify API client was called
        mock_api_client.gather_resource.assert_called_once_with("test_character")

        # Verify result
        assert isinstance(result, ActionResult)
        assert result.success is True
        assert "Gathered resources:" in result.message
        assert result.cooldown_seconds == 30

        # Verify state changes
        expected_state_changes = {
            GameState.COOLDOWN_READY: False,
            GameState.CAN_FIGHT: False,
            GameState.CAN_GATHER: False,
            GameState.CAN_CRAFT: False,
            GameState.CAN_TRADE: False,
            GameState.CAN_MOVE: False,
            GameState.CAN_REST: False,
            GameState.CAN_USE_ITEM: False,
            GameState.CAN_BANK: False,
            GameState.CHARACTER_XP: 1500,
            GameState.CHARACTER_GOLD: 100,
            GameState.CURRENT_X: 5,
            GameState.CURRENT_Y: 10,
            GameState.HP_CURRENT: 80,
            GameState.MINING_XP: 250,
            GameState.MINING_LEVEL: 3,
            GameState.WOODCUTTING_XP: 150,
            GameState.WOODCUTTING_LEVEL: 2,
            GameState.FISHING_XP: 100,
            GameState.FISHING_LEVEL: 2,
        }

        for key, expected_value in expected_state_changes.items():
            assert key in result.state_changes
            assert result.state_changes[key] == expected_value

    @pytest.mark.asyncio
    async def test_execute_successful_gathering_without_details(self):
        """Test successful gathering execution without details"""
        mock_character = Mock()
        mock_character.xp = 1200
        mock_character.gold = 50
        mock_character.x = 3
        mock_character.y = 7
        mock_character.hp = 90

        mock_cooldown = Mock()
        mock_cooldown.total_seconds = 25

        mock_data = Mock()
        mock_data.character = mock_character
        mock_data.cooldown = mock_cooldown

        # Set details to None to simulate no details
        mock_data.details = None

        mock_result = Mock()
        mock_result.data = mock_data

        mock_api_client = AsyncMock()
        mock_api_client.gather_resource.return_value = mock_result

        action = GatheringAction("wood", mock_api_client)
        current_state = {
            GameState.TOOL_EQUIPPED: "iron_axe",
            GameState.WOODCUTTING_LEVEL: 3,
            GameState.INVENTORY_SPACE_AVAILABLE: True,
        }

        result = await action.execute("test_character", current_state)

        assert isinstance(result, ActionResult)
        assert result.success is True
        assert result.message == "Gathering successful"
        assert result.cooldown_seconds == 25

    @pytest.mark.asyncio
    async def test_execute_api_error(self):
        """Test execute method when API call fails"""
        mock_api_client = AsyncMock()
        mock_api_client.gather_resource.side_effect = Exception("API error")

        action = GatheringAction("iron", mock_api_client)
        current_state = {
            GameState.TOOL_EQUIPPED: "steel_pickaxe",
            GameState.MINING_LEVEL: 10,
            GameState.INVENTORY_SPACE_AVAILABLE: True,
        }

        result = await action.execute("test_character", current_state)

        assert isinstance(result, ActionResult)
        assert result.success is False
        assert "Gathering failed: API error" in result.message
        assert result.state_changes == {}
        assert result.cooldown_seconds == 0

    @pytest.mark.asyncio
    async def test_execute_successful_gathering_missing_character_attributes(self):
        """Test successful gathering when character has missing skill attributes"""
        # Create a mock character with only basic attributes and mining
        mock_character = Mock(spec=['xp', 'gold', 'x', 'y', 'hp', 'mining_xp', 'mining_level'])
        mock_character.xp = 1000
        mock_character.gold = 75
        mock_character.x = 2
        mock_character.y = 4
        mock_character.hp = 70
        mock_character.mining_xp = 200
        mock_character.mining_level = 2

        mock_cooldown = Mock()
        mock_cooldown.total_seconds = 20

        mock_data = Mock()
        mock_data.character = mock_character
        mock_data.cooldown = mock_cooldown

        mock_result = Mock()
        mock_result.data = mock_data

        mock_api_client = AsyncMock()
        mock_api_client.gather_resource.return_value = mock_result

        action = GatheringAction("stone", mock_api_client)
        current_state = {
            GameState.TOOL_EQUIPPED: "iron_pickaxe",
            GameState.MINING_LEVEL: 5,
            GameState.INVENTORY_SPACE_AVAILABLE: True,
        }

        result = await action.execute("test_character", current_state)

        assert isinstance(result, ActionResult)
        assert result.success is True

        # Should still include basic character updates
        assert result.state_changes[GameState.CHARACTER_XP] == 1000
        assert result.state_changes[GameState.MINING_XP] == 200
        assert result.state_changes[GameState.MINING_LEVEL] == 2

        # Should not have woodcutting or fishing updates since Mock spec doesn't include them
        assert GameState.WOODCUTTING_XP not in result.state_changes
        assert GameState.FISHING_XP not in result.state_changes

    @pytest.mark.asyncio
    async def test_execute_details_string_conversion_error(self):
        """Test execute method when details string conversion fails"""
        mock_character = Mock()
        mock_character.xp = 1000
        mock_character.gold = 50
        mock_character.x = 3
        mock_character.y = 7
        mock_character.hp = 90

        mock_cooldown = Mock()
        mock_cooldown.total_seconds = 25

        # Create a mock details that raises an exception when converted to string
        mock_details = Mock()
        mock_details.__str__ = Mock(side_effect=Exception("String conversion error"))

        mock_data = Mock()
        mock_data.character = mock_character
        mock_data.cooldown = mock_cooldown
        mock_data.details = mock_details

        mock_result = Mock()
        mock_result.data = mock_data

        mock_api_client = AsyncMock()
        mock_api_client.gather_resource.return_value = mock_result

        action = GatheringAction("wood", mock_api_client)
        current_state = {
            GameState.TOOL_EQUIPPED: "iron_axe",
            GameState.WOODCUTTING_LEVEL: 3,
            GameState.INVENTORY_SPACE_AVAILABLE: True,
        }

        result = await action.execute("test_character", current_state)

        assert isinstance(result, ActionResult)
        assert result.success is True
        # Should fall back to default message when string conversion fails
        assert result.message == "Gathering successful"
        assert result.cooldown_seconds == 25

    def test_validate_preconditions_exception(self):
        """Test validate_preconditions when an exception occurs"""
        action = GatheringAction("gold")

        # Mock get_preconditions to raise an exception
        with patch.object(action, 'get_preconditions', side_effect=Exception("Precondition error")):
            assert action.validate_preconditions() is False

    def test_validate_effects_exception(self):
        """Test validate_effects when an exception occurs"""
        action = GatheringAction("stone")

        # Mock get_effects to raise an exception
        with patch.object(action, 'get_effects', side_effect=Exception("Effects error")):
            assert action.validate_effects() is False
