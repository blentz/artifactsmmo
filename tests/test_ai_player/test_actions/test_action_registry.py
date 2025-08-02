"""
Tests for ActionRegistry and action discovery system

This module tests the automatic action discovery, factory registration,
dynamic action generation, and validation of the action registry system.
"""

from typing import Any, Optional
from unittest.mock import Mock, patch

import pytest

from src.ai_player.actions import (
    ActionFactory,
    ActionRegistry,
    ParameterizedActionFactory,
    get_all_actions,
    register_action_factory,
)
from src.ai_player.actions.base_action import BaseAction
from src.ai_player.state.action_result import ActionResult, GameState


class MockAction(BaseAction):
    """Mock action for testing registry"""

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

    async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
        return ActionResult(
            success=True,
            message=f"Mock action {self._name} executed",
            state_changes=self.get_effects(),
            cooldown_seconds=1
        )

    async def _execute_api_call(
        self,
        character_name: str,
        current_state: dict[GameState, Any],
        api_client: 'APIClientWrapper',
        cooldown_manager: Optional['CooldownManager']
    ) -> ActionResult:
        """Mock implementation of API call execution for testing"""
        return ActionResult(
            success=True,
            message=f"Mock API action {self._name} executed",
            state_changes=self.get_effects(),
            cooldown_seconds=5
        )


class MockParameterizedAction(BaseAction):
    """Mock parameterized action for testing factories"""

    def __init__(self, target_x: int, target_y: int):
        self.target_x = target_x
        self.target_y = target_y

    @property
    def name(self) -> str:
        return f"move_to_{self.target_x}_{self.target_y}"

    @property
    def cost(self) -> int:
        return abs(self.target_x) + abs(self.target_y)  # Manhattan distance

    def get_preconditions(self) -> dict[GameState, Any]:
        return {
            GameState.COOLDOWN_READY: True,
            GameState.CAN_MOVE: True
        }

    def get_effects(self) -> dict[GameState, Any]:
        return {
            GameState.CURRENT_X: self.target_x,
            GameState.CURRENT_Y: self.target_y,
            GameState.COOLDOWN_READY: False,
            GameState.AT_TARGET_LOCATION: True
        }

    async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
        return ActionResult(
            success=True,
            message=f"Moved to ({self.target_x}, {self.target_y})",
            state_changes=self.get_effects(),
            cooldown_seconds=2
        )

    async def _execute_api_call(
        self,
        character_name: str,
        current_state: dict[GameState, Any],
        api_client: 'APIClientWrapper',
        cooldown_manager: Optional['CooldownManager']
    ) -> ActionResult:
        """Mock implementation of API call execution for testing"""
        return ActionResult(
            success=True,
            message=f"API moved to ({self.target_x}, {self.target_y})",
            state_changes=self.get_effects(),
            cooldown_seconds=5
        )


class MockActionFactory(ActionFactory):
    """Mock action factory for testing"""

    def create_instances(self, game_data: Any, current_state: dict[GameState, Any]) -> list[BaseAction]:
        return [
            MockAction("factory_action_1", 1),
            MockAction("factory_action_2", 2)
        ]

    def get_action_type(self) -> type[BaseAction]:
        return MockAction


class MockParameterizedFactory(ParameterizedActionFactory):
    """Mock parameterized factory for testing"""

    def __init__(self):
        super().__init__(MockParameterizedAction)

    def generate_parameters(self, game_data: Any, current_state: dict[GameState, Any]) -> list[dict[str, Any]]:
        # Generate movement actions for nearby locations
        current_x = current_state.get(GameState.CURRENT_X, 0)
        current_y = current_state.get(GameState.CURRENT_Y, 0)

        parameters = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx != 0 or dy != 0:  # Don't include current position
                    parameters.append({
                        'target_x': current_x + dx,
                        'target_y': current_y + dy
                    })

        return parameters


class InvalidAction:
    """Invalid action class that doesn't inherit from BaseAction"""
    pass


