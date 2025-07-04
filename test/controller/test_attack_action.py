"""Unit tests for AttackAction class."""

import unittest

from artifactsmmo_api_client.client import AuthenticatedClient
from src.controller.actions.attack import AttackAction
from src.lib.action_context import ActionContext


class TestAttackAction(unittest.TestCase):
    def setUp(self):
        self.client = AuthenticatedClient(base_url="https://api.artifactsmmo.com", token="test_token")
        self.char_name = "test_character"

    
    def test_estimate_fight_duration_with_monster_data(self):
        """Test fight duration estimation with monster data."""
        action = AttackAction()
        
        # Test with specific monster HP
        monster_data = {'hp': 50}
        context = ActionContext(character_level=10)
        duration = action.estimate_fight_duration(context, monster_data)
        self.assertEqual(duration, 5)  # 50 HP / 10 damage per turn
        
        # Test with low HP monster
        monster_data = {'hp': 5}
        duration = action.estimate_fight_duration(context, monster_data)
        self.assertEqual(duration, 1)  # Minimum 1 turn
        
        # Test with high HP monster
        monster_data = {'hp': 100}
        duration = action.estimate_fight_duration(context, monster_data)
        self.assertEqual(duration, 10)  # 100 HP / 10 damage per turn

    def test_estimate_fight_duration_without_monster_data(self):
        """Test fight duration estimation without monster data."""
        action = AttackAction()
        
        # Test with low level character
        context = ActionContext(character_level=1)
        duration = action.estimate_fight_duration(context)
        self.assertEqual(duration, 5)  # Max duration for low level
        
        # Test with mid level character
        context = ActionContext(character_level=10)
        duration = action.estimate_fight_duration(context)
        self.assertEqual(duration, 3)  # 5 - 10//5 = 3
        
        # Test with high level character
        context = ActionContext(character_level=20)
        duration = action.estimate_fight_duration(context)
        self.assertEqual(duration, 2)  # Min duration

    def test_estimate_fight_duration_no_character_state(self):
        """Test fight duration estimation with no character state."""
        action = AttackAction()
        context = ActionContext()  # Default level is 1
        duration = action.estimate_fight_duration(context)
        self.assertEqual(duration, 5)  # Default for level 1

    def test_attack_action_class_attributes(self):
        """Test AttackAction class has expected GOAP attributes."""
        # Check that GOAP attributes exist
        self.assertIsInstance(AttackAction.conditions, dict)
        self.assertIsInstance(AttackAction.reactions, dict)
        self.assertIsInstance(AttackAction.weight, (int, float))
        
        # Check specific GOAP conditions
        self.assertIn('combat_context', AttackAction.conditions)
        self.assertEqual(AttackAction.conditions['combat_context']['status'], 'ready')
        self.assertIn('character_status', AttackAction.conditions)
        self.assertTrue(AttackAction.conditions['character_status']['safe'])
        self.assertTrue(AttackAction.conditions['character_status']['alive'])
        
        # Check specific GOAP reactions
        self.assertIn('combat_context', AttackAction.reactions)
        self.assertEqual(AttackAction.reactions['combat_context']['status'], 'completed')
        # monsters_hunted is now tracked internally, not in GOAP reactions
        self.assertNotIn('goal_progress', AttackAction.reactions)
        
        # Check weight
        self.assertEqual(AttackAction.weight, 3.0)


if __name__ == '__main__':
    unittest.main()