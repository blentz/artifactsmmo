"""
Crafting Analysis Module

This module implements intelligent crafting analysis that parses real GameItem.craft
data to analyze recipes, material requirements, and crafting feasibility using only
cached game data without hardcoded values.
"""


from pydantic import BaseModel, Field

from src.game_data.models import GameItem, GameMap, GameResource

from ..state.character_game_state import CharacterGameState
from src.game_data.game_data import GameData


class RecipeStructure(BaseModel):
    """Character-independent recipe structure information."""
    item_code: str = Field(description="Code of the item being crafted")
    item_name: str = Field(default="", description="Name of the item being crafted")
    item_level: int = Field(default=1, description="Level of the resulting item")
    materials_needed: list[dict] = Field(default_factory=list, description="Required materials from recipe")
    skill_required: str = Field(default="", description="Skill needed for crafting")
    level_required: int = Field(default=1, description="Skill level required")
    is_craftable: bool = Field(description="Whether the item has a valid craft recipe")


class CraftingAnalysis(BaseModel):
    """Analysis result for a crafting recipe with character-specific feasibility."""
    recipe_structure: RecipeStructure = Field(description="Base recipe information")
    feasible: bool = Field(description="Whether crafting is currently feasible for this character")
    missing_materials: list[str] = Field(default_factory=list, description="Materials not in character inventory")
    reason: str = Field(default="", description="Reason if not feasible")
    character_skill_level: int = Field(default=1, description="Character's current skill level")