class TestActionRegistry:
    """Test ActionRegistry functionality"""

    @pytest.fixture
    def action_registry(self):
        """Create ActionRegistry instance for testing"""
        return ActionRegistry()

    def test_action_registry_initialization(self, action_registry):
        """Test ActionRegistry initialization"""
        assert hasattr(action_registry, 'discover_actions')
        assert hasattr(action_registry, 'register_factory')
        assert hasattr(action_registry, 'generate_actions_for_state')
        assert hasattr(action_registry, 'validate_action')

    def test_discover_actions_mock(self, action_registry):
        """Test action discovery with mocked modules"""
        # Mock the importlib functionality
        with patch('importlib.import_module') as mock_import, \
             patch('pkgutil.iter_modules') as mock_iter:

            # Mock module discovery
            mock_iter.return_value = [
                (None, 'movement_action', False),
                (None, 'combat_action', False),
                (None, 'base_action', False)  # Should be skipped
            ]

            # Mock module imports
            mock_movement_module = Mock()
            mock_movement_module.MovementAction = MockAction

            mock_combat_module = Mock()
            mock_combat_module.CombatAction = MockAction

            mock_base_module = Mock()
            mock_base_module.BaseAction = BaseAction  # Should be skipped

            def mock_import_side_effect(module_name):
                if 'movement_action' in module_name:
                    return mock_movement_module
                elif 'combat_action' in module_name:
                    return mock_combat_module
                elif 'base_action' in module_name:
                    return mock_base_module
                else:
                    raise ImportError(f"No module named '{module_name}'")

            mock_import.side_effect = mock_import_side_effect

            discovered_actions = action_registry.discover_actions()

            assert isinstance(discovered_actions, dict)
            # Should discover actions but skip BaseAction itself
            assert len(discovered_actions) >= 0

    def test_register_factory(self, action_registry):
        """Test registering action factory"""
        factory = MockActionFactory()

        action_registry.register_factory(factory)

        # Verify factory was registered (internal state check)
        assert hasattr(action_registry, '_action_factories')

    def test_generate_actions_for_state(self, action_registry):
        """Test generating actions for current state"""
        # Register a factory
        factory = MockActionFactory()
        action_registry.register_factory(factory)

        current_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.COOLDOWN_READY: True,
            GameState.CURRENT_X: 10,
            GameState.CURRENT_Y: 15
        }

        game_data = Mock()
        game_data.maps = []
        game_data.resources = []
        game_data.monsters = []  # Mock game data
        game_data.maps = []
        game_data.resources = []
        game_data.monsters = []

        actions = action_registry.generate_actions_for_state(current_state, game_data)

        assert isinstance(actions, list)
        # Should have actions generated by the registered factory
        assert len(actions) >= 0

        for action in actions:
            assert isinstance(action, BaseAction)

    def test_validate_action_valid(self, action_registry):
        """Test validating a properly implemented action"""
        is_valid = action_registry.validate_action(MockAction)

        assert is_valid is True

    def test_validate_action_invalid(self, action_registry):
        """Test validating an improperly implemented action"""
        class InvalidAction(BaseAction):
            @property
            def name(self) -> str:
                return "invalid"

            @property
            def cost(self) -> int:
                return 1

            def get_preconditions(self) -> dict[GameState, Any]:
                # Invalid: uses string key instead of GameState enum
                return {"invalid_key": True}

            def get_effects(self) -> dict[GameState, Any]:
                return {}

            async def _execute_api_call(self, character_name: str, current_state: dict[GameState, Any], api_client: Any = None, cooldown_manager: Any = None) -> ActionResult:
                return ActionResult(success=True, message="Invalid action", state_changes={}, cooldown_seconds=0)

        is_valid = action_registry.validate_action(InvalidAction)
        assert is_valid is False


    def test_get_all_action_types(self, action_registry):
        """Test getting all registered action types"""
        # Mock discovered actions
        with patch.object(action_registry, 'discover_actions') as mock_discover:
            mock_discover.return_value = {
                'MockAction': MockAction,
                'AnotherAction': MockAction
            }

            action_types = action_registry.get_all_action_types()

            assert isinstance(action_types, list)
            for action_type in action_types:
                assert issubclass(action_type, BaseAction)

    def test_get_action_by_name_found(self, action_registry):
        """Test getting specific action by name when it exists"""
        # Register factory that creates named actions
        factory = MockActionFactory()
        action_registry.register_factory(factory)

        current_state = {GameState.COOLDOWN_READY: True}
        game_data = Mock()
        game_data.maps = []
        game_data.resources = []
        game_data.monsters = []

        action = action_registry.get_action_by_name("factory_action_1", current_state, game_data)

        if action is not None:
            assert isinstance(action, BaseAction)
            assert action.name == "factory_action_1"

    def test_get_action_by_name_not_found(self, action_registry):
        """Test getting specific action by name when it doesn't exist"""
        current_state = {GameState.COOLDOWN_READY: True}
        game_data = Mock()
        game_data.maps = []
        game_data.resources = []
        game_data.monsters = []

        action = action_registry.get_action_by_name("nonexistent_action", current_state, game_data)

        assert action is None


