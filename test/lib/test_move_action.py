import unittest
from unittest.mock import Mock, patch

from artifactsmmo_api_client.client import AuthenticatedClient
from src.controller.actions.move import MoveAction


class TestMoveAction(unittest.TestCase):
    def setUp(self):
        self.client = AuthenticatedClient(base_url="https://api.artifactsmmo.com", token="test_token")
        self.char_name = "test_character"
        self.x = 10
        self.y = 20

    def test_move_action_initialization(self):
        action = MoveAction()
        self.assertIsInstance(action, MoveAction)
        self.assertFalse(hasattr(action, 'character_name'))
        self.assertFalse(hasattr(action, 'x'))
        self.assertFalse(hasattr(action, 'y'))

    @patch('src.controller.actions.movement_base.move_character_api')
    def test_move_action_execute(self, mock_move_api):
        # Mock the API response to avoid making actual API calls
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.cooldown = 5
        mock_move_api.return_value = mock_response
        
        action = MoveAction()
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name, x=self.x, y=self.y)
        response = action.execute(self.client, context)
        
        # Verify the API was called with correct parameters
        mock_move_api.assert_called_once()
        call_args = mock_move_api.call_args
        self.assertEqual(call_args.kwargs['name'], self.char_name)
        self.assertEqual(call_args.kwargs['client'], self.client)
        self.assertEqual(call_args.kwargs['body'].x, self.x)
        self.assertEqual(call_args.kwargs['body'].y, self.y)
        
        # Verify response is properly formatted
        self.assertIsInstance(response, dict)
        self.assertTrue(response.get('success'))
        self.assertTrue(response.get('moved'))
        self.assertEqual(response.get('target_x'), self.x)
        self.assertEqual(response.get('target_y'), self.y)
        self.assertEqual(response.get('cooldown'), 5)

    @patch('src.controller.actions.movement_base.move_character_api')
    def test_move_action_already_at_destination(self, mock_move_api):
        # Mock API to raise exception for "already at destination"
        mock_move_api.side_effect = Exception('Move failed: Unexpected status code: 490\n\nResponse content:\n{"error":{"code":490,"message":"Character already at destination."}}')
        
        action = MoveAction()
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name, x=self.x, y=self.y)
        response = action.execute(self.client, context)
        
        # Verify the API was called
        mock_move_api.assert_called_once()
        
        # Verify success response for "already at destination"
        self.assertIsInstance(response, dict)
        self.assertTrue(response.get('success', False))
        self.assertFalse(response.get('moved'))
        self.assertTrue(response.get('already_at_destination'))
        self.assertEqual(response.get('target_x'), self.x)
        self.assertEqual(response.get('target_y'), self.y)

    @patch('src.controller.actions.movement_base.move_character_api')
    def test_move_action_other_error(self, mock_move_api):
        # Mock API to raise a different exception
        mock_move_api.side_effect = Exception('Network error')
        
        action = MoveAction()
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name, x=self.x, y=self.y)
        response = action.execute(self.client, context)
        
        # Verify the API was called
        mock_move_api.assert_called_once()
        
        # Verify error response for other exceptions
        self.assertIsInstance(response, dict)
        self.assertFalse(response.get('success', True))
        self.assertIn('Network error', response.get('error', ''))

    def test_move_action_with_context_coordinates(self):
        # Test using coordinates from context
        action = MoveAction()
        
        # Test with target_x/target_y in context
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name, use_target_coordinates=True, target_x=30, target_y=40)
        response = action.execute(self.client, context)
        self.assertFalse(response.get('success'))  # Will fail due to no client mock
        
        # Verify coordinates were extracted correctly
        context = MockActionContext(character_name=self.char_name, use_target_coordinates=True, target_x=30, target_y=40)
        coords = action.get_target_coordinates(context)
        self.assertEqual(coords, (30, 40))
        
        # Test with x/y in context
        context = MockActionContext(character_name=self.char_name, x=50, y=60)
        coords = action.get_target_coordinates(context)
        self.assertEqual(coords, (50, 60))

    def test_move_action_no_coordinates(self):
        action = MoveAction()
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name)  # No coordinates
        response = action.execute(self.client, context)
        
        # Should fail with no coordinates
        self.assertFalse(response.get('success'))
        self.assertIn('No valid coordinates provided', response.get('error', ''))

if __name__ == '__main__':
    unittest.main()