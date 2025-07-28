"""
Tests for TaskManager functionality

This module tests the task management system including task discovery,
progress tracking, selection optimization, and API integration.
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from src.ai_player.state.game_state import GameState
from src.ai_player.task_manager import (
    Task,
    TaskGoalGenerator,
    TaskManager,
    TaskOptimizer,
    TaskPriority,
    TaskProgress,
    TaskProgressTracker,
    TaskRequirement,
    TaskReward,
    TaskType,
)


class TestTaskReward:
    """Test TaskReward functionality"""

    def test_calculate_value_basic(self):
        """Test basic reward value calculation"""
        reward = TaskReward(
            xp=100,
            gold=50,
            items=[{"code": "iron_sword", "quantity": 1, "level": 5}]
        )

        value = reward.calculate_value(character_level=5)

        expected_xp_value = 100 / 5  # 20
        expected_gold_value = 50 * 0.1  # 5
        expected_items_value = (5 * 10 * 1) * 0.5  # 25
        expected_total = expected_xp_value + expected_gold_value + expected_items_value  # 50

        assert value == expected_total

    def test_calculate_value_high_level_character(self):
        """Test reward value scales with character level"""
        reward = TaskReward(xp=100, gold=0, items=[])

        low_level_value = reward.calculate_value(character_level=1)
        high_level_value = reward.calculate_value(character_level=10)

        assert low_level_value > high_level_value

    def test_calculate_value_multiple_items(self):
        """Test value calculation with multiple items"""
        reward = TaskReward(
            xp=0,
            gold=0,
            items=[
                {"code": "sword", "quantity": 2, "level": 10},
                {"code": "potion", "quantity": 5, "level": 3}
            ]
        )

        value = reward.calculate_value(character_level=5)

        sword_value = (10 * 10 * 2) * 0.5  # 100
        potion_value = (3 * 10 * 5) * 0.5  # 75
        expected_total = sword_value + potion_value  # 175

        assert value == expected_total


class TestTaskRequirement:
    """Test TaskRequirement functionality"""

    def test_can_satisfy_level_requirement(self):
        """Test level requirement validation"""
        requirement = TaskRequirement(
            min_level=5,
            required_skills={},
            required_items=[],
            required_location=None
        )

        character_state = {GameState.CHARACTER_LEVEL: 5}
        assert requirement.can_satisfy(character_state) is True

        character_state = {GameState.CHARACTER_LEVEL: 3}
        assert requirement.can_satisfy(character_state) is False

    def test_can_satisfy_skill_requirements(self):
        """Test skill requirement validation"""
        requirement = TaskRequirement(
            min_level=1,
            required_skills={"mining": 10, "woodcutting": 5},
            required_items=[],
            required_location=None
        )

        character_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.MINING_LEVEL: 10,
            GameState.WOODCUTTING_LEVEL: 5
        }
        assert requirement.can_satisfy(character_state) is True

        character_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.MINING_LEVEL: 8,
            GameState.WOODCUTTING_LEVEL: 5
        }
        assert requirement.can_satisfy(character_state) is False

    def test_can_satisfy_unknown_skill(self):
        """Test requirement with unknown skill that doesn't exist in GameState"""
        requirement = TaskRequirement(
            min_level=1,
            required_skills={"unknown_skill": 5},
            required_items=[],
            required_location=None
        )

        character_state = {GameState.CHARACTER_LEVEL: 5}
        # Should return True as unknown skills are skipped
        assert requirement.can_satisfy(character_state) is True

    def test_can_satisfy_item_requirements(self):
        """Test item requirement validation"""
        requirement = TaskRequirement(
            min_level=1,
            required_skills={},
            required_items=[{"code": "iron_ore", "quantity": 5}],
            required_location=None
        )

        character_state = {
            GameState.CHARACTER_LEVEL: 5,
            'inventory': [{"code": "iron_ore", "quantity": 5}]
        }
        assert requirement.can_satisfy(character_state) is True

        character_state = {
            GameState.CHARACTER_LEVEL: 5,
            'inventory': [{"code": "iron_ore", "quantity": 3}]
        }
        assert requirement.can_satisfy(character_state) is False

    def test_can_satisfy_location_requirement(self):
        """Test location requirement validation"""
        requirement = TaskRequirement(
            min_level=1,
            required_skills={},
            required_items=[],
            required_location=(10, 15)
        )

        character_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.CURRENT_X: 10,
            GameState.CURRENT_Y: 15
        }
        assert requirement.can_satisfy(character_state) is True

        character_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.CURRENT_X: 5,
            GameState.CURRENT_Y: 15
        }
        assert requirement.can_satisfy(character_state) is False


