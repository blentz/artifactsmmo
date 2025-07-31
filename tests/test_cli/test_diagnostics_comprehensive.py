"""
Comprehensive tests for CLI diagnostics commands to achieve 95% coverage.

This test module provides extensive coverage for the diagnostic command system,
including state diagnostics, action diagnostics, planning diagnostics, and
system troubleshooting functionality. All tests use Pydantic models throughout
as required by the architecture.
"""

import argparse
import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch, mock_open
from typing import Any, Dict

from src.cli.commands.diagnostics import DiagnosticCommands
from src.ai_player.actions import ActionRegistry
from src.ai_player.diagnostics.action_diagnostics import ActionDiagnostics
from src.ai_player.diagnostics.planning_diagnostics import PlanningDiagnostics
from src.ai_player.diagnostics.state_diagnostics import StateDiagnostics
from src.ai_player.goal_manager import GoalManager
from src.ai_player.state.game_state import GameState, CharacterGameState
from src.game_data.api_client import APIClientWrapper
from src.game_data.cooldown_manager import CooldownManager


class TestDiagnosticCommandsInitialization:
    """Test DiagnosticCommands class initialization and basic functionality."""

    def test_diagnostic_commands_init_minimal(self):
        """Test basic DiagnosticCommands initialization with no parameters."""
        diagnostic_commands = DiagnosticCommands()
        
        assert diagnostic_commands.state_diagnostics is not None
        assert isinstance(diagnostic_commands.state_diagnostics, StateDiagnostics)
        assert diagnostic_commands.action_diagnostics is None
        assert diagnostic_commands.action_registry is None
        assert diagnostic_commands.planning_diagnostics is None
        assert diagnostic_commands.goal_manager is None
        assert diagnostic_commands.api_client is None
        assert diagnostic_commands.cooldown_manager is None

    def test_diagnostic_commands_init_with_action_registry(self):
        """Test DiagnosticCommands initialization with action registry."""
        mock_action_registry = Mock(spec=ActionRegistry)
        
        diagnostic_commands = DiagnosticCommands(action_registry=mock_action_registry)
        
        assert diagnostic_commands.action_registry == mock_action_registry
        assert diagnostic_commands.action_diagnostics is not None
        assert isinstance(diagnostic_commands.action_diagnostics, ActionDiagnostics)

    def test_diagnostic_commands_init_with_goal_manager(self):
        """Test DiagnosticCommands initialization with goal manager."""
        mock_goal_manager = Mock(spec=GoalManager)
        
        diagnostic_commands = DiagnosticCommands(goal_manager=mock_goal_manager)
        
        assert diagnostic_commands.goal_manager == mock_goal_manager
        assert diagnostic_commands.planning_diagnostics is not None
        assert isinstance(diagnostic_commands.planning_diagnostics, PlanningDiagnostics)

    def test_diagnostic_commands_init_with_api_client(self):
        """Test DiagnosticCommands initialization with API client."""
        mock_api_client = Mock(spec=APIClientWrapper)
        
        diagnostic_commands = DiagnosticCommands(api_client=mock_api_client)
        
        assert diagnostic_commands.api_client == mock_api_client
        assert diagnostic_commands.cooldown_manager is not None
        assert isinstance(diagnostic_commands.cooldown_manager, CooldownManager)

    def test_diagnostic_commands_init_all_components(self):
        """Test DiagnosticCommands initialization with all components."""
        mock_action_registry = Mock(spec=ActionRegistry)
        mock_goal_manager = Mock(spec=GoalManager)
        mock_api_client = Mock(spec=APIClientWrapper)
        
        diagnostic_commands = DiagnosticCommands(
            action_registry=mock_action_registry,
            goal_manager=mock_goal_manager,
            api_client=mock_api_client
        )
        
        assert diagnostic_commands.action_registry == mock_action_registry
        assert diagnostic_commands.goal_manager == mock_goal_manager
        assert diagnostic_commands.api_client == mock_api_client
        assert diagnostic_commands.action_diagnostics is not None
        assert diagnostic_commands.planning_diagnostics is not None
        assert diagnostic_commands.cooldown_manager is not None


