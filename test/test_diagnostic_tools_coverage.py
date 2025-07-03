"""
Additional tests to improve coverage for diagnostic tools.
"""

from unittest import TestCase
from unittest.mock import MagicMock, patch

from src.diagnostic_tools import DiagnosticTools


class TestDiagnosticToolsAdditionalCoverage(TestCase):
    """Additional tests for edge cases and error handling."""
    
    def test_parse_custom_state_invalid_type(self):
        """Test parsing custom state with invalid type."""
        # Test with integer (invalid type)
        tools = DiagnosticTools(custom_state=12345)
        
        # Should use clean state
        self.assertIn('character_status', tools.current_state)
        self.assertTrue(tools.current_state['character_status']['alive'])
        
    def test_parse_goal_string_default_boolean(self):
        """Test parsing goal string defaults to boolean."""
        tools = DiagnosticTools()
        
        result = tools._parse_goal_string('some_random_flag')
        
        self.assertEqual(result, {'some_random_flag': True})
        
    @patch('src.diagnostic_tools.ActionsData')
    @patch('logging.Logger.info')
    @patch('logging.Logger.error')
    def test_show_goal_plan_parse_failure(self, mock_error, mock_info, mock_actions_data):
        """Test show_goal_plan when goal parsing fails."""
        mock_actions_data.return_value.get_actions.return_value = {}
        
        tools = DiagnosticTools()
        # Mock the parse method to return None
        tools._parse_goal_string = MagicMock(return_value=None)
        
        tools.show_goal_plan('invalid_goal')
        
        # Should log error
        mock_error.assert_called_with('Failed to parse goal string')
        
    def test_simulate_action_simple_reactions(self):
        """Test simulating action with simple (non-nested) reactions."""
        tools = DiagnosticTools(clean_state=True)
        
        action_cfg = {
            'conditions': {},
            'reactions': {
                'simple_flag': True,
                'another_flag': 'test_value'
            },
            'weight': 1.5
        }
        
        state = {}
        success, cost = tools._simulate_action('test', action_cfg, state)
        
        self.assertTrue(success)
        self.assertEqual(cost, 1.5)
        self.assertEqual(state['simple_flag'], True)
        self.assertEqual(state['another_flag'], 'test_value')
        
    @patch('src.diagnostic_tools.ActionsData')
    @patch('logging.Logger.info')
    def test_evaluate_user_plan_live_failure(self, mock_info, mock_actions_data):
        """Test evaluating plan with live execution failure."""
        mock_actions_data.return_value.get_actions.return_value = {
            'test_action': {}
        }
        
        tools = DiagnosticTools(offline=False, clean_state=True)
        tools._execute_action_live = MagicMock(return_value=False)
        
        tools.evaluate_user_plan('test_action')
        
        # Should show plan as invalid
        self.assertTrue(any('Plan is INVALID' in str(call) for call in mock_info.call_args_list))
        
    @patch('src.diagnostic_tools.AIPlayerController')
    def test_execute_plan_live_exception_handling(self, mock_controller):
        """Test execute_plan_live with exception."""
        # Set up mock controller
        mock_instance = MagicMock()
        mock_controller.return_value = mock_instance
        mock_instance.execute_plan.side_effect = RuntimeError('Test error')
        
        tools = DiagnosticTools(client=MagicMock(), offline=False, clean_state=True)
        
        result = tools._execute_plan_live([{'name': 'test'}])
        
        self.assertFalse(result)
        
    def test_display_reactions_uses_display_conditions(self):
        """Test that _display_reactions calls _display_conditions."""
        tools = DiagnosticTools()
        
        # Test that display_reactions uses display_conditions internally
        with patch.object(tools, '_display_conditions') as mock_display:
            reactions = {'test': 'value'}
            tools._display_reactions(reactions, 5)
            
            # Verify it was called with the same arguments
            mock_display.assert_called_once_with(reactions, 5)
        
    def test_display_state_requirements_nested(self):
        """Test displaying nested state requirements."""
        tools = DiagnosticTools()
        
        with patch('logging.Logger.info') as mock_info:
            state = {
                'top_level': 'value',
                'nested': {
                    'inner1': 'value1',
                    'inner2': {
                        'deep': 'value2'
                    }
                }
            }
            
            tools._display_state_requirements(state)
            
            # Verify nested structure was logged
            calls = [str(call) for call in mock_info.call_args_list]
            self.assertTrue(any('top_level: value' in call for call in calls))
            self.assertTrue(any('nested:' in call for call in calls))
            self.assertTrue(any('inner1: value1' in call for call in calls))
            
    def test_format_state_for_display_dict_value(self):
        """Test formatting state with nested dict values."""
        tools = DiagnosticTools()
        
        state = {
            'nested_dict': {
                'empty': {}
            }
        }
        
        result = tools._format_state_for_display(state)
        
        self.assertIn('nested_dict: {empty: {...}}', result)