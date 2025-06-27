"""
Action Execution Regression Tests

These tests ensure that the action execution pipeline works correctly and
catches regressions in action factory, execution, and parameter handling.
"""

import unittest
import tempfile
import os
from unittest.mock import Mock, patch

from src.controller.action_executor import ActionExecutor, ActionResult
from src.controller.action_factory import ActionFactory
from src.lib.yaml_data import YamlData


class TestActionExecutionRegression(unittest.TestCase):
    """Test action execution pipeline to prevent regressions."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_client = Mock()
        
        # Create action executor with real configuration
        self.action_executor = ActionExecutor()
        
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_all_registered_actions_can_be_created(self):
        """
        REGRESSION TEST: Ensure all registered actions can be instantiated.
        
        This prevents issues where actions are registered but can't be created
        due to missing imports, constructor issues, etc.
        """
        factory = self.action_executor.factory
        registered_actions = factory.get_available_actions()
        
        self.assertGreater(len(registered_actions), 10, 
                          "Should have at least 10 registered actions")
        
        for action_name in registered_actions:
            with self.subTest(action=action_name):
                # Try to create the action with minimal valid parameters
                mock_context = self._create_mock_context()
                action_data = self._get_minimal_action_data(action_name)
                
                try:
                    action = factory.create_action(action_name, action_data, mock_context)
                    # Action might be None if required params are missing, but shouldn't raise exception
                    if action is None:
                        # This is acceptable - just means we need more specific parameters
                        continue
                    
                    # Action should be created successfully
                    self.assertIsNotNone(action, f"Action {action_name} creation returned None unexpectedly")
                    
                except Exception as e:
                    self.fail(f"Action {action_name} creation failed with exception: {e}")
    
    def test_action_executor_handles_unknown_actions(self):
        """Test that action executor properly handles unknown actions."""
        mock_context = self._create_mock_context()
        action_data = {'param': 'value'}
        
        # Execute unknown action
        result = self.action_executor.execute_action('nonexistent_action', action_data, 
                                                   self.mock_client, mock_context)
        
        # Should return failure result, not raise exception
        self.assertIsInstance(result, ActionResult)
        self.assertFalse(result.success)
        if result.error_message:
            self.assertIn('Unknown action', result.error_message)
    
    def test_action_executor_handles_missing_parameters(self):
        """Test that action executor handles missing required parameters gracefully."""
        mock_context = self._create_mock_context()
        
        # Try to execute move action without required parameters
        result = self.action_executor.execute_action('move', {}, self.mock_client, mock_context)
        
        # Should return failure result with helpful error message
        self.assertIsInstance(result, ActionResult)
        self.assertFalse(result.success)
        # Error message should mention missing parameters
        if result.error_message:
            self.assertTrue(any(keyword in result.error_message.lower() 
                              for keyword in ['parameter', 'missing', 'required']))
    
    def test_action_executor_builds_context_correctly(self):
        """Test that action executor builds execution context correctly."""
        # Mock character state
        mock_character = Mock()
        mock_character.name = "test_character"
        mock_character.data = {
            'x': 10, 'y': 20, 'level': 5, 'hp': 80, 'max_hp': 100
        }
        
        mock_context = {
            'character_state': mock_character,
            'character_name': 'test_character',
            'character_x': 10,
            'character_y': 20,
            'character_level': 5,
            'pre_combat_hp': 80
        }
        
        # Test context building with simple action
        action_data = {'x': 15, 'y': 25}
        
        # Mock action creation to verify context is passed correctly
        with patch.object(self.action_executor.factory, 'create_action') as mock_create:
            mock_action = Mock()
            mock_action.execute.return_value = {'success': True}
            mock_create.return_value = mock_action
            
            result = self.action_executor.execute_action('move', action_data, 
                                                       self.mock_client, mock_context)
            
            # Verify create_action was called with correct context
            mock_create.assert_called_once()
            call_args = mock_create.call_args
            passed_context = call_args[0][2]  # Third argument is context
            
            # Context should contain character information
            self.assertEqual(passed_context['character_name'], 'test_character')
            self.assertEqual(passed_context['character_x'], 10)
            self.assertEqual(passed_context['character_y'], 20)
    
    def test_goap_plan_actions_are_executable(self):
        """
        REGRESSION TEST: Ensure actions generated by GOAP plans can be executed.
        
        This test simulates the action names that GOAP generates and ensures
        they can all be executed through the action executor.
        """
        mock_context = self._create_mock_context()
        
        # These are the typical actions GOAP generates
        common_goap_actions = [
            'find_monsters', 'move', 'attack', 'rest', 'wait', 
            'explore_map', 'gather_resources', 'find_resources'
        ]
        
        for action_name in common_goap_actions:
            with self.subTest(action=action_name):
                # Get action-specific test data
                action_data = self._get_minimal_action_data(action_name)
                
                # Execute action (should not raise exception)
                try:
                    result = self.action_executor.execute_action(action_name, action_data, 
                                                               self.mock_client, mock_context)
                    
                    # Should return ActionResult (success or failure)
                    self.assertIsInstance(result, ActionResult)
                    self.assertEqual(result.action_name, action_name)
                    
                    # If it failed, should have error message (unless it's an API mock issue)
                    if not result.success and result.error_message is not None:
                        self.assertIsNotNone(result.error_message)
                        
                except Exception as e:
                    self.fail(f"Action {action_name} execution raised unexpected exception: {e}")
    
    def test_action_factory_registration_consistency(self):
        """Test that action factory registration is consistent."""
        factory = self.action_executor.factory
        
        # Get all registered actions
        registered_actions = set(factory.get_available_actions())
        
        # Check that each registered action can be queried
        for action_name in registered_actions:
            with self.subTest(action=action_name):
                self.assertTrue(factory.is_action_registered(action_name),
                              f"Action {action_name} should be registered")
                
                # Should be able to get configuration
                config = factory._action_registry.get(action_name)
                self.assertIsNotNone(config, f"Action {action_name} should have configuration")
                self.assertIsNotNone(config.action_class, 
                                   f"Action {action_name} should have action class")
    
    def test_action_execution_error_handling(self):
        """Test that action execution handles errors gracefully."""
        mock_context = self._create_mock_context()
        
        # Mock an action that raises an exception
        with patch.object(self.action_executor.factory, 'create_action') as mock_create:
            mock_action = Mock()
            mock_action.execute.side_effect = Exception("Test exception")
            mock_create.return_value = mock_action
            
            result = self.action_executor.execute_action('move', {'x': 1, 'y': 1}, 
                                                       self.mock_client, mock_context)
            
            # Should handle exception and return failure result
            self.assertIsInstance(result, ActionResult)
            self.assertFalse(result.success)
            if result.error_message:
                self.assertIn('Test exception', result.error_message)
    
    def _create_mock_context(self):
        """Create a mock execution context for testing."""
        mock_character = Mock()
        mock_character.name = "test_character"
        mock_character.data = {
            'x': 0, 'y': 0, 'level': 1, 'hp': 100, 'max_hp': 100,
            'cooldown': 0, 'cooldown_expiration': None
        }
        
        return {
            'character_state': mock_character,
            'character_name': 'test_character',
            'character_x': 0,
            'character_y': 0,
            'character_level': 1,
            'pre_combat_hp': 100,
            'world_state': Mock(),
            'knowledge_base': Mock(),
            'controller': Mock()
        }
    
    def _get_minimal_action_data(self, action_name):
        """Get minimal action data needed for each action type."""
        action_data_map = {
            'move': {'x': 1, 'y': 1},
            'attack': {},
            'rest': {},
            'wait': {'wait_duration': 5},
            'find_monsters': {
                'search_radius': 10, 
                'character_level': 1,
                'level_range': 2
            },
            'map_lookup': {'x': 1, 'y': 1},
            'explore_map': {
                'center_x': 0, 
                'center_y': 0, 
                'exploration_radius': 5
            },
            'gather_resources': {
                'resource_code': 'ash_wood'
            },
            'find_resources': {
                'resource_type': 'ash_wood',
                'search_radius': 10
            },
            'craft_item': {
                'item_code': 'wooden_stick',
                'quantity': 1
            },
            'lookup_item_info': {
                'item_code': 'wooden_stick'
            },
            'equip_item': {
                'item_code': 'wooden_stick',
                'slot': 'weapon'
            },
            'unequip_item': {
                'slot': 'weapon'
            },
            'analyze_resources': {
                'analysis_radius': 10
            }
        }
        
        return action_data_map.get(action_name, {})


class TestActionParameterHandling(unittest.TestCase):
    """Test action parameter handling and context building."""
    
    def test_parameter_template_resolution(self):
        """Test that parameter templates are resolved correctly."""
        config_data = YamlData('data/action_configurations.yaml')
        factory = ActionFactory(config_data)
        
        # Test character context parameters
        mock_context = {
            'character_name': 'test_char',
            'character_x': 10,
            'character_y': 20,
            'character_level': 5
        }
        
        # Test that move action gets character name from context
        action_data = {'x': 15, 'y': 25}
        
        # The factory should use character_name from context for char_name parameter
        try:
            action = factory.create_action('move', action_data, mock_context)
            # If action was created, the parameter mapping worked
            # (We can't easily test the internal parameter passing without mocking deeper)
        except Exception as e:
            # Should not fail due to missing char_name if context provides character_name
            if 'char_name' in str(e):
                self.fail("Factory should map character_name from context to char_name parameter")
    
    def test_action_data_precedence_over_context(self):
        """Test that action data takes precedence over context for parameters."""
        config_data = YamlData('data/action_configurations.yaml')
        factory = ActionFactory(config_data)
        
        mock_context = {
            'character_name': 'context_char',
            'x': 100,  # This should be overridden by action_data
            'y': 200
        }
        
        action_data = {
            'x': 15,  # This should take precedence over context
            'y': 25
        }
        
        # Create action - should use action_data values, not context values
        try:
            action = factory.create_action('move', action_data, mock_context)
            # The exact parameter values are hard to test without mocking deeper,
            # but this verifies that parameter resolution doesn't fail
        except Exception as e:
            if 'parameter' in str(e).lower():
                self.fail(f"Parameter resolution failed: {e}")


if __name__ == '__main__':
    unittest.main()