class CraftingAnalysisModule:
    """Analysis module for crafting recipes and material requirements.

    This class implements the PRP requirements to parse actual GameItem.craft
    data and analyze material dependencies using real cached game data,
    with no hardcoded recipes or material sources.
    """

    def analyze_recipe_structure(
        self,
        recipe_code: str,
        items: list[GameItem]
    ) -> RecipeStructure:
        """Analyze recipe structure without character-specific constraints.

        Parameters:
            recipe_code: Code of the item to craft
            items: List of all GameItem objects from cache

        Return values:
            RecipeStructure with recipe requirements and structure

        This method parses the raw recipe data without considering character
        capabilities, making it suitable for dependency tree analysis.
        """
        if not items:
            raise ValueError("Cannot analyze recipe structure: items list is empty")

        # Find the item using real data - NO hardcoding
        target_item = None
        for item in items:
            if item.code == recipe_code:
                target_item = item
                break

        if not target_item:
            return RecipeStructure(
                item_code=recipe_code,
                is_craftable=False
            )

        if not target_item.craft:
            return RecipeStructure(
                item_code=recipe_code,
                item_name=target_item.name,
                item_level=target_item.level,
                is_craftable=False
            )

        # Parse real crafting requirements - NO hardcoded data
        craft_data = target_item.craft
        required_materials = craft_data.get('materials', [])
        required_skill_level = craft_data.get('level', 1)
        skill_name = craft_data.get('skill', 'crafting')

        return RecipeStructure(
            item_code=recipe_code,
            item_name=target_item.name,
            item_level=target_item.level,
            materials_needed=required_materials,
            skill_required=skill_name,
            level_required=required_skill_level,
            is_craftable=True
        )

    def analyze_recipe_feasibility(
        self,
        recipe_code: str,
        items: list[GameItem],
        character_state: CharacterGameState
    ) -> CraftingAnalysis:
        """Analyze crafting recipe feasibility for a specific character.

        Parameters:
            recipe_code: Code of the item to craft
            items: List of all GameItem objects from cache
            character_state: Current character state with skill levels

        Return values:
            CraftingAnalysis with character-specific feasibility assessment

        This method combines recipe structure analysis with character capabilities
        to determine if the character can currently craft the item.
        """
        # First get the recipe structure
        recipe_structure = self.analyze_recipe_structure(recipe_code, items)

        if not recipe_structure.is_craftable:
            return CraftingAnalysis(
                recipe_structure=recipe_structure,
                feasible=False,
                reason=f"Item {recipe_code} is not craftable"
            )

        # Check if character has required skill level
        character_skill_level = self._get_character_skill_level(character_state, recipe_structure.skill_required)

        if character_skill_level < recipe_structure.level_required:
            return CraftingAnalysis(
                recipe_structure=recipe_structure,
                feasible=False,
                reason=f"Need {recipe_structure.skill_required} level {recipe_structure.level_required}, "
                       f"have {character_skill_level}",
                character_skill_level=character_skill_level
            )

        # Check material availability (this would need inventory data)
        # For now, assume materials need to be gathered
        missing_materials = [mat.get('code', 'unknown') for mat in recipe_structure.materials_needed]

        return CraftingAnalysis(
            recipe_structure=recipe_structure,
            feasible=True,  # Skill requirement met
            missing_materials=missing_materials,  # Assume all need gathering
            reason="Recipe is craftable with current skill level",
            character_skill_level=character_skill_level
        )

    def find_material_sources(
        self,
        material_code: str,
        resources: list[GameResource],
        maps: list[GameMap]
    ) -> list[tuple[GameMap, GameResource]]:
        """Find all locations where material can be gathered using real data.

        Parameters:
            material_code: Code of the material to find
            resources: List of all GameResource objects from cache
            maps: List of all GameMap objects from cache

        Return values:
            List of (location, resource) tuples where material can be obtained

        This method implements the exact requirements from the PRP:
        - Search resources list for items that drop the material
        - Cross-reference resource.code with map.content.code for locations
        - NO hardcoded material sources or locations
        """
        if not resources:
            raise ValueError("Cannot find material sources: resources list is empty")

        if not maps:
            raise ValueError("Cannot find material sources: maps list is empty")

        # Find resources that drop this material - NO hardcoding
        material_sources = []

        for resource in resources:
            # Check if this resource drops the required material
            resource_drops_material = False

            for drop in resource.drops:
                if isinstance(drop, dict) and drop.get('code') == material_code:
                    resource_drops_material = True
                    break

            if resource_drops_material:
                # Find locations where this resource exists
                resource_locations = [
                    game_map for game_map in maps
                    if (game_map.content and
                        game_map.content.type == "resource" and
                        game_map.content.code == resource.code)
                ]

                for location in resource_locations:
                    material_sources.append((location, resource))

        return material_sources

    def find_level_appropriate_recipes(
        self,
        items: list[GameItem],
        character_state: CharacterGameState,
        max_result_level: int = 5
    ) -> list[tuple[GameItem, CraftingAnalysis]]:
        """Find craftable recipes that produce level-appropriate items.

        Parameters:
            items: All items from cache
            character_state: Current character state
            max_result_level: Maximum level of resulting items

        Return values:
            List of (item, analysis) tuples for feasible level-appropriate recipes

        This method finds recipes that can create equipment suitable for
        the level 5 progression goal, using real craft data analysis.
        """
        if not items:
            raise ValueError("Cannot find recipes: items list is empty")

        appropriate_recipes = []

        for item in items:
            # Only consider items with level <= max_result_level
            if item.level <= max_result_level and item.craft:
                analysis = self.analyze_recipe_feasibility(item.code, items, character_state)

                # Include if recipe is feasible or close to feasible
                if analysis.feasible or (analysis.recipe_structure.skill_required and
                    self._get_character_skill_level(character_state, analysis.recipe_structure.skill_required) >=
                    analysis.recipe_structure.level_required - 1):
                    appropriate_recipes.append((item, analysis))

        # Sort by result item level (ascending) for progression planning
        return sorted(appropriate_recipes, key=lambda x: x[0].level)

    def calculate_material_dependency_tree(
        self,
        recipe_code: str,
        game_data: GameData,
        max_depth: int = 3
    ) -> dict:
        """Calculate complete dependency tree for a recipe including sub-materials.

        Parameters:
            recipe_code: Code of the item to craft
            items: All items from cache
            resources: All resources from cache
            maps: All maps from cache
            max_depth: Maximum recursion depth for nested recipes

        Return values:
            Dictionary representing the complete material dependency tree

        This method builds a complete dependency tree showing all materials
        needed, including materials that must be crafted from other materials,
        creating a comprehensive crafting plan.
        """
        dependency_tree = {
            'item_code': recipe_code,
            'direct_materials': [],
            'gathering_sources': [],
            'sub_recipes': [],
            'total_depth': 0
        }

        if max_depth <= 0:
            return dependency_tree

        # Get the base recipe analysis
        # Use recipe structure analysis instead of character-dependent analysis
        recipe_structure = self.analyze_recipe_structure(recipe_code, game_data.items)

        if not recipe_structure.is_craftable:
            return dependency_tree

        # Process each required material
        for material in recipe_structure.materials_needed:
            material_code = material.get('code', '')
            if not material_code:
                continue

            material_info = {
                'code': material_code,
                'quantity': material.get('quantity', 1),
                'sources': []
            }

            # Find gathering sources for this material
            gathering_sources = self.find_material_sources(material_code, game_data.resources, game_data.maps)
            for location, resource in gathering_sources:
                material_info['sources'].append({
                    'type': 'gathering',
                    'location': {'x': location.x, 'y': location.y},
                    'resource': resource.code,
                    'skill_required': resource.skill,
                    'level_required': resource.level
                })

            # Check if this material can also be crafted
            material_recipe = None
            for item in game_data.items:
                if item.code == material_code and item.craft:
                    material_recipe = item
                    break

            if material_recipe:
                # Recursively analyze sub-recipe
                sub_tree = self.calculate_material_dependency_tree(
                    material_code, game_data, max_depth - 1
                )
                material_info['sources'].append({
                    'type': 'crafting',
                    'recipe': sub_tree
                })
                dependency_tree['sub_recipes'].append(sub_tree)
                dependency_tree['total_depth'] = max(dependency_tree['total_depth'],
                                                   sub_tree['total_depth'] + 1)

            dependency_tree['direct_materials'].append(material_info)

        return dependency_tree

    def _get_character_skill_level(self, character_state: CharacterGameState, skill_name: str) -> int:
        """Get character's skill level for the specified skill.

        Parameters:
            character_state: Current character state
            skill_name: Name of the skill to check

        Return values:
            Integer skill level, defaults to 1 if skill not found
        """
        # Map skill names to character state attributes
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
