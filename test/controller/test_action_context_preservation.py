"""
Test Action Context Preservation

This module tests that actions properly preserve information in the ActionContext
for subsequent actions to use.
"""

import unittest
from unittest.mock import MagicMock, Mock, patch

from src.controller.actions.analyze_crafting_chain import AnalyzeCraftingChainAction
from src.controller.actions.evaluate_weapon_recipes import EvaluateWeaponRecipesAction
from src.lib.action_context import ActionContext


class TestActionContextPreservation(unittest.TestCase):
    """Test that actions properly update ActionContext to pass information to subsequent actions."""
    
    def setUp(self):
        """Set up test fixtures."""
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
        
        # Create context with necessary data
        context = ActionContext()
        context.character_name = "TestChar"
        context.character_level = 5
        # Add action_config to prevent AttributeError
        context.action_data['action_config'] = {}
        
        # Mock character state
        character_state = Mock()
        character_state.name = "TestChar"
        character_state.data = {
            'level': 5,
            'weaponcrafting_level': 3,
            'inventory': []
        }
        context.character_state = character_state
        
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
            }
        }
        knowledge_base.get_item_data = MagicMock(return_value=None)
        context.knowledge_base = knowledge_base
        
        # Mock API response for character data
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.inventory = []
        char_response.data.weaponcrafting_level = 3
        self.client.return_value = char_response
        
        # Execute the action
        with patch('src.controller.actions.evaluate_weapon_recipes.get_character_api', return_value=char_response):
            result = action.execute(self.client, context)
        
        # Verify the action was successful
        self.assertTrue(result['success'])
        
        # Verify target_item is in the result
        self.assertIn('target_item', result)
        self.assertEqual(result['target_item'], 'wooden_staff')
        
        # Verify target_item was set in the context results
        self.assertEqual(context.action_results.get('target_item'), 'wooden_staff')
        self.assertEqual(context.action_results.get('item_code'), 'wooden_staff')
    
    def test_analyze_crafting_chain_reads_target_item_from_context(self):
        """Test that analyze_crafting_chain can read target_item from context set by previous action."""
        # Create action
        action = AnalyzeCraftingChainAction()
        
        # Create context with target_item set by previous action
        context = ActionContext()
        context.character_name = "TestChar"
        context.action_results['target_item'] = 'wooden_staff'  # Set by previous action
        context.action_results['item_code'] = 'wooden_staff'
        
        # Mock knowledge base with proper data structure
        knowledge_base = Mock()
        # Create a Mock for data that behaves like a dict
        mock_data = Mock()
        mock_data.get = Mock(return_value={'wooden_staff': {
            'code': 'wooden_staff',
            'name': 'Wooden Staff',
            'craft_data': {
                'items': [{'code': 'ash_wood', 'quantity': 2}]
            }
        }})  # Return dict with the item when accessing items
        knowledge_base.data = mock_data
        knowledge_base.get_item_data = MagicMock(return_value={
            'code': 'wooden_staff',
            'name': 'Wooden Staff',
            'craft_data': {
                'items': [{'code': 'ash_wood', 'quantity': 2}]
            }
        })
        context.knowledge_base = knowledge_base
        
        # Mock map state
        map_state = Mock()
        map_state.find_closest_location = MagicMock(return_value=(5, 5))
        context.map_state = map_state
        
        # Execute the action
        result = action.execute(self.client, context)
        
        # Verify the action was successful
        self.assertTrue(result['success'])
        
        # Verify it used the correct target_item
        self.assertEqual(result['target_item'], 'wooden_staff')
    
    def test_action_context_get_method_checks_action_results(self):
        """Test that ActionContext.get() checks action_results for data from previous actions."""
        context = ActionContext()
        
        # Simulate previous action setting results
        context.action_results['target_item'] = 'wooden_staff'
        context.action_results['workshop_location'] = (10, 5)
        
        # Verify get() retrieves from action_results
        self.assertEqual(context.get('target_item'), 'wooden_staff')
        self.assertEqual(context.get('workshop_location'), (10, 5))
        
        # Verify get_parameter() also checks action_results
        self.assertEqual(context.get_parameter('target_item'), 'wooden_staff')
        
        # Verify non-existent keys return default
        self.assertIsNone(context.get('non_existent'))
        self.assertEqual(context.get('non_existent', 'default'), 'default')


if __name__ == '__main__':
    unittest.main()