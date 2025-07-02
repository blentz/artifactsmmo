"""Test module for Action Validator."""

import unittest
from unittest.mock import Mock, patch

from src.controller.action_validator import (
    ActionValidator,
    ValidationError,
    ValidationResult,
)


class TestActionValidator(unittest.TestCase):
    """Test cases for ActionValidator."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create validator with test configuration
        with patch('src.controller.action_validator.YamlData') as mock_yaml:
            mock_yaml.return_value.data = {
                'validation_rules': {
                    'global': [
                        {'type': 'required_context', 'fields': ['character_name']}
                    ],
                    'actions': {
                        'equip': [
                            {'type': 'required_params', 'params': ['item_code']},
                            {'type': 'valid_item', 'param': 'item_code'}
                        ],
                        'move': [
                            {'type': 'required_params', 'params': ['x', 'y']},
                            {'type': 'valid_coordinates', 'params': ['x', 'y']}
                        ]
                    }
                }
            }
            self.validator = ActionValidator()
    
    def test_validation_result_summary(self):
        """Test ValidationResult summary generation."""
        # Valid result
        result = ValidationResult(is_valid=True)
        self.assertEqual(result.summary, "Validation passed")
        
        # Invalid result with errors
        result = ValidationResult(
            is_valid=False,
            errors=[
                ValidationError("required_params", "Missing required parameters: item_code"),
                ValidationError("valid_item", "Invalid item code")
            ]
        )
        self.assertEqual(
            result.summary,
            "required_params: Missing required parameters: item_code; valid_item: Invalid item code"
        )
    
    def test_required_params_validator(self):
        """Test required_params validator."""
        # Missing parameter
        params = {'other': 'value'}
        rule = {'params': ['item_code']}
        context = Mock()
        
        error = self.validator._validate_required_params(params, rule, context)
        self.assertIsNotNone(error)
        self.assertEqual(error.validator, "required_params")
        self.assertIn("item_code", error.message)
        
        # Parameter present
        params = {'item_code': 'wooden_sword'}
        error = self.validator._validate_required_params(params, rule, context)
        self.assertIsNone(error)
        
        # Nested params
        params = {'params': {'item_code': 'wooden_sword'}}
        error = self.validator._validate_required_params(params, rule, context)
        self.assertIsNone(error)
    
    def test_required_context_validator(self):
        """Test required_context validator."""
        params = {}
        rule = {'fields': ['character_name', 'client']}
        
        # Missing fields in context object
        context = Mock()
        context.character_name = None
        context.client = Mock()
        
        error = self.validator._validate_required_context(params, rule, context)
        self.assertIsNotNone(error)
        self.assertIn("character_name", error.message)
        
        # All fields present
        context.character_name = "test_char"
        error = self.validator._validate_required_context(params, rule, context)
        self.assertIsNone(error)
    
    def test_character_alive_validator(self):
        """Test character_alive validator."""
        params = {}
        rule = {}
        
        # Character dead
        context = Mock()
        context.character_state = Mock()
        context.character_state.data = {'hp': 0}
        
        error = self.validator._validate_character_alive(params, rule, context)
        self.assertIsNotNone(error)
        self.assertEqual(error.validator, "character_alive")
        self.assertIn("not alive", error.message)
        
        # Character alive
        context.character_state.data = {'hp': 50}
        error = self.validator._validate_character_alive(params, rule, context)
        self.assertIsNone(error)
    
    def test_valid_coordinates_validator(self):
        """Test valid_coordinates validator."""
        rule = {'params': ['x', 'y']}
        context = Mock()
        
        # Invalid coordinate type
        params = {'x': 'not_a_number', 'y': 10}
        error = self.validator._validate_valid_coordinates(params, rule, context)
        self.assertIsNotNone(error)
        self.assertIn("not a valid integer", error.message)
        
        # Out of range
        params = {'x': 200, 'y': 10}
        error = self.validator._validate_valid_coordinates(params, rule, context)
        self.assertIsNotNone(error)
        self.assertIn("out of valid range", error.message)
        
        # Valid coordinates
        params = {'x': 10, 'y': 20}
        error = self.validator._validate_valid_coordinates(params, rule, context)
        self.assertIsNone(error)
    
    def test_not_at_location_validator(self):
        """Test not_at_location validator."""
        rule = {'params': ['x', 'y']}
        params = {'x': 10, 'y': 20}
        
        # Already at location
        context = Mock()
        context.character_state = Mock()
        context.character_state.data = {'x': 10, 'y': 20}
        
        error = self.validator._validate_not_at_location(params, rule, context)
        self.assertIsNotNone(error)
        self.assertIn("already at location", error.message)
        
        # Different location
        context.character_state.data = {'x': 5, 'y': 15}
        error = self.validator._validate_not_at_location(params, rule, context)
        self.assertIsNone(error)
    
    def test_valid_item_validator(self):
        """Test valid_item validator."""
        rule = {'param': 'item_code'}
        context = Mock()
        
        # Empty item code
        params = {'item_code': ''}
        error = self.validator._validate_valid_item(params, rule, context)
        self.assertIsNotNone(error)
        self.assertIn("Invalid or empty", error.message)
        
        # Valid item code
        params = {'item_code': 'wooden_sword'}
        error = self.validator._validate_valid_item(params, rule, context)
        self.assertIsNone(error)
    
    def test_validate_action_equip(self):
        """Test full validation for equip action."""
        # Missing item_code
        params = {}
        context = Mock()
        context.character_name = "test_char"
        
        result = self.validator.validate_action('equip', params, context)
        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.errors), 2)  # required_params and valid_item
        
        # Valid equip
        params = {'item_code': 'wooden_sword'}
        result = self.validator.validate_action('equip', params, context)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
    
    def test_validate_action_move(self):
        """Test full validation for move action."""
        context = Mock()
        context.character_name = "test_char"
        
        # Missing coordinates
        params = {'x': 10}
        result = self.validator.validate_action('move', params, context)
        self.assertFalse(result.is_valid)
        
        # Invalid coordinate
        params = {'x': 'abc', 'y': 10}
        result = self.validator.validate_action('move', params, context)
        self.assertFalse(result.is_valid)
        
        # Valid move
        params = {'x': 10, 'y': 20}
        result = self.validator.validate_action('move', params, context)
        self.assertTrue(result.is_valid)
    
    def test_unknown_action_validation(self):
        """Test validation for action without specific rules."""
        params = {'some': 'data'}
        context = Mock()
        context.character_name = "test_char"
        
        # Should only apply global rules
        result = self.validator.validate_action('unknown_action', params, context)
        self.assertTrue(result.is_valid)
        
        # Missing global context should fail
        context.character_name = None
        result = self.validator.validate_action('unknown_action', params, context)
        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.errors), 1)


if __name__ == '__main__':
    unittest.main()