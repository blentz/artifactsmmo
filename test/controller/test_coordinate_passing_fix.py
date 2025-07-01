"""
Test for coordinate passing between find_resources and move actions.

This tests the bug fix for the weapon upgrade workflow where move actions
were failing with "No valid coordinates provided for move action" even
though find_resources had successfully found coordinates.
"""

import unittest
from unittest.mock import Mock, patch

from src.controller.action_factory import ActionFactory
from src.controller.ai_player_controller import AIPlayerController

from test.fixtures import MockActionContext


class TestCoordinatePassingFix(unittest.TestCase):
    """Test the coordinate passing fix between find_resources and move actions."""
    
    def setUp(self):
        """Set up test controller and mocks."""
        self.controller = AIPlayerController()
        self.controller.set_client(Mock())
        
        # Mock character state
        self.mock_character_state = Mock()
        self.mock_character_state.name = "test_character"
        self.mock_character_state.data = {
            'x': 0, 'y': 0, 'level': 2, 'hp': 100, 'max_hp': 100
        }
        self.controller.set_character_state(self.mock_character_state)
    
    def test_move_action_uses_target_coordinates_from_context(self):
        """Test that move action can access target coordinates from context."""
        factory = ActionFactory()
        
        # Simulate context with target coordinates (from find_resources)
        context = MockActionContext(
            character_name='test_character',
            target_x=2,
            target_y=0,
            x=2,
            y=0,
            use_target_coordinates=True
        )
        
        # Create move action
        action = factory.create_action('move', {}, context)
        
        self.assertIsNotNone(action)
        # Verify action can get target coordinates from context
        target_x, target_y = action.get_target_coordinates(context)
        self.assertEqual(target_x, 2)
        self.assertEqual(target_y, 0)
    
    def test_move_action_without_coordinates_in_context(self):
        """Test that move action returns None coordinates when no coordinates available."""
        factory = ActionFactory()
        
        # Context without target coordinates
        context = MockActionContext(
            character_name='test_character'
        )
        
        # Create move action
        action = factory.create_action('move', {}, context)
        
        self.assertIsNotNone(action)
        # Verify action returns None coordinates when not available
        target_x, target_y = action.get_target_coordinates(context)
        self.assertIsNone(target_x)
        self.assertIsNone(target_y)
    
    def test_move_action_with_explicit_coordinates(self):
        """Test that move action works with explicit x/y coordinates."""
        factory = ActionFactory()
        
        context = MockActionContext(
            character_name='test_character',
            x=5,
            y=3
        )
        
        action = factory.create_action('move', {}, context)
        
        self.assertIsNotNone(action)
        # Verify action can get explicit coordinates from context
        target_x, target_y = action.get_target_coordinates(context)
        self.assertEqual(target_x, 5)
        self.assertEqual(target_y, 3)
    
    def test_action_context_preservation_between_actions(self):
        """Test that action context preserves coordinates between find_resources and move actions."""
        # Simulate find_resources response with location
        find_response = {
            'success': True,
            'location': (2, 0),
            'resource_code': 'copper_rocks'
        }
        
        # Update action context from find_resources response
        self.controller._update_action_context_from_response('find_resources', find_response)
        
        # Check that coordinates were stored in action context
        self.assertIn('target_x', self.controller.action_context)
        self.assertIn('target_y', self.controller.action_context)
        self.assertEqual(self.controller.action_context['target_x'], 2)
        self.assertEqual(self.controller.action_context['target_y'], 0)
    
    @patch('src.controller.actions.movement_base.move_character_api')
    def test_complete_find_and_move_workflow(self, mock_move_api):
        """Test complete workflow: find_resources -> action_context -> move action."""
        # Setup mock for move API
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.character = Mock()
        mock_response.data.character.x = 2
        mock_response.data.character.y = 0
        mock_move_api.return_value = mock_response
        
        # Step 1: Simulate find_resources finding coordinates
        find_response = {
            'success': True,
            'location': (2, 0),
            'resource_code': 'copper_rocks'
        }
        
        # Step 2: Update action context (this happens in _execute_single_action)
        self.controller._update_action_context_from_response('find_resources', find_response)
        
        # Step 3: Build execution context for move action (includes action_context)
        context = self.controller._build_execution_context({'use_target_coordinates': True})
        
        # Step 4: Create move action through factory
        factory = ActionFactory()
        action = factory.create_action('move', {}, context)
        
        # Verify move action was created
        self.assertIsNotNone(action)
        
        # Step 5: Execute move action with MockActionContext
        action_context = MockActionContext(**context)
        response = action.execute(self.controller.client, action_context)
        
        # Verify move was successful
        self.assertIsNotNone(response)
        mock_move_api.assert_called_once()
    
    def test_composite_action_move_configuration(self):
        """Test that composite actions have move steps configured correctly."""
        executor = self.controller.action_executor
        
        # Check that find_and_move_to_monster composite action exists
        self.assertTrue(executor._is_composite_action('find_and_move_to_monster'))
        
        # Get the composite action configuration
        config = executor.config_data.data.get('composite_actions', {}).get('find_and_move_to_monster', {})
        steps = config.get('steps', [])
        
        # Find the move step
        move_step = None
        for step in steps:
            if step.get('action') == 'move':
                move_step = step
                break
        
        self.assertIsNotNone(move_step, "Move step not found in find_and_move_to_monster composite action")
        
        # Verify move step has use_target_coordinates set
        params = move_step.get('params', {})
        self.assertIn('use_target_coordinates', params)
        self.assertTrue(params['use_target_coordinates'])


if __name__ == '__main__':
    unittest.main()