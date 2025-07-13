"""
Test Healing Flow

Tests the new healing flow with bridge actions.
"""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.assess_healing_needs import AssessHealingNeedsAction
from src.controller.actions.initiate_healing import InitiateHealingAction
from src.controller.actions.complete_healing import CompleteHealingAction
from src.controller.actions.reset_healing_state import ResetHealingStateAction
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters


class TestHealingFlow(unittest.TestCase):
    """Test the healing flow bridge actions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.context = ActionContext()
        
    def test_assess_healing_needs_required(self):
        """Test assess healing needs when HP is low."""
        # Set up character with low HP using StateParameters
        self.context.set(StateParameters.CHARACTER_HP, 50)
        self.context.set(StateParameters.CHARACTER_MAX_HP, 100)
        self.context.set(StateParameters.CHARACTER_HEALTHY, True)
        
        action = AssessHealingNeedsAction()
        result = action.execute(self.mock_client, self.context)
        
        self.assertTrue(result.success)
        self.assertTrue(result.data['healing_needed'])
        self.assertEqual(result.data['current_hp'], 50)
        self.assertEqual(result.data['max_hp'], 100)
        
    def test_assess_healing_needs_not_required(self):
        """Test assess healing needs when HP is full."""
        # Set up character with full HP using StateParameters
        self.context.set(StateParameters.CHARACTER_HP, 100)
        self.context.set(StateParameters.CHARACTER_MAX_HP, 100)
        self.context.set(StateParameters.CHARACTER_HEALTHY, True)
        
        action = AssessHealingNeedsAction()
        result = action.execute(self.mock_client, self.context)
        
        self.assertTrue(result.success)
        self.assertFalse(result.data['healing_needed'])
        self.assertEqual(result.data['current_hp'], 100)
        self.assertEqual(result.data['max_hp'], 100)
        
    def test_initiate_healing(self):
        """Test initiating healing process."""
        # Set up character with healing needed using StateParameters
        self.context.set(StateParameters.CHARACTER_HP, 30)
        self.context.set(StateParameters.CHARACTER_MAX_HP, 100)
        self.context.set(StateParameters.CHARACTER_HEALTHY, True)
        self.context.set(StateParameters.HEALING_NEEDED, True)
        
        action = InitiateHealingAction()
        result = action.execute(self.mock_client, self.context)
        
        self.assertTrue(result.success)
        self.assertTrue(result.data['healing_initiated'])
        self.assertEqual(result.data['healing_method'], 'rest')
        self.assertEqual(result.data['starting_hp'], 30)
        
    def test_complete_healing(self):
        """Test completing healing process."""
        # Set up character with full HP and healing in progress using StateParameters
        self.context.set(StateParameters.CHARACTER_HP, 100)
        self.context.set(StateParameters.CHARACTER_MAX_HP, 100)
        self.context.set(StateParameters.CHARACTER_HEALTHY, True)
        self.context.set(StateParameters.HEALING_STATUS, 'healing_initiated')
        self.context.set(StateParameters.HEALING_METHOD, 'rest')
        
        action = CompleteHealingAction()
        result = action.execute(self.mock_client, self.context)
        
        self.assertTrue(result.success)
        self.assertTrue(result.data['healing_completed'])
        self.assertEqual(result.data['final_hp'], 100)
        
    def test_reset_healing_state(self):
        """Test resetting healing state."""
        action = ResetHealingStateAction()
        result = action.execute(self.mock_client, self.context)
        
        self.assertTrue(result.success)
        self.assertTrue(result.data['healing_state_reset'])


if __name__ == '__main__':
    unittest.main()