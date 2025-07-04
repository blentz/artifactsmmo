"""
Test Reset Healing State Action

Tests for the ResetHealingStateAction class.
"""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.reset_healing_state import ResetHealingStateAction
from src.lib.action_context import ActionContext


class TestResetHealingStateAction(unittest.TestCase):
    """Test the ResetHealingStateAction class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.context = ActionContext()
        self.action = ResetHealingStateAction()
        
    def test_execute_success(self):
        """Test successful execution of reset healing state."""
        result = self.action.execute(self.mock_client, self.context)
        
        self.assertTrue(result.success)
        self.assertTrue(result.data['healing_state_reset'])
        
    def test_execute_with_exception(self):
        """Test execution when an exception occurs."""
        # Mock the logger to raise an exception
        with patch.object(self.action, 'logger') as mock_logger:
            mock_logger.debug.side_effect = Exception("Test exception")
            
            result = self.action.execute(self.mock_client, self.context)
            
            self.assertFalse(result.success)
            self.assertIn("Failed to reset healing state", result.error)
            self.assertIn("Test exception", result.error)
    
    def test_repr(self):
        """Test string representation of the action."""
        repr_str = repr(self.action)
        self.assertEqual(repr_str, "ResetHealingStateAction()")


if __name__ == '__main__':
    unittest.main()