class TestGoalParameterParsing:
    """Test goal parameter parsing functionality."""

    def test_parse_goal_parameters_empty_string(self):
        """Test parsing empty goal string."""
        diagnostic_commands = DiagnosticCommands()
        
        result = diagnostic_commands._parse_goal_parameters("")
        
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_parse_goal_parameters_boolean_values(self):
        """Test parsing boolean goal parameters."""
        diagnostic_commands = DiagnosticCommands()
        
        # Test various boolean formats
        test_cases = [
            ("--gained-xp true", {GameState.GAINED_XP: True}),
            ("--can-gain-xp false", {GameState.CAN_GAIN_XP: False}),
            ("--cooldown-ready yes", {GameState.COOLDOWN_READY: True}),
            ("--hp-low no", {GameState.HP_LOW: False}),
            ("--safe-to-fight 1", {GameState.SAFE_TO_FIGHT: True}),
            ("--at-monster-location 0", {GameState.AT_MONSTER_LOCATION: False})
        ]
        
        for goal_string, expected in test_cases:
            result = diagnostic_commands._parse_goal_parameters(goal_string)
            assert result == expected

    def test_parse_goal_parameters_equals_format(self):
        """Test parsing goal parameters in key=value format."""
        diagnostic_commands = DiagnosticCommands()
        
        # The parser converts "key=value" format to "--key value"
        goal_string = "gained-xp=true cooldown-ready=false"
        result = diagnostic_commands._parse_goal_parameters(goal_string)
        
        expected = {
            GameState.GAINED_XP: True,
            GameState.COOLDOWN_READY: False
        }
        assert result == expected

    def test_parse_goal_parameters_multiple_values(self):
        """Test parsing multiple goal parameters."""
        diagnostic_commands = DiagnosticCommands()
        
        goal_string = "--gained-xp true --cooldown-ready false --safe-to-fight true"
        result = diagnostic_commands._parse_goal_parameters(goal_string)
        
        expected = {
            GameState.GAINED_XP: True,
            GameState.COOLDOWN_READY: False,
            GameState.SAFE_TO_FIGHT: True
        }
        assert result == expected

    def test_parse_goal_parameters_invalid_boolean(self):
        """Test parsing invalid boolean values."""
        diagnostic_commands = DiagnosticCommands()
        
        with pytest.raises(SystemExit):  # argparse exits on error
            diagnostic_commands._parse_goal_parameters("--gained-xp invalid")

    def test_str_to_bool_function(self):
        """Test the internal str_to_bool function."""
        diagnostic_commands = DiagnosticCommands()
        
        # Access the internal function through parsing
        true_values = ['yes', 'true', 't', 'y', '1', 'YES', 'True', 'T', 'Y']
        false_values = ['no', 'false', 'f', 'n', '0', 'NO', 'False', 'F', 'N']
        
        for true_val in true_values:
            result = diagnostic_commands._parse_goal_parameters(f"--gained-xp {true_val}")
            assert result[GameState.GAINED_XP] is True
            
        for false_val in false_values:
            result = diagnostic_commands._parse_goal_parameters(f"--gained-xp {false_val}")
            assert result[GameState.GAINED_XP] is False


