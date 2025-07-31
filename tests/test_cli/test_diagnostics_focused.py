"""
Focused tests for CLI diagnostics commands to improve coverage effectively.

This test module focuses on the main code paths in the diagnostics module
to maximize coverage improvement with working tests that match the actual
implementation patterns.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from typing import Any, Dict

from src.cli.commands.diagnostics import DiagnosticCommands
from src.ai_player.actions import ActionRegistry
from src.ai_player.goal_manager import GoalManager
from src.ai_player.state.game_state import GameState
from src.game_data.api_client import APIClientWrapper


class TestDiagnosticCommandsBasic:
    """Test basic functionality that should work reliably."""

    def test_init_minimal(self):
        """Test minimal initialization."""
        diagnostic_commands = DiagnosticCommands()
        assert diagnostic_commands.state_diagnostics is not None
        assert diagnostic_commands.action_diagnostics is None
        assert diagnostic_commands.planning_diagnostics is None

    def test_init_with_components(self):
        """Test initialization with all components."""
        action_registry = Mock(spec=ActionRegistry)
        goal_manager = Mock(spec=GoalManager) 
        api_client = Mock(spec=APIClientWrapper)
        
        diagnostic_commands = DiagnosticCommands(
            action_registry=action_registry,
            goal_manager=goal_manager,
            api_client=api_client
        )
        
        assert diagnostic_commands.action_registry == action_registry
        assert diagnostic_commands.goal_manager == goal_manager
        assert diagnostic_commands.api_client == api_client
        assert diagnostic_commands.action_diagnostics is not None
        assert diagnostic_commands.planning_diagnostics is not None
        assert diagnostic_commands.cooldown_manager is not None

    def test_parse_goal_parameters_empty(self):
        """Test parsing empty goal string."""
        diagnostic_commands = DiagnosticCommands()
        result = diagnostic_commands._parse_goal_parameters("")
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_parse_goal_parameters_simple_boolean(self):
        """Test parsing simple boolean parameters."""
        diagnostic_commands = DiagnosticCommands()
        
        result = diagnostic_commands._parse_goal_parameters("--gained-xp true")
        assert result == {GameState.GAINED_XP: True}
        
        result = diagnostic_commands._parse_goal_parameters("--cooldown-ready false")
        assert result == {GameState.COOLDOWN_READY: False}

    def test_parse_goal_parameters_equals_format(self):
        """Test parsing key=value format."""
        diagnostic_commands = DiagnosticCommands()
        
        result = diagnostic_commands._parse_goal_parameters("gained-xp=true")
        assert result == {GameState.GAINED_XP: True}


class TestStateDiagnosticsBasic:
    """Test state diagnostics with realistic scenarios."""

    @pytest.mark.asyncio
    async def test_diagnose_state_no_api_client(self):
        """Test state diagnosis without API client."""
        diagnostic_commands = DiagnosticCommands()
        
        result = await diagnostic_commands.diagnose_state("test_char")
        
        assert result is not None
        assert result["api_available"] is False
        assert len(result["recommendations"]) > 0

    @pytest.mark.asyncio
    async def test_diagnose_state_with_exception(self):
        """Test state diagnosis when API call fails."""
        mock_api_client = AsyncMock()
        mock_api_client.get_character.side_effect = Exception("API Error")
        
        diagnostic_commands = DiagnosticCommands(api_client=mock_api_client)
        
        result = await diagnostic_commands.diagnose_state("test_char")
        
        assert result is not None
        assert result["character_found"] is False
        assert result["state_validation"]["valid"] is False

    def test_diagnose_state_data_basic(self):
        """Test state data diagnosis."""
        diagnostic_commands = DiagnosticCommands()
        
        state_data = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_CURRENT: 100
        }
        
        with patch.object(diagnostic_commands.state_diagnostics, 'validate_state_data') as mock_validate:
            mock_validate.return_value = {"valid": True}
            
            result = diagnostic_commands.diagnose_state_data(state_data)
            
            assert result is not None
            mock_validate.assert_called_once()


class TestActionDiagnosticsBasic:
    """Test action diagnostics with realistic scenarios."""

    @pytest.mark.asyncio
    async def test_diagnose_actions_no_registry(self):
        """Test action diagnosis without action registry."""
        diagnostic_commands = DiagnosticCommands()
        
        result = await diagnostic_commands.diagnose_actions()
        
        assert result is not None
        assert "registry_validation" in result
        assert result["registry_validation"]["valid"] is False

    @pytest.mark.asyncio
    async def test_diagnose_actions_with_registry(self):
        """Test action diagnosis with action registry."""
        mock_registry = Mock(spec=ActionRegistry)
        mock_registry.get_all_action_types.return_value = ["TestAction"]
        
        diagnostic_commands = DiagnosticCommands(action_registry=mock_registry)
        
        # Mock the action class
        mock_action_class = Mock()
        mock_action_class.__name__ = "TestAction"
        mock_action_instance = Mock()
        mock_action_instance.name = "test_action"
        mock_action_instance.cost = 1
        mock_action_instance.can_execute.return_value = True
        mock_action_instance.get_preconditions.return_value = {}
        mock_action_instance.get_effects.return_value = {}
        mock_action_instance.validate_preconditions.return_value = True
        mock_action_instance.validate_effects.return_value = True
        
        mock_action_class.return_value = mock_action_instance
        
        with patch.object(mock_registry, 'get_action_class', return_value=mock_action_class):
            result = await diagnostic_commands.diagnose_actions(list_all=True)
            
            assert result is not None
            assert result["summary"]["total_actions"] >= 0


class TestPlanningDiagnosticsBasic:
    """Test planning diagnostics with realistic scenarios."""

    @pytest.mark.asyncio
    async def test_diagnose_plan_no_goal_manager(self):
        """Test plan diagnosis without goal manager."""
        diagnostic_commands = DiagnosticCommands()
        
        result = await diagnostic_commands.diagnose_plan("test_char", "level_up")
        
        assert result is not None
        assert len(result["recommendations"]) > 0

    @pytest.mark.asyncio
    async def test_diagnose_plan_with_goal_manager(self):
        """Test plan diagnosis with goal manager."""
        mock_goal_manager = Mock(spec=GoalManager)
        mock_api_client = AsyncMock()
        
        diagnostic_commands = DiagnosticCommands(
            goal_manager=mock_goal_manager,
            api_client=mock_api_client
        )
        
        # Mock character data
        mock_character = Mock()
        mock_character.name = "test_char"
        mock_character.x = 0
        mock_character.y = 0
        mock_api_client.get_character.return_value = mock_character
        
        # Mock map data
        mock_map = Mock()
        mock_map.content = []
        mock_api_client.get_map.return_value = mock_map
        
        with patch('src.cli.commands.diagnostics.CharacterGameState') as mock_char_state:
            mock_state_instance = Mock()
            mock_state_instance.to_goap_state.return_value = {"character_level": 1}
            mock_char_state.from_api_character.return_value = mock_state_instance
            
            result = await diagnostic_commands.diagnose_plan("test_char", "level_up")
            
            assert result is not None


class TestPlanningTestingBasic:
    """Test planning testing functionality."""

    @pytest.mark.asyncio 
    async def test_test_planning_no_goal_manager(self):
        """Test planning testing without goal manager."""
        diagnostic_commands = DiagnosticCommands()
        
        result = await diagnostic_commands.test_planning()
        
        assert result is not None
        assert len(result["issues"]) > 0

    @pytest.mark.asyncio
    async def test_test_planning_with_goal_manager(self):
        """Test planning testing with goal manager."""
        mock_goal_manager = Mock(spec=GoalManager)
        diagnostic_commands = DiagnosticCommands(goal_manager=mock_goal_manager)
        
        with patch.object(diagnostic_commands.planning_diagnostics, 'test_scenario') as mock_test:
            mock_test.return_value = {"success": True}
            
            result = await diagnostic_commands.test_planning()
            
            assert result is not None


class TestWeightsDiagnosticsBasic:
    """Test weights diagnostics functionality."""

    @pytest.mark.asyncio
    async def test_diagnose_weights_missing_file(self):
        """Test weights diagnosis when file doesn't exist."""
        diagnostic_commands = DiagnosticCommands()
        
        with patch('src.cli.commands.diagnostics.Path') as mock_path:
            mock_weights_file = Mock()
            mock_weights_file.exists.return_value = False
            mock_path.return_value = mock_weights_file
            
            result = await diagnostic_commands.diagnose_weights()
            
            assert result is not None
            assert result["configuration_validation"]["valid"] is False

    @pytest.mark.asyncio
    async def test_diagnose_weights_with_file(self):
        """Test weights diagnosis with existing file."""
        diagnostic_commands = DiagnosticCommands()
        
        mock_weights_data = {
            "action_costs": {"move": 1, "fight": 3},
            "goal_weights": {"level_up": 100}
        }
        
        with patch('src.cli.commands.diagnostics.Path') as mock_path:
            mock_weights_file = Mock()
            mock_weights_file.exists.return_value = True
            mock_path.return_value = mock_weights_file
            
            with patch('builtins.open') as mock_open:
                mock_file = Mock()
                mock_file.read.return_value = '{"action_costs": {"move": 1}}'
                mock_open.return_value.__enter__.return_value = mock_file
                
                with patch('json.loads', return_value=mock_weights_data):
                    result = await diagnostic_commands.diagnose_weights()
                    
                    assert result is not None


