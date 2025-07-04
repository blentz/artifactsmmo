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


class TestHealingFlow(unittest.TestCase):
    """Test the healing flow bridge actions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.context = ActionContext()
        
    def test_assess_healing_needs_required(self):
        """Test assess healing needs when HP is low."""
        # Set up world state with low HP
        self.context.world_state = {
            'character_status': {
                'hp_percentage': 50.0,
                'alive': True
            }
        }
        
        action = AssessHealingNeedsAction()
        result = action.execute(self.mock_client, self.context)
        
        self.assertTrue(result.success)
        self.assertTrue(result.data['healing_needed'])
        self.assertEqual(result.data['current_hp_percentage'], 50.0)
        
    def test_assess_healing_needs_not_required(self):
        """Test assess healing needs when HP is full."""
        # Set up world state with full HP
        self.context.world_state = {
            'character_status': {
                'hp_percentage': 100.0,
                'alive': True
            }
        }
        
        action = AssessHealingNeedsAction()
        result = action.execute(self.mock_client, self.context)
        
        self.assertTrue(result.success)
        self.assertFalse(result.data['healing_needed'])
        
    def test_initiate_healing(self):
        """Test initiating healing process."""
        self.context.world_state = {
            'character_status': {
                'hp_percentage': 30.0,
                'alive': True
            }
        }
        
        action = InitiateHealingAction()
        result = action.execute(self.mock_client, self.context)
        
        self.assertTrue(result.success)
        self.assertTrue(result.data['healing_initiated'])
        self.assertEqual(result.data['healing_method'], 'rest')
        self.assertEqual(result.data['starting_hp'], 30.0)
        
    def test_complete_healing(self):
        """Test completing healing process."""
        self.context.world_state = {
            'character_status': {
                'hp_percentage': 100.0,
                'alive': True
            },
            'healing_context': {
                'healing_method': 'rest'
            }
        }
        self.context.starting_hp = 30.0
        
        action = CompleteHealingAction()
        result = action.execute(self.mock_client, self.context)
        
        self.assertTrue(result.success)
        self.assertTrue(result.data['healing_complete'])
        self.assertEqual(result.data['final_hp'], 100.0)
        self.assertEqual(result.data['hp_gained'], 70.0)
        
    def test_reset_healing_state(self):
        """Test resetting healing state."""
        action = ResetHealingStateAction()
        result = action.execute(self.mock_client, self.context)
        
        self.assertTrue(result.success)
        self.assertTrue(result.data['healing_state_reset'])


if __name__ == '__main__':
    unittest.main()