"""Test ResetEquipmentUpgradeAction"""

import unittest
from unittest.mock import Mock

from src.controller.actions.reset_equipment_upgrade import ResetEquipmentUpgradeAction
from src.lib.action_context import ActionContext


class TestResetEquipmentUpgradeAction(unittest.TestCase):
    """Test cases for ResetEquipmentUpgradeAction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = ResetEquipmentUpgradeAction()
        self.mock_client = Mock()
        
    def test_execute_success(self):
        """Test successful execution of reset equipment upgrade."""
        # Create context
        context = ActionContext(character_name="test_char")
        # Set equipment_status in context
        context['equipment_status'] = {
            'selected_item': 'iron_sword'
        }
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Equipment upgrade status reset, ready for new upgrade")
        
    def test_execute_with_previous_upgrade_context(self):
        """Test execution with previous upgrade context."""
        # Create context with previous upgrade data
        context = ActionContext(character_name="test_char")
        context['previous_weapon'] = 'copper_sword'
        context['previous_target_slot'] = 'weapon'
        context['equipment_status'] = {
            'selected_item': 'copper_sword'
        }
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Equipment upgrade status reset, ready for new upgrade")
        self.assertEqual(result.data['previous_item'], 'copper_sword')
        
    def test_repr(self):
        """Test string representation."""
        expected = "ResetEquipmentUpgradeAction()"
        self.assertEqual(repr(self.action), expected)


if __name__ == '__main__':
    unittest.main()