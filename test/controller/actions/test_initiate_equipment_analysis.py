"""Test InitiateEquipmentAnalysisAction"""

import unittest
from unittest.mock import Mock

from src.controller.actions.initiate_equipment_analysis import InitiateEquipmentAnalysisAction
from src.lib.action_context import ActionContext


class TestInitiateEquipmentAnalysisAction(unittest.TestCase):
    """Test cases for InitiateEquipmentAnalysisAction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = InitiateEquipmentAnalysisAction()
        self.mock_client = Mock()
        
    def test_execute_success(self):
        """Test successful execution of initiate equipment analysis."""
        # Create context
        context = ActionContext(character_name="test_char")
        # Set character_status in context
        context['character_status'] = {
            'level': 3
        }
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], "Equipment upgrade analysis initiated")
        
    def test_execute_with_equipment_context(self):
        """Test execution with existing equipment context."""
        # Create context with equipment data
        context = ActionContext(character_name="test_char")
        context['current_weapon'] = 'wooden_stick'
        context['character_status'] = {
            'level': 2
        }
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], "Equipment upgrade analysis initiated")
        self.assertEqual(result['character_level'], 2)
        
    def test_repr(self):
        """Test string representation."""
        expected = "InitiateEquipmentAnalysisAction()"
        self.assertEqual(repr(self.action), expected)


if __name__ == '__main__':
    unittest.main()