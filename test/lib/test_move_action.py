import unittest
from unittest.mock import Mock, patch

from artifactsmmo_api_client.client import AuthenticatedClient
from artifactsmmo_api_client.models.character_movement_response_schema import CharacterMovementResponseSchema
from src.controller.actions.move import MoveAction

class TestMoveAction(unittest.TestCase):
    def setUp(self):
        self.client = AuthenticatedClient(base_url="https://api.artifactsmmo.com", token="test_token")
        self.char_name = "test_character"
        self.x = 10
        self.y = 20

    def test_move_action_initialization(self):
        action = MoveAction(char_name=self.char_name, x=self.x, y=self.y)
        self.assertEqual(action.char_name, self.char_name)
        self.assertEqual(action.x, self.x)
        self.assertEqual(action.y, self.y)

    @patch('src.controller.actions.move.move_character_api')
    def test_move_action_execute(self, mock_move_api):
        # Mock the API response to avoid making actual API calls
        mock_response = Mock()
        mock_move_api.return_value = mock_response
        
        action = MoveAction(char_name=self.char_name, x=self.x, y=self.y)
        response = action.execute(client=self.client)
        
        # Verify the API was called with correct parameters
        mock_move_api.assert_called_once()
        call_args = mock_move_api.call_args
        self.assertEqual(call_args.kwargs['name'], self.char_name)
        self.assertEqual(call_args.kwargs['client'], self.client)
        self.assertEqual(call_args.kwargs['body'].x, self.x)
        self.assertEqual(call_args.kwargs['body'].y, self.y)
        
        # Verify response is returned
        self.assertIsNotNone(response)
        self.assertEqual(response, mock_response)

    @patch('src.controller.actions.move.move_character_api')
    def test_move_action_already_at_destination(self, mock_move_api):
        # Mock API to raise exception for "already at destination"
        mock_move_api.side_effect = Exception('Move failed: Unexpected status code: 490\n\nResponse content:\n{"error":{"code":490,"message":"Character already at destination."}}')
        
        action = MoveAction(char_name=self.char_name, x=self.x, y=self.y)
        response = action.execute(client=self.client)
        
        # Verify the API was called
        mock_move_api.assert_called_once()
        
        # Verify success response for "already at destination"
        self.assertIsInstance(response, dict)
        self.assertTrue(response.get('success', False))
        self.assertEqual(response.get('message'), "Character already at destination")
        self.assertEqual(response.get('x'), self.x)
        self.assertEqual(response.get('y'), self.y)
        self.assertEqual(response.get('char_name'), self.char_name)

    @patch('src.controller.actions.move.move_character_api')
    def test_move_action_other_error(self, mock_move_api):
        # Mock API to raise a different exception
        mock_move_api.side_effect = Exception('Network error')
        
        action = MoveAction(char_name=self.char_name, x=self.x, y=self.y)
        response = action.execute(client=self.client)
        
        # Verify the API was called
        mock_move_api.assert_called_once()
        
        # Verify error response for other exceptions
        self.assertIsInstance(response, dict)
        self.assertFalse(response.get('success', True))
        self.assertIn('Network error', response.get('error', ''))
        self.assertEqual(response.get('x'), self.x)
        self.assertEqual(response.get('y'), self.y)

if __name__ == '__main__':
    unittest.main()
