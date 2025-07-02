"""Unit tests for ActionExecutor YAML-driven execution."""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import yaml
from src.controller.action_executor import ActionExecutor, ActionResult

from test.fixtures import create_mock_client


class TestActionExecutor(unittest.TestCase):
    """Test cases for ActionExecutor class."""
    
    def setUp(self) -> None:
        """Set up test fixtures before each test method."""
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
            },
            'composite_actions': {
                'test_composite': {
                    'description': 'Test composite action',
                    'steps': [
                        {
                            'name': 'step1',
                            'action': 'move',
                            'required': True,
                            'params': {'x': 5, 'y': 10}
                        },
                        {
                            'name': 'step2', 
                            'action': 'attack',
                            'required': False,
                            'conditions': {'monster_found': True}
                        }
                    ]
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
        action_data = {'character_name': 'test_char', 'x': 5, 'y': 10}
        context = {'character_state': Mock(name='test_char'), 'character_name': 'test_char'}
        
        # Mock the factory execution
        with patch.object(self.executor.factory, 'execute_action') as mock_execute:
            mock_execute.return_value = (True, {'success': True})
            
            result = self.executor.execute_action('move', action_data, self.mock_client, context)
            
            self.assertIsInstance(result, ActionResult)
            self.assertTrue(result.success)
            self.assertEqual(result.action_name, 'move')
            self.assertIsNotNone(result.response)
    
    def test_execute_action_failure(self) -> None:
        """Test handling of action execution failure."""
        action_data = {}
        
        with patch.object(self.executor.factory, 'execute_action') as mock_execute:
            mock_execute.return_value = (False, None)
            
            result = self.executor.execute_action('unknown', action_data, self.mock_client)
            
            self.assertIsInstance(result, ActionResult)
            self.assertFalse(result.success)
            self.assertEqual(result.action_name, 'unknown')
    
    def test_is_composite_action(self) -> None:
        """Test identification of composite actions."""
        self.assertTrue(self.executor._is_composite_action('test_composite'))
        self.assertFalse(self.executor._is_composite_action('move'))
        self.assertFalse(self.executor._is_composite_action('unknown'))
    
    def test_execute_composite_action(self) -> None:
        """Test execution of composite action with multiple steps."""
        action_data = {'character_name': 'test_char'}
        context = {'character_state': Mock(name='test_char')}
        
        # Mock step executions
        with patch.object(self.executor, 'execute_action') as mock_execute:
            # First call is the composite action itself (recursive), then the steps
            mock_execute.side_effect = [
                ActionResult(success=True, response={'step': 'move'}, action_name='move'),
                ActionResult(success=True, response={'step': 'attack'}, action_name='attack')
            ]
            
            result = self.executor._execute_composite_action('test_composite', action_data, self.mock_client, context)
            
            self.assertIsInstance(result, ActionResult)
            self.assertTrue(result.success)
            self.assertEqual(result.action_name, 'test_composite')
            self.assertIn('composite', result.response)
    
    def test_resolve_parameter_templates(self) -> None:
        """Test parameter template resolution."""
        params = {
            'radius': '${action_data.search_radius:15}',
            'name': '${context.character_name:default}',
            'static': 'value'
        }
        action_data = {'search_radius': 20}
        context = {'character_name': 'hero'}
        
        resolved = self.executor._resolve_parameter_templates(params, action_data, context)
        
        self.assertEqual(resolved['radius'], 20)
        self.assertEqual(resolved['name'], 'hero')
        self.assertEqual(resolved['static'], 'value')
    
    def test_resolve_parameter_templates_defaults(self) -> None:
        """Test parameter template resolution with defaults."""
        params = {
            'missing': '${action_data.missing_key:42}',
            'no_default': '${context.missing}'
        }
        action_data = {}
        context = {}
        
        resolved = self.executor._resolve_parameter_templates(params, action_data, context)
        
        self.assertEqual(resolved['missing'], 42)
        self.assertIsNone(resolved['no_default'])
    
    def test_check_step_conditions(self) -> None:
        """Test step condition checking."""
        # Test empty conditions (should pass)
        self.assertTrue(self.executor._check_step_conditions({}, {}))
        
        # Test HP condition
        mock_char_state = Mock()
        mock_char_state.data = {'hp': 25, 'max_hp': 100}
        context = {'character_state': mock_char_state}
        
        # HP is low (25%) - condition should pass
        self.assertTrue(self.executor._check_step_conditions({'hp_low': True}, context))
        
        # HP is not low - condition should fail
        mock_char_state.data = {'hp': 80, 'max_hp': 100}
        self.assertFalse(self.executor._check_step_conditions({'hp_low': True}, context))
    
    def test_execute_hunt_action(self) -> None:
        """Test special hunt action execution."""
        action_data = {'search_radius': 20}
        
        # Mock controller with intelligent search
        mock_controller = Mock()
        mock_controller.intelligent_monster_search.return_value = True
        
        context = {
            'controller': mock_controller,
            'character_state': Mock(name='test_char')
        }
        
        # Mock attack execution
        with patch.object(self.executor, 'execute_action') as mock_execute:
            mock_execute.return_value = ActionResult(success=True, response={'attack': 'success'}, action_name='attack')
            
            result = self.executor._execute_hunt_action(action_data, self.mock_client, context)
            
            self.assertTrue(result.success)
            self.assertEqual(result.action_name, 'hunt')
            mock_controller.intelligent_monster_search.assert_called_once_with(20)
    
    def test_execute_hunt_action_no_monsters(self) -> None:
        """Test hunt action when no monsters found."""
        action_data = {}
        
        mock_controller = Mock()
        mock_controller.intelligent_monster_search.return_value = False
        
        context = {'controller': mock_controller}
        
        result = self.executor._execute_hunt_action(action_data, self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.action_name, 'hunt')
        self.assertIn('No monsters found', result.error_message)
    
    def test_handle_learning_callbacks(self) -> None:
        """Test learning callback handling."""
        # Mock controller with learning methods
        mock_controller = Mock()
        mock_response = Mock()
        mock_response.data.character.x = 5
        mock_response.data.character.y = 10
        
        context = {'controller': mock_controller}
        
        # Test move learning callback
        self.executor._handle_learning_callbacks('move', mock_response, context)
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
        
        context = {
            'controller': mock_controller,
            'pre_combat_hp': 80
        }
        
        self.executor._handle_learning_callbacks('attack', mock_response, context)
        
        # Verify the call was made with the correct parameters including fight_data dict
        args, kwargs = mock_controller.learn_from_combat.call_args
        self.assertEqual(args[0], 'chicken')  # monster_code
        self.assertEqual(args[1], 'win')      # result
        self.assertEqual(args[2], 80)         # pre_combat_hp
        
        # Check that fight_data dict was passed and contains expected keys
        fight_data = args[3]
        self.assertIsInstance(fight_data, dict)
        self.assertIn('xp', fight_data)
        self.assertIn('gold', fight_data)
        self.assertIn('drops', fight_data)
        self.assertIn('turns', fight_data)
    
    def test_update_state(self) -> None:
        """Test state update handling via post-execution updates."""
        mock_controller = Mock()
        mock_controller.get_current_world_state.return_value = {}
        mock_controller.update_world_state = Mock()
        mock_controller.action_context = {}  # Initialize as empty dict
        
        action_result = {'success': True}
        context = {}
        
        # Test the new unified post-execution handler
        self.executor.apply_post_execution_updates('move', action_result, mock_controller, context)
        
        # Verify action context was updated
        self.assertIn('move', mock_controller.action_context)
        self.assertEqual(mock_controller.action_context['move']['result'], action_result)
    
    def test_get_available_actions(self) -> None:
        """Test getting available actions (simple + composite)."""
        available = self.executor.get_available_actions()
        
        # Should include factory actions
        self.assertIn('move', available)
        self.assertIn('attack', available)
        
        # Should include composite actions
        self.assertIn('test_composite', available)
    
    def test_reload_configuration(self) -> None:
        """Test configuration reloading."""
        # Add new action to config file
        updated_config = {
            'action_configurations': {
                'new_action': {
                    'type': 'builtin',
                    'description': 'Newly added action'
                }
            },
            'composite_actions': {}
        }
        
        with open(self.config_file, 'w') as f:
            yaml.dump(updated_config, f)
        
        # Create a new executor with the updated config to simulate reload
        new_executor = ActionExecutor(self.config_file)
        
        # Verify config was loaded with new action
        configs = new_executor.config_data.data.get('action_configurations', {})
        self.assertIn('new_action', configs)
        self.assertNotIn('test_composite', new_executor.config_data.data.get('composite_actions', {}))
    
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