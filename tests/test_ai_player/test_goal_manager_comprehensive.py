"""
Comprehensive tests for GoalManager to achieve 95% coverage.

This test module provides extensive coverage for the goal management system,
including goal selection, GOAP planning, action generation, and state management.
All tests use Pydantic models throughout as required by the architecture.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.ai_player.actions import ActionRegistry, BaseAction
from src.ai_player.goal_manager import GoalManager
from src.ai_player.state.character_game_state import CharacterGameState
from src.ai_player.state.game_state import GameState
from src.ai_player.types.goap_models import GOAPActionPlan, GOAPTargetState
from src.game_data.cache_manager import CacheManager
from src.game_data.cooldown_manager import CooldownManager
from src.lib.goap import Action_List, Planner


class TestGoalManagerInitialization:
    """Test GoalManager initialization and basic setup."""

    def test_goal_manager_init_minimal(self):
        """Test basic GoalManager initialization."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)

        goal_manager = GoalManager(action_registry, cooldown_manager)

        assert goal_manager.action_registry == action_registry
        assert goal_manager.cooldown_manager == cooldown_manager
        assert goal_manager.cache_manager is None
        assert goal_manager.planner is None

    def test_goal_manager_init_with_cache_manager(self):
        """Test GoalManager initialization with cache manager."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        cache_manager = Mock(spec=CacheManager)

        goal_manager = GoalManager(action_registry, cooldown_manager, cache_manager)

        assert goal_manager.cache_manager == cache_manager


class TestGameDataRetrieval:
    """Test game data retrieval functionality."""

    @pytest.mark.asyncio
    async def test_get_game_data_no_cache_manager(self):
        """Test game data retrieval without cache manager."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)

        goal_manager = GoalManager(action_registry, cooldown_manager)

        result = await goal_manager.get_game_data()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_game_data_with_cache_manager(self):
        """Test successful game data retrieval."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        cache_manager = AsyncMock(spec=CacheManager)

        # Mock cache manager responses with all required fields
        mock_maps = [{
            "name": "spawn",
            "skin": "forest",
            "x": 0,
            "y": 0,
            "content": None
        }]
        mock_monsters = [{
            "code": "chicken",
            "name": "Chicken",
            "level": 1,
            "hp": 50,
            "attack_fire": 0,
            "attack_earth": 5,
            "attack_water": 0,
            "attack_air": 0,
            "res_fire": 0,
            "res_earth": 0,
            "res_water": 0,
            "res_air": 0,
            "min_gold": 1,
            "max_gold": 3
        }]
        mock_resources = [{
            "code": "ash_tree",
            "name": "Ash Tree",
            "skill": "woodcutting",
            "level": 1
        }]
        mock_npcs = [{
            "code": "weapons_master",
            "name": "Weapons Master",
            "description": "Master of weapons",
            "type": "trader"
        }]
        mock_items = [{
            "code": "copper_dagger",
            "name": "Copper Dagger",
            "level": 1,
            "type": "weapon",
            "subtype": "dagger",
            "description": "A basic copper dagger"
        }]

        cache_manager.get_all_maps.return_value = mock_maps
        cache_manager.get_all_monsters.return_value = mock_monsters
        cache_manager.get_all_resources.return_value = mock_resources
        cache_manager.get_all_npcs.return_value = mock_npcs
        cache_manager.get_all_items.return_value = mock_items

        goal_manager = GoalManager(action_registry, cooldown_manager, cache_manager)

        result = await goal_manager.get_game_data()

        assert result is not None
        assert len(result.maps) == 1
        assert result.maps[0].name == "spawn"
        assert result.maps[0].x == 0
        assert result.maps[0].y == 0

        assert len(result.monsters) == 1
        assert result.monsters[0].code == "chicken"
        assert result.monsters[0].name == "Chicken"
        assert result.monsters[0].level == 1

        assert len(result.resources) == 1
        assert result.resources[0].code == "ash_tree"
        assert result.resources[0].name == "Ash Tree"

        assert len(result.npcs) == 1
        assert result.npcs[0].code == "weapons_master"
        assert result.npcs[0].name == "Weapons Master"

        assert len(result.items) == 1
        assert result.items[0].code == "copper_dagger"
        assert result.items[0].name == "Copper Dagger"

    @pytest.mark.asyncio
    async def test_get_game_data_with_exception(self):
        """Test game data retrieval with cache manager exception."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        cache_manager = AsyncMock(spec=CacheManager)

        cache_manager.get_all_maps.side_effect = Exception("Cache error")

        goal_manager = GoalManager(action_registry, cooldown_manager, cache_manager)

        # Should propagate exception following fail-fast principles
        with pytest.raises(Exception, match="Cache error"):
            await goal_manager.get_game_data()


