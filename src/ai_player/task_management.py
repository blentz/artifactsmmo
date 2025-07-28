"""
Task Management

This module contains the main TaskManager class for coordinating task
discovery, tracking, and completion management.
"""

from datetime import datetime, timedelta
from typing import Any

from .state.game_state import GameState
from .task_models import Task, TaskProgress, TaskType, TaskPriority, TaskRequirement, TaskReward


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
        """Prioritize tasks based on efficiency and character needs"""
        return sorted(tasks, key=lambda t: t.calculate_efficiency_score(character_state), reverse=True)

    async def accept_task(self, character_name: str, task_code: str) -> bool:
        """Accept a task for the character"""
        try:
            response = await self.api_client.action_accept_new_task(character_name, code=task_code)
            return bool(response and hasattr(response, 'data') and response.data)
        except Exception:
            return False

    async def complete_task(self, character_name: str) -> bool:
        """Complete current task for the character"""
        try:
            response = await self.api_client.action_complete_task(character_name)
            if response and hasattr(response, 'data') and response.data:
                self.completed_tasks.add(f"{character_name}:current_task")
                return True
            return False
        except Exception:
            return False

    async def exchange_task(self, character_name: str) -> bool:
        """Exchange current task for a new random one"""
        try:
            response = await self.api_client.action_task_exchange(character_name)
            return bool(response and hasattr(response, 'data') and response.data)
        except Exception:
            return False

    def get_task_recommendations(self, character_state: dict[GameState, Any]) -> list[str]:
        """Get task recommendations based on character state"""
        recommendations = []

        character_level = character_state.get(GameState.CHARACTER_LEVEL, 1)
        hp_low = character_state.get(GameState.HP_LOW, False)
        inventory_full = character_state.get(GameState.INVENTORY_FULL, False)

        if hp_low:
            recommendations.append("Consider healing before accepting combat tasks")
        
        if inventory_full:
            recommendations.append("Clear inventory space before accepting gathering tasks")

        if character_level < 5:
            recommendations.append("Focus on basic resource gathering and simple combat tasks")
        elif character_level < 15:
            recommendations.append("Balance combat and crafting tasks for efficient progression")
        else:
            recommendations.append("Consider high-reward tasks and economic activities")

        return recommendations

    def is_item_needed_for_tasks(self, item_code: str, character_name: str) -> bool:
        """Check if item is needed for any active or available tasks"""
        # Check active tasks
        active_tasks = self.active_tasks.get(character_name, [])
        
        # Check available tasks from cache
        available_tasks = self.task_cache.get(character_name, [])
        
        for task in available_tasks:
            for required_item in task.requirements.required_items:
                if required_item.get('code') == item_code:
                    return True
        
        return False