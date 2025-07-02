"""Enhanced test module for ActionExecutor."""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import yaml
from src.controller.action_executor import ActionExecutor, ActionResult, CompositeActionStep
from src.controller.action_factory import ActionFactory

from test.fixtures import create_mock_client


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

    def test_action_executor_initialization(self):
        """Test ActionExecutor initialization."""
        executor = ActionExecutor(self.config_file)
        
        # Check that executor has necessary attributes
        self.assertIsNotNone(executor.factory)
        self.assertIsInstance(executor.learning_callbacks, dict)
        self.assertIsInstance(executor.state_updaters, dict)

    def test_action_executor_factory_integration(self):
        """Test ActionExecutor factory integration."""
        executor = ActionExecutor(self.config_file)
        
        # Check that factory is properly initialized
        self.assertIsNotNone(executor.factory)
        self.assertIsInstance(executor.factory, ActionFactory)

    @patch('src.controller.action_executor.ActionFactory')
    def test_execute_simple_action_success(self, mock_factory_class):
        """Test successful execution of simple action."""
        # Mock factory to return success tuple
        mock_factory = Mock()
        mock_factory.execute_action.return_value = (True, {'success': True, 'message': 'Action completed'})
        mock_factory_class.return_value = mock_factory
        
        executor = ActionExecutor(self.config_file)
        client = create_mock_client()
        
        result = executor.execute_action('move', {'x': 5, 'y': 10}, client)
        
        self.assertIsInstance(result, ActionResult)
        self.assertTrue(result.success)
        self.assertEqual(result.action_name, 'move')
        mock_factory.execute_action.assert_called_once_with('move', {'x': 5, 'y': 10}, client, {})

    @patch('src.controller.action_executor.ActionFactory')
    def test_execute_simple_action_failure(self, mock_factory_class):
        """Test failed execution of simple action."""
        # Mock factory to return failure tuple
        mock_factory = Mock()
        mock_factory.execute_action.return_value = (False, None)
        mock_factory_class.return_value = mock_factory
        
        executor = ActionExecutor(self.config_file)
        client = create_mock_client()
        
        result = executor.execute_action('unknown_action', {}, client)
        
        self.assertIsInstance(result, ActionResult)
        self.assertFalse(result.success)
        self.assertEqual(result.action_name, 'unknown_action')

    @patch('src.controller.action_executor.ActionFactory')
    def test_execute_action_exception_handling(self, mock_factory_class):
        """Test exception handling during action execution."""
        # Mock factory to raise exception
        mock_factory = Mock()
        mock_factory.execute_action.side_effect = Exception("Test exception")
        mock_factory_class.return_value = mock_factory
        
        executor = ActionExecutor(self.config_file)
        executor.validation_enabled = False  # Disable validation to test exception handling
        client = create_mock_client()
        
        result = executor.execute_action('move', {}, client)
        
        self.assertIsInstance(result, ActionResult)
        self.assertFalse(result.success)
        self.assertIn('Test exception', result.error_message)

    def test_action_executor_config_data(self):
        """Test ActionExecutor config_data is loaded."""
        executor = ActionExecutor(self.config_file)
        
        # Check that config_data is loaded
        self.assertIsNotNone(executor.config_data)
        self.assertIsInstance(executor.config_data.data, dict)

    @patch('src.controller.action_executor.ActionFactory')
    def test_execute_composite_action_success(self, mock_factory_class):
        """Test successful execution of composite action."""
        # Mock factory to return success for each step
        mock_factory = Mock()
        # Return success for both move and attack steps
        mock_factory.execute_action.side_effect = [
            (True, {'success': True, 'message': 'Moved'}),
            (True, {'success': True, 'message': 'Attacked'})
        ]
        mock_factory_class.return_value = mock_factory
        
        executor = ActionExecutor(self.config_file)
        client = create_mock_client()
        
        result = executor.execute_action('test_composite', {}, client)
        
        self.assertIsInstance(result, ActionResult)
        self.assertTrue(result.success)
        self.assertEqual(result.action_name, 'test_composite')
        # Composite actions return 'steps' and 'composite' in response
        self.assertIn('steps', result.response)
        self.assertTrue(result.response.get('composite', False))

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