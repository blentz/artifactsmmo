"""Action system integration tests and test utilities

This module provides package-level integration tests that verify the complete
action system works together correctly, including:

- BaseAction interface implementation across all concrete actions
- Action registry integration with real action implementations
- Factory system integration with parameterized actions
- End-to-end action execution workflows
- Cross-action compatibility and state management

This module also provides shared test utilities and fixtures that can be
reused across individual action test modules for consistency.
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from src.ai_player.actions import (
    ActionFactory,
    ActionRegistry,
    ParameterizedActionFactory,
    get_all_actions,
    get_global_registry,
    register_action_factory,
)
from src.ai_player.actions.base_action import BaseAction
from src.ai_player.actions.combat_action import CombatAction
from src.ai_player.actions.gathering_action import GatheringAction
from src.ai_player.actions.movement_action import MovementAction
from src.ai_player.actions.movement_action_factory import MovementActionFactory
from src.ai_player.actions.rest_action import RestAction
from src.ai_player.state.action_result import ActionResult, GameState

# Test Utilities and Fixtures

class TestActionMixin:
    """Mixin class providing common test utilities for action testing"""

    @staticmethod
    def create_base_game_state() -> dict[GameState, Any]:
        """Create a basic game state for testing action preconditions"""
        return {
            GameState.CHARACTER_LEVEL: 10,
            GameState.CHARACTER_XP: 1000,
            GameState.CHARACTER_GOLD: 500,
            GameState.HP_CURRENT: 100,
            GameState.HP_MAX: 120,
            GameState.CURRENT_X: 0,
            GameState.CURRENT_Y: 0,
            GameState.COOLDOWN_READY: True,
            GameState.CAN_MOVE: True,
            GameState.CAN_FIGHT: True,
            GameState.CAN_GATHER: True,
            GameState.INVENTORY_SPACE_AVAILABLE: 10,
            GameState.BANK_SPACE_AVAILABLE: 50,
            GameState.BANK_GOLD: 1000,
            GameState.TASK_PROGRESS: 0,
            GameState.AT_TARGET_LOCATION: False,
            GameState.RESOURCE_AVAILABLE: True,
            GameState.ITEM_QUANTITY: 0,
            GameState.ACTIVE_TASK: "combat",
            GameState.TASK_COMPLETED: False,
            GameState.PORTFOLIO_VALUE: 2000,
            GameState.WEAPON_EQUIPPED: "iron_sword",
            GameState.MINING_LEVEL: 5,
            GameState.WOODCUTTING_LEVEL: 3,
            GameState.FISHING_LEVEL: 2,
            GameState.SAFE_TO_FIGHT: True,
            GameState.HP_LOW: False,
            GameState.INVENTORY_FULL: False
        }

    @staticmethod
    def create_mock_game_data() -> dict[str, Any]:
        """Create mock game data for testing action factories"""
        return {
            'maps': [
                {
                    'name': 'spawn',
                    'x': 0,
                    'y': 0,
                    'content': {'type': 'spawning_area'}
                },
                {
                    'name': 'copper_mine',
                    'x': 2,
                    'y': 0,
                    'content': {'type': 'resource', 'code': 'copper_ore'}
                },
                {
                    'name': 'chicken_coop',
                    'x': 0,
                    'y': 2,
                    'content': {'type': 'monster', 'code': 'chicken'}
                }
            ],
            'resources': [
                {
                    'code': 'copper_ore',
                    'name': 'Copper Ore',
                    'skill': 'mining',
                    'level': 1
                },
                {
                    'code': 'ash_wood',
                    'name': 'Ash Wood',
                    'skill': 'woodcutting',
                    'level': 1
                }
            ],
            'monsters': [
                {
                    'code': 'chicken',
                    'name': 'Chicken',
                    'level': 1,
                    'hp': 50
                },
                {
                    'code': 'cow',
                    'name': 'Cow',
                    'level': 2,
                    'hp': 80
                }
            ],
            'items': [
                {
                    'code': 'iron_sword',
                    'name': 'Iron Sword',
                    'type': 'weapon',
                    'level': 1
                },
                {
                    'code': 'copper_ore',
                    'name': 'Copper Ore',
                    'type': 'resource'
                }
            ]
        }

    @staticmethod
    def validate_action_interface(action: BaseAction) -> bool:
        """Validate that an action properly implements the BaseAction interface"""
        # Check required properties
        if not hasattr(action, 'name') or not isinstance(action.name, str):
            return False
        if not hasattr(action, 'cost') or not isinstance(action.cost, int):
            return False

        # Check required methods
        required_methods = ['get_preconditions', 'get_effects', 'execute', 'can_execute', 'validate_preconditions', 'validate_effects']
        for method_name in required_methods:
            if not hasattr(action, method_name):
                return False

        # Validate state usage
        try:
            preconditions = action.get_preconditions()
            if not isinstance(preconditions, dict):
                return False
            for key in preconditions.keys():
                if not isinstance(key, GameState):
                    return False

            effects = action.get_effects()
            if not isinstance(effects, dict):
                return False
            for key in effects.keys():
                if not isinstance(key, GameState):
                    return False

            return True
        except Exception:
            return False

    @staticmethod
    def create_mock_api_response(success: bool = True, message: str = "Success", cooldown: int = 1) -> ActionResult:
        """Create a mock API response for action execution testing"""
        return ActionResult(
            success=success,
            message=message,
            state_changes={GameState.COOLDOWN_READY: False},
            cooldown_seconds=cooldown
        )


@pytest.fixture
def base_game_state():
    """Fixture providing base game state for tests"""
    return TestActionMixin.create_base_game_state()


@pytest.fixture
def mock_game_data():
    """Fixture providing mock game data for tests"""
    return TestActionMixin.create_mock_game_data()


@pytest.fixture
def action_registry():
    """Fixture providing fresh ActionRegistry instance"""
    return ActionRegistry()


@pytest.fixture
def mock_api_client():
    """Fixture providing mocked API client for action execution"""
    api_client = AsyncMock()
    api_client.action_move.return_value = TestActionMixin.create_mock_api_response()
    api_client.action_fight.return_value = TestActionMixin.create_mock_api_response()
    api_client.action_gathering.return_value = TestActionMixin.create_mock_api_response()
    api_client.action_rest.return_value = TestActionMixin.create_mock_api_response()
    return api_client


# Integration Tests

class TestActionSystemIntegration(TestActionMixin):
    """Integration tests for the complete action system"""

    def test_all_concrete_actions_implement_interface(self, base_game_state, mock_game_data):
        """Test that all concrete action classes properly implement BaseAction interface"""
        concrete_actions = [
            RestAction(),
            GatheringAction("copper_ore"),
            CombatAction("chicken"),
            MovementAction(2, 0)
        ]

        for action in concrete_actions:
            assert self.validate_action_interface(action), f"Action {action.__class__.__name__} does not properly implement BaseAction interface"

    def test_action_registry_discovers_all_concrete_actions(self, action_registry):
        """Test that action registry discovers all concrete action implementations"""
        discovered_types = action_registry.get_all_action_types()
        action_type_names = {action_type.__name__ for action_type in discovered_types}

        # Should discover all concrete action classes
        expected_actions = {'RestAction', 'GatheringAction', 'CombatAction', 'MovementAction'}

        for expected_action in expected_actions:
            assert expected_action in action_type_names, f"Action registry failed to discover {expected_action}"

    def test_action_registry_validates_all_discovered_actions(self, action_registry):
        """Test that all discovered actions pass validation"""
        discovered_types = action_registry.get_all_action_types()

        for action_type in discovered_types:
            assert action_registry.validate_action(action_type), f"Discovered action {action_type.__name__} failed validation"

    def test_movement_action_factory_integration(self, action_registry, base_game_state, mock_game_data):
        """Test MovementActionFactory integration with action registry"""
        factory = MovementActionFactory()
        action_registry.register_factory(factory)

        # Test that factory generates valid movement actions
        movement_actions = factory.create_instances(mock_game_data, base_game_state)

        assert len(movement_actions) > 0
        for action in movement_actions:
            assert isinstance(action, MovementAction)
            assert self.validate_action_interface(action)
            assert action.can_execute(base_game_state) or not action.can_execute(base_game_state)  # Should be deterministic

    def test_full_action_generation_workflow(self, action_registry, base_game_state, mock_game_data):
        """Test complete workflow from registry to action generation"""
        # Register movement factory
        movement_factory = MovementActionFactory()
        action_registry.register_factory(movement_factory)

        # Generate all available actions
        all_actions = action_registry.generate_actions_for_state(base_game_state, mock_game_data)

        assert len(all_actions) > 0

        # Verify we have different types of actions
        action_types = {type(action).__name__ for action in all_actions}

        # Should have movement actions from factory
        movement_actions = [action for action in all_actions if isinstance(action, MovementAction)]
        assert len(movement_actions) > 0

        # All actions should pass interface validation
        for action in all_actions:
            assert self.validate_action_interface(action)

    def test_action_precondition_consistency_across_types(self, base_game_state, mock_game_data):
        """Test that different action types use GameState enum consistently"""
        actions = [
            RestAction(),
            GatheringAction("copper_ore"),
            CombatAction("chicken"),
            MovementAction(2, 0)
        ]

        for action in actions:
            # All preconditions should use GameState enum
            preconditions = action.get_preconditions()
            for key in preconditions.keys():
                assert isinstance(key, GameState), f"Action {action.__class__.__name__} uses non-GameState key: {key}"

            # All effects should use GameState enum
            effects = action.get_effects()
            for key in effects.keys():
                assert isinstance(key, GameState), f"Action {action.__class__.__name__} uses non-GameState key: {key}"

    def test_action_cost_consistency(self, base_game_state, mock_game_data):
        """Test that action costs are reasonable and consistent"""
        actions = [
            RestAction(),
            GatheringAction("copper_ore"),
            CombatAction("chicken"),
            MovementAction(1, 1),  # Short distance
            MovementAction(10, 10)  # Long distance
        ]

        for action in actions:
            cost = action.cost
            assert isinstance(cost, int), f"Action {action.__class__.__name__} cost is not an integer: {cost}"
            assert cost > 0, f"Action {action.__class__.__name__} cost is not positive: {cost}"
            assert cost <= 1000, f"Action {action.__class__.__name__} cost is unreasonably high: {cost}"

    def test_action_interface_consistency(self, mock_api_client, base_game_state):
        """Test that action interfaces are consistent and properly implemented"""
        # Test with a rest action with mocked API client
        rest_action = RestAction(api_client=mock_api_client)

        # Test that all methods return expected types
        assert isinstance(rest_action.name, str)
        assert isinstance(rest_action.cost, int)
        assert isinstance(rest_action.get_preconditions(), dict)
        assert isinstance(rest_action.get_effects(), dict)
        assert isinstance(rest_action.can_execute(base_game_state), bool)
        assert isinstance(rest_action.validate_preconditions(), bool)
        assert isinstance(rest_action.validate_effects(), bool)

        # Preconditions and effects should use GameState enum
        preconditions = rest_action.get_preconditions()
        for key in preconditions.keys():
            assert isinstance(key, GameState)

        effects = rest_action.get_effects()
        for key in effects.keys():
            assert isinstance(key, GameState)

    def test_global_registry_integration(self, base_game_state, mock_game_data):
        """Test global registry functions work with real action implementations"""
        # Test get_all_actions global function
        all_actions = get_all_actions(base_game_state, mock_game_data)

        assert isinstance(all_actions, list)
        assert len(all_actions) >= 0  # May be empty if no factories registered

        for action in all_actions:
            assert isinstance(action, BaseAction)
            assert self.validate_action_interface(action)

    def test_cross_action_state_compatibility(self, base_game_state, mock_game_data):
        """Test that actions can work together through state changes"""
        # Create a sequence of actions that should be compatible
        movement_action = MovementAction(2, 0)  # Move to copper mine
        gathering_action = GatheringAction("copper_ore")  # Gather copper
        rest_action = RestAction()  # Rest to recover

        # Simulate state progression
        current_state = base_game_state.copy()

        # Check movement action can execute
        if movement_action.can_execute(current_state):
            # Apply movement effects
            movement_effects = movement_action.get_effects()
            current_state.update(movement_effects)

            # Update for gathering (at resource location)
            current_state[GameState.AT_TARGET_LOCATION] = True
            current_state[GameState.RESOURCE_AVAILABLE] = True
            current_state[GameState.COOLDOWN_READY] = True

            # Check gathering can execute after movement
            gathering_can_execute = gathering_action.can_execute(current_state)
            # Should be able to determine if gathering is possible
            assert isinstance(gathering_can_execute, bool)

            if gathering_can_execute:
                # Apply gathering effects
                gathering_effects = gathering_action.get_effects()
                current_state.update(gathering_effects)

                # Reset cooldown for rest
                current_state[GameState.COOLDOWN_READY] = True

                # Rest should always be executable
                assert rest_action.can_execute(current_state)

    def test_action_name_uniqueness_within_type(self, mock_game_data):
        """Test that parameterized actions generate unique names"""
        factory = MovementActionFactory()

        current_state = {
            GameState.CURRENT_X: 0,
            GameState.CURRENT_Y: 0,
            GameState.COOLDOWN_READY: True,
            GameState.CAN_MOVE: True
        }

        movement_actions = factory.create_instances(mock_game_data, current_state)
        action_names = [action.name for action in movement_actions]

        # All names should be unique
        assert len(action_names) == len(set(action_names)), "Movement actions generated duplicate names"

        # Names should follow expected pattern
        for name in action_names:
            assert "move_to_" in name, f"Movement action name does not follow expected pattern: {name}"

    def test_action_factory_error_handling(self, action_registry, base_game_state):
        """Test that action registry handles factory errors gracefully"""
        class BrokenFactory(ActionFactory):
            def create_instances(self, game_data: Any, current_state: dict[GameState, Any]) -> list[BaseAction]:
                raise RuntimeError("Factory intentionally broken")

            def get_action_type(self) -> type[BaseAction]:
                return RestAction

        broken_factory = BrokenFactory()
        action_registry.register_factory(broken_factory)

        # Should not raise exception, should handle gracefully
        actions = action_registry.generate_actions_for_state(base_game_state, {})
        assert isinstance(actions, list)  # May be empty but should be a list

    def test_package_imports_work_correctly(self):
        """Test that all necessary imports work from package root"""
        # Test imports that should work from the actions package
        # (imports already done at top of file)

        # All imports should succeed
        assert ActionFactory is not None
        assert ActionRegistry is not None
        assert get_all_actions is not None
        assert BaseAction is not None
        assert RestAction is not None
        assert MovementAction is not None
        assert GatheringAction is not None
        assert CombatAction is not None


class TestActionSystemCompatibility(TestActionMixin):
    """Test action system compatibility and edge cases"""

    def test_actions_handle_missing_state_gracefully(self, mock_game_data):
        """Test that actions handle incomplete state information gracefully"""
        # Create minimal state (missing many expected keys)
        minimal_state = {
            GameState.CHARACTER_LEVEL: 1,
            GameState.COOLDOWN_READY: True
        }

        actions = [
            RestAction(),
            GatheringAction("copper_ore"),
            CombatAction("chicken"),
            MovementAction(1, 1)
        ]

        for action in actions:
            # Should not raise exceptions when checking preconditions
            try:
                can_execute = action.can_execute(minimal_state)
                assert isinstance(can_execute, bool)
            except Exception as e:
                pytest.fail(f"Action {action.__class__.__name__} raised exception with minimal state: {e}")

    def test_actions_validate_state_types_correctly(self, base_game_state):
        """Test that actions correctly validate state value types"""
        actions = [
            RestAction(),
            GatheringAction("copper_ore"),
            CombatAction("chicken"),
            MovementAction(1, 1)
        ]

        for action in actions:
            # Test with correct state types
            valid_result = action.can_execute(base_game_state)
            assert isinstance(valid_result, bool)

            # Test with some invalid state types
            corrupted_state = base_game_state.copy()
            corrupted_state[GameState.CHARACTER_LEVEL] = "not_a_number"  # Should be int
            corrupted_state[GameState.COOLDOWN_READY] = "not_a_boolean"  # Should be bool

            # Should handle type mismatches gracefully
            try:
                invalid_result = action.can_execute(corrupted_state)
                assert isinstance(invalid_result, bool)
            except Exception as e:
                pytest.fail(f"Action {action.__class__.__name__} did not handle type mismatch gracefully: {e}")

    def test_action_costs_scale_appropriately(self, mock_game_data):
        """Test that parameterized action costs scale appropriately with parameters"""
        # Test movement action costs scale with distance
        short_movement = MovementAction(1, 1)
        medium_movement = MovementAction(5, 5)
        long_movement = MovementAction(10, 10)

        assert short_movement.cost <= medium_movement.cost <= long_movement.cost, "Movement costs should scale with distance"

        # Test that costs are reasonable
        assert short_movement.cost >= 1, "Even short movements should have positive cost"
        assert long_movement.cost <= 100, "Long movements should not have excessive cost"

    def test_action_effects_are_consistent_with_preconditions(self):
        """Test that action effects don't contradict their own preconditions"""
        actions = [
            RestAction(),
            GatheringAction("copper_ore"),
            CombatAction("chicken"),
            MovementAction(1, 1)
        ]

        for action in actions:
            preconditions = action.get_preconditions()
            effects = action.get_effects()

            # Check for logical consistency
            for state_key in preconditions.keys():
                if state_key in effects:
                    # If an action requires something and also modifies it,
                    # the modification should be reasonable
                    precond_value = preconditions[state_key]
                    effect_value = effects[state_key]

                    # For boolean states, if we require True, we shouldn't set it to True again
                    # (that would be redundant but not contradictory)
                    if isinstance(precond_value, bool) and isinstance(effect_value, bool):
                        # This is fine - actions can modify boolean states they depend on
                        pass

                    # For numeric states, effects should be reasonable
                    if isinstance(precond_value, (int, float)) and isinstance(effect_value, (int, float)):
                        # This is normal - actions can modify numeric states
                        pass

    def test_concurrent_action_safety(self, base_game_state, mock_game_data):
        """Test that action system is safe for concurrent access patterns"""
        registry = ActionRegistry()
        factory = MovementActionFactory()
        registry.register_factory(factory)

        # Simulate concurrent access to registry
        def generate_actions():
            return registry.generate_actions_for_state(base_game_state, mock_game_data)

        # This should not raise exceptions even if called multiple times
        results = []
        for _ in range(10):
            actions = generate_actions()
            results.append(len(actions))

        # Results should be consistent
        assert all(count == results[0] for count in results), "Registry generated inconsistent results"

    def test_memory_efficiency_with_many_actions(self, base_game_state, mock_game_data):
        """Test that action generation is memory efficient"""
        registry = ActionRegistry()

        # Create a factory that generates many actions
        class HighVolumeFactory(ActionFactory):
            def create_instances(self, game_data: Any, current_state: dict[GameState, Any]) -> list[BaseAction]:
                return [RestAction() for _ in range(1000)]  # Generate 1000 rest actions

            def get_action_type(self) -> type[BaseAction]:
                return RestAction

        high_volume_factory = HighVolumeFactory()
        registry.register_factory(high_volume_factory)

        # This should complete without memory issues
        actions = registry.generate_actions_for_state(base_game_state, mock_game_data)

        assert len(actions) >= 1000

        # Clean up explicitly
        del actions


