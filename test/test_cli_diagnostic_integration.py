"""
Tests for CLI diagnostic integration.

Tests the integration between CLI arguments and diagnostic tools.
"""

import argparse
import json
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

from src.cli import create_parser, validate_args


class TestCLIDiagnosticIntegration(TestCase):
    """Test CLI diagnostic argument handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = create_parser()
        
    def test_diagnostic_flags_offline_default(self):
        """Test diagnostic flags default to offline mode."""
        args = self.parser.parse_args(['-g', 'test_goal'])
        
        self.assertTrue(hasattr(args, 'offline'))
        self.assertTrue(hasattr(args, 'live'))
        self.assertFalse(args.offline)  # Not explicitly set
        self.assertFalse(args.live)
        
    def test_diagnostic_flags_offline_explicit(self):
        """Test explicit offline flag."""
        args = self.parser.parse_args(['-g', 'test_goal', '--offline'])
        
        self.assertTrue(args.offline)
        self.assertFalse(args.live)
        
    def test_diagnostic_flags_live(self):
        """Test live execution flag."""
        args = self.parser.parse_args(['-e', 'move->attack', '--live'])
        
        self.assertFalse(args.offline)
        self.assertTrue(args.live)
        
    def test_clean_state_flag(self):
        """Test clean state flag."""
        args = self.parser.parse_args(['-g', 'test_goal', '--clean-state'])
        
        self.assertTrue(args.clean_state)
        
    def test_custom_state_flag(self):
        """Test custom state flag."""
        custom_state = '{"character_status": {"level": 5}}'
        args = self.parser.parse_args(['-g', 'test_goal', '--state', custom_state])
        
        self.assertEqual(args.state, custom_state)
        
    def test_validate_args_offline_live_conflict(self):
        """Test validation catches offline/live conflict."""
        args = argparse.Namespace(
            offline=True,
            live=True,
            goal_planner='test',
            evaluate_plan=None,
            daemon=False,
            clean=False,
            create_character=None,
            delete_character=None,
            parallel=None,
            state=None,
            clean_state=False
        )
        
        result = validate_args(args)
        self.assertFalse(result)
        
    def test_validate_args_live_requires_action(self):
        """Test validation ensures live mode has action."""
        args = argparse.Namespace(
            offline=False,
            live=True,
            goal_planner=None,
            evaluate_plan=None,
            daemon=False,
            clean=False,
            create_character=None,
            delete_character=None,
            parallel=None,
            state=None,
            clean_state=False
        )
        
        result = validate_args(args)
        self.assertFalse(result)
        
    def test_validate_args_state_requires_diagnostic(self):
        """Test validation ensures state flag has diagnostic mode."""
        args = argparse.Namespace(
            offline=False,
            live=False,
            goal_planner=None,
            evaluate_plan=None,
            state='{"test": true}',
            daemon=False,
            clean=False,
            create_character=None,
            delete_character=None,
            parallel=None
        )
        
        result = validate_args(args)
        self.assertFalse(result)
        
    def test_validate_args_valid_diagnostic_combo(self):
        """Test valid diagnostic argument combinations."""
        # Valid offline goal planning
        args = argparse.Namespace(
            offline=True,
            live=False,
            goal_planner='test_goal',
            evaluate_plan=None,
            state=None,
            clean_state=False,
            daemon=False,
            clean=False,
            create_character=None,
            delete_character=None,
            parallel=None
        )
        
        result = validate_args(args)
        self.assertTrue(result)
        
        # Valid live plan evaluation
        args.offline = False
        args.live = True
        args.goal_planner = None
        args.evaluate_plan = 'move->attack'
        
        result = validate_args(args)
        self.assertTrue(result)
        
    @patch('src.main.DiagnosticTools')
    @patch('src.main.AuthenticatedClient')
    def test_show_goal_plan_integration(self, mock_client, mock_tools):
        """Test show_goal_plan with CLI arguments."""
        from src.main import show_goal_plan
        
        args = argparse.Namespace(
            live=True,
            clean_state=True,
            state='{"test": true}'
        )
        
        client = MagicMock()
        show_goal_plan('test_goal', client, args)
        
        # Verify DiagnosticTools was created with correct parameters
        mock_tools.assert_called_once_with(
            client=client,
            offline=False,  # live=True means offline=False
            clean_state=True,
            custom_state='{"test": true}'
        )
        
        # Verify show_goal_plan was called
        mock_tools.return_value.show_goal_plan.assert_called_once_with('test_goal')
        
    @patch('src.main.DiagnosticTools')
    @patch('src.main.AuthenticatedClient')
    def test_evaluate_user_plan_integration(self, mock_client, mock_tools):
        """Test evaluate_user_plan with CLI arguments."""
        from src.main import evaluate_user_plan
        
        args = argparse.Namespace(
            live=False,
            offline=True,
            clean_state=False,
            state=None
        )
        
        client = MagicMock()
        evaluate_user_plan('move->attack->rest', client, args)
        
        # Verify DiagnosticTools was created with correct parameters
        mock_tools.assert_called_once_with(
            client=client,
            offline=True,
            clean_state=False,
            custom_state=None
        )
        
        # Verify evaluate_user_plan was called
        mock_tools.return_value.evaluate_user_plan.assert_called_once_with('move->attack->rest')


class TestCLIHelpOutput(TestCase):
    """Test CLI help and documentation."""
    
    def test_help_includes_diagnostic_options(self):
        """Test that help text includes diagnostic options."""
        parser = create_parser()
        help_text = parser.format_help()
        
        # Check for diagnostic flags
        self.assertIn('--offline', help_text)
        self.assertIn('--live', help_text)
        self.assertIn('--clean-state', help_text)
        self.assertIn('--state', help_text)
        
        # Check descriptions - use actual text from CLI
        self.assertIn('offline mode without API', help_text)
        self.assertIn('Execute diagnostic plans with live API', help_text)
        self.assertIn('clean default state', help_text)
        self.assertIn('custom state (JSON format)', help_text)
        
    def test_examples_include_diagnostic_usage(self):
        """Test that examples show diagnostic usage."""
        parser = create_parser()
        help_text = parser.format_help()
        
        # Check for diagnostic examples
        self.assertIn('--live', help_text)
        self.assertIn('Execute goal plan with live API', help_text)
        self.assertIn('--offline', help_text)
        self.assertIn('Evaluate plan in offline mode', help_text)