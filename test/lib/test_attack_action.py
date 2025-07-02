"""Unit tests for AttackAction class."""

import unittest
from unittest.mock import Mock, patch

from artifactsmmo_api_client.client import AuthenticatedClient
from src.controller.actions.attack import AttackAction


class TestAttackAction(unittest.TestCase):
    def setUp(self):
        self.client = AuthenticatedClient(base_url="https://api.artifactsmmo.com", token="test_token")
        self.char_name = "test_character"

    def test_attack_action_initialization(self):
        action = AttackAction()
        self.assertIsInstance(action, AttackAction)
        self.assertFalse(hasattr(action, 'character_name'))
        self.assertIsNotNone(action.logger)

    def test_attack_action_repr(self):
        action = AttackAction()
        expected = "AttackAction()"
        self.assertEqual(repr(action), expected)

    @patch('src.controller.actions.attack.fight_character_api')
    def test_attack_action_execute_win(self, mock_fight_api):
        # Mock the API response for a win
        mock_response = Mock()
        mock_fight_data = {
            'result': 'win',
            'xp': 100,
            'gold': 50,
            'drops': [{'code': 'sword', 'quantity': 1}]
        }
        mock_response.data = Mock()
        mock_response.data.fight = Mock()
        mock_response.data.fight.to_dict.return_value = mock_fight_data
        mock_fight_api.return_value = mock_response
        
        action = AttackAction()
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name)
        result = action.execute(self.client, context)
        
        # Verify the API was called with correct parameters
        mock_fight_api.assert_called_once_with(
            name=self.char_name,
            client=self.client
        )
        
        # Verify response format
        self.assertTrue(result['success'])
        self.assertEqual(result['action'], 'AttackAction')
        self.assertEqual(result['xp_gained'], 100)
        self.assertEqual(result['gold_gained'], 50)
        self.assertEqual(result['drops'], mock_fight_data['drops'])
        self.assertTrue(result['monster_defeated'])

    @patch('src.controller.actions.attack.fight_character_api')
    def test_attack_action_execute_loss(self, mock_fight_api):
        # Mock the API response for a loss
        mock_response = Mock()
        mock_fight_data = {
            'result': 'loss',
            'xp': 0,
            'gold': 0,
            'drops': []
        }
        mock_response.data = Mock()
        mock_response.data.fight = Mock()
        mock_response.data.fight.to_dict.return_value = mock_fight_data
        mock_fight_api.return_value = mock_response
        
        action = AttackAction()
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name)
        result = action.execute(self.client, context)
        
        # Verify response shows loss
        self.assertTrue(result['success'])
        self.assertEqual(result['xp_gained'], 0)
        self.assertEqual(result['gold_gained'], 0)
        self.assertFalse(result['monster_defeated'])

    @patch('src.controller.actions.attack.fight_character_api')
    def test_attack_action_execute_no_fight_data(self, mock_fight_api):
        # Mock the API response without fight data
        mock_response = Mock()
        mock_response.data = None
        mock_fight_api.return_value = mock_response
        
        action = AttackAction()
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name)
        result = action.execute(self.client, context)
        
        # Should still return success with default values
        self.assertTrue(result['success'])
        self.assertEqual(result['xp_gained'], 0)
        self.assertEqual(result['gold_gained'], 0)
        self.assertEqual(result['drops'], [])
        self.assertFalse(result['monster_defeated'])

    @patch('src.controller.actions.attack.fight_character_api')
    def test_attack_action_execute_no_fight_object(self, mock_fight_api):
        # Mock the API response without fight object
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.fight = None
        mock_fight_api.return_value = mock_response
        
        action = AttackAction()
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name)
        result = action.execute(self.client, context)
        
        # Should still return success with default values
        self.assertTrue(result['success'])
        self.assertEqual(result['xp_gained'], 0)

    def test_attack_action_execute_no_client(self):
        action = AttackAction()
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name)
        result = action.execute(None, context)
        
        # Should return error
        self.assertFalse(result['success'])
        self.assertIn('error', result)

    @patch('src.controller.actions.attack.fight_character_api')
    def test_attack_action_execute_cooldown_error(self, mock_fight_api):
        # Mock API to raise cooldown error
        mock_fight_api.side_effect = Exception("Character is in cooldown")
        
        action = AttackAction()
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name)
        result = action.execute(self.client, context)
        
        # Should return error with cooldown flag
        self.assertFalse(result['success'])
        self.assertIn('Character is in cooldown', result['error'])
        self.assertTrue(result.get('is_cooldown', False))

    @patch('src.controller.actions.attack.fight_character_api')
    def test_attack_action_execute_no_monster_error(self, mock_fight_api):
        # Mock API to raise no monster error
        mock_fight_api.side_effect = Exception("Monster not found at this location")
        
        action = AttackAction()
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name)
        result = action.execute(self.client, context)
        
        # Should return error with no_monster flag
        self.assertFalse(result['success'])
        self.assertIn('No monster at location', result['error'])
        self.assertTrue(result.get('no_monster', False))

    @patch('src.controller.actions.attack.fight_character_api')
    def test_attack_action_execute_wrong_location_error(self, mock_fight_api):
        # Mock API to raise wrong location error
        mock_fight_api.side_effect = Exception("497 Character already at this location")
        
        action = AttackAction()
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name)
        result = action.execute(self.client, context)
        
        # Should return error with wrong_location flag
        self.assertFalse(result['success'])
        self.assertIn('must be at monster location', result['error'])
        self.assertTrue(result.get('wrong_location', False))

    @patch('src.controller.actions.attack.fight_character_api')
    def test_attack_action_execute_action_not_allowed_error(self, mock_fight_api):
        # Mock API to raise action not allowed error
        mock_fight_api.side_effect = Exception("486 This action is not allowed")
        
        action = AttackAction()
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name)
        result = action.execute(self.client, context)
        
        # Should return error with action_not_allowed flag
        self.assertFalse(result['success'])
        self.assertIn('Action not allowed', result['error'])
        self.assertTrue(result.get('action_not_allowed', False))

    @patch('src.controller.actions.attack.fight_character_api')
    def test_attack_action_execute_character_not_found_error(self, mock_fight_api):
        # Mock API to raise character not found error
        mock_fight_api.side_effect = Exception("Character not found")
        
        action = AttackAction()
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name)
        result = action.execute(self.client, context)
        
        # Should return appropriate error
        self.assertFalse(result['success'])
        self.assertIn('Character not found', result['error'])

    @patch('src.controller.actions.attack.fight_character_api')
    def test_attack_action_execute_generic_error(self, mock_fight_api):
        # Mock API to raise generic error
        mock_fight_api.side_effect = Exception("Network error")
        
        action = AttackAction()
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name)
        result = action.execute(self.client, context)
        
        # Should return error with original message
        self.assertFalse(result['success'])
        self.assertIn('Network error', result['error'])

    def test_attack_action_validate_no_character_name(self):
        """Test validation with empty character name returns error."""
        from test.fixtures import MockActionContext
        action = AttackAction()
        context = MockActionContext(character_name="")
        result = action.execute(self.client, context)
        self.assertFalse(result['success'])
        self.assertIn('character name', result['error'].lower())

    def test_estimate_fight_duration_with_monster_data(self):
        """Test fight duration estimation with monster data."""
        action = AttackAction()
        
        # Test with specific monster HP
        monster_data = {'hp': 50}
        duration = action.estimate_fight_duration(None, monster_data)
        self.assertEqual(duration, 5)  # 50 HP / 10 damage per turn
        
        # Test with low HP monster
        monster_data = {'hp': 5}
        duration = action.estimate_fight_duration(None, monster_data)
        self.assertEqual(duration, 1)  # Minimum 1 turn
        
        # Test with high HP monster
        monster_data = {'hp': 100}
        duration = action.estimate_fight_duration(None, monster_data)
        self.assertEqual(duration, 10)  # 100 HP / 10 damage per turn

    def test_estimate_fight_duration_without_monster_data(self):
        """Test fight duration estimation without monster data."""
        action = AttackAction()
        from test.fixtures import MockActionContext
        
        # Test with low level character
        context = MockActionContext(character_name="test", character_level=1)
        duration = action.estimate_fight_duration(context)
        self.assertEqual(duration, 5)  # Max duration for low level
        
        # Test with mid level character
        context = MockActionContext(character_name="test", character_level=10)
        duration = action.estimate_fight_duration(context)
        self.assertEqual(duration, 3)  # 5 - 10//5 = 3
        
        # Test with high level character
        context = MockActionContext(character_name="test", character_level=20)
        duration = action.estimate_fight_duration(context)
        self.assertEqual(duration, 2)  # Min duration

    def test_estimate_fight_duration_no_character_state(self):
        """Test fight duration estimation with no character state."""
        action = AttackAction()
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name="test")  # No character_level
        duration = action.estimate_fight_duration(context)
        self.assertEqual(duration, 5)  # Default for level 1

    def test_attack_action_class_attributes(self):
        """Test AttackAction class has expected GOAP attributes."""
        # Check that GOAP attributes exist
        self.assertIsInstance(AttackAction.conditions, dict)
        self.assertIsInstance(AttackAction.reactions, dict)
        self.assertIsInstance(AttackAction.weights, dict)
        
        # Check specific GOAP conditions (consolidated state format)
        self.assertIn('combat_context', AttackAction.conditions)
        self.assertIn('character_status', AttackAction.conditions)
        self.assertEqual(AttackAction.conditions['combat_context']['status'], 'ready')
        self.assertTrue(AttackAction.conditions['character_status']['safe'])
        self.assertTrue(AttackAction.conditions['character_status']['alive'])
        
        # Check specific GOAP reactions
        self.assertIn('combat_context', AttackAction.reactions)
        self.assertEqual(AttackAction.reactions['combat_context']['status'], 'completed')
        
        # Check weight
        self.assertIn('attack', AttackAction.weights)
        self.assertEqual(AttackAction.weights['attack'], 3.0)


if __name__ == '__main__':
    unittest.main()