"""Test module for InitiateCombatSearchAction."""

import unittest
from unittest.mock import Mock, patch
import logging

from src.controller.actions.initiate_combat_search import InitiateCombatSearchAction
from src.lib.action_context import ActionContext
from test.fixtures import MockActionContext, create_mock_client


class TestInitiateCombatSearchAction(unittest.TestCase):
    """Test cases for InitiateCombatSearchAction class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = InitiateCombatSearchAction()
        self.mock_client = create_mock_client()
        self.context = MockActionContext(character_name="TestCharacter")
    
    def test_init(self):
        """Test initialization."""
        action = InitiateCombatSearchAction()
        self.assertIsInstance(action, InitiateCombatSearchAction)
        self.assertIsInstance(action.logger, logging.Logger)
        
        # Check GOAP parameters
        self.assertEqual(action.conditions, {
            'combat_context': {
                'status': 'idle'
            },
            'character_status': {
                'alive': True,
                'cooldown_active': False
            }
        })
        self.assertEqual(action.reactions, {
            'combat_context': {
                'status': 'searching'
            }
        })
        self.assertEqual(action.weight, 2)
        self.assertEqual(action.g, 1)
    
    def test_execute_success(self):
        """Test successful execution."""
        result = self.action.execute(self.mock_client, self.context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Combat search initiated - ready to find monsters")
        
        # Check combat context in data
        self.assertIn('combat_context', result.data)
        combat_context = result.data['combat_context']
        self.assertEqual(combat_context['status'], 'searching')
        self.assertIsNone(combat_context['target'])
        self.assertIsNone(combat_context['location'])
        
        # Verify context was stored
        self.assertEqual(self.action._context, self.context)
    
    def test_execute_with_exception(self):
        """Test execution with exception handling."""
        # Mock logger.info to raise exception
        with patch.object(self.action.logger, 'info', side_effect=Exception("Test exception")):
            result = self.action.execute(self.mock_client, self.context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Failed to initiate combat search: Test exception")
    
    def test_execute_logs_message(self):
        """Test that execution logs appropriate message."""
        with patch.object(self.action.logger, 'info') as mock_log:
            self.action.execute(self.mock_client, self.context)
            
            mock_log.assert_called_once_with(
                "🔍 Initiating combat search - transitioning from idle to searching"
            )
    
    def test_execute_logs_error_on_exception(self):
        """Test that execution logs error on exception."""
        with patch.object(self.action.logger, 'info', side_effect=Exception("Test error")):
            with patch.object(self.action.logger, 'error') as mock_error:
                self.action.execute(self.mock_client, self.context)
                
                mock_error.assert_called_once_with("Failed to initiate combat search: Test error")
    
    def test_client_not_used(self):
        """Test that client parameter is not used in this action."""
        # Execute with None client - should still work
        result = self.action.execute(None, self.context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Combat search initiated - ready to find monsters")
    
    def test_repr(self):
        """Test __repr__ method."""
        self.assertEqual(repr(self.action), "InitiateCombatSearchAction()")
    
    def test_multiple_weight_definitions(self):
        """Test that weight is correctly set despite multiple definitions."""
        # The code has weight = 2.0 and weight = 2, the second overwrites the first
        self.assertEqual(self.action.weight, 2)
        self.assertIsInstance(self.action.weight, int)


if __name__ == '__main__':
    unittest.main()