class TestMovementTargetSelection:
    """Test movement target selection functionality."""

    @pytest.mark.asyncio
    async def test_select_movement_target_basic(self):
        """Test basic movement target selection."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        # Create mock character state
        current_state = Mock(spec=CharacterGameState)
        current_state.x = 0
        current_state.y = 0
        current_state.level = 5
        current_state.hp = 100
        current_state.max_hp = 100

        # Should raise AttributeError when no cache manager following fail-fast principles
        with pytest.raises(AttributeError):
            await goal_manager.select_movement_target(current_state, "combat")

    @pytest.mark.asyncio
    async def test_find_nearest_safe_location(self):
        """Test finding nearest safe location."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        # Should raise AttributeError when no cache manager following fail-fast principles
        with pytest.raises(AttributeError):
            await goal_manager.find_nearest_safe_location(0, 0)


class TestGoalSelection:
    """Test goal selection functionality."""

    @pytest.mark.asyncio
    async def test_select_next_goal_early_game(self):
        """Test goal selection for early game character."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        # Create early game character state
        current_state = Mock(spec=CharacterGameState)
        current_state.level = 1
        current_state.hp = 90
        current_state.max_hp = 100
        current_state.gold = 0
        current_state.x = 0
        current_state.y = 0
        current_state.at_monster_location = False
        current_state.mining_level = 1
        current_state.woodcutting_level = 1
        current_state.fishing_level = 1

        # Mock the to_goap_state method
        current_state.to_goap_state.return_value = {
            GameState.CHARACTER_LEVEL.value: 1,
            GameState.HP_CURRENT.value: 90,
            GameState.HP_MAX.value: 100,
            GameState.CHARACTER_GOLD.value: 0
        }

        # Mock goal weight calculator to return a gathering goal for early game
        mock_goal = Mock()
        mock_goal.get_target_state.return_value = GOAPTargetState(
            target_states={GameState.GAINED_XP: True, GameState.CHARACTER_LEVEL: 2},
            priority=6
        )
        goal_manager.goal_weight_calculator.select_optimal_goal = Mock(return_value=(mock_goal, []))
        type(mock_goal).__name__ = 'GatheringGoal'

        result = await goal_manager.select_next_goal(current_state)

        assert isinstance(result, GOAPTargetState)
        assert bool(result)  # GOAPTargetState.__bool__ checks if target_states is not empty

    def test_max_level_achieved_false(self):
        """Test max level check for low level character."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        current_state = Mock(spec=CharacterGameState)
        current_state.level = 5

        result = goal_manager.max_level_achieved(current_state)

        assert result is False

    def test_max_level_achieved_true(self):
        """Test max level check for max level character."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        current_state = Mock(spec=CharacterGameState)
        current_state.level = 45  # Max level

        result = goal_manager.max_level_achieved(current_state)

        assert result is True


class TestGoalGeneration:
    """Test goal generation for different game phases."""

    def test_get_early_game_goals(self):
        """Test early game goal generation."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        current_state = {
            GameState.CHARACTER_LEVEL: 2,
            GameState.HP_CURRENT: 100,
            GameState.CHARACTER_GOLD: 50
        }

        result = goal_manager.get_early_game_goals(current_state)

        assert isinstance(result, list)
        assert len(result) > 0
        for goal in result:
            assert isinstance(goal, dict)

    def test_get_mid_game_goals(self):
        """Test mid game goal generation."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        current_state = {
            GameState.CHARACTER_LEVEL: 15,
            GameState.HP_CURRENT: 150,
            GameState.CHARACTER_GOLD: 1000
        }

        result = goal_manager.get_mid_game_goals(current_state)

        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_late_game_goals(self):
        """Test late game goal generation."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        current_state = {
            GameState.CHARACTER_LEVEL: 35,
            GameState.HP_CURRENT: 300,
            GameState.CHARACTER_GOLD: 10000
        }

        result = goal_manager.get_late_game_goals(current_state)

        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_survival_goals(self):
        """Test survival goal generation."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        current_state = {
            GameState.CHARACTER_LEVEL: 10,
            GameState.HP_CURRENT: 20,  # Low HP
            GameState.HP_MAX: 100
        }

        result = goal_manager.get_survival_goals(current_state)

        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_progression_goals(self):
        """Test progression goal generation."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        current_state = {
            GameState.CHARACTER_LEVEL: 10,
            GameState.HP_CURRENT: 100,
            GameState.MINING_LEVEL: 5
        }

        result = goal_manager.get_progression_goals(current_state)

        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_economic_goals(self):
        """Test economic goal generation."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        current_state = {
            GameState.CHARACTER_LEVEL: 10,
            GameState.CHARACTER_GOLD: 100,
            GameState.HP_CURRENT: 100
        }

        result = goal_manager.get_economic_goals(current_state)

        assert isinstance(result, list)
        assert len(result) > 0


class TestGoalPrioritization:
    """Test goal prioritization functionality."""

    def test_prioritize_goals_basic(self):
        """Test basic goal prioritization."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        available_goals = [
            {GameState.CHARACTER_LEVEL: 2},
            {GameState.HP_CURRENT: 100},
            {GameState.CHARACTER_GOLD: 500}
        ]

        current_state = {
            GameState.CHARACTER_LEVEL: 1,
            GameState.HP_CURRENT: 50,
            GameState.CHARACTER_GOLD: 0
        }

        result = goal_manager.prioritize_goals(available_goals, current_state)

        assert isinstance(result, dict)
        assert len(result) > 0

    def test_is_goal_achievable_true(self):
        """Test goal achievability check for achievable goal."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        goal = {GameState.CHARACTER_LEVEL: 2}
        current_state = {GameState.CHARACTER_LEVEL: 1}

        result = goal_manager.is_goal_achievable(goal, current_state)

        assert result is True

    def test_is_goal_achievable_false(self):
        """Test goal achievability check for unachievable goal."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        goal = {GameState.CHARACTER_LEVEL: 50}  # Beyond max level
        current_state = {GameState.CHARACTER_LEVEL: 1}

        result = goal_manager.is_goal_achievable(goal, current_state)

        assert result is False

    def test_estimate_goal_cost(self):
        """Test goal cost estimation."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        goal = {GameState.CHARACTER_LEVEL: 5}
        current_state = {GameState.CHARACTER_LEVEL: 1}

        result = goal_manager.estimate_goal_cost(goal, current_state)

        assert isinstance(result, int)
        assert result > 0


class TestActionPlanning:
    """Test action planning functionality."""

    @pytest.mark.asyncio
    async def test_plan_actions_basic(self):
        """Test basic action planning."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        # Mock character state
        current_state = Mock(spec=CharacterGameState)
        current_state.name = "test_char"  # Add missing name attribute
        current_state.to_goap_state.return_value = {
            GameState.CHARACTER_LEVEL.value: 1,
            GameState.HP_CURRENT.value: 100
        }

        goal = GOAPTargetState(
            target_states={GameState.CHARACTER_LEVEL: 2},
            priority=5
        )

        # Mock action registry
        mock_action = Mock(spec=BaseAction)
        mock_action.name = "test_action"
        mock_action.cost = 1
        mock_action.get_preconditions.return_value = {}
        mock_action.get_effects.return_value = {GameState.CHARACTER_LEVEL: 2}

        action_registry.generate_actions_for_state.return_value = [mock_action]

        with patch.object(goal_manager, '_create_goap_planner') as mock_create_planner:
            mock_planner = Mock(spec=Planner)
            mock_planner.calculate.return_value = [{"name": "test_action"}]
            mock_create_planner.return_value = mock_planner

            result = await goal_manager.plan_actions(current_state, goal)

            assert isinstance(result, GOAPActionPlan)

    @pytest.mark.asyncio
    async def test_create_goap_actions(self):
        """Test GOAP action creation."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        current_state = Mock(spec=CharacterGameState)
        current_state.to_goap_state.return_value = {
            GameState.CHARACTER_LEVEL.value: 1
        }

        # Mock actions
        mock_action = Mock(spec=BaseAction)
        mock_action.name = "test_action"
        mock_action.cost = 1
        mock_action.get_preconditions.return_value = {}
        mock_action.get_effects.return_value = {}

        action_registry.generate_actions_for_state.return_value = [mock_action]

        with patch.object(goal_manager, 'get_game_data', return_value=None):
            result = await goal_manager.create_goap_actions(current_state)

            assert isinstance(result, Action_List)

    def test_should_defer_planning_character_ready(self):
        """Test planning deferral when character is ready to act."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        cooldown_manager.is_ready.return_value = True
        goal_manager = GoalManager(action_registry, cooldown_manager)

        result = goal_manager.should_defer_planning("test_char")

        assert result is False  # Should not defer when character is ready

    def test_should_defer_planning_with_cooldown_manager(self):
        """Test planning deferral with cooldown manager."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        cooldown_manager.is_ready.return_value = True
        goal_manager = GoalManager(action_registry, cooldown_manager)

        result = goal_manager.should_defer_planning("test_char")

        assert result is False


class TestStateConversion:
    """Test state conversion utilities."""

    def test_convert_state_for_goap(self):
        """Test state conversion for GOAP compatibility."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        current_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_CURRENT: 100,
            GameState.CHARACTER_GOLD: 500
        }

        result = goal_manager.convert_state_for_goap(current_state)

        assert isinstance(result, dict)
        assert GameState.CHARACTER_LEVEL.value in result
        assert result[GameState.CHARACTER_LEVEL.value] == 5

    def test_convert_action_to_goap(self):
        """Test action conversion for GOAP compatibility."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        mock_action = Mock(spec=BaseAction)
        mock_action.name = "test_action"
        mock_action.cost = 2
        mock_action.get_preconditions.return_value = {GameState.HP_CURRENT: 50}
        mock_action.get_effects.return_value = {GameState.CHARACTER_LEVEL: 2}

        name, preconditions, effects, cost = goal_manager.convert_action_to_goap(mock_action)

        assert name == "test_action"
        assert cost == 2
        assert isinstance(preconditions, dict)
        assert isinstance(effects, dict)


class TestPriorityCalculation:
    """Test priority calculation methods."""

    def test_calculate_survival_priority(self):
        """Test survival priority calculation."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        # Low HP state should have high survival priority
        current_state = {
            GameState.HP_CURRENT: 20,
            GameState.HP_MAX: 100
        }

        result = goal_manager._calculate_survival_priority(current_state)

        assert isinstance(result, int)
        assert result > 0

    def test_calculate_progression_priority(self):
        """Test progression priority calculation."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        current_state = {
            GameState.CHARACTER_LEVEL: 10,
            GameState.MINING_LEVEL: 5,
            GameState.HP_CURRENT: 100
        }

        result = goal_manager._calculate_progression_priority(current_state)

        assert isinstance(result, int)
        assert result >= 0

    def test_calculate_economic_priority(self):
        """Test economic priority calculation."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        # Low gold should increase economic priority
        current_state = {
            GameState.CHARACTER_GOLD: 10,
            GameState.CHARACTER_LEVEL: 10
        }

        result = goal_manager._calculate_economic_priority(current_state)

        assert isinstance(result, int)
        assert result >= 0


