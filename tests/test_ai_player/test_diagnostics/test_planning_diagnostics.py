"""
Tests for Planning Diagnostics Module

This module tests the PlanningDiagnostics class which provides diagnostic
functions for GOAP planning process visualization and troubleshooting.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.ai_player.diagnostics.planning_diagnostics import PlanningDiagnostics
from src.ai_player.goal_manager import GoalManager
from src.ai_player.state.character_game_state import CharacterGameState
from src.ai_player.state.game_state import GameState
from src.ai_player.types.goap_models import GOAPAction, GOAPActionPlan


class TestPlanningDiagnostics:
    """Test PlanningDiagnostics class"""

    def setup_method(self):
        """Setup test fixtures"""
        self.mock_goal_manager = Mock(spec=GoalManager)
        self.diagnostics = PlanningDiagnostics(self.mock_goal_manager)

        # Create mock character game state
        self.mock_char_state = Mock(spec=CharacterGameState)
        self.mock_char_state.to_goap_state.return_value = {
            GameState.CHARACTER_LEVEL.value: 10,
            GameState.CHARACTER_XP.value: 1000,
            GameState.COOLDOWN_READY.value: True,
        }
        self.mock_char_state.get.side_effect = lambda key: {
            GameState.CHARACTER_LEVEL: 10,
            GameState.CHARACTER_XP: 1000,
            GameState.COOLDOWN_READY: True,
        }.get(key)

        # Sample goal state
        self.sample_goal_state = {GameState.CHARACTER_LEVEL: 15, GameState.CHARACTER_XP: 2000}

    def test_init(self):
        """Test PlanningDiagnostics initialization"""
        goal_manager = Mock()
        diagnostics = PlanningDiagnostics(goal_manager)

        assert diagnostics.goal_manager is goal_manager

    @pytest.mark.asyncio
    async def test_analyze_planning_steps_successful_plan(self):
        """Test analysis of successful planning steps"""
        # Mock successful plan
        mock_plan = [{"name": "move_to_location", "cost": 2}, {"name": "gather_resource", "cost": 3}]
        self.mock_goal_manager.plan_actions = AsyncMock(return_value=mock_plan)

        result = await self.diagnostics.analyze_planning_steps(self.mock_char_state, self.sample_goal_state)

        assert result["planning_successful"] is True
        assert result["steps"] == mock_plan
        assert result["total_cost"] == 5  # 2 + 3 from the action costs
        assert len(result["state_transitions"]) == 2
        assert isinstance(result["planning_time"], float)
        assert result["issues"] == []

    @pytest.mark.asyncio
    async def test_analyze_planning_steps_no_plan_found(self):
        """Test analysis when no plan is found"""
        self.mock_goal_manager.plan_actions = AsyncMock(return_value=None)

        result = await self.diagnostics.analyze_planning_steps(self.mock_char_state, self.sample_goal_state)

        assert result["planning_successful"] is False
        assert "No plan found - goal may be unreachable" in result["issues"]
        assert result["total_cost"] == 0
        assert result["state_transitions"] == []

    @pytest.mark.asyncio
    async def test_analyze_planning_steps_planning_exception(self):
        """Test that planning exceptions propagate following fail-fast principles"""
        self.mock_goal_manager.plan_actions = AsyncMock(side_effect=Exception("Planning error"))

        with pytest.raises(Exception, match="Planning error"):
            await self.diagnostics.analyze_planning_steps(self.mock_char_state, self.sample_goal_state)

    @pytest.mark.asyncio
    async def test_analyze_planning_steps_analysis_exception(self):
        """Test that analysis exceptions propagate following fail-fast principles"""
        # Make plan_actions raise exception that should propagate
        self.mock_goal_manager.plan_actions = AsyncMock(side_effect=Exception("State error"))
        # Also make to_goap_state fail in the state transition analysis
        self.mock_char_state.to_goap_state.side_effect = Exception("State error")

        with pytest.raises(Exception, match="State error"):
            await self.diagnostics.analyze_planning_steps(self.mock_char_state, self.sample_goal_state)

    @pytest.mark.asyncio
    async def test_test_goal_reachability_with_goal_manager_method(self):
        """Test goal reachability when goal manager has is_goal_achievable method"""
        self.mock_goal_manager.is_goal_achievable = Mock(return_value=True)

        result = await self.diagnostics.test_goal_reachability(self.mock_char_state, self.sample_goal_state)

        assert result is True
        # The implementation converts CharacterGameState to dict via to_goap_state(), then converts to GameState enum dict
        expected_current_state = {
            GameState.CHARACTER_LEVEL: 10,
            GameState.CHARACTER_XP: 1000,
            GameState.COOLDOWN_READY: True,
        }
        self.mock_goal_manager.is_goal_achievable.assert_called_once_with(
            self.sample_goal_state, expected_current_state
        )

    @pytest.mark.asyncio
    async def test_test_goal_reachability_level_cannot_decrease(self):
        """Test that goal reachability fails when trying to decrease character level"""
        # Remove is_goal_achievable method to test heuristic checks
        if hasattr(self.mock_goal_manager, "is_goal_achievable"):
            delattr(self.mock_goal_manager, "is_goal_achievable")

        goal_state = {GameState.CHARACTER_LEVEL: 5}  # Lower than current level of 10

        result = await self.diagnostics.test_goal_reachability(self.mock_char_state, goal_state)

        assert result is False

    @pytest.mark.asyncio
    async def test_test_goal_reachability_xp_cannot_decrease(self):
        """Test that goal reachability fails when trying to decrease XP"""
        # Remove is_goal_achievable method to test heuristic checks
        if hasattr(self.mock_goal_manager, "is_goal_achievable"):
            delattr(self.mock_goal_manager, "is_goal_achievable")

        goal_state = {GameState.CHARACTER_XP: 500}  # Lower than current XP of 1000

        result = await self.diagnostics.test_goal_reachability(self.mock_char_state, goal_state)

        assert result is False

    @pytest.mark.asyncio
    async def test_test_goal_reachability_with_planning_attempt(self):
        """Test goal reachability using planning attempt"""
        # Remove is_goal_achievable method to test planning fallback
        delattr(self.mock_goal_manager, "is_goal_achievable")
        self.mock_goal_manager.plan_actions = AsyncMock(return_value=[{"name": "test_action"}])

        result = await self.diagnostics.test_goal_reachability(self.mock_char_state, self.sample_goal_state)

        assert result is True

    @pytest.mark.asyncio
    async def test_test_goal_reachability_planning_fails(self):
        """Test goal reachability when planning fails"""
        # Remove is_goal_achievable method
        delattr(self.mock_goal_manager, "is_goal_achievable")
        self.mock_goal_manager.plan_actions = AsyncMock(return_value=None)

        result = await self.diagnostics.test_goal_reachability(self.mock_char_state, self.sample_goal_state)

        assert result is False

    @pytest.mark.asyncio
    async def test_test_goal_reachability_exception_propagates(self):
        """Test that exceptions in reachability testing propagate following fail-fast principles"""
        # Remove is_goal_achievable method
        delattr(self.mock_goal_manager, "is_goal_achievable")
        self.mock_goal_manager.plan_actions = AsyncMock(side_effect=Exception("Planning error"))

        with pytest.raises(Exception, match="Planning error"):
            await self.diagnostics.test_goal_reachability(self.mock_char_state, self.sample_goal_state)

    def test_visualize_plan_empty_plan(self):
        """Test visualization of empty plan"""
        result = self.diagnostics.visualize_plan([])

        assert result == "No plan to visualize"

    def test_visualize_plan_with_actions(self):
        """Test visualization of plan with actions"""
        plan = [
            {"name": "move_to_location", "cost": 2, "preconditions": {"at_bank": True}, "effects": {"at_mine": True}},
            {"name": "gather_resource", "cost": 3},
        ]

        result = self.diagnostics.visualize_plan(plan)

        assert "=== ACTION PLAN VISUALIZATION ===" in result
        assert "Total actions: 2" in result
        assert "[1] move_to_location (cost: 2)" in result
        assert "[2] gather_resource (cost: 3)" in result
        assert "Requires: {'at_bank': True}" in result
        assert "Results: {'at_mine': True}" in result
        assert "GOAL ACHIEVED" in result

    def test_estimate_state_after_action_with_effects(self):
        """Test state estimation after action with effects"""
        current_state = {GameState.CHARACTER_LEVEL: 10, GameState.CHARACTER_XP: 1000}
        action = {"effects": {GameState.CHARACTER_LEVEL: 11, GameState.CHARACTER_XP: 1100}}

        result = self.diagnostics._estimate_state_after_action(current_state, action)

        assert result[GameState.CHARACTER_LEVEL] == 11
        assert result[GameState.CHARACTER_XP] == 1100

    def test_estimate_state_after_action_string_keys(self):
        """Test state estimation with string keys in effects"""
        current_state = {GameState.CHARACTER_LEVEL: 10}
        action = {
            "effects": {
                "character_level": 11,  # String key
                "invalid_key": 999,  # Invalid key
            }
        }

        result = self.diagnostics._estimate_state_after_action(current_state, action)

        # Should handle string conversion and skip invalid keys
        assert GameState.CHARACTER_LEVEL in result

    def test_analyze_plan_efficiency_empty_plan(self):
        """Test efficiency analysis of empty plan"""
        empty_plan = GOAPActionPlan(actions=[], total_cost=0, estimated_duration=0.0, plan_id="empty")
        result = self.diagnostics.analyze_plan_efficiency(empty_plan)

        assert result["total_actions"] == 0
        assert result["total_cost"] == 0
        assert result["efficiency_score"] == 0.0
        assert result["redundant_actions"] == []
        assert result["optimization_suggestions"] == []
        assert result["action_types"] == {}

    def test_analyze_plan_efficiency_with_actions(self):
        """Test efficiency analysis with actions"""
        actions = [
            GOAPAction(name="move_to_location", action_type="movement", cost=2),
            GOAPAction(name="gather_copper", action_type="gathering", cost=3),
            GOAPAction(name="gather_copper", action_type="gathering", cost=3),  # Duplicate
            GOAPAction(name="craft_item", action_type="crafting", cost=1),
        ]
        plan = GOAPActionPlan(actions=actions, total_cost=9, estimated_duration=4.0, plan_id="test")

        result = self.diagnostics.analyze_plan_efficiency(plan)

        assert result["total_actions"] == 4
        assert result["total_cost"] == 9
        assert result["efficiency_score"] > 0
        assert len(result["redundant_actions"]) == 1
        assert "gather_copper" in result["redundant_actions"][0]
        assert result["action_types"]["move"] == 1
        assert result["action_types"]["gather"] == 2
        assert result["action_types"]["craft"] == 1

    def test_analyze_plan_efficiency_optimization_suggestions(self):
        """Test efficiency analysis optimization suggestions"""
        # Long plan
        long_actions = [GOAPAction(name=f"action_{i}", action_type="test", cost=1) for i in range(15)]
        long_plan = GOAPActionPlan(actions=long_actions, total_cost=15, estimated_duration=15.0, plan_id="long")
        result = self.diagnostics.analyze_plan_efficiency(long_plan)
        assert any("quite long" in suggestion for suggestion in result["optimization_suggestions"])

        # Single action type plan
        single_actions = [GOAPAction(name="move_action", action_type="move", cost=1) for _ in range(3)]
        single_type_plan = GOAPActionPlan(
            actions=single_actions, total_cost=3, estimated_duration=3.0, plan_id="single"
        )
        result = self.diagnostics.analyze_plan_efficiency(single_type_plan)
        assert any("only one action type" in suggestion for suggestion in result["optimization_suggestions"])

    def test_simulate_plan_execution_success(self):
        """Test successful plan execution simulation"""
        plan = [
            {
                "name": "test_action",
                "preconditions": {GameState.CHARACTER_LEVEL: 10},
                "effects": {GameState.CHARACTER_XP: 1100},
            }
        ]
        start_state = {GameState.CHARACTER_LEVEL: 10, GameState.CHARACTER_XP: 1000}

        result = self.diagnostics.simulate_plan_execution(plan, start_state)

        assert result["success"] is True
        assert result["final_state"][GameState.CHARACTER_XP] == 1100
        assert len(result["execution_steps"]) == 1
        assert result["execution_steps"][0]["executed"] is True

    def test_simulate_plan_execution_preconditions_not_met(self):
        """Test simulation when preconditions are not met"""
        plan = [
            {
                "name": "test_action",
                "preconditions": {GameState.CHARACTER_LEVEL: 15},  # Higher than current
                "effects": {GameState.CHARACTER_XP: 1100},
            }
        ]
        start_state = {GameState.CHARACTER_LEVEL: 10, GameState.CHARACTER_XP: 1000}

        result = self.diagnostics.simulate_plan_execution(plan, start_state)

        assert result["success"] is False
        assert result["execution_steps"][0]["executed"] is False
        assert len(result["execution_steps"][0]["issues"]) > 0

    def test_simulate_plan_execution_string_keys(self):
        """Test simulation with string keys in preconditions/effects"""
        plan = [
            {
                "name": "test_action",
                "preconditions": {"character_level": 10},  # String key
                "effects": {"character_xp": 1100},  # String key
            }
        ]
        start_state = {GameState.CHARACTER_LEVEL: 10, GameState.CHARACTER_XP: 1000}

        result = self.diagnostics.simulate_plan_execution(plan, start_state)

        assert result["success"] is True
        assert result["execution_steps"][0]["executed"] is True

    def test_simulate_plan_execution_invalid_keys(self):
        """Test simulation with invalid keys propagates exception following fail-fast principles"""
        plan = [{"name": "test_action", "preconditions": {"invalid_key": 10}, "effects": {"another_invalid_key": 1100}}]
        start_state = {GameState.CHARACTER_LEVEL: 10}

        # Should propagate ValueError for invalid GameState enum value
        with pytest.raises(ValueError, match="'invalid_key' is not a valid GameState"):
            self.diagnostics.simulate_plan_execution(plan, start_state)

    @pytest.mark.asyncio
    async def test_identify_planning_bottlenecks_unreachable_goal(self):
        """Test identification of unreachable goal bottleneck"""
        # Mock unreachable goal
        with patch.object(self.diagnostics, "test_goal_reachability", return_value=False):
            bottlenecks = await self.diagnostics.identify_planning_bottlenecks(
                self.mock_char_state, self.sample_goal_state
            )

        assert any("unreachable" in bottleneck for bottleneck in bottlenecks)

    @pytest.mark.asyncio
    async def test_identify_planning_bottlenecks_large_state_space(self):
        """Test identification of large state space bottleneck"""
        # Create large goal state with valid GameState enums
        large_goal_state = {
            GameState.CHARACTER_LEVEL: 15,
            GameState.CHARACTER_XP: 2000,
            GameState.MINING_XP: 1000,
            GameState.WOODCUTTING_XP: 1000,
            GameState.FISHING_XP: 1000,
            GameState.WEAPONCRAFTING_XP: 1000,
            GameState.GEARCRAFTING_XP: 1000,
            GameState.JEWELRYCRAFTING_XP: 1000,
            GameState.COOKING_XP: 1000,
            GameState.ALCHEMY_XP: 1000,
            GameState.COOLDOWN_READY: True,
        }
        # Mock large start state too
        self.mock_char_state.to_goap_state.return_value = {f"state_{i}": i for i in range(15)}

        with patch.object(self.diagnostics, "test_goal_reachability", return_value=True):
            bottlenecks = await self.diagnostics.identify_planning_bottlenecks(self.mock_char_state, large_goal_state)

        assert any("Large state space" in bottleneck for bottleneck in bottlenecks)

    @pytest.mark.asyncio
    async def test_identify_planning_bottlenecks_large_gap(self):
        """Test identification of large value gap bottleneck"""
        goal_state = {GameState.CHARACTER_LEVEL: 150}  # Much higher than current 10

        with patch.object(self.diagnostics, "test_goal_reachability", return_value=True):
            bottlenecks = await self.diagnostics.identify_planning_bottlenecks(self.mock_char_state, goal_state)

        assert any("Large gap" in bottleneck for bottleneck in bottlenecks)

    @pytest.mark.asyncio
    async def test_identify_planning_bottlenecks_no_actions(self):
        """Test identification of no actions bottleneck"""
        self.mock_goal_manager.create_goap_actions = AsyncMock(return_value=None)

        with patch.object(self.diagnostics, "test_goal_reachability", return_value=True):
            bottlenecks = await self.diagnostics.identify_planning_bottlenecks(
                self.mock_char_state, self.sample_goal_state
            )

        assert any("No actions available" in bottleneck for bottleneck in bottlenecks)

    @pytest.mark.asyncio
    async def test_identify_planning_bottlenecks_action_access_error(self):
        """Test that action access errors propagate following fail-fast principles"""
        self.mock_goal_manager.create_goap_actions = AsyncMock(side_effect=Exception("Access error"))

        with pytest.raises(Exception, match="Access error"):
            await self.diagnostics.identify_planning_bottlenecks(self.mock_char_state, self.sample_goal_state)

    @pytest.mark.asyncio
    async def test_identify_planning_bottlenecks_missing_required_keys(self):
        """Test identification of missing required state keys"""
        # Remove required keys from state
        self.mock_char_state.to_goap_state.return_value = {
            GameState.CHARACTER_XP.value: 1000
            # Missing CHARACTER_LEVEL and COOLDOWN_READY
        }

        with patch.object(self.diagnostics, "test_goal_reachability", return_value=True):
            bottlenecks = await self.diagnostics.identify_planning_bottlenecks(
                self.mock_char_state, self.sample_goal_state
            )

        assert any("Missing required state keys" in bottleneck for bottleneck in bottlenecks)

    @pytest.mark.asyncio
    async def test_identify_planning_bottlenecks_exception_handling(self):
        """Test that bottleneck identification exceptions propagate following fail-fast principles"""
        self.mock_char_state.to_goap_state.side_effect = Exception("State error")

        with pytest.raises(Exception, match="State error"):
            await self.diagnostics.identify_planning_bottlenecks(self.mock_char_state, self.sample_goal_state)

    @pytest.mark.asyncio
    async def test_measure_planning_performance_success(self):
        """Test successful planning performance measurement"""
        mock_plan = [{"name": "test_action"}]
        self.mock_goal_manager.plan_actions = AsyncMock(return_value=mock_plan)

        metrics = await self.diagnostics.measure_planning_performance(self.mock_char_state, self.sample_goal_state)

        assert metrics["success"] is True
        assert metrics["plan_length"] == 1
        assert isinstance(metrics["planning_time_seconds"], float)
        assert "performance_class" in metrics
        assert "memory_usage_estimate" in metrics

    @pytest.mark.asyncio
    async def test_measure_planning_performance_no_plan(self):
        """Test performance measurement when no plan is found"""
        self.mock_goal_manager.plan_actions = AsyncMock(return_value=None)

        metrics = await self.diagnostics.measure_planning_performance(self.mock_char_state, self.sample_goal_state)

        assert metrics["success"] is False
        assert metrics["plan_length"] == 0
        assert isinstance(metrics["planning_time_seconds"], float)

    @pytest.mark.asyncio
    async def test_measure_planning_performance_exception(self):
        """Test that performance measurement exceptions propagate following fail-fast principles"""
        self.mock_goal_manager.plan_actions = AsyncMock(side_effect=Exception("Planning error"))

        with pytest.raises(Exception, match="Planning error"):
            await self.diagnostics.measure_planning_performance(self.mock_char_state, self.sample_goal_state)

    @pytest.mark.asyncio
    async def test_measure_planning_performance_classes(self):
        """Test performance classification"""
        # Mock fast planning
        with patch("src.ai_player.diagnostics.planning_diagnostics.datetime") as mock_datetime:
            start_time = datetime.now()
            end_time = start_time + timedelta(microseconds=50000)  # 0.05 seconds
            mock_datetime.now.side_effect = [start_time, end_time]

            self.mock_goal_manager.plan_actions = AsyncMock(return_value=[{"name": "test"}])

            metrics = await self.diagnostics.measure_planning_performance(self.mock_char_state, self.sample_goal_state)

            assert metrics["performance_class"] == "fast"

    def test_validate_plan_feasibility_empty_plan(self):
        """Test validation of empty plan"""
        issues = self.diagnostics.validate_plan_feasibility([], {})

        assert "Plan is empty" in issues[0]

    def test_validate_plan_feasibility_valid_plan(self):
        """Test validation of valid plan"""
        plan = [
            {
                "name": "test_action",
                "preconditions": {GameState.CHARACTER_LEVEL: 10},
                "effects": {GameState.CHARACTER_XP: 1100},
            }
        ]
        start_state = {GameState.CHARACTER_LEVEL: 10, GameState.CHARACTER_XP: 1000}

        with patch.object(self.diagnostics, "simulate_plan_execution") as mock_simulate:
            mock_simulate.return_value = {"success": True, "issues": []}

            issues = self.diagnostics.validate_plan_feasibility(plan, start_state)

            # Should have no significant issues for valid plan
            assert len(issues) == 0 or all("same value" not in issue for issue in issues)

    def test_validate_plan_feasibility_simulation_failure(self):
        """Test validation when simulation fails"""
        plan = [{"name": "test_action"}]
        start_state = {GameState.CHARACTER_LEVEL: 10}

        with patch.object(self.diagnostics, "simulate_plan_execution") as mock_simulate:
            mock_simulate.return_value = {"success": False, "issues": ["Precondition not met"]}

            issues = self.diagnostics.validate_plan_feasibility(plan, start_state)

            assert any("Plan simulation failed" in issue for issue in issues)
            assert any("Precondition not met" in issue for issue in issues)

    def test_validate_plan_feasibility_missing_action_name(self):
        """Test validation of plan with missing action names"""
        plan = [{"cost": 1}]  # Missing name
        start_state = {GameState.CHARACTER_LEVEL: 10}

        with patch.object(self.diagnostics, "simulate_plan_execution") as mock_simulate:
            mock_simulate.return_value = {"success": True, "issues": []}

            issues = self.diagnostics.validate_plan_feasibility(plan, start_state)

            assert any("missing name" in issue for issue in issues)

    def test_validate_plan_feasibility_invalid_effect_keys(self):
        """Test validation with invalid effect keys"""
        plan = [{"name": "test_action", "effects": {"invalid_key": 100}}]
        start_state = {GameState.CHARACTER_LEVEL: 10}

        with patch.object(self.diagnostics, "simulate_plan_execution") as mock_simulate:
            mock_simulate.return_value = {"success": True, "issues": []}

            issues = self.diagnostics.validate_plan_feasibility(plan, start_state)

            assert any("invalid effect key" in issue for issue in issues)

    def test_validate_plan_feasibility_logical_inconsistency(self):
        """Test validation detecting logical inconsistencies"""
        plan = [
            {
                "name": "test_action",
                "preconditions": {GameState.CHARACTER_LEVEL: 10},
                "effects": {GameState.CHARACTER_LEVEL: 10},  # Same as precondition
            }
        ]
        start_state = {GameState.CHARACTER_LEVEL: 10}

        with patch.object(self.diagnostics, "simulate_plan_execution") as mock_simulate:
            mock_simulate.return_value = {"success": True, "issues": []}

            issues = self.diagnostics.validate_plan_feasibility(plan, start_state)

            assert any("same value as precondition" in issue for issue in issues)
