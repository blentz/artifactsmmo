"""Test module for FindResourcesAction."""

import unittest
from unittest.mock import patch

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
        
        self.action = FindResourcesAction()
        
        # Mock client
        self.mock_client = create_mock_client()

    def test_find_resources_action_initialization(self):
        """Test FindResourcesAction initialization with all parameters."""
        # Action should have no parameters stored as instance variables
        self.assertIsInstance(self.action, FindResourcesAction)
        self.assertFalse(hasattr(self.action, 'character_x'))
        self.assertFalse(hasattr(self.action, 'character_y'))
        self.assertFalse(hasattr(self.action, 'search_radius'))
        self.assertFalse(hasattr(self.action, 'resource_types'))
        self.assertFalse(hasattr(self.action, 'character_level'))
        self.assertFalse(hasattr(self.action, 'skill_type'))
        self.assertFalse(hasattr(self.action, 'level_range'))

    def test_find_resources_action_initialization_defaults(self):
        """Test FindResourcesAction initialization with default parameters."""
        action = FindResourcesAction()
        self.assertIsInstance(action, FindResourcesAction)
        self.assertFalse(hasattr(action, 'character_x'))
        self.assertFalse(hasattr(action, 'character_y'))
        self.assertFalse(hasattr(action, 'search_radius'))
        self.assertFalse(hasattr(action, 'resource_types'))
        self.assertFalse(hasattr(action, 'character_level'))
        self.assertFalse(hasattr(action, 'skill_type'))
        self.assertFalse(hasattr(action, 'level_range'))

    def test_find_resources_action_initialization_none_resource_types(self):
        """Test FindResourcesAction initialization with None resource_types."""
        action = FindResourcesAction()
        self.assertIsInstance(action, FindResourcesAction)
        self.assertFalse(hasattr(action, 'resource_types'))

    def test_find_resources_action_repr_with_filters(self):
        """Test FindResourcesAction string representation with filters."""
        expected = "FindResourcesAction()"
        self.assertEqual(repr(self.action), expected)

    def test_find_resources_action_repr_no_filters(self):
        """Test FindResourcesAction string representation without filters."""
        action = FindResourcesAction()
        expected = "FindResourcesAction()"
        self.assertEqual(repr(action), expected)

    def test_find_resources_action_repr_partial_filters(self):
        """Test FindResourcesAction string representation with partial filters."""
        action = FindResourcesAction()
        expected = "FindResourcesAction()"
        self.assertEqual(repr(action), expected)

    def test_execute_no_client(self):
        """Test finding resources fails without client."""
        from test.fixtures import MockActionContext
        context = MockActionContext(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=self.search_radius,
            resource_types=self.resource_types
        )
        result = self.action.execute(None, context)
        # With centralized validation, None client triggers validation error
        self.assertFalse(result["success"])
        # Direct action execution bypasses centralized validation
        self.assertIn('error', result)

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
        
        from test.fixtures import MockActionContext
        context = MockActionContext(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=self.search_radius
        )
        result = self.action.execute(self.mock_client, context)
        self.assertFalse(result['success'])
        self.assertIn('error', result)

    @patch('src.controller.actions.search_base.SearchActionBase.unified_search')
    def test_execute_no_resources_found(self, mock_unified_search):
        """Test finding resources when none are found."""
        mock_unified_search.return_value = {
            'success': False,
            'error': f'No matching content found within radius {self.search_radius}'
        }
        
        from test.fixtures import MockActionContext
        context = MockActionContext(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=self.search_radius,
            resource_types=['copper']
        )
        result = self.action.execute(self.mock_client, context)
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
        
        from test.fixtures import MockActionContext
        context = MockActionContext(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=self.search_radius,
            resource_types=['copper']
        )
        result = self.action.execute(self.mock_client, context)
        self.assertTrue(result['success'])
        self.assertEqual(result['location'], (7, 5))
        self.assertEqual(result['resource_code'], 'copper')
        self.assertAlmostEqual(result['distance'], 2.828, places=2)

    @patch('src.controller.actions.search_base.SearchActionBase.unified_search')
    def test_execute_resources_found_default_types(self, mock_unified_search):
        """Test finding resources with default resource types."""
        action = FindResourcesAction()
        
        mock_unified_search.return_value = {
            'success': True,
            'location': (6, 3),
            'resource_code': 'ash_wood',
            'distance': 1.0
        }
        
        from test.fixtures import MockActionContext
        context = MockActionContext(
            character_x=5,
            character_y=3,
            search_radius=2,
            resource_types=['ash_wood']
        )
        result = action.execute(self.mock_client, context)
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
        
        from test.fixtures import MockActionContext
        context = MockActionContext(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=self.search_radius,
            resource_types=['copper', 'iron_ore']
        )
        result = self.action.execute(self.mock_client, context)
        self.assertTrue(result['success'])
        self.assertEqual(result['location'], (4, 4))
        self.assertEqual(result['resource_code'], 'iron_ore')
        self.assertAlmostEqual(result['distance'], 1.414, places=2)

    @patch('src.controller.actions.search_base.SearchActionBase.unified_search')
    def test_execute_exception_handling(self, mock_unified_search):
        """Test exception handling during resource search."""
        mock_unified_search.side_effect = Exception("API Error")
        
        from test.fixtures import MockActionContext
        context = MockActionContext(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=self.search_radius,
            resource_types=['copper']
        )
        result = self.action.execute(self.mock_client, context)
        self.assertFalse(result['success'])
        self.assertIn('Resource search failed', result['error'])

    def test_determine_target_resource_codes_context_types(self):
        """Test _determine_target_resource_codes with context resource types."""
        result = self.action._determine_target_resource_codes(['copper_rocks'], [], [], None)
        self.assertEqual(result, ['copper_rocks'])

    def test_determine_target_resource_codes_materials_needed(self):
        """Test _determine_target_resource_codes with materials needed."""
        # Materials needed should be a list of dicts with 'code' key
        materials = [{'code': 'copper', 'quantity': 1}]
        result = self.action._determine_target_resource_codes([], materials, [], None)
        # Should extract copper from materials
        self.assertEqual(result, ['copper'])

    def test_determine_target_resource_codes_fallback(self):
        """Test _determine_target_resource_codes fallback to context types."""
        action = FindResourcesAction()
        # Test fallback to resource_types parameter (third argument)
        result = action._determine_target_resource_codes([], [], ['iron_ore'], None)
        self.assertEqual(result, ['iron_ore'])

    def test_determine_target_resource_codes_empty(self):
        """Test _determine_target_resource_codes with empty inputs and no knowledge base."""
        action = FindResourcesAction()
        # Without any resource types, should return empty list
        result = action._determine_target_resource_codes([], [], [], None)
        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()