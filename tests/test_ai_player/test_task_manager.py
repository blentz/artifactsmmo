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
        mock_api_client.accept_task.return_value = Mock()

        result = await task_manager.accept_task("test_character", "test_task")

        assert result is True
        mock_api_client.accept_task.assert_called_once_with("test_character", "test_task")

    @pytest.mark.asyncio
    async def test_accept_task_failure(self, task_manager, mock_api_client):
        """Test task acceptance failure"""
        mock_api_client.accept_task.side_effect = Exception("API Error")

        result = await task_manager.accept_task("test_character", "test_task")

        assert result is False

    @pytest.mark.asyncio
    async def test_complete_task_success(self, task_manager, mock_api_client):
        """Test successful task completion"""
        mock_api_client.complete_task.return_value = Mock()

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

        result = await task_manager.complete_task("test_character", "test_task")

        assert result is True
        assert "test_task" in task_manager.completed_tasks
        assert len(task_manager.active_tasks["test_character"]) == 0

    @pytest.mark.asyncio
    async def test_complete_task_failure(self, task_manager, mock_api_client):
        """Test task completion failure"""
        mock_api_client.complete_task.side_effect = Exception("API Error")

        result = await task_manager.complete_task("test_character", "test_task")

        assert result is False

    @pytest.mark.asyncio
    async def test_complete_task_api_returns_false(self, task_manager, mock_api_client):
        """Test task completion when API returns false"""
        mock_api_client.complete_task.return_value = None  # API returns falsy

        result = await task_manager.complete_task("test_character", "test_task")

        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_task_success(self, task_manager, mock_api_client):
        """Test successful task cancellation"""
        mock_api_client.cancel_task.return_value = Mock()

        # Add a task to active tasks
        task_manager.active_tasks["test_character"] = [
            TaskProgress(
                task_code="test_task",
                character_name="test_character",
                progress=5,
                target=10,
                completed=False,
                started_at=datetime.now()
            )
        ]

        result = await task_manager.cancel_task("test_character", "test_task")

        assert result is True
        assert len(task_manager.active_tasks["test_character"]) == 0

    @pytest.mark.asyncio
    async def test_cancel_task_failure(self, task_manager, mock_api_client):
        """Test task cancellation failure"""
        mock_api_client.cancel_task.side_effect = Exception("API Error")

        result = await task_manager.cancel_task("test_character", "test_task")

        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_task_api_returns_false(self, task_manager, mock_api_client):
        """Test task cancellation when API returns false"""
        mock_api_client.cancel_task.return_value = None  # API returns falsy

        result = await task_manager.cancel_task("test_character", "test_task")

        assert result is False

    def test_track_task_progress_existing(self, task_manager):
        """Test tracking progress for existing task"""
        task_progress = TaskProgress(
            task_code="test_task",
            character_name="test_character",
            progress=5,
            target=10,
            completed=False,
            started_at=datetime.now()
        )
        task_manager.active_tasks["test_character"] = [task_progress]

        result = task_manager.track_task_progress("test_character", "test_task")

        assert result == task_progress

    def test_track_task_progress_new(self, task_manager):
        """Test tracking progress for new task"""
        result = task_manager.track_task_progress("test_character", "test_task")

        assert result.task_code == "test_task"
        assert result.character_name == "test_character"
        assert result.progress == 0
        assert result.target == 1
        assert not result.completed

    def test_update_task_progress_existing(self, task_manager):
        """Test updating progress for existing task"""
        task_progress = TaskProgress(
            task_code="test_task",
            character_name="test_character",
            progress=5,
            target=10,
            completed=False,
            started_at=datetime.now()
        )
        task_manager.active_tasks["test_character"] = [task_progress]

        task_manager.update_task_progress("test_character", "test_task", 8)

        assert task_progress.progress == 8
        assert not task_progress.completed

    def test_update_task_progress_complete(self, task_manager):
        """Test updating progress to completion"""
        task_progress = TaskProgress(
            task_code="test_task",
            character_name="test_character",
            progress=8,
            target=10,
            completed=False,
            started_at=datetime.now()
        )
        task_manager.active_tasks["test_character"] = [task_progress]

        task_manager.update_task_progress("test_character", "test_task", 10)

        assert task_progress.progress == 10
        assert task_progress.completed

    def test_update_task_progress_new_task(self, task_manager):
        """Test updating progress for new task"""
        task_manager.update_task_progress("test_character", "test_task", 3)

        assert len(task_manager.active_tasks["test_character"]) == 1
        assert task_manager.active_tasks["test_character"][0].progress == 3

    def test_is_task_completable(self, task_manager):
        """Test checking if task is completable"""
        # Create a test task
        task = Task(
            code="test_task",
            name="Test Task",
            task_type=TaskType.GATHER_RESOURCES,
            description="",
            requirements=TaskRequirement(
                min_level=5,
                required_skills={},
                required_items=[],
                required_location=None
            ),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )

        task_manager.task_cache["test_character"] = [task]

        # Mark task as completed
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

        character_state = {
            GameState.CHARACTER_LEVEL: 5
        }

        result = task_manager.is_task_completable("test_task", "test_character", character_state)
        assert result is True

    def test_is_task_completable_not_completed(self, task_manager):
        """Test checking if task is completable when not yet completed"""
        # Mark task as not completed
        task_manager.active_tasks["test_character"] = [
            TaskProgress(
                task_code="test_task",
                character_name="test_character",
                progress=5,
                target=10,
                completed=False,  # Not completed
                started_at=datetime.now()
            )
        ]

        character_state = {
            GameState.CHARACTER_LEVEL: 5
        }

        result = task_manager.is_task_completable("test_task", "test_character", character_state)
        assert result is False

    def test_is_task_completable_task_not_in_cache(self, task_manager):
        """Test checking completable for task not in cache"""
        # Mark task as completed but don't have it in cache
        task_manager.active_tasks["test_character"] = [
            TaskProgress(
                task_code="unknown_task",
                character_name="test_character",
                progress=10,
                target=10,
                completed=True,
                started_at=datetime.now()
            )
        ]

        character_state = {
            GameState.CHARACTER_LEVEL: 5
        }

        result = task_manager.is_task_completable("unknown_task", "test_character", character_state)
        assert result is True  # Returns True if not in cache

    def test_estimate_task_completion_time_basic(self, task_manager):
        """Test basic task completion time estimation"""
        task = Task(
            code="test_task",
            name="Test Task",
            task_type=TaskType.GATHER_RESOURCES,
            description="",
            requirements=TaskRequirement(
                min_level=5,
                required_skills={},
                required_items=[],
                required_location=None
            ),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )

        character_state = {GameState.CHARACTER_LEVEL: 5}

        result = task_manager.estimate_task_completion_time(task, character_state)

        assert result >= 1
        assert isinstance(result, int)

    def test_estimate_task_completion_time_with_bonuses(self, task_manager):
        """Test task completion time with various bonuses"""
        task = Task(
            code="test_task",
            name="Test Task",
            task_type=TaskType.GATHER_RESOURCES,
            description="",
            requirements=TaskRequirement(
                min_level=5,
                required_skills={},
                required_items=[],
                required_location=None
            ),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )

        state_with_tool = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.TOOL_EQUIPPED: True
        }

        state_without_tool = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.TOOL_EQUIPPED: False
        }

        time_with_tool = task_manager.estimate_task_completion_time(task, state_with_tool)
        time_without_tool = task_manager.estimate_task_completion_time(task, state_without_tool)

        assert time_with_tool <= time_without_tool

    def test_estimate_task_completion_time_with_travel(self, task_manager):
        """Test task completion time with travel distance"""
        task = Task(
            code="test_task",
            name="Test Task",
            task_type=TaskType.GATHER_RESOURCES,
            description="",
            requirements=TaskRequirement(
                min_level=5,
                required_skills={},
                required_items=[],
                required_location=(10, 10)
            ),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )

        state_near = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.CURRENT_X: 10,
            GameState.CURRENT_Y: 10
        }

        state_far = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.CURRENT_X: 0,
            GameState.CURRENT_Y: 0
        }

        time_near = task_manager.estimate_task_completion_time(task, state_near)
        time_far = task_manager.estimate_task_completion_time(task, state_far)

        assert time_far > time_near

    def test_estimate_task_completion_time_crafting(self, task_manager):
        """Test task completion time with crafting modifiers"""
        task = Task(
            code="test_task",
            name="Test Task",
            task_type=TaskType.CRAFT_ITEMS,
            description="",
            requirements=TaskRequirement(
                min_level=5,
                required_skills={},
                required_items=[],
                required_location=None
            ),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )

        state_with_materials = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HAS_CRAFTING_MATERIALS: True
        }

        state_without_materials = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HAS_CRAFTING_MATERIALS: False
        }

        time_with_materials = task_manager.estimate_task_completion_time(task, state_with_materials)
        time_without_materials = task_manager.estimate_task_completion_time(task, state_without_materials)

        assert time_with_materials <= time_without_materials

    def test_estimate_task_completion_time_combat_modifiers(self, task_manager):
        """Test task completion time with combat modifiers"""
        task = Task(
            code="test_task",
            name="Test Task",
            task_type=TaskType.KILL_MONSTERS,
            description="",
            requirements=TaskRequirement(
                min_level=5,
                required_skills={},
                required_items=[],
                required_location=None
            ),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )

        state_low_hp = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_LOW: True,
            GameState.COMBAT_ADVANTAGE: False
        }

        state_advantage = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_LOW: False,
            GameState.COMBAT_ADVANTAGE: True
        }

        time_low_hp = task_manager.estimate_task_completion_time(task, state_low_hp)
        time_advantage = task_manager.estimate_task_completion_time(task, state_advantage)

        assert time_low_hp > time_advantage

    def test_find_similar_tasks(self, task_manager):
        """Test finding similar tasks"""
        base_task = Task(
            code="base_task",
            name="Base Task",
            task_type=TaskType.GATHER_RESOURCES,
            description="",
            requirements=TaskRequirement(
                min_level=5,
                required_skills={"mining": 3},
                required_items=[],
                required_location=(5, 5)
            ),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )

        similar_tasks = [
            Task(
                code="same_type",
                name="Same Type",
                task_type=TaskType.GATHER_RESOURCES,
                description="",
                requirements=TaskRequirement(1, {}, [], None),
                rewards=TaskReward(0, 0, []),
                estimated_duration=30,
                priority=TaskPriority.MEDIUM
            ),
            Task(
                code="same_location",
                name="Same Location",
                task_type=TaskType.KILL_MONSTERS,
                description="",
                requirements=TaskRequirement(1, {}, [], (5, 5)),
                rewards=TaskReward(0, 0, []),
                estimated_duration=30,
                priority=TaskPriority.MEDIUM
            ),
            Task(
                code="similar_level",
                name="Similar Level",
                task_type=TaskType.CRAFT_ITEMS,
                description="",
                requirements=TaskRequirement(6, {}, [], None),
                rewards=TaskReward(0, 0, []),
                estimated_duration=30,
                priority=TaskPriority.MEDIUM
            ),
            Task(
                code="same_skill",
                name="Same Skill",
                task_type=TaskType.CRAFT_ITEMS,
                description="",
                requirements=TaskRequirement(1, {"mining": 5}, [], None),
                rewards=TaskReward(0, 0, []),
                estimated_duration=30,
                priority=TaskPriority.MEDIUM
            )
        ]

        # Add a task with different skill intersection
        skill_intersection_task = Task(
            code="skill_intersection",
            name="Skill Intersection",
            task_type=TaskType.DELIVER_ITEMS,
            description="",
            requirements=TaskRequirement(1, {"mining": 2, "crafting": 3}, [], None),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )
        similar_tasks.append(skill_intersection_task)

        result = task_manager.find_similar_tasks(base_task, similar_tasks)

        assert len(result) == 5
        assert result[0].code == "same_type"  # Highest priority (same type)
        assert "same_location" in [t.code for t in result]
        assert "similar_level" in [t.code for t in result]
        assert "same_skill" in [t.code for t in result]
        assert "skill_intersection" in [t.code for t in result]

    def test_find_similar_tasks_excludes_self(self, task_manager):
        """Test that find_similar_tasks excludes the task itself"""
        task = Task(
            code="test_task",
            name="Test Task",
            task_type=TaskType.GATHER_RESOURCES,
            description="",
            requirements=TaskRequirement(5, {}, [], None),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )

        available_tasks = [task]  # Only the task itself

        result = task_manager.find_similar_tasks(task, available_tasks)

        assert len(result) == 0

    def test_find_similar_tasks_skill_intersection_only(self, task_manager):
        """Test finding tasks with only skill intersection as similarity"""
        base_task = Task(
            code="base_task",
            name="Base Task",
            task_type=TaskType.GATHER_RESOURCES,
            description="",
            requirements=TaskRequirement(
                min_level=5,
                required_skills={"mining": 3, "woodcutting": 2},
                required_items=[],
                required_location=(5, 5)
            ),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )

        # Task that only shares skills (different type, location, and level > 5 difference)
        skill_only_task = Task(
            code="skill_only",
            name="Skill Only",
            task_type=TaskType.CRAFT_ITEMS,  # Different type
            description="",
            requirements=TaskRequirement(
                min_level=15,  # Level difference > 5
                required_skills={"mining": 5},  # Shared skill
                required_items=[],
                required_location=(20, 20)  # Different location
            ),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )

        available_tasks = [skill_only_task]

        result = task_manager.find_similar_tasks(base_task, available_tasks)

        assert len(result) == 1
        assert result[0].code == "skill_only"

    def test_get_task_requirements_actions_level_too_low(self, task_manager):
        """Test get_task_requirements_actions when character level is too low"""
        task = Task(
            code="test_task",
            name="Test Task",
            task_type=TaskType.GATHER_RESOURCES,
            description="",
            requirements=TaskRequirement(
                min_level=10,  # Higher than character level
                required_skills={},
                required_items=[],
                required_location=None
            ),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )

        character_state = {GameState.CHARACTER_LEVEL: 5}  # Too low

        result = task_manager.get_task_requirements_actions(task, character_state)
        assert result == []

    def test_get_task_requirements_actions_missing_items(self, task_manager):
        """Test get_task_requirements_actions when missing items"""
        task = Task(
            code="test_task",
            name="Test Task",
            task_type=TaskType.GATHER_RESOURCES,
            description="",
            requirements=TaskRequirement(
                min_level=5,
                required_skills={},
                required_items=[{"code": "iron_ore", "quantity": 10}],
                required_location=None
            ),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )

        character_state = {
            GameState.CHARACTER_LEVEL: 5,
            'inventory': [{"code": "iron_ore", "quantity": 5}]  # Not enough
        }

        result = task_manager.get_task_requirements_actions(task, character_state)
        assert result == []

    def test_get_task_requirements_actions_wrong_location(self, task_manager):
        """Test get_task_requirements_actions when at wrong location"""
        task = Task(
            code="test_task",
            name="Test Task",
            task_type=TaskType.GATHER_RESOURCES,
            description="",
            requirements=TaskRequirement(
                min_level=5,
                required_skills={},
                required_items=[],
                required_location=(10, 10)
            ),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )

        character_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.CURRENT_X: 0,
            GameState.CURRENT_Y: 0,
            'inventory': []
        }

        result = task_manager.get_task_requirements_actions(task, character_state)
        assert result == []

    def test_get_task_requirements_actions_all_requirements_met(self, task_manager):
        """Test get_task_requirements_actions when all requirements are met"""
        task = Task(
            code="test_task",
            name="Test Task",
            task_type=TaskType.GATHER_RESOURCES,
            description="",
            requirements=TaskRequirement(
                min_level=5,
                required_skills={},
                required_items=[{"code": "iron_ore", "quantity": 5}],
                required_location=(10, 10)
            ),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )

        character_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.CURRENT_X: 10,
            GameState.CURRENT_Y: 10,
            'inventory': [{"code": "iron_ore", "quantity": 5}]
        }

        result = task_manager.get_task_requirements_actions(task, character_state)
        assert result == []  # Empty list when all requirements met


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
        assert progress_tracker.completion_rates == {}

    def test_record_task_start(self, progress_tracker):
        """Test recording task start"""
        progress_tracker.record_task_start("test_character", "test_task")
        assert "test_character" in progress_tracker.progress_history
        assert "test_task" in progress_tracker.progress_history["test_character"]

    def test_record_task_completion(self, progress_tracker):
        """Test recording task completion"""
        reward = TaskReward(100, 50, [])
        progress_tracker.record_task_completion("test_character", "test_task", 30, reward)
        assert "test_character" in progress_tracker.completion_rates
        assert progress_tracker.completion_rates["test_character"]["test_task"] == 30

    def test_record_task_progress(self, progress_tracker):
        """Test recording task progress"""
        progress_tracker.record_task_progress("test_character", "test_task", 5, datetime.now())
        # This method currently has pass implementation, testing it doesn't crash

    def test_analyze_task_efficiency(self, progress_tracker):
        """Test analyzing task efficiency"""
        result = progress_tracker.analyze_task_efficiency("test_task")
        assert result["efficiency"] == 1.0
        assert result["success_rate"] == 1.0

    def test_predict_completion_time(self, progress_tracker):
        """Test predicting completion time"""
        result = progress_tracker.predict_completion_time("test_task", 10)
        assert result == 20  # 30 - 10

    def test_get_task_statistics(self, progress_tracker):
        """Test getting task statistics"""
        result = progress_tracker.get_task_statistics("test_character")
        assert result["completed_tasks"] == 0
        assert result["total_time"] == 0
        assert result["average_efficiency"] == 1.0

    def test_identify_improvement_opportunities(self, progress_tracker):
        """Test identifying improvement opportunities"""
        result = progress_tracker.identify_improvement_opportunities("test_character")
        assert result == []


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
    def task_optimizer(self, mock_task_manager, mock_progress_tracker):
        """Create TaskOptimizer instance"""
        return TaskOptimizer(mock_task_manager, mock_progress_tracker)

    def test_init(self, task_optimizer, mock_task_manager, mock_progress_tracker):
        """Test TaskOptimizer initialization"""
        assert task_optimizer.task_manager == mock_task_manager
        assert task_optimizer.progress_tracker == mock_progress_tracker

    def test_optimize_task_sequence(self, task_optimizer, mock_task_manager):
        """Test optimizing task sequence"""
        tasks = []
        character_state = {}
        mock_task_manager.prioritize_tasks.return_value = tasks

        result = task_optimizer.optimize_task_sequence(tasks, character_state)

        assert result == tasks
        mock_task_manager.prioritize_tasks.assert_called_once_with(tasks, character_state)

    def test_find_task_chains_empty(self, task_optimizer):
        """Test finding task chains with no similar tasks"""
        tasks = [Task(
            code="test_task",
            name="Test Task",
            task_type=TaskType.GATHER_RESOURCES,
            description="",
            requirements=TaskRequirement(1, {}, [], None),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )]

        result = task_optimizer.find_task_chains(tasks)
        assert result == []

    def test_find_task_chains_with_similar_tasks(self, task_optimizer, mock_task_manager):
        """Test finding task chains with similar tasks"""
        base_task = Task(
            code="base_task",
            name="Base Task",
            task_type=TaskType.GATHER_RESOURCES,
            description="",
            requirements=TaskRequirement(1, {}, [], None),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )
        
        similar_task1 = Task(
            code="similar1",
            name="Similar 1",
            task_type=TaskType.GATHER_RESOURCES,
            description="",
            requirements=TaskRequirement(1, {}, [], None),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )
        
        similar_task2 = Task(
            code="similar2",
            name="Similar 2",
            task_type=TaskType.GATHER_RESOURCES,
            description="",
            requirements=TaskRequirement(1, {}, [], None),
            rewards=TaskReward(0, 0, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )

        tasks = [base_task, similar_task1, similar_task2]
        mock_task_manager.find_similar_tasks.return_value = [similar_task1, similar_task2]

        result = task_optimizer.find_task_chains(tasks)
        
        assert len(result) == 3  # One chain for each task
        assert len(result[0]) <= 3  # Chain limited to 3 tasks

    def test_calculate_opportunity_cost(self, task_optimizer):
        """Test calculating opportunity cost"""
        task = Task(
            code="main_task",
            name="Main Task",
            task_type=TaskType.GATHER_RESOURCES,
            description="",
            requirements=TaskRequirement(1, {}, [], None),
            rewards=TaskReward(50, 25, []),
            estimated_duration=30,
            priority=TaskPriority.MEDIUM
        )

        alternative = Task(
            code="alt_task",
            name="Alternative Task",
            task_type=TaskType.GATHER_RESOURCES,
            description="",
            requirements=TaskRequirement(1, {}, [], None),
            rewards=TaskReward(100, 50, []),
            estimated_duration=30,
            priority=TaskPriority.HIGH
        )

        character_state = {GameState.CHARACTER_LEVEL: 5}

        result = task_optimizer.calculate_opportunity_cost(task, [alternative], character_state)
        assert result >= 0.0

    def test_suggest_preparation_actions_gathering(self, task_optimizer):
        """Test suggesting preparation actions for gathering"""
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

        character_state = {GameState.TOOL_EQUIPPED: False}

        result = task_optimizer.suggest_preparation_actions(task, character_state)
        assert "Equip appropriate gathering tool" in result

    def test_suggest_preparation_actions_combat(self, task_optimizer):
        """Test suggesting preparation actions for combat"""
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

        character_state = {GameState.HP_CURRENT: 40}

        result = task_optimizer.suggest_preparation_actions(task, character_state)
        assert "Rest to recover HP" in result

    def test_evaluate_task_abandonment(self, task_optimizer):
        """Test evaluating task abandonment"""
        task_progress = TaskProgress(
            task_code="test_task",
            character_name="test_character",
            progress=2,
            target=10,
            completed=False,
            started_at=datetime.now()
        )

        result = task_optimizer.evaluate_task_abandonment([task_progress], [])
        assert len(result) == 1
        assert "Consider abandoning test_task" in result[0]
