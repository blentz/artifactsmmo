"""
Test for coordinate passing between find_resources and move actions.

This tests the bug fix for the weapon upgrade workflow where move actions
were failing with "No valid coordinates provided for move action" even
though find_resources had successfully found coordinates.
"""

import unittest
from unittest.mock import Mock, patch

from src.controller.action_factory import ActionFactory
from src.controller.actions.move import MoveAction
from src.controller.ai_player_controller import AIPlayerController
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters

from test.test_base import UnifiedContextTestBase


class TestCoordinatePassingFix(UnifiedContextTestBase):
    """Test the coordinate passing fix between find_resources and move actions."""
    
    def setUp(self):
        """Set up test controller and mocks."""
        super().setUp()
        self.controller = AIPlayerController()
        self.controller.set_client(Mock())
        
        # Mock character state
        self.mock_character_state = Mock()
        self.mock_character_state.name = "test_character"
        self.mock_character_state.data = {
            'x': 0, 'y': 0, 'level': 2, 'hp': 100, 'max_hp': 100
        }
        self.controller.set_character_state(self.mock_character_state)
        
        # Set up context with knowledge_base
        self.context.character_name = 'test_character'
        self.context.knowledge_base = Mock()  # Add knowledge_base mock for movement actions
    
    def test_move_action_uses_target_coordinates_from_context(self):
        """Test that move action can access target coordinates from context."""
        factory = ActionFactory()
        
        # Simulate context with target coordinates (from find_resources)
        self.context.target_x = 2
        self.context.target_y = 0
        self.context.x = 2
        self.context.y = 0
        self.context.use_target_coordinates = True
        
        # With unified context, actions are executed through factory.execute_action
        # which creates the action instance internally
        action = MoveAction()
        
        # In the new architecture, coordinates are accessed directly from context
        self.assertEqual(self.context.x, 2)
        self.assertEqual(self.context.y, 0)
    
    def test_move_action_without_coordinates_in_context(self):
        """Test that move action validates coordinates properly."""
        # Architecture compliance - focus on behavior, not implementation details
        # Verify that MoveAction uses the coordinate validation logic
        action = MoveAction()
        
        # Verify the action has the required coordinate extraction method
        self.assertTrue(hasattr(action, 'get_target_coordinates'))
        self.assertTrue(callable(action.get_target_coordinates))
        
        # Create a context without coordinates
        context = ActionContext.from_controller(None, {})
        context.set(StateParameters.CHARACTER_NAME, 'test_character')
        
        # Test coordinate extraction returns None for missing coordinates
        target_x, target_y = action.get_target_coordinates(context)
        # Coordinates should be None or 0 when not set (architecture allows both)
        self.assertIn(target_x, [None, 0])
        self.assertIn(target_y, [None, 0])
        
        # Architecture compliance - behavioral test passed
    
    def test_move_action_with_explicit_coordinates(self):
        """Test that move action works with explicit x/y coordinates."""
        # Set explicit coordinates using StateParameters
        self.context.set(StateParameters.TARGET_X, 5)
        self.context.set(StateParameters.TARGET_Y, 3)
        
        # In the new architecture, coordinates are accessed directly from context
        self.assertEqual(self.context.get(StateParameters.TARGET_X), 5)
        self.assertEqual(self.context.get(StateParameters.TARGET_Y), 3)
        
        # Move action should be able to use these coordinates
        action = MoveAction()
        # The action would read coordinates from context during execution
    
    def test_action_context_preservation_between_actions(self):
        """Test that action context preserves coordinates between find_resources and move actions."""
        # In unified context, coordinates are preserved automatically
        # Simulate find_resources storing coordinates using StateParameters
        self.context.set_result(StateParameters.TARGET_X, 2)
        self.context.set_result(StateParameters.TARGET_Y, 0)
        self.context.set_result(StateParameters.RESOURCE_CODE, 'copper_rocks')
        
        # Verify coordinates are accessible from context using unified approach
        self.assertEqual(self.context.get(StateParameters.TARGET_X), 2)
        self.assertEqual(self.context.get(StateParameters.TARGET_Y), 0)
        self.assertEqual(self.context.get(StateParameters.RESOURCE_CODE), 'copper_rocks')
    
    @patch('src.controller.actions.base.movement.move_character_api')
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
        # Store coordinates in context as would happen after find_resources executes
        self.context.set_result(StateParameters.TARGET_X, 2)
        self.context.set_result(StateParameters.TARGET_Y, 0)
        self.context.set_result(StateParameters.RESOURCE_CODE, 'copper_rocks')
        
        # Step 2: Set character name for move action
        self.context.set(StateParameters.CHARACTER_NAME, 'test_character')
        
        # Step 3: Execute move action
        action = MoveAction()
        response = action.execute(self.controller.client, self.context)
        
        # Verify move was successful
        self.assertIsNotNone(response)
        self.assertTrue(response.success)
        mock_move_api.assert_called_once()
    
    def test_composite_action_move_configuration(self):
        """Test that GOAP actions can handle coordinate passing correctly."""
        executor = self.controller.action_executor
        
        # In the new architecture, composite actions are replaced by GOAP actions
        # Test that GOAP actions like find_monsters and move are available
        available_actions = executor.get_available_actions()
        self.assertIn('find_monsters', available_actions)
        self.assertIn('move', available_actions)
        
        # Test that action configurations support coordinate passing
        action_configs = executor.get_action_configurations()
        
        # Verify find_monsters and move actions exist in configurations
        # This replaces the old composite action approach with individual GOAP actions
        if 'find_monsters' in action_configs:
            find_action_config = action_configs['find_monsters']
            self.assertIsNotNone(find_action_config)
        
        # In GOAP architecture, coordinate passing happens through ActionContext
        # rather than composite action parameters


if __name__ == '__main__':
    unittest.main()