class TestTask:
    """Test Task functionality"""

    def create_test_task(self) -> Task:
        """Create a test task for testing"""
        requirements = TaskRequirement(
            min_level=5,
            required_skills={"mining": 3},
            required_items=[],
            required_location=None
        )

        rewards = TaskReward(
            xp=100,
            gold=50,
            items=[{"code": "iron_ore", "quantity": 2, "level": 3}]
        )

        return Task(
            code="test_task",
            name="Test Mining Task",
            task_type=TaskType.GATHER_RESOURCES,
            description="Test task for mining",
            requirements=requirements,
            rewards=rewards,
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )

    def test_is_suitable_for_character_requirements(self):
        """Test task suitability based on requirements"""
        task = self.create_test_task()

        suitable_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.MINING_LEVEL: 3,
            GameState.CAN_GATHER: True,
            GameState.INVENTORY_FULL: False
        }
        assert task.is_suitable_for_character(suitable_state) is True

        unsuitable_state = {
            GameState.CHARACTER_LEVEL: 3,
            GameState.MINING_LEVEL: 1
        }
        assert task.is_suitable_for_character(unsuitable_state) is False

    def test_is_suitable_for_character_level_difference(self):
        """Test task suitability based on level difference"""
        task = self.create_test_task()

        character_state = {
            GameState.CHARACTER_LEVEL: 20,  # Too high level
            GameState.MINING_LEVEL: 20,
            GameState.CAN_GATHER: True,
            GameState.INVENTORY_FULL: False
        }
        assert task.is_suitable_for_character(character_state) is False

    def test_is_suitable_combat_task_conditions(self):
        """Test combat task specific suitability conditions"""
        task = self.create_test_task()
        task.task_type = TaskType.KILL_MONSTERS

        suitable_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.MINING_LEVEL: 3,
            GameState.HP_LOW: False,
            GameState.CAN_FIGHT: True
        }
        assert task.is_suitable_for_character(suitable_state) is True

        unsuitable_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.MINING_LEVEL: 3,
            GameState.HP_LOW: True,
            GameState.CAN_FIGHT: False
        }
        assert task.is_suitable_for_character(unsuitable_state) is False

        # Test separately with just CAN_FIGHT: False
        unsuitable_cant_fight = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.MINING_LEVEL: 3,
            GameState.HP_LOW: False,
            GameState.CAN_FIGHT: False
        }
        assert task.is_suitable_for_character(unsuitable_cant_fight) is False

    def test_is_suitable_gathering_task_conditions(self):
        """Test gathering task specific suitability conditions"""
        task = self.create_test_task()
        task.task_type = TaskType.GATHER_RESOURCES

        # Test suitable state
        suitable_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.MINING_LEVEL: 3,
            GameState.CAN_GATHER: True,
            GameState.INVENTORY_FULL: False
        }
        assert task.is_suitable_for_character(suitable_state) is True

        # Test with can't gather
        unsuitable_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.MINING_LEVEL: 3,
            GameState.CAN_GATHER: False,
            GameState.INVENTORY_FULL: False
        }
        assert task.is_suitable_for_character(unsuitable_state) is False

        # Test with inventory full
        unsuitable_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.MINING_LEVEL: 3,
            GameState.CAN_GATHER: True,
            GameState.INVENTORY_FULL: True
        }
        assert task.is_suitable_for_character(unsuitable_state) is False

    def test_is_suitable_crafting_task_conditions(self):
        """Test crafting task specific suitability conditions"""
        task = self.create_test_task()
        task.task_type = TaskType.CRAFT_ITEMS

        # Test suitable state
        suitable_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.MINING_LEVEL: 3,
            GameState.CAN_CRAFT: True,
            GameState.HAS_CRAFTING_MATERIALS: True
        }
        assert task.is_suitable_for_character(suitable_state) is True

        # Test with can't craft
        unsuitable_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.MINING_LEVEL: 3,
            GameState.CAN_CRAFT: False,
            GameState.HAS_CRAFTING_MATERIALS: True
        }
        assert task.is_suitable_for_character(unsuitable_state) is False

        # Test without crafting materials
        unsuitable_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.MINING_LEVEL: 3,
            GameState.CAN_CRAFT: True,
            GameState.HAS_CRAFTING_MATERIALS: False
        }
        assert task.is_suitable_for_character(unsuitable_state) is False

    def test_calculate_efficiency_score(self):
        """Test efficiency score calculation"""
        task = self.create_test_task()

        character_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.TOOL_EQUIPPED: True
        }

        efficiency = task.calculate_efficiency_score(character_state)

        assert efficiency > 0
        assert isinstance(efficiency, float)

    def test_calculate_efficiency_score_with_bonuses(self):
        """Test efficiency calculation with various bonuses"""
        task = self.create_test_task()
        task.task_type = TaskType.GATHER_RESOURCES

        state_with_tool = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.TOOL_EQUIPPED: True
        }

        state_without_tool = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.TOOL_EQUIPPED: False
        }

        efficiency_with_tool = task.calculate_efficiency_score(state_with_tool)
        efficiency_without_tool = task.calculate_efficiency_score(state_without_tool)

        assert efficiency_with_tool > efficiency_without_tool

    def test_calculate_efficiency_score_combat_modifiers(self):
        """Test efficiency calculation with combat modifiers"""
        task = self.create_test_task()
        task.task_type = TaskType.KILL_MONSTERS

        # Test with low HP penalty
        state_low_hp = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_LOW: True,
            GameState.COMBAT_ADVANTAGE: False
        }

        # Test with combat advantage
        state_advantage = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_LOW: False,
            GameState.COMBAT_ADVANTAGE: True
        }

        # Test normal state
        state_normal = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_LOW: False,
            GameState.COMBAT_ADVANTAGE: False
        }

        efficiency_low_hp = task.calculate_efficiency_score(state_low_hp)
        efficiency_advantage = task.calculate_efficiency_score(state_advantage)
        efficiency_normal = task.calculate_efficiency_score(state_normal)

        assert efficiency_advantage > efficiency_normal > efficiency_low_hp

    def test_calculate_efficiency_score_zero_time(self):
        """Test efficiency calculation with zero time edge case"""
        task = self.create_test_task()
        task.estimated_duration = 0

        character_state = {GameState.CHARACTER_LEVEL: 5}

        efficiency = task.calculate_efficiency_score(character_state)
        assert efficiency == 0.0


