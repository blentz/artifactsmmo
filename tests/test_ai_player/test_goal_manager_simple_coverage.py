"""
Goal Manager Simple Coverage Tests

Targets specific uncovered lines in goal_manager.py to achieve higher coverage.
Focus on exception handling, edge cases, and error scenarios that existing tests miss.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock

from src.ai_player.goal_manager import GoalManager
from src.ai_player.state.game_state import GameState
from src.ai_player.state.character_game_state import CharacterGameState
from src.game_data.game_data import GameData


class TestGoalManagerSimpleCoverage:
    """Simple coverage tests targeting specific uncovered lines in goal_manager.py"""

    @pytest.fixture
    def mock_cache_manager(self):
        """Create a mock cache manager for testing"""
        cache_manager = AsyncMock()

        # Mock cache manager methods to trigger line 86-92 coverage
        cache_manager.get_all_maps.return_value = [Mock(code="test_map")]
        cache_manager.get_all_monsters.return_value = [Mock(code="test_monster")]
        cache_manager.get_all_resources.return_value = [Mock(code="test_resource")]
        cache_manager.get_all_npcs.return_value = [Mock(code="test_npc")]
        cache_manager.get_all_items.return_value = [Mock(code="test_item")]

        return cache_manager

    @pytest.fixture
    def mock_action_registry(self):
        """Create a mock action registry"""
        action_registry = Mock()
        action_registry.generate_actions_for_state.return_value = []
        return action_registry

    @pytest.fixture
    def mock_cooldown_manager(self):
        """Create a mock cooldown manager"""
        cooldown_manager = Mock()
        return cooldown_manager

    @pytest.fixture
    def goal_manager(self, mock_cache_manager, mock_action_registry, mock_cooldown_manager):
        """Create goal manager with mocked dependencies"""
        return GoalManager(
            action_registry=mock_action_registry,
            cooldown_manager=mock_cooldown_manager,
            cache_manager=mock_cache_manager,
        )

    @pytest.fixture
    def character_state(self):
        """Create a test character state"""
        state = CharacterGameState(
            name="test_character",
            level=10,
            xp=0,
            gold=0,
            hp=100,
            max_hp=100,
            x=5,
            y=5,
            mining_level=5,
            mining_xp=0,
            woodcutting_level=1,
            woodcutting_xp=0,
            fishing_level=1,
            fishing_xp=0,
            weaponcrafting_level=5,
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
        )
        return state

    async def test_get_game_data_cache_manager_exception_handling(self, goal_manager):
        """Test get_game_data method exception handling - covers lines 86-92"""
        # Mock cache manager to raise exception on get_all_maps
        goal_manager.cache_manager.get_all_maps.side_effect = Exception("Cache error")

        result = await goal_manager.get_game_data()
        assert result is None

    async def test_get_game_data_without_cache_manager(self):
        """Test get_game_data when cache_manager is None - covers lines 83-84"""
        action_registry = Mock()
        cooldown_manager = Mock()
        goal_manager = GoalManager(
            action_registry=action_registry, cooldown_manager=cooldown_manager, cache_manager=None
        )

        result = await goal_manager.get_game_data()
        assert result is None

    async def test_get_game_data_successful_case(self, goal_manager):
        """Test successful get_game_data execution - covers lines 88-91"""
        result = await goal_manager.get_game_data()

        assert result is not None
        assert isinstance(result, GameData)

        # Verify all cache manager methods were called
        goal_manager.cache_manager.get_all_maps.assert_called_once()
        goal_manager.cache_manager.get_all_monsters.assert_called_once()
        goal_manager.cache_manager.get_all_resources.assert_called_once()
        goal_manager.cache_manager.get_all_npcs.assert_called_once()
        goal_manager.cache_manager.get_all_items.assert_called_once()

    async def test_find_nearest_content_location_no_cache_manager(self):
        """Test find_nearest_content_location when cache_manager is None"""
        action_registry = Mock()
        cooldown_manager = Mock()
        goal_manager = GoalManager(
            action_registry=action_registry, cooldown_manager=cooldown_manager, cache_manager=None
        )

        result = await goal_manager.find_nearest_content_location(5, 5, "monster")
        assert result is None

    async def test_find_nearest_safe_location_no_cache_manager(self):
        """Test find_nearest_safe_location when cache_manager is None"""
        action_registry = Mock()
        cooldown_manager = Mock()
        goal_manager = GoalManager(
            action_registry=action_registry, cooldown_manager=cooldown_manager, cache_manager=None
        )

        result = await goal_manager.find_nearest_safe_location(5, 5)
        assert result is None

    async def test_should_defer_planning_without_cooldown_manager(self):
        """Test should_defer_planning when cooldown_manager is None"""
        action_registry = Mock()
        goal_manager = GoalManager(action_registry=action_registry, cooldown_manager=None, cache_manager=None)

        result = goal_manager.should_defer_planning("test_character")
        assert result is False

    def test_max_level_achieved_with_high_level_character(self, goal_manager, character_state):
        """Test max_level_achieved with high level character"""
        character_state.level = 45
        character_state.mining_level = 45
        character_state.woodcutting_level = 45
        character_state.fishing_level = 45
        character_state.weaponcrafting_level = 45
        character_state.gearcrafting_level = 45
        character_state.jewelrycrafting_level = 45
        character_state.cooking_level = 45
        character_state.alchemy_level = 45

        result = goal_manager.max_level_achieved(character_state)
        assert result is True

    def test_max_level_achieved_with_low_level_character(self, goal_manager, character_state):
        """Test max_level_achieved with low level character"""
        character_state.level = 10

        result = goal_manager.max_level_achieved(character_state)
        assert result is False

    def test_estimate_goal_cost_empty_goal(self, goal_manager, character_state):
        """Test estimate_goal_cost with empty goal"""
        goal = {}
        current_state = character_state.to_goap_state()

        result = goal_manager.estimate_goal_cost(goal, current_state)
        assert result == 1

    def test_is_goal_achievable_empty_goal(self, goal_manager, character_state):
        """Test is_goal_achievable with empty goal"""
        goal = {}
        current_state = character_state.to_goap_state()

        result = goal_manager.is_goal_achievable(goal, current_state)
        assert result is True

    def test_get_survival_goals_high_hp(self, goal_manager, character_state):
        """Test get_survival_goals with high HP character"""
        current_state = character_state.to_goap_state()
        current_state[GameState.HP_CURRENT.value] = 100
        current_state[GameState.HP_MAX.value] = 100

        result = goal_manager.get_survival_goals(current_state)
        assert isinstance(result, list)
        assert len(result) == 0  # No survival goals needed with full HP

    def test_get_economic_goals_high_level(self, goal_manager, character_state):
        """Test get_economic_goals with high level character"""
        character_state.level = 25
        current_state = character_state.to_goap_state()

        result = goal_manager.get_economic_goals(current_state)
        assert isinstance(result, list)
        # Should return some economic goals for high level character
