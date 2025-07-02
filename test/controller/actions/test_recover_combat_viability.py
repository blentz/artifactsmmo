"""Test RecoverCombatViabilityAction"""

import unittest
from unittest.mock import Mock

from src.controller.actions.recover_combat_viability import RecoverCombatViabilityAction
from src.lib.action_context import ActionContext


class TestRecoverCombatViabilityAction(unittest.TestCase):
    """Test cases for RecoverCombatViabilityAction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = RecoverCombatViabilityAction()
        self.mock_client = Mock()
        
    def test_execute_success(self):
        """Test successful execution of recover combat viability."""
        # Create context
        context = ActionContext(character_name="test_char")
        # Set equipment_status in context
        context['equipment_status'] = {
            'selected_item': 'iron_sword'
        }
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], "Combat viability recovered, ready to resume hunting")
        
    def test_execute_with_upgraded_equipment_context(self):
        """Test execution with upgraded equipment context."""
        # Create context with upgraded equipment data
        context = ActionContext(character_name="test_char")
        context['new_weapon'] = 'copper_sword'
        context['old_weapon'] = 'wooden_stick'
        context['equipment_upgraded'] = True
        context['equipment_status'] = {
            'selected_item': 'copper_sword'
        }
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], "Combat viability recovered, ready to resume hunting")
        self.assertEqual(result['equipment_upgraded'], 'copper_sword')
        self.assertEqual(result['win_rate_reset'], True)
        
    def test_repr(self):
        """Test string representation."""
        expected = "RecoverCombatViabilityAction()"
        self.assertEqual(repr(self.action), expected)


if __name__ == '__main__':
    unittest.main()