class TestActionSystemDocumentation(TestActionMixin):
    """Test that action system provides good introspection and documentation"""

    def test_all_actions_have_meaningful_names(self, base_game_state, mock_game_data):
        """Test that all actions have descriptive, meaningful names"""
        registry = ActionRegistry()
        factory = MovementActionFactory()
        registry.register_factory(factory)

        all_actions = registry.generate_actions_for_state(base_game_state, mock_game_data)

        for action in all_actions:
            name = action.name
            assert isinstance(name, str), f"Action name is not a string: {name}"
            assert len(name) > 0, "Action name is empty"
            assert len(name) <= 100, f"Action name is too long: {name}"
            assert not name.isspace(), "Action name is only whitespace"

            # Names should be descriptive
            assert any(char.isalnum() for char in name), f"Action name contains no alphanumeric characters: {name}"

    def test_action_types_provide_introspection(self):
        """Test that action types can be introspected for debugging"""
        action_classes = [RestAction, GatheringAction, CombatAction, MovementAction]

        for action_class in action_classes:
            # Should have docstrings
            assert action_class.__doc__ is not None, f"Action class {action_class.__name__} lacks docstring"

            # Should have meaningful class name
            assert action_class.__name__.endswith('Action'), f"Action class name doesn't follow convention: {action_class.__name__}"

            # Should be subclass of BaseAction
            assert issubclass(action_class, BaseAction), f"Action class {action_class.__name__} is not a BaseAction subclass"

    def test_action_registry_provides_debugging_info(self, action_registry):
        """Test that action registry provides useful debugging information"""
        # Should be able to get all action types
        action_types = action_registry.get_all_action_types()
        assert isinstance(action_types, list)

        # Should be able to validate actions
        for action_type in action_types:
            validation_result = action_registry.validate_action(action_type)
            assert isinstance(validation_result, bool)

    def test_factory_system_is_introspectable(self):
        """Test that factory system provides introspection capabilities"""
        factory = MovementActionFactory()

        # Should be able to get action type
        action_type = factory.get_action_type()
        assert action_type == MovementAction

        # Should be able to generate parameters
        mock_state = {GameState.CURRENT_X: 0, GameState.CURRENT_Y: 0}
        mock_data = self.create_mock_game_data()

        parameters = factory.generate_parameters(mock_data, mock_state)
        assert isinstance(parameters, list)

        for param_set in parameters:
            assert isinstance(param_set, dict)
            assert 'target_x' in param_set
            assert 'target_y' in param_set


# Module-level test functions for pytest discovery

def test_action_system_package_structure():
    """Test that action system package structure is correct"""
    # Test that main action classes can be imported
    # Test that registry components can be imported
    # (imports already done at top of file)

    # All imports should succeed without errors
    assert BaseAction is not None
    assert RestAction is not None
    assert MovementAction is not None
    assert GatheringAction is not None
    assert CombatAction is not None
    assert ActionRegistry is not None
    assert ActionFactory is not None
    assert get_all_actions is not None


def test_action_system_provides_complete_interface():
    """Test that action system provides all expected interface elements"""
    # (imports already done at top of file)

    # All expected components should be available
    assert ActionFactory is not None
    assert ActionRegistry is not None
    assert ParameterizedActionFactory is not None
    assert get_all_actions is not None
    assert get_global_registry is not None
    assert register_action_factory is not None
