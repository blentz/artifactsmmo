import unittest
from unittest.mock import Mock, patch

from src.controller.actions.movement_base import MovementActionBase

from test.fixtures import MockActionContext, create_mock_client


class TestMovementAction(MovementActionBase):
    """Test implementation of MovementActionBase for testing."""
    
    def __init__(self):
        super().__init__()
    
    def get_target_coordinates(self, context):
        """Simple test implementation."""
        return context.get('x'), context.get('y')


class TestMovementActionBase(unittest.TestCase):
    def setUp(self):
        self.client = create_mock_client()
        self.char_name = "test_character"

    def test_movement_base_initialization(self):
        action = TestMovementAction()
        # Action no longer stores character_name as instance attribute
        self.assertFalse(hasattr(action, 'character_name'))
        self.assertIsNotNone(action.logger)

    @patch('src.controller.actions.movement_base.move_character_api')
    def test_execute_movement_success(self, mock_move_api):
        # Mock successful API response
        mock_response = Mock()
        mock_character = Mock()
        mock_character.x = 5
        mock_character.y = 10
        mock_response.data = Mock(cooldown=10, character=mock_character)
        mock_move_api.return_value = mock_response
        
        action = TestMovementAction()
        context = MockActionContext(character_name=self.char_name, x=5, y=10)
        # execute_movement expects a dict, not MockActionContext
        movement_context = {'character_name': self.char_name}
        result = action.execute_movement(self.client, 5, 10, movement_context)
        
        # Verify API was called correctly
        mock_move_api.assert_called_once()
        
        # Verify response format
        self.assertTrue(result.success)
        self.assertTrue(result.data['moved'])
        self.assertEqual(result.data['target_x'], 5)
        self.assertEqual(result.data['target_y'], 10)
        self.assertEqual(result.data['cooldown'], 10)
        self.assertTrue(result.data['movement_completed'])

    @patch('src.controller.actions.movement_base.move_character_api')
    def test_execute_movement_already_at_destination(self, mock_move_api):
        # Mock "already at destination" error
        mock_move_api.side_effect = Exception('490 Character already at destination')
        
        action = TestMovementAction()
        context = MockActionContext(character_name=self.char_name)
        # execute_movement expects a dict, not MockActionContext
        movement_context = {'character_name': self.char_name}
        result = action.execute_movement(self.client, 5, 10, movement_context)
        
        # Verify response format for already at destination
        self.assertTrue(result.success)
        self.assertFalse(result.data['moved'])
        self.assertTrue(result.data['already_at_destination'])
        self.assertEqual(result.data['target_x'], 5)
        self.assertEqual(result.data['target_y'], 10)
        self.assertTrue(result.data['movement_completed'])

    @patch('src.controller.actions.movement_base.move_character_api')
    def test_execute_movement_other_error(self, mock_move_api):
        # Mock other error
        mock_move_api.side_effect = Exception('Network error')
        
        action = TestMovementAction()
        context = MockActionContext(character_name=self.char_name)
        # execute_movement expects a dict, not MockActionContext
        movement_context = {'character_name': self.char_name}
        result = action.execute_movement(self.client, 5, 10, movement_context)
        
        # Verify error response
        self.assertFalse(result.success)
        self.assertIn('Network error', result.error)

    def test_execute_no_coordinates(self):
        action = TestMovementAction()
        context = MockActionContext(character_name=self.char_name)
        result = action.execute(self.client, context)
        
        # Should fail with no coordinates
        self.assertFalse(result.success)
        self.assertIn('No valid coordinates provided', result.error)

    @patch('src.controller.actions.movement_base.move_character_api')
    def test_execute_with_context(self, mock_move_api):
        # Mock successful API response
        mock_response = Mock()
        mock_character = Mock()
        mock_character.x = 15
        mock_character.y = 20
        mock_response.data = Mock(cooldown=5, character=mock_character)
        mock_move_api.return_value = mock_response
        
        action = TestMovementAction()
        context = MockActionContext(character_name=self.char_name, x=15, y=20)
        result = action.execute(self.client, context)
        
        # Verify success
        self.assertTrue(result.success)
        self.assertEqual(result.data['target_x'], 15)
        self.assertEqual(result.data['target_y'], 20)

    def test_calculate_distance(self):
        action = TestMovementAction()
        
        # Test Manhattan distance calculation
        distance = action.calculate_distance(0, 0, 3, 4)
        self.assertEqual(distance, 7)  # |3-0| + |4-0| = 7
        
        distance = action.calculate_distance(5, 5, 2, 8)
        self.assertEqual(distance, 6)  # |2-5| + |8-5| = 6

    @patch('src.controller.actions.movement_base.move_character_api')
    def test_movement_context_building(self, mock_move_api):
        """Test that movement context is properly included in response."""
        mock_response = Mock()
        mock_character = Mock()
        mock_character.x = 10
        mock_character.y = 20
        mock_response.data = Mock(character=mock_character)
        mock_move_api.return_value = mock_response
        
        # Create custom action with context building
        class ContextTestAction(MovementActionBase):
            def get_target_coordinates(self, context):
                return 10, 20
            
            def build_movement_context(self, context):
                return {
                    'custom_field': 'test_value',
                    'resource_code': context.get('resource_code')
                }
        
        action = ContextTestAction()
        context = MockActionContext(character_name=self.char_name, resource_code='iron_ore')
        result = action.execute(self.client, context)
        
        # Verify context was included in response
        self.assertEqual(result.data.get('custom_field'), 'test_value')
        self.assertEqual(result.data.get('resource_code'), 'iron_ore')

    def test_no_api_client(self):
        action = TestMovementAction()
        context = MockActionContext(character_name=self.char_name, x=5, y=10)
        result = action.execute(None, context)
        
        # Should fail with no client
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)


if __name__ == '__main__':
    unittest.main()