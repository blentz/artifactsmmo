"""Test CompleteEquipmentUpgradeAction"""

import unittest
from unittest.mock import Mock

from src.controller.actions.complete_equipment_upgrade import CompleteEquipmentUpgradeAction
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters


class TestCompleteEquipmentUpgradeAction(unittest.TestCase):
    """Test cases for CompleteEquipmentUpgradeAction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = CompleteEquipmentUpgradeAction()
        self.mock_client = Mock()
        
    def test_execute_success(self):
        """Test successful execution of complete equipment upgrade."""
        # Create context
        context = ActionContext()
        context.set(StateParameters.CHARACTER_NAME, "test_char")
        # Set equipment_status parameters in context
        context.set(StateParameters.TARGET_ITEM, 'iron_sword')
        context.set(StateParameters.TARGET_SLOT, 'weapon')
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Equipment upgrade completed with iron_sword")
        
    def test_execute_with_character_state(self):
        """Test execution with character state context."""
        # Create context with character data
        context = ActionContext()
        context.set(StateParameters.CHARACTER_NAME, "test_char")
        context.set(StateParameters.CHARACTER_X, 5)
        context.set(StateParameters.CHARACTER_Y, 10)
        # Set equipment_status parameters in context
        context.set(StateParameters.TARGET_ITEM, 'wooden_shield')
        context.set(StateParameters.TARGET_SLOT, 'shield')
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Equipment upgrade completed with wooden_shield")
        self.assertEqual(result.data['equipped_item'], 'wooden_shield')
        self.assertEqual(result.data['target_slot'], 'shield')
        
    def test_repr(self):
        """Test string representation."""
        expected = "CompleteEquipmentUpgradeAction()"
        self.assertEqual(repr(self.action), expected)


if __name__ == '__main__':
    unittest.main()