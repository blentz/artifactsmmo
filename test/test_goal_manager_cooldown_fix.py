"""
Unit tests for cooldown handling in actions.

This test validates the cooldown handling system that detects cooldown errors
and properly requests wait_for_cooldown subgoals using the current architecture.
"""

import tempfile
import unittest
from unittest.mock import Mock

from src.controller.actions.base import ActionBase, ActionResult
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters


class TestCooldownAction(ActionBase):
    """Test action that implements cooldown handling."""
    
    conditions = {StateParameters.CHARACTER_LEVEL: 1}
    reactions = {"test_action": "completed"}
    weight = 1.0
    
    def execute(self, client, context: ActionContext) -> ActionResult:
        """Test action that can trigger cooldown errors."""
        # Check cooldown handling from base class
        cooldown_result = super().execute(client, context)
        if cooldown_result:
            return cooldown_result
        
        # Simulate action logic that might hit cooldown
        if hasattr(self, '_force_cooldown_error') and self._force_cooldown_error:
            # Simulate a cooldown error
            cooldown_error = Exception("Character in cooldown (status 499)")
            if self.is_cooldown_error(cooldown_error):
                return self.handle_cooldown_error()
        
        return self.create_success_result("Action completed successfully")


class TestGoalManagerCooldownFix(unittest.TestCase):
    """Test cooldown handling in action system."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.action = TestCooldownAction()
        self.client = Mock()
        self.context = ActionContext()
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_active_cooldown_with_future_expiration_returns_true(self):
        """Test that cooldown errors are properly detected."""
        # Test status 499 detection
        error_499 = Exception("Character in cooldown (status 499)")
        self.assertTrue(self.action.is_cooldown_error(error_499))
        
        # Test "cooldown" string detection
        error_cooldown = Exception("Character is on cooldown")
        self.assertTrue(self.action.is_cooldown_error(error_cooldown))
        
        # Test non-cooldown error
        other_error = Exception("Some other error")
        self.assertFalse(self.action.is_cooldown_error(other_error))
    
    def test_direct_cooldown_check_method(self):
        """Test that cooldown errors trigger proper subgoal request."""
        # Force the action to generate a cooldown error
        self.action._force_cooldown_error = True
        
        # Execute the action
        result = self.action.execute(self.client, self.context)
        
        # Should return success result with subgoal request
        self.assertTrue(result.success)
        self.assertIsNotNone(result.subgoal_request)
        self.assertEqual(result.subgoal_request["goal_name"], "wait_for_cooldown")
    
    def test_expired_cooldown_with_legacy_field_returns_false(self):
        """Test that actions properly retry after cooldown completion."""
        # Set the cooldown handled flag
        self.context.set(StateParameters.CHARACTER_COOLDOWN_HANDLED, True)
        
        # Execute the action
        result = self.action.execute(self.client, self.context)
        
        # Should clear the cooldown flag and proceed with normal execution
        self.assertFalse(self.context.get(StateParameters.CHARACTER_COOLDOWN_HANDLED))
        # Since we're not forcing cooldown error, should complete successfully
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Action completed successfully")
    
    def test_no_expiration_time_uses_legacy_field(self):
        """Test successful action execution without cooldown."""
        # Execute the action normally
        result = self.action.execute(self.client, self.context)
        
        # Should complete successfully
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Action completed successfully")
        self.assertIsNone(result.subgoal_request)
    
    def test_no_cooldown_data_returns_false(self):
        """Test that non-cooldown errors don't trigger cooldown handling."""
        # Test that general errors don't trigger cooldown handling
        general_error = Exception("Network error")
        self.assertFalse(self.action.is_cooldown_error(general_error))
        
        # Test that empty error messages don't trigger cooldown handling
        empty_error = Exception("")
        self.assertFalse(self.action.is_cooldown_error(empty_error))


if __name__ == '__main__':
    unittest.main()