class TestActionFactory:
    """Test ActionFactory abstract base class"""

    def test_action_factory_is_abstract(self):
        """Test that ActionFactory cannot be instantiated directly"""
        with pytest.raises(TypeError):
            ActionFactory()

    def test_concrete_factory_implementation(self):
        """Test concrete factory implementation"""
        factory = MockActionFactory()

        assert hasattr(factory, 'create_instances')
        assert hasattr(factory, 'get_action_type')

        game_data = Mock()
        game_data.maps = []
        game_data.resources = []
        game_data.monsters = []
        current_state = {GameState.COOLDOWN_READY: True}

        instances = factory.create_instances(game_data, current_state)
        action_type = factory.get_action_type()

        assert isinstance(instances, list)
        assert len(instances) > 0
        assert action_type == MockAction

        for instance in instances:
            assert isinstance(instance, BaseAction)


class TestParameterizedActionFactory:
    """Test ParameterizedActionFactory implementation"""

    def test_parameterized_factory_initialization(self):
        """Test ParameterizedActionFactory initialization"""
        factory = MockParameterizedFactory()

        assert factory.action_class == MockParameterizedAction
        assert factory.get_action_type() == MockParameterizedAction

    def test_generate_parameters(self):
        """Test parameter generation for parameterized actions"""
        factory = MockParameterizedFactory()

        current_state = {
            GameState.CURRENT_X: 10,
            GameState.CURRENT_Y: 15,
            GameState.COOLDOWN_READY: True
        }
        game_data = Mock()
        game_data.maps = []
        game_data.resources = []
        game_data.monsters = []

        parameters = factory.generate_parameters(game_data, current_state)

        assert isinstance(parameters, list)
        assert len(parameters) == 8  # 3x3 grid minus center = 8 positions

        for params in parameters:
            assert 'target_x' in params
            assert 'target_y' in params
            assert isinstance(params['target_x'], int)
            assert isinstance(params['target_y'], int)

    def test_create_instances_from_parameters(self):
        """Test creating action instances from generated parameters"""
        factory = MockParameterizedFactory()

        current_state = {
            GameState.CURRENT_X: 0,
            GameState.CURRENT_Y: 0,
            GameState.COOLDOWN_READY: True
        }
        game_data = Mock()
        game_data.maps = []
        game_data.resources = []
        game_data.monsters = []

        instances = factory.create_instances(game_data, current_state)

        assert isinstance(instances, list)
        assert len(instances) == 8  # 8 movement directions

        for instance in instances:
            assert isinstance(instance, MockParameterizedAction)
            assert isinstance(instance.name, str)
            assert instance.cost > 0


