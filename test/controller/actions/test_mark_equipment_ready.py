"""Test MarkEquipmentReadyAction"""

import unittest
from unittest.mock import Mock

from src.controller.actions.mark_equipment_ready import MarkEquipmentReadyAction
from src.lib.action_context import ActionContext


class TestMarkEquipmentReadyAction(unittest.TestCase):
    """Test cases for MarkEquipmentReadyAction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = MarkEquipmentReadyAction()
        self.mock_client = Mock()
        
    def test_execute_success(self):
        """Test successful execution of mark equipment ready."""
        # Create context
        context = ActionContext(character_name="test_char")
        # Set equipment_status in context
        context['equipment_status'] = {
            'selected_item': 'steel_armor',
            'target_slot': 'body_armor'
        }
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], "steel_armor is ready to be equipped")
        
    def test_execute_with_item_context(self):
        """Test execution with item context."""
        # Create context with item data
        context = ActionContext(character_name="test_char")
        context['equipment_status'] = {
            'selected_item': 'copper_sword',
            'target_slot': 'weapon'
        }
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], "copper_sword is ready to be equipped")
        self.assertEqual(result['selected_item'], 'copper_sword')
        self.assertEqual(result['target_slot'], 'weapon')
        
    def test_repr(self):
        """Test string representation."""
        expected = "MarkEquipmentReadyAction()"
        self.assertEqual(repr(self.action), expected)


if __name__ == '__main__':
    unittest.main()