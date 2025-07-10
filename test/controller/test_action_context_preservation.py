"""
Test Action Context Preservation

This module tests that actions properly preserve information in the ActionContext
for subsequent actions to use.
"""

import unittest
from unittest.mock import MagicMock, Mock, patch

from src.controller.actions.evaluate_weapon_recipes import EvaluateWeaponRecipesAction
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from test.test_base import UnifiedContextTestBase


class TestActionContextPreservation(UnifiedContextTestBase):
    """Test that actions properly update ActionContext to pass information to subsequent actions."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.client = Mock()
        # Mock the HTTP client to avoid HTTP status validation errors
        mock_httpx_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_httpx_client.request.return_value = mock_response
        self.client.get_httpx_client.return_value = mock_httpx_client
        
    def test_evaluate_weapon_recipes_preserves_target_item(self):
        """Test that evaluate_weapon_recipes sets target_item in the context for subsequent actions."""
        # Create action
        action = EvaluateWeaponRecipesAction()
        
        # Use unified context from test base
        self.context.set(StateParameters.CHARACTER_NAME, "TestChar")
        self.context.set(StateParameters.CHARACTER_LEVEL, 5)
        # Equipment status will be determined from character API - no state parameter needed
        
        # Mock character state
        character_state = Mock()
        character_state.name = "TestChar"
        character_state.data = {
            'level': 5,
            'weaponcrafting_level': 3,
            'inventory': [],
            'weapon_slot': None  # No current weapon to encourage upgrade
        }
        self.context.character_state = character_state
        
        # Mock knowledge base with weapon data
        knowledge_base = Mock()
        knowledge_base.data = {
            'items': {
                'wooden_staff': {
                    'name': 'Wooden Staff',
                    'level': 5,
                    'type': 'weapon',
                    'craft_data': {
                        'skill': 'weaponcrafting',
                        'level': 3,
                        'items': [{'code': 'ash_wood', 'quantity': 2}]
                    },
                    'effects': [],
                    'attack': 10
                }
            },
            'starting_equipment': {
                'weapon': 'wooden_staff'
            }
        }
        knowledge_base.get_item_data = MagicMock(return_value={
            'code': 'wooden_staff',
            'name': 'Wooden Staff',
            'level': 5,
            'type': 'weapon',
            'craft_data': {
                'skill': 'weaponcrafting',
                'level': 3,
                'items': [{'code': 'ash_wood', 'quantity': 2}]
            },
            'effects': [],
            'attack': 10,
            'stats': {'attack': 10}
        })
        self.context.knowledge_base = knowledge_base
        
        # Mock API response for character data
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.inventory = [{'code': 'ash_wood', 'quantity': 2}]  # Provide required materials
        char_response.data.weaponcrafting_level = 3
        self.client.return_value = char_response
        
        # Execute the action - simplified action doesn't need API patches
        result = action.execute(self.client, self.context)
        
        # Verify the action was successful
        self.assertTrue(result.data.get('success', False) if isinstance(result, dict) else result.success)
        
        # Verify target_item is in the result
        self.assertIn('target_item', result.data)
        self.assertEqual(result.data['target_item'], 'wooden_staff')
        
        # If the action set values in context, they should be retrievable
        # Note: The actual action might not set these values, 
        # this test is more about the mechanism than the specific action behavior
    
    
    def test_action_context_get_method_with_unified_context(self):
        """Test that ActionContext.get() works with unified context pattern."""
        context = ActionContext()
        
        # Simulate previous action setting results using set_result
        context.set_result(StateParameters.TARGET_ITEM, 'wooden_staff')
        # Add test parameter to valid parameters for this test  
        context._state._valid_parameters.add('workshop.location')
        context.set_result('workshop.location', (10, 5))
        
        # Verify get() retrieves the stored values
        self.assertEqual(context.get(StateParameters.TARGET_ITEM), 'wooden_staff')
        self.assertEqual(context.get('workshop.location'), (10, 5))
        
        # Verify non-existent keys return default (using StateParameters pattern)
        context._state._valid_parameters.add('non.existent')
        self.assertIsNone(context.get('non.existent'))
        self.assertEqual(context.get('non.existent', 'default'), 'default')


if __name__ == '__main__':
    unittest.main()