class TestPlanValidation:
    """Test plan validation functionality."""

    def test_validate_plan_valid(self):
        """Test plan validation for valid plan."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        plan = [
            {"name": "move_to_location", "cost": 1},
            {"name": "fight_monster", "cost": 3}
        ]

        current_state = {
            GameState.CHARACTER_LEVEL: 1,
            GameState.HP_CURRENT: 100
        }

        result = goal_manager.validate_plan(plan, current_state)

        assert isinstance(result, bool)

    def test_evaluate_goal_feasibility_simple(self):
        """Test simple goal feasibility evaluation."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        current_state = {GameState.CHARACTER_LEVEL: 1}
        goal = {GameState.CHARACTER_LEVEL: 2}

        result = goal_manager.evaluate_goal_feasibility(current_state, goal, simple=True)

        assert isinstance(result, bool)

    def test_evaluate_goal_feasibility_detailed(self):
        """Test detailed goal feasibility evaluation."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        current_state = {GameState.CHARACTER_LEVEL: 1}
        goal = {GameState.CHARACTER_LEVEL: 2}

        result = goal_manager.evaluate_goal_feasibility(current_state, goal, simple=False)

        assert isinstance(result, (bool, dict))


class TestUtilityMethods:
    """Test utility and helper methods."""

    def test_get_available_goals_no_filters(self):
        """Test getting available goals without filters."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        current_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_CURRENT: 100
        }

        result = goal_manager.get_available_goals(current_state)

        assert isinstance(result, list)

    def test_get_available_goals_with_filters(self):
        """Test getting available goals with filters."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        current_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_CURRENT: 100
        }

        filters = {"min_level": 3, "max_cost": 10}

        result = goal_manager.get_available_goals(current_state, filters)

        assert isinstance(result, list)

    def test_update_goal_priorities(self):
        """Test goal priority updates."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        current_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_CURRENT: 80
        }

        priorities = {"survival": 5, "progression": 8, "economic": 3}

        result = goal_manager.update_goal_priorities(current_state, priorities)

        assert isinstance(result, dict)
        assert "survival" in result
        assert "progression" in result
        assert "economic" in result

    def test_convert_actions_for_goap(self):
        """Test converting actions for GOAP."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        mock_action = Mock(spec=BaseAction)
        mock_action.name = "test_action"
        mock_action.cost = 1
        mock_action.get_preconditions.return_value = {}
        mock_action.get_effects.return_value = {}

        actions = [mock_action]

        result = goal_manager.convert_actions_for_goap(actions)

        assert isinstance(result, Action_List)


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_goal_manager_with_empty_state(self):
        """Test goal manager with empty state data."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        # Test with empty state dict instead of None
        empty_state = {}
        result = goal_manager.get_early_game_goals(empty_state)

        # Should handle gracefully with default values
        assert isinstance(result, list)

    def test_string_representation(self):
        """Test string representation of GoalManager."""
        action_registry = Mock(spec=ActionRegistry)
        cooldown_manager = Mock(spec=CooldownManager)
        goal_manager = GoalManager(action_registry, cooldown_manager)

        str_repr = str(goal_manager)
        assert isinstance(str_repr, str)