class TestTaskManager:
    """Test TaskManager functionality"""

    @pytest.fixture
    def mock_api_client(self):
        """Create mock API client"""
        client = Mock()
        client.get_all_tasks = AsyncMock()
        client.get_character = AsyncMock()
        client.accept_task = AsyncMock()
        client.action_accept_new_task = AsyncMock()
        client.action_complete_task = AsyncMock()
        client.complete_task = AsyncMock()
        client.cancel_task = AsyncMock()
        return client

    @pytest.fixture
    def task_manager(self, mock_api_client):
        """Create TaskManager instance with mock API client"""
        return TaskManager(mock_api_client)

    def test_init(self, task_manager):
        """Test TaskManager initialization"""
        assert task_manager.active_tasks == {}
        assert task_manager.completed_tasks == set()
        assert task_manager.task_cache == {}
        assert task_manager.last_cache_update is None

    @pytest.mark.asyncio
    async def test_fetch_available_tasks_from_api(self, task_manager, mock_api_client):
        """Test fetching tasks from API"""
        mock_task_data = Mock()
        mock_task_data.code = "test_task"
        mock_task_data.type = "gather_resources"
        mock_task_data.level = 5
        mock_task_data.rewards_xp = 100
        mock_task_data.rewards_gold = 50
        mock_task_data.rewards_items = []

        mock_api_client.get_all_tasks.return_value = [mock_task_data]

        tasks = await task_manager.fetch_available_tasks("test_character")

        assert len(tasks) == 1
        assert tasks[0].code == "test_task"
        assert tasks[0].task_type == TaskType.GATHER_RESOURCES
        assert "test_character" in task_manager.task_cache

    @pytest.mark.asyncio
    async def test_fetch_available_tasks_invalid_type(self, task_manager, mock_api_client):
        """Test fetching tasks with invalid task type defaults to KILL_MONSTERS"""
        mock_task_data = Mock()
        mock_task_data.code = "test_task"
        mock_task_data.type = "invalid_type"
        mock_task_data.level = 5
        mock_task_data.rewards_xp = 100
        mock_task_data.rewards_gold = 50
        mock_task_data.rewards_items = []

        mock_api_client.get_all_tasks.return_value = [mock_task_data]

        tasks = await task_manager.fetch_available_tasks("test_character")

        assert len(tasks) == 1
        assert tasks[0].task_type == TaskType.KILL_MONSTERS

    @pytest.mark.asyncio
    async def test_fetch_available_tasks_with_priority(self, task_manager, mock_api_client):
        """Test fetching tasks with valid priority"""
        mock_task_data = Mock()
        mock_task_data.code = "test_task"
        mock_task_data.type = "gather_resources"
        mock_task_data.level = 5
        mock_task_data.rewards_xp = 100
        mock_task_data.rewards_gold = 50
        mock_task_data.rewards_items = []
        mock_task_data.priority = "high"

        mock_api_client.get_all_tasks.return_value = [mock_task_data]

        tasks = await task_manager.fetch_available_tasks("test_character")

        assert len(tasks) == 1
        assert tasks[0].priority == TaskPriority.HIGH

    @pytest.mark.asyncio
    async def test_fetch_available_tasks_api_error_with_cache(self, task_manager, mock_api_client):
        """Test API error falls back to cache"""
        # Pre-populate cache
        cached_task = Task(
            code="cached_task",
            name="Cached Task",
            task_type=TaskType.KILL_MONSTERS,
            description="",
            requirements=TaskRequirement(1, {}, [], None),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )
        task_manager.task_cache["test_character"] = [cached_task]

        # Simulate API error
        mock_api_client.get_all_tasks.side_effect = Exception("API Error")

        tasks = await task_manager.fetch_available_tasks("test_character")

        assert len(tasks) == 1
        assert tasks[0].code == "cached_task"

    @pytest.mark.asyncio
    async def test_fetch_available_tasks_api_error_no_cache(self, task_manager, mock_api_client):
        """Test API error with no cache returns empty list"""
        mock_api_client.get_all_tasks.side_effect = Exception("API Error")

        tasks = await task_manager.fetch_available_tasks("test_character")

        assert len(tasks) == 0

    @pytest.mark.asyncio
    async def test_fetch_available_tasks_uses_cache(self, task_manager):
        """Test that fetch_available_tasks uses cache when available"""
        cached_task = Task(
            code="cached_task",
            name="Cached Task",
            task_type=TaskType.KILL_MONSTERS,
            description="",
            requirements=TaskRequirement(1, {}, [], None),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )

        task_manager.task_cache["test_character"] = [cached_task]
        task_manager.last_cache_update = datetime.now()

        tasks = await task_manager.fetch_available_tasks("test_character")

        assert len(tasks) == 1
        assert tasks[0].code == "cached_task"

    @pytest.mark.asyncio
    async def test_get_character_tasks(self, task_manager, mock_api_client):
        """Test getting character's active tasks"""
        mock_character = Mock()
        mock_character.task = "active_task"
        mock_character.task_progress = 5
        mock_character.task_total = 10

        mock_api_client.get_character.return_value = mock_character

        active_tasks = await task_manager.get_character_tasks("test_character")

        assert len(active_tasks) == 1
        assert active_tasks[0].task_code == "active_task"
        assert active_tasks[0].progress == 5
        assert active_tasks[0].target == 10

    @pytest.mark.asyncio
    async def test_get_character_tasks_no_active_task(self, task_manager, mock_api_client):
        """Test getting character tasks when no task is active"""
        mock_character = Mock()
        mock_character.task = None

        mock_api_client.get_character.return_value = mock_character

        active_tasks = await task_manager.get_character_tasks("test_character")

        assert len(active_tasks) == 0

    @pytest.mark.asyncio
    async def test_get_character_tasks_api_error(self, task_manager, mock_api_client):
        """Test get_character_tasks handles API errors gracefully"""
        mock_api_client.get_character.side_effect = Exception("API Error")

        active_tasks = await task_manager.get_character_tasks("test_character")

        assert len(active_tasks) == 0

    def test_select_optimal_task(self, task_manager):
        """Test optimal task selection"""
        tasks = [
            Task(
                code="low_efficiency",
                name="Low Task",
                task_type=TaskType.KILL_MONSTERS,
                description="",
                requirements=TaskRequirement(1, {}, [], None),
                rewards=TaskReward(10, 5, []),
                estimated_duration=60,
                priority=TaskPriority.LOW
            ),
            Task(
                code="high_efficiency",
                name="High Task",
                task_type=TaskType.GATHER_RESOURCES,
                description="",
                requirements=TaskRequirement(1, {}, [], None),
                rewards=TaskReward(100, 50, []),
                estimated_duration=30,
                priority=TaskPriority.HIGH
            )
        ]

        character_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.CAN_GATHER: True,
            GameState.CAN_FIGHT: True
        }

        optimal_task = task_manager.select_optimal_task(character_state, tasks)

        assert optimal_task is not None
        assert optimal_task.code == "high_efficiency"

    def test_select_optimal_task_no_suitable_tasks(self, task_manager):
        """Test optimal task selection when no tasks are suitable"""
        tasks = [
            Task(
                code="unsuitable_task",
                name="Unsuitable Task",
                task_type=TaskType.KILL_MONSTERS,
                description="",
                requirements=TaskRequirement(100, {}, [], None),  # Level too high
                rewards=TaskReward(10, 5, []),
                estimated_duration=60,
                priority=TaskPriority.LOW
            )
        ]

        character_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.CAN_GATHER: True,
            GameState.CAN_FIGHT: True
        }

        optimal_task = task_manager.select_optimal_task(character_state, tasks)

        assert optimal_task is None

    def test_prioritize_tasks(self, task_manager):
        """Test task prioritization"""
        tasks = [
            Task(
                code="medium_task",
                name="Medium",
                task_type=TaskType.KILL_MONSTERS,
                description="",
                requirements=TaskRequirement(1, {}, [], None),
                rewards=TaskReward(50, 25, []),
                estimated_duration=30,
                priority=TaskPriority.MEDIUM
            ),
            Task(
                code="high_task",
                name="High",
                task_type=TaskType.GATHER_RESOURCES,
                description="",
                requirements=TaskRequirement(1, {}, [], None),
                rewards=TaskReward(50, 25, []),
                estimated_duration=30,
                priority=TaskPriority.HIGH
            )
        ]

        character_state = {GameState.CHARACTER_LEVEL: 5}

        prioritized = task_manager.prioritize_tasks(tasks, character_state)

        assert prioritized[0].priority == TaskPriority.HIGH
        assert prioritized[1].priority == TaskPriority.MEDIUM

    @pytest.mark.asyncio
    async def test_accept_task_success(self, task_manager, mock_api_client):
        """Test successful task acceptance"""
        mock_response = Mock()
        mock_response.data = {'task_code': 'test_task'}  # Truthy data
        mock_api_client.action_accept_new_task.return_value = mock_response

        result = await task_manager.accept_task("test_character", "test_task")

        assert result is True
        mock_api_client.action_accept_new_task.assert_called_once_with("test_character", code="test_task")

    @pytest.mark.asyncio
    async def test_accept_task_failure(self, task_manager, mock_api_client):
        """Test task acceptance failure"""
        mock_api_client.action_accept_new_task.side_effect = Exception("API Error")

        result = await task_manager.accept_task("test_character", "test_task")

        assert result is False

    @pytest.mark.asyncio
    async def test_complete_task_success(self, task_manager, mock_api_client):
        """Test successful task completion"""
        mock_response = Mock()
        mock_response.data = {'task_code': 'test_task'}  # Truthy data
        mock_api_client.action_complete_task.return_value = mock_response

        # Add a task to active tasks
        task_manager.active_tasks["test_character"] = [
            TaskProgress(
                task_code="test_task",
                character_name="test_character",
                progress=10,
                target=10,
                completed=True,
                started_at=datetime.now()
            )
        ]

        result = await task_manager.complete_task("test_character")

        assert result is True
        assert "test_character:current_task" in task_manager.completed_tasks

    @pytest.mark.asyncio
    async def test_complete_task_failure(self, task_manager, mock_api_client):
        """Test task completion failure"""
        mock_api_client.action_complete_task.side_effect = Exception("API Error")

        result = await task_manager.complete_task("test_character")

        assert result is False

    @pytest.mark.asyncio
    async def test_complete_task_api_returns_false(self, task_manager, mock_api_client):
        """Test task completion when API returns false"""
        mock_response = Mock()
        mock_response.data = None  # Falsy data
        mock_api_client.action_complete_task.return_value = mock_response

        result = await task_manager.complete_task("test_character")

        assert result is False





