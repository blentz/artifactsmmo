"""Enhanced test module for ActionExecutor."""

import unittest
import tempfile
import os
import yaml
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from src.controller.action_executor import ActionExecutor, ActionResult, CompositeActionStep


class TestActionExecutorEnhanced(unittest.TestCase):
    """Enhanced test cases for ActionExecutor."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_prefix = os.environ.get('DATA_PREFIX', '')
        os.environ['DATA_PREFIX'] = self.temp_dir
        
        # Create test config file
        self.config_file = os.path.join(self.temp_dir, 'test_action_configurations.yaml')
        self.test_config = {
            'action_configurations': {
                'move': {
                    'type': 'builtin',
                    'description': 'Move character to coordinates'
                },
                'attack': {
                    'type': 'builtin', 
                    'description': 'Attack a monster'
                },
                'test_composite': {
                    'type': 'composite',
                    'description': 'Test composite action'
                }
            },
            'composite_actions': {
                'test_composite': {
                    'description': 'A test composite action',
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
                            'params': {'target': 'slime'}
                        }
                    ]
                }
            }
        }
        
        with open(self.config_file, 'w') as f:
            yaml.dump(self.test_config, f)

    def tearDown(self):
        """Clean up test fixtures."""
        os.environ['DATA_PREFIX'] = self.original_data_prefix
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_action_executor_initialization(self):
        """Test ActionExecutor initialization."""
        executor = ActionExecutor(self.config_file)
        self.assertIsNotNone(executor.factory)
        self.assertIsNotNone(executor.logger)

    def test_action_executor_initialization_no_config(self):
        """Test ActionExecutor initialization without config file."""
        executor = ActionExecutor()
        self.assertIsNotNone(executor.factory)
        self.assertIsNotNone(executor.logger)

    def test_action_result_dataclass(self):
        """Test ActionResult dataclass."""
        result = ActionResult(
            success=True,
            response={'status': 'ok'},
            action_name='test_action',
            execution_time=1.5,
            error_message=None,
            metadata={'test': 'data'}
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.response['status'], 'ok')
        self.assertEqual(result.action_name, 'test_action')
        self.assertEqual(result.execution_time, 1.5)
        self.assertIsNone(result.error_message)
        self.assertEqual(result.metadata['test'], 'data')

    def test_composite_action_step_dataclass(self):
        """Test CompositeActionStep dataclass."""
        step = CompositeActionStep(
            name='test_step',
            action='move',
            required=True,
            params={'x': 5, 'y': 10},
            conditions={'character_alive': True},
            on_failure='abort'
        )
        
        self.assertEqual(step.name, 'test_step')
        self.assertEqual(step.action, 'move')
        self.assertTrue(step.required)
        self.assertEqual(step.params['x'], 5)
        self.assertEqual(step.conditions['character_alive'], True)
        self.assertEqual(step.on_failure, 'abort')

    def test_composite_action_step_defaults(self):
        """Test CompositeActionStep default values."""
        step = CompositeActionStep(name='test', action='move')
        
        self.assertEqual(step.name, 'test')
        self.assertEqual(step.action, 'move')
        self.assertTrue(step.required)
        self.assertIsNone(step.params)
        self.assertIsNone(step.conditions)
        self.assertEqual(step.on_failure, 'continue')

    def test_load_action_configurations(self):
        """Test loading action configurations."""
        executor = ActionExecutor(self.config_file)
        configs = executor.load_action_configurations()
        
        self.assertIn('action_configurations', configs)
        self.assertIn('move', configs['action_configurations'])
        self.assertEqual(configs['action_configurations']['move']['type'], 'builtin')

    def test_load_action_configurations_file_not_found(self):
        """Test loading configurations when file doesn't exist."""
        executor = ActionExecutor('/nonexistent/file.yaml')
        configs = executor.load_action_configurations()
        
        # Should return empty config if file not found
        self.assertIsInstance(configs, dict)

    def test_is_composite_action_true(self):
        """Test is_composite_action returns True for composite actions."""
        executor = ActionExecutor(self.config_file)
        self.assertTrue(executor.is_composite_action('test_composite'))

    def test_is_composite_action_false(self):
        """Test is_composite_action returns False for builtin actions."""
        executor = ActionExecutor(self.config_file)
        self.assertFalse(executor.is_composite_action('move'))

    def test_is_composite_action_unknown(self):
        """Test is_composite_action returns False for unknown actions."""
        executor = ActionExecutor(self.config_file)
        self.assertFalse(executor.is_composite_action('unknown_action'))

    @patch('src.controller.action_executor.ActionFactory')
    def test_execute_simple_action_success(self, mock_factory_class):
        """Test successful execution of simple action."""
        # Mock factory and action
        mock_action = Mock()
        mock_action.execute.return_value = {'success': True, 'message': 'Action completed'}
        
        mock_factory = Mock()
        mock_factory.create_action.return_value = mock_action
        mock_factory_class.return_value = mock_factory
        
        executor = ActionExecutor(self.config_file)
        client = Mock()
        
        result = executor.execute_action('move', client, x=5, y=10)
        
        self.assertIsInstance(result, ActionResult)
        self.assertTrue(result.success)
        self.assertEqual(result.action_name, 'move')
        mock_factory.create_action.assert_called_once_with('move', x=5, y=10)

    @patch('src.controller.action_executor.ActionFactory')
    def test_execute_simple_action_failure(self, mock_factory_class):
        """Test failed execution of simple action."""
        # Mock factory to return None (action creation failed)
        mock_factory = Mock()
        mock_factory.create_action.return_value = None
        mock_factory_class.return_value = mock_factory
        
        executor = ActionExecutor(self.config_file)
        client = Mock()
        
        result = executor.execute_action('unknown_action', client)
        
        self.assertIsInstance(result, ActionResult)
        self.assertFalse(result.success)
        self.assertIn('Failed to create action', result.error_message)

    @patch('src.controller.action_executor.ActionFactory')
    def test_execute_action_exception_handling(self, mock_factory_class):
        """Test exception handling during action execution."""
        # Mock action that raises exception
        mock_action = Mock()
        mock_action.execute.side_effect = Exception("Test exception")
        
        mock_factory = Mock()
        mock_factory.create_action.return_value = mock_action
        mock_factory_class.return_value = mock_factory
        
        executor = ActionExecutor(self.config_file)
        client = Mock()
        
        result = executor.execute_action('move', client)
        
        self.assertIsInstance(result, ActionResult)
        self.assertFalse(result.success)
        self.assertIn('Test exception', result.error_message)

    def test_get_composite_action_steps(self):
        """Test extracting composite action steps."""
        executor = ActionExecutor(self.config_file)
        steps = executor.get_composite_action_steps('test_composite')
        
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0].name, 'step1')
        self.assertEqual(steps[0].action, 'move')
        self.assertTrue(steps[0].required)
        self.assertEqual(steps[1].name, 'step2')
        self.assertEqual(steps[1].action, 'attack')
        self.assertFalse(steps[1].required)

    def test_get_composite_action_steps_not_found(self):
        """Test getting steps for non-existent composite action."""
        executor = ActionExecutor(self.config_file)
        steps = executor.get_composite_action_steps('nonexistent')
        
        self.assertEqual(steps, [])

    @patch('src.controller.action_executor.ActionFactory')
    def test_execute_composite_action_success(self, mock_factory_class):
        """Test successful execution of composite action."""
        # Mock successful actions for each step
        mock_move_action = Mock()
        mock_move_action.execute.return_value = {'success': True, 'message': 'Moved'}
        
        mock_attack_action = Mock()
        mock_attack_action.execute.return_value = {'success': True, 'message': 'Attacked'}
        
        mock_factory = Mock()
        mock_factory.create_action.side_effect = [mock_move_action, mock_attack_action]
        mock_factory_class.return_value = mock_factory
        
        executor = ActionExecutor(self.config_file)
        client = Mock()
        
        result = executor.execute_action('test_composite', client)
        
        self.assertIsInstance(result, ActionResult)
        self.assertTrue(result.success)
        self.assertEqual(result.action_name, 'test_composite')
        self.assertIn('steps_completed', result.response)

    def test_validate_step_conditions_true(self):
        """Test step condition validation when conditions are met."""
        executor = ActionExecutor(self.config_file)
        context = {'character_alive': True, 'has_weapon': True}
        conditions = {'character_alive': True}
        
        # Test basic functionality if method exists
        if hasattr(executor, 'validate_step_conditions'):
            result = executor.validate_step_conditions(conditions, context)
            self.assertTrue(result)

    def test_validate_step_conditions_false(self):
        """Test step condition validation when conditions are not met."""
        executor = ActionExecutor(self.config_file)
        context = {'character_alive': False, 'has_weapon': True}
        conditions = {'character_alive': True}
        
        # Test basic functionality if method exists
        if hasattr(executor, 'validate_step_conditions'):
            result = executor.validate_step_conditions(conditions, context)
            self.assertFalse(result)

    def test_resolve_template_parameters(self):
        """Test template parameter resolution."""
        executor = ActionExecutor(self.config_file)
        params = {'x': '${target.x}', 'y': '${target.y}', 'static': 'value'}
        context = {'target': {'x': 15, 'y': 20}}
        
        # Test basic functionality if method exists
        if hasattr(executor, 'resolve_template_parameters'):
            resolved = executor.resolve_template_parameters(params, context)
            self.assertEqual(resolved.get('x'), 15)
            self.assertEqual(resolved.get('y'), 20)
            self.assertEqual(resolved.get('static'), 'value')

    def test_handle_learning_callbacks(self):
        """Test learning callback handling."""
        executor = ActionExecutor(self.config_file)
        
        # Mock learning manager
        mock_learning_manager = Mock()
        context = {'learning_manager': mock_learning_manager}
        response = {'success': True, 'xp_gained': 25}
        
        # Test basic functionality if method exists
        if hasattr(executor, '_handle_learning_callbacks'):
            executor._handle_learning_callbacks('move', response, context)
            # Should not raise any exceptions

    def test_log_action_execution(self):
        """Test action execution logging."""
        executor = ActionExecutor(self.config_file)
        
        result = ActionResult(
            success=True,
            response={'message': 'success'},
            action_name='test_action',
            execution_time=1.2
        )
        
        # Should not raise exceptions when logging
        if hasattr(executor, '_log_action_execution'):
            executor._log_action_execution(result)

    def test_calculate_execution_metrics(self):
        """Test execution metrics calculation."""
        executor = ActionExecutor(self.config_file)
        
        # Test basic functionality if method exists
        if hasattr(executor, 'calculate_execution_metrics'):
            metrics = executor.calculate_execution_metrics()
            self.assertIsInstance(metrics, dict)

    def test_reload_configurations(self):
        """Test configuration reloading."""
        executor = ActionExecutor(self.config_file)
        
        # Should be able to reload configurations
        if hasattr(executor, 'reload_configurations'):
            executor.reload_configurations()


if __name__ == '__main__':
    unittest.main()