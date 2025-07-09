"""Test module for GatherResourcesAction."""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.gather_resources import GatherResourcesAction

from test.fixtures import MockActionContext, create_mock_client


class TestGatherResourcesAction(unittest.TestCase):
    """Test cases for GatherResourcesAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.character_name = "TestCharacter"
        self.target_resource = "copper"
        self.action = GatherResourcesAction()
        
        # Mock client
        self.mock_client = create_mock_client()
        
        # Mock character response
        self.mock_character_data = Mock()
        self.mock_character_data.x = 5
        self.mock_character_data.y = 3
        
        self.mock_character_response = Mock()
        self.mock_character_response.data = self.mock_character_data
        self.mock_client._character_cache = self.mock_character_response

    def test_gather_resources_action_initialization(self):
        """Test GatherResourcesAction initialization."""
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(self.action, 'character_name'))
        self.assertFalse(hasattr(self.action, 'target_resource'))

    def test_gather_resources_action_initialization_no_target(self):
        """Test GatherResourcesAction initialization without target resource."""
        action = GatherResourcesAction()
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(action, 'character_name'))
        self.assertFalse(hasattr(action, 'target_resource'))

    def test_gather_resources_action_repr_with_target(self):
        """Test GatherResourcesAction string representation with target."""
        # Repr is now simplified
        expected = "GatherResourcesAction()"
        self.assertEqual(repr(self.action), expected)
    
    @patch('src.controller.actions.gather_resources.get_map_api')
    @patch('src.controller.actions.gather_resources.gathering_api')
    @patch('src.controller.actions.gather_resources.get_resource_api')
    def test_execute_with_no_position_uses_character_cache(self, mock_get_resource, mock_gathering, mock_get_map):
        """Test execute uses character cache when position not provided."""
        # Create context without character position
        context = MockActionContext(
            character_name=self.character_name,
            target_resource=self.target_resource,
            character_x=None,  # No position provided
            character_y=None
        )
        
        # Mock map response
        mock_map_data = Mock()
        mock_map_data.content = Mock()
        mock_map_data.content.code = 'copper'  # Changed to match resource code
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map.return_value = mock_map_response
        
        # Mock resource API
        mock_resource_data = Mock()
        mock_resource_data.name = 'Copper Rocks'
        mock_resource_response = Mock()
        mock_resource_response.data = mock_resource_data
        mock_get_resource.return_value = mock_resource_response
        
        # Mock successful gather with proper structure
        mock_skill_data = Mock(spec=[])  # spec=[] prevents iteration errors
        mock_skill_data.xp = 10
        mock_skill_data.skill = 'mining'
        mock_gathering.return_value = Mock(data=mock_skill_data)
        
        # Add character cache to client
        self.mock_client._character_cache = self.mock_character_response
        
        result = self.action.execute(self.mock_client, context)
        
        # Should use position from character cache
        if not result.success:
            print(f"Error: {result.error}")
            print(f"Data: {result.data}")
        self.assertTrue(result.success)
        mock_get_map.assert_called_once_with(x=5, y=3, client=self.mock_client)

    def test_gather_resources_action_repr_no_target(self):
        """Test GatherResourcesAction string representation without target."""
        action = GatherResourcesAction()
        expected = "GatherResourcesAction()"
        self.assertEqual(repr(action), expected)

    def test_execute_no_client(self):
        """Test gathering fails without client."""
        context = MockActionContext(character_name=self.character_name, target_resource=self.target_resource, character_x=5, character_y=3)
        result = self.action.execute(None, context)
        # With centralized validation, None client triggers validation error
        self.assertFalse(result.success)
        # Direct action execution bypasses centralized validation
        self.assertIsNotNone(result.error)

    def test_execute_no_character_cache(self):
        """Test gathering fails without character data."""
        mock_client = create_mock_client()
        mock_client._character_cache = None
        
        # Test without position in context
        context = MockActionContext(character_name=self.character_name, target_resource=self.target_resource, character_x=None, character_y=None)
        result = self.action.execute(mock_client, context)
        self.assertFalse(result.success)
        self.assertIn('No character data or position available', result.error)

    @patch('src.controller.actions.gather_resources.get_map_api')
    def test_execute_map_api_fails(self, mock_get_map_api):
        """Test gathering fails when map API fails."""
        mock_get_map_api.return_value = None
        
        context = MockActionContext(character_name=self.character_name, target_resource=self.target_resource, character_x=5, character_y=3)
        result = self.action.execute(self.mock_client, context)
        self.assertFalse(result.success)
        self.assertIn('Could not get map information', result.error)
        self.assertEqual(result.data['location'], (5, 3))

    @patch('src.controller.actions.gather_resources.get_map_api')
    def test_execute_map_api_no_data(self, mock_get_map_api):
        """Test gathering fails when map API returns no data."""
        mock_response = Mock()
        mock_response.data = None
        mock_get_map_api.return_value = mock_response
        
        context = MockActionContext(character_name=self.character_name, target_resource=self.target_resource, character_x=5, character_y=3)
        result = self.action.execute(self.mock_client, context)
        self.assertFalse(result.success)
        self.assertIn('Could not get map information', result.error)

    @patch('src.controller.actions.gather_resources.get_map_api')
    def test_execute_no_resource_at_location(self, mock_get_map_api):
        """Test gathering fails when no resource at location."""
        # Mock map data without resource
        mock_map_data = Mock()
        mock_map_data.content = None
        
        mock_response = Mock()
        mock_response.data = mock_map_data
        mock_get_map_api.return_value = mock_response
        
        context = MockActionContext(character_name=self.character_name, target_resource=self.target_resource, character_x=5, character_y=3)
        result = self.action.execute(self.mock_client, context)
        self.assertFalse(result.success)
        self.assertIn('Gathering action failed', result.error)

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
        
        context = MockActionContext(character_name=self.character_name, target_resource=self.target_resource, character_x=5, character_y=3)
        result = self.action.execute(self.mock_client, context)
        self.assertFalse(result.success)
        self.assertIn('Gathering action failed', result.error)

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
        
        context = MockActionContext(character_name=self.character_name, target_resource=self.target_resource, character_x=5, character_y=3)
        result = self.action.execute(self.mock_client, context)
        self.assertFalse(result.success)
        self.assertIn('Gathering action failed', result.error)
        # The available_resource field is no longer present in error responses

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
        
        context = MockActionContext(character_name=self.character_name, target_resource=self.target_resource, character_x=5, character_y=3)
        result = self.action.execute(self.mock_client, context)
        self.assertFalse(result.success)
        self.assertIn('Could not get details for resource copper', result.error)

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
        
        context = MockActionContext(character_name=self.character_name, target_resource=self.target_resource, character_x=5, character_y=3)
        result = self.action.execute(self.mock_client, context)
        self.assertFalse(result.success)
        self.assertIn('Could not get details for resource copper', result.error)

    @patch('src.controller.actions.gather_resources.gathering_api')
    @patch('src.controller.actions.gather_resources.get_resource_api')
    @patch('src.controller.actions.gather_resources.get_map_api')
    def test_execute_gathering_api_fails(self, mock_get_map_api, mock_get_resource_api, mock_gathering_api):
        """Test gathering fails when gathering API fails."""
        self._setup_successful_mocks(mock_get_map_api, mock_get_resource_api)
        
        # Mock gathering API failure
        mock_gathering_api.return_value = None
        
        context = MockActionContext(character_name=self.character_name, target_resource=self.target_resource, character_x=5, character_y=3)
        result = self.action.execute(self.mock_client, context)
        self.assertFalse(result.success)
        self.assertIn('Gathering action failed - no response data', result.error)

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
        
        context = MockActionContext(character_name=self.character_name, target_resource=self.target_resource, character_x=5, character_y=3)
        result = self.action.execute(self.mock_client, context)
        self.assertFalse(result.success)
        self.assertIn('Gathering action failed - no response data', result.error)

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
        
        context = MockActionContext(character_name=self.character_name, target_resource=self.target_resource, character_x=5, character_y=3)
        result = self.action.execute(self.mock_client, context)
        self.assertTrue(result.success)
        self.assertEqual(result.data['resource_code'], 'copper')
        self.assertEqual(result.data['location'], (5, 3))

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
        
        context = MockActionContext(character_name=self.character_name, target_resource=self.target_resource, character_x=5, character_y=3)
        result = self.action.execute(self.mock_client, context)
        self.assertTrue(result.success)
        self.assertEqual(result.data['cooldown'], 15)
        self.assertEqual(result.data['xp_gained'], 15)
        self.assertEqual(result.data['skill'], 'mining')
        self.assertEqual(result.data['character_level'], 12)
        self.assertEqual(result.data['character_hp'], 90)
        self.assertEqual(result.data['character_max_hp'], 100)
        self.assertEqual(len(result.data['items_obtained']), 1)
        self.assertEqual(result.data['items_obtained'][0]['code'], 'copper')
        self.assertEqual(result.data['items_obtained'][0]['quantity'], 1)

    @patch('src.controller.actions.gather_resources.get_map_api')
    def test_execute_exception_handling(self, mock_get_map_api):
        """Test exception handling during gathering."""
        mock_get_map_api.side_effect = Exception("Network error")
        
        context = MockActionContext(character_name=self.character_name, target_resource=self.target_resource, character_x=5, character_y=3)
        result = self.action.execute(self.mock_client, context)
        self.assertFalse(result.success)
        self.assertIn('Gathering action failed: Network error', result.error)

    @patch('src.controller.actions.gather_resources.get_resource_api')
    @patch('src.controller.actions.gather_resources.get_map_api')
    def test_execute_no_target_any_resource(self, mock_get_map_api, mock_get_resource_api):
        """Test gathering any resource when no target specified."""
        # Create action without target
        action = GatherResourcesAction()
        
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
            
            context = MockActionContext(character_name=self.character_name, character_x=5, character_y=3)
            result = action.execute(self.mock_client, context)
            self.assertTrue(result.success)
            self.assertEqual(result.data['resource_code'], 'iron_ore')

    def test_execute_has_goap_attributes(self):
        """Test that GatherResourcesAction has expected GOAP attributes."""
        self.assertTrue(hasattr(GatherResourcesAction, 'conditions'))
        self.assertTrue(hasattr(GatherResourcesAction, 'reactions'))
        self.assertTrue(hasattr(GatherResourcesAction, 'weight'))

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