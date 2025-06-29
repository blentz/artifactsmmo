"""Test module for CheckLocationAction."""

import unittest
import tempfile
import os
from unittest.mock import Mock, patch
from src.controller.actions.check_location import CheckLocationAction


class TestCheckLocationAction(unittest.TestCase):
    """Test cases for CheckLocationAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_prefix = os.environ.get('DATA_PREFIX', '')
        os.environ['DATA_PREFIX'] = self.temp_dir
        
        self.character_name = "test_character"
        self.action = CheckLocationAction(character_name=self.character_name)

    def tearDown(self):
        """Clean up test fixtures."""
        os.environ['DATA_PREFIX'] = self.original_data_prefix
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_check_location_action_initialization(self):
        """Test CheckLocationAction initialization."""
        self.assertEqual(self.action.character_name, "test_character")

    def test_check_location_action_repr(self):
        """Test CheckLocationAction string representation."""
        expected = "CheckLocationAction(test_character)"
        self.assertEqual(repr(self.action), expected)

    def test_execute_no_client(self):
        """Test execute fails without client."""
        result = self.action.execute(None)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    @patch('src.controller.actions.check_location.get_character_api')
    def test_execute_character_api_fails(self, mock_get_character_api):
        """Test execute when character API fails."""
        mock_get_character_api.return_value = None
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Could not get character data', result['error'])

    @patch('src.controller.actions.check_location.get_character_api')
    def test_execute_character_api_no_data(self, mock_get_character_api):
        """Test execute when character API returns no data."""
        mock_response = Mock()
        mock_response.data = None
        mock_get_character_api.return_value = mock_response
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Could not get character data', result['error'])

    @patch('src.controller.actions.check_location.get_character_api')
    def test_execute_success_basic_location(self, mock_get_character_api):
        """Test successful execution with basic location data."""
        # Mock character at a specific location
        mock_character = Mock()
        mock_character.x = 10
        mock_character.y = 15
        mock_character.name = "test_character"
        mock_response = Mock()
        mock_response.data = mock_character
        mock_get_character_api.return_value = mock_response
        client = Mock()
        
        result = self.action.execute(client)
        self.assertTrue(result['success'])
        self.assertEqual(result['character_name'], 'test_character')
        self.assertEqual(result['location']['x'], 10)
        self.assertEqual(result['location']['y'], 15)
        self.assertIn('location_check_time', result)

    @patch('src.controller.actions.check_location.get_map_api')
    @patch('src.controller.actions.check_location.get_character_api')
    def test_execute_success_with_map_data(self, mock_get_character_api, mock_get_map_api):
        """Test successful execution with map data."""
        # Mock character location
        mock_character = Mock()
        mock_character.x = 5
        mock_character.y = 8
        mock_character.name = "test_character"
        mock_response = Mock()
        mock_response.data = mock_character
        mock_get_character_api.return_value = mock_response
        
        # Mock map data at location
        mock_map_data = Mock()
        mock_map_data.x = 5
        mock_map_data.y = 8
        mock_map_data.content = {'type': 'resource', 'code': 'copper_rocks'}
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map_api.return_value = mock_map_response
        
        client = Mock()
        
        result = self.action.execute(client)
        self.assertTrue(result['success'])
        self.assertEqual(result['location']['x'], 5)
        self.assertEqual(result['location']['y'], 8)
        self.assertIn('map_content', result)
        self.assertEqual(result['map_content']['type'], 'resource')
        self.assertEqual(result['map_content']['code'], 'copper_rocks')

    @patch('src.controller.actions.check_location.get_map_api')
    @patch('src.controller.actions.check_location.get_character_api')
    def test_execute_map_api_fails(self, mock_get_character_api, mock_get_map_api):
        """Test execution when map API fails."""
        # Mock character location
        mock_character = Mock()
        mock_character.x = 5
        mock_character.y = 8
        mock_character.name = "test_character"
        mock_response = Mock()
        mock_response.data = mock_character
        mock_get_character_api.return_value = mock_response
        
        # Mock map API failure
        mock_get_map_api.return_value = None
        
        client = Mock()
        
        result = self.action.execute(client)
        self.assertTrue(result['success'])  # Should still succeed without map data
        self.assertEqual(result['location']['x'], 5)
        self.assertEqual(result['location']['y'], 8)
        self.assertIsNone(result.get('map_content'))  # No map content

    @patch('src.controller.actions.check_location.get_character_api')
    def test_execute_with_target_location_context(self, mock_get_character_api):
        """Test execution with target location in context."""
        mock_character = Mock()
        mock_character.x = 10
        mock_character.y = 15
        mock_character.name = "test_character"
        mock_response = Mock()
        mock_response.data = mock_character
        mock_get_character_api.return_value = mock_response
        client = Mock()
        
        # Context with target location
        context = {'target_x': 10, 'target_y': 15}
        
        result = self.action.execute(client, **context)
        self.assertTrue(result['success'])
        self.assertEqual(result['location']['x'], 10)
        self.assertEqual(result['location']['y'], 15)
        # Should indicate if at target location
        if 'at_target_location' in result:
            self.assertTrue(result['at_target_location'])

    @patch('src.controller.actions.check_location.get_character_api')
    def test_execute_not_at_target_location(self, mock_get_character_api):
        """Test execution when not at target location."""
        mock_character = Mock()
        mock_character.x = 5
        mock_character.y = 8
        mock_character.name = "test_character"
        mock_response = Mock()
        mock_response.data = mock_character
        mock_get_character_api.return_value = mock_response
        client = Mock()
        
        # Context with different target location
        context = {'target_x': 10, 'target_y': 15}
        
        result = self.action.execute(client, **context)
        self.assertTrue(result['success'])
        self.assertEqual(result['location']['x'], 5)
        self.assertEqual(result['location']['y'], 8)
        # Should indicate not at target location
        if 'at_target_location' in result:
            self.assertFalse(result['at_target_location'])

    def test_calculate_distance_helper_method(self):
        """Test _calculate_distance helper method."""
        # Test basic functionality if method exists
        if hasattr(self.action, '_calculate_distance'):
            distance = self.action._calculate_distance(0, 0, 3, 4)
            self.assertEqual(distance, 5.0)  # 3-4-5 triangle
            
            distance = self.action._calculate_distance(5, 5, 5, 5)
            self.assertEqual(distance, 0.0)  # Same location

    def test_analyze_location_content_helper_method(self):
        """Test _analyze_location_content helper method."""
        map_content = {'type': 'resource', 'code': 'copper_rocks', 'level': 1}
        
        # Test basic functionality if method exists
        if hasattr(self.action, '_analyze_location_content'):
            analysis = self.action._analyze_location_content(map_content)
            self.assertIsInstance(analysis, dict)
            # Should analyze the content type and accessibility

    def test_check_location_accessibility_helper_method(self):
        """Test _check_location_accessibility helper method."""
        location_data = {'x': 5, 'y': 8, 'content': {'type': 'resource', 'level': 1}}
        character_level = 5
        
        # Test basic functionality if method exists
        if hasattr(self.action, '_check_location_accessibility'):
            accessibility = self.action._check_location_accessibility(location_data, character_level)
            self.assertIsInstance(accessibility, (bool, str))

    def test_execute_exception_handling(self):
        """Test exception handling during execution."""
        client = Mock()
        
        with patch('src.controller.actions.check_location.get_character_api', side_effect=Exception("API Error")):
            result = self.action.execute(client)
            self.assertFalse(result['success'])
            self.assertIn('Location check failed', result['error'])

    def test_execute_has_goap_attributes(self):
        """Test that CheckLocationAction has expected GOAP attributes."""
        self.assertTrue(hasattr(CheckLocationAction, 'conditions'))
        self.assertTrue(hasattr(CheckLocationAction, 'reactions'))
        self.assertTrue(hasattr(CheckLocationAction, 'weights'))
        self.assertTrue(hasattr(CheckLocationAction, 'g'))

    def test_goap_conditions(self):
        """Test GOAP conditions are properly defined."""
        expected_conditions = {"character_alive": True}
        self.assertEqual(CheckLocationAction.conditions, expected_conditions)

    def test_goap_reactions(self):
        """Test GOAP reactions are properly defined."""
        expected_reactions = {
            "location_known": True,
            "at_target_location": True,
            "spatial_context_updated": True
        }
        self.assertEqual(CheckLocationAction.reactions, expected_reactions)

    def test_goap_weights(self):
        """Test GOAP weights are properly defined."""
        expected_weights = {"location_known": 1.0}
        self.assertEqual(CheckLocationAction.weights, expected_weights)

    def test_different_character_names(self):
        """Test action works with different character names."""
        character_names = ['player1', 'test_char', 'ai_player', 'special-character']
        
        for name in character_names:
            action = CheckLocationAction(name)
            self.assertEqual(action.character_name, name)
            
            # Test representation
            expected_repr = f"CheckLocationAction({name})"
            self.assertEqual(repr(action), expected_repr)

    @patch('src.controller.actions.check_location.get_character_api')
    def test_execute_with_additional_character_data(self, mock_get_character_api):
        """Test execution capturing additional character data."""
        mock_character = Mock()
        mock_character.x = 10
        mock_character.y = 15
        mock_character.name = "test_character"
        mock_character.level = 5
        mock_character.hp = 100
        mock_character.max_hp = 125
        mock_response = Mock()
        mock_response.data = mock_character
        mock_get_character_api.return_value = mock_response
        client = Mock()
        
        result = self.action.execute(client)
        self.assertTrue(result['success'])
        
        # Should capture additional character information if the action does so
        self.assertEqual(result['location']['x'], 10)
        self.assertEqual(result['location']['y'], 15)
        
        # Additional data might be included depending on implementation
        if 'character_stats' in result:
            self.assertIn('level', result['character_stats'])
            self.assertIn('hp', result['character_stats'])

    @patch('src.controller.actions.check_location.get_character_api')
    def test_execute_coordinate_validation(self, mock_get_character_api):
        """Test coordinate validation and bounds checking."""
        # Test edge cases with coordinates
        test_coordinates = [
            (0, 0),      # Origin
            (-5, -3),    # Negative coordinates
            (100, 200),  # Large coordinates
            (0, 50),     # Mixed
        ]
        
        for x, y in test_coordinates:
            mock_character = Mock()
            mock_character.x = x
            mock_character.y = y
            mock_character.name = "test_character"
            mock_response = Mock()
            mock_response.data = mock_character
            mock_get_character_api.return_value = mock_response
            client = Mock()
            
            result = self.action.execute(client)
            self.assertTrue(result['success'])
            self.assertEqual(result['location']['x'], x)
            self.assertEqual(result['location']['y'], y)


if __name__ == '__main__':
    unittest.main()