class TestTaskGoalGenerator:
    """Test TaskGoalGenerator functionality"""

    @pytest.fixture
    def mock_task_manager(self):
        """Create mock task manager"""
        return Mock()

    @pytest.fixture
    def goal_generator(self, mock_task_manager):
        """Create TaskGoalGenerator instance"""
        return TaskGoalGenerator(mock_task_manager)

    def test_init(self, goal_generator, mock_task_manager):
        """Test TaskGoalGenerator initialization"""
        assert goal_generator.task_manager == mock_task_manager

    def test_generate_task_goals(self, goal_generator):
        """Test generating task goals"""
        result = goal_generator.generate_task_goals("test_character", {})
        assert result == []

    def test_create_kill_monster_goal(self, goal_generator):
        """Test creating kill monster goal"""
        task = Task(
            code="test_task",
            name="Test Task",
            task_type=TaskType.KILL_MONSTERS,
            description="",
            requirements=TaskRequirement(1, {}, [], None),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )
        result = goal_generator.create_kill_monster_goal(task, {})
        assert result == {}

    def test_create_gather_resource_goal(self, goal_generator):
        """Test creating gather resource goal"""
        task = Task(
            code="test_task",
            name="Test Task",
            task_type=TaskType.GATHER_RESOURCES,
            description="",
            requirements=TaskRequirement(1, {}, [], None),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )
        result = goal_generator.create_gather_resource_goal(task, {})
        assert result == {}

    def test_create_craft_item_goal(self, goal_generator):
        """Test creating craft item goal"""
        task = Task(
            code="test_task",
            name="Test Task",
            task_type=TaskType.CRAFT_ITEMS,
            description="",
            requirements=TaskRequirement(1, {}, [], None),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )
        result = goal_generator.create_craft_item_goal(task, {})
        assert result == {}

    def test_create_delivery_goal(self, goal_generator):
        """Test creating delivery goal"""
        task = Task(
            code="test_task",
            name="Test Task",
            task_type=TaskType.DELIVER_ITEMS,
            description="",
            requirements=TaskRequirement(1, {}, [], None),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )
        result = goal_generator.create_delivery_goal(task, {})
        assert result == {}

    def test_create_trade_goal(self, goal_generator):
        """Test creating trade goal"""
        task = Task(
            code="test_task",
            name="Test Task",
            task_type=TaskType.TRADE_ITEMS,
            description="",
            requirements=TaskRequirement(1, {}, [], None),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )
        result = goal_generator.create_trade_goal(task, {})
        assert result == {}

    def test_prioritize_task_goals(self, goal_generator):
        """Test prioritizing task goals"""
        goals = [{"goal1": True}, {"goal2": True}]
        result = goal_generator.prioritize_task_goals(goals, {})
        assert result == goals


