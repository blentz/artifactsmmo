"""
Craft Execution Goal Implementation

This module implements a specialized goal for executing crafting actions with proper
recipe validation and cooldown handling.
"""

from typing import Any

from ..state.character_game_state import CharacterGameState
from ..state.game_state import GameState
from src.game_data.game_data import GameData
from ..types.goap_models import GOAPTargetState
from .base_goal import BaseGoal
from .sub_goal_request import SubGoalRequest


class CraftExecutionGoal(BaseGoal):
    """Goal for executing crafting actions.

    This goal handles the final crafting action after materials are gathered and
    character is at the appropriate workshop location.
    """

    def __init__(self, recipe_code: str, workshop_type: str):
        """Initialize craft execution goal.

        Parameters:
            recipe_code: The code of the recipe to craft
            workshop_type: Type of workshop required (e.g., 'weaponcrafting')
        """
        self.recipe_code = recipe_code
        self.workshop_type = workshop_type

    def calculate_weight(self, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate goal weight based on crafting importance and execution feasibility.

        This method implements weighted scoring:
        - Necessity (40%): How critical completing the craft is
        - Readiness (30%): All prerequisites met
        - Value (20%): XP and item value
        - Stability (10%): Predictable crafting outcomes
        """
        self.validate_game_data(game_data)

        # Base weight for craft execution
        base_weight = 9.0  # Highest priority in crafting sequence

        # Calculate final weight based on conditions
        if character_state.at_workshop_location and character_state.has_crafting_materials:
            base_weight = 10.0  # Perfect conditions
        elif character_state.has_crafting_materials and not character_state.at_workshop_location:
            base_weight = 5.0  # Has materials but wrong location
        elif character_state.at_workshop_location and not character_state.has_crafting_materials:
            base_weight = 3.0  # Right location but no materials
        else:
            base_weight = 2.7  # Neither condition met

        # Reduce weight if skill level is borderline
        skill_level = self._get_character_skill_level(character_state, self.workshop_type)
        recipe = self._find_recipe(game_data)
        if recipe and skill_level < recipe.level_required:
            base_weight *= 0.7

        return min(10.0, base_weight)

    def get_target_state(self, character_state: CharacterGameState, game_data: GameData) -> GOAPTargetState:
        """Return GOAP target state for craft execution.

        This method defines the desired state conditions for successful crafting:
        1. Character must be at workshop
        2. Character must have all materials
        3. Character must have required skill level
        4. Character must gain XP and create item
        """
        self.validate_game_data(game_data)

        target_states = {
            GameState.AT_WORKSHOP_LOCATION: True,
            GameState.HAS_CRAFTING_MATERIALS: True,
            GameState.CRAFTING_MATERIALS_READY: True,
            GameState.CAN_CRAFT: True,
            GameState.COOLDOWN_READY: True,
            GameState.GAINED_XP: True,
            GameState.HAS_CRAFTED_ITEM: True,
            GameState.CRAFTING_COMPLETED: True,
            GameState.INVENTORY_SPACE_AVAILABLE: True,
        }

        return GOAPTargetState(
            target_states=target_states,
            priority=9,  # Highest priority once prerequisites are met
            timeout_seconds=60,  # 1 minute timeout for crafting action
        )

    def is_feasible(self, character_state: CharacterGameState, game_data: GameData) -> bool:
        """Check if crafting is feasible with current character state."""
        self.validate_game_data(game_data)

        # Level 1-2 characters should focus on simple XP-gaining activities, not complex crafting
        if character_state.level <= 2:
            return False

        # Must be at workshop
        if not character_state.at_workshop_location:
            return False

        # Must have materials
        if not character_state.has_crafting_materials:
            return False

        # Must have required skill level
        recipe = self._find_recipe(game_data)
        if not recipe:
            return False

        skill_level = self._get_character_skill_level(character_state, self.workshop_type)
        if skill_level < recipe.level_required - 1:  # Allow slightly lower level
            return False

        return True

    def get_progression_value(self, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate contribution to progression goals."""
        # Crafting completion has high progression value
        base_value = 0.8

        # Higher value if recipe gives good XP
        recipe = self._find_recipe(game_data)
        if recipe:
            skill_level = self._get_character_skill_level(character_state, self.workshop_type)
            level_difference = recipe.level_required - skill_level
            if 0 <= level_difference <= 2:
                base_value += 0.2

        return min(1.0, base_value)

    def estimate_error_risk(self, character_state: CharacterGameState) -> float:
        """Estimate crafting-specific error risk."""
        # Crafting generally has low error risk
        base_risk = 0.2

        # Increase risk if skill level is borderline
        skill_level = self._get_character_skill_level(character_state, self.workshop_type)
        if skill_level < 3:
            base_risk += 0.2

        return min(1.0, base_risk)

    def generate_sub_goal_requests(
        self, character_state: CharacterGameState, game_data: GameData
    ) -> list["SubGoalRequest"]:
        """Generate sub-goal requests for crafting dependencies.

        Craft execution is a leaf goal and doesn't generate sub-goals.
        """
        return []

    def _find_recipe(self, game_data: GameData) -> Any | None:
        """Find recipe details in game data."""
        for item in game_data.items:
            if item.code == self.recipe_code:
                return item
        return None

    def _get_character_skill_level(self, character_state: CharacterGameState, skill_name: str) -> int:
        """Get character's skill level for the specified skill."""
        skill_mapping = {
            "weaponcrafting": character_state.weaponcrafting_level,
            "gearcrafting": character_state.gearcrafting_level,
            "jewelrycrafting": character_state.jewelrycrafting_level,
        }

        return skill_mapping.get(skill_name.lower(), 1)
