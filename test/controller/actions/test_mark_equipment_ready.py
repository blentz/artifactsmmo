"""Test MarkEquipmentReadyAction"""

import unittest
from unittest.mock import Mock

from src.controller.actions.mark_equipment_ready import MarkEquipmentReadyAction
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters


class TestMarkEquipmentReadyAction(unittest.TestCase):
    """Test cases for MarkEquipmentReadyAction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = MarkEquipmentReadyAction()
        self.mock_client = Mock()
        
    def test_execute_success(self):
        """Test successful execution of mark equipment ready."""
        # Create context
        context = ActionContext()
        context.set(StateParameters.CHARACTER_NAME, "test_char")
        # Set equipment status in context
        context.set(StateParameters.TARGET_ITEM, 'steel_armor')
        context.set(StateParameters.TARGET_SLOT, 'body_armor')
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.message, "steel_armor is ready to be equipped")
        
    def test_execute_with_item_context(self):
        """Test execution with item context."""
        # Create context with item data
        context = ActionContext()
        context.set(StateParameters.CHARACTER_NAME, "test_char")
        context.set(StateParameters.TARGET_ITEM, 'copper_sword')
        context.set(StateParameters.TARGET_SLOT, 'weapon')
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.message, "copper_sword is ready to be equipped")
        self.assertEqual(result.data['selected_item'], 'copper_sword')
        self.assertEqual(result.data['target_slot'], 'weapon')
        
    def test_repr(self):
        """Test string representation."""
        expected = "MarkEquipmentReadyAction()"
        self.assertEqual(repr(self.action), expected)


if __name__ == '__main__':
    unittest.main()