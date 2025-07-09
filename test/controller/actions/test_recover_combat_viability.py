"""Test RecoverCombatViabilityAction"""

import unittest
from unittest.mock import Mock

from src.controller.actions.recover_combat_viability import RecoverCombatViabilityAction
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from test.test_base import UnifiedContextTestBase


class TestRecoverCombatViabilityAction(UnifiedContextTestBase):
    """Test cases for RecoverCombatViabilityAction."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.action = RecoverCombatViabilityAction()
        self.mock_client = Mock()
        
    def test_execute_success(self):
        """Test successful execution of recover combat viability."""
        # Set character name and equipment status using StateParameters
        self.context.set(StateParameters.CHARACTER_NAME, "test_char")
        self.context.set(StateParameters.EQUIPMENT_SELECTED_ITEM, 'iron_sword')
        
        # Execute action
        result = self.action.execute(self.mock_client, self.context)
        
        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Combat viability recovered, ready to resume hunting")
        
    def test_execute_with_upgraded_equipment_context(self):
        """Test execution with upgraded equipment context."""
        # Set context with upgraded equipment data using StateParameters
        self.context.set(StateParameters.CHARACTER_NAME, "test_char")
        self.context.set(StateParameters.EQUIPMENT_NEW_WEAPON, 'copper_sword')
        self.context.set(StateParameters.EQUIPMENT_OLD_WEAPON, 'wooden_stick')
        self.context.set(StateParameters.EQUIPMENT_UPGRADED, True)
        self.context.set(StateParameters.EQUIPMENT_SELECTED_ITEM, 'copper_sword')
        
        # Execute action
        result = self.action.execute(self.mock_client, self.context)
        
        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Combat viability recovered, ready to resume hunting")
        self.assertEqual(result.data['equipment_upgraded'], 'copper_sword')
        self.assertEqual(result.data['win_rate_reset'], True)
        
    def test_repr(self):
        """Test string representation."""
        expected = "RecoverCombatViabilityAction()"
        self.assertEqual(repr(self.action), expected)


if __name__ == '__main__':
    unittest.main()