"""
Coverage test for Action Registry System - Tests the real implementation
"""


from typing import Any
from unittest.mock import patch

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
from src.ai_player.state.character_game_state import CharacterGameState
from src.ai_player.state.game_state import ActionResult, GameState


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

    class TestAction(BaseAction):
        @property
        def name(self) -> str:
            return "test_action"

        @property
        def cost(self) -> int:
            return 1

        def get_preconditions(self) -> dict[GameState, Any]:
            return {GameState.COOLDOWN_READY: True}

        def get_effects(self) -> dict[GameState, Any]:
            return {GameState.COOLDOWN_READY: False}

        async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
            return ActionResult(success=True, state_changes={})

    class TestFactory(ActionFactory):
        def create_instances(self, game_data: Any, current_state: dict[GameState, Any]) -> list[BaseAction]:
            return [TestAction()]

        def get_action_type(self) -> type[BaseAction]:
            return TestAction

    factory = TestFactory()
    instances = factory.create_instances({}, {})
    assert len(instances) == 1
    assert isinstance(instances[0], TestAction)
    assert factory.get_action_type() == TestAction


def test_parameterized_action_factory():
    """Test ParameterizedActionFactory concrete implementation"""

    class ParameterizedTestAction(BaseAction):
        def __init__(self, target: str = "default"):
            self.target = target

        @property
        def name(self) -> str:
            return f"test_action_{self.target}"

        @property
        def cost(self) -> int:
            return 1

        def get_preconditions(self) -> dict[GameState, Any]:
            return {GameState.COOLDOWN_READY: True}

        def get_effects(self) -> dict[GameState, Any]:
            return {GameState.COOLDOWN_READY: False}

        async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
            return ActionResult(success=True, state_changes={})

    class TestParameterizedFactory(ParameterizedActionFactory):
        def __init__(self):
            super().__init__(ParameterizedTestAction)

        def generate_parameters(self, game_data: Any, current_state: dict[GameState, Any]) -> list[dict[str, Any]]:
            return [{"target": "A"}, {"target": "B"}]

    factory = TestParameterizedFactory()
    instances = factory.create_instances({}, {})
    assert len(instances) == 2
    assert instances[0].name == "test_action_A"
    assert instances[1].name == "test_action_B"


def test_factory_registration():
    """Test action factory registration and generation"""
    # Clear global registry
    src.ai_player.actions._global_registry = None

    class TestAction(BaseAction):
        @property
        def name(self) -> str:
            return "factory_test_action"

        @property
        def cost(self) -> int:
            return 1

        def get_preconditions(self) -> dict[GameState, Any]:
            return {GameState.COOLDOWN_READY: True}

        def get_effects(self) -> dict[GameState, Any]:
            return {GameState.COOLDOWN_READY: False}

        async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
            return ActionResult(success=True, state_changes={})

    class TestFactory(ActionFactory):
        def create_instances(self, game_data: Any, current_state: dict[GameState, Any]) -> list[BaseAction]:
            return [TestAction()]

        def get_action_type(self) -> type[BaseAction]:
            return TestAction

    registry = get_global_registry()
    factory = TestFactory()
    register_action_factory(factory)

    # Test that factory is registered
    assert TestAction in registry._action_factories

    # Test generation with factory
    actions = registry.generate_actions_for_state({}, {})
    factory_actions = [a for a in actions if a.name == "factory_test_action"]
    assert len(factory_actions) == 1


def test_factory_error_handling():
    """Test error handling in factory action generation"""
    # Clear global registry
    src.ai_player.actions._global_registry = None

    class ErrorAction(BaseAction):
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

    class ErrorFactory(ActionFactory):
        def create_instances(self, game_data: Any, current_state: dict[GameState, Any]) -> list[BaseAction]:
            raise ValueError("Test error in factory")

        def get_action_type(self) -> type[BaseAction]:
            return ErrorAction

    registry = ActionRegistry()
    factory = ErrorFactory()
    registry.register_factory(factory)

    # Factory errors should bubble up, not be swallowed
    with pytest.raises(ValueError, match="Test error in factory"):
        registry.generate_actions_for_state({}, {})


def test_non_parameterized_action_creation_errors():
    """Test error handling when creating non-parameterized actions"""

    class ErrorAction(BaseAction):
        def __init__(self, required_param: str):  # Requires parameter but no factory
            self.required_param = required_param

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

    registry = ActionRegistry()
    registry._discovered_actions["ErrorAction"] = ErrorAction

    # Should handle TypeError when action requires parameters
    actions = registry.generate_actions_for_state({}, {})
    # Should not crash and ErrorAction should be skipped


