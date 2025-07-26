"""
Task Management System for ArtifactsMMO AI Player

This module provides task discovery, tracking, and completion management for the AI player.
It integrates with the ArtifactsMMO task system to provide structured progression goals
and optimal task selection based on character capabilities and progression strategy.

The task manager works with the GOAP system to prioritize task-based goals and generate
action plans for efficient task completion and reward optimization.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from .actions.base_action import BaseAction
from .state.game_state import GameState


class TaskType(Enum):
    """Types of tasks available in ArtifactsMMO"""
    KILL_MONSTERS = "kill_monsters"
    GATHER_RESOURCES = "gather_resources"
    CRAFT_ITEMS = "craft_items"
    DELIVER_ITEMS = "deliver_items"
    TRADE_ITEMS = "trade_items"
    EXPLORE_MAPS = "explore_maps"


class TaskPriority(Enum):
    """Task priority levels for selection"""
    EMERGENCY = "emergency"  # Low HP, inventory full, etc.
    HIGH = "high"           # Efficient progression tasks
    MEDIUM = "medium"       # Standard progression tasks
    LOW = "low"            # Optional/economic tasks


@dataclass
class TaskProgress:
    """Tracking progress on a specific task"""
    task_code: str
    character_name: str
    progress: int
    target: int
    completed: bool
    started_at: Any  # datetime
    estimated_completion: Any | None = None  # datetime

    @property
    def completion_percentage(self) -> float:
        """Calculate completion percentage"""
        return (self.progress / self.target) * 100 if self.target > 0 else 0


@dataclass
class TaskReward:
    """Represents task completion rewards"""
    xp: int
    gold: int
    items: list[dict[str, Any]]

    def calculate_value(self, character_level: int) -> float:
        """Calculate relative value of rewards for character.
        
        Parameters:
            character_level: Current level of the character for value scaling
            
        Return values:
            Float representing the relative value of these rewards for the character
            
        This method calculates the total value of task rewards considering XP value
        at the character's current level, gold amount, and item values to enable
        task prioritization and optimal reward selection.
        """
        xp_value = self.xp / max(1, character_level)
        gold_value = self.gold

        items_value = 0.0
        for item in self.items:
            quantity = item.get('quantity', 1)
            item_level = item.get('level', 1)
            base_value = item_level * 10
            items_value += base_value * quantity

        total_value = xp_value + (gold_value * 0.1) + (items_value * 0.5)
        return max(0.0, total_value)


@dataclass
class TaskRequirement:
    """Requirements to start/complete a task"""
    min_level: int
    required_skills: dict[str, int]
    required_items: list[dict[str, Any]]
    required_location: tuple[int, int] | None

    def can_satisfy(self, character_state: dict[GameState, Any]) -> bool:
        """Check if character can satisfy requirements.
        
        Parameters:
            character_state: Dictionary with GameState enum keys and current character state
            
        Return values:
            Boolean indicating whether character meets all task requirements
            
        This method validates that the character meets all requirements including
        minimum level, required skills, inventory items, and location constraints
        before task acceptance or completion using GameState enum validation.
        """
        current_level = character_state.get(GameState.CHARACTER_LEVEL, 1)
        if current_level < self.min_level:
            return False

        for skill, required_level in self.required_skills.items():
            skill_enum = getattr(GameState, f"{skill.upper()}_LEVEL", None)
            if skill_enum is None:
                continue
            character_skill_level = character_state.get(skill_enum, 1)
            if character_skill_level < required_level:
                return False

        for required_item in self.required_items:
            item_code = required_item['code']
            required_quantity = required_item.get('quantity', 1)

            character_quantity = 0
            for inventory_item in character_state.get('inventory', []):
                if inventory_item.get('code') == item_code:
                    character_quantity += inventory_item.get('quantity', 0)

            if character_quantity < required_quantity:
                return False

        if self.required_location is not None:
            current_x = character_state.get(GameState.CURRENT_X, 0)
            current_y = character_state.get(GameState.CURRENT_Y, 0)
            required_x, required_y = self.required_location
            if current_x != required_x or current_y != required_y:
                return False

        return True


@dataclass
class Task:
    """Complete task information"""
    code: str
    name: str
    task_type: TaskType
    description: str
    requirements: TaskRequirement
    rewards: TaskReward
    estimated_duration: int  # minutes
    priority: TaskPriority

    def is_suitable_for_character(self, character_state: dict[GameState, Any]) -> bool:
        """Check if task is suitable for character's current state.
        
        Parameters:
            character_state: Dictionary with GameState enum keys and current character state
            
        Return values:
            Boolean indicating whether task is appropriate for character's current progression
            
        This method evaluates task suitability considering character level, skills,
        equipment, and progression state to ensure task selection aligns with
        optimal character development and efficiency goals.
        """
        if not self.requirements.can_satisfy(character_state):
            return False

        character_level = character_state.get(GameState.CHARACTER_LEVEL, 1)

        level_difference = abs(character_level - self.requirements.min_level)
        if level_difference > 10:
            return False

        if self.task_type == TaskType.KILL_MONSTERS:
            if character_state.get(GameState.HP_LOW, False):
                return False
            if not character_state.get(GameState.CAN_FIGHT, True):
                return False

        if self.task_type == TaskType.GATHER_RESOURCES:
            if not character_state.get(GameState.CAN_GATHER, True):
                return False
            if character_state.get(GameState.INVENTORY_FULL, False):
                return False

        if self.task_type == TaskType.CRAFT_ITEMS:
            if not character_state.get(GameState.CAN_CRAFT, True):
                return False
            if not character_state.get(GameState.HAS_CRAFTING_MATERIALS, False):
                return False

        return True

    def calculate_efficiency_score(self, character_state: dict[GameState, Any]) -> float:
        """Calculate task efficiency (reward/time ratio).
        
        Parameters:
            character_state: Dictionary with GameState enum keys and current character state
            
        Return values:
            Float representing task efficiency score (higher = more efficient)
            
        This method calculates the efficiency of completing this task considering
        reward value versus estimated completion time for the character's current
        state, enabling optimal task prioritization and selection.
        """
        character_level = character_state.get(GameState.CHARACTER_LEVEL, 1)

        reward_value = self.rewards.calculate_value(character_level)

        base_time = self.estimated_duration

        level_modifier = max(0.5, min(2.0, character_level / self.requirements.min_level))
        adjusted_time = base_time / level_modifier

        if self.task_type == TaskType.KILL_MONSTERS:
            if character_state.get(GameState.HP_LOW, False):
                adjusted_time *= 1.5
            if character_state.get(GameState.COMBAT_ADVANTAGE, False):
                adjusted_time *= 0.8

        if self.task_type == TaskType.GATHER_RESOURCES:
            tool_equipped = character_state.get(GameState.TOOL_EQUIPPED, False)
            if tool_equipped:
                adjusted_time *= 0.7

        if adjusted_time <= 0:
            return 0.0

        efficiency = reward_value / adjusted_time

        priority_bonus = {
            TaskPriority.EMERGENCY: 3.0,
            TaskPriority.HIGH: 2.0,
            TaskPriority.MEDIUM: 1.0,
            TaskPriority.LOW: 0.5
        }.get(self.priority, 1.0)

        return efficiency * priority_bonus


class TaskManager:
    """Main task management system"""

    def __init__(self, api_client):
        """Initialize TaskManager with API client for task operations.
        
        Parameters:
            api_client: API client wrapper for fetching task data from ArtifactsMMO
            
        Return values:
            None (constructor)
            
        This constructor initializes the TaskManager with task tracking collections
        and API client integration, setting up the infrastructure for task
        discovery, progress monitoring, and completion management.
        """
        self.api_client = api_client
        self.active_tasks: dict[str, list[TaskProgress]] = {}
        self.completed_tasks: set = set()
        self.task_cache: dict[str, list[Task]] = {}
        self.last_cache_update: datetime | None = None
        self.cache_duration = timedelta(minutes=30)

    async def fetch_available_tasks(self, character_name: str) -> list[Task]:
        """Fetch all available tasks from API.
        
        Parameters:
            character_name: Name of the character to fetch available tasks for
            
        Return values:
            List of Task objects representing all available tasks for the character
            
        This method retrieves all tasks available to the specified character from
        the ArtifactsMMO API, filtering by character level and requirements while
        caching results for efficient subsequent access.
        """
        current_time = datetime.now()

        if (self.last_cache_update is None or
            current_time - self.last_cache_update > self.cache_duration or
            character_name not in self.task_cache):

            try:
                raw_tasks = await self.api_client.get_all_tasks()

                tasks = []
                for task_data in raw_tasks:
                    if hasattr(task_data, 'type') and task_data.type in [t.value for t in TaskType]:
                        task_type = TaskType(task_data.type)
                    else:
                        task_type = TaskType.KILL_MONSTERS

                    requirements = TaskRequirement(
                        min_level=getattr(task_data, 'level', 1),
                        required_skills=getattr(task_data, 'skills', {}),
                        required_items=getattr(task_data, 'items', []),
                        required_location=None
                    )

                    rewards = TaskReward(
                        xp=getattr(task_data, 'rewards_xp', 0),
                        gold=getattr(task_data, 'rewards_gold', 0),
                        items=getattr(task_data, 'rewards_items', [])
                    )

                    priority = TaskPriority.MEDIUM
                    if hasattr(task_data, 'priority') and task_data.priority in [p.value for p in TaskPriority]:
                        priority = TaskPriority(task_data.priority)

                    task = Task(
                        code=task_data.code,
                        name=getattr(task_data, 'name', task_data.code),
                        task_type=task_type,
                        description=getattr(task_data, 'description', ''),
                        requirements=requirements,
                        rewards=rewards,
                        estimated_duration=getattr(task_data, 'duration', 30),
                        priority=priority
                    )
                    tasks.append(task)

                self.task_cache[character_name] = tasks
                self.last_cache_update = current_time

            except Exception:
                if character_name in self.task_cache:
                    return self.task_cache[character_name]
                return []

        return self.task_cache.get(character_name, [])

    async def get_character_tasks(self, character_name: str) -> list[TaskProgress]:
        """Get character's current active tasks.
        
        Parameters:
            character_name: Name of the character to retrieve active tasks for
            
        Return values:
            List of TaskProgress objects representing currently active tasks
            
        This method retrieves all active tasks for the specified character including
        progress tracking, completion status, and estimated completion times for
        planning and prioritization purposes.
        """
        try:
            character = await self.api_client.get_character(character_name)

            active_tasks = []

            if hasattr(character, 'task') and character.task:
                task_progress = TaskProgress(
                    task_code=character.task,
                    character_name=character_name,
                    progress=getattr(character, 'task_progress', 0),
                    target=getattr(character, 'task_total', 1),
                    completed=False,
                    started_at=datetime.now()
                )
                active_tasks.append(task_progress)

            self.active_tasks[character_name] = active_tasks
            return active_tasks

        except Exception:
            return self.active_tasks.get(character_name, [])

    def select_optimal_task(self, character_state: dict[GameState, Any],
                           available_tasks: list[Task]) -> Task | None:
        """Select the most optimal task for character progression.
        
        Parameters:
            character_state: Dictionary with GameState enum keys and current character state
            available_tasks: List of Task objects to choose from
            
        Return values:
            Task object representing the optimal choice, or None if no suitable task
            
        This method analyzes available tasks considering character state, efficiency
        scores, rewards, and progression goals to select the most beneficial task
        for current character development and AI player objectives.
        """
        suitable_tasks = [task for task in available_tasks if task.is_suitable_for_character(character_state)]

        if not suitable_tasks:
            return None

        prioritized_tasks = self.prioritize_tasks(suitable_tasks, character_state)

        return prioritized_tasks[0] if prioritized_tasks else None

    def prioritize_tasks(self, tasks: list[Task], character_state: dict[GameState, Any]) -> list[Task]:
        """Sort tasks by priority and efficiency"""
        def task_score(task: Task) -> float:
            efficiency = task.calculate_efficiency_score(character_state)

            priority_weight = {
                TaskPriority.EMERGENCY: 1000.0,
                TaskPriority.HIGH: 100.0,
                TaskPriority.MEDIUM: 10.0,
                TaskPriority.LOW: 1.0
            }.get(task.priority, 1.0)

            return efficiency * priority_weight

        return sorted(tasks, key=task_score, reverse=True)

    async def accept_task(self, character_name: str, task_code: str) -> bool:
        """Accept a new task via API"""
        try:
            response = await self.api_client.accept_task(character_name, task_code)
            return bool(response)
        except Exception:
            return False

    async def complete_task(self, character_name: str, task_code: str) -> bool:
        """Complete a task via API"""
        try:
            response = await self.api_client.complete_task(character_name)
            if response:
                self.completed_tasks.add(task_code)
                if character_name in self.active_tasks:
                    self.active_tasks[character_name] = [
                        task for task in self.active_tasks[character_name]
                        if task.task_code != task_code
                    ]
                return True
            return False
        except Exception:
            return False

    async def cancel_task(self, character_name: str, task_code: str) -> bool:
        """Cancel an active task via API"""
        try:
            response = await self.api_client.cancel_task(character_name)
            if response:
                if character_name in self.active_tasks:
                    self.active_tasks[character_name] = [
                        task for task in self.active_tasks[character_name]
                        if task.task_code != task_code
                    ]
                return True
            return False
        except Exception:
            return False

    def track_task_progress(self, character_name: str, task_code: str) -> TaskProgress:
        """Track progress on active task"""
        active_tasks = self.active_tasks.get(character_name, [])

        for task_progress in active_tasks:
            if task_progress.task_code == task_code:
                return task_progress

        return TaskProgress(
            task_code=task_code,
            character_name=character_name,
            progress=0,
            target=1,
            completed=False,
            started_at=datetime.now()
        )

    def update_task_progress(self, character_name: str, task_code: str,
                           progress: int) -> None:
        """Update task progress tracking"""
        if character_name not in self.active_tasks:
            self.active_tasks[character_name] = []

        for task_progress in self.active_tasks[character_name]:
            if task_progress.task_code == task_code:
                task_progress.progress = progress
                if progress >= task_progress.target:
                    task_progress.completed = True
                    current_time = datetime.now()
                    elapsed_time = current_time - task_progress.started_at
                    task_progress.estimated_completion = current_time
                return

        new_task_progress = TaskProgress(
            task_code=task_code,
            character_name=character_name,
            progress=progress,
            target=1,
            completed=progress >= 1,
            started_at=datetime.now()
        )
        self.active_tasks[character_name].append(new_task_progress)

    def is_task_completable(self, task_code: str, character_name: str, character_state: dict[GameState, Any]) -> bool:
        """Check if task can be completed with current character state"""
        task_progress = self.track_task_progress(character_name, task_code)
        if not task_progress.completed:
            return False

        for character_tasks in self.task_cache.values():
            for task in character_tasks:
                if task.code == task_code:
                    return task.requirements.can_satisfy(character_state)

        return True

    def get_task_requirements_actions(self, task: Task, character_state: dict[GameState, Any]) -> list[BaseAction]:
        """Generate actions needed to satisfy task requirements"""
        required_actions = []

        character_level = character_state.get(GameState.CHARACTER_LEVEL, 1)
        if character_level < task.requirements.min_level:
            # Would need combat/gathering actions to gain XP
            return []

        # Check for required items
        inventory = character_state.get('inventory', [])
        for required_item in task.requirements.required_items:
            item_code = required_item['code']
            required_quantity = required_item.get('quantity', 1)

            character_quantity = 0
            for inventory_item in inventory:
                if inventory_item.get('code') == item_code:
                    character_quantity += inventory_item.get('quantity', 0)

            if character_quantity < required_quantity:
                # Would need gathering/crafting/purchase actions
                return []

        # Check location requirement
        if task.requirements.required_location is not None:
            current_x = character_state.get(GameState.CURRENT_X, 0)
            current_y = character_state.get(GameState.CURRENT_Y, 0)
            required_x, required_y = task.requirements.required_location

            if current_x != required_x or current_y != required_y:
                # Would need movement action
                return []

        return required_actions

    def estimate_task_completion_time(self, task: Task, character_state: dict[GameState, Any]) -> int:
        """Estimate time to complete task in minutes"""
        base_time = task.estimated_duration
        character_level = character_state.get(GameState.CHARACTER_LEVEL, 1)

        # Apply level-based modifier
        level_modifier = max(0.5, min(2.0, character_level / task.requirements.min_level))
        adjusted_time = base_time / level_modifier

        # Apply task-specific modifiers
        if task.task_type == TaskType.KILL_MONSTERS:
            if character_state.get(GameState.HP_LOW, False):
                adjusted_time *= 1.5
            if character_state.get(GameState.COMBAT_ADVANTAGE, False):
                adjusted_time *= 0.8

        elif task.task_type == TaskType.GATHER_RESOURCES:
            tool_equipped = character_state.get(GameState.TOOL_EQUIPPED, False)
            if tool_equipped:
                adjusted_time *= 0.7

        elif task.task_type == TaskType.CRAFT_ITEMS:
            if character_state.get(GameState.HAS_CRAFTING_MATERIALS, False):
                adjusted_time *= 0.8

        # Add travel time if location required
        if task.requirements.required_location is not None:
            current_x = character_state.get(GameState.CURRENT_X, 0)
            current_y = character_state.get(GameState.CURRENT_Y, 0)
            required_x, required_y = task.requirements.required_location

            distance = abs(current_x - required_x) + abs(current_y - required_y)
            travel_time = distance * 0.5  # Assume 0.5 minutes per tile
            adjusted_time += travel_time

        return max(1, int(adjusted_time))

    def find_similar_tasks(self, task: Task, available_tasks: list[Task]) -> list[Task]:
        """Find tasks with similar objectives for efficient chaining"""
        similar_tasks = []

        for available_task in available_tasks:
            if available_task.code == task.code:
                continue

            # Same task type
            if available_task.task_type == task.task_type:
                similar_tasks.append(available_task)
                continue

            # Same location requirement
            if (task.requirements.required_location is not None and
                available_task.requirements.required_location == task.requirements.required_location):
                similar_tasks.append(available_task)
                continue

            # Similar level requirements
            level_diff = abs(available_task.requirements.min_level - task.requirements.min_level)
            if level_diff <= 5:
                similar_tasks.append(available_task)
                continue

            # Same required skills
            task_skills = set(task.requirements.required_skills.keys())
            available_skills = set(available_task.requirements.required_skills.keys())
            if task_skills.intersection(available_skills):
                similar_tasks.append(available_task)

        # Sort by similarity score (task type > location > level > skills)
        def similarity_score(similar_task: Task) -> int:
            score = 0
            if similar_task.task_type == task.task_type:
                score += 100
            if (task.requirements.required_location is not None and
                similar_task.requirements.required_location == task.requirements.required_location):
                score += 50
            level_diff = abs(similar_task.requirements.min_level - task.requirements.min_level)
            score += max(0, 25 - level_diff)

            task_skills = set(task.requirements.required_skills.keys())
            similar_skills = set(similar_task.requirements.required_skills.keys())
            score += len(task_skills.intersection(similar_skills)) * 10

            return score

        return sorted(similar_tasks, key=similarity_score, reverse=True)


class TaskGoalGenerator:
    """Generates GOAP goals based on active tasks"""

    def __init__(self, task_manager: TaskManager):
        self.task_manager = task_manager

    def generate_task_goals(self, character_name: str, character_state: dict[GameState, Any]) -> list[dict[GameState, Any]]:
        """Generate GOAP goals for active tasks"""
        return []

    def create_kill_monster_goal(self, task: Task, character_state: dict[GameState, Any]) -> dict[GameState, Any]:
        """Create goal for monster killing tasks"""
        return {}

    def create_gather_resource_goal(self, task: Task, character_state: dict[GameState, Any]) -> dict[GameState, Any]:
        """Create goal for resource gathering tasks"""
        return {}

    def create_craft_item_goal(self, task: Task, character_state: dict[GameState, Any]) -> dict[GameState, Any]:
        """Create goal for crafting tasks"""
        return {}

    def create_delivery_goal(self, task: Task, character_state: dict[GameState, Any]) -> dict[GameState, Any]:
        """Create goal for item delivery tasks"""
        return {}

    def create_trade_goal(self, task: Task, character_state: dict[GameState, Any]) -> dict[GameState, Any]:
        """Create goal for trading tasks"""
        return {}

    def prioritize_task_goals(self, goals: list[dict[GameState, Any]],
                             character_state: dict[GameState, Any]) -> list[dict[GameState, Any]]:
        """Prioritize task goals based on efficiency and requirements"""
        return goals


class TaskProgressTracker:
    """Tracks and analyzes task completion progress"""

    def __init__(self):
        self.progress_history = {}
        self.completion_rates = {}

    def record_task_start(self, character_name: str, task_code: str) -> None:
        """Record when task was started"""
        if character_name not in self.progress_history:
            self.progress_history[character_name] = {}
        self.progress_history[character_name][task_code] = datetime.now()

    def record_task_progress(self, character_name: str, task_code: str,
                           progress: int, timestamp: Any) -> None:
        """Record task progress update"""
        pass

    def record_task_completion(self, character_name: str, task_code: str,
                             completion_time: int, rewards: TaskReward) -> None:
        """Record task completion details"""
        if character_name not in self.completion_rates:
            self.completion_rates[character_name] = {}
        self.completion_rates[character_name][task_code] = completion_time

    def analyze_task_efficiency(self, task_code: str) -> dict[str, float]:
        """Analyze historical efficiency for task type"""
        return {"efficiency": 1.0, "success_rate": 1.0}

    def predict_completion_time(self, task_code: str, current_progress: int) -> int:
        """Predict remaining time based on historical data"""
        return max(1, 30 - current_progress)

    def get_task_statistics(self, character_name: str) -> dict[str, Any]:
        """Get comprehensive task statistics for character"""
        return {"completed_tasks": 0, "total_time": 0, "average_efficiency": 1.0}

    def identify_improvement_opportunities(self, character_name: str) -> list[str]:
        """Identify areas where task efficiency could be improved"""
        return []


class TaskOptimizer:
    """Optimizes task selection and execution strategies"""

    def __init__(self, task_manager: TaskManager, progress_tracker: TaskProgressTracker):
        self.task_manager = task_manager
        self.progress_tracker = progress_tracker

    def optimize_task_sequence(self, available_tasks: list[Task],
                              character_state: dict[GameState, Any]) -> list[Task]:
        """Optimize sequence of tasks for maximum efficiency"""
        return self.task_manager.prioritize_tasks(available_tasks, character_state)

    def find_task_chains(self, available_tasks: list[Task]) -> list[list[Task]]:
        """Find chains of related tasks that can be completed efficiently together"""
        chains = []
        for task in available_tasks:
            similar = self.task_manager.find_similar_tasks(task, available_tasks)
            if similar:
                chains.append([task] + similar[:2])  # Limit chain length to 3
        return chains

    def calculate_opportunity_cost(self, task: Task, alternative_tasks: list[Task],
                                  character_state: dict[GameState, Any]) -> float:
        """Calculate opportunity cost of choosing one task over others"""
        task_efficiency = task.calculate_efficiency_score(character_state)
        best_alternative = 0.0
        for alt_task in alternative_tasks:
            if alt_task.code != task.code:
                alt_efficiency = alt_task.calculate_efficiency_score(character_state)
                best_alternative = max(best_alternative, alt_efficiency)
        return max(0.0, best_alternative - task_efficiency)

    def suggest_preparation_actions(self, task: Task, character_state: dict[GameState, Any]) -> list[str]:
        """Suggest actions to prepare for optimal task execution"""
        suggestions = []
        if task.task_type == TaskType.GATHER_RESOURCES:
            if not character_state.get(GameState.TOOL_EQUIPPED, False):
                suggestions.append("Equip appropriate gathering tool")
        elif task.task_type == TaskType.KILL_MONSTERS:
            if character_state.get(GameState.HP_CURRENT, 100) < 50:
                suggestions.append("Rest to recover HP")
        return suggestions

    def evaluate_task_abandonment(self, active_tasks: list[TaskProgress],
                                 new_opportunities: list[Task]) -> list[str]:
        """Evaluate whether to abandon current tasks for better opportunities"""
        abandon_recommendations = []
        for task_progress in active_tasks:
            if task_progress.completion_percentage < 25:  # Less than 25% complete
                abandon_recommendations.append(f"Consider abandoning {task_progress.task_code} - low progress")
        return abandon_recommendations
