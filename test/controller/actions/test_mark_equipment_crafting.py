"""Test MarkEquipmentCraftingAction"""

import unittest
from unittest.mock import Mock

from src.controller.actions.mark_equipment_crafting import MarkEquipmentCraftingAction
from src.lib.action_context import ActionContext


class TestMarkEquipmentCraftingAction(unittest.TestCase):
    """Test cases for MarkEquipmentCraftingAction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = MarkEquipmentCraftingAction()
        self.mock_client = Mock()
        
    def test_execute_success(self):
        """Test successful execution of mark equipment crafting."""
        # Create context
        context = ActionContext(character_name="test_char")
        # Set equipment_status in context
        context['equipment_status'] = {
            'selected_item': 'iron_sword',
            'target_slot': 'weapon'
        }
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], "Equipment crafting initiated for iron_sword")
        
    def test_execute_with_workshop_context(self):
        """Test execution with workshop context."""
        # Create context with workshop data
        context = ActionContext(character_name="test_char")
        context['at_workshop'] = True
        context['workshop_type'] = 'weaponcrafting'
        context['equipment_status'] = {
            'selected_item': 'wooden_shield',
            'target_slot': 'shield'
        }
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], "Equipment crafting initiated for wooden_shield")
        self.assertEqual(result['selected_item'], 'wooden_shield')
        self.assertEqual(result['target_slot'], 'shield')
        
    def test_repr(self):
        """Test string representation."""
        expected = "MarkEquipmentCraftingAction()"
        self.assertEqual(repr(self.action), expected)


if __name__ == '__main__':
    unittest.main()