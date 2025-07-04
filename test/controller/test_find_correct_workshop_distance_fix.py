"""
Test for FindCorrectWorkshopAction distance calculation fix
"""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.find_correct_workshop import FindCorrectWorkshopAction
from src.lib.action_context import ActionContext


class TestFindCorrectWorkshopDistanceFix(unittest.TestCase):
    """Test that FindCorrectWorkshopAction correctly calculates distances."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = FindCorrectWorkshopAction()
        self.client = Mock()
        
    def test_calculate_distance_with_correct_parameters(self):
        """Test that _calculate_distance is called with all required parameters."""
        # Create context with character position
        context = ActionContext()
        context.character_name = "TestChar"
        context.character_x = 5
        context.character_y = 5
        context.action_data['item_code'] = 'wooden_staff'
        
        # Mock map state and knowledge base
        context.map_state = Mock()
        context.map_state.data = {}
        
        context.knowledge_base = Mock()
        context.knowledge_base.data = {
            'workshops': {
                'weaponcrafting_workshop': {
                    'x': 10,
                    'y': 10,
                    'craft_skill': 'weaponcrafting'
                }
            }
        }
        
        # Mock item API response
        item_response = Mock()
        item_response.data = Mock()
        item_response.data.craft = Mock()
        item_response.data.craft.skill = 'weaponcrafting'
        
        with patch('src.controller.actions.find_correct_workshop.get_item_api', return_value=item_response):
            # Execute the action
            result = self.action.execute(self.client, context)
        
        # Verify success
        self.assertTrue(result.success)
        self.assertEqual(result.data['workshop_type'], 'weaponcrafting')
        
        # Verify distance calculation was correct (from 5,5 to 10,10)
        expected_distance = ((10-5)**2 + (10-5)**2) ** 0.5  # ~7.07
        self.assertAlmostEqual(result.data['distance'], expected_distance, places=1)
    
    def test_result_processor_uses_character_position(self):
        """Test that the result processor correctly uses character position for distance."""
        # Create context
        context = ActionContext()
        context.character_name = "TestChar"
        context.character_x = 0
        context.character_y = 0
        context.action_data['item_code'] = 'wooden_staff'
        context.action_data['search_radius'] = 5
        
        # Mock map state
        map_state = Mock()
        map_state.scan = Mock(return_value={
            'success': True,
            'location': (3, 4),
            'content': {
                'code': 'weaponcrafting_workshop',
                'type': 'workshop'
            }
        })
        context.map_state = map_state
        
        # Mock knowledge base (empty)
        context.knowledge_base = Mock()
        context.knowledge_base.data = {'workshops': {}}
        
        # Mock item API response
        item_response = Mock()
        item_response.data = Mock()
        item_response.data.craft = Mock()
        item_response.data.craft.skill = 'weaponcrafting'
        
        with patch('src.controller.actions.find_correct_workshop.get_item_api', return_value=item_response):
            # Mock unified_search to capture the result processor
            original_unified_search = self.action.unified_search
            result_processor = None
            
            def capture_result_processor(client, char_x, char_y, radius, filter_func, processor, map_state):
                nonlocal result_processor
                result_processor = processor
                # Return a mock result
                return processor((3, 4), 'weaponcrafting_workshop', {})
            
            self.action.unified_search = capture_result_processor
            
            # Execute the action
            result = self.action.execute(self.client, context)
            
            # Restore original method
            self.action.unified_search = original_unified_search
        
        # Verify the result processor was captured and result is correct
        self.assertIsNotNone(result_processor)
        self.assertTrue(result.success)
        
        # Verify distance calculation (from 0,0 to 3,4 = distance 5)
        self.assertEqual(result.data['distance'], 5.0)


if __name__ == '__main__':
    unittest.main()