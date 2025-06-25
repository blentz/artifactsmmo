"""Unit tests for ActionFactory metaprogramming approach."""

import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

from src.controller.action_factory import ActionFactory, ActionExecutorConfig
from src.controller.actions.base import ActionBase


class MockAction(ActionBase):
    """Mock action class for testing."""
    
    conditions = {'test_condition': True}
    reactions = {'test_reaction': True}
    weights = {'mock': 1.5}
    
    def __init__(self, param1: str, param2: int = 10):
        super().__init__()
        self.param1 = param1
        self.param2 = param2
    
    def execute(self, client, **kwargs):
        return {'success': True, 'param1': self.param1, 'param2': self.param2}


class TestActionFactory(unittest.TestCase):
    """Test cases for ActionFactory class."""
    
    def setUp(self) -> None:
        """Set up test fixtures before each test method."""
        self.factory = ActionFactory()
        self.mock_client = Mock()
    
    def test_factory_initialization(self) -> None:
        """Test that factory initializes with default actions."""
        available_actions = self.factory.get_available_actions()
        
        # Check that default actions are registered
        expected_actions = ['move', 'attack', 'rest', 'map_lookup', 'find_monsters']
        for action in expected_actions:
            self.assertIn(action, available_actions)
    
    def test_register_action(self) -> None:
        """Test registering a new action configuration."""
        config = ActionExecutorConfig(
            action_class=MockAction,
            constructor_params={'param1': 'test_param', 'param2': 'optional_param'}
        )
        
        self.factory.register_action('test_action', config)
        self.assertTrue(self.factory.is_action_registered('test_action'))
        self.assertIn('test_action', self.factory.get_available_actions())
    
    def test_create_action_success(self) -> None:
        """Test successful action creation."""
        # Register test action
        config = ActionExecutorConfig(
            action_class=MockAction,
            constructor_params={'param1': 'test_param', 'param2': 'optional_param'}
        )
        self.factory.register_action('test_action', config)
        
        # Create action with data
        action_data = {'test_param': 'hello', 'optional_param': 25}
        action = self.factory.create_action('test_action', action_data)
        
        self.assertIsNotNone(action)
        self.assertIsInstance(action, MockAction)
        self.assertEqual(action.param1, 'hello')
        self.assertEqual(action.param2, 25)
    
    def test_create_action_with_defaults(self) -> None:
        """Test action creation with default parameters."""
        config = ActionExecutorConfig(
            action_class=MockAction,
            constructor_params={'param1': 'test_param'}  # param2 will use default
        )
        self.factory.register_action('test_action', config)
        
        action_data = {'test_param': 'hello'}
        action = self.factory.create_action('test_action', action_data)
        
        self.assertIsNotNone(action)
        self.assertEqual(action.param1, 'hello')
        self.assertEqual(action.param2, 10)  # Default value
    
    def test_create_action_with_context(self) -> None:
        """Test action creation with context values."""
        config = ActionExecutorConfig(
            action_class=MockAction,
            constructor_params={'param1': 'context_value', 'param2': 'data_value'}
        )
        self.factory.register_action('test_action', config)
        
        action_data = {'data_value': 42}
        context = {'context_value': 'from_context'}
        action = self.factory.create_action('test_action', action_data, context)
        
        self.assertIsNotNone(action)
        self.assertEqual(action.param1, 'from_context')
        self.assertEqual(action.param2, 42)
    
    def test_create_action_missing_required_param(self) -> None:
        """Test action creation fails with missing required parameter."""
        config = ActionExecutorConfig(
            action_class=MockAction,
            constructor_params={'param1': 'missing_param'}
        )
        self.factory.register_action('test_action', config)
        
        action_data = {}  # Missing required parameter
        action = self.factory.create_action('test_action', action_data)
        
        self.assertIsNone(action)
    
    def test_create_action_unknown_action(self) -> None:
        """Test that creating unknown action returns None."""
        action = self.factory.create_action('unknown_action', {})
        self.assertIsNone(action)
    
    def test_execute_action(self) -> None:
        """Test complete action execution through factory."""
        config = ActionExecutorConfig(
            action_class=MockAction,
            constructor_params={'param1': 'test_param', 'param2': 'optional_param'}
        )
        self.factory.register_action('test_action', config)
        
        action_data = {'test_param': 'executed', 'optional_param': 100}
        success, response = self.factory.execute_action('test_action', action_data, self.mock_client)
        
        self.assertTrue(success)
        self.assertIsNotNone(response)
        self.assertEqual(response['param1'], 'executed')
        self.assertEqual(response['param2'], 100)
    
    def test_execute_action_failure(self) -> None:
        """Test action execution failure handling."""
        # Don't register the action
        success, response = self.factory.execute_action('unknown_action', {}, self.mock_client)
        
        self.assertFalse(success)
        self.assertIsNone(response)
    
    @patch('src.controller.action_factory.importlib.import_module')
    def test_register_action_from_yaml(self, mock_import) -> None:
        """Test registering action from YAML configuration."""
        # Mock the import
        mock_module = Mock()
        mock_module.MockAction = MockAction
        mock_import.return_value = mock_module
        
        yaml_config = {
            'class_path': 'test.module.MockAction',
            'constructor_params': {'param1': 'yaml_param'}
        }
        
        self.factory.register_action_from_yaml('yaml_action', yaml_config)
        self.assertTrue(self.factory.is_action_registered('yaml_action'))
    
    def test_register_action_from_yaml_missing_class_path(self) -> None:
        """Test that YAML registration fails without class_path."""
        yaml_config = {'constructor_params': {'param1': 'test'}}
        
        with self.assertRaises(ValueError):
            self.factory.register_action_from_yaml('invalid_action', yaml_config)
    
    def test_action_with_preprocessors(self) -> None:
        """Test action creation with parameter preprocessors."""
        def uppercase_preprocessor(value):
            return value.upper() if isinstance(value, str) else value
        
        config = ActionExecutorConfig(
            action_class=MockAction,
            constructor_params={'param1': 'test_param'},
            preprocessors={'param1': uppercase_preprocessor}
        )
        self.factory.register_action('test_action', config)
        
        action_data = {'test_param': 'hello'}
        action = self.factory.create_action('test_action', action_data)
        
        self.assertIsNotNone(action)
        self.assertEqual(action.param1, 'HELLO')
    
    def test_move_action_integration(self) -> None:
        """Test that default move action can be created and executed."""
        action_data = {
            'character_name': 'test_char',
            'x': 5,
            'y': 10
        }
        
        action = self.factory.create_action('move', action_data)
        self.assertIsNotNone(action)
        self.assertEqual(action.char_name, 'test_char')
        self.assertEqual(action.x, 5)
        self.assertEqual(action.y, 10)
    
    def test_attack_action_integration(self) -> None:
        """Test that default attack action can be created."""
        action_data = {'character_name': 'test_char'}
        
        action = self.factory.create_action('attack', action_data)
        self.assertIsNotNone(action)
        self.assertEqual(action.char_name, 'test_char')
    
    def test_find_monsters_action_integration(self) -> None:
        """Test that default find_monsters action can be created."""
        action_data = {
            'character_x': 0,
            'character_y': 0,
            'search_radius': 15,
            'monster_types': ['chicken'],
            'character_level': 5,
            'level_range': 3
        }
        
        action = self.factory.create_action('find_monsters', action_data)
        self.assertIsNotNone(action)
        self.assertEqual(action.character_x, 0)
        self.assertEqual(action.character_y, 0)
        self.assertEqual(action.search_radius, 15)
        self.assertEqual(action.monster_types, ['chicken'])
        self.assertEqual(action.character_level, 5)
        self.assertEqual(action.level_range, 3)


if __name__ == '__main__':
    unittest.main()