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
        """Test getting default GOAP parameters for move action."""
        defaults = self.controller._get_action_class_defaults('move')
        
        self.assertIsInstance(defaults, dict)
        self.assertIn('conditions', defaults)
        self.assertIn('reactions', defaults)
        self.assertIn('weight', defaults)
        
        # Check specific move action defaults
        self.assertEqual(defaults['conditions']['can_move'], True)
        self.assertEqual(defaults['conditions']['character_alive'], True)
        self.assertEqual(defaults['reactions']['at_target_location'], True)
        self.assertEqual(defaults['weight'], 1.0)

    def test_get_action_class_defaults_attack(self) -> None:
        """Test getting default GOAP parameters for attack action."""
        defaults = self.controller._get_action_class_defaults('attack')
        
        self.assertIsInstance(defaults, dict)
        self.assertIn('conditions', defaults)
        self.assertIn('reactions', defaults)
        self.assertIn('weight', defaults)
        
        # Check specific attack action defaults
        self.assertEqual(defaults['conditions']['monster_present'], True)
        self.assertEqual(defaults['conditions']['can_attack'], True)
        self.assertEqual(defaults['conditions']['character_safe'], True)
        self.assertEqual(defaults['reactions']['monster_present'], False)
        self.assertEqual(defaults['reactions']['has_hunted_monsters'], True)
        self.assertEqual(defaults['weight'], 3.0)

    def test_get_action_class_defaults_rest(self) -> None:
        """Test getting default GOAP parameters for rest action."""
        defaults = self.controller._get_action_class_defaults('rest')
        
        self.assertIsInstance(defaults, dict)
        
        # Check specific rest action defaults
        self.assertEqual(defaults['conditions']['character_alive'], True)
        self.assertEqual(defaults['conditions']['needs_rest'], True)
        self.assertEqual(defaults['conditions']['character_safe'], False)
        self.assertEqual(defaults['reactions']['character_safe'], True)
        self.assertEqual(defaults['reactions']['needs_rest'], False)
        self.assertEqual(defaults['weight'], 1.5)

    def test_get_action_class_defaults_find_monsters(self) -> None:
        """Test getting default GOAP parameters for find_monsters action."""
        defaults = self.controller._get_action_class_defaults('find_monsters')
        
        self.assertIsInstance(defaults, dict)
        
        # Check specific find_monsters action defaults
        self.assertEqual(defaults['conditions']['need_combat'], True)
        self.assertEqual(defaults['conditions']['monsters_available'], False)
        self.assertEqual(defaults['reactions']['monsters_available'], True)
        self.assertEqual(defaults['reactions']['monster_present'], True)
        self.assertEqual(defaults['weight'], 2.0)

    def test_get_action_class_defaults_unknown_action(self) -> None:
        """Test getting defaults for unknown action returns empty dict."""
        defaults = self.controller._get_action_class_defaults('unknown_action')
        self.assertEqual(defaults, {})

    def test_create_planner_uses_class_defaults(self) -> None:
        """Test that planner creation uses class defaults when config is minimal."""
        start_state = {'character_alive': True, 'can_move': True}
        goal_state = {'at_target_location': True}
        
        # Minimal config that doesn't override defaults
        actions_config = {
            'move': {
                'description': 'Move to target'
                # No conditions, reactions, or weight specified
            }
        }
        
        planner = self.controller.create_planner(start_state, goal_state, actions_config)
        
        # Verify planner was created successfully
        self.assertIsNotNone(planner)
        
        # Get action list to verify defaults were used
        action_list = planner.action_list
        self.assertIsNotNone(action_list)
        
        # Check that move action has the class defaults
        self.assertIn('move', action_list.conditions)
        self.assertEqual(action_list.conditions['move']['can_move'], True)
        self.assertEqual(action_list.conditions['move']['character_alive'], True)
        
        self.assertIn('move', action_list.reactions)
        self.assertEqual(action_list.reactions['move']['at_target_location'], True)
        
        self.assertIn('move', action_list.weights)
        self.assertEqual(action_list.weights['move'], 1.0)

    def test_create_planner_config_overrides_defaults(self) -> None:
        """Test that config file values override class defaults."""
        start_state = {'character_alive': True, 'custom_condition': True}
        goal_state = {'at_target_location': True}
        
        # Config that overrides some defaults
        actions_config = {
            'move': {
                'conditions': {
                    'custom_condition': True  # Override/add to defaults
                },
                'reactions': {
                    'at_target_location': True,
                    'custom_reaction': True  # Add to defaults
                },
                'weight': 2.5  # Override default weight
            }
        }
        
        planner = self.controller.create_planner(start_state, goal_state, actions_config)
        action_list = planner.action_list
        
        # Check that both defaults and overrides are present
        move_conditions = action_list.conditions['move']
        self.assertEqual(move_conditions['can_move'], True)  # From class default
        self.assertEqual(move_conditions['character_alive'], True)  # From class default
        self.assertEqual(move_conditions['custom_condition'], True)  # From config
        
        move_reactions = action_list.reactions['move']
        self.assertEqual(move_reactions['at_target_location'], True)  # Merged
        self.assertEqual(move_reactions['custom_reaction'], True)  # From config
        
        # Weight should be overridden
        self.assertEqual(action_list.weights['move'], 2.5)

    def test_create_planner_with_multiple_actions(self) -> None:
        """Test planner creation with multiple actions using their defaults."""
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
            'move': {'description': 'Move character'},
            'find_monsters': {'description': 'Find monsters'},
            'attack': {'description': 'Attack monsters'},
            'rest': {'description': 'Rest when needed'}
        }
        
        planner = self.controller.create_planner(start_state, goal_state, actions_config)
        action_list = planner.action_list
        
        # Verify all actions have their defaults
        self.assertIn('move', action_list.conditions)
        self.assertIn('find_monsters', action_list.conditions)
        self.assertIn('attack', action_list.conditions)
        self.assertIn('rest', action_list.conditions)
        
        # Check specific defaults are preserved
        self.assertEqual(action_list.weights['attack'], 3.0)  # Attack has high priority
        self.assertEqual(action_list.weights['rest'], 1.5)    # Rest has medium priority
        self.assertEqual(action_list.weights['find_monsters'], 2.0)  # Find monsters medium-high
        
        # Check attack conditions
        attack_conditions = action_list.conditions['attack']
        self.assertTrue(attack_conditions['monster_present'])
        self.assertTrue(attack_conditions['can_attack'])
        self.assertTrue(attack_conditions['character_safe'])

    def test_weight_precedence(self) -> None:
        """Test that action weights follow expected precedence."""
        # Based on our class definitions:
        # attack: 3.0 (highest - goal action)
        # find_monsters: 2.0 (medium-high - enables goal)
        # rest: 1.5 (medium - survival)
        # move: 1.0 (lowest - utility)
        
        attack_defaults = self.controller._get_action_class_defaults('attack')
        find_defaults = self.controller._get_action_class_defaults('find_monsters')
        rest_defaults = self.controller._get_action_class_defaults('rest')
        move_defaults = self.controller._get_action_class_defaults('move')
        
        attack_weight = attack_defaults['weight']
        find_weight = find_defaults['weight']
        rest_weight = rest_defaults['weight']
        move_weight = move_defaults['weight']
        
        # Verify precedence: attack > find_monsters > rest > move
        self.assertGreater(attack_weight, find_weight)
        self.assertGreater(find_weight, rest_weight)
        self.assertGreater(rest_weight, move_weight)


if __name__ == '__main__':
    unittest.main()