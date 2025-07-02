"""Test AbortCombatSearchAction"""

import unittest
from unittest.mock import Mock

from src.controller.actions.abort_combat_search import AbortCombatSearchAction
from src.lib.action_context import ActionContext


class TestAbortCombatSearchAction(unittest.TestCase):
    """Test cases for AbortCombatSearchAction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = AbortCombatSearchAction()
        self.mock_client = Mock()
        
    def test_execute_success(self):
        """Test successful execution of abort combat search."""
        # Create context
        context = ActionContext(character_name="test_char")
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], "Combat search aborted, returning to idle state")
        
    def test_execute_with_search_context(self):
        """Test execution with search context."""
        # Create context with search data
        context = ActionContext(character_name="test_char")
        context['search_radius_used'] = 5
        context['locations_searched'] = 10
        context['search_pattern'] = 'spiral'
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], "Combat search aborted, returning to idle state")
        self.assertEqual(result['reason'], "No monsters available")
        
    def test_repr(self):
        """Test string representation."""
        expected = "AbortCombatSearchAction()"
        self.assertEqual(repr(self.action), expected)


if __name__ == '__main__':
    unittest.main()