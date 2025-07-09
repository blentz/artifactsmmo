"""Unit tests for ActionExecutor YAML-driven execution."""

import os
import tempfile
from unittest.mock import Mock, patch

import yaml
from src.controller.action_executor import ActionExecutor
from src.controller.actions.base import ActionResult

from test.fixtures import create_mock_client
from test.test_base import UnifiedContextTestBase


class TestActionExecutor(UnifiedContextTestBase):
    """Test cases for ActionExecutor class."""
    
    def setUp(self) -> None:
        """Set up test fixtures before each test method."""
        super().setUp()
        # Create temporary config file
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, 'test_action_configurations.yaml')
        
        # Create test configuration
        test_config = {
            'action_configurations': {
                'test_action': {
                    'type': 'builtin',
                    'description': 'Test action for unit tests'
                }
            }
        }
        
        with open(self.config_file, 'w') as f:
            yaml.dump(test_config, f)
        
        self.executor = ActionExecutor(self.config_file)
        self.mock_client = create_mock_client()
    
    def tearDown(self) -> None:
        """Clean up test fixtures after each test method."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_executor_initialization(self) -> None:
        """Test that executor initializes correctly."""
        self.assertIsNotNone(self.executor.factory)
        self.assertIsNotNone(self.executor.config_data)
    
    def test_execute_simple_action(self) -> None:
        """Test executing a simple action through executor."""
        from src.lib.state_parameters import StateParameters
        
        # Set up context with unified state using StateParameters
        self.context.set(StateParameters.CHARACTER_NAME, 'test_char')
        self.context.set(StateParameters.TARGET_X, 5)
        self.context.set(StateParameters.TARGET_Y, 10)
        self.context.character_state = Mock(name='test_char')
        
        # Mock the factory execution
        with patch.object(self.executor.factory, 'execute_action') as mock_execute:
            mock_execute.return_value = ActionResult(success=True, data={'success': True}, action_name='move')
            
            result = self.executor.execute_action('move', self.mock_client, self.context)
            
            self.assertIsInstance(result, ActionResult)
            self.assertTrue(result.success)
            self.assertEqual(result.action_name, 'move')
            self.assertIsNotNone(result.data)
    
    def test_execute_action_failure(self) -> None:
        """Test handling of action execution failure."""
        with patch.object(self.executor.factory, 'execute_action') as mock_execute:
            mock_execute.return_value = ActionResult(success=False, error='Action failed', action_name='unknown')
            
            result = self.executor.execute_action('unknown', self.mock_client, self.context)
            
            self.assertIsInstance(result, ActionResult)
            self.assertFalse(result.success)
            self.assertEqual(result.action_name, 'unknown')
    
    # Composite actions have been deprecated and removed
    # Tests for _is_composite_action, _execute_composite_action, and _check_step_conditions
    # have been removed as they test deprecated functionality
    
    # Special hunt actions have been deprecated and removed
    # Hunt functionality should now go through proper GOAP actions instead of special handling
    # Tests for _execute_hunt_action have been removed
    
    def test_handle_learning_callbacks(self) -> None:
        """Test learning callback handling."""
        # Mock controller with learning methods
        mock_controller = Mock()
        mock_response = Mock()
        mock_response.data.character.x = 5
        mock_response.data.character.y = 10
        self.context.controller = mock_controller
        
        # Test move learning callback
        self.executor._handle_learning_callbacks('move', mock_response, self.context)
        mock_controller.learn_from_map_exploration.assert_called_once_with(5, 10, mock_response)
    
    def test_handle_learning_callbacks_combat(self) -> None:
        """Test combat learning callback handling."""
        mock_controller = Mock()
        mock_response = Mock()
        mock_response.data.fight.monster = {'code': 'chicken'}
        mock_response.data.fight.result = 'win'
        mock_response.data.fight.xp = 25
        mock_response.data.fight.gold = 10
        mock_response.data.fight.drops = []
        mock_response.data.fight.turns = 3
        
        self.context.controller = mock_controller
        self.context.pre_combat_hp = 80
        
        self.executor._handle_learning_callbacks('attack', mock_response, self.context)
        
        # Verify the call was made with the response (simplified callback)
        args, kwargs = mock_controller.learn_from_combat.call_args
        self.assertEqual(args[0], mock_response)  # response object passed directly
    
    def test_update_state(self) -> None:
        """Test state update handling - executor should not do parameter mapping."""
        mock_controller = Mock()
        mock_controller.get_current_world_state.return_value = {}
        mock_controller.update_world_state = Mock()
        
        # Test data
        action_result = ActionResult(success=True, data={'status': 'completed'}, action_name='move')
        
        # Test the post-execution handler - should not crash
        self.executor.apply_post_execution_updates('move', action_result, mock_controller, self.context)
        
        # Verify no errors occurred - the executor should handle this gracefully
        # Actions are responsible for their own context updates, not the executor
        self.assertTrue(True)  # Test passes if no exception is raised
    
    def test_get_available_actions(self) -> None:
        """Test getting available actions from factory."""
        available = self.executor.get_available_actions()
        
        # Should include core factory actions
        self.assertIn('move', available)
        self.assertIn('attack', available)
        
        # Should have a reasonable number of actions (at least 10)
        self.assertGreater(len(available), 10)
        
        # Should not include deprecated composite actions
        self.assertNotIn('test_composite', available)
    
    def test_reload_configuration(self) -> None:
        """Test configuration reloading."""
        # Add new action to config file
        updated_config = {
            'action_configurations': {
                'new_action': {
                    'type': 'builtin',
                    'description': 'Newly added action'
                }
            }
        }
        
        with open(self.config_file, 'w') as f:
            yaml.dump(updated_config, f)
        
        # Create a new executor with the updated config to simulate reload
        new_executor = ActionExecutor(self.config_file)
        
        # Verify config was loaded with new action
        configs = new_executor.config_data.data.get('action_configurations', {})
        self.assertIn('new_action', configs)
        # Verify old test_action is no longer present
        self.assertNotIn('test_action', configs)
    
    def test_register_callbacks(self) -> None:
        """Test registering learning callbacks and state updaters."""
        mock_callback = Mock()
        mock_updater = Mock()
        
        self.executor.register_learning_callback('test_action', mock_callback)
        self.executor.register_state_updater('test_action', mock_updater)
        
        self.assertEqual(self.executor.learning_callbacks['test_action'], mock_callback)
        self.assertEqual(self.executor.state_updaters['test_action'], mock_updater)


if __name__ == '__main__':
    unittest.main()