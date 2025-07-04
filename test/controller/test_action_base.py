"""Test module for ActionBase."""

import unittest

from src.controller.actions.base import ActionBase, ActionResult
from src.lib.action_context import ActionContext

from test.fixtures import MockActionContext, create_mock_client


class TestableActionBase(ActionBase):
    """Concrete implementation of ActionBase for testing."""
    
    conditions = {}
    reactions = {}
    weight = 1.0
    
    def execute(self, client, context: ActionContext) -> ActionResult:
        """Test implementation of execute."""
        self._context = context
        return self.create_success_result("Test execution")


class TestActionBase(unittest.TestCase):
    """Test cases for ActionBase."""

    def setUp(self):
        """Set up test fixtures."""
        self.action = TestableActionBase()
        self.mock_client = create_mock_client()
        self.mock_context = MockActionContext(character_name="test_character")

    
    def test_create_success_result_basic(self):
        """Test create_success_result with basic message."""
        result = self.action.create_success_result("Test success")
        
        self.assertIsInstance(result, ActionResult)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Test success")
        self.assertIsNone(result.error)
        self.assertEqual(result.action_name, "TestableActionBase")

    def test_create_success_result_with_data(self):
        """Test create_success_result with additional data."""
        result = self.action.create_success_result("Test success", items=[1, 2, 3], location=(5, 3))
        
        self.assertIsInstance(result, ActionResult)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Test success")
        self.assertEqual(result.data['items'], [1, 2, 3])
        self.assertEqual(result.data['location'], (5, 3))

    def test_create_error_result_basic(self):
        """Test create_error_result with basic error message."""
        result = self.action.create_error_result("Test error")
        
        self.assertIsInstance(result, ActionResult)
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Test error")
        self.assertEqual(result.action_name, "TestableActionBase")

    def test_create_error_result_with_data(self):
        """Test create_error_result with additional data."""
        result = self.action.create_error_result("Test error", code='E001', location=(5, 3))
        
        self.assertIsInstance(result, ActionResult)
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Test error")
        self.assertEqual(result.data['code'], 'E001')
        self.assertEqual(result.data['location'], (5, 3))

    def test_create_result_with_state_changes(self):
        """Test create_result_with_state_changes method."""
        state_changes = {'hp': 100, 'location': {'x': 5, 'y': 3}}
        result = self.action.create_result_with_state_changes(
            success=True,
            state_changes=state_changes,
            message="State updated",
            items_collected=5
        )
        
        self.assertIsInstance(result, ActionResult)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "State updated")
        self.assertEqual(result.state_changes, state_changes)
        self.assertEqual(result.data['items_collected'], 5)

    def test_action_base_has_goap_attributes(self):
        """Test that ActionBase has expected GOAP class attributes."""
        self.assertTrue(hasattr(ActionBase, 'conditions'))
        self.assertTrue(hasattr(ActionBase, 'reactions'))
        self.assertTrue(hasattr(ActionBase, 'weight'))
        
        # Check that they are correct types
        self.assertIsInstance(ActionBase.conditions, dict)
        self.assertIsInstance(ActionBase.reactions, dict)
        self.assertIsInstance(ActionBase.weight, (int, float))

    def test_action_base_repr(self):
        """Test ActionBase string representation."""
        result = repr(self.action)
        self.assertEqual(result, "TestableActionBase(weight=1.0)")


if __name__ == '__main__':
    unittest.main()