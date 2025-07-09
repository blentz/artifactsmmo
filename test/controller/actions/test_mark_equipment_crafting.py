"""Test MarkEquipmentCraftingAction"""

import unittest
from unittest.mock import Mock

from src.controller.actions.mark_equipment_crafting import MarkEquipmentCraftingAction
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters


class TestMarkEquipmentCraftingAction(unittest.TestCase):
    """Test cases for MarkEquipmentCraftingAction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = MarkEquipmentCraftingAction()
        self.mock_client = Mock()
        
    def test_execute_success(self):
        """Test successful execution of mark equipment crafting."""
        # Create context
        context = ActionContext()
        context.set(StateParameters.CHARACTER_NAME, "test_char")
        # Set equipment status in context
        context.set(StateParameters.EQUIPMENT_SELECTED_ITEM, 'iron_sword')
        context.set(StateParameters.EQUIPMENT_TARGET_SLOT, 'weapon')
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Equipment crafting initiated for iron_sword")
        
    def test_execute_with_workshop_context(self):
        """Test execution with workshop context."""
        # Create context with workshop data
        context = ActionContext()
        context.set(StateParameters.CHARACTER_NAME, "test_char")
        context.set(StateParameters.WORKSHOP_AT_WORKSHOP, True)
        context.set(StateParameters.WORKSHOP_TYPE, 'weaponcrafting')
        context.set(StateParameters.EQUIPMENT_SELECTED_ITEM, 'wooden_shield')
        context.set(StateParameters.EQUIPMENT_TARGET_SLOT, 'shield')
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Equipment crafting initiated for wooden_shield")
        self.assertEqual(result.data['selected_item'], 'wooden_shield')
        self.assertEqual(result.data['target_slot'], 'shield')
        
    def test_repr(self):
        """Test string representation."""
        expected = "MarkEquipmentCraftingAction()"
        self.assertEqual(repr(self.action), expected)


if __name__ == '__main__':
    unittest.main()