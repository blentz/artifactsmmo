"""
Task Data Models

Pydantic models for task data that align with TaskSchema and related models
from the artifactsmmo-api-client. Provides type safety and validation while
maintaining exact field name compatibility.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TaskReward(BaseModel):
    """Task reward data aligned with reward schemas"""
    model_config = ConfigDict(validate_assignment=True)

    code: str  # Item code or 'gold'
    quantity: int = Field(ge=1)


class Task(BaseModel):
    """Task model aligned with artifactsmmo-api-client TaskSchema"""
    model_config = ConfigDict(validate_assignment=True)

    # Basic task info - exact field names from API
    code: str  # Unique identifier
    type: str  # Task type (monsters, items, etc.)
    total: int = Field(ge=1)  # Total required for completion

    # Optional task data
    skill: str | None = None  # Required skill
    level: int | None = None  # Required level
    items: list[dict[str, Any]] | None = None  # Required items
    rewards: list[TaskReward] | None = None  # Task rewards

    @classmethod
    def from_api_task(cls, api_task: Any) -> "Task":
        """Create Task from API TaskSchema

        Args:
            api_task: TaskSchema instance from artifactsmmo-api-client

        Returns:
            Task instance with all fields mapped from API response
        """
        # Map rewards if present
        rewards = None
        if hasattr(api_task, 'rewards') and api_task.rewards:
            rewards = [
                TaskReward(
                    code=reward.code,
                    quantity=reward.quantity
                )
                for reward in api_task.rewards
            ]

        return cls(
            code=api_task.code,
            type=api_task.type,
            total=api_task.total,
            skill=getattr(api_task, 'skill', None),
            level=getattr(api_task, 'level', None),
            items=getattr(api_task, 'items', None),
            rewards=rewards,
        )

    @property
    def is_combat_task(self) -> bool:
        """Check if task involves combat/monsters"""
        return self.type.lower() == "monsters"

    @property
    def is_gathering_task(self) -> bool:
        """Check if task involves gathering/items"""
        return self.type.lower() == "items"

    @property
    def has_skill_requirement(self) -> bool:
        """Check if task has skill requirement"""
        return self.skill is not None

    @property
    def has_level_requirement(self) -> bool:
        """Check if task has level requirement"""
        return self.level is not None

    @property
    def has_item_requirements(self) -> bool:
        """Check if task has item requirements"""
        return self.items is not None and len(self.items) > 0

    @property
    def has_rewards(self) -> bool:
        """Check if task has rewards"""
        return self.rewards is not None and len(self.rewards) > 0

    def can_complete_with_character(self, character: Any) -> bool:
        """Check if character meets task requirements

        Args:
            character: Character instance to check against

        Returns:
            True if character meets all task requirements
        """
        # Check level requirement
        if self.has_level_requirement:
            if hasattr(character, 'level') and character.level < self.level:
                return False

        # Check skill requirement
        if self.has_skill_requirement and self.skill is not None:
            skill_level_attr = f"{self.skill.lower()}_level"
            if hasattr(character, skill_level_attr):
                skill_level = getattr(character, skill_level_attr)
                if self.level and skill_level < self.level:
                    return False

        return True

    def get_gold_reward(self) -> int:
        """Get total gold reward from task

        Returns:
            Total gold reward amount
        """
        if not self.has_rewards or self.rewards is None:
            return 0

        total_gold = 0
        for reward in self.rewards:
            if reward.code.lower() == "gold":
                total_gold += reward.quantity

        return total_gold

    def get_item_rewards(self) -> list[TaskReward]:
        """Get item rewards (non-gold) from task

        Returns:
            List of item rewards
        """
        if not self.has_rewards or self.rewards is None:
            return []

        return [reward for reward in self.rewards if reward.code.lower() != "gold"]
