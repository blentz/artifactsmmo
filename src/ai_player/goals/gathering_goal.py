"""
Gathering Goal Implementation

This module implements intelligent resource gathering goal selection that collects
materials needed for crafting progression using data-driven resource analysis and
optimal location selection without hardcoded resource locations or values.
"""

from typing import Any

from src.game_data.models import GameMap, GameResource

from ..analysis.crafting_analysis import CraftingAnalysisModule
from ..analysis.map_analysis import MapAnalysisModule
from ..state.character_game_state import CharacterGameState
from ..state.game_state import GameState
from ..types.game_data import GameData
from ..types.goap_models import GOAPTargetState
from .base_goal import BaseGoal
from .sub_goal_request import SubGoalRequest


class GatheringGoal(BaseGoal):
    """Intelligent gathering goal for material collection and resource optimization.

    This goal implements strategic resource gathering using data-driven analysis
    to collect materials needed for crafting progression toward level 5, with
    optimal location selection and skill-based resource targeting.
    """

    def __init__(self, target_resource_code: str | None = None, target_material_code: str | None = None):
        """Initialize gathering goal with optional target specification.

        Parameters:
            target_resource_code: Optional specific resource code to gather from
            target_material_code: Optional specific material code to collect
        """
        self.target_resource_code = target_resource_code
        self.target_material_code = target_material_code
        self.crafting_analysis = CraftingAnalysisModule()
        self.map_analysis = MapAnalysisModule()

    def calculate_weight(self, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate gathering goal weight using multi-factor scoring.

        This method implements the PRP requirement for weighted scoring:
        - Necessity (40%): Materials needed for crafting progression
        - Feasibility (30%): Character has required gathering skills and access
        - Progression Value (20%): Materials enable level-appropriate equipment creation
        - Stability (10%): Low error risk with predictable resource availability
        """
        self.validate_game_data(game_data)

        # Calculate necessity (40% weight)
        necessity = self._calculate_gathering_necessity(character_state, game_data)

        # Calculate feasibility (30% weight)
        feasibility = self._calculate_gathering_feasibility(character_state, game_data)

        # Calculate progression value (20% weight)
        progression = self.get_progression_value(character_state)

        # Calculate stability (10% weight) - gathering is generally stable
        stability = 0.9  # High stability - resource gathering has predictable outcomes

        # Combine factors with PRP-specified weights
        final_weight = (necessity * 0.4 + feasibility * 0.3 +
                       progression * 0.2 + stability * 0.1)

        return min(10.0, final_weight * 10.0)  # Scale to 0-10 range

    def is_feasible(self, character_state: CharacterGameState, game_data: GameData) -> bool:
        """Check if gathering goal can be pursued with current character state."""
        self.validate_game_data(game_data)

        # Find available resources using real game data
        available_resources = self._find_available_resources(character_state, game_data)

        if not available_resources:
            return False

        # Check if character has gathering skills for at least some resources
        for resource_code, (resource, locations) in available_resources.items():
            if self._can_gather_resource(character_state, resource):
                return True

        return False

    def get_target_state(
        self,
        character_state: CharacterGameState,
        game_data: GameData
    ) -> GOAPTargetState:
        """Return GOAP target state for gathering goal.
        
        This method defines the desired state conditions for successful gathering:
        1. Character must be at a resource location where gathering is possible
        2. Character must have appropriate gathering tool equipped
        3. Character must gain resources and skill XP through gathering actions
        4. Inventory must have space for collected materials
        """
        self.validate_game_data(game_data)

        # Select optimal resource target
        resource_result = self._select_optimal_resource(character_state, game_data)
        if not resource_result:
            # Return empty target state if no feasible gathering targets
            return GOAPTargetState(
                target_states={},
                priority=0,
                timeout_seconds=None
            )

        target_resource, target_locations = resource_result

        # Get best location for gathering
        if not target_locations:
            return GOAPTargetState(
                target_states={},
                priority=0,
                timeout_seconds=None
            )

        # Find nearest location
        current_pos = (character_state.x, character_state.y)
        distances = self.map_analysis.calculate_travel_efficiency(
            current_pos, [(loc.x, loc.y) for loc in target_locations]
        )
        if distances:
            best_pos = max(distances.keys(), key=lambda pos: distances[pos])
            target_location = next(loc for loc in target_locations
                                 if (loc.x, loc.y) == best_pos)
        else:
            target_location = target_locations[0]

        # Define target state conditions for gathering success
        target_states = {
            # Must be at resource location for gathering
            GameState.AT_RESOURCE_LOCATION: True,
            GameState.CURRENT_X: target_location.x,
            GameState.CURRENT_Y: target_location.y,

            # Must have appropriate tool equipped
            GameState.TOOL_EQUIPPED: True,
            GameState.CAN_GATHER: True,

            # Must gain resources and XP
            GameState.GAINED_XP: True,
            GameState.HAS_REQUIRED_ITEMS: True,
            GameState.RESOURCE_AVAILABLE: True,

            # Inventory management
            GameState.INVENTORY_SPACE_AVAILABLE: True,

            # Action readiness
            GameState.COOLDOWN_READY: True,
        }

        return GOAPTargetState(
            target_states=target_states,
            priority=6,  # Medium-high priority for progression support
            timeout_seconds=600  # 10 minute timeout for gathering chains
        )

    def get_progression_value(self, character_state: CharacterGameState) -> float:
        """Calculate contribution to reaching level 5 with appropriate gear."""
        # Gathering contributes to progression by:
        # 1. Providing materials for crafting level-appropriate equipment
        # 2. Providing gathering skill XP
        # 3. Enabling economic activities (selling materials for gold)


        # Higher value for characters who need materials for crafting
        material_need = self._assess_material_need(character_state)

        # Consider gathering skill levels (diverse skills are valuable)
        gathering_skills = [
            character_state.mining_level,
            character_state.woodcutting_level,
            character_state.fishing_level
        ]
        avg_gathering_skill = sum(gathering_skills) / len(gathering_skills)
        skill_development_value = max(0.2, (5 - avg_gathering_skill) / 4.0)

        return min(1.0, material_need * 0.6 + skill_development_value * 0.4)

    def estimate_error_risk(self, character_state: CharacterGameState) -> float:
        """Estimate gathering-specific error risk."""
        # Gathering generally has low error risk
        base_risk = 0.1

        # Increase risk if character lacks appropriate tools
        tool_risk = 0.0
        if not character_state.weapon_slot:  # Weapon slot often used for gathering tools
            tool_risk += 0.2

        # Increase risk if character has low gathering skills
        gathering_skills = [
            character_state.mining_level,
            character_state.woodcutting_level,
            character_state.fishing_level
        ]
        min_skill = min(gathering_skills)
        skill_risk = max(0.0, (2 - min_skill) * 0.1)

        return min(1.0, base_risk + tool_risk + skill_risk)

    def generate_sub_goal_requests(
        self,
        character_state: CharacterGameState,
        game_data: GameData
    ) -> list[SubGoalRequest]:
        """Generate sub-goal requests for gathering dependencies."""
        sub_goals: list[SubGoalRequest] = []

        # Select target resource
        resource_result = self._select_optimal_resource(character_state, game_data)
        if not resource_result:
            return sub_goals
        target_resource, target_locations = resource_result

        # Request movement to resource location if not already there
        if target_locations:
            # Find nearest resource location
            current_pos = (character_state.x, character_state.y)
            distances = self.map_analysis.calculate_travel_efficiency(
                current_pos, [(loc.x, loc.y) for loc in target_locations]
            )

            if distances:
                best_pos = max(distances.keys(), key=lambda pos: distances[pos])
                sub_goals.append(SubGoalRequest.move_to_location(
                    best_pos[0],
                    best_pos[1],
                    "GatheringGoal",
                    f"Move to {target_resource.name} resource location"
                ))

        # Request appropriate tool if needed
        required_tool_type = self._get_required_tool_type(target_resource.skill)
        if required_tool_type and not self._has_appropriate_tool(character_state, required_tool_type):
            sub_goals.append(SubGoalRequest.equip_item_type(
                required_tool_type,
                5,  # Max level 5 tools for progression goal
                "GatheringGoal",
                f"Need {required_tool_type} for {target_resource.skill}"
            ))

        return sub_goals

    def _find_available_resources(self, character_state: CharacterGameState, game_data: GameData) -> dict[str, tuple[GameResource, list[GameMap]]]:
        """Find available resources that character can potentially gather."""
        available_resources = {}

        for resource in game_data.resources:
            # Check if character skill level is sufficient or close
            char_skill_level = self._get_character_skill_level(character_state, resource.skill)

            if char_skill_level >= resource.level - 1:  # Allow slightly under-leveled
                # Find locations for this resource
                resource_locations = self.map_analysis.find_content_by_code(
                    "resource", resource.code, game_data.maps
                )

                if resource_locations:
                    available_resources[resource.code] = (resource, resource_locations)

        return available_resources

    def _select_optimal_resource(
        self, character_state: CharacterGameState, game_data: GameData
    ) -> tuple[Any, Any] | None:
        """Select the optimal resource to gather based on character needs."""
        if self.target_resource_code:
            # Use specific resource if requested
            for resource in game_data.resources:
                if resource.code == self.target_resource_code:
                    locations = self.map_analysis.find_content_by_code(
                        "resource", resource.code, game_data.maps
                    )
                    if locations and self._can_gather_resource(character_state, resource):
                        return resource, locations

        if self.target_material_code:
            # Find resources that drop the target material
            material_sources = self.crafting_analysis.find_material_sources(
                self.target_material_code, game_data.resources, game_data.maps
            )

            for location, resource in material_sources:
                if self._can_gather_resource(character_state, resource):
                    all_locations = self.map_analysis.find_content_by_code(
                        "resource", resource.code, game_data.maps
                    )
                    return resource, all_locations

        # Find optimal resource based on character needs and capabilities
        available_resources = self._find_available_resources(character_state, game_data)

        if not available_resources:
            return None, None

        # Score resources by value
        scored_resources = []
        for resource_code, (resource, locations) in available_resources.items():
            score = self._score_resource_value(resource, locations, character_state, game_data)
            scored_resources.append((resource, locations, score))

        # Return highest scoring resource
        scored_resources.sort(key=lambda x: x[2], reverse=True)
        if scored_resources:
            return scored_resources[0][0], scored_resources[0][1]

        return None, None

    def _score_resource_value(
        self, resource: Any, locations: Any, character_state: CharacterGameState, game_data: GameData
    ) -> float:
        """Score resource value for prioritization."""
        score = 0.0

        # Prefer resources character can gather efficiently
        char_skill_level = self._get_character_skill_level(character_state, resource.skill)
        skill_efficiency = min(1.0, char_skill_level / resource.level)
        score += skill_efficiency * 0.4

        # Prefer resources with valuable drops
        valuable_drops = self._assess_drop_value(resource, game_data)
        score += valuable_drops * 0.3

        # Prefer nearby resources
        if locations:
            current_pos = (character_state.x, character_state.y)
            distances = [abs(loc.x - current_pos[0]) + abs(loc.y - current_pos[1]) for loc in locations]
            min_distance = min(distances)
            proximity_score = 1.0 / max(1, min_distance / 5.0)  # Normalize
            score += proximity_score * 0.2

        # Prefer resources that provide needed materials
        material_need_score = self._assess_material_need_for_resource(resource, character_state, game_data)
        score += material_need_score * 0.1

        return score

    def _can_gather_resource(self, character_state: CharacterGameState, resource: Any) -> bool:
        """Check if character can gather from this resource."""
        char_skill_level = self._get_character_skill_level(character_state, resource.skill)
        return char_skill_level >= resource.level - 1  # Allow slightly under-leveled

    def _get_character_skill_level(self, character_state: CharacterGameState, skill_name: str) -> int:
        """Get character's skill level for the specified skill."""
        skill_mapping = {
            'mining': character_state.mining_level,
            'woodcutting': character_state.woodcutting_level,
            'fishing': character_state.fishing_level,
        }

        return skill_mapping.get(skill_name.lower(), 1)

    def _calculate_gathering_necessity(self, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate how necessary gathering is for character progression."""
        # High necessity if character needs materials for crafting
        material_need = self._assess_material_need(character_state)

        # Higher necessity if gathering skills are lagging behind character level
        gathering_skills = [
            character_state.mining_level,
            character_state.woodcutting_level,
            character_state.fishing_level
        ]
        avg_gathering_skill = sum(gathering_skills) / len(gathering_skills)
        skill_lag = max(0.0, character_state.level - avg_gathering_skill)
        skill_necessity = min(1.0, skill_lag / 3.0)

        return min(1.0, material_need * 0.7 + skill_necessity * 0.3)

    def _calculate_gathering_feasibility(self, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate gathering feasibility score."""
        feasibility_score = 0.0

        # Skill feasibility (40% of feasibility)
        gathering_skills = [
            character_state.mining_level,
            character_state.woodcutting_level,
            character_state.fishing_level
        ]
        avg_skill = sum(gathering_skills) / len(gathering_skills)
        skill_feasibility = min(1.0, avg_skill / 5.0)  # Normalize to level 5
        feasibility_score += skill_feasibility * 0.4

        # Resource availability (40% of feasibility)
        available_resources = self._find_available_resources(character_state, game_data)
        resource_availability = min(1.0, len(available_resources) / 5.0)  # Normalize
        feasibility_score += resource_availability * 0.4

        # Tool availability (20% of feasibility)
        # Simplified - assume tools are generally available or character has weapon slot
        tool_feasibility = 0.8 if character_state.weapon_slot else 0.5
        feasibility_score += tool_feasibility * 0.2

        return min(1.0, feasibility_score)

    def _assess_material_need(self, character_state: CharacterGameState) -> float:
        """Assess how much the character needs materials for progression."""
        # Simplified assessment - assume moderate material need
        # In full implementation, this would analyze inventory and crafting needs
        return 0.7

    def _assess_drop_value(self, resource: Any, game_data: Any) -> float:
        """Assess the value of materials this resource drops."""
        # Simplified - assume moderate value
        # In full implementation, this would analyze drop rarity and usefulness
        return 0.6

    def _assess_material_need_for_resource(
        self, resource: Any, character_state: CharacterGameState, game_data: GameData
    ) -> float:
        """Assess need for materials this specific resource provides."""
        # Simplified - assume moderate need
        # In full implementation, this would check crafting recipes and inventory
        return 0.5

    def _get_required_tool_type(self, skill_name: str) -> str | None:
        """Get the tool type required for a gathering skill."""
        tool_mapping = {
            'mining': 'pickaxe',
            'woodcutting': 'axe',
            'fishing': 'fishing_rod'
        }

        return tool_mapping.get(skill_name.lower())

    def _has_appropriate_tool(self, character_state: CharacterGameState, tool_type: str) -> bool:
        """Check if character has appropriate tool equipped."""
        # Simplified check - assume weapon slot is used for tools
        return character_state.weapon_slot is not None
