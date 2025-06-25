"""Test module for FindResourcesAction."""

import unittest
from unittest.mock import Mock, patch
from src.controller.actions.find_resources import FindResourcesAction


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
        self.mock_client = Mock()

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
        self.assertEqual(action.search_radius, 10)
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

    @patch('src.controller.actions.find_resources.FindResourcesAction._search_radius_for_resources')
    def test_execute_no_resources_found(self, mock_search_radius):
        """Test finding resources when none are found."""
        mock_search_radius.return_value = []
        
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn(f'No resources found within radius {self.search_radius}', result['error'])

    @patch('src.controller.actions.find_resources.FindResourcesAction._search_radius_for_resources')
    def test_execute_resources_found_specific_types(self, mock_search_radius):
        """Test finding resources with specific resource types."""
        # Mock finding resources at radius 2
        mock_search_radius.side_effect = [
            [],  # radius 1
            [((7, 5), 'copper')],  # radius 2
            []   # radius 3 (shouldn't be called)
        ]
        
        result = self.action.execute(self.mock_client)
        self.assertTrue(result['success'])
        self.assertEqual(result['location'], (7, 5))
        self.assertEqual(result['resource_code'], 'copper')
        self.assertAlmostEqual(result['distance'], 2.828, places=2)

    @patch('src.controller.actions.find_resources.FindResourcesAction._search_radius_for_resources')
    def test_execute_resources_found_default_types(self, mock_search_radius):
        """Test finding resources with default resource types."""
        action = FindResourcesAction(character_x=5, character_y=3, search_radius=2)
        
        # Mock finding resources at radius 1
        mock_search_radius.side_effect = [
            [((6, 3), 'ash_wood')]  # radius 1
        ]
        
        result = action.execute(self.mock_client)
        self.assertTrue(result['success'])
        self.assertEqual(result['location'], (6, 3))
        self.assertEqual(result['resource_code'], 'ash_wood')
        self.assertEqual(result['distance'], 1.0)

    @patch('src.controller.actions.find_resources.FindResourcesAction._search_radius_for_resources')
    def test_execute_multiple_resources_closest_selected(self, mock_search_radius):
        """Test finding resources selects closest when multiple found."""
        # Mock finding multiple resources at radius 2
        # Distance from (5,3) to (7,5) = sqrt((7-5)^2 + (5-3)^2) = sqrt(4+4) = 2.83
        # Distance from (5,3) to (4,4) = sqrt((4-5)^2 + (4-3)^2) = sqrt(1+1) = 1.41
        mock_search_radius.side_effect = [
            [],  # radius 1
            [((7, 5), 'copper'), ((4, 4), 'iron_ore')]  # radius 2 - (4,4) is closer
        ]
        
        result = self.action.execute(self.mock_client)
        self.assertTrue(result['success'])
        self.assertEqual(result['location'], (4, 4))  # Closer location
        self.assertEqual(result['resource_code'], 'iron_ore')

    @patch('src.controller.actions.find_resources.FindResourcesAction._search_radius_for_resources')
    def test_execute_exception_handling(self, mock_search_radius):
        """Test exception handling during resource search."""
        mock_search_radius.side_effect = Exception("Network error")
        
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn('Resource search failed: Network error', result['error'])

    @patch('src.controller.actions.find_resources.get_map_api')
    def test_search_radius_for_resources_success(self, mock_get_map_api):
        """Test _search_radius_for_resources finds resources."""
        # Mock map response with resource
        mock_content = Mock()
        mock_content.type_ = 'resource'
        mock_content.code = 'copper'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map_api.return_value = mock_map_response
        
        target_codes = ['copper', 'iron_ore']
        result = self.action._search_radius_for_resources(self.mock_client, target_codes, 1)
        
        # Should find resources at radius 1 coordinates
        self.assertTrue(len(result) > 0)
        # Check that at least one result has the expected resource
        found_copper = any(resource_code == 'copper' for location, resource_code in result)
        self.assertTrue(found_copper)

    @patch('src.controller.actions.find_resources.get_map_api')
    def test_search_radius_for_resources_no_content(self, mock_get_map_api):
        """Test _search_radius_for_resources with no content."""
        # Mock map response with no content
        mock_map_data = Mock()
        mock_map_data.content = None
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map_api.return_value = mock_map_response
        
        target_codes = ['copper']
        result = self.action._search_radius_for_resources(self.mock_client, target_codes, 1)
        
        self.assertEqual(len(result), 0)

    @patch('src.controller.actions.find_resources.get_map_api')
    def test_search_radius_for_resources_wrong_type(self, mock_get_map_api):
        """Test _search_radius_for_resources with wrong content type."""
        # Mock map response with wrong content type
        mock_content = Mock()
        mock_content.type_ = 'workshop'
        mock_content.code = 'copper'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map_api.return_value = mock_map_response
        
        target_codes = ['copper']
        result = self.action._search_radius_for_resources(self.mock_client, target_codes, 1)
        
        self.assertEqual(len(result), 0)

    @patch('src.controller.actions.find_resources.get_map_api')
    def test_search_radius_for_resources_wrong_code(self, mock_get_map_api):
        """Test _search_radius_for_resources with wrong resource code."""
        # Mock map response with wrong resource code
        mock_content = Mock()
        mock_content.type_ = 'resource'
        mock_content.code = 'gold_ore'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map_api.return_value = mock_map_response
        
        target_codes = ['copper']
        result = self.action._search_radius_for_resources(self.mock_client, target_codes, 1)
        
        self.assertEqual(len(result), 0)

    @patch('src.controller.actions.find_resources.get_map_api')
    def test_search_radius_for_resources_api_fails(self, mock_get_map_api):
        """Test _search_radius_for_resources handles API failures."""
        mock_get_map_api.return_value = None
        
        target_codes = ['copper']
        result = self.action._search_radius_for_resources(self.mock_client, target_codes, 1)
        
        self.assertEqual(len(result), 0)

    @patch('src.controller.actions.find_resources.get_map_api')
    def test_search_radius_for_resources_api_exception(self, mock_get_map_api):
        """Test _search_radius_for_resources handles API exceptions."""
        mock_get_map_api.side_effect = Exception("API error")
        
        target_codes = ['copper']
        result = self.action._search_radius_for_resources(self.mock_client, target_codes, 1)
        
        # Should return empty list, not raise exception
        self.assertEqual(len(result), 0)

    @patch('src.controller.actions.find_resources.FindResourcesAction._search_radius_for_workshops')
    def test_find_workshops_success(self, mock_search_workshops):
        """Test find_workshops method successfully finds workshops."""
        # Mock finding workshops at radius 2
        mock_search_workshops.side_effect = [
            [],  # radius 1
            [((8, 6), 'weapon_workshop')],  # radius 2
        ]
        
        result = self.action.find_workshops(self.mock_client, 'weapon')
        
        self.assertIsNotNone(result)
        self.assertEqual(result['location'], (8, 6))
        self.assertEqual(result['workshop_code'], 'weapon_workshop')
        self.assertEqual(result['workshop_type'], 'weapon')
        self.assertAlmostEqual(result['distance'], 4.24, places=1)

    @patch('src.controller.actions.find_resources.FindResourcesAction._search_radius_for_workshops')
    def test_find_workshops_none_found(self, mock_search_workshops):
        """Test find_workshops method when no workshops found."""
        mock_search_workshops.return_value = []
        
        result = self.action.find_workshops(self.mock_client)
        
        self.assertIsNone(result)

    @patch('src.controller.actions.find_resources.FindResourcesAction._search_radius_for_workshops')
    def test_find_workshops_multiple_found_closest_selected(self, mock_search_workshops):
        """Test find_workshops selects closest when multiple found."""
        # Mock finding multiple workshops at radius 1
        mock_search_workshops.side_effect = [
            [((4, 3), 'cooking_workshop'), ((6, 3), 'weapon_workshop')]  # radius 1
        ]
        
        result = self.action.find_workshops(self.mock_client)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['location'], (4, 3))  # Closer location
        self.assertEqual(result['workshop_code'], 'cooking_workshop')

    @patch('src.controller.actions.find_resources.get_map_api')
    def test_search_radius_for_workshops_success(self, mock_get_map_api):
        """Test _search_radius_for_workshops finds workshops."""
        # Mock map response with workshop
        mock_content = Mock()
        mock_content.type_ = 'workshop'
        mock_content.code = 'weapon_workshop'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map_api.return_value = mock_map_response
        
        result = self.action._search_radius_for_workshops(self.mock_client, 1, 'weapon')
        
        # Should find workshops at radius 1 coordinates
        self.assertTrue(len(result) > 0)
        # Check that at least one result has the expected workshop
        found_weapon = any('weapon_workshop' in workshop_code for location, workshop_code in result)
        self.assertTrue(found_weapon)

    @patch('src.controller.actions.find_resources.get_map_api')
    def test_search_radius_for_workshops_no_type_filter(self, mock_get_map_api):
        """Test _search_radius_for_workshops without type filter."""
        # Mock map response with workshop
        mock_content = Mock()
        mock_content.type_ = 'workshop'
        mock_content.code = 'any_workshop'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map_api.return_value = mock_map_response
        
        result = self.action._search_radius_for_workshops(self.mock_client, 1, None)
        
        # Should find any workshop when no type filter
        self.assertTrue(len(result) > 0)

    @patch('src.controller.actions.find_resources.get_map_api')
    def test_search_radius_for_workshops_type_mismatch(self, mock_get_map_api):
        """Test _search_radius_for_workshops with type mismatch."""
        # Mock map response with different workshop type
        mock_content = Mock()
        mock_content.type_ = 'workshop'
        mock_content.code = 'cooking_workshop'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map_api.return_value = mock_map_response
        
        result = self.action._search_radius_for_workshops(self.mock_client, 1, 'weapon')
        
        # Should not find workshop with wrong type
        self.assertEqual(len(result), 0)

    @patch('src.controller.actions.find_resources.get_map_api')
    def test_search_radius_for_workshops_no_content(self, mock_get_map_api):
        """Test _search_radius_for_workshops with no content."""
        # Mock map response with no content
        mock_map_data = Mock()
        mock_map_data.content = None
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map_api.return_value = mock_map_response
        
        result = self.action._search_radius_for_workshops(self.mock_client, 1, None)
        
        self.assertEqual(len(result), 0)

    @patch('src.controller.actions.find_resources.get_map_api')
    def test_search_radius_for_workshops_wrong_type(self, mock_get_map_api):
        """Test _search_radius_for_workshops with wrong content type."""
        # Mock map response with wrong content type
        mock_content = Mock()
        mock_content.type_ = 'resource'
        mock_content.code = 'copper'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map_api.return_value = mock_map_response
        
        result = self.action._search_radius_for_workshops(self.mock_client, 1, None)
        
        self.assertEqual(len(result), 0)

    @patch('src.controller.actions.find_resources.get_map_api')
    def test_search_radius_for_workshops_no_code_attribute(self, mock_get_map_api):
        """Test _search_radius_for_workshops with no code attribute."""
        # Mock map response with workshop but no code
        mock_content = Mock()
        mock_content.type_ = 'workshop'
        del mock_content.code
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map_api.return_value = mock_map_response
        
        result = self.action._search_radius_for_workshops(self.mock_client, 1, None)
        
        # Should still find workshop even without code, using empty string
        self.assertTrue(len(result) > 0)
        found_empty = any(workshop_code == '' for location, workshop_code in result)
        self.assertTrue(found_empty)

    @patch('src.controller.actions.find_resources.get_map_api')
    def test_search_radius_for_workshops_api_exception(self, mock_get_map_api):
        """Test _search_radius_for_workshops handles API exceptions."""
        mock_get_map_api.side_effect = Exception("API error")
        
        result = self.action._search_radius_for_workshops(self.mock_client, 1, None)
        
        # Should return empty list, not raise exception
        self.assertEqual(len(result), 0)


if __name__ == '__main__':
    unittest.main()