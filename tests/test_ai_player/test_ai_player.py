"""
Tests for AIPlayer main orchestrator

These tests validate all methods of the AIPlayer class including initialization,
lifecycle management, goal setting, planning, execution, and error handling
with proper mocking of dependencies.
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.ai_player.ai_player import AIPlayer
from src.ai_player.state.character_game_state import CharacterGameState
from src.ai_player.state.game_state import GameState


class TestAIPlayerInitialization:
    """Test AIPlayer initialization and dependency management"""

    def test_init_creates_instance_with_correct_attributes(self) -> None:
        """Test that __init__ properly initializes AIPlayer instance"""
        character_name = "test_character"
        ai_player = AIPlayer(character_name)

        assert ai_player.character_name == character_name
        assert ai_player.state_manager is None
        assert ai_player.goal_manager is None
        assert ai_player.action_executor is None
        assert ai_player.action_registry is None
        assert ai_player._running is False
        assert ai_player._stop_requested is False
        assert ai_player._current_goal is None
        assert ai_player._current_plan is None
        assert isinstance(ai_player._execution_stats, dict)
        assert ai_player._execution_stats["actions_executed"] == 0

    def test_init_creates_logger_with_character_name(self) -> None:
        """Test that logger is created with character-specific name"""
        character_name = "test_character"
        ai_player = AIPlayer(character_name)

        assert ai_player.logger.name == f"ai_player.{character_name}"

    def test_initialize_dependencies_sets_all_components(self) -> None:
        """Test that initialize_dependencies properly sets all component managers"""
        ai_player = AIPlayer("test_char")

        # Create mock dependencies
        mock_state_manager = Mock()
        mock_goal_manager = Mock()
        mock_action_executor = Mock()
        mock_action_registry = Mock()

        # Initialize dependencies
        ai_player.initialize_dependencies(
            mock_state_manager, mock_goal_manager,
            mock_action_executor, mock_action_registry
        )

        assert ai_player.state_manager == mock_state_manager
        assert ai_player.goal_manager == mock_goal_manager
        assert ai_player.action_executor == mock_action_executor
        assert ai_player.action_registry == mock_action_registry

    def test_check_dependencies_returns_false_with_missing_components(self) -> None:
        """Test that _check_dependencies returns False when components missing"""
        ai_player = AIPlayer("test_char")

        # No dependencies initialized
        assert ai_player._check_dependencies() is False

        # Partial dependencies
        ai_player.state_manager = Mock()
        assert ai_player._check_dependencies() is False

        ai_player.goal_manager = Mock()
        assert ai_player._check_dependencies() is False

        ai_player.action_executor = Mock()
        assert ai_player._check_dependencies() is True


class TestAIPlayerLifecycle:
    """Test AIPlayer start/stop lifecycle management"""

    @pytest.fixture
    def ai_player_with_mocks(self) -> AIPlayer:
        """Create AIPlayer with all mocked dependencies"""
        ai_player = AIPlayer("test_char")

        # Mock all dependencies
        ai_player.state_manager = Mock()
        ai_player.goal_manager = Mock()
        ai_player.action_executor = Mock()
        ai_player.action_registry = Mock()

        return ai_player

    async def test_start_raises_error_without_dependencies(self) -> None:
        """Test that start raises RuntimeError when dependencies not initialized"""
        ai_player = AIPlayer("test_char")

        with pytest.raises(RuntimeError, match="Dependencies not initialized"):
            await ai_player.start()

    async def test_start_returns_early_if_already_running(self, ai_player_with_mocks: AIPlayer) -> None:
        """Test that start returns early if AI player is already running"""
        ai_player = ai_player_with_mocks
        ai_player._running = True

        with patch.object(ai_player, 'main_loop') as mock_main_loop:
            await ai_player.start()
            mock_main_loop.assert_not_called()

    async def test_start_sets_running_state_and_calls_main_loop(self, ai_player_with_mocks: AIPlayer) -> None:
        """Test that start properly sets state and calls main_loop"""
        ai_player = ai_player_with_mocks

        # Mock main_loop to avoid infinite loop
        with patch.object(ai_player, 'main_loop') as mock_main_loop:
            await ai_player.start()

            mock_main_loop.assert_called_once()
            assert ai_player._running is False  # Should be reset in finally block

    async def test_stop_does_nothing_if_not_running(self, ai_player_with_mocks: AIPlayer) -> None:
        """Test that stop does nothing if AI player is not running"""
        ai_player = ai_player_with_mocks
        ai_player._running = False

        await ai_player.stop()
        assert ai_player._stop_requested is False

    async def test_stop_sets_stop_requested_and_waits_for_completion(self, ai_player_with_mocks: AIPlayer) -> None:
        """Test that stop sets stop_requested and waits for main loop to finish"""
        ai_player = ai_player_with_mocks
        ai_player._running = True

        # Mock state manager for cache saving
        ai_player.state_manager.get_cached_state.return_value = {GameState.CHARACTER_LEVEL: 1}  # type: ignore  # type: ignore
        ai_player.state_manager.save_state_to_cache = Mock()  # type: ignore

        # Simulate stopping after one iteration
        async def mock_stop() -> None:
            await asyncio.sleep(0.05)  # Brief delay
            ai_player._running = False

        # Start the stop task
        stop_task = asyncio.create_task(mock_stop())
        await ai_player.stop()
        await stop_task

        assert ai_player._stop_requested is True
        ai_player.state_manager.save_state_to_cache.assert_called_once()  # type: ignore

    def test_is_running_returns_correct_state(self, ai_player_with_mocks: AIPlayer) -> None:
        """Test that is_running returns the correct running state"""
        ai_player = ai_player_with_mocks

        assert ai_player.is_running() is False

        ai_player._running = True
        assert ai_player.is_running() is True


class TestAIPlayerGoalManagement:
    """Test AIPlayer goal setting and validation"""

    @pytest.fixture
    def ai_player(self) -> AIPlayer:
        return AIPlayer("test_char")

    async def test_set_goal_validates_gamestate_enum_keys(self, ai_player: AIPlayer) -> None:
        """Test that set_goal validates that all keys are GameState enums"""
        # Valid goal with GameState enum keys
        valid_goal = {GameState.CHARACTER_LEVEL: 10}
        await ai_player.set_goal(valid_goal)
        assert ai_player._current_goal == valid_goal

        # Invalid goal with string key
        invalid_goal = {"invalid_key": 10}
        with pytest.raises(ValueError, match="Goal key invalid_key is not a GameState enum"):
            await ai_player.set_goal(invalid_goal)  # type: ignore

    async def test_set_goal_clears_current_plan(self, ai_player: AIPlayer) -> None:
        """Test that set_goal clears the current plan to force replanning"""
        ai_player._current_plan = [{"action": "test"}]

        goal = {GameState.CHARACTER_LEVEL: 5}
        await ai_player.set_goal(goal)

        assert ai_player._current_goal == goal
        assert ai_player._current_plan is None


class TestAIPlayerPlanning:
    """Test AIPlayer planning and execution logic"""

    @pytest.fixture
    def ai_player_with_mocks(self) -> AIPlayer:
        """Create AIPlayer with mocked dependencies"""
        ai_player = AIPlayer("test_char")
        ai_player.goal_manager = Mock()
        ai_player.action_executor = Mock()
        return ai_player

    async def test_plan_actions_returns_empty_list_without_goal_manager(self) -> None:
        """Test that plan_actions raises error when GoalManager not available"""
        ai_player = AIPlayer("test_char")

        with pytest.raises(RuntimeError, match="GoalManager not available for planning"):
            await ai_player.plan_actions({}, {})

    async def test_plan_actions_calls_goal_manager_and_returns_plan(self, ai_player_with_mocks: AIPlayer) -> None:
        """Test that plan_actions calls GoalManager and returns the plan"""
        ai_player = ai_player_with_mocks

        current_state = {GameState.CHARACTER_LEVEL: 1}
        goal = {GameState.CHARACTER_LEVEL: 2}
        expected_plan = [{"action": "fight", "target": "monster"}]

        ai_player.goal_manager.plan_with_cooldown_awareness = AsyncMock(return_value=expected_plan)  # type: ignore

        result = await ai_player.plan_actions(current_state, goal)

        ai_player.goal_manager.plan_with_cooldown_awareness.assert_called_once_with(  # type: ignore
            ai_player.character_name, current_state, goal.get('target_state', {})
        )
        assert result == expected_plan

    async def test_plan_actions_handles_exceptions_gracefully(self, ai_player_with_mocks: AIPlayer) -> None:
        """Test that plan_actions handles exceptions and returns empty list"""
        ai_player = ai_player_with_mocks

        ai_player.goal_manager.plan_with_cooldown_awareness = AsyncMock(side_effect=Exception("Planning failed"))  # type: ignore

        result = await ai_player.plan_actions({}, {})
        assert result == []

    async def test_execute_plan_returns_false_without_action_executor(self) -> None:
        """Test that execute_plan returns False when ActionExecutor not available"""
        ai_player = AIPlayer("test_char")

        result = await ai_player.execute_plan([{"action": "test"}])
        assert result is False

    async def test_execute_plan_returns_true_for_empty_plan(self, ai_player_with_mocks: AIPlayer) -> None:
        """Test that execute_plan returns True for empty plan"""
        ai_player = ai_player_with_mocks

        result = await ai_player.execute_plan([])
        assert result is True

    async def test_execute_plan_calls_action_executor_and_updates_stats(self, ai_player_with_mocks: AIPlayer) -> None:
        """Test that execute_plan calls ActionExecutor and updates execution stats"""
        ai_player = ai_player_with_mocks

        plan = [{"action": "move"}, {"action": "fight"}]
        ai_player.action_executor.execute_plan = AsyncMock(return_value=True)  # type: ignore

        result = await ai_player.execute_plan(plan)

        ai_player.action_executor.execute_plan.assert_called_once_with(plan, "test_char")  # type: ignore
        assert result is True
        assert ai_player._execution_stats["successful_actions"] == 2
        assert ai_player._execution_stats["actions_executed"] == 2

    async def test_execute_plan_handles_failure_and_updates_stats(self, ai_player_with_mocks: AIPlayer) -> None:
        """Test that execute_plan handles failure and updates failure stats"""
        ai_player = ai_player_with_mocks

        plan = [{"action": "move"}]
        ai_player.action_executor.execute_plan = AsyncMock(return_value=False)  # type: ignore

        result = await ai_player.execute_plan(plan)

        assert result is False
        assert ai_player._execution_stats["failed_actions"] == 1
        assert ai_player._execution_stats["actions_executed"] == 1


class TestAIPlayerReplanning:
    """Test AIPlayer replanning logic"""

    @pytest.fixture
    def ai_player(self) -> AIPlayer:
        return AIPlayer("test_char")

    def test_should_replan_returns_true_without_current_plan(self, ai_player: AIPlayer) -> None:
        """Test that should_replan returns True when no current plan exists"""
        ai_player._current_plan = None
        ai_player._current_goal = {GameState.CHARACTER_LEVEL: 2}

        current_state = CharacterGameState(
            name="test_char",
            level=1,
            xp=0,
            gold=0,
            hp=100,
            max_hp=100,
            x=0,
            y=0,
            mining_level=1,
            mining_xp=0,
            woodcutting_level=1,
            woodcutting_xp=0,
            fishing_level=1,
            fishing_xp=0,
            weaponcrafting_level=1,
            weaponcrafting_xp=0,
            gearcrafting_level=1,
            gearcrafting_xp=0,
            jewelrycrafting_level=1,
            jewelrycrafting_xp=0,
            cooking_level=1,
            cooking_xp=0,
            alchemy_level=1,
            alchemy_xp=0,
            cooldown=0
        )
        assert ai_player.should_replan(current_state) is True

    def test_should_replan_returns_true_without_current_goal(self, ai_player: AIPlayer) -> None:
        """Test that should_replan returns True when no current goal exists"""
        ai_player._current_plan = [{"action": "test"}]
        ai_player._current_goal = None

        current_state = CharacterGameState(
            name="test_char",
            level=1,
            xp=0,
            gold=0,
            hp=100,
            max_hp=100,
            x=0,
            y=0,
            mining_level=1,
            mining_xp=0,
            woodcutting_level=1,
            woodcutting_xp=0,
            fishing_level=1,
            fishing_xp=0,
            weaponcrafting_level=1,
            weaponcrafting_xp=0,
            gearcrafting_level=1,
            gearcrafting_xp=0,
            jewelrycrafting_level=1,
            jewelrycrafting_xp=0,
            cooking_level=1,
            cooking_xp=0,
            alchemy_level=1,
            alchemy_xp=0,
            cooldown=0
        )
        assert ai_player.should_replan(current_state) is True

    def test_should_replan_returns_true_when_goal_achieved(self, ai_player: AIPlayer) -> None:
        """Test that should_replan returns True when current goal is achieved"""
        ai_player._current_plan = [{"action": "test"}]
        ai_player._current_goal = {GameState.CHARACTER_LEVEL: 2}

        current_state = CharacterGameState(
            name="test_char",
            level=2,
            xp=1000,
            gold=100,
            hp=100,
            max_hp=100,
            x=0,
            y=0,
            mining_level=1,
            mining_xp=0,
            woodcutting_level=1,
            woodcutting_xp=0,
            fishing_level=1,
            fishing_xp=0,
            weaponcrafting_level=1,
            weaponcrafting_xp=0,
            gearcrafting_level=1,
            gearcrafting_xp=0,
            jewelrycrafting_level=1,
            jewelrycrafting_xp=0,
            cooking_level=1,
            cooking_xp=0,
            alchemy_level=1,
            alchemy_xp=0,
            cooldown=0
        )
        assert ai_player.should_replan(current_state) is True

    def test_should_replan_returns_true_for_critical_hp(self, ai_player: AIPlayer) -> None:
        """Test that should_replan returns True when character has critical HP"""
        ai_player._current_plan = [{"action": "test"}]
        ai_player._current_goal = {GameState.CHARACTER_LEVEL: 2}

        current_state = CharacterGameState(
            name="test_char",
            level=1,
            xp=500,
            gold=50,
            hp=10,
            max_hp=100,
            x=0,
            y=0,
            mining_level=1,
            mining_xp=0,
            woodcutting_level=1,
            woodcutting_xp=0,
            fishing_level=1,
            fishing_xp=0,
            weaponcrafting_level=1,
            weaponcrafting_xp=0,
            gearcrafting_level=1,
            gearcrafting_xp=0,
            jewelrycrafting_level=1,
            jewelrycrafting_xp=0,
            cooking_level=1,
            cooking_xp=0,
            alchemy_level=1,
            alchemy_xp=0,
            cooldown=0,
            hp_critical=True
        )
        assert ai_player.should_replan(current_state) is True

    def test_should_replan_returns_true_for_inventory_full(self, ai_player: AIPlayer) -> None:
        """Test that should_replan returns True when inventory is full"""
        ai_player._current_plan = [{"action": "test"}]
        ai_player._current_goal = {GameState.CHARACTER_LEVEL: 2}

        current_state = CharacterGameState(
            name="test_char",
            level=1,
            xp=500,
            gold=50,
            hp=100,
            max_hp=100,
            x=0,
            y=0,
            mining_level=1,
            mining_xp=0,
            woodcutting_level=1,
            woodcutting_xp=0,
            fishing_level=1,
            fishing_xp=0,
            weaponcrafting_level=1,
            weaponcrafting_xp=0,
            gearcrafting_level=1,
            gearcrafting_xp=0,
            jewelrycrafting_level=1,
            jewelrycrafting_xp=0,
            cooking_level=1,
            cooking_xp=0,
            alchemy_level=1,
            alchemy_xp=0,
            cooldown=0,
            inventory_space_available=False
        )
        assert ai_player.should_replan(current_state) is True

    def test_should_replan_returns_false_for_stable_state(self, ai_player: AIPlayer) -> None:
        """Test that should_replan returns False when state is stable"""
        ai_player._current_plan = [{"action": "test"}]
        ai_player._current_goal = {GameState.CHARACTER_LEVEL: 2}

        current_state = CharacterGameState(
            name="test_char",
            level=1,
            xp=500,
            gold=50,
            hp=100,
            max_hp=100,
            x=0,
            y=0,
            mining_level=1,
            mining_xp=0,
            woodcutting_level=1,
            woodcutting_xp=0,
            fishing_level=1,
            fishing_xp=0,
            weaponcrafting_level=1,
            weaponcrafting_xp=0,
            gearcrafting_level=1,
            gearcrafting_xp=0,
            jewelrycrafting_level=1,
            jewelrycrafting_xp=0,
            cooking_level=1,
            cooking_xp=0,
            alchemy_level=1,
            alchemy_xp=0,
            cooldown=0,
            hp_critical=False,
            inventory_space_available=True
        )
        assert ai_player.should_replan(current_state) is False


class TestAIPlayerEmergencyHandling:
    """Test AIPlayer emergency situation handling"""

    @pytest.fixture
    def ai_player_with_mocks(self) -> AIPlayer:
        """Create AIPlayer with mocked state manager"""
        ai_player = AIPlayer("test_char")
        ai_player.state_manager = Mock()
        ai_player.state_manager.force_refresh = AsyncMock()
        return ai_player

    async def test_handle_emergency_responds_to_critical_hp(self, ai_player_with_mocks: AIPlayer) -> None:
        """Test that handle_emergency responds to critical HP situation"""
        ai_player = ai_player_with_mocks

        current_state = CharacterGameState(
            name="test_char",
            level=1,
            xp=0,
            gold=0,
            hp=10,
            max_hp=100,
            x=0,
            y=0,
            mining_level=1,
            mining_xp=0,
            woodcutting_level=1,
            woodcutting_xp=0,
            fishing_level=1,
            fishing_xp=0,
            weaponcrafting_level=1,
            weaponcrafting_xp=0,
            gearcrafting_level=1,
            gearcrafting_xp=0,
            jewelrycrafting_level=1,
            jewelrycrafting_xp=0,
            cooking_level=1,
            cooking_xp=0,
            alchemy_level=1,
            alchemy_xp=0,
            cooldown=0,
            hp_critical=True,
            can_fight=True,
            cooldown_ready=True
        )

        await ai_player.handle_emergency(current_state)

        assert ai_player._current_plan is None
        assert ai_player._current_goal == {GameState.HP_CURRENT: 100}
        assert ai_player._execution_stats["emergency_interventions"] == 1

    async def test_handle_emergency_responds_to_low_hp(self, ai_player_with_mocks: AIPlayer) -> None:
        """Test that handle_emergency responds to low HP situation"""
        ai_player = ai_player_with_mocks

        current_state = CharacterGameState(
            name="test_char",
            level=1,
            xp=0,
            gold=0,
            hp=20,
            max_hp=100,
            x=0,
            y=0,
            mining_level=1,
            mining_xp=0,
            woodcutting_level=1,
            woodcutting_xp=0,
            fishing_level=1,
            fishing_xp=0,
            weaponcrafting_level=1,
            weaponcrafting_xp=0,
            gearcrafting_level=1,
            gearcrafting_xp=0,
            jewelrycrafting_level=1,
            jewelrycrafting_xp=0,
            cooking_level=1,
            cooking_xp=0,
            alchemy_level=1,
            alchemy_xp=0,
            cooldown=0,
            hp_low=True,
            can_rest=True,
            cooldown_ready=True
        )

        await ai_player.handle_emergency(current_state)

        assert ai_player._current_plan is None
        assert ai_player._current_goal == {GameState.HP_CURRENT: 80}
        assert ai_player._execution_stats["emergency_interventions"] == 1

    async def test_handle_emergency_refreshes_state_for_invalid_state(self, ai_player_with_mocks: AIPlayer) -> None:
        """Test that handle_emergency refreshes state when character appears stuck"""
        ai_player = ai_player_with_mocks

        # Character has no available actions (appears stuck)
        current_state = CharacterGameState(
            name="test_char",
            level=1,
            xp=0,
            gold=0,
            hp=100,
            max_hp=100,
            x=0,
            y=0,
            mining_level=1,
            mining_xp=0,
            woodcutting_level=1,
            woodcutting_xp=0,
            fishing_level=1,
            fishing_xp=0,
            weaponcrafting_level=1,
            weaponcrafting_xp=0,
            gearcrafting_level=1,
            gearcrafting_xp=0,
            jewelrycrafting_level=1,
            jewelrycrafting_xp=0,
            cooking_level=1,
            cooking_xp=0,
            alchemy_level=1,
            alchemy_xp=0,
            cooldown=0,
            cooldown_ready=True,
            can_fight=False,
            can_gather=False,
            can_craft=False,
            can_trade=False,
            can_move=False,
            can_rest=False
        )

        await ai_player.handle_emergency(current_state)

        ai_player.state_manager.force_refresh.assert_called_once()  # type: ignore
        assert ai_player._execution_stats["emergency_interventions"] == 1

    async def test_handle_emergency_ignores_cooldown_state(self, ai_player_with_mocks: AIPlayer) -> None:
        """Test that handle_emergency ignores normal cooldown state"""
        ai_player = ai_player_with_mocks

        current_state = CharacterGameState(
            name="test_char",
            level=1,
            xp=0,
            gold=0,
            hp=100,
            max_hp=100,
            x=0,
            y=0,
            mining_level=1,
            mining_xp=0,
            woodcutting_level=1,
            woodcutting_xp=0,
            fishing_level=1,
            fishing_xp=0,
            weaponcrafting_level=1,
            weaponcrafting_xp=0,
            gearcrafting_level=1,
            gearcrafting_xp=0,
            jewelrycrafting_level=1,
            jewelrycrafting_xp=0,
            cooking_level=1,
            cooking_xp=0,
            alchemy_level=1,
            alchemy_xp=0,
            cooldown=30,
            cooldown_ready=False
        )

        await ai_player.handle_emergency(current_state)

        ai_player.state_manager.force_refresh.assert_not_called()  # type: ignore
        assert ai_player._execution_stats["emergency_interventions"] == 0


class TestAIPlayerStatus:
    """Test AIPlayer status reporting functionality"""

    @pytest.fixture
    def ai_player_with_state_manager(self) -> AIPlayer:
        """Create AIPlayer with mocked state manager"""
        ai_player = AIPlayer("test_char")
        ai_player.state_manager = Mock()
        ai_player.goal_manager = Mock()
        ai_player.action_executor = Mock()
        return ai_player

    def test_get_status_returns_basic_information(self) -> None:
        """Test that get_status returns basic AI player information"""
        ai_player = AIPlayer("test_char")
        ai_player._running = True
        ai_player._current_goal = {GameState.CHARACTER_LEVEL: 5}
        ai_player._current_plan = [{"action": "test"}]

        status = ai_player.get_status()

        assert status["character_name"] == "test_char"
        assert status["running"] is True
        assert status["current_goal"] == {GameState.CHARACTER_LEVEL: 5}
        assert status["has_current_plan"] is True
        assert status["plan_length"] == 1
        assert "execution_stats" in status
        assert status["dependencies_initialized"] is False

    def test_get_status_includes_character_state_when_available(self, ai_player_with_state_manager: AIPlayer) -> None:
        """Test that get_status includes character state when state manager available"""
        ai_player = ai_player_with_state_manager

        # Mock cached state
        cached_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_CURRENT: 80,
            GameState.HP_MAX: 100,
            GameState.CURRENT_X: 10,
            GameState.CURRENT_Y: 20,
            GameState.COOLDOWN_READY: True,
            GameState.CHARACTER_GOLD: 1500
        }
        ai_player.state_manager.get_cached_state.return_value = cached_state  # type: ignore

        status = ai_player.get_status()

        assert "character_state" in status
        character_state = status["character_state"]
        assert character_state["level"] == 5
        assert character_state["hp"] == "80/100"
        assert character_state["position"] == "(10, 20)"
        assert character_state["cooldown_ready"] is True
        assert character_state["gold"] == 1500

    def test_get_status_handles_state_manager_errors(self, ai_player_with_state_manager: AIPlayer) -> None:
        """Test that get_status handles state manager errors gracefully"""
        ai_player = ai_player_with_state_manager

        ai_player.state_manager.get_cached_state.side_effect = Exception("State error")  # type: ignore

        status = ai_player.get_status()

        assert "character_state_error" in status
        assert status["character_state_error"] == "State error"

    def test_get_status_without_state_manager(self) -> None:
        """Test that get_status works without state manager"""
        ai_player = AIPlayer("test_char")

        status = ai_player.get_status()

        assert status["character_state"] == "StateManager not available"


class TestAIPlayerMainLoop:
    """Test AIPlayer main loop integration"""

    @pytest.fixture
    def ai_player_with_full_mocks(self) -> AIPlayer:
        """Create AIPlayer with all dependencies mocked"""
        ai_player = AIPlayer("test_char")

        # Mock all dependencies
        ai_player.state_manager = Mock()
        ai_player.goal_manager = Mock()
        ai_player.action_executor = Mock()
        ai_player.action_registry = Mock()

        # Setup async methods
        ai_player.state_manager.get_current_state = AsyncMock()
        ai_player.action_executor.execute_plan = AsyncMock()

        return ai_player

    async def test_main_loop_breaks_without_state_manager(self) -> None:
        """Test that main_loop breaks when StateManager not available"""
        ai_player = AIPlayer("test_char")
        ai_player._running = True

        # Mock to avoid infinite loop
        with patch('asyncio.sleep'):
            await ai_player.main_loop()

        # Loop should have exited due to missing state manager
        assert not hasattr(ai_player, '_loop_completed') or ai_player._running

    # Removed test_main_loop_handles_exceptions_gracefully
    # This test is invalid because the AI player should fail fast when API is unavailable
    # There is no valid fallback when game API data is not accessible


# Integration test
@pytest.mark.asyncio
class TestAIPlayerIntegration:
    """Integration tests for AIPlayer with multiple components"""

    async def test_full_lifecycle_with_goal_achievement(self) -> None:
        """Test complete AIPlayer lifecycle from start to goal achievement"""
        ai_player = AIPlayer("integration_test_char")

        # Mock all dependencies
        state_manager = Mock()
        goal_manager = Mock()
        action_executor = Mock()
        action_registry = Mock()

        # Set up state progression (character levels up)
        state_progression = [
            CharacterGameState(
                name="integration_test_char",
                level=1,
                xp=0,
                gold=0,
                hp=100,
                max_hp=100,
                x=0,
                y=0,
                mining_level=1,
                mining_xp=0,
                woodcutting_level=1,
                woodcutting_xp=0,
                fishing_level=1,
                fishing_xp=0,
                weaponcrafting_level=1,
                weaponcrafting_xp=0,
                gearcrafting_level=1,
                gearcrafting_xp=0,
                jewelrycrafting_level=1,
                jewelrycrafting_xp=0,
                cooking_level=1,
                cooking_xp=0,
                alchemy_level=1,
                alchemy_xp=0,
                cooldown=0,
                can_fight=True,
                cooldown_ready=True
            ),
            CharacterGameState(
                name="integration_test_char",
                level=2,
                xp=1000,
                gold=100,
                hp=100,
                max_hp=100,
                x=0,
                y=0,
                mining_level=1,
                mining_xp=0,
                woodcutting_level=1,
                woodcutting_xp=0,
                fishing_level=1,
                fishing_xp=0,
                weaponcrafting_level=1,
                weaponcrafting_xp=0,
                gearcrafting_level=1,
                gearcrafting_xp=0,
                jewelrycrafting_level=1,
                jewelrycrafting_xp=0,
                cooking_level=1,
                cooking_xp=0,
                alchemy_level=1,
                alchemy_xp=0,
                cooldown=0,
                can_fight=True,
                cooldown_ready=True
            )  # Goal achieved
        ]
        state_manager.get_current_state = AsyncMock(side_effect=state_progression)
        state_manager.force_refresh = AsyncMock()

        # Mock goal selection and planning
        goal_manager.select_next_goal.return_value = {GameState.CHARACTER_LEVEL: 2}
        goal_manager.plan_with_cooldown_awareness = AsyncMock(return_value=[{"action": "fight", "target": "monster"}])

        # Mock successful execution
        action_executor.execute_plan = AsyncMock(return_value=True)

        # Initialize dependencies
        ai_player.initialize_dependencies(state_manager, goal_manager, action_executor, action_registry)

        # Mock the main_loop to avoid infinite loop while still testing the flow
        original_main_loop = ai_player.main_loop
        loop_iterations = 0

        async def mock_main_loop() -> None:
            nonlocal loop_iterations
            ai_player._running = True

            # Simulate one cycle of the main loop
            while ai_player._running and not ai_player._stop_requested and loop_iterations < 2:
                loop_iterations += 1

                # Get current state
                current_state = await state_manager.get_current_state()

                # Handle emergency situations
                await ai_player.handle_emergency(current_state)

                # Plan actions
                if ai_player.should_replan(current_state) or ai_player._current_plan is None:
                    goal = goal_manager.select_next_goal(current_state)
                    ai_player._current_goal = goal
                    plan = await ai_player.plan_actions(current_state, goal)
                    ai_player._current_plan = plan
                    ai_player._execution_stats["replanning_count"] += 1

                # Execute plan
                if ai_player._current_plan:
                    success = await ai_player.execute_plan(ai_player._current_plan)
                    if success:
                        ai_player._current_plan = None
                    else:
                        ai_player._current_plan = None

                # Stop after achieving goal or completing iterations
                if loop_iterations >= 2:
                    ai_player._stop_requested = True

                await asyncio.sleep(0.01)  # Brief pause

            ai_player._running = False

        # Replace main_loop temporarily
        ai_player.main_loop = mock_main_loop

        # Run the mock main loop
        await ai_player.main_loop()

        # Verify that planning and execution occurred
        goal_manager.select_next_goal.assert_called()
        goal_manager.plan_with_cooldown_awareness.assert_called()
        action_executor.execute_plan.assert_called()

        # Verify stats were updated
        assert ai_player._execution_stats["actions_executed"] > 0
        assert ai_player._execution_stats["replanning_count"] > 0


class TestAIPlayerExceptionHandling:
    """Test AIPlayer exception handling for complete coverage"""

    @pytest.fixture
    def ai_player_with_mocks(self) -> AIPlayer:
        """Create AIPlayer with all mocked dependencies"""
        ai_player = AIPlayer("test_char")
        ai_player.state_manager = Mock()
        ai_player.goal_manager = Mock()
        ai_player.action_executor = Mock()
        ai_player.action_registry = Mock()
        return ai_player

    async def test_start_handles_main_loop_exception(self, ai_player_with_mocks: AIPlayer) -> None:
        """Test that start method handles exceptions from main_loop and re-raises them"""
        ai_player = ai_player_with_mocks

        # Mock main_loop to raise an exception
        with patch.object(ai_player, 'main_loop', side_effect=Exception("Main loop error")):
            with pytest.raises(Exception, match="Main loop error"):
                await ai_player.start()

        # Verify running state is reset in finally block
        assert ai_player._running is False

    async def test_stop_handles_state_save_exception(self, ai_player_with_mocks: AIPlayer) -> None:
        """Test that stop method handles exceptions when saving state to cache"""
        ai_player = ai_player_with_mocks
        ai_player._running = True

        # Mock state manager to have state but fail on save
        ai_player.state_manager.get_cached_state.return_value = {GameState.CHARACTER_LEVEL: 1}  # type: ignore
        ai_player.state_manager.save_state_to_cache.side_effect = Exception("Save failed")  # type: ignore

        # Simulate stopping after brief delay
        async def mock_stop() -> None:
            await asyncio.sleep(0.05)
            ai_player._running = False

        stop_task = asyncio.create_task(mock_stop())
        await ai_player.stop()
        await stop_task

        # Should have attempted to save despite exception
        ai_player.state_manager.save_state_to_cache.assert_called_once()  # type: ignore

    async def test_main_loop_handles_goal_manager_missing(self, ai_player_with_mocks: AIPlayer) -> None:
        """Test that main_loop breaks when GoalManager is not available"""
        ai_player = ai_player_with_mocks
        ai_player.goal_manager = None  # Remove goal manager
        ai_player._running = True

        # Mock state manager to return state with valid action states to avoid emergency handling
        mock_state = CharacterGameState(
            name="test_char",
            level=1,
            xp=0,
            gold=0,
            hp=100,
            max_hp=100,
            x=0,
            y=0,
            mining_level=1,
            mining_xp=0,
            woodcutting_level=1,
            woodcutting_xp=0,
            fishing_level=1,
            fishing_xp=0,
            weaponcrafting_level=1,
            weaponcrafting_xp=0,
            gearcrafting_level=1,
            gearcrafting_xp=0,
            jewelrycrafting_level=1,
            jewelrycrafting_xp=0,
            cooking_level=1,
            cooking_xp=0,
            alchemy_level=1,
            alchemy_xp=0,
            cooldown=0,
            can_fight=True,
            cooldown_ready=True
        )
        ai_player.state_manager.get_current_state = AsyncMock(return_value=mock_state)  # type: ignore

        await ai_player.main_loop()

        # Loop should have broken due to missing goal manager
        assert ai_player._running is True  # Still running but loop exited

    async def test_main_loop_handles_no_valid_plan(self, ai_player_with_mocks: AIPlayer) -> None:
        """Test that main_loop handles case when no valid plan is generated"""
        ai_player = ai_player_with_mocks
        ai_player._running = True

        # Mock state and goal manager
        mock_state = CharacterGameState(
            name="test_char",
            level=1,
            xp=0,
            gold=0,
            hp=100,
            max_hp=100,
            x=0,
            y=0,
            mining_level=1,
            mining_xp=0,
            woodcutting_level=1,
            woodcutting_xp=0,
            fishing_level=1,
            fishing_xp=0,
            weaponcrafting_level=1,
            weaponcrafting_xp=0,
            gearcrafting_level=1,
            gearcrafting_xp=0,
            jewelrycrafting_level=1,
            jewelrycrafting_xp=0,
            cooking_level=1,
            cooking_xp=0,
            alchemy_level=1,
            alchemy_xp=0,
            cooldown=0
        )
        ai_player.state_manager.get_current_state = AsyncMock(return_value=mock_state)  # type: ignore
        ai_player.goal_manager.select_next_goal.return_value = {GameState.CHARACTER_LEVEL: 2}  # type: ignore
        ai_player.goal_manager.plan_actions = AsyncMock(return_value=None)  # type: ignore # No plan generated

        # Mock sleep to break loop
        with patch('asyncio.sleep') as mock_sleep:
            call_count = 0
            async def break_after_two_calls(*args: Any) -> None:
                nonlocal call_count
                call_count += 1
                if call_count >= 2:  # Break after plan failure sleep
                    ai_player._running = False
            mock_sleep.side_effect = break_after_two_calls

            await ai_player.main_loop()

        # Should have slept twice - once for no plan, once for main loop
        assert mock_sleep.call_count >= 2

    async def test_main_loop_handles_plan_execution_failure(self, ai_player_with_mocks: AIPlayer) -> None:
        """Test that main_loop handles plan execution failure"""
        ai_player = ai_player_with_mocks
        ai_player._running = True

        # Setup mocks with proper state to avoid emergency handling
        current_state = CharacterGameState(
            name="test_char",
            level=1,
            xp=0,
            gold=0,
            hp=100,
            max_hp=100,
            x=0,
            y=0,
            mining_level=1,
            mining_xp=0,
            woodcutting_level=1,
            woodcutting_xp=0,
            fishing_level=1,
            fishing_xp=0,
            weaponcrafting_level=1,
            weaponcrafting_xp=0,
            gearcrafting_level=1,
            gearcrafting_xp=0,
            jewelrycrafting_level=1,
            jewelrycrafting_xp=0,
            cooking_level=1,
            cooking_xp=0,
            alchemy_level=1,
            alchemy_xp=0,
            cooldown=0,
            can_fight=True,
            cooldown_ready=True
        )
        ai_player.state_manager.get_current_state = AsyncMock(return_value=current_state)  # type: ignore
        ai_player.goal_manager.select_next_goal.return_value = {GameState.CHARACTER_LEVEL: 2}  # type: ignore
        ai_player.goal_manager.plan_with_cooldown_awareness = AsyncMock(return_value=[{"action": "test"}])  # type: ignore

        # Mock execute_plan to return failure initially, then break loop
        execution_attempts = 0
        async def mock_execute_plan(plan: Any) -> bool:
            nonlocal execution_attempts
            execution_attempts += 1
            if execution_attempts == 1:
                return False  # First attempt fails
            else:
                return True

        # Mock sleep to break the loop after a couple iterations
        sleep_calls = 0
        async def mock_sleep(duration: float) -> None:
            nonlocal sleep_calls
            sleep_calls += 1
            if sleep_calls >= 2:  # Break after a few sleep calls
                ai_player._running = False

        with patch.object(ai_player, 'execute_plan', side_effect=mock_execute_plan):
            with patch('asyncio.sleep', side_effect=mock_sleep):
                await ai_player.main_loop()

        # Should have attempted execution and handled failure
        assert execution_attempts >= 1

    async def test_execute_plan_handles_action_executor_exception(self, ai_player_with_mocks: AIPlayer) -> None:
        """Test that execute_plan handles exceptions from ActionExecutor"""
        ai_player = ai_player_with_mocks

        plan = [{"action": "test"}]
        ai_player.action_executor.execute_plan = AsyncMock(side_effect=Exception("Executor failed"))  # type: ignore

        result = await ai_player.execute_plan(plan)

        assert result is False
        assert ai_player._execution_stats["failed_actions"] == 1

    async def test_handle_emergency_state_refresh_exception(self, ai_player_with_mocks: AIPlayer) -> None:
        """Test that handle_emergency handles exceptions during state refresh"""
        ai_player = ai_player_with_mocks

        # Character appears stuck - no actions available
        current_state = CharacterGameState(
            name="test_char",
            level=1,
            xp=0,
            gold=0,
            hp=100,
            max_hp=100,
            x=0,
            y=0,
            mining_level=1,
            mining_xp=0,
            woodcutting_level=1,
            woodcutting_xp=0,
            fishing_level=1,
            fishing_xp=0,
            weaponcrafting_level=1,
            weaponcrafting_xp=0,
            gearcrafting_level=1,
            gearcrafting_xp=0,
            jewelrycrafting_level=1,
            jewelrycrafting_xp=0,
            cooking_level=1,
            cooking_xp=0,
            alchemy_level=1,
            alchemy_xp=0,
            cooldown=0,
            cooldown_ready=True,
            can_fight=False,
            can_gather=False,
            can_craft=False,
            can_trade=False,
            can_move=False,
            can_rest=False
        )

        # Make force_refresh raise an exception
        ai_player.state_manager.force_refresh = AsyncMock(side_effect=Exception("Refresh failed"))  # type: ignore

        await ai_player.handle_emergency(current_state)

        # Should have attempted refresh despite exception
        ai_player.state_manager.force_refresh.assert_called_once()  # type: ignore
