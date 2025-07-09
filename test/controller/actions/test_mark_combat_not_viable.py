"""Test MarkCombatNotViableAction"""

import unittest
from unittest.mock import Mock

from src.controller.actions.mark_combat_not_viable import MarkCombatNotViableAction
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters


class TestMarkCombatNotViableAction(unittest.TestCase):
    """Test cases for MarkCombatNotViableAction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = MarkCombatNotViableAction()
        self.mock_client = Mock()
        
    def test_execute_success(self):
        """Test successful execution of mark combat not viable."""
        # Create context
        context = ActionContext()
        context.set(StateParameters.CHARACTER_NAME, "test_char")
        # Set combat context in context
        context.set(StateParameters.COMBAT_RECENT_WIN_RATE, 0.0)
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Combat marked as not viable (win rate: 0.0%)")
        
    def test_execute_with_win_rate_context(self):
        """Test execution with win rate context."""
        # Create context with combat data
        context = ActionContext()
        context.set(StateParameters.CHARACTER_NAME, "test_char")
        context.set(StateParameters.COMBAT_RECENT_WIN_RATE, 0.15)
        context.set(StateParameters.COMBAT_STATUS, 'active')
        context.set(StateParameters.RECENT_LOSSES, 8)
        context.set(StateParameters.RECENT_WINS, 2)
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Combat marked as not viable (win rate: 15.0%)")
        self.assertEqual(result.data['recent_win_rate'], 0.15)
        self.assertEqual(result.data['recommendation'], "Upgrade equipment before continuing combat")
        
    def test_repr(self):
        """Test string representation."""
        expected = "MarkCombatNotViableAction()"
        self.assertEqual(repr(self.action), expected)


if __name__ == '__main__':
    unittest.main()