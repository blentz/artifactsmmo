"""
Cooldown-Aware GOAP Planner

This module extends the basic Planner with cooldown timing awareness,
enabling planning that considers character cooldown timing constraints
for realistic action sequencing.
"""

from datetime import datetime, timedelta
from typing import Any

from ..lib.goap import Action_List, Planner


class CooldownAwarePlanner(Planner):
    """Extended GOAP planner with cooldown timing awareness"""

    def __init__(self, cooldown_manager, *args, **kwargs):
        """Initialize CooldownAwarePlanner with cooldown management.
        
        Parameters:
            cooldown_manager: CooldownManager instance for timing constraint validation
            *args: Additional arguments passed to parent Planner constructor
            **kwargs: Additional keyword arguments passed to parent Planner constructor
            
        Return values:
            None (constructor)
            
        This constructor initializes the extended GOAP planner with cooldown
        awareness capabilities, enabling planning that considers character
        cooldown timing constraints for realistic action sequencing.
        """
        super().__init__(*args, **kwargs)
        self.cooldown_manager = cooldown_manager

    def calculate_with_timing_constraints(self, character_name: str) -> list[dict[str, Any]]:
        """Generate plan considering current cooldown state.
        
        Parameters:
            character_name: Name of the character for cooldown-aware planning
            
        Return values:
            List of action dictionaries with optimal timing considering cooldowns
            
        This method generates GOAP plans that account for character cooldown
        status, optimizing action timing and preventing invalid plans that
        would fail due to cooldown constraints in the AI player system.
        """
        try:
            # If character is on cooldown, return empty plan
            if not self.cooldown_manager.is_ready(character_name):
                return []

            # Use standard calculation if character is ready
            return self.calculate()
        except Exception:
            return []

    def filter_actions_by_cooldown(self, actions: Action_List, character_name: str) -> Action_List:
        """Filter out actions that require character to be off cooldown when character is on cooldown.
        
        Parameters:
            actions: Action_List containing all possible actions
            character_name: Name of the character to check cooldown status
            
        Return values:
            Action_List with cooldown-incompatible actions removed
            
        This method filters the available action list to remove actions that
        require cooldown readiness when the character is currently on cooldown,
        preventing invalid planning attempts in the GOAP system.
        """
        # If character is ready, return all actions
        if self.cooldown_manager.is_ready(character_name):
            return actions

        # Filter out actions that require cooldown readiness
        filtered_actions = Action_List()

        for action_name in actions.conditions.keys():
            conditions = actions.conditions[action_name]

            # If action requires cooldown readiness, skip it
            if conditions.get("cooldown_ready", False):
                continue

            # Add action to filtered list
            filtered_actions.add_condition(action_name, **conditions)
            filtered_actions.add_reaction(action_name, **actions.reactions[action_name])
            filtered_actions.set_weight(action_name, actions.weights[action_name])

        return filtered_actions

    def estimate_plan_duration(self, plan: list[dict[str, Any]]) -> timedelta:
        """Estimate total time to execute plan including cooldowns.
        
        Parameters:
            plan: List of action dictionaries representing the planned sequence
            
        Return values:
            Timedelta representing estimated total execution time
            
        This method calculates the expected time required to execute a complete
        action plan including individual action cooldowns and sequencing timing,
        enabling accurate planning and scheduling in the AI player system.
        """
        total_seconds = 0

        for action in plan:
            # Basic action execution time (varies by action type)
            action_name = action.get('name', '')
            if 'move' in action_name.lower():
                total_seconds += 5  # Movement actions
            elif 'fight' in action_name.lower():
                total_seconds += 10  # Combat actions
            elif 'gather' in action_name.lower():
                total_seconds += 8  # Gathering actions
            else:
                total_seconds += 3  # Default action time

            # Add cooldown time
            total_seconds += 1  # Standard cooldown

        return timedelta(seconds=total_seconds)

    def defer_planning_until_ready(self, character_name: str) -> datetime | None:
        """Return when planning should be deferred until character is off cooldown.
        
        Parameters:
            character_name: Name of the character to check cooldown deferral timing
            
        Return values:
            Datetime when planning can resume, or None if character is ready now
            
        This method determines if GOAP planning should be deferred due to character
        cooldown status, returning the specific time when planning can safely resume
        to avoid generating invalid action plans.
        """
        if self.cooldown_manager.is_ready(character_name):
            return None

        # Get remaining cooldown time in seconds
        remaining_seconds = self.cooldown_manager.get_remaining_time(character_name)

        # Calculate when the character will be ready
        ready_time = datetime.now() + timedelta(seconds=remaining_seconds)

        return ready_time