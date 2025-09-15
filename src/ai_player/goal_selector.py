"""
Weighted Goal Selection System

This module implements the intelligent goal selection system that orchestrates
multiple specialized goals using weighted scoring to select optimal goals for
character progression toward level 5 with appropriate gear.
"""

import logging

from .goals.base_goal import BaseGoal
from .goals.combat_goal import CombatGoal
from .goals.crafting_goal import CraftingGoal
from .goals.equipment_goal import EquipmentGoal
from .goals.gathering_goal import GatheringGoal
from .goals.rest_goal import RestGoal
from .goals.sub_goal_request import SubGoalRequest
from .state.character_game_state import CharacterGameState
from src.game_data.game_data import GameData


class GoalWeightCalculator:
    """Advanced goal selection system using weighted multi-factor scoring.

    This class implements the PRP requirement for weighted goal selection with:
    - Multi-factor weight calculation (necessity, feasibility, progression, stability)
    - Dynamic priority adjustment based on character state
    - Goal feasibility validation with real game data
    - Strategic goal orchestration for level 5 progression
    """

    def __init__(self):
        """Initialize the goal weight calculator with all specialized goals."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.goals = [CombatGoal(), CraftingGoal(), GatheringGoal(), EquipmentGoal(), RestGoal()]

        # Track goal selection history for adaptation
        self.selection_history = []
        self.performance_metrics = {}

    def calculate_final_weight(self, goal: BaseGoal, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate final weight for a goal using multi-factor scoring.

        Parameters:
            goal: The goal to evaluate
            character_state: Current character state
            game_data: Complete game data from cache

        Return values:
            Float weight score (0.0 to 10.0) indicating goal priority

        This method implements the PRP-specified multi-factor calculation:
        - Necessity (40%): Required for progression (HP critical, missing gear, level blocks)
        - Feasibility (30%): Can be accomplished with current resources/state
        - Progression Value (20%): Contributes to reaching level 5 with appropriate gear
        - Stability (10%): Reduces error potential and maintains steady progress
        """
        try:
            # Use the goal's own calculate_weight method which implements the multi-factor formula
            base_weight = goal.calculate_weight(character_state, game_data)

            # Apply dynamic adjustments based on context
            adjusted_weight = self._apply_dynamic_adjustments(goal, base_weight, character_state, game_data)

            return min(10.0, adjusted_weight)

        except (AttributeError, TypeError) as e:
            # Handle component errors - missing methods or wrong types
            print(f"Component error calculating weight for {type(goal).__name__}: {e}")
            return 0.1
        except ValueError as e:
            # Handle data validation errors
            print(f"Invalid data calculating weight for {type(goal).__name__}: {e}")
            return 0.1

    def select_optimal_goal(
        self, character_state: CharacterGameState, game_data: GameData
    ) -> tuple[BaseGoal | None, list[SubGoalRequest]]:
        """Select the optimal goal using weighted scoring and feasibility validation.

        Parameters:
            character_state: Current character state
            game_data: Complete game data from cache

        Return values:
            Tuple of (selected_goal, sub_goal_requests) or (None, []) if no feasible goals

        This method evaluates all available goals, calculates their weights,
        validates feasibility, and selects the highest-priority achievable goal
        while also collecting any sub-goal requests for dependency resolution.
        """
        if not game_data:
            self.logger.warning("No game data available for goal selection")
            return None, []

        # Log character state for debugging
        self.logger.debug("Character state for goal selection:")
        self.logger.debug(f"  - Level: {character_state.level}")
        self.logger.debug(f"  - Position: ({character_state.x}, {character_state.y})")
        self.logger.debug(f"  - HP: {character_state.hp}/{character_state.max_hp}")
        self.logger.debug(f"  - Gold: {character_state.gold}")
        self.logger.debug(f"  - Inventory space used: {character_state.inventory_space_used}")

        # Evaluate all goals
        scored_goals = []
        all_sub_goal_requests = []

        for goal in self.goals:
            # Check feasibility first
            goal_name = type(goal).__name__
            self.logger.debug(f"Evaluating goal: {goal_name}")
            feasible = goal.is_feasible(character_state, game_data)
            self.logger.debug(f"  - Feasibility check for {goal_name}: {feasible}")
            if not feasible:
                self.logger.debug(f"  - {goal_name} rejected as not feasible")
                continue

            # Calculate weight
            weight = self.calculate_final_weight(goal, character_state, game_data)
            self.logger.debug(f"  - Weight for {goal_name}: {weight}")

            if weight > 0.1:  # Only consider goals with meaningful weight
                scored_goals.append((goal, weight))

                # Collect sub-goal requests for this goal
                if hasattr(goal, "generate_sub_goal_requests"):
                    sub_goals = goal.generate_sub_goal_requests(character_state, game_data)
                    all_sub_goal_requests.extend(sub_goals)

        if not scored_goals:
            self.logger.warning("No feasible goals found")
            return None, all_sub_goal_requests

        # Sort by weight (highest first)
        scored_goals.sort(key=lambda x: x[1], reverse=True)

        # Select the highest weighted goal
        selected_goal, final_weight = scored_goals[0]
        self.logger.debug(f"Selected goal: {type(selected_goal).__name__} with weight {final_weight}")

        # Record selection for adaptation
        self._record_goal_selection(selected_goal, final_weight, character_state)

        # Filter sub-goal requests for the selected goal
        selected_goal_type = type(selected_goal).__name__
        relevant_sub_goals = [
            sg for sg in all_sub_goal_requests if sg.requester == selected_goal_type.replace("Goal", "Goal")
        ]

        return selected_goal, relevant_sub_goals

    def get_goal_priorities(
        self, character_state: CharacterGameState, game_data: GameData
    ) -> list[tuple[str, float, bool]]:
        """Get priority scores for all goals for diagnostics and monitoring.

        Parameters:
            character_state: Current character state
            game_data: Complete game data from cache

        Return values:
            List of (goal_name, weight, is_feasible) tuples sorted by weight

        This method provides visibility into the goal selection process for
        debugging, monitoring, and user feedback about AI decision making.
        """
        goal_priorities = []

        for goal in self.goals:
            try:
                goal_name = type(goal).__name__
                is_feasible = goal.is_feasible(character_state, game_data)

                if is_feasible:
                    weight = self.calculate_final_weight(goal, character_state, game_data)
                else:
                    weight = 0.0

                goal_priorities.append((goal_name, weight, is_feasible))

            except (AttributeError, TypeError) as e:
                print(f"Component error getting priority for {type(goal).__name__}: {e}")
                goal_priorities.append((type(goal).__name__, 0.0, False))
            except ValueError as e:
                print(f"Invalid data getting priority for {type(goal).__name__}: {e}")
                goal_priorities.append((type(goal).__name__, 0.0, False))

        # Sort by weight (highest first)
        goal_priorities.sort(key=lambda x: x[1], reverse=True)

        return goal_priorities

    def update_goal_performance(self, goal: BaseGoal, success: bool, progress_made: float = 0.0) -> None:
        """Update performance metrics for goal adaptation.

        Parameters:
            goal: The goal that was executed
            success: Whether the goal execution was successful
            progress_made: Amount of progress made (0.0 to 1.0)

        This method tracks goal performance to enable adaptive improvements
        in goal selection and weighting over time.
        """
        goal_name = type(goal).__name__

        if goal_name not in self.performance_metrics:
            self.performance_metrics[goal_name] = {
                "successes": 0,
                "attempts": 0,
                "total_progress": 0.0,
                "avg_progress": 0.0,
            }

        metrics = self.performance_metrics[goal_name]
        metrics["attempts"] += 1

        if success:
            metrics["successes"] += 1

        metrics["total_progress"] += progress_made
        metrics["avg_progress"] = metrics["total_progress"] / metrics["attempts"]

    def _apply_dynamic_adjustments(
        self, goal: BaseGoal, base_weight: float, character_state: CharacterGameState, game_data: GameData
    ) -> float:
        """Apply dynamic adjustments to goal weights based on context."""
        adjusted_weight = base_weight

        # Emergency adjustments for critical situations
        if self._is_emergency_situation(character_state):
            adjusted_weight = self._apply_emergency_adjustments(goal, adjusted_weight, character_state)

        # Performance-based adjustments
        goal_name = type(goal).__name__
        if goal_name in self.performance_metrics:
            performance_factor = self._calculate_performance_factor(goal_name)
            adjusted_weight *= performance_factor

        # Situational context adjustments
        adjusted_weight = self._apply_situational_adjustments(goal, adjusted_weight, character_state)

        return adjusted_weight

    def _is_emergency_situation(self, character_state: CharacterGameState) -> bool:
        """Check if character is in an emergency situation requiring priority adjustment."""
        # Critical HP
        if character_state.hp < character_state.max_hp * 0.2:
            return True

        # No equipment at higher levels
        if character_state.level >= 3 and not character_state.weapon_slot:
            return True

        return False

    def _apply_emergency_adjustments(self, goal: BaseGoal, weight: float, character_state: CharacterGameState) -> float:
        """Apply emergency priority adjustments."""
        goal_type = type(goal).__name__

        # Boost equipment goals if severely undergeared
        if goal_type == "EquipmentGoal" and character_state.level >= 3 and not character_state.weapon_slot:
            return weight * 2.0

        # Prioritize gathering/crafting for emergency equipment
        if goal_type in ["GatheringGoal", "CraftingGoal"] and character_state.level >= 3:
            return weight * 1.5

        # Reduce combat priority if HP is critical
        if goal_type == "CombatGoal" and character_state.hp < character_state.max_hp * 0.2:
            return weight * 0.3

        return weight

    def _calculate_performance_factor(self, goal_name: str) -> float:
        """Calculate performance adjustment factor for a goal."""
        metrics = self.performance_metrics[goal_name]

        if metrics["attempts"] < 3:
            return 1.0  # Not enough data for adjustment

        success_rate = metrics["successes"] / metrics["attempts"]
        avg_progress = metrics["avg_progress"]

        # Boost well-performing goals, reduce poorly performing ones
        performance_score = (success_rate * 0.6) + (avg_progress * 0.4)

        # Convert to multiplier (0.7 to 1.3 range)
        return 0.7 + (performance_score * 0.6)

    def _apply_situational_adjustments(
        self, goal: BaseGoal, weight: float, character_state: CharacterGameState
    ) -> float:
        """Apply situational context adjustments."""
        goal_type = type(goal).__name__

        # Boost progression-focused goals when close to level 5
        if character_state.level >= 4:
            if goal_type in ["CombatGoal", "EquipmentGoal"]:
                weight *= 1.2

        # For Level 1-2 characters: Focus on simple XP-gaining activities
        if character_state.level <= 2:
            # Heavily boost simple XP-gaining goals
            if goal_type in ["CombatGoal", "GatheringGoal"]:
                weight *= 3.0  # Significantly boost simple XP goals
            # Severely penalize complex crafting goals for low-level characters
            elif goal_type in ["CraftingGoal", "CraftExecutionGoal", "WorkshopMovementGoal"]:
                weight *= 0.1  # Nearly eliminate complex crafting goals for Level 1-2
            # Moderate boost for equipment goals (basic gear)
            elif goal_type == "EquipmentGoal":
                weight *= 1.5  # Still useful for basic equipment

        # For Level 3+: Allow more complex goals
        elif character_state.level >= 3:
            # Boost foundational goals for mid-level characters
            if goal_type in ["GatheringGoal", "CraftingGoal"]:
                weight *= 1.1

        return weight

    def _record_goal_selection(self, goal: BaseGoal, weight: float, character_state: CharacterGameState) -> None:
        """Record goal selection for historical analysis."""
        selection_record = {
            "goal_type": type(goal).__name__,
            "weight": weight,
            "character_level": character_state.level,
            "character_hp_ratio": character_state.hp / max(1, character_state.max_hp),
            "timestamp": None,  # Would use datetime in full implementation
        }

        self.selection_history.append(selection_record)

        # Keep only recent history
        if len(self.selection_history) > 100:
            self.selection_history = self.selection_history[-100:]
