"""Test module for GatherResourcesAction."""

import unittest
from unittest.mock import Mock, patch
from src.controller.actions.gather_resources import GatherResourcesAction


class TestGatherResourcesAction(unittest.TestCase):
    """Test cases for GatherResourcesAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.character_name = "TestCharacter"
        self.target_resource = "copper"
        self.action = GatherResourcesAction(self.character_name, self.target_resource)
        
        # Mock client
        self.mock_client = Mock()
        
        # Mock character response
        self.mock_character_data = Mock()
        self.mock_character_data.x = 5
        self.mock_character_data.y = 3
        
        self.mock_character_response = Mock()
        self.mock_character_response.data = self.mock_character_data
        self.mock_client._character_cache = self.mock_character_response

    def test_gather_resources_action_initialization(self):
        """Test GatherResourcesAction initialization."""
        self.assertEqual(self.action.character_name, self.character_name)
        self.assertEqual(self.action.target_resource, self.target_resource)

    def test_gather_resources_action_initialization_no_target(self):
        """Test GatherResourcesAction initialization without target resource."""
        action = GatherResourcesAction(self.character_name)
        self.assertEqual(action.character_name, self.character_name)
        self.assertIsNone(action.target_resource)

    def test_gather_resources_action_repr_with_target(self):
        """Test GatherResourcesAction string representation with target."""
        expected = f"GatherResourcesAction({self.character_name}, target={self.target_resource})"
        self.assertEqual(repr(self.action), expected)

    def test_gather_resources_action_repr_no_target(self):
        """Test GatherResourcesAction string representation without target."""
        action = GatherResourcesAction(self.character_name)
        expected = f"GatherResourcesAction({self.character_name})"
        self.assertEqual(repr(action), expected)

    def test_execute_no_client(self):
        """Test gathering fails without client."""
        result = self.action.execute(None)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    def test_execute_no_character_cache(self):
        """Test gathering fails without character data."""
        mock_client = Mock()
        mock_client._character_cache = None
        
        result = self.action.execute(mock_client)
        self.assertFalse(result['success'])
        self.assertIn('No character data or position available', result['error'])

    @patch('src.controller.actions.gather_resources.get_map_api')
    def test_execute_map_api_fails(self, mock_get_map_api):
        """Test gathering fails when map API fails."""
        mock_get_map_api.return_value = None
        
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn('Could not get map information', result['error'])
        self.assertEqual(result['location'], (5, 3))

    @patch('src.controller.actions.gather_resources.get_map_api')
    def test_execute_map_api_no_data(self, mock_get_map_api):
        """Test gathering fails when map API returns no data."""
        mock_response = Mock()
        mock_response.data = None
        mock_get_map_api.return_value = mock_response
        
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn('Could not get map information', result['error'])

    @patch('src.controller.actions.gather_resources.get_map_api')
    def test_execute_no_resource_at_location(self, mock_get_map_api):
        """Test gathering fails when no resource at location."""
        # Mock map data without resource
        mock_map_data = Mock()
        mock_map_data.content = None
        
        mock_response = Mock()
        mock_response.data = mock_map_data
        mock_get_map_api.return_value = mock_response
        
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn('No resource available at current location', result['error'])

    @patch('src.controller.actions.gather_resources.get_map_api')
    def test_execute_wrong_content_type(self, mock_get_map_api):
        """Test gathering fails when location has wrong content type."""
        # Mock map data with non-resource content
        mock_content = Mock()
        mock_content.type_ = 'workshop'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_response = Mock()
        mock_response.data = mock_map_data
        mock_get_map_api.return_value = mock_response
        
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn('No resource available at current location', result['error'])

    @patch('src.controller.actions.gather_resources.get_map_api')
    def test_execute_wrong_target_resource(self, mock_get_map_api):
        """Test gathering fails when resource doesn't match target."""
        # Mock map data with different resource
        mock_content = Mock()
        mock_content.type_ = 'resource'
        mock_content.code = 'iron_ore'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_response = Mock()
        mock_response.data = mock_map_data
        mock_get_map_api.return_value = mock_response
        
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn('Resource iron_ore does not match target copper', result['error'])
        self.assertEqual(result['available_resource'], 'iron_ore')

    @patch('src.controller.actions.gather_resources.get_resource_api')
    @patch('src.controller.actions.gather_resources.get_map_api')
    def test_execute_resource_api_fails(self, mock_get_map_api, mock_get_resource_api):
        """Test gathering fails when resource API fails."""
        # Mock map data with target resource
        mock_content = Mock()
        mock_content.type_ = 'resource'
        mock_content.code = 'copper'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map_api.return_value = mock_map_response
        
        # Mock resource API failure
        mock_get_resource_api.return_value = None
        
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn('Could not get details for resource copper', result['error'])

    @patch('src.controller.actions.gather_resources.get_resource_api')
    @patch('src.controller.actions.gather_resources.get_map_api')
    def test_execute_resource_api_no_data(self, mock_get_map_api, mock_get_resource_api):
        """Test gathering fails when resource API returns no data."""
        # Mock map data with target resource
        mock_content = Mock()
        mock_content.type_ = 'resource'
        mock_content.code = 'copper'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map_api.return_value = mock_map_response
        
        # Mock resource API with no data
        mock_resource_response = Mock()
        mock_resource_response.data = None
        mock_get_resource_api.return_value = mock_resource_response
        
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn('Could not get details for resource copper', result['error'])

    @patch('src.controller.actions.gather_resources.gathering_api')
    @patch('src.controller.actions.gather_resources.get_resource_api')
    @patch('src.controller.actions.gather_resources.get_map_api')
    def test_execute_gathering_api_fails(self, mock_get_map_api, mock_get_resource_api, mock_gathering_api):
        """Test gathering fails when gathering API fails."""
        self._setup_successful_mocks(mock_get_map_api, mock_get_resource_api)
        
        # Mock gathering API failure
        mock_gathering_api.return_value = None
        
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn('Gathering action failed - no response data', result['error'])

    @patch('src.controller.actions.gather_resources.gathering_api')
    @patch('src.controller.actions.gather_resources.get_resource_api')
    @patch('src.controller.actions.gather_resources.get_map_api')
    def test_execute_gathering_api_no_data(self, mock_get_map_api, mock_get_resource_api, mock_gathering_api):
        """Test gathering fails when gathering API returns no data."""
        self._setup_successful_mocks(mock_get_map_api, mock_get_resource_api)
        
        # Mock gathering API with no data
        mock_gathering_response = Mock()
        mock_gathering_response.data = None
        mock_gathering_api.return_value = mock_gathering_response
        
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn('Gathering action failed - no response data', result['error'])

    @patch('src.controller.actions.gather_resources.gathering_api')
    @patch('src.controller.actions.gather_resources.get_resource_api')
    @patch('src.controller.actions.gather_resources.get_map_api')
    def test_execute_success_minimal_data(self, mock_get_map_api, mock_get_resource_api, mock_gathering_api):
        """Test successful gathering with minimal response data."""
        self._setup_successful_mocks(mock_get_map_api, mock_get_resource_api)
        
        # Mock gathering response with minimal data
        mock_skill_data = Mock(spec=[])
        mock_skill_data.xp = 0
        mock_skill_data.skill = 'unknown'
        
        mock_gathering_response = Mock()
        mock_gathering_response.data = mock_skill_data
        mock_gathering_api.return_value = mock_gathering_response
        
        result = self.action.execute(self.mock_client)
        self.assertTrue(result['success'])
        self.assertEqual(result['resource_code'], 'copper')
        self.assertEqual(result['location'], (5, 3))

    @patch('src.controller.actions.gather_resources.gathering_api')
    @patch('src.controller.actions.gather_resources.get_resource_api')
    @patch('src.controller.actions.gather_resources.get_map_api')
    def test_execute_success_full_data(self, mock_get_map_api, mock_get_resource_api, mock_gathering_api):
        """Test successful gathering with full response data."""
        self._setup_successful_mocks(mock_get_map_api, mock_get_resource_api)
        
        # Mock gathering response with full data
        mock_cooldown = Mock()
        mock_cooldown.total_seconds = 15
        
        mock_character = Mock()
        mock_character.level = 12
        mock_character.hp = 90
        mock_character.max_hp = 100
        
        mock_obtained_item = Mock()
        mock_obtained_item.code = 'copper'
        mock_obtained_item.quantity = 1
        
        mock_details = Mock()
        mock_details.items = [mock_obtained_item]
        
        mock_skill_data = Mock()
        mock_skill_data.cooldown = mock_cooldown
        mock_skill_data.xp = 15
        mock_skill_data.skill = 'mining'
        mock_skill_data.character = mock_character
        mock_skill_data.details = mock_details
        
        mock_gathering_response = Mock()
        mock_gathering_response.data = mock_skill_data
        mock_gathering_api.return_value = mock_gathering_response
        
        result = self.action.execute(self.mock_client)
        self.assertTrue(result['success'])
        self.assertEqual(result['cooldown'], 15)
        self.assertEqual(result['xp_gained'], 15)
        self.assertEqual(result['skill'], 'mining')
        self.assertEqual(result['character_level'], 12)
        self.assertEqual(result['character_hp'], 90)
        self.assertEqual(result['character_max_hp'], 100)
        self.assertEqual(len(result['items_obtained']), 1)
        self.assertEqual(result['items_obtained'][0]['code'], 'copper')
        self.assertEqual(result['items_obtained'][0]['quantity'], 1)

    @patch('src.controller.actions.gather_resources.get_map_api')
    def test_execute_exception_handling(self, mock_get_map_api):
        """Test exception handling during gathering."""
        mock_get_map_api.side_effect = Exception("Network error")
        
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn('Gathering action failed: Network error', result['error'])

    @patch('src.controller.actions.gather_resources.get_resource_api')
    @patch('src.controller.actions.gather_resources.get_map_api')
    def test_execute_no_target_any_resource(self, mock_get_map_api, mock_get_resource_api):
        """Test gathering any resource when no target specified."""
        # Create action without target
        action = GatherResourcesAction(self.character_name)
        
        # Mock map data with any resource
        mock_content = Mock()
        mock_content.type_ = 'resource'
        mock_content.code = 'iron_ore'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map_api.return_value = mock_map_response
        
        # Mock resource data
        mock_resource_data = Mock()
        mock_resource_data.name = 'Iron Ore'
        
        mock_resource_response = Mock()
        mock_resource_response.data = mock_resource_data
        mock_get_resource_api.return_value = mock_resource_response
        
        # Since we're not testing the gathering API call itself, 
        # we can mock it to return a valid response
        with patch('src.controller.actions.gather_resources.gathering_api') as mock_gathering_api:
            mock_skill_data = Mock(spec=[])
            mock_skill_data.xp = 10
            mock_skill_data.skill = 'mining'
            
            mock_gathering_response = Mock()
            mock_gathering_response.data = mock_skill_data
            mock_gathering_api.return_value = mock_gathering_response
            
            result = action.execute(self.mock_client)
            self.assertTrue(result['success'])
            self.assertEqual(result['resource_code'], 'iron_ore')

    def test_execute_has_goap_attributes(self):
        """Test that GatherResourcesAction has expected GOAP attributes."""
        self.assertTrue(hasattr(GatherResourcesAction, 'conditions'))
        self.assertTrue(hasattr(GatherResourcesAction, 'reactions'))
        self.assertTrue(hasattr(GatherResourcesAction, 'weights'))
        self.assertTrue(hasattr(GatherResourcesAction, 'g'))

    def _setup_successful_mocks(self, mock_get_map_api, mock_get_resource_api):
        """Helper method to setup successful mock responses."""
        # Mock map data with resource
        mock_content = Mock()
        mock_content.type_ = 'resource'
        mock_content.code = 'copper'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map_api.return_value = mock_map_response
        
        # Mock resource data
        mock_resource_data = Mock()
        mock_resource_data.name = 'Copper Ore'
        
        mock_resource_response = Mock()
        mock_resource_response.data = mock_resource_data
        mock_get_resource_api.return_value = mock_resource_response


if __name__ == '__main__':
    unittest.main()