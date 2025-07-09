"""Unit tests for ActionFactory metaprogramming approach."""

import unittest
from unittest.mock import Mock, patch

from src.controller.action_factory import ActionExecutorConfig, ActionFactory
from src.controller.actions.base import ActionBase, ActionResult
from src.lib.action_context import ActionContext

from test.fixtures import create_mock_client
from test.test_base import UnifiedContextTestBase


class MockAction(ActionBase):
    """Mock action class for testing."""
    
    conditions = {'test_condition': True}
    reactions = {'test_reaction': True}
    weight = 1.5
    
    def __init__(self):
        super().__init__()
    
    def execute(self, client, context):
        # Use context to get parameters
        return ActionResult(
            success=True,
            data={
                'param1': getattr(context, 'param1', None),
                'param2': getattr(context, 'param2', None)
            }
        )


class TestActionFactory(UnifiedContextTestBase):
    """Test cases for ActionFactory class."""
    
    def setUp(self) -> None:
        """Set up test fixtures before each test method."""
        super().setUp()
        self.factory = ActionFactory()
        self.mock_client = create_mock_client()
    
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
        config = ActionExecutorConfig(action_class=MockAction)
        self.factory.register_action('test_action', config)
        
        # Create action with context
        action = self.factory.create_action('test_action', self.context)
        
        self.assertIsNotNone(action)
        self.assertIsInstance(action, MockAction)
    
    # Removed test_create_action_with_defaults - no longer applicable with unified context
    
    def test_create_action_with_context(self) -> None:
        """Test action creation and execution with context values."""
        config = ActionExecutorConfig(action_class=MockAction)
        self.factory.register_action('test_action', config)
        
        # Set context values
        self.context.param1 = 'from_context'
        self.context.param2 = 42
        
        action = self.factory.create_action('test_action', self.context)
        self.assertIsNotNone(action)
        
        # Execute and verify context values are used
        result = action.execute(self.mock_client, self.context)
        self.assertEqual(result.data['param1'], 'from_context')
        self.assertEqual(result.data['param2'], 42)
    
    # Removed test_create_action_missing_required_param - actions no longer have required constructor params
    
    def test_create_action_unknown_action(self) -> None:
        """Test that creating unknown action returns None."""
        action = self.factory.create_action('unknown_action', {})
        self.assertIsNone(action)
    
    def test_execute_action(self) -> None:
        """Test complete action execution through factory."""
        config = ActionExecutorConfig(action_class=MockAction)
        self.factory.register_action('test_action', config)
        
        # Set context values
        self.context.param1 = 'executed'
        self.context.param2 = 100
        
        result = self.factory.execute_action('test_action', self.mock_client, self.context)
        
        self.assertTrue(result.success)
        self.assertIsNotNone(result.data)
        self.assertEqual(result.data['param1'], 'executed')
        self.assertEqual(result.data['param2'], 100)
    
    def test_execute_action_failure(self) -> None:
        """Test action execution failure handling."""
        # Don't register the action
        result = self.factory.execute_action('unknown_action', self.mock_client, self.context)
        
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
    
    # Removed test_register_action_from_yaml - method is a placeholder only
    
    # Removed test_register_action_from_yaml_missing_class_path - YAML registration not implemented
    
    # Removed test_action_with_preprocessors - preprocessors no longer used with unified context
    
    def test_move_action_integration(self) -> None:
        """Test that default move action can be created and executed."""
        # Set context for move action
        self.context.character_name = 'test_char'
        self.context.x = 5
        self.context.y = 10
        
        action = self.factory.create_action('move', self.context)
        self.assertIsNotNone(action)
    
    def test_attack_action_integration(self) -> None:
        """Test that default attack action can be created."""
        # Set context for attack action  
        self.context.character_name = 'test_char'
        
        action = self.factory.create_action('attack', self.context)
        self.assertIsNotNone(action)
    
    def test_find_monsters_action_integration(self) -> None:
        """Test that default find_monsters action can be created."""
        # Set context for find_monsters action
        self.context.character_x = 0
        self.context.character_y = 0
        self.context.search_radius = 15
        self.context.monster_types = ['chicken']
        self.context.character_level = 5
        self.context.level_range = 3
        
        action = self.factory.create_action('find_monsters', self.context)
        self.assertIsNotNone(action)


if __name__ == '__main__':
    unittest.main()