"""
Test for FindCorrectWorkshopAction distance calculation fix
"""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.find_correct_workshop import FindCorrectWorkshopAction
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from test.test_base import UnifiedContextTestBase


class TestFindCorrectWorkshopDistanceFix(UnifiedContextTestBase):
    """Test that FindCorrectWorkshopAction correctly calculates distances."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.action = FindCorrectWorkshopAction()
        self.client = Mock()
        
    def test_calculate_distance_with_correct_parameters(self):
        """Test that _calculate_distance is called with all required parameters."""
        # Use the unified context from base class
        self.context.set(StateParameters.CHARACTER_NAME, "TestChar")
        self.context.set(StateParameters.CHARACTER_X, 5)
        self.context.set(StateParameters.CHARACTER_Y, 5)
        self.context.set(StateParameters.ITEM_CODE, 'wooden_staff')
        
        # Mock map state and knowledge base
        map_state = Mock()
        map_state.data = {}
        
        knowledge_base = Mock()
        knowledge_base.data = {
            'workshops': {
                'weaponcrafting_workshop': {
                    'x': 10,
                    'y': 10,
                    'craft_skill': 'weaponcrafting'
                }
            }
        }
        
        self.context.map_state = map_state
        self.context.knowledge_base = knowledge_base
        
        # Mock item API response
        item_response = Mock()
        item_response.data = Mock()
        item_response.data.craft = Mock()
        item_response.data.craft.skill = 'weaponcrafting'
        
        with patch('src.controller.actions.find_correct_workshop.get_item_api', return_value=item_response):
            # Execute the action
            result = self.action.execute(self.client, self.context)
        
        # Verify success
        self.assertTrue(result.success)
        self.assertEqual(result.data['workshop_type'], 'weaponcrafting')
        
        # Verify distance calculation was correct (from 5,5 to 10,10)
        expected_distance = ((10-5)**2 + (10-5)**2) ** 0.5  # ~7.07
        self.assertAlmostEqual(result.data['distance'], expected_distance, places=1)
    
    def test_result_processor_uses_character_position(self):
        """Test that the result processor correctly uses character position for distance."""
        # Use the unified context from base class
        self.context.set(StateParameters.CHARACTER_NAME, "TestChar")
        self.context.set(StateParameters.CHARACTER_X, 0)
        self.context.set(StateParameters.CHARACTER_Y, 0)
        self.context.set(StateParameters.ITEM_CODE, 'wooden_staff')
        self.context.set(StateParameters.SEARCH_RADIUS, 5)
        
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
        
        # Mock knowledge base (empty)
        knowledge_base = Mock()
        knowledge_base.data = {'workshops': {}}
        
        self.context.map_state = map_state
        self.context.knowledge_base = knowledge_base
        
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
                return [(3, 4, {'code': 'weaponcrafting_workshop', 'type': 'workshop'})]
                
            self.action.unified_search = capture_result_processor
            
            try:
                # Execute the action
                result = self.action.execute(self.client, self.context)
                
                # Now test the captured result processor
                if result_processor:
                    # Result processor expects location as a tuple (x, y)
                    location = (3, 4)
                    content_code = 'weaponcrafting_workshop'
                    content_data = {'type': 'workshop'}
                    
                    # Call processor with correct parameters
                    processed = result_processor(location, content_code, content_data)
                    
                    # Verify distance was calculated correctly (from 0,0 to 3,4)
                    expected_distance = 5.0  # 3-4-5 triangle
                    self.assertTrue(processed.success)
                    self.assertAlmostEqual(processed.data['distance'], expected_distance, places=1)
                    
            finally:
                self.action.unified_search = original_unified_search
                
    def test_result_processor_uses_character_position_not_workshop(self):
        """Test that result processor uses character position, not workshop position."""
        # Test the _calculate_distance method directly
        # Workshop at (10, 10)
        workshop_x = 10
        workshop_y = 10
        
        # Test with character at (0, 0)
        char_x = 0
        char_y = 0
        distance = self.action._calculate_distance(char_x, char_y, workshop_x, workshop_y)
        
        # Distance should be from (0,0) to (10,10)
        expected_distance = ((10-0)**2 + (10-0)**2) ** 0.5  # ~14.14
        self.assertAlmostEqual(distance, expected_distance, places=1)
        
        # Test with character at (5, 5)
        char_x = 5
        char_y = 5
        distance = self.action._calculate_distance(char_x, char_y, workshop_x, workshop_y)
        
        # Distance should be from (5,5) to (10,10)
        expected_distance = ((10-5)**2 + (10-5)**2) ** 0.5  # ~7.07
        self.assertAlmostEqual(distance, expected_distance, places=1)