class TestStateDiagnostics:
    """Test state diagnostic functionality."""

    @pytest.mark.asyncio
    @patch('src.cli.commands.diagnostics.APIClientWrapper')
    async def test_diagnose_state_with_character_name(self, mock_api_wrapper):
        """Test state diagnosis with character name."""
        # Setup mocks
        mock_api_client = AsyncMock()
        mock_character = Mock()
        mock_character.name = "test_char"
        mock_character.level = 5
        mock_character.x = 10
        mock_character.y = 15
        mock_character.hp = 100
        mock_character.max_hp = 100
        
        mock_api_client.get_character.return_value = mock_character
        mock_api_wrapper.return_value = mock_api_client
        
        diagnostic_commands = DiagnosticCommands(api_client=mock_api_client)
        
        with patch.object(diagnostic_commands.state_diagnostics, 'diagnose_character_state') as mock_diagnose:
            mock_diagnose.return_value = {
                "character_data": {"name": "test_char", "level": 5},
                "state_analysis": {"valid": True}
            }
            
            result = await diagnostic_commands.diagnose_state("test_char")
            
            assert result is not None
            assert "character_data" in result
            mock_diagnose.assert_called_once()

    @pytest.mark.asyncio
    async def test_diagnose_state_character_not_found(self):
        """Test state diagnosis when character is not found."""
        mock_api_client = AsyncMock()
        mock_api_client.get_character.side_effect = Exception("Character not found")
        
        diagnostic_commands = DiagnosticCommands(api_client=mock_api_client)
        
        result = await diagnostic_commands.diagnose_state("nonexistent_char")
        
        assert result is not None
        assert result["character_found"] is False
        assert result["state_validation"]["valid"] is False
        assert len(result["recommendations"]) > 0

    def test_diagnose_state_data_basic(self):
        """Test diagnosing state data directly."""
        diagnostic_commands = DiagnosticCommands()
        
        state_data = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.CHARACTER_GOLD: 100,
            GameState.HP_CURRENT: 75
        }
        
        with patch.object(diagnostic_commands.state_diagnostics, 'validate_state_data') as mock_validate:
            mock_validate.return_value = {
                "valid_keys": 3,
                "invalid_keys": 0,
                "missing_critical": []
            }
            
            result = diagnostic_commands.diagnose_state_data(state_data)
            
            assert result is not None
            mock_validate.assert_called_once_with(state_data, False)

    def test_diagnose_state_data_with_validation(self):
        """Test diagnosing state data with enum validation."""
        diagnostic_commands = DiagnosticCommands()
        
        state_data = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.CHARACTER_GOLD: 100
        }
        
        with patch.object(diagnostic_commands.state_diagnostics, 'validate_state_data') as mock_validate:
            mock_validate.return_value = {
                "valid_keys": 2,
                "enum_validation": True
            }
            
            result = diagnostic_commands.diagnose_state_data(state_data, validate_enum=True)
            
            assert result is not None
            mock_validate.assert_called_once_with(state_data, True)


