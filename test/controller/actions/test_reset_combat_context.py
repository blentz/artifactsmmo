"""
Test Reset Combat Context Action

Tests for the ResetCombatContextAction class.
"""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.reset_combat_context import ResetCombatContextAction
from src.lib.action_context import ActionContext


class TestResetCombatContextAction(unittest.TestCase):
    """Test the ResetCombatContextAction class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.context = ActionContext()
        self.context.character_name = "test_character"
        self.action = ResetCombatContextAction()
        
    def test_init(self):
        """Test action initialization."""
        action = ResetCombatContextAction()
        self.assertIsInstance(action, ResetCombatContextAction)
        
    def test_execute_success(self):
        """Test successful execution of reset combat context."""
        result = self.action.execute(self.mock_client, self.context)
        
        self.assertTrue(result['success'])
        self.assertTrue(result['combat_context_reset'])
        self.assertEqual(result['previous_status'], 'completed')
        self.assertEqual(result['new_status'], 'idle')
        self.assertIn("Combat context reset to idle state", result['message'])
        
    def test_execute_no_character_name(self):
        """Test execution when no character name is provided."""
        self.context.character_name = None
        
        result = self.action.execute(self.mock_client, self.context)
        
        self.assertFalse(result['success'])
        self.assertIn("No character name provided", result['error'])
        
    def test_execute_with_exception(self):
        """Test execution when an exception occurs."""
        # Mock get_success_response to raise an exception after log_execution_start
        with patch.object(self.action, 'get_success_response') as mock_response:
            mock_response.side_effect = Exception("Test exception")
            
            result = self.action.execute(self.mock_client, self.context)
            
            self.assertFalse(result['success'])
            self.assertIn("Failed to reset combat context", result['error'])
            self.assertIn("Test exception", result['error'])
    
    def test_goap_parameters(self):
        """Test GOAP parameters are properly defined."""
        self.assertEqual(self.action.conditions, {
            'combat_context': {
                'status': 'completed',
            },
        })
        
        self.assertEqual(self.action.reactions, {
            'combat_context': {
                'status': 'idle',
                'target': None,
                'location': None,
            },
        })
        
        self.assertEqual(self.action.weights, {'combat_context.status': 1.0})
    
    def test_repr(self):
        """Test string representation of the action."""
        repr_str = repr(self.action)
        self.assertEqual(repr_str, "ResetCombatContextAction()")


if __name__ == '__main__':
    unittest.main()