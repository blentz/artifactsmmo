"""
Crafting Goal Implementation

This module implements intelligent crafting goal selection that creates level-appropriate
equipment and gains crafting XP using data-driven recipe analysis and material planning
without hardcoded recipes or values.
"""

from typing import Any

from ..analysis.crafting_analysis import CraftingAnalysisModule
from ..analysis.map_analysis import MapAnalysisModule
from ..state.character_game_state import CharacterGameState
from ..state.game_state import GameState
from src.game_data.game_data import GameData
from ..types.goap_models import GOAPTargetState
from .base_goal import BaseGoal
from .sub_goal_request import SubGoalRequest


class CraftingGoal(BaseGoal):
    """Intelligent crafting goal for level-appropriate equipment creation.

    This goal implements strategic crafting planning using the CraftingAnalysisModule
    to create equipment suitable for level 5 progression, with material dependency
    resolution and sub-goal request generation for gathering requirements.
    """

    def __init__(self, target_item_code: str | None = None, max_result_level: int = 5):
        """Initialize crafting goal with optional target specification.

        Parameters:
            target_item_code: Optional specific item code to craft
            max_result_level: Maximum level of items to craft (default 5 for progression goal)
        """
        self.target_item_code = target_item_code
        self.max_result_level = max_result_level
        self.crafting_analysis = CraftingAnalysisModule()
        self.map_analysis = MapAnalysisModule()

    def calculate_weight(self, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate crafting goal weight using multi-factor scoring.

        This method implements the PRP requirement for weighted scoring:
        - Necessity (40%): Equipment needed for progression
        - Feasibility (30%): Character has required skills and materials available
        - Progression Value (20%): Creates level-appropriate gear for level 5 goal
        - Stability (10%): Low error risk with predictable outcomes
        """
        self.validate_game_data(game_data)

        # Calculate necessity (40% weight)
        necessity = self._calculate_crafting_necessity(character_state, game_data)

        # Calculate feasibility (30% weight)
        feasibility = self._calculate_crafting_feasibility(character_state, game_data)

        # Calculate progression value (20% weight)
        progression = self.get_progression_value(character_state)

        # Calculate stability (10% weight) - crafting is generally stable
        stability = 0.8  # High stability - crafting has predictable outcomes

        # Combine factors with PRP-specified weights
        final_weight = (necessity * 0.4 + feasibility * 0.3 +
                       progression * 0.2 + stability * 0.1)

        return min(10.0, final_weight * 10.0)  # Scale to 0-10 range

    def is_feasible(self, character_state: CharacterGameState, game_data: GameData) -> bool:
        """Check if crafting goal can be pursued with current character state."""
        self.validate_game_data(game_data)

        # Find craftable recipes using analysis module
        craftable_recipes = self.crafting_analysis.find_level_appropriate_recipes(
            game_data.items, character_state, self.max_result_level
        )

        if not craftable_recipes:
            return False

        # Check if we have at least one feasible recipe
        for item, analysis in craftable_recipes:
            if analysis.feasible:
                return True

            # Also consider recipes that are close to feasible
            if (analysis.recipe_structure.skill_required and
                self._get_character_skill_level(character_state, analysis.recipe_structure.skill_required) >=
                analysis.recipe_structure.level_required - 1):
                return True

        return False

    def get_target_state(
        self,
        character_state: CharacterGameState,
        game_data: GameData
    ) -> GOAPTargetState:
        """Return GOAP target state for crafting goal.
        
        This method defines the desired state conditions for successful crafting:
        1. Character must be at a workshop location where crafting is possible
        2. Character must have all required materials for the recipe
        3. Character must have sufficient skill level for the recipe
        4. Character must gain crafting XP and create the target item
        """
        self.validate_game_data(game_data)

        # Select target recipe
        target_recipe = self._select_optimal_recipe(character_state, game_data)
        if not target_recipe:
            # Return empty target state if no feasible crafting targets
            return GOAPTargetState(
                target_states={},
                priority=1,
                timeout_seconds=None
            )

        item, analysis = target_recipe

        # Find appropriate workshop location
        workshop_locations = self.map_analysis.find_content_by_code(
            "workshop", analysis.recipe_structure.skill_required, game_data.maps
        )

        if not workshop_locations:
            # No workshop available for this crafting skill
            return GOAPTargetState(
                target_states={},
                priority=1,
                timeout_seconds=None
            )

        # Find nearest workshop location
        current_pos = (character_state.x, character_state.y)
        distances = self.map_analysis.calculate_travel_efficiency(
            current_pos, [(loc.x, loc.y) for loc in workshop_locations]
        )
        if distances:
            best_pos = max(distances.keys(), key=lambda pos: distances[pos])
            target_location = next(loc for loc in workshop_locations
                                 if (loc.x, loc.y) == best_pos)
        else:
            target_location = workshop_locations[0]

        # Define target state conditions for crafting success
        target_states = {
            # Must be at workshop location for crafting
            GameState.AT_WORKSHOP_LOCATION: True,
            GameState.CURRENT_X: target_location.x,
            GameState.CURRENT_Y: target_location.y,

            # Must have required materials
            GameState.HAS_CRAFTING_MATERIALS: True,
            GameState.HAS_REQUIRED_ITEMS: True,

            # Must be able to craft
            GameState.CAN_CRAFT: True,

            # Must gain XP and create item
            GameState.GAINED_XP: True,

            # Inventory management
            GameState.INVENTORY_SPACE_AVAILABLE: True,

            # Action readiness
            GameState.COOLDOWN_READY: True,
        }

        return GOAPTargetState(
            target_states=target_states,
            priority=7,  # High priority for equipment creation
            timeout_seconds=900  # 15 minute timeout for material gathering + crafting
        )

    def get_progression_value(self, character_state: CharacterGameState) -> float:
        """Calculate contribution to reaching level 5 with appropriate gear."""
        # Crafting contributes to progression in multiple ways:
        # 1. Creates level-appropriate equipment for combat effectiveness
        # 2. Provides crafting skill XP
        # 3. Enables better equipment for safer, more efficient combat

        current_level = character_state.level

        if current_level >= 5:
            # Still valuable for creating level-appropriate gear
            return 0.6

        # Higher value for characters who need better equipment
        equipment_need = self._assess_equipment_need(character_state)
        level_progress_value = (5 - current_level) / 4.0

        return min(1.0, 0.5 + (equipment_need + level_progress_value) * 0.25)

    def estimate_error_risk(self, character_state: CharacterGameState) -> float:
        """Estimate crafting-specific error risk."""
        # Crafting generally has low error risk compared to combat
        base_risk = 0.2

        # Increase risk if character skill levels are borderline
        skill_risk = 0.0
        if hasattr(character_state, 'weaponcrafting_level') and character_state.weaponcrafting_level < 3:
            skill_risk += 0.1
        if hasattr(character_state, 'gearcrafting_level') and character_state.gearcrafting_level < 3:
            skill_risk += 0.1

        return min(1.0, base_risk + skill_risk)

    def generate_sub_goal_requests(
        self,
        character_state: CharacterGameState,
        game_data: GameData
    ) -> list[SubGoalRequest]:
        """Generate sub-goal requests for crafting dependencies."""
        sub_goals: list[SubGoalRequest] = []

        # Select target recipe
        target_recipe = self._select_optimal_recipe(character_state, game_data)
        if not target_recipe:
            return sub_goals

        item, analysis = target_recipe

        # Request materials that are missing
        for material_info in analysis.recipe_structure.materials_needed:
            material_code = material_info.get('code', '')
            quantity = material_info.get('quantity', 1)

            if material_code:
                sub_goals.append(SubGoalRequest.obtain_item(
                    material_code,
                    quantity,
                    "CraftingGoal",
                    f"Need {quantity}x {material_code} for crafting {item.name}"
                ))

        # Request movement to workshop if needed
        if not character_state.at_workshop_location:
            # Find nearest workshop location
            workshop_locations = self.map_analysis.find_nearest_content(
                (character_state.x, character_state.y),
                "workshop",
                game_data.maps
            )

            if workshop_locations:
                target_workshop, _ = workshop_locations[0]
                sub_goals.append(SubGoalRequest.move_to_location(
                    target_workshop.x,
                    target_workshop.y,
                    "CraftingGoal",
                    f"Move to workshop for crafting {item.name}"
                ))

        return sub_goals

    def _select_optimal_recipe(
        self, character_state: CharacterGameState, game_data: GameData
    ) -> tuple[Any, Any] | None:
        """Select the optimal recipe to craft based on character state and goals."""
        if self.target_item_code:
            # Use specific item if requested
            analysis = self.crafting_analysis.analyze_recipe_feasibility(
                self.target_item_code, game_data.items, character_state
            )

            target_item = None
            for item in game_data.items:
                if item.code == self.target_item_code:
                    target_item = item
                    break

            if target_item and (analysis.feasible or len(analysis.missing_materials) <= 2):
                return (target_item, analysis)

        # Find all feasible level-appropriate recipes
        craftable_recipes = self.crafting_analysis.find_level_appropriate_recipes(
            game_data.items, character_state, self.max_result_level
        )

        if not craftable_recipes:
            return None

        # Score recipes by value to progression
        scored_recipes = []
        for item, analysis in craftable_recipes:
            score = self._score_recipe_value(item, analysis, character_state)
            scored_recipes.append((item, analysis, score))

        # Return highest scoring recipe
        scored_recipes.sort(key=lambda x: x[2], reverse=True)
        if scored_recipes:
            return (scored_recipes[0][0], scored_recipes[0][1])

        return None

    def _score_recipe_value(self, item: Any, analysis: Any, character_state: CharacterGameState) -> float:
        """Score recipe value for prioritization."""
        score = 0.0

        # Prefer equipment items
        if item.type in ['weapon', 'helmet', 'body_armor', 'leg_armor', 'boots', 'ring', 'amulet']:
            score += 0.5

        # Prefer items appropriate for current level
        level_appropriateness = max(0.0, 1.0 - abs(item.level - character_state.level) / 3.0)
        score += level_appropriateness * 0.3

        # Prefer feasible recipes
        if analysis.feasible:
            score += 0.3
        elif len(analysis.missing_materials) <= 2:
            score += 0.1

        # Prefer recipes with lower material complexity
        material_complexity = len(analysis.recipe_structure.materials_needed)
        complexity_penalty = min(0.2, material_complexity * 0.05)
        score -= complexity_penalty

        return score

    def _calculate_crafting_necessity(self, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate how necessary crafting is for character progression."""
        # High necessity if character lacks level-appropriate equipment
        equipment_need = self._assess_equipment_need(character_state)

        # Higher necessity for lower level characters who need gear upgrades
        level_factor = max(0.2, (5 - character_state.level) / 4.0)

        return min(1.0, equipment_need * 0.6 + level_factor * 0.4)

    def _calculate_crafting_feasibility(self, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate crafting feasibility score."""
        feasibility_score = 0.0

        # Skill feasibility (50% of feasibility)
        skill_levels = [
            character_state.weaponcrafting_level,
            character_state.gearcrafting_level,
            character_state.jewelrycrafting_level
        ]
        avg_crafting_skill = sum(skill_levels) / len(skill_levels)
        skill_feasibility = min(1.0, avg_crafting_skill / 5.0)  # Normalize to level 5
        feasibility_score += skill_feasibility * 0.5

        # Recipe availability (30% of feasibility)
        craftable_recipes = self.crafting_analysis.find_level_appropriate_recipes(
            game_data.items, character_state, self.max_result_level
        )
        recipe_availability = min(1.0, len(craftable_recipes) / 5.0)  # Normalize
        feasibility_score += recipe_availability * 0.3

        # Material accessibility (20% of feasibility)
        # Simplified - assume materials are generally available
        material_feasibility = 0.7
        feasibility_score += material_feasibility * 0.2

        return min(1.0, feasibility_score)

    def _assess_equipment_need(self, character_state: CharacterGameState) -> float:
        """Assess how much the character needs better equipment."""
        total_slots = 8  # weapon, helmet, chest, legs, boots, ring1, ring2, amulet
        equipped_slots = 0

        # Count equipped items
        equipment_slots = [
            character_state.weapon_slot,
            character_state.helmet_slot,
            character_state.body_armor_slot,
            character_state.leg_armor_slot,
            character_state.boots_slot,
            character_state.ring1_slot,
            character_state.ring2_slot,
            character_state.amulet_slot,
        ]

        for slot in equipment_slots:
            if slot:
                equipped_slots += 1

        # Calculate equipment coverage
        equipment_coverage = equipped_slots / total_slots

        # Need is inversely related to coverage
        return 1.0 - equipment_coverage

    def _get_character_skill_level(self, character_state: CharacterGameState, skill_name: str) -> int:
        """Get character's skill level for the specified skill."""
        skill_mapping = {
            'mining': character_state.mining_level,
            'woodcutting': character_state.woodcutting_level,
            'fishing': character_state.fishing_level,
            'weaponcrafting': character_state.weaponcrafting_level,
            'gearcrafting': character_state.gearcrafting_level,
            'jewelrycrafting': character_state.jewelrycrafting_level,
            'cooking': character_state.cooking_level,
            'alchemy': character_state.alchemy_level,
        }

        return skill_mapping.get(skill_name.lower(), 1)