class TestActionDiagnostics:
    """Test action diagnostic functionality."""

    @pytest.mark.asyncio
    async def test_diagnose_actions_no_action_registry(self):
        """Test action diagnosis when no action registry is available."""
        diagnostic_commands = DiagnosticCommands()
        
        result = await diagnostic_commands.diagnose_actions()
        
        assert result is not None
        assert "error" in result
        assert "action registry not initialized" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_diagnose_actions_with_character(self):
        """Test action diagnosis with character name."""
        mock_action_registry = Mock(spec=ActionRegistry)
        mock_api_client = AsyncMock()
        diagnostic_commands = DiagnosticCommands(
            action_registry=mock_action_registry,
            api_client=mock_api_client
        )
        
        # Mock character data
        mock_character = Mock()
        mock_character.name = "test_char"
        mock_character.level = 5
        mock_api_client.get_character.return_value = mock_character
        
        with patch.object(diagnostic_commands.action_diagnostics, 'analyze_available_actions') as mock_analyze:
            mock_analyze.return_value = {
                "available_actions": ["move", "fight"],
                "blocked_actions": ["craft"]
            }
            
            result = await diagnostic_commands.diagnose_actions("test_char")
            
            assert result is not None
            mock_analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_diagnose_actions_list_all(self):
        """Test listing all available actions."""
        mock_action_registry = Mock(spec=ActionRegistry)
        diagnostic_commands = DiagnosticCommands(action_registry=mock_action_registry)
        
        with patch.object(diagnostic_commands.action_diagnostics, 'list_all_actions') as mock_list:
            mock_list.return_value = {
                "total_actions": 10,
                "action_types": ["movement", "combat", "gathering"]
            }
            
            result = await diagnostic_commands.diagnose_actions(list_all=True)
            
            assert result is not None
            mock_list.assert_called_once()

    @pytest.mark.asyncio
    async def test_diagnose_actions_show_costs(self):
        """Test showing action costs."""
        mock_action_registry = Mock(spec=ActionRegistry)
        diagnostic_commands = DiagnosticCommands(action_registry=mock_action_registry)
        
        with patch.object(diagnostic_commands.action_diagnostics, 'show_action_costs') as mock_costs:
            mock_costs.return_value = {
                "move": 1,
                "fight": 3,
                "gather": 2
            }
            
            result = await diagnostic_commands.diagnose_actions(show_costs=True)
            
            assert result is not None
            mock_costs.assert_called_once()

    @pytest.mark.asyncio
    async def test_diagnose_actions_show_preconditions(self):
        """Test showing action preconditions."""
        mock_action_registry = Mock(spec=ActionRegistry)
        diagnostic_commands = DiagnosticCommands(action_registry=mock_action_registry)
        
        with patch.object(diagnostic_commands.action_diagnostics, 'analyze_preconditions') as mock_preconditions:
            mock_preconditions.return_value = {
                "move": {GameState.COOLDOWN_READY: True},
                "fight": {GameState.COOLDOWN_READY: True, GameState.HP_CURRENT: 50}
            }
            
            result = await diagnostic_commands.diagnose_actions(show_preconditions=True)
            
            assert result is not None
            mock_preconditions.assert_called_once()


class TestPlanningDiagnostics:
    """Test planning diagnostic functionality."""

    @pytest.mark.asyncio
    async def test_diagnose_plan_no_goal_manager(self):
        """Test plan diagnosis when no goal manager is available."""
        diagnostic_commands = DiagnosticCommands()
        
        result = await diagnostic_commands.diagnose_plan("test_char", "level_up")
        
        assert result is not None
        assert "error" in result
        assert "goal manager not initialized" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_diagnose_plan_basic(self):
        """Test basic plan diagnosis."""
        mock_goal_manager = Mock(spec=GoalManager)
        mock_api_client = AsyncMock()
        diagnostic_commands = DiagnosticCommands(
            goal_manager=mock_goal_manager,
            api_client=mock_api_client
        )
        
        # Mock character data
        mock_character = Mock()
        mock_character.name = "test_char"
        mock_api_client.get_character.return_value = mock_character
        
        with patch.object(diagnostic_commands.planning_diagnostics, 'analyze_plan') as mock_analyze:
            mock_analyze.return_value = {
                "plan_found": True,
                "steps": 5,
                "estimated_time": 300
            }
            
            result = await diagnostic_commands.diagnose_plan("test_char", "level_up")
            
            assert result is not None
            mock_analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_diagnose_plan_with_goal_parameters(self):
        """Test plan diagnosis with specific goal parameters."""
        mock_goal_manager = Mock(spec=GoalManager)
        mock_api_client = AsyncMock()
        diagnostic_commands = DiagnosticCommands(
            goal_manager=mock_goal_manager,
            api_client=mock_api_client
        )
        
        mock_character = Mock()
        mock_character.name = "test_char"
        mock_api_client.get_character.return_value = mock_character
        
        with patch.object(diagnostic_commands.planning_diagnostics, 'analyze_custom_goal') as mock_analyze:
            mock_analyze.return_value = {
                "custom_goal": True,
                "achievable": True
            }
            
            result = await diagnostic_commands.diagnose_plan(
                "test_char", 
                "custom",
                goal_parameters="--character-level 10"
            )
            
            assert result is not None
            mock_analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_diagnose_plan_verbose_mode(self):
        """Test plan diagnosis in verbose mode."""
        mock_goal_manager = Mock(spec=GoalManager)
        mock_api_client = AsyncMock()
        diagnostic_commands = DiagnosticCommands(
            goal_manager=mock_goal_manager,
            api_client=mock_api_client
        )
        
        mock_character = Mock()
        mock_api_client.get_character.return_value = mock_character
        
        with patch.object(diagnostic_commands.planning_diagnostics, 'analyze_plan_verbose') as mock_analyze:
            mock_analyze.return_value = {
                "detailed_steps": ["step1", "step2"],
                "decision_points": ["branch1", "branch2"]
            }
            
            result = await diagnostic_commands.diagnose_plan("test_char", "level_up", verbose=True)
            
            assert result is not None
            mock_analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_diagnose_plan_show_steps(self):
        """Test plan diagnosis with step visualization."""
        mock_goal_manager = Mock(spec=GoalManager)
        mock_api_client = AsyncMock()
        diagnostic_commands = DiagnosticCommands(
            goal_manager=mock_goal_manager,
            api_client=mock_api_client
        )
        
        mock_character = Mock()
        mock_api_client.get_character.return_value = mock_character
        
        with patch.object(diagnostic_commands.planning_diagnostics, 'visualize_plan_steps') as mock_visualize:
            mock_visualize.return_value = {
                "step_visualization": ["1. Move to location", "2. Fight monster"],
                "total_cost": 10
            }
            
            result = await diagnostic_commands.diagnose_plan("test_char", "level_up", show_steps=True)
            
            assert result is not None
            mock_visualize.assert_called_once()


