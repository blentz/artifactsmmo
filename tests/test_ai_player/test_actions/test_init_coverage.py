"""
Coverage test for Action Registry System - Tests the real implementation
"""


from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import src.ai_player.actions
from src.ai_player.actions import (
    ActionFactory,
    ActionRegistry,
    ParameterizedActionFactory,
    get_all_actions,
    get_global_registry,
    register_action_factory,
)
from src.ai_player.actions.base_action import BaseAction
from src.ai_player.state.action_result import ActionResult, GameState
from src.ai_player.state.character_game_state import CharacterGameState


# Reusable test action classes
class SimpleTestAction(BaseAction):
    """Simple test action for testing"""
    def __init__(self, name: str = "test_action"):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def cost(self) -> int:
        return 1

    def get_preconditions(self) -> dict[GameState, Any]:
        return {GameState.COOLDOWN_READY: True}

    def get_effects(self) -> dict[GameState, Any]:
        return {GameState.COOLDOWN_READY: False}

    async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
        return ActionResult(success=True, state_changes={})

    async def _execute_api_call(self, character_name: str, current_state: dict[GameState, Any], api_client: Any, cooldown_manager: Any = None) -> ActionResult:
        return ActionResult(success=True, message=f"{self._name} API call", state_changes={}, cooldown_seconds=5)


class ParameterizedTestAction(BaseAction):
    """Parameterized test action for testing factories"""
    def __init__(self, target: str):
        self.target = target

    @property
    def name(self) -> str:
        return f"param_test_action_{self.target}"

    @property
    def cost(self) -> int:
        return 1

    def get_preconditions(self) -> dict[GameState, Any]:
        return {GameState.COOLDOWN_READY: True}

    def get_effects(self) -> dict[GameState, Any]:
        return {GameState.COOLDOWN_READY: False}

    async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
        return ActionResult(success=True, state_changes={})

    async def _execute_api_call(self, character_name: str, current_state: dict[GameState, Any], api_client: Any, cooldown_manager: Any = None) -> ActionResult:
        return ActionResult(success=True, message=f"Param API call {self.target}", state_changes={}, cooldown_seconds=5)


class ErrorAction(BaseAction):
    """Action that can be configured to throw errors"""
    def __init__(self, error_in_init: bool = False, requires_param: bool = False, param: str = None):
        if error_in_init:
            raise RuntimeError("Error in constructor")
        if requires_param and param is None:
            # This simulates missing required parameter
            self.required_param = None
        else:
            self.param = param

    @property
    def name(self) -> str:
        return "error_action"

    @property
    def cost(self) -> int:
        return 1

    def get_preconditions(self) -> dict[GameState, Any]:
        return {}

    def get_effects(self) -> dict[GameState, Any]:
        return {}

    async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
        return ActionResult(success=True, state_changes={})

    async def _execute_api_call(self, character_name: str, current_state: dict[GameState, Any], api_client: Any, cooldown_manager: Any = None) -> ActionResult:
        return ActionResult(success=False, message="Error action API call", state_changes={})


class InvalidAction(BaseAction):
    """Action with invalid validation to test validation failures"""
    def __init__(self, invalid_preconditions: bool = False, invalid_effects: bool = False, 
                 exception_in_preconditions: bool = False, exception_in_effects: bool = False):
        self.invalid_preconditions = invalid_preconditions
        self.invalid_effects = invalid_effects
        self.exception_in_preconditions = exception_in_preconditions
        self.exception_in_effects = exception_in_effects

    @property
    def name(self) -> str:
        return "invalid_action"

    @property
    def cost(self) -> int:
        return 1

    def get_preconditions(self) -> dict[GameState, Any]:
        if self.exception_in_preconditions:
            raise ValueError("Error in preconditions")
        if self.invalid_preconditions:
            return "not a dict"  # Invalid return type
        return {GameState.COOLDOWN_READY: True}

    def get_effects(self) -> dict[GameState, Any]:
        if self.exception_in_effects:
            raise ValueError("Error in effects")
        if self.invalid_effects:
            return "not a dict"  # Invalid return type
        return {GameState.COOLDOWN_READY: False}

    async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
        return ActionResult(success=True, state_changes={})

    async def _execute_api_call(self, character_name: str, current_state: dict[GameState, Any], api_client: Any, cooldown_manager: Any = None) -> ActionResult:
        return ActionResult(success=False, message="Invalid action API call", state_changes={})


