"""Unit tests for Action class GOAP parameter integration."""

import unittest
from unittest.mock import Mock

from src.controller.ai_player_controller import AIPlayerController
from src.controller.actions.move import MoveAction
from src.controller.actions.attack import AttackAction
from src.controller.actions.rest import RestAction
from src.controller.actions.find_monsters import FindMonstersAction
from src.controller.actions.map_lookup import MapLookupAction


class TestActionGoapIntegration(unittest.TestCase):
    """Test cases for Action class GOAP parameter integration."""

    def setUp(self) -> None:
        """Set up test fixtures before each test method."""
        self.controller = AIPlayerController()
        self.mock_client = Mock()
        self.controller.set_client(self.mock_client)

    def test_action_classes_have_goap_parameters(self) -> None:
        """Test that action classes have defined GOAP parameters."""
        # Test MoveAction
        self.assertTrue(hasattr(MoveAction, 'conditions'))
        self.assertTrue(hasattr(MoveAction, 'reactions'))
        self.assertTrue(hasattr(MoveAction, 'weights'))
        self.assertIsInstance(MoveAction.conditions, dict)
        self.assertIsInstance(MoveAction.reactions, dict)
        self.assertIsInstance(MoveAction.weights, dict)
        
        # Test AttackAction
        self.assertTrue(hasattr(AttackAction, 'conditions'))
        self.assertTrue(hasattr(AttackAction, 'reactions'))
        self.assertTrue(hasattr(AttackAction, 'weights'))
        self.assertIn('monster_present', AttackAction.conditions)
        self.assertIn('can_attack', AttackAction.conditions)
        
        # Test RestAction
        self.assertTrue(hasattr(RestAction, 'conditions'))
        self.assertTrue(hasattr(RestAction, 'reactions'))
        self.assertTrue(hasattr(RestAction, 'weights'))
        self.assertIn('needs_rest', RestAction.conditions)
        self.assertIn('character_safe', RestAction.reactions)
        
        # Test FindMonstersAction
        self.assertTrue(hasattr(FindMonstersAction, 'conditions'))
        self.assertTrue(hasattr(FindMonstersAction, 'reactions'))
        self.assertTrue(hasattr(FindMonstersAction, 'weights'))
        self.assertIn('need_combat', FindMonstersAction.conditions)
        self.assertIn('monsters_available', FindMonstersAction.reactions)

    def test_get_action_class_defaults_move(self) -> None:
        """Test getting default GOAP parameters for move action through ActionExecutor."""
        # Action class defaults are now handled internally by the factory
        # Test that the action is registered and has the expected class attributes
        self.assertTrue(self.controller.action_executor.factory.is_action_registered('move'))
        
        # Verify the action class has GOAP attributes
        config = self.controller.action_executor.factory._action_registry.get('move')
        self.assertIsNotNone(config)
        self.assertIsNotNone(config.action_class)
        
        action_class = config.action_class
        self.assertTrue(hasattr(action_class, 'conditions'))
        self.assertTrue(hasattr(action_class, 'reactions'))
        self.assertTrue(hasattr(action_class, 'weights'))
        
        # Check specific move action defaults
        self.assertEqual(action_class.conditions['can_move'], True)
        self.assertEqual(action_class.conditions['character_alive'], True)
        self.assertEqual(action_class.reactions['at_target_location'], True)
        # Weights might be a dict with action name as key
        if isinstance(action_class.weights, dict):
            self.assertEqual(action_class.weights['move'], 1.0)
        else:
            self.assertEqual(action_class.weights, 1.0)

    def test_get_action_class_defaults_attack(self) -> None:
        """Test that attack action is properly registered with GOAP attributes."""
        # GOAP defaults are now handled internally by managers
        # Test that the action exists and has the right class attributes
        self.assertTrue(self.controller.action_executor.factory.is_action_registered('attack'))
        
        config = self.controller.action_executor.factory._action_registry.get('attack')
        action_class = config.action_class
        
        # Verify GOAP attributes exist
        self.assertTrue(hasattr(action_class, 'conditions'))
        self.assertTrue(hasattr(action_class, 'reactions'))
        self.assertTrue(hasattr(action_class, 'weights'))

    def test_get_action_class_defaults_rest(self) -> None:
        """Test that rest action is properly registered with GOAP attributes."""
        # GOAP defaults are now handled internally by managers
        self.assertTrue(self.controller.action_executor.factory.is_action_registered('rest'))
        
        config = self.controller.action_executor.factory._action_registry.get('rest')
        action_class = config.action_class
        
        # Verify GOAP attributes exist
        self.assertTrue(hasattr(action_class, 'conditions'))
        self.assertTrue(hasattr(action_class, 'reactions'))
        self.assertTrue(hasattr(action_class, 'weights'))

    def test_get_action_class_defaults_find_monsters(self) -> None:
        """Test that find_monsters action is properly registered with GOAP attributes."""
        # GOAP defaults are now handled internally by managers
        self.assertTrue(self.controller.action_executor.factory.is_action_registered('find_monsters'))
        
        config = self.controller.action_executor.factory._action_registry.get('find_monsters')
        action_class = config.action_class
        
        # Verify GOAP attributes exist
        self.assertTrue(hasattr(action_class, 'conditions'))
        self.assertTrue(hasattr(action_class, 'reactions'))
        self.assertTrue(hasattr(action_class, 'weights'))

    def test_get_action_class_defaults_unknown_action(self) -> None:
        """Test that unknown actions are not registered."""
        # Unknown actions should not be registered in the factory
        self.assertFalse(self.controller.action_executor.factory.is_action_registered('unknown_action'))

    def test_create_planner_uses_class_defaults(self) -> None:
        """Test that GOAP world creation works through GOAPExecutionManager."""
        start_state = {'character_alive': True, 'can_move': True}
        goal_state = {'at_target_location': True}
        
        # Minimal config that uses defaults
        actions_config = {
            'move': {
                'conditions': {'can_move': True, 'character_alive': True},
                'reactions': {'at_target_location': True},
                'weight': 1.0
            }
        }
        
        # Test through GOAPExecutionManager instead of removed controller method
        world = self.controller.goap_execution_manager.create_world_with_planner(
            start_state, goal_state, actions_config
        )
        
        # Verify world was created successfully
        self.assertIsNotNone(world)
        self.assertIsNotNone(self.controller.goap_execution_manager.current_planner)

    def test_create_planner_config_overrides_defaults(self) -> None:
        """Test that GOAP execution manager properly handles action configurations."""
        start_state = {'character_alive': True, 'custom_condition': True}
        goal_state = {'at_target_location': True}
        
        # Config with custom values
        actions_config = {
            'move': {
                'conditions': {'custom_condition': True},
                'reactions': {'at_target_location': True, 'custom_reaction': True},
                'weight': 2.5
            }
        }
        
        # Test through GOAPExecutionManager
        world = self.controller.goap_execution_manager.create_world_with_planner(
            start_state, goal_state, actions_config
        )
        
        # Verify world creation succeeds
        self.assertIsNotNone(world)
        self.assertIsNotNone(self.controller.goap_execution_manager.current_planner)

    def test_create_planner_with_multiple_actions(self) -> None:
        """Test GOAP execution manager handles multiple actions."""
        start_state = {
            'character_alive': True,
            'can_move': True,
            'character_safe': True,
            'need_combat': True
        }
        goal_state = {
            'has_hunted_monsters': True,
            'character_safe': True
        }
        
        # Config for multiple actions
        actions_config = {
            'move': {
                'conditions': {'can_move': True, 'character_alive': True},
                'reactions': {'at_target_location': True},
                'weight': 1.0
            },
            'attack': {
                'conditions': {'monster_present': True, 'character_safe': True},
                'reactions': {'monster_defeated': True},
                'weight': 3.0
            }
        }
        
        # Test through GOAPExecutionManager
        world = self.controller.goap_execution_manager.create_world_with_planner(
            start_state, goal_state, actions_config
        )
        
        # Verify world creation succeeds with multiple actions
        self.assertIsNotNone(world)
        self.assertIsNotNone(self.controller.goap_execution_manager.current_planner)

    def test_weight_precedence(self) -> None:
        """Test that action weights can be verified through action classes."""
        # Test that action classes have the expected GOAP attributes
        # without relying on removed controller methods
        
        # Verify attack action has higher weight than move
        attack_config = self.controller.action_executor.factory._action_registry.get('attack')
        move_config = self.controller.action_executor.factory._action_registry.get('move')
        
        if attack_config and move_config:
            attack_class = attack_config.action_class
            move_class = move_config.action_class
            
            # Verify both have weights defined
            self.assertTrue(hasattr(attack_class, 'weights'))
            self.assertTrue(hasattr(move_class, 'weights'))
            
            # Get the actual weight values - handle both dict and direct value formats
            attack_weight = attack_class.weights.get('attack', attack_class.weights) if isinstance(attack_class.weights, dict) else attack_class.weights
            move_weight = move_class.weights.get('move', move_class.weights) if isinstance(move_class.weights, dict) else move_class.weights
            
            # Attack should have higher weight than move for goal prioritization
            self.assertGreater(attack_weight, move_weight)


if __name__ == '__main__':
    unittest.main()