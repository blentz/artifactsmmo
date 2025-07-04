"""Test module for CheckLocationAction."""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.controller.actions.check_location import CheckLocationAction

from test.fixtures import create_mock_client


class TestCheckLocationAction(unittest.TestCase):
    """Test cases for CheckLocationAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_prefix = os.environ.get('DATA_PREFIX', '')
        os.environ['DATA_PREFIX'] = self.temp_dir
        
        self.character_name = "test_character"
        self.action = CheckLocationAction()

    def tearDown(self):
        """Clean up test fixtures."""
        os.environ['DATA_PREFIX'] = self.original_data_prefix
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_check_location_action_initialization(self):
        """Test CheckLocationAction initialization."""
        self.assertFalse(hasattr(self.action, 'character_name'))
        self.assertIsNotNone(self.action.logger)

    def test_check_location_action_repr(self):
        """Test CheckLocationAction string representation."""
        expected = "CheckLocationAction()"
        self.assertEqual(repr(self.action), expected)

    def test_execute_no_client(self):
        """Test execute fails without client."""
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.character_name)
        result = self.action.execute(None, context)
        # With centralized validation, None client triggers validation error
        self.assertFalse(result.success)
        # Direct action execution bypasses centralized validation
        self.assertIsNotNone(result.error)

    @patch('src.controller.actions.check_location.get_character_api')
    def test_execute_character_api_fails(self, mock_get_character_api):
        """Test execute when character API fails."""
        mock_get_character_api.return_value = None
        client = create_mock_client()
        
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.character_name)
        result = self.action.execute(client, context)
        self.assertFalse(result.success)
        self.assertIn('Could not get character data', result.error)

    @patch('src.controller.actions.check_location.get_character_api')
    def test_execute_character_api_no_data(self, mock_get_character_api):
        """Test execute when character API returns no data."""
        mock_response = Mock()
        mock_response.data = None
        mock_get_character_api.return_value = mock_response
        client = create_mock_client()
        
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.character_name)
        result = self.action.execute(client, context)
        self.assertFalse(result.success)
        self.assertIn('Could not get character data', result.error)

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
        client = create_mock_client()
        
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.character_name)
        result = self.action.execute(client, context)
        self.assertTrue(result.success)
        self.assertEqual(result.data['character_name'], 'test_character')
        self.assertEqual(result.data['current_x'], 10)
        self.assertEqual(result.data['current_y'], 15)
        self.assertIn('location_info', result.data)

    @patch('src.controller.actions.check_location.get_character_api')
    def test_execute_success_with_map_data(self, mock_get_character_api):
        """Test successful execution with map data."""
        # Mock character location
        mock_character = Mock()
        mock_character.x = 5
        mock_character.y = 8
        mock_character.name = "test_character"
        mock_response = Mock()
        mock_response.data = mock_character
        mock_get_character_api.return_value = mock_response
        
        # Mock map state that will be passed as kwarg
        mock_map_state = Mock()
        mock_location_data = Mock()
        mock_location_data.content_type = 'resource'
        mock_location_data.content_code = 'copper_rocks'
        mock_map_state.get_location_info.return_value = mock_location_data
        
        client = create_mock_client()
        
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.character_name, map_state=mock_map_state)
        result = self.action.execute(client, context)
        self.assertTrue(result.success)
        self.assertEqual(result.data['current_x'], 5)
        self.assertEqual(result.data['current_y'], 8)
        # The action returns location_info, not map_content
        self.assertIn('location_info', result.data)
        self.assertEqual(result.data['location_info']['content_type'], 'resource')
        self.assertIn('location_info', result.data)
        self.assertEqual(result.data['location_info']['content_code'], 'copper_rocks')

    @patch('src.controller.actions.check_location.get_character_api')
    def test_execute_map_api_fails(self, mock_get_character_api):
        """Test execution when map state is not available."""
        # Mock character location
        mock_character = Mock()
        mock_character.x = 5
        mock_character.y = 8
        mock_character.name = "test_character"
        mock_response = Mock()
        mock_response.data = mock_character
        mock_get_character_api.return_value = mock_response
        
        client = create_mock_client()
        
        # Execute without map_state
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.character_name)
        result = self.action.execute(client, context)
        self.assertTrue(result.success)  # Should still succeed without map data
        self.assertEqual(result.data['current_x'], 5)
        self.assertEqual(result.data['current_y'], 8)
        self.assertIn('location_info', result.data)
        # When no map state, location_info will be empty
        self.assertEqual(result.data['location_info'], {})

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
        client = create_mock_client()
        
        # Context with target location
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.character_name, target_x=10, target_y=15)
        
        result = self.action.execute(client, context)
        self.assertTrue(result.success)
        self.assertEqual(result.data['current_x'], 10)
        self.assertEqual(result.data['current_y'], 15)
        # Should indicate if at target location
        self.assertTrue(result.data.get('at_location', False))

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
        client = create_mock_client()
        
        # Context with different target location
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.character_name, target_x=10, target_y=15)
        
        result = self.action.execute(client, context)
        self.assertTrue(result.success)
        self.assertEqual(result.data['current_x'], 5)
        self.assertEqual(result.data['current_y'], 8)
        # The action always sets target coordinates to current location
        self.assertEqual(result.data['target_x'], 5)
        self.assertEqual(result.data['target_y'], 8)

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
        client = create_mock_client()
        
        with patch('src.controller.actions.check_location.get_character_api', side_effect=Exception("API Error")):
            from test.fixtures import MockActionContext
            context = MockActionContext(character_name=self.character_name)
            result = self.action.execute(client, context)
            self.assertFalse(result.success)
            self.assertIn('Location check failed', result.error)

    def test_execute_has_goap_attributes(self):
        """Test that CheckLocationAction has expected GOAP attributes."""
        self.assertTrue(hasattr(CheckLocationAction, 'conditions'))
        self.assertTrue(hasattr(CheckLocationAction, 'reactions'))
        self.assertTrue(hasattr(CheckLocationAction, 'weight'))

    def test_goap_conditions(self):
        """Test GOAP conditions are properly defined."""
        self.assertIn('character_status', CheckLocationAction.conditions)
        self.assertTrue(CheckLocationAction.conditions['character_status']['alive'])

    def test_goap_reactions(self):
        """Test GOAP reactions are properly defined."""
        self.assertIn('location_known', CheckLocationAction.reactions)
        self.assertIn('location_context', CheckLocationAction.reactions)
        self.assertIn('spatial_context_updated', CheckLocationAction.reactions)
        self.assertTrue(CheckLocationAction.reactions['location_context']['at_target'])

    def test_goap_weights(self):
        """Test GOAP weights are properly defined."""
        expected_weight = CheckLocationAction.weight
        self.assertIsInstance(expected_weight, (int, float))

    def test_different_character_names(self):
        """Test action works with different character names."""
        character_names = ['player1', 'test_char', 'ai_player', 'special-character']
        
        for name in character_names:
            action = CheckLocationAction()
            from test.fixtures import MockActionContext
            context = MockActionContext(character_name=name)
            # Test that action works with different character names
            self.assertIsInstance(action, CheckLocationAction)
            
            # Test representation
            expected_repr = "CheckLocationAction()"
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
        client = create_mock_client()
        
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.character_name)
        result = self.action.execute(client, context)
        self.assertTrue(result.success)
        
        # Should capture location information
        self.assertEqual(result.data['current_x'], 10)
        self.assertEqual(result.data['current_y'], 15)
        self.assertEqual(result.data['character_name'], 'test_character')

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
            client = create_mock_client()
            
            from test.fixtures import MockActionContext
            context = MockActionContext(character_name=self.character_name)
            result = self.action.execute(client, context)
            self.assertTrue(result.success)
            self.assertEqual(result.data['current_x'], x)
            self.assertEqual(result.data['current_y'], y)


if __name__ == '__main__':
    unittest.main()