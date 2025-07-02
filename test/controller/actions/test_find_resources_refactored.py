"""Comprehensive unit tests for FindResourcesAction (refactored version)"""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.find_resources_refactored import FindResourcesAction
from test.fixtures import MockActionContext, create_mock_client


class TestFindResourcesAction(unittest.TestCase):
    """Test cases for FindResourcesAction class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = FindResourcesAction()
        self.mock_client = create_mock_client()
        self.character_name = "TestCharacter"
        
        # Create mock knowledge base
        self.mock_knowledge_base = Mock()
        self.mock_knowledge_base.data = {
            'resources': {
                'iron_ore': {
                    'code': 'iron_ore',
                    'name': 'Iron Ore',
                    'skill_required': 'mining',
                    'level_required': 5,
                    'last_seen_location': [10, 15]
                },
                'copper_ore': {
                    'code': 'copper_ore', 
                    'name': 'Copper Ore',
                    'skill_required': 'mining',
                    'level_required': 1
                    # No location data
                }
            }
        }
        
        # Create mock map state
        self.mock_map_state = Mock()
        self.mock_map_state.data = {
            '5,8': {
                'x': 5,
                'y': 8,
                'content': {
                    'type': 'resource',
                    'code': 'ash_wood',
                    'skill': 'woodcutting',
                    'level': 3
                }
            },
            '12,20': {
                'x': 12,
                'y': 20,
                'content': {
                    'type': 'resource',
                    'code': 'iron_ore',
                    'skill': 'mining',
                    'level': 5
                }
            }
        }
    
    
    def test_determine_target_resource_codes_with_types(self):
        """Test target resource code determination with provided types."""
        resource_types = ['iron_ore', 'copper_ore']
        result = self.action._determine_target_resource_codes(resource_types)
        
        self.assertEqual(result, ['iron_ore', 'copper_ore'])
    
    def test_determine_target_resource_codes_empty(self):
        """Test target resource code determination with no types."""
        result = self.action._determine_target_resource_codes([])
        
        self.assertEqual(result, [])
    
    def test_find_closest_kb_resource_with_location(self):
        """Test finding closest knowledge base resource with location data."""
        kb_results = [
            {
                'code': 'iron_ore',
                'data': {
                    'last_seen_location': [10, 15],
                    'skill_required': 'mining'
                }
            },
            {
                'code': 'gold_ore',
                'data': {
                    'last_seen_location': [20, 25],
                    'skill_required': 'mining'
                }
            }
        ]
        
        result = self.action._find_closest_kb_resource(kb_results, 12, 17)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['code'], 'iron_ore')  # Closer to (12,17) than gold_ore
        self.assertEqual(result['location'], (10, 15))
    
    def test_find_closest_kb_resource_no_location(self):
        """Test finding closest resource when no location data available."""
        kb_results = [
            {
                'code': 'copper_ore',
                'data': {
                    'skill_required': 'mining'
                    # No last_seen_location
                }
            }
        ]
        
        result = self.action._find_closest_kb_resource(kb_results, 10, 10)
        
        self.assertIsNone(result)
    
    def test_find_closest_kb_resource_invalid_location(self):
        """Test finding closest resource with invalid location data."""
        kb_results = [
            {
                'code': 'bad_ore',
                'data': {
                    'last_seen_location': [10],  # Invalid - only one coordinate
                    'skill_required': 'mining'
                }
            }
        ]
        
        result = self.action._find_closest_kb_resource(kb_results, 10, 10)
        
        self.assertIsNone(result)
    
    def test_calculate_distance(self):
        """Test Manhattan distance calculation."""
        # Distance from (0,0) to (3,4) should be 7
        distance = self.action._calculate_distance(3, 4, 0, 0)
        self.assertEqual(distance, 7)
        
        # Distance from (10,15) to (12,17) should be 4
        distance = self.action._calculate_distance(10, 15, 12, 17)
        self.assertEqual(distance, 4)
    
    def test_format_resource_response_knowledge_base(self):
        """Test formatting resource response from knowledge base source."""
        resource_info = {
            'location': (10, 15),
            'code': 'iron_ore',
            'data': {
                'name': 'Iron Ore',
                'skill_required': 'mining',
                'level_required': 5
            }
        }
        
        result = self.action._format_resource_response(
            resource_info, 'knowledge_base', 12, 17
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['location'], (10, 15))
        self.assertEqual(result['distance'], 4)  # Manhattan distance
        self.assertEqual(result['resource_code'], 'iron_ore')
        self.assertEqual(result['resource_name'], 'Iron Ore')
        self.assertEqual(result['resource_skill'], 'mining')
        self.assertEqual(result['resource_level'], 5)
        self.assertEqual(result['source'], 'knowledge_base')
        self.assertEqual(result['target_x'], 10)
        self.assertEqual(result['target_y'], 15)
    
    def test_format_resource_response_map_state(self):
        """Test formatting resource response from map state source."""
        resource_info = {
            'location': (5, 8),
            'code': 'ash_wood',
            'content': {
                'skill': 'woodcutting',
                'level': 3
            },
            'data': {
                'name': 'Ash Wood'
            }
        }
        
        result = self.action._format_resource_response(
            resource_info, 'map_state', 0, 0
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['resource_skill'], 'woodcutting')  # From content
        self.assertEqual(result['resource_level'], 3)  # From content
        self.assertEqual(result['source'], 'map_state')
    
    def test_create_resource_filter_basic(self):
        """Test creating basic resource filter."""
        filter_func = self.action.create_resource_filter()
        
        # Should accept any resource
        resource_data = {'type': 'resource', 'code': 'iron_ore'}
        self.assertTrue(filter_func(resource_data, 0, 0))
        
        # Should reject non-resources
        non_resource_data = {'type': 'monster', 'code': 'goblin'}
        self.assertFalse(filter_func(non_resource_data, 0, 0))
    
    def test_create_resource_filter_with_resource_types(self):
        """Test creating resource filter with specific resource types."""
        filter_func = self.action.create_resource_filter(
            resource_types=['iron_ore', 'copper_ore']
        )
        
        # Should accept specified resources
        iron_data = {'type': 'resource', 'code': 'iron_ore'}
        self.assertTrue(filter_func(iron_data, 0, 0))
        
        # Should reject other resources
        gold_data = {'type': 'resource', 'code': 'gold_ore'}
        self.assertFalse(filter_func(gold_data, 0, 0))
    
    def test_create_resource_filter_with_skill_type(self):
        """Test creating resource filter with skill type."""
        filter_func = self.action.create_resource_filter(skill_type='mining')
        
        # Should accept mining resources
        mining_data = {'type': 'resource', 'code': 'iron_ore', 'skill': 'mining'}
        self.assertTrue(filter_func(mining_data, 0, 0))
        
        # Should reject non-mining resources
        woodcut_data = {'type': 'resource', 'code': 'ash_wood', 'skill': 'woodcutting'}
        self.assertFalse(filter_func(woodcut_data, 0, 0))
    
    def test_create_resource_filter_with_character_level(self):
        """Test creating resource filter with character level."""
        filter_func = self.action.create_resource_filter(character_level=10)
        
        # Should accept resources within level range (5 levels)
        appropriate_data = {'type': 'resource', 'code': 'iron_ore', 'level': 8}
        self.assertTrue(filter_func(appropriate_data, 0, 0))
        
        # Should reject resources too far from character level
        high_level_data = {'type': 'resource', 'code': 'diamond_ore', 'level': 20}
        self.assertFalse(filter_func(high_level_data, 0, 0))
    
    def test_create_resource_filter_type_underscore(self):
        """Test resource filter with type_ instead of type."""
        filter_func = self.action.create_resource_filter()
        
        # Should work with type_ attribute
        resource_data = {'type_': 'resource', 'code': 'iron_ore'}
        self.assertTrue(filter_func(resource_data, 0, 0))
    
    def test_perform_action_no_target_codes(self):
        """Test perform_action with no target resource codes."""
        context = MockActionContext(
            character_name=self.character_name,
            character_x=10,
            character_y=10,
            resource_types=[],  # Empty list
            knowledge_base=self.mock_knowledge_base,
            map_state=self.mock_map_state
        )
        
        result = self.action.perform_action(self.mock_client, context)
        
        self.assertFalse(result['success'])
        self.assertIn('No target resource types specified', result['error'])
    
    def test_perform_action_knowledge_base_hit(self):
        """Test perform_action finding resource in knowledge base."""
        # Mock the search_knowledge_base_resources method
        with patch.object(self.action, 'search_knowledge_base_resources') as mock_search:
            mock_search.return_value = [
                {
                    'code': 'iron_ore',
                    'data': {
                        'name': 'Iron Ore',
                        'skill_required': 'mining',
                        'level_required': 5,
                        'last_seen_location': [10, 15]
                    }
                }
            ]
            
            context = MockActionContext(
                character_name=self.character_name,
                character_x=12,
                character_y=17,
                resource_types=['iron_ore'],
                knowledge_base=self.mock_knowledge_base,
                map_state=self.mock_map_state
            )
            
            result = self.action.perform_action(self.mock_client, context)
            
            self.assertTrue(result['success'])
            self.assertEqual(result['source'], 'knowledge_base')
            self.assertEqual(result['resource_code'], 'iron_ore')
            self.assertEqual(result['distance'], 4)
    
    def test_perform_action_map_state_hit(self):
        """Test perform_action finding resource in map state."""
        # Mock empty knowledge base search
        with patch.object(self.action, 'search_knowledge_base_resources', return_value=[]):
            with patch.object(self.action, 'search_map_state_for_content') as mock_map_search:
                mock_map_search.return_value = [
                    {
                        'location': (5, 8),
                        'code': 'ash_wood',
                        'content': {
                            'skill': 'woodcutting',
                            'level': 3
                        }
                    }
                ]
                
                context = MockActionContext(
                    character_name=self.character_name,
                    character_x=0,
                    character_y=0,
                    resource_types=['ash_wood'],
                    knowledge_base=self.mock_knowledge_base,
                    map_state=self.mock_map_state
                )
                
                result = self.action.perform_action(self.mock_client, context)
                
                self.assertTrue(result['success'])
                self.assertEqual(result['source'], 'map_state')
                self.assertEqual(result['resource_code'], 'ash_wood')
    
    def test_perform_action_api_fallback(self):
        """Test perform_action falling back to API search."""
        # Mock empty knowledge base and map state searches
        with patch.object(self.action, 'search_knowledge_base_resources', return_value=[]):
            with patch.object(self.action, 'search_map_state_for_content', return_value=[]):
                with patch.object(self.action, 'unified_search') as mock_unified:
                    mock_unified.return_value = {
                        'success': True,
                        'source': 'api_search',
                        'resource_code': 'iron_ore'
                    }
                    
                    context = MockActionContext(
                        character_name=self.character_name,
                        character_x=10,
                        character_y=10,
                        resource_types=['iron_ore'],
                        search_radius=5,
                        character_level=10,
                        skill_type='mining',
                        knowledge_base=self.mock_knowledge_base,
                        map_state=self.mock_map_state
                    )
                    
                    result = self.action.perform_action(self.mock_client, context)
                    
                    self.assertTrue(result['success'])
                    self.assertEqual(result['source'], 'api_search')
                    
                    # Verify unified_search was called with correct parameters
                    mock_unified.assert_called_once()
                    args = mock_unified.call_args
                    self.assertEqual(args[0][1], 10)  # character_x
                    self.assertEqual(args[0][2], 10)  # character_y
                    self.assertEqual(args[0][3], 5)   # search_radius
    
    def test_perform_action_with_optional_parameters(self):
        """Test perform_action with various optional parameters."""
        context = MockActionContext(
            character_name=self.character_name,
            character_x=5,
            character_y=8,
            resource_types=['iron_ore'],
            search_radius=10,
            character_level=15,
            skill_type='mining',
            level_range=3,
            knowledge_base=None,  # No knowledge base
            map_state=None       # No map state
        )
        
        with patch.object(self.action, 'unified_search') as mock_unified:
            mock_unified.return_value = {'success': False, 'error': 'Not found'}
            
            result = self.action.perform_action(self.mock_client, context)
            
            # Should skip knowledge base and map state searches
            # and go straight to API search
            mock_unified.assert_called_once()
    
    def test_resource_result_processor_function(self):
        """Test that the resource result processor function works correctly."""
        # This test verifies the lambda function created in perform_action
        context = MockActionContext(
            character_name=self.character_name,
            character_x=10,
            character_y=10,
            resource_types=['iron_ore'],
            knowledge_base=None,
            map_state=None
        )
        
        with patch.object(self.action, 'unified_search') as mock_unified:
            # Capture the result processor function
            mock_unified.return_value = {'success': True}
            
            self.action.perform_action(self.mock_client, context)
            
            # Get the result processor function from the call
            call_args = mock_unified.call_args
            result_processor = call_args[0][5]  # 6th argument (0-indexed)
            
            # Test the processor function
            test_result = result_processor(
                location=(15, 20),
                content_code='iron_ore',
                content_data={'name': 'Iron Ore', 'skill': 'mining', 'level': 5}
            )
            
            self.assertTrue(test_result['success'])
            self.assertEqual(test_result['source'], 'api_search')
            self.assertEqual(test_result['target_x'], 15)
            self.assertEqual(test_result['target_y'], 20)
    
    def test_perform_action_multiple_resource_types_map_state(self):
        """Test perform_action with multiple resource types checking map state."""
        with patch.object(self.action, 'search_knowledge_base_resources', return_value=[]):
            with patch.object(self.action, 'search_map_state_for_content') as mock_map_search:
                # First resource type returns nothing, second returns results
                mock_map_search.side_effect = [[], [{'location': (5, 8), 'code': 'ash_wood'}]]
                
                context = MockActionContext(
                    character_name=self.character_name,
                    character_x=0,
                    character_y=0,
                    resource_types=['iron_ore', 'ash_wood'],
                    knowledge_base=self.mock_knowledge_base,
                    map_state=self.mock_map_state
                )
                
                result = self.action.perform_action(self.mock_client, context)
                
                self.assertTrue(result['success'])
                self.assertEqual(result['source'], 'map_state')
                
                # Should have called search twice - once for each resource type
                self.assertEqual(mock_map_search.call_count, 2)
    
    def test_perform_action_context_defaults(self):
        """Test perform_action uses context defaults for missing parameters."""
        context = MockActionContext(
            character_name=self.character_name,
            # Missing character_x, character_y - should use context defaults
            resource_types=['iron_ore'],
            knowledge_base=None,
            map_state=None
        )
        # Set context defaults
        context.character_x = 25
        context.character_y = 30
        
        with patch.object(self.action, 'unified_search') as mock_unified:
            mock_unified.return_value = {'success': False}
            
            self.action.perform_action(self.mock_client, context)
            
            # Verify unified_search was called with context defaults
            args = mock_unified.call_args[0]
            self.assertEqual(args[1], 25)  # character_x from context
            self.assertEqual(args[2], 30)  # character_y from context


if __name__ == '__main__':
    unittest.main()