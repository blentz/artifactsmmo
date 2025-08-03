"""
Tests for CLI diagnostic commands

This module tests the DiagnosticCommands class implementation including
state diagnostics, action analysis, and GOAP planning visualization.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.ai_player.actions import ActionRegistry
from src.ai_player.goal_manager import GoalManager
from src.ai_player.state.character_game_state import CharacterGameState
from src.ai_player.state.game_state import CooldownInfo, GameState
from src.ai_player.types.goap_models import GOAPAction, GOAPActionPlan, GOAPTargetState
from src.cli.commands.diagnostics import DiagnosticCommands
from src.game_data.api_client import APIClientWrapper


class TestDiagnosticCommandsInit:
    """Test DiagnosticCommands initialization"""

    def test_init_with_no_dependencies(self):
        """Test initialization without dependencies"""
        diagnostics = DiagnosticCommands()

        assert diagnostics.state_diagnostics is not None
        assert diagnostics.action_diagnostics is None
        assert diagnostics.planning_diagnostics is None
        assert diagnostics.action_registry is None
        assert diagnostics.goal_manager is None

    def test_init_with_action_registry(self):
        """Test initialization with ActionRegistry"""
        mock_registry = Mock(spec=ActionRegistry)
        diagnostics = DiagnosticCommands(action_registry=mock_registry)

        assert diagnostics.action_registry is mock_registry
        assert diagnostics.action_diagnostics is not None
        assert diagnostics.planning_diagnostics is None

    def test_init_with_goal_manager(self):
        """Test initialization with GoalManager"""
        mock_goal_manager = AsyncMock(spec=GoalManager)
        diagnostics = DiagnosticCommands(goal_manager=mock_goal_manager)

        assert diagnostics.goal_manager is mock_goal_manager
        assert diagnostics.planning_diagnostics is not None
        assert diagnostics.action_diagnostics is None

    def test_init_with_all_dependencies(self):
        """Test initialization with all dependencies"""
        mock_registry = Mock(spec=ActionRegistry)
        mock_goal_manager = AsyncMock(spec=GoalManager)

        diagnostics = DiagnosticCommands(
            action_registry=mock_registry,
            goal_manager=mock_goal_manager
        )

        assert diagnostics.action_registry is mock_registry
        assert diagnostics.goal_manager is mock_goal_manager
        assert diagnostics.action_diagnostics is not None
        assert diagnostics.planning_diagnostics is not None
        assert diagnostics.api_client is None
        assert diagnostics.cooldown_manager is None

    def test_init_with_api_client(self):
        """Test initialization with API client"""
        mock_api_client = Mock(spec=APIClientWrapper)
        diagnostics = DiagnosticCommands(api_client=mock_api_client)

        assert diagnostics.api_client is mock_api_client
        assert diagnostics.cooldown_manager is not None
        assert diagnostics.action_diagnostics is None
        assert diagnostics.planning_diagnostics is None

    def test_init_with_all_dependencies_including_api(self):
        """Test initialization with all dependencies including API client"""
        mock_registry = Mock(spec=ActionRegistry)
        mock_goal_manager = AsyncMock(spec=GoalManager)
        mock_api_client = Mock(spec=APIClientWrapper)

        diagnostics = DiagnosticCommands(
            action_registry=mock_registry,
            goal_manager=mock_goal_manager,
            api_client=mock_api_client
        )

        assert diagnostics.action_registry is mock_registry
        assert diagnostics.goal_manager is mock_goal_manager
        assert diagnostics.action_diagnostics is not None
        assert diagnostics.planning_diagnostics is not None
        assert diagnostics.api_client is mock_api_client
        assert diagnostics.cooldown_manager is not None


class TestValidateStateKeys:
    """Test validate_state_keys method"""

    def test_validate_state_keys_valid_keys(self):
        """Test validation with valid GameState keys"""
        diagnostics = DiagnosticCommands()

        valid_state = {
            "character_level": 10,
            "character_xp": 2500,
            "hp_current": 90,
            "hp_max": 100
        }

        invalid_keys = diagnostics.validate_state_keys(valid_state)
        assert isinstance(invalid_keys, list)
        # StateDiagnostics should validate these keys exist in GameState enum

    def test_validate_state_keys_invalid_keys(self):
        """Test validation with invalid keys"""
        diagnostics = DiagnosticCommands()

        invalid_state = {
            "invalid_key": 123,
            "another_invalid": "test",
            "character_level": 10  # This one is valid
        }

        invalid_keys = diagnostics.validate_state_keys(invalid_state)
        assert isinstance(invalid_keys, list)
        # Should identify the invalid keys

    def test_validate_state_keys_empty_dict(self):
        """Test validation with empty dictionary"""
        diagnostics = DiagnosticCommands()

        invalid_keys = diagnostics.validate_state_keys({})
        assert isinstance(invalid_keys, list)
        assert len(invalid_keys) == 0


class TestFormatMethods:
    """Test formatting methods"""

    def test_format_state_output(self):
        """Test state output formatting"""
        diagnostics = DiagnosticCommands()

        state_data = {
            GameState.CHARACTER_LEVEL: 15,
            GameState.CHARACTER_XP: 3500,
            GameState.HP_CURRENT: 85,
            GameState.HP_MAX: 100,
            GameState.CURRENT_X: 25,
            GameState.CURRENT_Y: 30
        }

        formatted = diagnostics.format_state_output(state_data)
        assert isinstance(formatted, str)
        assert len(formatted) > 0

    def test_format_action_output_empty(self):
        """Test action output formatting with empty data"""
        diagnostics = DiagnosticCommands()

        formatted = diagnostics.format_action_output({})
        assert isinstance(formatted, str)
        assert "No action data to display" in formatted

    def test_format_action_output_with_data(self):
        """Test action output formatting with action data"""
        diagnostics = DiagnosticCommands()

        # Create a proper diagnostic result dict structure
        diagnostic_result = {
            "character_name": "test_character",
            "registry_available": True,
            "summary": {
                "total_actions": 2,
                "executable_actions": 1,
                "cost_range": {"min": 3, "max": 5},
                "action_types": {"movement": 1, "combat": 1}
            },
            "registry_validation": {
                "valid": True,
                "errors": [],
                "warnings": []
            },
            "actions_analyzed": [
                {
                    "name": "move_to_forest",
                    "cost": 3,
                    "executable": True,
                    "preconditions": {"cooldown_ready": True},
                    "effects": {"current_x": 10, "current_y": 15}
                },
                {
                    "name": "fight_goblin",
                    "cost": 5,
                    "executable": False,
                    "issues": ["Not enough HP"]
                }
            ],
            "recommendations": []
        }

        formatted = diagnostics.format_action_output(diagnostic_result)
        assert isinstance(formatted, str)
        assert "move_to_forest" in formatted
        assert "fight_goblin" in formatted
        assert "Cost: 3" in formatted
        assert "Not enough HP" in formatted

    def test_format_planning_output_empty(self):
        """Test planning output formatting with empty data"""
        diagnostics = DiagnosticCommands()

        formatted = diagnostics.format_planning_output({})
        assert isinstance(formatted, str)
        assert "No planning data to display" in formatted

    def test_format_planning_output_with_data(self):
        """Test planning output formatting with planning data"""
        diagnostics = DiagnosticCommands()

        # Create proper diagnostic result structure
        diagnostic_result = {
            "character_name": "test_character",
            "goal": "level_up",
            "planning_available": True,
            "planning_analysis": {
                "planning_successful": True,
                "total_cost": 15,
                "planning_time": 0.123,
                "steps": [
                    {"name": "move_action", "cost": 3},
                    {"name": "fight_action", "cost": 7},
                    {"name": "rest_action", "cost": 5}
                ],
                "efficiency_score": 85.5
            },
            "plan_steps": [
                {"name": "move_action", "cost": 3},
                {"name": "fight_action", "cost": 7},
                {"name": "rest_action", "cost": 5}
            ],
            "recommendations": ["Consider combining movement actions"],
            "diagnostic_time": "2024-01-01T12:00:00"
        }

        formatted = diagnostics.format_planning_output(diagnostic_result)
        assert isinstance(formatted, str)
        assert "test_character" in formatted
        assert "level_up" in formatted
        assert "move_action" in formatted
        assert "Consider combining movement actions" in formatted


class TestDiagnoseStateMethods:
    """Test state diagnosis methods"""

    @pytest.mark.asyncio
    async def test_diagnose_state_basic(self):
        """Test basic state diagnosis"""
        diagnostics = DiagnosticCommands()

        result = await diagnostics.diagnose_state("test_character")

        assert isinstance(result, dict)
        assert "character_name" in result
        assert "diagnostic_time" in result
        assert "recommendations" in result
        assert result["character_name"] == "test_character"
        assert result["api_available"] is False

    @pytest.mark.asyncio
    async def test_diagnose_state_with_api_client(self):
        """Test state diagnosis with API client"""

        # Mock character data
        mock_character_data = Mock()
        mock_character_data.name = "test_character"
        mock_character_data.level = 10
        mock_character_data.xp = 2500
        mock_character_data.max_xp = 3000
        mock_character_data.gold = 150
        mock_character_data.hp = 85
        mock_character_data.max_hp = 100
        mock_character_data.x = 5
        mock_character_data.y = 10
        mock_character_data.skin = "default"

        # Mock character game state object
        mock_character_game_state = Mock()
        mock_character_game_state.to_goap_state.return_value = {
            GameState.CHARACTER_LEVEL.value: 10,
            GameState.CHARACTER_XP.value: 2500,
            GameState.HP_CURRENT.value: 85,
            GameState.HP_MAX.value: 100
        }

        # Mock API client
        mock_api_client = Mock(spec=APIClientWrapper)
        mock_api_client.get_character = AsyncMock(return_value=mock_character_data)

        # Mock CharacterGameState.from_api_character
        with patch.object(CharacterGameState, 'from_api_character', return_value=mock_character_game_state):
            diagnostics = DiagnosticCommands(api_client=mock_api_client)
            result = await diagnostics.diagnose_state("test_character")

        assert isinstance(result, dict)
        assert result["api_available"] is True
        assert result["character_found"] is True
        assert "api_character_data" in result
        assert result["api_character_data"]["level"] == 10
        assert result["api_character_data"]["hp"] == 85
        mock_api_client.get_character.assert_called_once_with("test_character")

    @pytest.mark.asyncio
    async def test_diagnose_state_api_error(self):
        """Test API error propagation following fail-fast principles"""
        mock_api_client = Mock(spec=APIClientWrapper)
        mock_api_client.get_character = AsyncMock(side_effect=Exception("Character not found"))

        diagnostics = DiagnosticCommands(api_client=mock_api_client)

        # Should propagate exception following fail-fast principles
        with pytest.raises(Exception, match="Character not found"):
            await diagnostics.diagnose_state("test_character")

    @pytest.mark.asyncio
    async def test_diagnose_state_with_validation(self):
        """Test state diagnosis with validation enabled"""
        diagnostics = DiagnosticCommands()

        result = await diagnostics.diagnose_state("test_character", validate_enum=True)

        assert isinstance(result, dict)
        assert "state_validation" in result
        assert "recommendations" in result

    def test_diagnose_state_data_complete(self):
        """Test state data diagnosis with complete state"""
        diagnostics = DiagnosticCommands()

        complete_state = {
            GameState.CHARACTER_LEVEL: 10,
            GameState.CHARACTER_XP: 2500,
            GameState.CHARACTER_GOLD: 150,
            GameState.HP_CURRENT: 90,
            GameState.HP_MAX: 100,
            GameState.CURRENT_X: 25,
            GameState.CURRENT_Y: 30,
            GameState.COOLDOWN_READY: True
        }

        result = diagnostics.diagnose_state_data(complete_state)

        assert isinstance(result, dict)
        assert "state_validation" in result
        assert "state_statistics" in result
        assert "recommendations" in result
        assert result["state_validation"]["valid"] is True

    def test_diagnose_state_data_invalid_values(self):
        """Test state data diagnosis with invalid values"""
        diagnostics = DiagnosticCommands()

        invalid_state = {
            GameState.CHARACTER_LEVEL: -5,  # Invalid negative level
            GameState.HP_CURRENT: 150,      # HP exceeds max
            GameState.HP_MAX: 100,
            GameState.CHARACTER_GOLD: -10   # Invalid negative gold
        }

        result = diagnostics.diagnose_state_data(invalid_state)

        assert isinstance(result, dict)
        assert result["state_validation"]["valid"] is False
        assert len(result["state_validation"]["invalid_values"]) > 0
        assert len(result["recommendations"]) > 0

    def test_diagnose_state_data_with_enum_validation(self):
        """Test state data diagnosis with enum validation"""
        diagnostics = DiagnosticCommands()

        state_data = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_CURRENT: 80,
            GameState.COOLDOWN_READY: True
        }

        result = diagnostics.diagnose_state_data(state_data, validate_enum=True)

        assert isinstance(result, dict)
        assert "state_validation" in result
        # Should validate that all keys are proper GameState enums

    def test_diagnose_state_data_low_health_recommendation(self):
        """Test state data diagnosis with low health triggers recommendation"""
        diagnostics = DiagnosticCommands()

        low_health_state = {
            GameState.CHARACTER_LEVEL: 10,
            GameState.HP_CURRENT: 40,  # Low health
            GameState.HP_MAX: 100,
            GameState.COOLDOWN_READY: True
        }

        result = diagnostics.diagnose_state_data(low_health_state)

        assert isinstance(result, dict)
        # Should generate recommendation for low health
        health_recommendation = any("health is low" in rec.lower() for rec in result["recommendations"])
        assert health_recommendation

    def test_diagnose_state_data_low_level_recommendation(self):
        """Test state data diagnosis with low level triggers recommendation"""
        diagnostics = DiagnosticCommands()

        low_level_state = {
            GameState.CHARACTER_LEVEL: 3,  # Low level
            GameState.HP_CURRENT: 100,
            GameState.HP_MAX: 100,
            GameState.COOLDOWN_READY: True
        }

        result = diagnostics.diagnose_state_data(low_level_state)

        assert isinstance(result, dict)
        # Should generate recommendation for low level
        level_recommendation = any("low character level" in rec.lower() for rec in result["recommendations"])
        assert level_recommendation

    def test_diagnose_state_data_with_invalid_enum_keys(self):
        """Test state diagnosis when enum validation finds invalid keys"""
        diagnostics = DiagnosticCommands()

        state_data = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_CURRENT: 80,
        }

        # Mock the state diagnostics to return invalid keys
        with patch.object(diagnostics.state_diagnostics, 'validate_state_enum_usage', return_value=['invalid_key1', 'invalid_key2']):
            result = diagnostics.diagnose_state_data(state_data, validate_enum=True)

        assert isinstance(result, dict)
        assert result["state_validation"]["valid"] is False
        assert len(result["state_validation"]["invalid_keys"]) == 2
        assert "Found 2 invalid enum keys" in result["state_validation"]["issues"]

    def test_diagnose_state_data_exception_handling(self):
        """Test exception propagation following fail-fast principles"""
        diagnostics = DiagnosticCommands()

        # Mock state diagnostics to raise an exception
        with patch.object(diagnostics.state_diagnostics, 'validate_state_completeness', side_effect=Exception("Test error")):
            # Should propagate exception following fail-fast principles
            with pytest.raises(Exception, match="Test error"):
                diagnostics.diagnose_state_data({GameState.CHARACTER_LEVEL: 5})


class TestDiagnoseActionsMethods:
    """Test action diagnosis methods"""

    @pytest.mark.asyncio
    async def test_diagnose_actions_no_registry(self):
        """Test action diagnosis without ActionRegistry"""
        diagnostics = DiagnosticCommands()  # No registry provided

        result = await diagnostics.diagnose_actions("test_character")

        assert isinstance(result, dict)
        assert result["registry_available"] is False
        assert "ActionRegistry required" in str(result["recommendations"])

    @pytest.mark.asyncio
    async def test_diagnose_actions_with_registry(self):
        """Test action diagnosis with ActionRegistry"""
        mock_registry = Mock(spec=ActionRegistry)
        mock_registry.get_all_action_types.return_value = [
            Mock(__name__="MockAction", name="test_action", cost=5),
        ]

        diagnostics = DiagnosticCommands(action_registry=mock_registry)

        with patch.object(diagnostics.action_diagnostics, 'validate_action_registry', return_value=[]):
            with patch.object(diagnostics.action_diagnostics, 'validate_action_costs', return_value=[]):
                result = await diagnostics.diagnose_actions("test_character")

        assert isinstance(result, dict)
        assert result["registry_available"] is True
        assert "summary" in result
        assert "actions_analyzed" in result

    @pytest.mark.asyncio
    async def test_diagnose_actions_show_costs(self):
        """Test action diagnosis with cost details"""
        mock_action_class = Mock()
        mock_action_instance = Mock()
        mock_action_instance.name = "test_action"
        mock_action_instance.cost = 3
        mock_action_instance.get_preconditions.return_value = {}
        mock_action_instance.get_effects.return_value = {}
        mock_action_instance.validate_preconditions.return_value = True
        mock_action_instance.validate_effects.return_value = True
        mock_action_class.return_value = mock_action_instance
        mock_action_class.__name__ = "TestAction"

        mock_registry = Mock(spec=ActionRegistry)
        mock_registry.get_all_action_types.return_value = [mock_action_class]

        diagnostics = DiagnosticCommands(action_registry=mock_registry)

        with patch.object(diagnostics.action_diagnostics, 'validate_action_registry', return_value=[]):
            with patch.object(diagnostics.action_diagnostics, 'validate_action_costs', return_value=[]):
                result = await diagnostics.diagnose_actions(
                    "test_character",
                    show_costs=True,
                    show_preconditions=True
                )

        assert isinstance(result, dict)
        assert "summary" in result
        assert "cost_range" in result["summary"]

    @pytest.mark.asyncio
    async def test_diagnose_actions_with_registry_errors(self):
        """Test action diagnosis with registry validation errors"""
        mock_registry = Mock(spec=ActionRegistry)
        mock_registry.get_all_action_types.return_value = []

        diagnostics = DiagnosticCommands(action_registry=mock_registry)

        with patch.object(diagnostics.action_diagnostics, 'validate_action_registry', return_value=['Error 1', 'Error 2']):
            with patch.object(diagnostics.action_diagnostics, 'validate_action_costs', return_value=['Warning 1']):
                result = await diagnostics.diagnose_actions("test_character")

        assert isinstance(result, dict)
        assert result["registry_validation"]["valid"] is False
        assert len(result["registry_validation"]["errors"]) == 2
        assert len(result["registry_validation"]["warnings"]) == 1

    @pytest.mark.asyncio
    async def test_diagnose_actions_action_analysis_exception(self):
        """Test exception propagation following fail-fast principles"""
        mock_action_class = Mock()
        mock_action_class.side_effect = Exception("Action creation failed")
        mock_action_class.__name__ = "FailingAction"

        mock_registry = Mock(spec=ActionRegistry)
        mock_registry.get_all_action_types.return_value = [mock_action_class]

        diagnostics = DiagnosticCommands(action_registry=mock_registry)

        with patch.object(diagnostics.action_diagnostics, 'validate_action_registry', return_value=[]):
            with patch.object(diagnostics.action_diagnostics, 'validate_action_costs', return_value=[]):
                # Should propagate exception following fail-fast principles
                with pytest.raises(Exception, match="Action creation failed"):
                    await diagnostics.diagnose_actions("test_character")

    @pytest.mark.asyncio
    async def test_diagnose_actions_general_exception(self):
        """Test exception propagation following fail-fast principles"""
        mock_registry = Mock(spec=ActionRegistry)
        diagnostics = DiagnosticCommands(action_registry=mock_registry)

        with patch.object(diagnostics.action_diagnostics, 'validate_action_registry', side_effect=Exception("Registry failed")):
            # Should propagate exception following fail-fast principles
            with pytest.raises(Exception, match="Registry failed"):
                await diagnostics.diagnose_actions("test_character")


class TestDiagnosePlanMethods:
    """Test plan diagnosis methods"""

    @pytest.mark.asyncio
    async def test_diagnose_plan_no_planning_diagnostics(self):
        """Test plan diagnosis without PlanningDiagnostics"""
        diagnostics = DiagnosticCommands()  # No goal manager provided

        result = await diagnostics.diagnose_plan("test_character", "level_up")

        assert isinstance(result, dict)
        assert result["planning_available"] is False
        assert "GoalManager required" in str(result["recommendations"])

    @pytest.mark.asyncio
    async def test_diagnose_plan_with_planning_diagnostics(self):
        """Test plan diagnosis with PlanningDiagnostics"""
        mock_goal_manager = AsyncMock(spec=GoalManager)
        diagnostics = DiagnosticCommands(goal_manager=mock_goal_manager)

        with patch.object(diagnostics.planning_diagnostics, 'test_goal_reachability', return_value=True):
            with patch.object(diagnostics.planning_diagnostics, 'identify_planning_bottlenecks', return_value=[]):
                with patch.object(diagnostics.planning_diagnostics, 'measure_planning_performance',
                                return_value={"success": True, "performance_class": "fast"}):
                    result = await diagnostics.diagnose_plan("test_character", "level_up")

        assert isinstance(result, dict)
        assert result["planning_available"] is True
        assert "planning_analysis" in result
        assert "bottlenecks" in result
        assert "performance_metrics" in result

    @pytest.mark.asyncio
    async def test_diagnose_plan_unreachable_goal(self):
        """Test plan diagnosis with unreachable goal"""
        mock_goal_manager = AsyncMock(spec=GoalManager)
        # Mock goal manager methods to simulate unreachable goal
        # Create proper GOAPTargetState for unreachable goal
        unreachable_goal = GOAPTargetState(target_states={GameState.CHARACTER_LEVEL: 100})
        mock_goal_manager.select_next_goal.return_value = unreachable_goal
        # Create empty GOAPActionPlan for unreachable goal
        empty_plan = GOAPActionPlan(actions=[], total_cost=0, estimated_duration=0.0, plan_id="empty")
        mock_goal_manager.plan_actions = AsyncMock(return_value=empty_plan)

        diagnostics = DiagnosticCommands(goal_manager=mock_goal_manager)

        # Mock all the planning diagnostic methods
        diagnostics.planning_diagnostics.test_goal_reachability = AsyncMock(return_value=False)
        diagnostics.planning_diagnostics.analyze_planning_steps = AsyncMock(return_value={"planning_successful": False, "steps": []})
        diagnostics.planning_diagnostics.identify_planning_bottlenecks = AsyncMock(return_value=['Bottleneck 1'])
        diagnostics.planning_diagnostics.measure_planning_performance = AsyncMock(
            return_value={"success": False, "performance_class": "slow"}
        )

        result = await diagnostics.diagnose_plan("test_character", "level_up", verbose=True)

        assert isinstance(result, dict)
        unreachable_recommendation = any("Goal appears to be unreachable" in rec for rec in result["recommendations"])
        assert unreachable_recommendation
        assert len(result["bottlenecks"]) > 0
        bottleneck_recommendation = any("bottlenecks to address" in rec for rec in result["recommendations"])
        assert bottleneck_recommendation

    @pytest.mark.asyncio
    async def test_diagnose_plan_with_verbose_and_analysis(self):
        """Test plan diagnosis with verbose mode and successful analysis"""
        mock_goal_manager = AsyncMock(spec=GoalManager)
        # Mock goal manager methods to simulate successful planning
        # Create proper GOAPTargetState for successful goal
        successful_goal = GOAPTargetState(target_states={GameState.CHARACTER_LEVEL: 5})
        mock_goal_manager.select_next_goal.return_value = successful_goal
        # Create non-empty GOAPActionPlan for successful planning
        successful_action = GOAPAction(name="action1", action_type="test", cost=5)
        successful_plan = GOAPActionPlan(actions=[successful_action], total_cost=5, estimated_duration=1.0, plan_id="success")
        mock_goal_manager.plan_actions = AsyncMock(return_value=successful_plan)

        diagnostics = DiagnosticCommands(goal_manager=mock_goal_manager)

        mock_planning_steps = {
            "planning_successful": True,
            "steps": [{"name": "action1", "cost": 5}]
        }

        mock_efficiency = {
            "efficiency_score": 75.0,
            "optimization_suggestions": ["Test suggestion"]
        }

        with patch.object(diagnostics.planning_diagnostics, 'test_goal_reachability', new_callable=AsyncMock, return_value=True):
            with patch.object(diagnostics.planning_diagnostics, 'analyze_planning_steps', new_callable=AsyncMock, return_value=mock_planning_steps):
                with patch.object(diagnostics.planning_diagnostics, 'analyze_plan_efficiency', return_value=mock_efficiency):
                    with patch.object(diagnostics.planning_diagnostics, 'identify_planning_bottlenecks', new_callable=AsyncMock, return_value=[]):
                        with patch.object(diagnostics.planning_diagnostics, 'measure_planning_performance',
                                        new_callable=AsyncMock, return_value={"success": True, "performance_class": "fast"}):
                            result = await diagnostics.diagnose_plan("test_character", "level_up", verbose=True)

        assert isinstance(result, dict)
        assert result["planning_analysis"]["planning_successful"] is True
        assert "plan_efficiency" in result

    @pytest.mark.asyncio
    async def test_diagnose_plan_exception_handling(self):
        """Test exception propagation following fail-fast principles"""
        mock_goal_manager = AsyncMock(spec=GoalManager)
        diagnostics = DiagnosticCommands(goal_manager=mock_goal_manager)

        with patch.object(diagnostics.planning_diagnostics, 'test_goal_reachability', new_callable=AsyncMock, side_effect=Exception("Planning failed")):
            # Should propagate exception following fail-fast principles
            with pytest.raises(Exception, match="Planning failed"):
                await diagnostics.diagnose_plan("test_character", "level_up")




class TestTestPlanningMethod:
    """Test test_planning method"""

    @pytest.mark.asyncio
    async def test_test_planning_no_diagnostics(self):
        """Test planning test without PlanningDiagnostics"""
        diagnostics = DiagnosticCommands()

        result = await diagnostics.test_planning()

        assert isinstance(result, dict)
        assert result["planning_available"] is False
        assert result["overall_success"] is False

    @pytest.mark.asyncio
    async def test_test_planning_with_mock_file(self):
        """Test planning test with mock state file"""
        mock_goal_manager = AsyncMock(spec=GoalManager)
        diagnostics = DiagnosticCommands(goal_manager=mock_goal_manager)

        mock_state_data = {
            "character_level": 5,
            "character_gold": 100,
            "hp_current": 100,
            "hp_max": 100,
            "cooldown_ready": True
        }

        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.open', create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_state_data)
                with patch('json.load', return_value=mock_state_data):
                    with patch.object(diagnostics.planning_diagnostics, 'test_goal_reachability') as mock_reachability:
                        async def mock_reachability_func():
                            return True
                        mock_reachability.side_effect = mock_reachability_func
                        with patch.object(diagnostics.planning_diagnostics, 'measure_planning_performance') as mock_performance:
                            async def mock_performance_func():
                                return {"success": True, "planning_time_seconds": 0.1, "plan_length": 3}
                            mock_performance.side_effect = mock_performance_func
                            result = await diagnostics.test_planning(mock_state_file="test_state.json", goal_level=10)

        assert isinstance(result, dict)
        assert "scenarios_tested" in result
        assert "performance_summary" in result

    @pytest.mark.asyncio
    async def test_test_planning_default_scenarios(self):
        """Test planning test with default scenarios"""
        mock_goal_manager = AsyncMock(spec=GoalManager)
        diagnostics = DiagnosticCommands(goal_manager=mock_goal_manager)

        with patch.object(diagnostics.planning_diagnostics, 'test_goal_reachability', new_callable=AsyncMock, return_value=True):
            with patch.object(diagnostics.planning_diagnostics, 'measure_planning_performance',
                            new_callable=AsyncMock, return_value={"success": True, "planning_time_seconds": 0.05, "plan_length": 2}):
                result = await diagnostics.test_planning(start_level=1, goal_level=5)

        assert isinstance(result, dict)
        assert result["overall_success"] is True
        assert "scenarios_tested" in result
        assert len(result["scenarios_tested"]) >= 2  # Should test multiple scenarios


class TestDiagnoseWeightsMethod:
    """Test diagnose_weights method"""

    @pytest.mark.asyncio
    async def test_diagnose_weights_no_action_diagnostics(self):
        """Test weight diagnosis without ActionDiagnostics"""
        diagnostics = DiagnosticCommands()

        result = await diagnostics.diagnose_weights()

        assert isinstance(result, dict)
        assert result["action_diagnostics_available"] is False
        assert "ActionRegistry required" in str(result["recommendations"])

    @pytest.mark.asyncio
    async def test_diagnose_weights_with_action_diagnostics(self):
        """Test weight diagnosis with ActionDiagnostics"""
        mock_action_class = Mock()
        mock_action_instance = Mock()
        mock_action_instance.name = "test_action"
        mock_action_instance.cost = 5
        mock_action_class.return_value = mock_action_instance
        mock_action_class.__name__ = "TestAction"

        mock_registry = Mock(spec=ActionRegistry)
        mock_registry.get_all_action_types.return_value = [mock_action_class]

        diagnostics = DiagnosticCommands(action_registry=mock_registry)

        with patch.object(diagnostics.action_diagnostics, 'validate_action_costs', return_value=[]):
            with patch.object(diagnostics.action_diagnostics, 'detect_action_conflicts', return_value=[]):
                result = await diagnostics.diagnose_weights(show_action_costs=True)

        assert isinstance(result, dict)
        assert result["action_diagnostics_available"] is True
        assert "cost_analysis" in result
        assert "configuration_validation" in result

    @pytest.mark.asyncio
    async def test_diagnose_weights_cost_outliers(self):
        """Test weight diagnosis with cost outliers"""
        # Create actions with very different costs
        mock_cheap_action = Mock()
        mock_cheap_action.name = "cheap_action"
        mock_cheap_action.cost = 1
        mock_cheap_class = Mock()
        mock_cheap_class.return_value = mock_cheap_action
        mock_cheap_class.__name__ = "CheapAction"

        mock_expensive_action = Mock()
        mock_expensive_action.name = "expensive_action"
        mock_expensive_action.cost = 100  # 100x more expensive
        mock_expensive_class = Mock()
        mock_expensive_class.return_value = mock_expensive_action
        mock_expensive_class.__name__ = "ExpensiveAction"

        mock_registry = Mock(spec=ActionRegistry)
        mock_registry.get_all_action_types.return_value = [mock_cheap_class, mock_expensive_class]

        diagnostics = DiagnosticCommands(action_registry=mock_registry)

        with patch.object(diagnostics.action_diagnostics, 'validate_action_costs', return_value=[]):
            with patch.object(diagnostics.action_diagnostics, 'detect_action_conflicts', return_value=[]):
                result = await diagnostics.diagnose_weights()

        assert isinstance(result, dict)
        assert "cost_analysis" in result
        assert "outliers" in result["cost_analysis"]


class TestDiagnoseCooldownsMethod:
    """Test diagnose_cooldowns method"""

    @pytest.mark.asyncio
    async def test_diagnose_cooldowns_basic(self):
        """Test basic cooldown diagnosis"""
        diagnostics = DiagnosticCommands()

        result = await diagnostics.diagnose_cooldowns("test_character")

        assert isinstance(result, dict)
        assert "character_name" in result
        assert "cooldown_status" in result
        assert "timing_analysis" in result
        assert "recommendations" in result
        assert result["character_name"] == "test_character"
        assert result["api_available"] is False

    @pytest.mark.asyncio
    async def test_diagnose_cooldowns_with_monitoring(self):
        """Test cooldown diagnosis with monitoring enabled"""
        diagnostics = DiagnosticCommands()

        result = await diagnostics.diagnose_cooldowns("test_character", monitor=True)

        assert isinstance(result, dict)
        assert "monitoring_data" in result
        assert len(result["monitoring_data"]) > 0
        assert "monitoring_started" in result["monitoring_data"][0]["status"]

    @pytest.mark.asyncio
    async def test_diagnose_cooldowns_with_api_client(self):
        """Test cooldown diagnosis with API client"""

        # Mock character data
        mock_character_data = Mock()
        mock_character_data.name = "test_character"
        mock_character_data.level = 10
        mock_character_data.hp = 85
        mock_character_data.max_hp = 100
        mock_character_data.x = 5
        mock_character_data.y = 10
        mock_character_data.speed = 5

        # Mock API client
        mock_api_client = Mock(spec=APIClientWrapper)
        mock_api_client.get_character = AsyncMock(return_value=mock_character_data)

        diagnostics = DiagnosticCommands(api_client=mock_api_client)

        # Mock cooldown manager
        diagnostics.cooldown_manager.get_cooldown_info = Mock(return_value=None)
        diagnostics.cooldown_manager.is_ready = Mock(return_value=True)
        diagnostics.cooldown_manager.get_remaining_time = Mock(return_value=0.0)

        result = await diagnostics.diagnose_cooldowns("test_character")

        assert isinstance(result, dict)
        assert result["api_available"] is True
        assert result["character_found"] is True
        assert result["cooldown_status"]["ready"] is True
        assert result["cooldown_status"]["remaining_seconds"] == 0.0
        assert result["cooldown_status"]["compliance_status"] == "compliant"
        mock_api_client.get_character.assert_called_once_with("test_character")

    @pytest.mark.asyncio
    async def test_diagnose_cooldowns_on_cooldown(self):
        """Test cooldown diagnosis when character is on cooldown"""

        # Mock character data
        mock_character_data = Mock()
        mock_character_data.name = "test_character"
        mock_character_data.level = 10
        mock_character_data.hp = 85
        mock_character_data.max_hp = 100
        mock_character_data.x = 5
        mock_character_data.y = 10
        mock_character_data.speed = 5

        # Mock cooldown info
        future_time = datetime.now() + timedelta(seconds=15)
        mock_cooldown_info = CooldownInfo(
            character_name="test_character",
            expiration=future_time.isoformat(),
            total_seconds=30,
            remaining_seconds=15,
            reason="movement"
        )

        # Mock API client
        mock_api_client = Mock(spec=APIClientWrapper)
        mock_api_client.get_character = AsyncMock(return_value=mock_character_data)

        diagnostics = DiagnosticCommands(api_client=mock_api_client)

        # Mock cooldown manager
        diagnostics.cooldown_manager.get_cooldown_info = Mock(return_value=mock_cooldown_info)
        diagnostics.cooldown_manager.is_ready = Mock(return_value=False)
        diagnostics.cooldown_manager.get_remaining_time = Mock(return_value=15.0)

        result = await diagnostics.diagnose_cooldowns("test_character")

        assert isinstance(result, dict)
        assert result["cooldown_status"]["ready"] is False
        assert result["cooldown_status"]["remaining_seconds"] == 15.0
        assert result["cooldown_status"]["compliance_status"] == "on_cooldown"
        assert result["cooldown_status"]["reason"] == "movement"

    @pytest.mark.asyncio
    async def test_diagnose_cooldowns_with_monitoring_and_api(self):
        """Test cooldown diagnosis with monitoring and API client"""
        # Mock character data
        mock_character_data = Mock()
        mock_character_data.name = "test_character"
        mock_character_data.level = 10
        mock_character_data.hp = 85
        mock_character_data.max_hp = 100
        mock_character_data.x = 5
        mock_character_data.y = 10
        mock_character_data.speed = 5

        # Mock API client
        mock_api_client = Mock(spec=APIClientWrapper)
        mock_api_client.get_character = AsyncMock(return_value=mock_character_data)

        diagnostics = DiagnosticCommands(api_client=mock_api_client)

        # Mock cooldown manager
        diagnostics.cooldown_manager.get_cooldown_info = Mock(return_value=None)
        diagnostics.cooldown_manager.is_ready = Mock(return_value=True)
        diagnostics.cooldown_manager.get_remaining_time = Mock(return_value=0.0)

        result = await diagnostics.diagnose_cooldowns("test_character", monitor=True)

        assert isinstance(result, dict)
        assert "monitoring_data" in result
        assert len(result["monitoring_data"]) > 0
        assert result["monitoring_data"][0]["status"] == "active_monitoring"
        assert result["monitoring_data"][0]["cooldown_ready"] is True
        assert result["monitoring_data"][0]["character_level"] == 10

    @pytest.mark.asyncio
    async def test_diagnose_cooldowns_api_error(self):
        """Test API error propagation following fail-fast principles"""
        mock_api_client = Mock(spec=APIClientWrapper)
        mock_api_client.get_character = AsyncMock(side_effect=Exception("API error"))

        diagnostics = DiagnosticCommands(api_client=mock_api_client)

        # Should propagate exception following fail-fast principles
        with pytest.raises(Exception, match="API error"):
            await diagnostics.diagnose_cooldowns("test_character")

    @pytest.mark.asyncio
    async def test_diagnose_cooldowns_low_hp_warning(self):
        """Test cooldown diagnosis with low HP warning"""
        # Mock character data with low HP
        mock_character_data = Mock()
        mock_character_data.name = "test_character"
        mock_character_data.level = 10
        mock_character_data.hp = 25  # Low HP
        mock_character_data.max_hp = 100
        mock_character_data.x = 5
        mock_character_data.y = 10
        mock_character_data.speed = 5

        # Mock API client
        mock_api_client = Mock(spec=APIClientWrapper)
        mock_api_client.get_character = AsyncMock(return_value=mock_character_data)

        diagnostics = DiagnosticCommands(api_client=mock_api_client)

        # Mock cooldown manager
        diagnostics.cooldown_manager.get_cooldown_info = Mock(return_value=None)
        diagnostics.cooldown_manager.is_ready = Mock(return_value=True)
        diagnostics.cooldown_manager.get_remaining_time = Mock(return_value=0.0)

        result = await diagnostics.diagnose_cooldowns("test_character")

        assert isinstance(result, dict)
        # Should have low HP recommendation
        low_hp_recommendation = any("Low HP detected" in rec for rec in result["recommendations"])
        assert low_hp_recommendation

    @pytest.mark.asyncio
    async def test_diagnose_cooldowns_zero_hp_warning(self):
        """Test cooldown diagnosis with zero HP warning"""
        # Mock character data with zero HP
        mock_character_data = Mock()
        mock_character_data.name = "test_character"
        mock_character_data.level = 10
        mock_character_data.hp = 0  # Zero HP
        mock_character_data.max_hp = 100
        mock_character_data.x = 5
        mock_character_data.y = 10
        mock_character_data.speed = 5

        # Mock API client
        mock_api_client = Mock(spec=APIClientWrapper)
        mock_api_client.get_character = AsyncMock(return_value=mock_character_data)

        diagnostics = DiagnosticCommands(api_client=mock_api_client)

        # Mock cooldown manager
        diagnostics.cooldown_manager.get_cooldown_info = Mock(return_value=None)
        diagnostics.cooldown_manager.is_ready = Mock(return_value=True)
        diagnostics.cooldown_manager.get_remaining_time = Mock(return_value=0.0)

        result = await diagnostics.diagnose_cooldowns("test_character")

        assert isinstance(result, dict)
        # Should have zero HP warning
        zero_hp_warning = any("Character HP is 0" in warning for warning in result["timing_analysis"]["timing_warnings"])
        assert zero_hp_warning

    @pytest.mark.asyncio
    async def test_diagnose_cooldowns_long_cooldown_warning(self):
        """Test cooldown diagnosis with long cooldown warning"""
        # Mock character data
        mock_character_data = Mock()
        mock_character_data.name = "test_character"
        mock_character_data.level = 10
        mock_character_data.hp = 85
        mock_character_data.max_hp = 100
        mock_character_data.x = 5
        mock_character_data.y = 10
        mock_character_data.speed = 5

        # Mock API client
        mock_api_client = Mock(spec=APIClientWrapper)
        mock_api_client.get_character = AsyncMock(return_value=mock_character_data)

        diagnostics = DiagnosticCommands(api_client=mock_api_client)

        # Mock cooldown manager with long remaining time
        diagnostics.cooldown_manager.get_cooldown_info = Mock(return_value=None)
        diagnostics.cooldown_manager.is_ready = Mock(return_value=False)
        diagnostics.cooldown_manager.get_remaining_time = Mock(return_value=40.0)  # Long cooldown

        result = await diagnostics.diagnose_cooldowns("test_character")

        assert isinstance(result, dict)
        # Should have long cooldown warning
        long_cooldown_warning = any("exceeds standard API cooldown" in warning for warning in result["timing_analysis"]["timing_warnings"])
        assert long_cooldown_warning

    @pytest.mark.asyncio
    async def test_diagnose_cooldowns_low_speed_warning(self):
        """Test cooldown diagnosis with low speed warning"""
        # Mock character data with low speed
        mock_character_data = Mock()
        mock_character_data.name = "test_character"
        mock_character_data.level = 10
        mock_character_data.hp = 85
        mock_character_data.max_hp = 100
        mock_character_data.x = 5
        mock_character_data.y = 10
        mock_character_data.speed = 0.5  # Low speed

        # Mock API client
        mock_api_client = Mock(spec=APIClientWrapper)
        mock_api_client.get_character = AsyncMock(return_value=mock_character_data)

        diagnostics = DiagnosticCommands(api_client=mock_api_client)

        # Mock cooldown manager
        diagnostics.cooldown_manager.get_cooldown_info = Mock(return_value=None)
        diagnostics.cooldown_manager.is_ready = Mock(return_value=True)
        diagnostics.cooldown_manager.get_remaining_time = Mock(return_value=0.0)

        result = await diagnostics.diagnose_cooldowns("test_character")

        assert isinstance(result, dict)
        # Should have low speed warning
        low_speed_warning = any("Low character speed" in warning for warning in result["timing_analysis"]["timing_warnings"])
        assert low_speed_warning


class TestDiagnosticIntegration:
    """Integration tests for DiagnosticCommands"""

    def test_full_initialization_flow(self):
        """Test complete initialization with all dependencies"""
        mock_registry = Mock(spec=ActionRegistry)
        mock_goal_manager = AsyncMock(spec=GoalManager)

        diagnostics = DiagnosticCommands(
            action_registry=mock_registry,
            goal_manager=mock_goal_manager
        )

        # Verify all components are properly initialized
        assert diagnostics.state_diagnostics is not None
        assert diagnostics.action_diagnostics is not None
        assert diagnostics.planning_diagnostics is not None
        assert diagnostics.action_registry is mock_registry
        assert diagnostics.goal_manager is mock_goal_manager

    @pytest.mark.asyncio
    async def test_diagnostic_workflow_sequence(self):
        """Test running multiple diagnostics in sequence"""
        mock_registry = Mock(spec=ActionRegistry)
        mock_goal_manager = AsyncMock(spec=GoalManager)

        diagnostics = DiagnosticCommands(
            action_registry=mock_registry,
            goal_manager=mock_goal_manager
        )

        # Run state diagnosis
        state_result = await diagnostics.diagnose_state("test_character")
        assert isinstance(state_result, dict)

        # Run action diagnosis
        with patch.object(diagnostics.action_diagnostics, 'validate_action_registry', return_value=[]):
            with patch.object(diagnostics.action_diagnostics, 'validate_action_costs', return_value=[]):
                action_result = await diagnostics.diagnose_actions("test_character")
        assert isinstance(action_result, dict)

        # Run planning diagnosis
        with patch.object(diagnostics.planning_diagnostics, 'test_goal_reachability') as mock_reachability:
            async def mock_reachability_func():
                return True
            mock_reachability.side_effect = mock_reachability_func
            with patch.object(diagnostics.planning_diagnostics, 'identify_planning_bottlenecks') as mock_bottlenecks:
                async def mock_bottlenecks_func():
                    return []
                mock_bottlenecks.side_effect = mock_bottlenecks_func
                with patch.object(diagnostics.planning_diagnostics, 'measure_planning_performance') as mock_performance:
                    async def mock_performance_func():
                        return {"success": True}
                    mock_performance.side_effect = mock_performance_func
                    plan_result = await diagnostics.diagnose_plan("test_character", "level_up")
        assert isinstance(plan_result, dict)

        # All should have completed successfully
        assert "diagnostic_time" in state_result
        assert "diagnostic_time" in action_result
        assert "diagnostic_time" in plan_result

    def test_error_handling_throughout_diagnostics(self):
        """Test error handling across different diagnostic methods"""
        diagnostics = DiagnosticCommands()

        # State data diagnosis should handle invalid inputs gracefully
        result = diagnostics.diagnose_state_data({})
        assert isinstance(result, dict)

        # Format methods should handle empty inputs gracefully
        state_format = diagnostics.format_state_output({})
        action_format = diagnostics.format_action_output({})
        planning_format = diagnostics.format_planning_output({})

        assert isinstance(state_format, str)
        assert isinstance(action_format, str)
        assert isinstance(planning_format, str)

    @pytest.mark.asyncio
    async def test_performance_with_complex_scenarios(self):
        """Test diagnostic performance with complex scenarios"""
        mock_registry = Mock(spec=ActionRegistry)
        mock_goal_manager = AsyncMock(spec=GoalManager)

        # Create a large number of mock actions to test performance
        large_action_list = []
        for i in range(100):
            mock_action_class = Mock()
            mock_action_instance = Mock()
            mock_action_instance.name = f"action_{i}"
            mock_action_instance.cost = i + 1
            mock_action_class.return_value = mock_action_instance
            mock_action_class.__name__ = f"Action{i}"
            large_action_list.append(mock_action_class)

        mock_registry.get_all_action_types.return_value = large_action_list

        diagnostics = DiagnosticCommands(
            action_registry=mock_registry,
            goal_manager=mock_goal_manager
        )

        # Test action diagnosis with large dataset
        with patch.object(diagnostics.action_diagnostics, 'validate_action_registry', return_value=[]):
            with patch.object(diagnostics.action_diagnostics, 'validate_action_costs', return_value=[]):
                result = await diagnostics.diagnose_actions("test_character")

        assert isinstance(result, dict)
        assert result["summary"]["total_actions"] == 100
        # Should complete reasonably quickly even with large datasets