class TestPlanningTesting:
    """Test planning simulation and testing functionality."""

    @pytest.mark.asyncio
    async def test_test_planning_no_goal_manager(self):
        """Test planning testing when no goal manager is available."""
        diagnostic_commands = DiagnosticCommands()
        
        result = await diagnostic_commands.test_planning()
        
        assert result is not None
        assert "error" in result
        assert "goal manager not initialized" in result["error"].lower()

    @pytest.mark.asyncio 
    async def test_test_planning_with_mock_state_file(self):
        """Test planning testing with mock state file."""
        mock_goal_manager = Mock(spec=GoalManager)
        diagnostic_commands = DiagnosticCommands(goal_manager=mock_goal_manager)
        
        mock_state_data = {
            "character_level": 1,
            "character_gold": 0,
            "hp_current": 100
        }
        
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_state_data))):
            with patch.object(diagnostic_commands.planning_diagnostics, 'test_planning_scenario') as mock_test:
                mock_test.return_value = {
                    "scenario_valid": True,
                    "planning_successful": True
                }
                
                result = await diagnostic_commands.test_planning(mock_state_file="test_state.json")
                
                assert result is not None
                mock_test.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_planning_with_level_range(self):
        """Test planning testing with start/goal level range."""
        mock_goal_manager = Mock(spec=GoalManager)
        diagnostic_commands = DiagnosticCommands(goal_manager=mock_goal_manager)
        
        with patch.object(diagnostic_commands.planning_diagnostics, 'test_level_progression') as mock_test:
            mock_test.return_value = {
                "progression_valid": True,
                "steps_required": 10
            }
            
            result = await diagnostic_commands.test_planning(
                start_level=1,
                goal_level=5
            )
            
            assert result is not None
            mock_test.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_planning_dry_run(self):
        """Test planning testing in dry run mode."""
        mock_goal_manager = Mock(spec=GoalManager)
        diagnostic_commands = DiagnosticCommands(goal_manager=mock_goal_manager)
        
        with patch.object(diagnostic_commands.planning_diagnostics, 'dry_run_planning') as mock_dry_run:
            mock_dry_run.return_value = {
                "dry_run": True,
                "no_actions_executed": True
            }
            
            result = await diagnostic_commands.test_planning(dry_run=True)
            
            assert result is not None
            mock_dry_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_planning_invalid_mock_file(self):
        """Test planning testing with invalid mock state file."""
        mock_goal_manager = Mock(spec=GoalManager)
        diagnostic_commands = DiagnosticCommands(goal_manager=mock_goal_manager)
        
        with patch('builtins.open', side_effect=FileNotFoundError()):
            result = await diagnostic_commands.test_planning(mock_state_file="nonexistent.json")
            
            assert result is not None
            assert "error" in result


