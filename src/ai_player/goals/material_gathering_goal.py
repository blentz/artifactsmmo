"""
Material Gathering Goal Implementation

This module implements a specialized goal for gathering specific crafting materials
with quantity tracking and proper cooldown handling.
"""

from typing import Any

from ..state.character_game_state import CharacterGameState
from ..state.game_state import GameState
from src.game_data.game_data import GameData
from ..types.goap_models import GOAPTargetState
from .base_goal import BaseGoal
from .sub_goal_request import SubGoalRequest


class MaterialGatheringGoal(BaseGoal):
    """Goal for gathering specific crafting materials with quantity tracking.

    This goal handles gathering individual materials needed for crafting recipes,
    with proper quantity tracking and cooldown management between gathering actions.
    """

    def __init__(self, material_code: str, quantity: int):
        """Initialize material gathering goal.

        Parameters:
            material_code: The code of the material to gather
            quantity: The required quantity of the material
        """
        self.material_code = material_code
        self.quantity = quantity

    def calculate_weight(self, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate goal weight based on material importance and gathering feasibility.

        This method implements weighted scoring:
        - Necessity (40%): How critical the material is for crafting
        - Feasibility (30%): Character's ability to gather the material
        - Efficiency (20%): Resource availability and location
        - Stability (10%): Predictable gathering outcomes
        """
        self.validate_game_data(game_data)

        # Base weight for material gathering
        base_weight = 8.0  # High priority for crafting dependencies

        # Find closest resource location
        current_pos = (character_state.x, character_state.y)
        min_distance = float("inf")
        resource_locations = self._find_resource_locations(game_data)
        if resource_locations:
            for location in resource_locations:
                distance = abs(location.x - current_pos[0]) + abs(location.y - current_pos[1])
                min_distance = min(min_distance, distance)

            # Adjust weight based on distance to resource
            if min_distance == 0:  # At resource location
                base_weight = 10.0  # At resource location
            elif min_distance == 1:  # Adjacent to resource
                base_weight = 9.0  # Next to resource
            else:
                base_weight = 8.0  # Further away

        # Check if we're at a monster location that drops this material
        for resource in game_data.resources:
            for drop in resource.drops:
                if drop.code == self.material_code:
                    # Check if we're at a location with this monster
                    for map_data in game_data.maps:
                        if (
                            map_data.content
                            and map_data.content.type == "monster"
                            and map_data.x == character_state.x
                            and map_data.y == character_state.y
                        ):
                            base_weight = 9.0  # At monster location that drops material
                            break

        # Reduce weight if character lacks required skills
        for resource in game_data.resources:
            for drop in resource.drops:
                if drop.code == self.material_code:
                    skill_level = self._get_character_skill_level(character_state, resource.skill)
                    if skill_level < resource.level:
                        base_weight *= 0.5
                    break

        return min(10.0, base_weight)

    def get_target_state(self, character_state: CharacterGameState, game_data: GameData) -> GOAPTargetState:
        """Return GOAP target state for material gathering.

        This method defines the desired state conditions for successful gathering:
        1. Character must be at resource location
        2. Character must have required gathering skills
        3. Character must have inventory space
        4. Character must obtain required quantity of materials
        """
        self.validate_game_data(game_data)

        # Convert material code to uppercase for state enum
        material_state_key = f"HAS_MATERIAL_{self.material_code.upper()}"
        inventory_state_key = f"INVENTORY_CONTAINS_{self.material_code.upper()}"

        # Get corresponding GameState enum values
        has_material_state = getattr(GameState, material_state_key)
        inventory_contains_state = getattr(GameState, inventory_state_key)

        target_states = {
            GameState.AT_RESOURCE_LOCATION: True,
            GameState.RESOURCE_AVAILABLE: True,
            GameState.CAN_GATHER: True,
            GameState.COOLDOWN_READY: True,
            GameState.INVENTORY_SPACE_AVAILABLE: True,
            has_material_state: True,
            inventory_contains_state: self.quantity,
            GameState.MATERIAL_GATHERING_IN_PROGRESS: True,
        }

        return GOAPTargetState(
            target_states=target_states,
            priority=8,  # High priority for crafting dependencies
            timeout_seconds=300,  # 5 minute timeout for gathering
        )

    def is_feasible(self, character_state: CharacterGameState, game_data: GameData) -> bool:
        """Check if material gathering is feasible with current character state."""
        self.validate_game_data(game_data)

        # Check if resource exists and is accessible
        resource_locations = self._find_resource_locations(game_data)
        if not resource_locations:
            return False

        # Check if character has required skills
        for resource in game_data.resources:
            for drop in resource.drops:
                if drop.code == self.material_code:
                    skill_level = self._get_character_skill_level(character_state, resource.skill)
                    if skill_level >= resource.level - 1:  # Allow slightly lower level
                        return True
                    break

        return False

    def get_progression_value(self, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate contribution to progression goals."""
        # Material gathering contributes indirectly through crafting
        return 0.4  # Moderate progression value

    def estimate_error_risk(self, character_state: CharacterGameState) -> float:
        """Estimate gathering-specific error risk."""
        # Gathering generally has low error risk
        return 0.2

    def generate_sub_goal_requests(
        self, character_state: CharacterGameState, game_data: GameData
    ) -> list["SubGoalRequest"]:
        """Generate sub-goal requests for gathering dependencies.

        Material gathering is a leaf goal and doesn't generate sub-goals.
        """
        return []

    def _find_resource_locations(self, game_data: GameData) -> list[Any]:
        """Find locations where the required material can be gathered."""
        resource_locations = []
        for resource in game_data.resources:
            for drop in resource.drops:
                if drop.code == self.material_code:
                    # Find all locations of this resource type
                    locations = [
                        map_data
                        for map_data in game_data.maps
                        if map_data.content
                        and map_data.content.type == "resource"
                        and map_data.content.code == resource.code
                    ]
                    resource_locations.extend(locations)
        return resource_locations

    def _get_character_skill_level(self, character_state: CharacterGameState, skill_name: str) -> int:
        """Get character's skill level for the specified skill."""
        skill_mapping = {
            "mining": character_state.mining_level,
            "woodcutting": character_state.woodcutting_level,
            "fishing": character_state.fishing_level,
            "weaponcrafting": character_state.weaponcrafting_level,
            "gearcrafting": character_state.gearcrafting_level,
            "jewelrycrafting": character_state.jewelrycrafting_level,
            "cooking": character_state.cooking_level,
            "alchemy": character_state.alchemy_level,
        }

        return skill_mapping.get(skill_name.lower(), 1)
