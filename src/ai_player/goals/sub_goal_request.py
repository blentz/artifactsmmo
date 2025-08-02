"""
Sub-Goal Request System

This module implements the sub-goal request architecture that allows actions to
dynamically request dependencies at runtime, enabling natural goal chain resolution
without pre-planning all possible scenarios.
"""

from typing import Any

from pydantic import BaseModel, Field


class SubGoalRequest(BaseModel):
    """Request for a sub-goal to be dynamically created and pursued.

    This model represents a dependency that was discovered at runtime during
    action execution. Instead of failing, actions can return sub-goal requests
    that the GoalManager will incorporate into planning to resolve dependencies.
    """

    goal_type: str = Field(description="Type of sub-goal needed")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Specific requirements for the sub-goal")
    priority: int = Field(ge=1, le=10, description="Urgency level (1-10, higher is more urgent)")
    requester: str = Field(description="Identifier of the action/goal that requested this")
    reason: str = Field(description="Human-readable explanation of why this sub-goal is needed")

    @classmethod
    def move_to_location(
        cls, target_x: int, target_y: int, requester: str, reason: str = "Movement required"
    ) -> 'SubGoalRequest':
        """Create a movement sub-goal request.

        Parameters:
            target_x: Target X coordinate
            target_y: Target Y coordinate
            requester: Action/goal requesting the movement
            reason: Why movement is needed

        Return values:
            SubGoalRequest for movement to specified location
        """
        return cls(
            goal_type="move_to_location",
            parameters={"target_x": target_x, "target_y": target_y},
            priority=7,
            requester=requester,
            reason=reason
        )

    @classmethod
    def obtain_item(
        cls, item_code: str, quantity: int, requester: str, reason: str = "Item required"
    ) -> 'SubGoalRequest':
        """Create an item acquisition sub-goal request.

        Parameters:
            item_code: Code of the item needed
            quantity: Number of items needed
            requester: Action/goal requesting the item
            reason: Why the item is needed

        Return values:
            SubGoalRequest for obtaining the specified item
        """
        return cls(
            goal_type="obtain_item",
            parameters={"item_code": item_code, "quantity": quantity},
            priority=8,
            requester=requester,
            reason=reason
        )

    @classmethod
    def reach_hp_threshold(
        cls, min_hp_percentage: float, requester: str, reason: str = "HP recovery needed"
    ) -> 'SubGoalRequest':
        """Create an HP recovery sub-goal request.

        Parameters:
            min_hp_percentage: Minimum HP percentage needed (0.0 to 1.0)
            requester: Action/goal requesting HP recovery
            reason: Why HP recovery is needed

        Return values:
            SubGoalRequest for HP recovery to specified threshold
        """
        return cls(
            goal_type="reach_hp_threshold",
            parameters={"min_hp_percentage": min_hp_percentage},
            priority=9,  # High priority for survival
            requester=requester,
            reason=reason
        )

    @classmethod
    def equip_item_type(
        cls, item_type: str, max_level: int, requester: str,
        reason: str = "Equipment upgrade needed"
    ) -> 'SubGoalRequest':
        """Create an equipment upgrade sub-goal request.

        Parameters:
            item_type: Type of equipment needed (weapon, helmet, etc.)
            max_level: Maximum item level acceptable
            requester: Action/goal requesting the equipment
            reason: Why the equipment is needed

        Return values:
            SubGoalRequest for equipping specified item type
        """
        return cls(
            goal_type="equip_item_type",
            parameters={"item_type": item_type, "max_level": max_level},
            priority=6,
            requester=requester,
            reason=reason
        )
