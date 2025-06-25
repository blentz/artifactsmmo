"""Unit tests for RestAction class."""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.rest import RestAction


class TestRestAction(unittest.TestCase):
    """Test cases for RestAction class."""

    def setUp(self) -> None:
        """Set up test fixtures before each test method."""
        self.char_name = "test_character"
        self.rest_action = RestAction(self.char_name)

    def test_rest_action_initialization(self):
        """Test RestAction initialization."""
        action = RestAction("test_char")
        
        self.assertEqual(action.char_name, "test_char")
        self.assertEqual(action.critical_hp_threshold, 20)
        self.assertEqual(action.safe_hp_threshold, 50)

    def test_rest_action_repr(self):
        """Test RestAction string representation."""
        action = RestAction("test_char")
        expected = "RestAction(test_char)"
        
        self.assertEqual(repr(action), expected)

    def test_should_rest_with_low_hp(self):
        """Test should_rest returns True when HP is critically low."""
        # HP is 15 out of 100 (15%)
        result = self.rest_action.should_rest(15, 100)
        self.assertTrue(result)
        
        # HP is 10 out of 50 (20%) - below critical threshold
        result = self.rest_action.should_rest(10, 50)
        self.assertTrue(result)

    def test_should_rest_with_sufficient_hp(self):
        """Test should_rest returns False when HP is sufficient."""
        # HP is 50 out of 100 (50%)
        result = self.rest_action.should_rest(50, 100)
        self.assertFalse(result)
        
        # HP is 25 out of 50 (50%) - above critical threshold
        result = self.rest_action.should_rest(25, 50)
        self.assertFalse(result)

    def test_should_rest_with_zero_max_hp(self):
        """Test should_rest handles zero max HP gracefully."""
        result = self.rest_action.should_rest(10, 0)
        self.assertFalse(result)

    def test_is_hp_safe_with_safe_levels(self):
        """Test is_hp_safe returns True when HP is at safe levels."""
        # HP is 60 out of 100 (60%) - above safe threshold
        result = self.rest_action.is_hp_safe(60, 100)
        self.assertTrue(result)
        
        # HP is exactly at safe threshold (50%)
        result = self.rest_action.is_hp_safe(50, 100)
        self.assertTrue(result)

    def test_is_hp_safe_with_unsafe_levels(self):
        """Test is_hp_safe returns False when HP is unsafe."""
        # HP is 30 out of 100 (30%) - below safe threshold
        result = self.rest_action.is_hp_safe(30, 100)
        self.assertFalse(result)

    def test_is_hp_safe_with_zero_max_hp(self):
        """Test is_hp_safe handles zero max HP gracefully."""
        result = self.rest_action.is_hp_safe(10, 0)
        self.assertFalse(result)

    def test_estimate_rest_time(self):
        """Test rest time estimation."""
        # Need to recover 25 HP: 25/5 = 5 seconds
        result = self.rest_action.estimate_rest_time(25, 50)
        self.assertEqual(result, 5.0)
        
        # Need to recover 10 HP: 10/5 = 2 seconds, but minimum is 3
        result = self.rest_action.estimate_rest_time(40, 50)
        self.assertEqual(result, 3)
        
        # Already at target HP: 0 HP to recover, but minimum is 3
        result = self.rest_action.estimate_rest_time(50, 50)
        self.assertEqual(result, 3)

    @patch('src.controller.actions.rest.rest_character_api')
    def test_rest_action_execute(self, mock_rest_api):
        """Test executing rest action."""
        # Setup mock response
        mock_response = Mock()
        mock_char_data = Mock()
        mock_char_data.hp = 80
        mock_char_data.max_hp = 100
        mock_response.data.character = mock_char_data
        mock_rest_api.return_value = mock_response
        
        # Setup mock client
        mock_client = Mock()
        
        # Execute action
        result = self.rest_action.execute(mock_client)
        
        # Verify API was called correctly
        mock_rest_api.assert_called_once_with(name=self.char_name, client=mock_client)
        self.assertEqual(result, mock_response)

    @patch('src.controller.actions.rest.rest_character_api')
    def test_rest_action_execute_with_character_state_sufficient_hp(self, mock_rest_api):
        """Test executing rest action when character has sufficient HP."""
        # Setup character state with sufficient HP
        mock_character_state = Mock()
        mock_character_state.data = {'hp': 60, 'max_hp': 100}
        
        # Setup mock client
        mock_client = Mock()
        
        # Execute action
        result = self.rest_action.execute(mock_client, character_state=mock_character_state)
        
        # Verify API was NOT called and success response with skipped=True was returned
        mock_rest_api.assert_not_called()
        self.assertIsNotNone(result)
        self.assertTrue(result['success'])
        self.assertTrue(result.get('skipped', False))
        self.assertIn('Rest not needed', result.get('message', ''))

    @patch('src.controller.actions.rest.rest_character_api')
    def test_rest_action_execute_with_character_state_low_hp(self, mock_rest_api):
        """Test executing rest action when character has low HP."""
        # Setup character state with low HP
        mock_character_state = Mock()
        mock_character_state.data = {'hp': 15, 'max_hp': 100}
        
        # Setup mock response
        mock_response = Mock()
        mock_char_data = Mock()
        mock_char_data.hp = 80
        mock_char_data.max_hp = 100
        mock_response.data.character = mock_char_data
        mock_rest_api.return_value = mock_response
        
        # Setup mock client
        mock_client = Mock()
        
        # Execute action
        result = self.rest_action.execute(mock_client, character_state=mock_character_state)
        
        # Verify API was called and response returned
        mock_rest_api.assert_called_once_with(name=self.char_name, client=mock_client)
        self.assertEqual(result, mock_response)

    @patch('src.controller.actions.rest.rest_character_api')
    def test_rest_action_execute_with_cooldown_logging(self, mock_rest_api):
        """Test executing rest action logs cooldown information."""
        # Setup mock response with cooldown data
        mock_response = Mock()
        mock_char_data = Mock()
        mock_char_data.hp = 90
        mock_char_data.max_hp = 100
        mock_cooldown_data = Mock()
        mock_cooldown_data.total_seconds = 15
        mock_response.data.character = mock_char_data
        mock_response.data.cooldown = mock_cooldown_data
        mock_rest_api.return_value = mock_response
        
        # Setup mock client
        mock_client = Mock()
        
        # Execute action
        result = self.rest_action.execute(mock_client)
        
        # Verify response is returned (logging is tested implicitly)
        self.assertEqual(result, mock_response)

    def test_rest_action_class_attributes(self):
        """Test RestAction class has expected GOAP attributes."""
        # Check that GOAP attributes exist and have meaningful values
        self.assertIsInstance(RestAction.conditions, dict)
        self.assertIsInstance(RestAction.reactions, dict)
        self.assertIsInstance(RestAction.weights, dict)
        self.assertIsNone(RestAction.g)
        
        # Check specific GOAP conditions
        self.assertIn('character_alive', RestAction.conditions)
        self.assertIn('needs_rest', RestAction.conditions)
        self.assertIn('character_safe', RestAction.conditions)
        self.assertTrue(RestAction.conditions['character_alive'])
        self.assertTrue(RestAction.conditions['needs_rest'])
        self.assertFalse(RestAction.conditions['character_safe'])
        
        # Check specific GOAP reactions
        self.assertIn('character_safe', RestAction.reactions)
        self.assertIn('needs_rest', RestAction.reactions)
        self.assertIn('can_attack', RestAction.reactions)
        self.assertTrue(RestAction.reactions['character_safe'])
        self.assertFalse(RestAction.reactions['needs_rest'])
        self.assertTrue(RestAction.reactions['can_attack'])
        
        # Check weight
        self.assertIn('rest', RestAction.weights)
        self.assertEqual(RestAction.weights['rest'], 1.5)


if __name__ == '__main__':
    unittest.main()