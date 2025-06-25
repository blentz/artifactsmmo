"""Test module for ActionBase."""

import unittest
from unittest.mock import Mock
from src.controller.actions.base import ActionBase


class TestActionBase(unittest.TestCase):
    """Test cases for ActionBase."""

    def setUp(self):
        """Set up test fixtures."""
        self.action = ActionBase()
        self.mock_client = Mock()

    def test_action_base_initialization(self):
        """Test ActionBase initialization."""
        # Check that logger is set up
        self.assertIsNotNone(self.action.logger)
        self.assertEqual(self.action.logger.name, 'ActionBase')

    def test_execute_not_implemented(self):
        """Test that execute method raises NotImplementedError."""
        with self.assertRaises(NotImplementedError) as context:
            self.action.execute(self.mock_client)
        
        self.assertIn("Subclasses must implement execute method", str(context.exception))

    def test_validate_execution_context_with_client(self):
        """Test validate_execution_context with valid client."""
        result = self.action.validate_execution_context(self.mock_client)
        self.assertTrue(result)

    def test_validate_execution_context_without_client(self):
        """Test validate_execution_context with None client."""
        result = self.action.validate_execution_context(None)
        self.assertFalse(result)

    def test_get_error_response_basic(self):
        """Test get_error_response with basic error message."""
        error_msg = "Test error"
        result = self.action.get_error_response(error_msg)
        
        expected = {
            'success': False,
            'error': error_msg,
            'action': 'ActionBase'
        }
        self.assertEqual(result, expected)

    def test_get_error_response_with_additional_data(self):
        """Test get_error_response with additional data."""
        error_msg = "Test error"
        additional_data = {'location': (5, 3), 'code': 'E001'}
        result = self.action.get_error_response(error_msg, **additional_data)
        
        expected = {
            'success': False,
            'error': error_msg,
            'action': 'ActionBase',
            'location': (5, 3),
            'code': 'E001'
        }
        self.assertEqual(result, expected)

    def test_get_success_response_basic(self):
        """Test get_success_response with no data."""
        result = self.action.get_success_response()
        
        expected = {
            'success': True,
            'action': 'ActionBase'
        }
        self.assertEqual(result, expected)

    def test_get_success_response_with_data(self):
        """Test get_success_response with data."""
        data = {'result': 'completed', 'items': [1, 2, 3]}
        result = self.action.get_success_response(**data)
        
        expected = {
            'success': True,
            'action': 'ActionBase',
            'result': 'completed',
            'items': [1, 2, 3]
        }
        self.assertEqual(result, expected)

    def test_log_execution_start(self):
        """Test log_execution_start method."""
        with self.assertLogs(self.action.logger, level='INFO') as log:
            self.action.log_execution_start(test_param="value", another_param=123)
        
        self.assertEqual(len(log.output), 1)
        self.assertIn("Executing ActionBase with context:", log.output[0])
        self.assertIn("'test_param': 'value'", log.output[0])
        self.assertIn("'another_param': 123", log.output[0])

    def test_log_execution_result_success(self):
        """Test log_execution_result method with success."""
        result = {'success': True, 'message': 'Test result'}
        
        with self.assertLogs(self.action.logger, level='INFO') as log:
            self.action.log_execution_result(result)
        
        self.assertEqual(len(log.output), 1)
        self.assertIn("ActionBase completed successfully", log.output[0])

    def test_log_execution_result_failure(self):
        """Test log_execution_result method with failure."""
        result = {'success': False, 'error': 'Test error'}
        
        with self.assertLogs(self.action.logger, level='WARNING') as log:
            self.action.log_execution_result(result)
        
        self.assertEqual(len(log.output), 1)
        self.assertIn("ActionBase failed: Test error", log.output[0])

    def test_log_execution_result_non_dict(self):
        """Test log_execution_result method with non-dict result."""
        result = "some string result"
        
        with self.assertLogs(self.action.logger, level='INFO') as log:
            self.action.log_execution_result(result)
        
        self.assertEqual(len(log.output), 1)
        self.assertIn("ActionBase completed with result: str", log.output[0])

    def test_action_base_has_goap_attributes(self):
        """Test that ActionBase has expected GOAP class attributes."""
        self.assertTrue(hasattr(ActionBase, 'conditions'))
        self.assertTrue(hasattr(ActionBase, 'reactions'))
        self.assertTrue(hasattr(ActionBase, 'weights'))
        self.assertTrue(hasattr(ActionBase, 'g'))
        
        # Check that they are correct types
        self.assertIsInstance(ActionBase.conditions, dict)
        self.assertIsInstance(ActionBase.reactions, dict)
        self.assertIsInstance(ActionBase.weights, dict)
        self.assertIsNone(ActionBase.g)  # g is None by default

    def test_action_base_repr(self):
        """Test ActionBase string representation."""
        result = repr(self.action)
        self.assertEqual(result, "ActionBase()")


if __name__ == '__main__':
    unittest.main()