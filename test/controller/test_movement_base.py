import unittest
from unittest.mock import Mock, patch

from artifactsmmo_api_client.client import AuthenticatedClient
from src.controller.actions.movement_base import MovementActionBase


class TestMovementAction(MovementActionBase):
    """Test implementation of MovementActionBase for testing."""
    
    def __init__(self, character_name: str, test_x: int = None, test_y: int = None):
        super().__init__(character_name)
        self.test_x = test_x
        self.test_y = test_y
    
    def get_target_coordinates(self, **kwargs):
        """Simple test implementation."""
        if self.test_x is not None and self.test_y is not None:
            return self.test_x, self.test_y
        return kwargs.get('x'), kwargs.get('y')


class TestMovementActionBase(unittest.TestCase):
    def setUp(self):
        self.client = AuthenticatedClient(base_url="https://api.artifactsmmo.com", token="test_token")
        self.char_name = "test_character"

    def test_movement_base_initialization(self):
        action = TestMovementAction(self.char_name)
        self.assertEqual(action.character_name, self.char_name)
        self.assertIsNotNone(action.logger)

    @patch('src.controller.actions.movement_base.move_character_api')
    def test_execute_movement_success(self, mock_move_api):
        # Mock successful API response
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.cooldown = 10
        mock_move_api.return_value = mock_response
        
        action = TestMovementAction(self.char_name, 5, 10)
        result = action.execute_movement(self.client, 5, 10)
        
        # Verify API was called correctly
        mock_move_api.assert_called_once()
        self.assertEqual(mock_move_api.call_args.kwargs['name'], self.char_name)
        
        # Verify response format
        self.assertTrue(result['success'])
        self.assertTrue(result['moved'])
        self.assertEqual(result['target_x'], 5)
        self.assertEqual(result['target_y'], 10)
        self.assertEqual(result['cooldown'], 10)
        self.assertTrue(result['movement_completed'])

    @patch('src.controller.actions.movement_base.move_character_api')
    def test_execute_movement_already_at_destination(self, mock_move_api):
        # Mock "already at destination" error
        mock_move_api.side_effect = Exception('490 Character already at destination')
        
        action = TestMovementAction(self.char_name)
        result = action.execute_movement(self.client, 5, 10)
        
        # Verify response format for already at destination
        self.assertTrue(result['success'])
        self.assertFalse(result['moved'])
        self.assertTrue(result['already_at_destination'])
        self.assertEqual(result['target_x'], 5)
        self.assertEqual(result['target_y'], 10)
        self.assertTrue(result['movement_completed'])

    @patch('src.controller.actions.movement_base.move_character_api')
    def test_execute_movement_other_error(self, mock_move_api):
        # Mock other error
        mock_move_api.side_effect = Exception('Network error')
        
        action = TestMovementAction(self.char_name)
        result = action.execute_movement(self.client, 5, 10)
        
        # Verify error response
        self.assertFalse(result['success'])
        self.assertIn('Network error', result['error'])

    def test_execute_no_coordinates(self):
        action = TestMovementAction(self.char_name)
        result = action.execute(self.client)
        
        # Should fail with no coordinates
        self.assertFalse(result['success'])
        self.assertIn('No valid coordinates provided', result['error'])

    @patch('src.controller.actions.movement_base.move_character_api')
    def test_execute_with_context(self, mock_move_api):
        # Mock successful API response
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.cooldown = 5
        mock_move_api.return_value = mock_response
        
        action = TestMovementAction(self.char_name)
        result = action.execute(self.client, x=15, y=20)
        
        # Verify success
        self.assertTrue(result['success'])
        self.assertEqual(result['target_x'], 15)
        self.assertEqual(result['target_y'], 20)

    def test_calculate_distance(self):
        action = TestMovementAction(self.char_name)
        
        # Test Manhattan distance calculation
        distance = action.calculate_distance(0, 0, 3, 4)
        self.assertEqual(distance, 7)  # |3-0| + |4-0| = 7
        
        distance = action.calculate_distance(5, 5, 2, 8)
        self.assertEqual(distance, 6)  # |2-5| + |8-5| = 6

    @patch('src.controller.actions.movement_base.move_character_api')
    def test_movement_context_building(self, mock_move_api):
        """Test that movement context is properly included in response."""
        mock_response = Mock()
        mock_response.data = Mock()
        mock_move_api.return_value = mock_response
        
        # Create custom action with context building
        class ContextTestAction(MovementActionBase):
            def get_target_coordinates(self, **kwargs):
                return 10, 20
            
            def build_movement_context(self, **kwargs):
                return {
                    'custom_field': 'test_value',
                    'resource_code': kwargs.get('resource_code')
                }
        
        action = ContextTestAction(self.char_name)
        result = action.execute(self.client, resource_code='iron_ore')
        
        # Verify context was included in response
        self.assertEqual(result.get('custom_field'), 'test_value')
        self.assertEqual(result.get('resource_code'), 'iron_ore')

    def test_no_api_client(self):
        action = TestMovementAction(self.char_name, 5, 10)
        result = action.execute(None)
        
        # Should fail with no client
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])


if __name__ == '__main__':
    unittest.main()