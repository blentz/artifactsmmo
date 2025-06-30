"""Test module for FindResourcesAction."""

import unittest
from unittest.mock import Mock, patch
from src.controller.actions.find_resources import FindResourcesAction
from test.fixtures import create_mock_client


class TestFindResourcesAction(unittest.TestCase):
    """Test cases for FindResourcesAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.character_x = 5
        self.character_y = 3
        self.search_radius = 3
        self.resource_types = ['copper', 'iron_ore']
        self.character_level = 10
        self.skill_type = 'mining'
        self.level_range = 5
        
        self.action = FindResourcesAction(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=self.search_radius,
            resource_types=self.resource_types,
            character_level=self.character_level,
            skill_type=self.skill_type,
            level_range=self.level_range
        )
        
        # Mock client
        self.mock_client = create_mock_client()

    def test_find_resources_action_initialization(self):
        """Test FindResourcesAction initialization with all parameters."""
        self.assertEqual(self.action.character_x, self.character_x)
        self.assertEqual(self.action.character_y, self.character_y)
        self.assertEqual(self.action.search_radius, self.search_radius)
        self.assertEqual(self.action.resource_types, self.resource_types)
        self.assertEqual(self.action.character_level, self.character_level)
        self.assertEqual(self.action.skill_type, self.skill_type)
        self.assertEqual(self.action.level_range, self.level_range)

    def test_find_resources_action_initialization_defaults(self):
        """Test FindResourcesAction initialization with default parameters."""
        action = FindResourcesAction()
        self.assertEqual(action.character_x, 0)
        self.assertEqual(action.character_y, 0)
        self.assertEqual(action.search_radius, 5)
        self.assertEqual(action.resource_types, [])
        self.assertIsNone(action.character_level)
        self.assertIsNone(action.skill_type)
        self.assertEqual(action.level_range, 5)

    def test_find_resources_action_initialization_none_resource_types(self):
        """Test FindResourcesAction initialization with None resource_types."""
        action = FindResourcesAction(resource_types=None)
        self.assertEqual(action.resource_types, [])

    def test_find_resources_action_repr_with_filters(self):
        """Test FindResourcesAction string representation with filters."""
        expected = (f"FindResourcesAction({self.character_x}, {self.character_y}, "
                   f"radius={self.search_radius}, types={self.resource_types}, "
                   f"skill={self.skill_type}, level={self.character_level})")
        self.assertEqual(repr(self.action), expected)

    def test_find_resources_action_repr_no_filters(self):
        """Test FindResourcesAction string representation without filters."""
        action = FindResourcesAction(character_x=1, character_y=2, search_radius=5)
        expected = "FindResourcesAction(1, 2, radius=5)"
        self.assertEqual(repr(action), expected)

    def test_find_resources_action_repr_partial_filters(self):
        """Test FindResourcesAction string representation with partial filters."""
        action = FindResourcesAction(character_x=1, character_y=2, search_radius=5, skill_type='mining')
        expected = "FindResourcesAction(1, 2, radius=5, skill=mining)"
        self.assertEqual(repr(action), expected)

    def test_execute_no_client(self):
        """Test finding resources fails without client."""
        result = self.action.execute(None)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    def test_execute_has_goap_attributes(self):
        """Test that FindResourcesAction has expected GOAP attributes."""
        self.assertTrue(hasattr(FindResourcesAction, 'conditions'))
        self.assertTrue(hasattr(FindResourcesAction, 'reactions'))
        self.assertTrue(hasattr(FindResourcesAction, 'weights'))
        self.assertTrue(hasattr(FindResourcesAction, 'g'))

    @patch('src.controller.actions.search_base.SearchActionBase.unified_search')
    def test_execute_no_resource_types(self, mock_unified_search):
        """Test finding resources fails without resource types."""
        # When no resource types are provided, the method will expand search and may use default types
        mock_unified_search.return_value = {
            'success': False,
            'error': 'No matching content found within radius 3'
        }
        
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn('error', result)

    @patch('src.controller.actions.search_base.SearchActionBase.unified_search')
    def test_execute_no_resources_found(self, mock_unified_search):
        """Test finding resources when none are found."""
        mock_unified_search.return_value = {
            'success': False,
            'error': f'No matching content found within radius {self.search_radius}'
        }
        
        result = self.action.execute(self.mock_client, resource_types=['copper'])
        self.assertFalse(result['success'])
        self.assertIn('error', result)

    @patch('src.controller.actions.search_base.SearchActionBase.unified_search')
    def test_execute_resources_found_specific_types(self, mock_unified_search):
        """Test finding resources with specific resource types."""
        mock_unified_search.return_value = {
            'success': True,
            'location': (7, 5),
            'resource_code': 'copper',
            'distance': 2.828
        }
        
        result = self.action.execute(self.mock_client, resource_types=['copper'])
        self.assertTrue(result['success'])
        self.assertEqual(result['location'], (7, 5))
        self.assertEqual(result['resource_code'], 'copper')
        self.assertAlmostEqual(result['distance'], 2.828, places=2)

    @patch('src.controller.actions.search_base.SearchActionBase.unified_search')
    def test_execute_resources_found_default_types(self, mock_unified_search):
        """Test finding resources with default resource types."""
        action = FindResourcesAction(character_x=5, character_y=3, search_radius=2)
        
        mock_unified_search.return_value = {
            'success': True,
            'location': (6, 3),
            'resource_code': 'ash_wood',
            'distance': 1.0
        }
        
        result = action.execute(self.mock_client, resource_types=['ash_wood'])
        self.assertTrue(result['success'])
        self.assertEqual(result['location'], (6, 3))
        self.assertEqual(result['resource_code'], 'ash_wood')
        self.assertEqual(result['distance'], 1.0)

    @patch('src.controller.actions.search_base.SearchActionBase.unified_search')
    def test_execute_multiple_resources_closest_selected(self, mock_unified_search):
        """Test finding resources selects closest when multiple found."""
        mock_unified_search.return_value = {
            'success': True,
            'location': (4, 4),
            'resource_code': 'iron_ore',
            'distance': 1.414
        }
        
        result = self.action.execute(self.mock_client, resource_types=['copper', 'iron_ore'])
        self.assertTrue(result['success'])
        self.assertEqual(result['location'], (4, 4))
        self.assertEqual(result['resource_code'], 'iron_ore')
        self.assertAlmostEqual(result['distance'], 1.414, places=2)

    @patch('src.controller.actions.search_base.SearchActionBase.unified_search')
    def test_execute_exception_handling(self, mock_unified_search):
        """Test exception handling during resource search."""
        mock_unified_search.side_effect = Exception("API Error")
        
        result = self.action.execute(self.mock_client, resource_types=['copper'])
        self.assertFalse(result['success'])
        self.assertIn('Resource search failed', result['error'])

    def test_determine_target_resource_codes_context_types(self):
        """Test _determine_target_resource_codes with context resource types."""
        result = self.action._determine_target_resource_codes(['copper_rocks'], [])
        self.assertEqual(result, ['copper_rocks'])

    def test_determine_target_resource_codes_materials_needed(self):
        """Test _determine_target_resource_codes with materials needed."""
        result = self.action._determine_target_resource_codes([], ['copper'])
        # Should use dynamic discovery to find copper_rocks that drops copper
        self.assertIsInstance(result, list)

    def test_determine_target_resource_codes_fallback(self):
        """Test _determine_target_resource_codes fallback to instance types."""
        action = FindResourcesAction(resource_types=['iron_ore'])
        result = action._determine_target_resource_codes([], [])
        self.assertEqual(result, ['iron_ore'])

    def test_determine_target_resource_codes_empty(self):
        """Test _determine_target_resource_codes with empty inputs and no knowledge base."""
        action = FindResourcesAction()
        # Without knowledge base, should return empty list
        result = action._determine_target_resource_codes([], [])
        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()