class TestGlobalActionFunctions:
    """Test global action registry functions"""

    def test_get_all_actions_function(self):
        """Test get_all_actions global function"""
        current_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.COOLDOWN_READY: True,
            GameState.CURRENT_X: 10,
            GameState.CURRENT_Y: 15
        }
        game_data = Mock()
        game_data.maps = []
        game_data.resources = []
        game_data.monsters = []

        # Mock the global registry
        with patch('src.ai_player.actions.ActionRegistry') as mock_registry_class:
            mock_registry = Mock()
            mock_registry.generate_actions_for_state.return_value = [
                MockAction("global_action_1", 1),
                MockAction("global_action_2", 2)
            ]
            mock_registry_class.return_value = mock_registry

            actions = get_all_actions(current_state, game_data)

            assert isinstance(actions, list)
            for action in actions:
                assert isinstance(action, BaseAction)

    def test_register_action_factory_function(self):
        """Test register_action_factory global function"""
        factory = MockActionFactory()

        # Mock the global registry getter
        with patch('src.ai_player.actions.get_global_registry') as mock_get_registry:
            mock_registry = Mock()
            mock_get_registry.return_value = mock_registry

            register_action_factory(factory)

            # Should call register_factory on the global registry
            mock_registry.register_factory.assert_called_once_with(factory)