class TestTaskProgressTracker:
    """Test TaskProgressTracker functionality"""

    @pytest.fixture
    def progress_tracker(self):
        """Create TaskProgressTracker instance"""
        return TaskProgressTracker()

    def test_init(self, progress_tracker):
        """Test TaskProgressTracker initialization"""
        assert progress_tracker.progress_history == {}
        assert progress_tracker.completion_times == {}
        assert progress_tracker.efficiency_metrics == {}

    def test_analyze_task_efficiency(self, progress_tracker):
        """Test analyzing task efficiency"""
        result = progress_tracker.analyze_task_efficiency("test_character", "test_task")
        assert isinstance(result, dict)


class TestTaskOptimizer:
    """Test TaskOptimizer functionality"""

    @pytest.fixture
    def mock_task_manager(self):
        """Create mock task manager"""
        task_manager = Mock()
        task_manager.prioritize_tasks.return_value = []
        task_manager.find_similar_tasks.return_value = []
        return task_manager

    @pytest.fixture
    def mock_progress_tracker(self):
        """Create mock progress tracker"""
        return Mock()

    @pytest.fixture
    def task_optimizer(self):
        """Create TaskOptimizer instance"""
        return TaskOptimizer()

    def test_init(self, task_optimizer):
        """Test TaskOptimizer initialization"""
        assert task_optimizer.optimization_history == {}
        assert task_optimizer.performance_cache == {}

    def test_optimize_task_sequence(self, task_optimizer):
        """Test optimizing task sequence"""
        tasks = [
            Task(
                code="test_task",
                name="Test Task",
                task_type=TaskType.GATHER_RESOURCES,
                description="",
                requirements=TaskRequirement(1, {}, [], None),
                rewards=TaskReward(0, 0, []),
                estimated_duration=30,
                priority=TaskPriority.MEDIUM
            )
        ]
        character_state = {GameState.CHARACTER_LEVEL: 5}

        result = task_optimizer.optimize_task_sequence(tasks, character_state)

        assert result == tasks  # Current implementation returns tasks unchanged






