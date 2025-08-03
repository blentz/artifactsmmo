"""
Tests for ActionRegistry factory-based architecture

Tests the new simplified ActionRegistry that uses only factories
without action discovery or validation, following fail-fast principles.
"""

from typing import Any
from unittest.mock import Mock

import pytest

from src.ai_player.actions.action_registry import ActionRegistry
from src.ai_player.actions.action_factory import ActionFactory
from src.ai_player.actions.base_action import BaseAction
from src.ai_player.state.action_result import ActionResult, GameState
from src.ai_player.state.character_game_state import CharacterGameState


class MockAction(BaseAction):
    """Mock action for testing"""

    def __init__(self, name: str = "mock_action", cost: int = 1):
        self._name = name
        self._cost = cost

    @property
    def name(self) -> str:
        return self._name

    @property
    def cost(self) -> int:
        return self._cost

    def get_preconditions(self) -> dict[GameState, Any]:
        return {GameState.COOLDOWN_READY: True}

    def get_effects(self) -> dict[GameState, Any]:
        return {GameState.COOLDOWN_READY: False}

    async def execute(self, character_name: str, current_state: dict[GameState, Any], **kwargs) -> ActionResult:
        return ActionResult(
            success=True,
            message=f"Mock action {self._name} executed",
            state_changes=self.get_effects(),
            cooldown_seconds=1
        )

    async def _execute_api_call(self, character_name: str, current_state: dict[GameState, Any], api_client=None, cooldown_manager=None) -> ActionResult:
        return ActionResult(
            success=True,
            message=f"Mock API action {self._name} executed",
            state_changes=self.get_effects(),
            cooldown_seconds=1
        )


class MockActionFactory(ActionFactory):
    """Mock action factory for testing"""

    def create_instances(self, game_data: Any, current_state: CharacterGameState) -> list[BaseAction]:
        return [
            MockAction("factory_action_1", 1),
            MockAction("factory_action_2", 2)
        ]

    def get_action_type(self) -> type[BaseAction]:
        return MockAction


class TestActionRegistry:
    """Test ActionRegistry factory-based functionality"""

    @pytest.fixture
    def action_registry(self):
        """Create ActionRegistry instance for testing"""
        return ActionRegistry()

    def test_action_registry_initialization(self, action_registry):
        """Test ActionRegistry initialization with correct methods"""
        assert hasattr(action_registry, 'register_factory')
        assert hasattr(action_registry, 'generate_actions_for_state')
        assert hasattr(action_registry, 'get_all_action_types')
        assert hasattr(action_registry, 'get_action_by_name')

    def test_register_factory(self, action_registry):
        """Test registering action factory"""
        factory = MockActionFactory()
        action_registry.register_factory(factory)
        
        # Verify factory was registered (internal state check)
        assert hasattr(action_registry, '_action_factories')
        assert MockAction in action_registry._action_factories

    def test_generate_actions_for_state(self, action_registry):
        """Test generating actions for current state"""
        factory = MockActionFactory()
        action_registry.register_factory(factory)

        current_state = CharacterGameState(
            name="test_character",
            level=5,
            xp=100,
            gold=50,
            hp=100,
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
            cooldown=0,
            cooldown_ready=True
        )

        game_data = Mock()
        game_data.maps = []
        game_data.resources = []
        game_data.monsters = []

        actions = action_registry.generate_actions_for_state(current_state, game_data)

        assert isinstance(actions, list)
        assert len(actions) == 2  # Should have exactly the 2 actions from MockActionFactory
        
        for action in actions:
            assert isinstance(action, BaseAction)

    def test_get_all_action_types(self, action_registry):
        """Test getting all registered action types"""
        factory = MockActionFactory()
        action_registry.register_factory(factory)

        action_types = action_registry.get_all_action_types()

        assert isinstance(action_types, list)
        assert MockAction in action_types

    def test_get_action_by_name_found(self, action_registry):
        """Test getting specific action by name when it exists"""
        factory = MockActionFactory()
        action_registry.register_factory(factory)

        current_state = CharacterGameState(
            name="test_character",
            level=1,
            xp=0,
            gold=0,
            hp=100,
            max_hp=100,
            x=0,
            y=0,
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
            cooldown=0,
            cooldown_ready=True
        )
        
        game_data = Mock()
        game_data.maps = []
        game_data.resources = []
        game_data.monsters = []

        action = action_registry.get_action_by_name("factory_action_1", current_state, game_data)

        assert action is not None
        assert isinstance(action, BaseAction)
        assert action.name == "factory_action_1"

    def test_get_action_by_name_not_found(self, action_registry):
        """Test getting specific action by name when it doesn't exist"""
        current_state = CharacterGameState(
            name="test_character",
            level=1,
            xp=0,
            gold=0,
            hp=100,
            max_hp=100,
            x=0,
            y=0,
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
            cooldown=0,
            cooldown_ready=True
        )
        
        game_data = Mock()
        game_data.maps = []
        game_data.resources = []
        game_data.monsters = []

        action = action_registry.get_action_by_name("nonexistent_action", current_state, game_data)

        assert action is None

    def test_factory_exception_propagation(self, action_registry):
        """Test that factory exceptions are properly propagated following fail-fast principles"""
        
        class FailingFactory(ActionFactory):
            def create_instances(self, game_data: Any, current_state: CharacterGameState) -> list[BaseAction]:
                raise RuntimeError("Factory failed")

            def get_action_type(self) -> type[BaseAction]:
                return MockAction

        failing_factory = FailingFactory()
        action_registry.register_factory(failing_factory)

        current_state = CharacterGameState(
            name="test_character",
            level=1,
            xp=0,
            gold=0,
            hp=100,
            max_hp=100,
            x=0,
            y=0,
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
            cooldown=0,
            cooldown_ready=True
        )
        
        game_data = Mock()

        # Should propagate exception instead of hiding it
        with pytest.raises(RuntimeError, match="Factory failed"):
            action_registry.generate_actions_for_state(current_state, game_data)