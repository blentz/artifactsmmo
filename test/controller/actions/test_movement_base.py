"""Test module for MovementActionBase class."""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.base.movement import MovementActionBase
from src.lib.action_context import ActionContext
from test.fixtures import MockActionContext, create_mock_client, MockKnowledgeBase


class TestMovementActionBase(unittest.TestCase):
    """Test cases for MovementActionBase class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = MovementActionBase()
        self.mock_client = create_mock_client()
    
    def test_init(self):
        """Test initialization."""
        action = MovementActionBase()
        self.assertIsInstance(action, MovementActionBase)
        self.assertEqual(action.conditions, {
            'character_status': {
                'alive': True,
            },
        })
        self.assertEqual(action.reactions, {})
        self.assertEqual(action.weight, 10)
    
    def test_get_target_coordinates_default(self):
        """Test get_target_coordinates with default implementation."""
        context = MockActionContext(target_x=10, target_y=20)
        x, y = self.action.get_target_coordinates(context)
        self.assertEqual(x, 10)
        self.assertEqual(y, 20)
    
    def test_get_target_coordinates_missing(self):
        """Test get_target_coordinates when coordinates are missing."""
        context = MockActionContext()
        x, y = self.action.get_target_coordinates(context)
        self.assertIsNone(x)
        self.assertIsNone(y)
    
    def test_calculate_distance(self):
        """Test calculate_distance method."""
        # Test simple case
        distance = self.action.calculate_distance(0, 0, 3, 4)
        self.assertEqual(distance, 7)  # |3-0| + |4-0| = 7
        
        # Test with negative coordinates
        distance = self.action.calculate_distance(-5, -5, 5, 5)
        self.assertEqual(distance, 20)  # |5-(-5)| + |5-(-5)| = 20
        
        # Test same location
        distance = self.action.calculate_distance(10, 10, 10, 10)
        self.assertEqual(distance, 0)
    
    def test_build_movement_context_default(self):
        """Test build_movement_context default implementation."""
        context = MockActionContext()
        movement_context = self.action.build_movement_context(context)
        self.assertEqual(movement_context, {})
    
    @patch('src.controller.actions.base.movement.move_character_api')
    def test_execute_movement_success(self, mock_move_api):
        """Test successful movement execution."""
        # Mock response
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.cooldown = 5
        # Mock character position in response
        mock_response.data.character = Mock()
        mock_response.data.character.x = 10
        mock_response.data.character.y = 20
        mock_move_api.return_value = mock_response
        
        # Set up context for the knowledge base refresh
        context = ActionContext()
        context.knowledge_base = MockKnowledgeBase()
        self.action._context = context
        
        # Execute movement
        result = self.action.execute_movement(
            self.mock_client, 
            10, 
            20,
            {'character_name': 'TestChar', 'extra_info': 'test'}
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Moved to (10, 20)")
        self.assertTrue(result.data['moved'])
        self.assertEqual(result.data['target_x'], 10)
        self.assertEqual(result.data['target_y'], 20)
        self.assertEqual(result.data['current_x'], 10)
        self.assertEqual(result.data['current_y'], 20)
        self.assertEqual(result.data['cooldown'], 5)
        self.assertTrue(result.data['movement_completed'])
        self.assertEqual(result.data['extra_info'], 'test')
    
    @patch('src.controller.actions.base.movement.move_character_api')
    def test_execute_movement_no_context(self, mock_move_api):
        """Test movement execution with no context provided."""
        # Mock response
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.cooldown = None
        # Mock character position in response
        mock_response.data.character = Mock()
        mock_response.data.character.x = 5
        mock_response.data.character.y = 15
        mock_move_api.return_value = mock_response
        
        # Set up context for the knowledge base refresh
        context = ActionContext()
        context.knowledge_base = MockKnowledgeBase()
        self.action._context = context
        
        # Execute movement with None context
        result = self.action.execute_movement(self.mock_client, 5, 15, None)
        
        self.assertTrue(result.success)
        # Verify API was called with 'unknown' character name
        mock_move_api.assert_called_once()
        call_args = mock_move_api.call_args
        self.assertEqual(call_args[1]['name'], 'unknown')
    
    @patch('src.controller.actions.base.movement.move_character_api')
    def test_execute_movement_no_response_data(self, mock_move_api):
        """Test movement execution when API returns no response."""
        # Mock None response
        mock_move_api.return_value = None
        
        result = self.action.execute_movement(self.mock_client, 10, 20)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Movement failed: No response data")
        self.assertEqual(result.data['target_x'], 10)
        self.assertEqual(result.data['target_y'], 20)
    
    @patch('src.controller.actions.base.movement.move_character_api')
    def test_execute_movement_already_at_destination(self, mock_move_api):
        """Test movement execution when already at destination."""
        # Mock 490 error
        mock_move_api.side_effect = Exception("490: Already at destination")
        
        # Set up context for the knowledge base refresh
        context = ActionContext()
        context.knowledge_base = MockKnowledgeBase()
        self.action._context = context
        
        result = self.action.execute_movement(
            self.mock_client, 
            10, 
            20,
            {'character_name': 'TestChar'}
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Already at destination (10, 20)")
        self.assertFalse(result.data['moved'])
        self.assertTrue(result.data['already_at_destination'])
        self.assertTrue(result.data['movement_completed'])
        self.assertEqual(result.data['current_x'], 10)
        self.assertEqual(result.data['current_y'], 20)
    
    @patch('src.controller.actions.base.movement.move_character_api')
    def test_execute_movement_general_error(self, mock_move_api):
        """Test movement execution with general error."""
        # Mock general error
        mock_move_api.side_effect = Exception("Connection timeout")
        
        result = self.action.execute_movement(self.mock_client, 10, 20)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Movement failed: Connection timeout")
        self.assertEqual(result.data['target_x'], 10)
        self.assertEqual(result.data['target_y'], 20)
    
    def test_execute_no_coordinates(self):
        """Test execute when no coordinates are provided."""
        context = MockActionContext(character_name="TestChar")
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "No valid coordinates provided")
        self.assertIsNone(result.data['provided_x'])
        self.assertIsNone(result.data['provided_y'])
    
    @patch('src.controller.actions.base.movement.move_character_api')
    def test_execute_success(self, mock_move_api):
        """Test successful execute method."""
        # Mock response
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.cooldown = 3
        # Mock character position in response
        mock_response.data.character = Mock()
        mock_response.data.character.x = 15
        mock_response.data.character.y = 25
        mock_move_api.return_value = mock_response
        
        context = MockActionContext(
            character_name="TestChar",
            target_x=15,
            target_y=25
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Moved to (15, 25)")
        self.assertEqual(result.data['character_name'], 'TestChar')
        
        # Verify context was stored
        self.assertEqual(self.action._context, context)
    
    @patch('src.controller.actions.base.movement.move_character_api')
    def test_execute_movement_validation_failure(self, mock_move_api):
        """Test movement execution when character doesn't reach target position."""
        # Mock response where character ends up at different location
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.cooldown = 2
        # Mock character position that doesn't match target
        mock_response.data.character = Mock()
        mock_response.data.character.x = 5  # Target is (10, 20)
        mock_response.data.character.y = 10  # Character ended up at (5, 10)
        mock_move_api.return_value = mock_response
        
        # Execute movement
        result = self.action.execute_movement(
            self.mock_client, 
            10,  # target_x
            20,  # target_y
            {'character_name': 'TestChar'}
        )
        
        # Should fail due to position validation
        self.assertFalse(result.success)
        self.assertIn("Movement validation failed", result.error)
        self.assertEqual(result.data['target_x'], 10)
        self.assertEqual(result.data['target_y'], 20)
        self.assertEqual(result.data['actual_x'], 5)
        self.assertEqual(result.data['actual_y'], 10)
        self.assertTrue(result.data['movement_failed'])
    
    def test_repr(self):
        """Test __repr__ method."""
        self.assertEqual(repr(self.action), "MovementActionBase()")


if __name__ == '__main__':
    unittest.main()