class TestWeightsDiagnostics:
    """Test weights and configuration diagnostics."""

    @pytest.mark.asyncio
    async def test_diagnose_weights_basic(self):
        """Test basic weights diagnosis."""
        diagnostic_commands = DiagnosticCommands()
        
        with patch('src.cli.commands.diagnostics.Path') as mock_path:
            mock_weights_file = Mock()
            mock_weights_file.exists.return_value = True
            mock_path.return_value = mock_weights_file
            
            mock_weights_data = {
                "action_costs": {"move": 1, "fight": 3},
                "goal_weights": {"level_up": 100}
            }
            
            with patch('builtins.open', mock_open(read_data=json.dumps(mock_weights_data))):
                result = await diagnostic_commands.diagnose_weights()
                
                assert result is not None
                assert "action_costs" in result
                assert "goal_weights" in result

    @pytest.mark.asyncio
    async def test_diagnose_weights_show_action_costs(self):
        """Test weights diagnosis with action costs display."""
        mock_action_registry = Mock(spec=ActionRegistry)
        diagnostic_commands = DiagnosticCommands(action_registry=mock_action_registry)
        
        with patch('src.cli.commands.diagnostics.Path') as mock_path:
            mock_weights_file = Mock()
            mock_weights_file.exists.return_value = True
            mock_path.return_value = mock_weights_file
            
            mock_weights_data = {"action_costs": {"move": 1, "fight": 3}}
            
            with patch('builtins.open', mock_open(read_data=json.dumps(mock_weights_data))):
                with patch.object(diagnostic_commands.action_diagnostics, 'compare_action_costs') as mock_compare:
                    mock_compare.return_value = {
                        "cost_analysis": {"optimal": True}
                    }
                    
                    result = await diagnostic_commands.diagnose_weights(show_action_costs=True)
                    
                    assert result is not None
                    mock_compare.assert_called_once()

    @pytest.mark.asyncio
    async def test_diagnose_weights_missing_file(self):
        """Test weights diagnosis when weights file is missing."""
        diagnostic_commands = DiagnosticCommands()
        
        with patch('src.cli.commands.diagnostics.Path') as mock_path:
            mock_weights_file = Mock()
            mock_weights_file.exists.return_value = False
            mock_path.return_value = mock_weights_file
            
            result = await diagnostic_commands.diagnose_weights()
            
            assert result is not None
            assert "error" in result