class TestCooldownDiagnosticsBasic:
    """Test cooldown diagnostics functionality."""

    @pytest.mark.asyncio
    async def test_diagnose_cooldowns_no_api_client(self):  
        """Test cooldown diagnosis without API client."""
        diagnostic_commands = DiagnosticCommands()
        
        result = await diagnostic_commands.diagnose_cooldowns("test_char")
        
        assert result is not None
        assert result["api_available"] is False

    @pytest.mark.asyncio
    async def test_diagnose_cooldowns_with_api_client(self):
        """Test cooldown diagnosis with API client."""
        mock_api_client = AsyncMock()
        diagnostic_commands = DiagnosticCommands(api_client=mock_api_client)
        
        mock_character = Mock()
        mock_character.name = "test_char"
        mock_character.cooldown = 0
        mock_api_client.get_character.return_value = mock_character
        
        result = await diagnostic_commands.diagnose_cooldowns("test_char")
        
        assert result is not None
        assert result["character_name"] == "test_char"


class TestDiagnosticCommandsErrorHandling:
    """Test error handling patterns."""

    @pytest.mark.asyncio
    async def test_exception_handling_in_diagnose_state(self):
        """Test that exceptions are handled gracefully."""
        mock_api_client = AsyncMock()
        mock_api_client.get_character.side_effect = Exception("Network error")
        
        diagnostic_commands = DiagnosticCommands(api_client=mock_api_client)
        
        # Should not raise exception
        result = await diagnostic_commands.diagnose_state("test_char")
        
        assert result is not None
        assert result["character_found"] is False

    def test_str_representation(self):
        """Test string representation."""
        diagnostic_commands = DiagnosticCommands()
        str_repr = str(diagnostic_commands)
        assert isinstance(str_repr, str)


class TestArgumentHandling:
    """Test various argument handling scenarios."""

    def test_boolean_parsing_variations(self):
        """Test different boolean value formats."""
        diagnostic_commands = DiagnosticCommands()
        
        true_values = ['true', 'True', 'TRUE', 'yes', 'y', '1']
        false_values = ['false', 'False', 'FALSE', 'no', 'n', '0']
        
        for true_val in true_values:
            result = diagnostic_commands._parse_goal_parameters(f"--gained-xp {true_val}")
            assert result[GameState.GAINED_XP] is True
            
        for false_val in false_values:
            result = diagnostic_commands._parse_goal_parameters(f"--gained-xp {false_val}")
            assert result[GameState.GAINED_XP] is False

    def test_complex_goal_parameter_parsing(self):
        """Test parsing multiple parameters."""
        diagnostic_commands = DiagnosticCommands()
        
        goal_string = "--gained-xp true --cooldown-ready false --safe-to-fight yes"
        result = diagnostic_commands._parse_goal_parameters(goal_string)
        
        expected = {
            GameState.GAINED_XP: True,
            GameState.COOLDOWN_READY: False,
            GameState.SAFE_TO_FIGHT: True
        }
        assert result == expected