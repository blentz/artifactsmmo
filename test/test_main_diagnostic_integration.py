"""
Tests for main.py diagnostic integration.

Tests the integration of diagnostic tools in the main module.
"""

import argparse
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

from src.main import show_goal_plan, evaluate_user_plan


class TestMainDiagnosticIntegration(TestCase):
    """Test diagnostic tool integration in main module."""
    
    @patch('src.main.DiagnosticTools')
    def test_show_goal_plan_defaults(self, mock_diagnostic_tools):
        """Test show_goal_plan with default arguments."""
        # Create mock client
        mock_client = MagicMock()
        
        # Create args without diagnostic attributes
        args = argparse.Namespace()
        
        # Call function
        show_goal_plan('test_goal', mock_client, args)
        
        # Verify DiagnosticTools was created with defaults
        mock_diagnostic_tools.assert_called_once_with(
            client=mock_client,
            offline=True,  # Default when online not specified
            clean_state=False,
            custom_state=None,
            args=args
        )
        
        # Verify show_goal_plan was called
        mock_diagnostic_tools.return_value.show_goal_plan.assert_called_once_with('test_goal')
        
    @patch('src.main.DiagnosticTools')
    def test_show_goal_plan_live_mode(self, mock_diagnostic_tools):
        """Test show_goal_plan in live mode."""
        mock_client = MagicMock()
        
        args = argparse.Namespace(
            online=True,
            clean_state=False,
            state=None
        )
        
        show_goal_plan('reach_level_10', mock_client, args)
        
        # Verify offline=False when online=True
        mock_diagnostic_tools.assert_called_once_with(
            client=mock_client,
            offline=False,
            clean_state=False,
            custom_state=None,
            args=args
        )
        
    @patch('src.main.DiagnosticTools')
    def test_show_goal_plan_clean_state(self, mock_diagnostic_tools):
        """Test show_goal_plan with clean state."""
        mock_client = MagicMock()
        
        args = argparse.Namespace(
            online=False,
            clean_state=True,
            state=None
        )
        
        show_goal_plan('test_goal', mock_client, args)
        
        mock_diagnostic_tools.assert_called_once_with(
            client=mock_client,
            offline=True,
            clean_state=True,
            custom_state=None,
            args=args
        )
        
    @patch('src.main.DiagnosticTools')
    def test_show_goal_plan_custom_state(self, mock_diagnostic_tools):
        """Test show_goal_plan with custom state."""
        mock_client = MagicMock()
        
        custom_state_json = '{"character_status": {"level": 5}}'
        args = argparse.Namespace(
            online=False,
            clean_state=False,
            state=custom_state_json
        )
        
        show_goal_plan('test_goal', mock_client, args)
        
        mock_diagnostic_tools.assert_called_once_with(
            client=mock_client,
            offline=True,
            clean_state=False,
            custom_state=custom_state_json,
            args=args
        )
        
    @patch('src.main.DiagnosticTools')
    def test_evaluate_user_plan_defaults(self, mock_diagnostic_tools):
        """Test evaluate_user_plan with default arguments."""
        mock_client = MagicMock()
        
        args = argparse.Namespace()
        
        evaluate_user_plan('move->attack', mock_client, args)
        
        mock_diagnostic_tools.assert_called_once_with(
            client=mock_client,
            offline=True,
            clean_state=False,
            custom_state=None,
            args=args
        )
        
        mock_diagnostic_tools.return_value.evaluate_user_plan.assert_called_once_with('move->attack')
        
    @patch('src.main.DiagnosticTools')
    def test_evaluate_user_plan_all_options(self, mock_diagnostic_tools):
        """Test evaluate_user_plan with all options set."""
        mock_client = MagicMock()
        
        custom_state = '{"test": "state"}'
        args = argparse.Namespace(
            online=True,
            clean_state=True,
            state=custom_state
        )
        
        evaluate_user_plan('rest', mock_client, args)
        
        mock_diagnostic_tools.assert_called_once_with(
            client=mock_client,
            offline=False,  # online=True
            clean_state=True,
            custom_state=custom_state,
            args=args
        )
        
    def test_attribute_handling_missing_attributes(self):
        """Test graceful handling of missing attributes."""
        # Test that hasattr checks work correctly
        args = argparse.Namespace()
        
        # These should not exist
        self.assertFalse(hasattr(args, 'online'))
        self.assertFalse(hasattr(args, 'clean_state'))
        self.assertFalse(hasattr(args, 'state'))
        
        # Add one attribute
        args.online = True
        self.assertTrue(hasattr(args, 'online'))
        self.assertFalse(hasattr(args, 'clean_state'))