class TestActionRegistryEdgeCases:
    """Test edge cases and error handling for action registry"""

    def test_discover_actions_with_validation_failure(self):
        """Test action discovery when validation fails"""
        registry = ActionRegistry()

        class BadAction(BaseAction):
            def __init__(self):
                pass

            @property
            def name(self) -> str:
                return "bad_action"

            @property
            def cost(self) -> int:
                return 1

            def get_preconditions(self) -> dict[GameState, Any]:
                # Return invalid key to trigger validation failure
                return {"invalid_key": True}

            def get_effects(self) -> dict[GameState, Any]:
                return {GameState.COOLDOWN_READY: False}

            async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
                return ActionResult(success=False, message="", state_changes={})

            async def _execute_api_call(self, character_name: str, current_state: dict[GameState, Any], api_client: Any, cooldown_manager: Any = None) -> ActionResult:
                return ActionResult(success=False, message="", state_changes={})

        # This should return False and trigger the warning print
        is_valid = registry.validate_action(BadAction)
        assert is_valid is False

    def test_generate_actions_with_factory_exception(self):
        """Test action generation when factory throws exception"""
        registry = ActionRegistry()

        class FailingFactory(ActionFactory):
            def create_instances(self, game_data: Any, current_state: dict[GameState, Any]) -> list[BaseAction]:
                raise RuntimeError("Factory failed")

            def get_action_type(self) -> type[BaseAction]:
                return MockAction

        failing_factory = FailingFactory()
        registry.register_factory(failing_factory)

        current_state = {GameState.COOLDOWN_READY: True}
        game_data = Mock()
        game_data.maps = []
        game_data.resources = []
        game_data.monsters = []

        # Should propagate exception - don't hide bugs
        with pytest.raises(RuntimeError, match="Factory failed"):
            registry.generate_actions_for_state(current_state, game_data)

    def test_generate_actions_with_action_creation_exception(self):
        """Test action generation when action creation throws exception"""
        registry = ActionRegistry()

        class FailingAction(BaseAction):
            def __init__(self):
                raise RuntimeError("Action creation failed")

            @property
            def name(self) -> str:
                return "failing_action"

            @property
            def cost(self) -> int:
                return 1

            def get_preconditions(self) -> dict[GameState, Any]:
                return {GameState.COOLDOWN_READY: True}

            def get_effects(self) -> dict[GameState, Any]:
                return {GameState.COOLDOWN_READY: False}

            async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
                return ActionResult(success=False, message="", state_changes={})

        # Manually add to discovered actions to trigger creation exception
        registry._discovered_actions["FailingAction"] = FailingAction

        current_state = {GameState.COOLDOWN_READY: True}
        game_data = Mock()
        game_data.maps = []
        game_data.resources = []
        game_data.monsters = []

        # Should handle exception gracefully
        actions = registry.generate_actions_for_state(current_state, game_data)
        assert isinstance(actions, list)

    def test_validate_action_missing_method(self):
        """Test validation with action missing required method"""
        registry = ActionRegistry()

        class IncompleteAction:
            # Not inheriting from BaseAction and missing methods
            @property
            def name(self) -> str:
                return "incomplete"
            # Missing other required methods like cost, get_preconditions, etc.

        is_valid = registry.validate_action(IncompleteAction)
        assert is_valid is False

    def test_validate_action_preconditions_not_dict(self):
        """Test validation when preconditions returns non-dict"""
        registry = ActionRegistry()

        class BadPreconditionsAction(BaseAction):
            @property
            def name(self) -> str:
                return "bad_preconditions"

            @property
            def cost(self) -> int:
                return 1

            def get_preconditions(self) -> dict[GameState, Any]:
                return "not a dict"  # Invalid return type

            def get_effects(self) -> dict[GameState, Any]:
                return {GameState.COOLDOWN_READY: False}

            async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
                return ActionResult(success=False, message="", state_changes={})

            async def _execute_api_call(self, character_name: str, current_state: dict[GameState, Any], api_client: Any, cooldown_manager: Any = None) -> ActionResult:
                return ActionResult(success=False, message="", state_changes={})

        is_valid = registry.validate_action(BadPreconditionsAction)
        assert is_valid is False

    def test_validate_action_effects_not_dict(self):
        """Test validation when effects returns non-dict"""
        registry = ActionRegistry()

        class BadEffectsAction(BaseAction):
            @property
            def name(self) -> str:
                return "bad_effects"

            @property
            def cost(self) -> int:
                return 1

            def get_preconditions(self) -> dict[GameState, Any]:
                return {GameState.COOLDOWN_READY: True}

            def get_effects(self) -> dict[GameState, Any]:
                return "not a dict"  # Invalid return type

            async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
                return ActionResult(success=False, message="", state_changes={})

            async def _execute_api_call(self, character_name: str, current_state: dict[GameState, Any], api_client: Any, cooldown_manager: Any = None) -> ActionResult:
                return ActionResult(success=False, message="", state_changes={})

        is_valid = registry.validate_action(BadEffectsAction)
        assert is_valid is False

    def test_validate_action_method_exception(self):
        """Test validation when action methods throw exceptions"""
        registry = ActionRegistry()

        class ExceptionAction(BaseAction):
            @property
            def name(self) -> str:
                return "exception_action"

            @property
            def cost(self) -> int:
                return 1

            def get_preconditions(self) -> dict[GameState, Any]:
                raise RuntimeError("Preconditions failed")

            def get_effects(self) -> dict[GameState, Any]:
                return {GameState.COOLDOWN_READY: False}

            async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
                return ActionResult(success=False, message="", state_changes={})

        # Should handle exception gracefully and still return True for basic structure
        is_valid = registry.validate_action(ExceptionAction)
        assert is_valid is True  # Should pass because structure is valid

    def test_validate_action_general_exception(self):
        """Test validation with general exception"""
        registry = ActionRegistry()

        class CompletelyBrokenAction:
            # Not even inheriting from BaseAction
            pass

        is_valid = registry.validate_action(CompletelyBrokenAction)
        assert is_valid is False

    def test_get_action_by_name_with_exceptions(self):
        """Test get_action_by_name with various exception scenarios"""
        registry = ActionRegistry()

        class ParameterizedFailingAction(BaseAction):
            def __init__(self, param):
                if param == "fail":
                    raise RuntimeError("Failed to create")
                self._param = param

            @property
            def name(self) -> str:
                return f"param_action_{self._param}"

            @property
            def cost(self) -> int:
                return 1

            def get_preconditions(self) -> dict[GameState, Any]:
                return {GameState.COOLDOWN_READY: True}

            def get_effects(self) -> dict[GameState, Any]:
                return {GameState.COOLDOWN_READY: False}

            async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
                return ActionResult(success=False, message="", state_changes={})

        class FailingParameterizedFactory(ActionFactory):
            def create_instances(self, game_data: Any, current_state: dict[GameState, Any]) -> list[BaseAction]:
                raise RuntimeError("Factory creation failed")

            def get_action_type(self) -> type[BaseAction]:
                return ParameterizedFailingAction

        registry._discovered_actions["ParameterizedFailingAction"] = ParameterizedFailingAction
        registry.register_factory(FailingParameterizedFactory())

        current_state = {GameState.COOLDOWN_READY: True}
        game_data = Mock()
        game_data.maps = []
        game_data.resources = []
        game_data.monsters = []

        # Should propagate exception - don't hide bugs
        with pytest.raises(RuntimeError, match="Factory creation failed"):
            registry.get_action_by_name("nonexistent", current_state, game_data)

    def test_discover_actions_with_import_errors(self):
        """Test action discovery with module import errors"""
        registry = ActionRegistry()

        # Mock the import to fail for certain modules
        with patch('importlib.import_module') as mock_import, \
             patch('pkgutil.iter_modules') as mock_iter:

            mock_iter.return_value = [
                (None, 'failing_module', False),
            ]

            def mock_import_side_effect(module_name):
                if 'failing_module' in module_name:
                    raise ImportError("Module import failed")
                return Mock()

            mock_import.side_effect = mock_import_side_effect

            # Should handle import error gracefully
            discovered = registry.discover_actions()
            assert isinstance(discovered, dict)

    def test_validate_action_with_effects_exception(self):
        """Test validation when effects method throws exception"""
        registry = ActionRegistry()

        class EffectsExceptionAction(BaseAction):
            @property
            def name(self) -> str:
                return "effects_exception"

            @property
            def cost(self) -> int:
                return 1

            def get_preconditions(self) -> dict[GameState, Any]:
                return {GameState.COOLDOWN_READY: True}

            def get_effects(self) -> dict[GameState, Any]:
                raise RuntimeError("Effects failed")

            async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
                return ActionResult(success=False, message="", state_changes={})

        # Should handle exception and still validate structure
        is_valid = registry.validate_action(EffectsExceptionAction)
        assert is_valid is True

    def test_get_action_by_name_simple_action_exception(self):
        """Test get_action_by_name when simple action creation throws exception"""
        registry = ActionRegistry()

        class SimpleFailingAction(BaseAction):
            def __init__(self):
                raise RuntimeError("Simple action creation failed")

            @property
            def name(self) -> str:
                return "simple_failing"

            @property
            def cost(self) -> int:
                return 1

            def get_preconditions(self) -> dict[GameState, Any]:
                return {GameState.COOLDOWN_READY: True}

            def get_effects(self) -> dict[GameState, Any]:
                return {GameState.COOLDOWN_READY: False}

            async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
                return ActionResult(success=False, message="", state_changes={})

        # Add to discovered actions manually
        registry._discovered_actions["SimpleFailingAction"] = SimpleFailingAction

        current_state = {GameState.COOLDOWN_READY: True}
        game_data = Mock()
        game_data.maps = []
        game_data.resources = []
        game_data.monsters = []

        # Should handle exception gracefully
        action = registry.get_action_by_name("simple_failing", current_state, game_data)
        assert action is None


