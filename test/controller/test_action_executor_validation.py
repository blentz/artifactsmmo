"""Test module for ActionExecutor validation phase."""

import unittest
from unittest.mock import Mock, patch

from src.controller.action_executor import ActionExecutor
from src.controller.action_validator import ValidationError, ValidationResult

from test.fixtures import MockActionContext


class TestActionExecutorValidation(unittest.TestCase):
    """Test cases for ActionExecutor validation phase integration."""
    
    def setUp(self):
        """Set up test fixtures."""
        with patch('src.controller.action_executor.YamlData') as mock_yaml, \
             patch('src.controller.action_executor.ActionValidator') as mock_validator:
            mock_yaml.return_value.data = {
                'action_configurations': {},
                'composite_actions': {}
            }
            self.executor = ActionExecutor()
            self.mock_client = Mock()
            # Store reference to the mocked validator instance
            self.mock_validator = self.executor.validator
    
    def test_validation_phase_called(self):
        """Test that validation phase is called during action execution."""
        # Mock successful validation
        mock_validation_result = ValidationResult(is_valid=True)
        self.mock_validator.validate_action = Mock(return_value=mock_validation_result)
        
        # Mock factory execution to return ActionResult
        from src.controller.actions.base import ActionResult
        mock_result = ActionResult(success=True, message="Action completed", data={'success': True})
        self.executor.factory.execute_action = Mock(return_value=mock_result)
        
        # Create context
        context = MockActionContext(character_name="test_char")
        
        # Execute action
        result = self.executor.execute_action('equip', {'item_code': 'wooden_sword'}, self.mock_client, context)
        
        # Verify validation was called
        self.mock_validator.validate_action.assert_called_once()
        call_args = self.mock_validator.validate_action.call_args
        self.assertEqual(call_args[0][0], 'equip')  # action_name
        self.assertIn('item_code', call_args[0][1])  # params
        
        # Verify execution continued
        self.assertTrue(result.success)
    
    def test_validation_failure_stops_execution(self):
        """Test that validation failure prevents action execution."""
        # Mock failed validation
        validation_errors = [
            ValidationError("required_params", "Missing required parameters: item_code")
        ]
        mock_validation_result = ValidationResult(
            is_valid=False,
            errors=validation_errors
        )
        self.mock_validator.validate_action = Mock(return_value=mock_validation_result)
        
        # Mock factory execution (should not be called)
        self.executor.factory.execute_action = Mock()
        
        # Create context
        context = MockActionContext(character_name="test_char")
        
        # Execute action
        result = self.executor.execute_action('equip', {}, self.mock_client, context)
        
        # Verify validation was called
        self.mock_validator.validate_action.assert_called_once()
        
        # Verify execution was NOT called
        self.executor.factory.execute_action.assert_not_called()
        
        # Verify result indicates validation failure
        self.assertFalse(result.success)
        self.assertIn("Validation failed", result.error)
        self.assertIn("validation_errors", result.data)
        # Validation errors are stored in the data
        self.assertIsInstance(result.data['validation_errors'], list)
        self.assertGreater(len(result.data['validation_errors']), 0)
    
    def test_validation_disabled_flag(self):
        """Test that validation can be disabled via flag."""
        # Disable validation
        self.executor.validation_enabled = False
        
        # Mock factory execution to return ActionResult
        from src.controller.actions.base import ActionResult
        mock_result = ActionResult(success=True, message="Action completed", data={'success': True})
        self.executor.factory.execute_action = Mock(return_value=mock_result)
        
        # Create context
        context = MockActionContext(character_name="test_char")
        
        # Execute action with missing parameters
        result = self.executor.execute_action('equip', {}, self.mock_client, context)
        
        # Verify validation was NOT called
        # The validator should not be called since validation is disabled
        if hasattr(self.mock_validator, 'validate_action'):
            if isinstance(self.mock_validator.validate_action, Mock):
                self.mock_validator.validate_action.assert_not_called()
        
        # Verify execution was called despite missing params
        self.executor.factory.execute_action.assert_called_once()
    
    def test_nested_params_validation(self):
        """Test validation with nested params structure."""
        # Mock successful validation
        mock_validation_result = ValidationResult(is_valid=True)
        self.mock_validator.validate_action = Mock(return_value=mock_validation_result)
        
        # Mock factory execution to return ActionResult
        from src.controller.actions.base import ActionResult
        mock_result = ActionResult(success=True, message="Action completed", data={'success': True})
        self.executor.factory.execute_action = Mock(return_value=mock_result)
        
        # Create context
        context = MockActionContext(character_name="test_char")
        
        # Execute action with nested params
        action_data = {
            'params': {
                'item_code': 'wooden_sword',
                'slot': 'weapon'
            }
        }
        result = self.executor.execute_action('equip', action_data, self.mock_client, context)
        
        # Verify validation was called with flattened params
        call_args = self.executor.validator.validate_action.call_args
        validated_params = call_args[0][1]
        self.assertEqual(validated_params['item_code'], 'wooden_sword')
        self.assertEqual(validated_params['slot'], 'weapon')
        self.assertNotIn('params', validated_params)  # Nested structure flattened
    
    def test_validation_error_details_in_response(self):
        """Test that validation error details are included in response."""
        # Mock failed validation with multiple errors
        validation_errors = [
            ValidationError("required_params", "Missing required parameters: item_code", 
                          details={'missing': ['item_code']}),
            ValidationError("character_alive", "Character is not alive (HP is 0)",
                          details={'current_hp': 0})
        ]
        mock_validation_result = ValidationResult(
            is_valid=False,
            errors=validation_errors
        )
        self.mock_validator.validate_action = Mock(return_value=mock_validation_result)
        
        # Create context
        context = MockActionContext(character_name="test_char")
        
        # Execute action
        result = self.executor.execute_action('equip', {}, self.mock_client, context)
        
        # Verify error details in response
        self.assertFalse(result.success)
        self.assertIn('validation_errors', result.data)
        errors = result.data['validation_errors']
        self.assertEqual(len(errors), 2)
        
        # Check first error
        self.assertEqual(errors[0]['validator'], 'required_params')
        self.assertIn('item_code', errors[0]['message'])
        
        # Check second error
        self.assertEqual(errors[1]['validator'], 'character_alive')
        self.assertIn('HP is 0', errors[1]['message'])


if __name__ == '__main__':
    unittest.main()