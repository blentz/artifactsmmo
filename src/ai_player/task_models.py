"""
Task Models

This module contains all the data structures and enums used throughout
the task management system for the AI player.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

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
