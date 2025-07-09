"""Test AbortCombatSearchAction"""

import unittest
from unittest.mock import Mock

from src.controller.actions.abort_combat_search import AbortCombatSearchAction
from src.controller.actions.base import ActionResult
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters


class TestAbortCombatSearchAction(unittest.TestCase):
    """Test cases for AbortCombatSearchAction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = AbortCombatSearchAction()
        self.mock_client = Mock()
        
    def test_execute_success(self):
        """Test successful execution of abort combat search."""
        # Create context
        context = ActionContext()
        context.set(StateParameters.CHARACTER_NAME, "test_char")
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify result
        self.assertIsInstance(result, ActionResult)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Combat search aborted, returning to idle state")
        self.assertIn('combat_context', result.state_changes)
        self.assertEqual(result.state_changes['combat_context']['status'], 'idle')
        
    def test_execute_with_search_context(self):
        """Test execution with search context."""
        # Create context with search data using StateParameters
        context = ActionContext()
        context.set(StateParameters.CHARACTER_NAME, "test_char")
        # Note: search_radius_used, locations_searched, search_pattern are not core StateParameters
        # These would be handled by the action's internal logic, not stored in context
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify result
        self.assertIsInstance(result, ActionResult)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Combat search aborted, returning to idle state")
        self.assertEqual(result.data['reason'], "No monsters available")
        self.assertIn('combat_context', result.state_changes)
        
    def test_repr(self):
        """Test string representation."""
        expected = "AbortCombatSearchAction()"
        self.assertEqual(repr(self.action), expected)


if __name__ == '__main__':
    unittest.main()