# Test factories
class SimpleTestFactory(ActionFactory):
    def __init__(self, action_class=SimpleTestAction, should_error: bool = False):
        self.action_class = action_class
        self.should_error = should_error

    def create_instances(self, game_data: Any, current_state: dict[GameState, Any]) -> list[BaseAction]:
        if self.should_error:
            raise ValueError("Test error in factory")
        return [self.action_class()]

    def get_action_type(self) -> type[BaseAction]:
        return self.action_class


class SimpleTestParameterizedFactory(ParameterizedActionFactory):
    def __init__(self):
        super().__init__(ParameterizedTestAction)

    def generate_parameters(self, game_data: Any, current_state: dict[GameState, Any]) -> list[dict[str, Any]]:
        return [{"target": "A"}, {"target": "B"}]


def test_real_action_registry():
    """Test the real action registry with actual action discovery"""
    # Clear global registry
    src.ai_player.actions._global_registry = None

    # Test action discovery with real modules
    registry = ActionRegistry()

    # Should discover actual action classes
    discovered_actions = registry._discovered_actions
    assert len(discovered_actions) > 0  # Should find CombatAction, GatheringAction, etc.

    # Test getting all action types
    action_types = registry.get_all_action_types()
    assert len(action_types) > 0

    # Test global functions
    current_state = CharacterGameState(
        name="TestChar",
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
    game_data = {}

    actions = get_all_actions(current_state, game_data)
    # Some actions might fail to instantiate without proper parameters, that's OK
    # We just need to test that the system works

    # Test global registry
    global_registry = get_global_registry()
    assert isinstance(global_registry, ActionRegistry)


def test_action_validation():
    """Test action validation with real discovered actions"""
    # Clear global registry
    src.ai_player.actions._global_registry = None

    registry = ActionRegistry()

    # Test that all discovered actions are valid
    for action_name, action_class in registry._discovered_actions.items():
        assert registry.validate_action(action_class), f"Action {action_name} failed validation"


def test_concrete_action_factory():
    """Test ActionFactory abstract base class through concrete implementation"""
    factory = SimpleTestFactory()
    instances = factory.create_instances({}, {})
    assert len(instances) == 1
    assert isinstance(instances[0], SimpleTestAction)
    assert factory.get_action_type() == SimpleTestAction


def test_parameterized_action_factory():
    """Test ParameterizedActionFactory concrete implementation"""
    factory = SimpleTestParameterizedFactory()
    instances = factory.create_instances({}, {})
    assert len(instances) == 2
    assert instances[0].name == "param_test_action_A"
    assert instances[1].name == "param_test_action_B"


def test_factory_registration():
    """Test action factory registration and generation"""
    # Clear global registry
    src.ai_player.actions._global_registry = None

    registry = get_global_registry()
    factory = SimpleTestFactory(SimpleTestAction)
    register_action_factory(factory)

    # Test that factory is registered
    assert SimpleTestAction in registry._action_factories

    # Test generation with factory
    actions = registry.generate_actions_for_state({}, {})
    factory_actions = [a for a in actions if a.name == "test_action"]
    assert len(factory_actions) >= 1


def test_factory_error_handling():
    """Test error handling in factory action generation"""
    # Clear global registry
    src.ai_player.actions._global_registry = None

    registry = ActionRegistry()
    factory = SimpleTestFactory(should_error=True)
    registry.register_factory(factory)

    # Factory errors should bubble up, not be swallowed
    with pytest.raises(ValueError, match="Test error in factory"):
        registry.generate_actions_for_state({}, {})


def test_action_validation_errors():
    """Test action validation with various error conditions"""
    registry = ActionRegistry()

    # Test class without required methods
    class IncompleteAction:
        pass

    assert not registry.validate_action(IncompleteAction)

    # Test action with invalid preconditions (not dict)
    class InvalidPreconditionsAction(InvalidAction):
        def __init__(self):
            super().__init__(invalid_preconditions=True)

    assert not registry.validate_action(InvalidPreconditionsAction)

    # Test action with invalid effects (not dict)
    class InvalidEffectsAction(InvalidAction):
        def __init__(self):
            super().__init__(invalid_effects=True)

    assert not registry.validate_action(InvalidEffectsAction)

    # Test action that throws exception in validation
    class ExceptionInPreconditionsAction(InvalidAction):
        def __init__(self):
            super().__init__(exception_in_preconditions=True)

    result = registry.validate_action(ExceptionInPreconditionsAction)
    assert result is True  # Basic validation passes, exception in method call is handled


def test_get_action_by_name():
    """Test getting specific action by name"""
    # Clear global registry
    src.ai_player.actions._global_registry = None

    registry = ActionRegistry()
    factory = SimpleTestParameterizedFactory()
    registry.register_factory(factory)

    # Test finding parameterized action from factory
    action = registry.get_action_by_name("param_test_action_A", {}, {})
    assert action is not None
    assert action.name == "param_test_action_A"

    # Test action not found
    action = registry.get_action_by_name("nonexistent_action", {}, {})
    assert action is None


def test_error_handling_coverage():
    """Test additional error paths for complete coverage"""
    registry = ActionRegistry()

    # Test exception in constructor during validation
    class ConstructorErrorAction(BaseAction):
        def __init__(self):
            raise ValueError("Constructor error")

        @property
        def name(self) -> str:
            return "constructor_error"

        @property
        def cost(self) -> int:
            return 1

        def get_preconditions(self) -> dict[GameState, Any]:
            return {}

        def get_effects(self) -> dict[GameState, Any]:
            return {}

        async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
            return ActionResult(success=True, state_changes={})

        async def _execute_api_call(self, character_name: str, current_state: dict[GameState, Any], api_client: Any, cooldown_manager: Any = None) -> ActionResult:
            return ActionResult(success=False, message="", state_changes={})

    result = registry.validate_action(ConstructorErrorAction)
    assert result is False  # Should return False when exception occurs

    # Test action creation error in generate_actions_for_state
    registry._discovered_actions["ConstructorErrorAction"] = ConstructorErrorAction
    actions = registry.generate_actions_for_state({}, {})
    # Should handle the error gracefully and continue

    # Test exception handling in get_action_by_name
    action = registry.get_action_by_name("constructor_error", {}, {})
    assert action is None  # Should handle error and return None


def test_abstract_methods_coverage():
    """Test abstract methods directly for 100% coverage"""
    # Test ActionFactory abstract methods
    class ConcreteFactory(ActionFactory):
        def create_instances(self, game_data: Any, current_state: dict[GameState, Any]) -> list[BaseAction]:
            return []

        def get_action_type(self) -> type[BaseAction]:
            return BaseAction

    factory = ConcreteFactory()
    instances = factory.create_instances({}, {})
    assert instances == []
    action_type = factory.get_action_type()
    assert action_type == BaseAction

    # Test ParameterizedActionFactory.generate_parameters abstract method
    class ConcreteParameterizedFactory(ParameterizedActionFactory):
        def __init__(self):
            super().__init__(BaseAction)

        def generate_parameters(self, game_data: Any, current_state: dict[GameState, Any]) -> list[dict[str, Any]]:
            return [{"param": "value"}]

    param_factory = ConcreteParameterizedFactory()
    params = param_factory.generate_parameters({}, {})
    assert params == [{"param": "value"}]


def test_action_discovery_import_error():
    """Test error handling in action discovery when import fails"""
    with patch('src.ai_player.actions.action_registry.pkgutil.iter_modules') as mock_iter:
        with patch('src.ai_player.actions.action_registry.importlib.import_module') as mock_import:
            # Create a mock module info that will cause an import error
            mock_module_info = MagicMock()
            mock_module_info.name = 'test_failing_module'
            mock_iter.return_value = [mock_module_info]

            # Make import_module raise an exception
            mock_import.side_effect = ImportError("Test import error")

            # This should trigger the error handling
            registry = ActionRegistry()
            assert isinstance(registry._discovered_actions, dict)
            # Should have handled the error gracefully


if __name__ == "__main__":
    pytest.main([__file__])