def test_action_validation_errors():
    """Test action validation with various error conditions"""
    registry = ActionRegistry()

    # Test class without required methods
    class InvalidAction1:
        pass

    assert not registry.validate_action(InvalidAction1)

    # Test class that's not a BaseAction subclass
    class InvalidAction2:
        def name(self): return "test"
        def cost(self): return 1
        def get_preconditions(self): return {}
        def get_effects(self): return {}
        def execute(self): pass

    # This will fail isinstance check in discover_actions, but let's test validation
    # We need a proper BaseAction subclass for validation

    # Test action with invalid preconditions (not dict)
    class InvalidAction3(BaseAction):
        @property
        def name(self) -> str:
            return "invalid_action3"

        @property
        def cost(self) -> int:
            return 1

        def get_preconditions(self) -> dict[GameState, Any]:
            return "not a dict"  # Invalid return type

        def get_effects(self) -> dict[GameState, Any]:
            return {}

        async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
            return ActionResult(success=True, state_changes={})

    assert not registry.validate_action(InvalidAction3)

    # Test action with non-GameState keys in preconditions
    class InvalidAction4(BaseAction):
        @property
        def name(self) -> str:
            return "invalid_action4"

        @property
        def cost(self) -> int:
            return 1

        def get_preconditions(self) -> dict[GameState, Any]:
            return {"invalid_key": True}  # Not GameState enum

        def get_effects(self) -> dict[GameState, Any]:
            return {}

        async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
            return ActionResult(success=True, state_changes={})

    assert not registry.validate_action(InvalidAction4)

    # Test action with invalid effects (not dict)
    class InvalidAction5(BaseAction):
        @property
        def name(self) -> str:
            return "invalid_action5"

        @property
        def cost(self) -> int:
            return 1

        def get_preconditions(self) -> dict[GameState, Any]:
            return {}

        def get_effects(self) -> dict[GameState, Any]:
            return "not a dict"  # Invalid return type

        async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
            return ActionResult(success=True, state_changes={})

    assert not registry.validate_action(InvalidAction5)

    # Test action with non-GameState keys in effects
    class InvalidAction6(BaseAction):
        @property
        def name(self) -> str:
            return "invalid_action6"

        @property
        def cost(self) -> int:
            return 1

        def get_preconditions(self) -> dict[GameState, Any]:
            return {}

        def get_effects(self) -> dict[GameState, Any]:
            return {"invalid_key": True}  # Not GameState enum

        async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
            return ActionResult(success=True, state_changes={})

    assert not registry.validate_action(InvalidAction6)

    # Test action that throws exception in validation
    class InvalidAction7(BaseAction):
        @property
        def name(self) -> str:
            return "invalid_action7"

        @property
        def cost(self) -> int:
            return 1

        def get_preconditions(self) -> dict[GameState, Any]:
            raise ValueError("Error in preconditions")

        def get_effects(self) -> dict[GameState, Any]:
            return {}

        async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
            return ActionResult(success=True, state_changes={})

    # Should handle exception gracefully and still return True for basic validation
    result = registry.validate_action(InvalidAction7)
    assert result is True  # Basic validation passes, exception in method call is handled


def test_get_action_by_name():
    """Test getting specific action by name"""
    # Clear global registry
    src.ai_player.actions._global_registry = None

    class SimpleTestAction(BaseAction):
        @property
        def name(self) -> str:
            return "simple_test_action"

        @property
        def cost(self) -> int:
            return 1

        def get_preconditions(self) -> dict[GameState, Any]:
            return {}

        def get_effects(self) -> dict[GameState, Any]:
            return {}

        async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
            return ActionResult(success=True, state_changes={})

    class ParameterizedTestAction(BaseAction):
        def __init__(self, target: str):  # Remove default to force factory usage
            self.target = target

        @property
        def name(self) -> str:
            return f"param_test_action_{self.target}"

        @property
        def cost(self) -> int:
            return 1

        def get_preconditions(self) -> dict[GameState, Any]:
            return {}

        def get_effects(self) -> dict[GameState, Any]:
            return {}

        async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
            return ActionResult(success=True, state_changes={})

    class TestFactory(ActionFactory):
        def create_instances(self, game_data: Any, current_state: dict[GameState, Any]) -> list[BaseAction]:
            return [ParameterizedTestAction("X"), ParameterizedTestAction("Y")]

        def get_action_type(self) -> type[BaseAction]:
            return ParameterizedTestAction

    registry = ActionRegistry()

    factory = TestFactory()
    registry.register_factory(factory)

    # Test finding parameterized action from factory
    action = registry.get_action_by_name("param_test_action_X", {}, {})
    assert action is not None
    assert action.name == "param_test_action_X"

    # Test finding another parameterized action from factory
    action = registry.get_action_by_name("param_test_action_Y", {}, {})
    assert action is not None
    assert action.name == "param_test_action_Y"

    # Test action not found
    action = registry.get_action_by_name("nonexistent_action", {}, {})
    assert action is None