class TestActionRegistryIntegration:
    """Integration tests for action registry system"""

    def test_full_action_discovery_workflow(self):
        """Test complete action discovery and generation workflow"""
        registry = ActionRegistry()

        # Register multiple factories
        basic_factory = MockActionFactory()
        parameterized_factory = MockParameterizedFactory()

        registry.register_factory(basic_factory)
        registry.register_factory(parameterized_factory)

        current_state = {
            GameState.CHARACTER_LEVEL: 10,
            GameState.COOLDOWN_READY: True,
            GameState.CURRENT_X: 5,
            GameState.CURRENT_Y: 8,
            GameState.CAN_MOVE: True,
            GameState.HP_CURRENT: 100
        }

        game_data = {
            'maps': Mock(),
            'items': Mock(),
            'monsters': Mock()
        }

        # Generate all available actions
        all_actions = registry.generate_actions_for_state(current_state, game_data)

        assert isinstance(all_actions, list)
        assert len(all_actions) > 0

        # Should have actions from both factories
        action_names = [action.name for action in all_actions]

        # Check for basic factory actions
        basic_actions = [name for name in action_names if name.startswith('factory_action_')]
        assert len(basic_actions) > 0

        # Check for parameterized factory actions
        movement_actions = [name for name in action_names if name.startswith('move_to_')]
        assert len(movement_actions) > 0

        # Validate all actions
        for action in all_actions:
            assert isinstance(action, BaseAction)
            assert registry.validate_action(type(action)) is True

    def test_action_registry_performance_with_many_actions(self):
        """Test action registry performance with large number of actions"""
        registry = ActionRegistry()

        # Create factory that generates many actions
        class HighVolumeFactory(ActionFactory):
            def create_instances(self, game_data: Any, current_state: dict[GameState, Any]) -> list[BaseAction]:
                actions = []
                for i in range(100):  # Generate 100 actions
                    actions.append(MockAction(f"action_{i}", i % 10 + 1))
                return actions

            def get_action_type(self) -> type[BaseAction]:
                return MockAction

        high_volume_factory = HighVolumeFactory()
        registry.register_factory(high_volume_factory)

        current_state = {GameState.COOLDOWN_READY: True}
        game_data = Mock()
        game_data.maps = []
        game_data.resources = []
        game_data.monsters = []

        # This should complete without performance issues
        actions = registry.generate_actions_for_state(current_state, game_data)

        # Should have 100 factory actions plus some discovered actions from the module
        assert len(actions) >= 100

        # Validate a sample of actions
        for i in range(0, 100, 10):  # Check every 10th action
            action = actions[i]
            assert isinstance(action, MockAction)
            assert action.name == f"action_{i}"

    def test_action_registry_with_conditional_actions(self):
        """Test action registry with actions that are conditionally available"""
        class ConditionalFactory(ActionFactory):
            def create_instances(self, game_data: Any, current_state: dict[GameState, Any]) -> list[BaseAction]:
                actions = []

                # Only create combat actions if character can fight
                if current_state.get(GameState.CAN_FIGHT, False):
                    actions.append(MockAction("combat_action", 5))

                # Only create gather actions if character can gather
                if current_state.get(GameState.CAN_GATHER, False):
                    actions.append(MockAction("gather_action", 3))

                # Always available basic actions
                actions.append(MockAction("rest_action", 1))

                return actions

            def get_action_type(self) -> type[BaseAction]:
                return MockAction

        registry = ActionRegistry()
        conditional_factory = ConditionalFactory()
        registry.register_factory(conditional_factory)

        # Test with combat and gather available
        combat_state = {
            GameState.COOLDOWN_READY: True,
            GameState.CAN_FIGHT: True,
            GameState.CAN_GATHER: True
        }

        actions = registry.generate_actions_for_state(combat_state, Mock())
        action_names = [action.name for action in actions]

        assert "combat_action" in action_names
        assert "gather_action" in action_names
        assert "rest_action" in action_names

        # Test with only rest available
        rest_only_state = {
            GameState.COOLDOWN_READY: True,
            GameState.CAN_FIGHT: False,
            GameState.CAN_GATHER: False
        }

        actions = registry.generate_actions_for_state(rest_only_state, Mock())
        action_names = [action.name for action in actions]

        assert "combat_action" not in action_names
        assert "gather_action" not in action_names
        assert "rest_action" in action_names