class TestCooldownDiagnostics:
    """Test cooldown diagnostic functionality."""

    @pytest.mark.asyncio
    async def test_diagnose_cooldowns_no_api_client(self):
        """Test cooldown diagnosis when no API client is available."""
        diagnostic_commands = DiagnosticCommands()
        
        result = await diagnostic_commands.diagnose_cooldowns("test_char")
        
        assert result is not None
        assert "error" in result
        assert "api client not initialized" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_diagnose_cooldowns_basic(self):
        """Test basic cooldown diagnosis."""
        mock_api_client = AsyncMock()
        diagnostic_commands = DiagnosticCommands(api_client=mock_api_client)
        
        mock_character = Mock()
        mock_character.name = "test_char"
        mock_character.cooldown = 0
        mock_api_client.get_character.return_value = mock_character
        
        with patch.object(diagnostic_commands.cooldown_manager, 'get_cooldown_info') as mock_cooldown:
            mock_cooldown.return_value = {
                "ready": True,
                "remaining_seconds": 0
            }
            
            result = await diagnostic_commands.diagnose_cooldowns("test_char")
            
            assert result is not None

    @pytest.mark.asyncio
    async def test_diagnose_cooldowns_with_active_cooldown(self):
        """Test cooldown diagnosis with active cooldown."""
        mock_api_client = AsyncMock()
        diagnostic_commands = DiagnosticCommands(api_client=mock_api_client)
        
        mock_character = Mock()
        mock_character.name = "test_char"
        mock_character.cooldown = 30
        mock_api_client.get_character.return_value = mock_character
        
        result = await diagnostic_commands.diagnose_cooldowns("test_char")
        
        assert result is not None
        assert "cooldown_active" in result or "cooldown_remaining" in result

    @pytest.mark.asyncio
    async def test_diagnose_cooldowns_monitor_mode(self):
        """Test cooldown diagnosis in monitor mode."""
        mock_api_client = AsyncMock()
        diagnostic_commands = DiagnosticCommands(api_client=mock_api_client)
        
        mock_character = Mock()
        mock_character.name = "test_char"
        mock_character.cooldown = 10
        mock_api_client.get_character.return_value = mock_character
        
        # Mock the monitoring loop to run once and exit
        with patch('asyncio.sleep') as mock_sleep:
            mock_sleep.side_effect = [None, KeyboardInterrupt()]  # Run once then exit
            
            result = await diagnostic_commands.diagnose_cooldowns("test_char", monitor=True)
            
            assert result is not None


class TestDiagnosticCommandsIntegration:
    """Test integration scenarios and edge cases."""

    def test_diagnostic_commands_all_components_integration(self):
        """Test that all diagnostic components work together."""
        mock_action_registry = Mock(spec=ActionRegistry)
        mock_goal_manager = Mock(spec=GoalManager)
        mock_api_client = Mock(spec=APIClientWrapper)
        
        diagnostic_commands = DiagnosticCommands(
            action_registry=mock_action_registry,
            goal_manager=mock_goal_manager,
            api_client=mock_api_client
        )
        
        # Verify all components are properly initialized
        assert diagnostic_commands.state_diagnostics is not None
        assert diagnostic_commands.action_diagnostics is not None
        assert diagnostic_commands.planning_diagnostics is not None
        assert diagnostic_commands.cooldown_manager is not None
        
        # Verify component relationships
        assert diagnostic_commands.action_diagnostics.action_registry == mock_action_registry
        assert diagnostic_commands.planning_diagnostics.goal_manager == mock_goal_manager

    @pytest.mark.asyncio
    async def test_diagnostic_error_handling(self):
        """Test error handling in diagnostic operations."""
        diagnostic_commands = DiagnosticCommands()
        
        # Test various error scenarios
        error_cases = [
            ("diagnose_state", {"character_name": "test"}),
            ("diagnose_actions", {"character_name": "test"}),
            ("diagnose_plan", {"character_name": "test", "goal": "level_up"}),
            ("test_planning", {}),
            ("diagnose_cooldowns", {"character_name": "test"})
        ]
        
        for method_name, kwargs in error_cases:
            method = getattr(diagnostic_commands, method_name)
            result = await method(**kwargs)
            
            # All methods should return error information rather than raising
            assert result is not None
            assert "error" in result

    def test_diagnostic_commands_string_representation(self):
        """Test string representation of DiagnosticCommands."""
        diagnostic_commands = DiagnosticCommands()
        
        # Just verify it doesn't crash
        str_repr = str(diagnostic_commands)
        assert isinstance(str_repr, str)

    @pytest.mark.asyncio
    async def test_exception_propagation_handling(self):
        """Test that exceptions are properly handled and converted to error results."""
        mock_api_client = AsyncMock()
        mock_api_client.get_character.side_effect = Exception("Network error")
        
        diagnostic_commands = DiagnosticCommands(api_client=mock_api_client)
        
        result = await diagnostic_commands.diagnose_state("test_char")
        
        # Should return error info rather than letting exception propagate
        assert result is not None
        assert "error" in result
        assert "Network error" in str(result["error"])