def test_additional_error_coverage():
    """Test additional error paths to achieve 100% coverage"""

    # Test line 264-265: Exception in validate_action when creating instance fails
    class ExceptionAction(BaseAction):
        def __init__(self):
            raise ValueError("Exception in constructor")

        @property
        def name(self) -> str:
            return "exception_action"

        @property
        def cost(self) -> int:
            return 1

        def get_preconditions(self) -> dict[GameState, Any]:
            return {}

        def get_effects(self) -> dict[GameState, Any]:
            return {}

        async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
            return ActionResult(success=True, state_changes={})

    registry = ActionRegistry()
    result = registry.validate_action(ExceptionAction)
    assert result is False  # Should return False when exception occurs

    # Test lines 188-190: Exception when creating action instance in generate_actions_for_state
    class InstantiationErrorAction(BaseAction):
        def __init__(self):
            raise RuntimeError("Instantiation error")

        @property
        def name(self) -> str:
            return "instantiation_error_action"

        @property
        def cost(self) -> int:
            return 1

        def get_preconditions(self) -> dict[GameState, Any]:
            return {}

        def get_effects(self) -> dict[GameState, Any]:
            return {}

        async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
            return ActionResult(success=True, state_changes={})

    registry._discovered_actions["InstantiationErrorAction"] = InstantiationErrorAction
    actions = registry.generate_actions_for_state({}, {})
    # Should handle the error gracefully and continue

    # Test lines 300-301: Exception handling in get_action_by_name
    class ErrorInNameAction(BaseAction):
        def __init__(self):
            raise Exception("Error when creating instance")

        @property
        def name(self) -> str:
            return "error_in_name_action"

        @property
        def cost(self) -> int:
            return 1

        def get_preconditions(self) -> dict[GameState, Any]:
            return {}

        def get_effects(self) -> dict[GameState, Any]:
            return {}

        async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
            return ActionResult(success=True, state_changes={})

    registry._discovered_actions["ErrorInNameAction"] = ErrorInNameAction
    action = registry.get_action_by_name("error_in_name_action", {}, {})
    assert action is None  # Should handle error and return None


def test_abstract_methods_coverage():
    """Test abstract methods directly for 100% coverage"""

    # Test lines 42, 58: ActionFactory abstract methods (through concrete implementation)
    class ConcreteFactory(ActionFactory):
        def create_instances(self, game_data: Any, current_state: dict[GameState, Any]) -> list[BaseAction]:
            # This covers line 42
            return []

        def get_action_type(self) -> type[BaseAction]:
            # This covers line 58
            return BaseAction

    factory = ConcreteFactory()
    instances = factory.create_instances({}, {})
    assert instances == []
    action_type = factory.get_action_type()
    assert action_type == BaseAction

    # Test line 330: ParameterizedActionFactory.generate_parameters abstract method
    class ConcreteParameterizedFactory(ParameterizedActionFactory):
        def __init__(self):
            super().__init__(BaseAction)

        def generate_parameters(self, game_data: Any, current_state: dict[GameState, Any]) -> list[dict[str, Any]]:
            # This covers line 330
            return [{"param": "value"}]

    param_factory = ConcreteParameterizedFactory()
    params = param_factory.generate_parameters({}, {})
    assert params == [{"param": "value"}]


def test_action_discovery_import_error():
    """Test error handling in action discovery when import fails"""
    from unittest.mock import MagicMock

    # Test the import error handling in lines 128-132
    with patch('src.ai_player.actions.action_registry.pkgutil.iter_modules') as mock_iter:
        with patch('src.ai_player.actions.action_registry.importlib.import_module') as mock_import:
            # Create a mock module info that will cause an import error
            mock_module_info = MagicMock()
            mock_module_info.name = 'test_failing_module'
            mock_iter.return_value = [mock_module_info]

            # Make import_module raise an exception
            mock_import.side_effect = ImportError("Test import error")

            # This should trigger the error handling in lines 128-132
            registry = ActionRegistry()
            assert isinstance(registry._discovered_actions, dict)
            # Should have handled the error gracefully


def test_validation_failure_path():
    """Test the validation failure warning path (line 128)"""

    # Create a class that will fail validation but still pass the basic checks
    class FailingValidationAction(BaseAction):
        @property
        def name(self) -> str:
            return "failing_validation_action"

        @property
        def cost(self) -> int:
            return 1

        def get_preconditions(self) -> dict[GameState, Any]:
            return {"not_gamestate": True}  # This will fail validation

        def get_effects(self) -> dict[GameState, Any]:
            return {}

        async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
            return ActionResult(success=True, state_changes={})

    # Mock inspect.getmembers to return our failing action
    with patch('src.ai_player.actions.action_registry.inspect.getmembers') as mock_getmembers:
        with patch('src.ai_player.actions.action_registry.pkgutil.iter_modules') as mock_iter:
            # Set up the mock to find our action class
            mock_module_info = type('MockModuleInfo', (), {'name': 'test_module'})()
            mock_iter.return_value = [mock_module_info]

            # Make getmembers return our failing action
            mock_getmembers.return_value = [('FailingValidationAction', FailingValidationAction)]

            # Mock the module import
            with patch('src.ai_player.actions.action_registry.importlib.import_module') as mock_import:
                mock_module = type('MockModule', (), {})()
                mock_module.__dict__['FailingValidationAction'] = FailingValidationAction
                mock_import.return_value = mock_module

                # This should trigger the validation failure warning on line 128
                registry = ActionRegistry()
                # The action should not be in discovered actions because validation failed
                assert 'FailingValidationAction' not in registry._discovered_actions


if __name__ == "__main__":
    pytest.main([__file__])
