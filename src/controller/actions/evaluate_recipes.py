"""
Evaluate Recipes Action - General purpose recipe evaluation for any equipment slot

This action evaluates all available recipes for a given equipment slot and selects
the best craftable option based on material availability, stat improvements, and
character requirements.
"""

import logging
from typing import Dict, List, Optional, Tuple

from src.controller.actions.base import ActionBase, ActionResult
from src.game.character.state import CharacterState
from src.lib.action_context import ActionContext


class EvaluateRecipesAction(ActionBase):
    """
    General-purpose action to evaluate recipes for any equipment slot.
    
    This action:
    1. Fetches all recipes for the specified slot and crafting skill
    2. Filters recipes by level appropriateness and material availability
    3. Scores recipes based on stat improvements and crafting difficulty
    4. Selects the best craftable option
    5. Updates action context with the selected item for subsequent crafting
    """
    
    # GOAP parameters for planning
    conditions = {
            'character_status': {
                'alive': True,
            },
            'equipment_status': {
                'target_slot': '!null',
                'selected_item': None
            }
        }
    
    reactions = {
        'equipment_status': {
            'selected_item': 'wooden_staff',
            'recipe_evaluated': True
        }
    }
    
    weight = 2.0
    
    # Slot to skill mapping
    SLOT_TO_SKILL = {
        'weapon': 'weaponcrafting',
        'shield': 'weaponcrafting',
        'helmet': 'gearcrafting',
        'body_armor': 'gearcrafting',
        'leg_armor': 'gearcrafting',
        'boots': 'gearcrafting',
        'amulet': 'jewelrycrafting',
        'ring1': 'jewelrycrafting',
        'ring2': 'jewelrycrafting',
        'consumable': 'cooking',  # Food items
        'potion': 'alchemy'      # Potions
    }
    
    # Stat priorities by slot type
    SLOT_STAT_PRIORITIES = {
        'weapon': {
            'attack_fire': 3.0,
            'attack_earth': 3.0,
            'attack_water': 3.0,
            'attack_air': 3.0,
            'dmg_fire': 2.0,
            'dmg_earth': 2.0,
            'dmg_water': 2.0,
            'dmg_air': 2.0
        },
        'shield': {
            'res_fire': 3.0,
            'res_earth': 3.0,
            'res_water': 3.0,
            'res_air': 3.0,
            'hp': 2.0
        },
        'helmet': {
            'hp': 3.0,
            'res_fire': 2.0,
            'res_earth': 2.0,
            'res_water': 2.0,
            'res_air': 2.0
        },
        'body_armor': {
            'hp': 3.0,
            'res_fire': 2.0,
            'res_earth': 2.0,
            'res_water': 2.0,
            'res_air': 2.0
        },
        'leg_armor': {
            'hp': 3.0,
            'res_fire': 2.0,
            'res_earth': 2.0,
            'res_water': 2.0,
            'res_air': 2.0
        },
        'boots': {
            'haste': 3.0,
            'hp': 2.0,
            'res_fire': 1.5,
            'res_earth': 1.5,
            'res_water': 1.5,
            'res_air': 1.5
        },
        'amulet': {
            'critical_strike': 3.0,
            'wisdom': 2.5,
            'hp': 2.0
        },
        'ring1': {
            'critical_strike': 3.0,
            'wisdom': 2.5,
            'attack_fire': 2.0,
            'attack_earth': 2.0,
            'attack_water': 2.0,
            'attack_air': 2.0
        },
        'ring2': {
            'critical_strike': 3.0,
            'wisdom': 2.5,
            'attack_fire': 2.0,
            'attack_earth': 2.0,
            'attack_water': 2.0,
            'attack_air': 2.0
        },
        'consumable': {
            'hp_restore': 3.0,
            'boost_hp': 2.0,
            'boost_damage': 2.0
        },
        'potion': {
            'boost_hp': 3.0,
            'boost_damage': 3.0,
            'boost_resistance': 2.0,
            'boost_haste': 2.0
        }
    }
    
    def __init__(self):
        """Initialize the evaluate recipes action."""
        super().__init__()
        
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Execute the recipe evaluation for the specified equipment slot.
        
        Args:
            client: API client for making requests
            context: ActionContext containing all execution parameters
            
        Returns:
            Action result dictionary
        """
        self._context = context
        
        # Get target slot from action context (set by SelectOptimalSlotAction)
        target_slot = context.get_parameter('target_equipment_slot')
        if not target_slot:
            return self.create_error_result("No target equipment slot specified - run SelectOptimalSlotAction first")
            
        # Get target craft skill from context (may be set by goal or previous action)
        target_craft_skill = context.get_parameter('target_craft_skill')
        
        self.logger.info(f"🔍 Evaluating recipes for slot: {target_slot}")
        
        # Get character state from context
        character_state = context.character_state
        if not character_state:
            return self.create_error_result("No character state available")
            
        # Determine crafting skill - prioritize explicit target_craft_skill over slot mapping
        if target_craft_skill:
            craft_skill = target_craft_skill
            # Validate that the target slot is compatible with the target skill
            if not self._validate_slot_skill_compatibility(target_slot, craft_skill):
                return self.create_error_result(f"Slot '{target_slot}' not compatible with skill '{craft_skill}'")
        else:
            # Fall back to slot-to-skill mapping
            craft_skill = self.SLOT_TO_SKILL.get(target_slot)
            if not craft_skill:
                return self.create_error_result(f"Unknown equipment slot: {target_slot}")
            
        # Get current equipment in this slot
        current_item = self._get_current_equipment(character_state, target_slot)
        
        # Fetch available recipes for this crafting skill
        recipes = self._fetch_recipes(craft_skill, character_state, client)
        if not recipes:
            return self.create_error_result(f"No {craft_skill} recipes available")
            
        # Evaluate and score each recipe
        scored_recipes = []
        for recipe in recipes:
            score, reasoning = self._evaluate_recipe(
                recipe, current_item, character_state, craft_skill, target_slot, client
            )
            if score > 0:
                scored_recipes.append((recipe, score, reasoning))
                
        if not scored_recipes:
            return self.create_error_result(f"No craftable recipes found for {target_slot}")
            
        # Sort by score and select the best option
        scored_recipes.sort(key=lambda x: x[1], reverse=True)
        best_recipe, best_score, best_reasoning = scored_recipes[0]
        
        # Log top candidates
        self.logger.info(f"Top {min(3, len(scored_recipes))} recipe candidates for {target_slot}:")
        for i, (recipe, score, reasoning) in enumerate(scored_recipes[:3]):
            self.logger.info(f"  {i+1}. {recipe['item']['code']} (score: {score:.2f}) - {reasoning}")
            
        # Update action context with selected item
        selected_item = best_recipe['item']['code']
        context.set_result('selected_item_code', selected_item)
        context.set_result('selected_recipe', best_recipe)
        context.set_result('target_equipment_slot', target_slot)
        context.set_result('required_craft_skill', craft_skill)
        context.set_result('required_craft_level', best_recipe.get('level', 1))
        
        # Store workshop type needed
        workshop_type = f"{craft_skill}_workshop"
        context.set_result('required_workshop_type', workshop_type)
        
        self.logger.info(f"✅ Selected {selected_item} for {target_slot} crafting (score: {best_score:.2f})")
        self.logger.info(f"   Reasoning: {best_reasoning}")
        self.logger.info(f"   Required workshop: {workshop_type}")
        
        return self.create_success_result(
            message=f"Selected {selected_item} for {target_slot} slot",
            selected_item=selected_item,
            target_slot=target_slot,
            craft_skill=craft_skill,
            workshop_type=workshop_type,
            score=best_score,
            reasoning=best_reasoning
        )
        
    def _validate_slot_skill_compatibility(self, target_slot: str, craft_skill: str) -> bool:
        """
        Validate that a target slot is compatible with a crafting skill.
        
        Args:
            target_slot: Equipment slot to validate
            craft_skill: Crafting skill to validate against
            
        Returns:
            True if slot and skill are compatible
        """
        # Get the skill that normally handles this slot
        expected_skill = self.SLOT_TO_SKILL.get(target_slot)
        
        # Allow exact match
        if expected_skill == craft_skill:
            return True
            
        # Allow some cross-compatibility for related skills
        compatible_mappings = {
            'weaponcrafting': ['weapon', 'shield'],
            'gearcrafting': ['helmet', 'body_armor', 'leg_armor', 'boots'],
            'jewelrycrafting': ['amulet', 'ring1', 'ring2'],
            'cooking': ['consumable'],
            'alchemy': ['potion']
        }
        
        compatible_slots = compatible_mappings.get(craft_skill, [])
        return target_slot in compatible_slots
        
    def _get_current_equipment(self, character_state: CharacterState, slot: str) -> Optional[Dict]:
        """Get the current equipment in the specified slot."""
        if not character_state.data or 'equipment' not in character_state.data:
            return None
            
        equipment = character_state.data.get('equipment', {})
        
        # Handle special cases for rings
        if slot in ['ring1', 'ring2']:
            slot_name = 'ring'
        else:
            slot_name = slot
            
        return equipment.get(slot_name)
        
    def _item_fits_slot(self, item_slot: str, target_slot: str) -> bool:
        """
        Check if an item can be equipped in the target slot.
        
        Args:
            item_slot: The slot designation from the item
            target_slot: The target equipment slot
            
        Returns:
            True if the item fits in the target slot
        """
        # Direct match
        if item_slot == target_slot:
            return True
            
        # Handle ring slots - both ring1 and ring2 can use ring items
        if target_slot in ['ring1', 'ring2'] and item_slot == 'ring':
            return True
            
        return False
        
    def _fetch_recipes(self, craft_skill: str, character_state: CharacterState, client) -> List[Dict]:
        """Fetch all recipes for the specified crafting skill."""
        try:
            # Import API method
            from artifactsmmo_api_client.api.items.get_all_items_items_get import sync as get_all_items
            
            # Fetch all items with crafting info
            response = get_all_items(
                client=client,
                craft_skill=craft_skill,
                craft_material='',  # Get all materials
                size=100
            )
            
            if response and hasattr(response, 'data'):
                recipes = []
                for item in response.data:
                    if hasattr(item, 'craft') and item.craft:
                        recipe_data = {
                            'item': item.to_dict() if hasattr(item, 'to_dict') else item,
                            'level': item.craft.level if hasattr(item.craft, 'level') else 1,
                            'items': []
                        }
                        
                        # Extract required items
                        if hasattr(item.craft, 'items') and item.craft.items:
                            for craft_item in item.craft.items:
                                if hasattr(craft_item, 'code') and hasattr(craft_item, 'quantity'):
                                    recipe_data['items'].append({
                                        'code': craft_item.code,
                                        'quantity': craft_item.quantity
                                    })
                                    
                        recipes.append(recipe_data)
                        
                return recipes
            return []
            
        except Exception as e:
            self.logger.error(f"Failed to fetch {craft_skill} recipes: {e}")
            return []
            
    def _evaluate_recipe(self, recipe: Dict, current_item: Optional[Dict], 
                        character_state: CharacterState, craft_skill: str, 
                        target_slot: str, client) -> Tuple[float, str]:
        """
        Evaluate a recipe and return a score with reasoning.
        
        Returns:
            Tuple of (score, reasoning_string)
        """
        item = recipe['item']
        item_code = item['code']
        item_level = item.get('level', 1)
        
        # Check if item can be equipped in target slot
        item_slot = item.get('slot', '')
        if not self._item_fits_slot(item_slot, target_slot):
            return 0, f"Item slot '{item_slot}' doesn't match target slot '{target_slot}'"
        
        # Check if this is a starter item (level 0-1)
        if item_level <= 1 and current_item and current_item.get('level', 0) > 1:
            return 0, "Starter item, not an upgrade"
            
        # Check level appropriateness
        char_level = character_state.data.get('level', 1)
        level_range = 3  # Configurable
        
        if item_level > char_level + level_range:
            return 0, f"Too high level (requires level {item_level})"
            
        # Be more permissive with low-level items for low-level characters
        # Allow level 1 items for characters up to level 5
        min_level = 1 if char_level <= 5 else max(1, char_level - level_range)
        if item_level < min_level:
            return 0, f"Too low level (level {item_level})"
            
        # Check skill requirements
        char_skills = character_state.data.get('skills', {})
        current_skill_level = char_skills.get(craft_skill, 0)
        required_skill_level = recipe.get('level', 1)
        
        if current_skill_level < required_skill_level:
            return 0, f"Insufficient {craft_skill} level ({current_skill_level}/{required_skill_level})"
            
        # Check material availability
        inventory = character_state.data.get('inventory', [])
        inventory_dict = {item['code']: item['quantity'] for item in inventory if item}
        
        materials_available = True
        missing_materials = []
        total_materials_needed = 0
        materials_in_inventory = 0
        
        for material in recipe.get('items', []):
            mat_code = material['code']
            mat_qty = material['quantity']
            total_materials_needed += mat_qty
            
            available_qty = inventory_dict.get(mat_code, 0)
            materials_in_inventory += min(available_qty, mat_qty)
            
            if available_qty < mat_qty:
                materials_available = False
                missing_materials.append(f"{mat_code} ({available_qty}/{mat_qty})")
                
        # Calculate base score
        score = 100.0
        
        # Inventory proximity bonus (primary factor)
        if total_materials_needed > 0:
            inventory_proximity = materials_in_inventory / total_materials_needed
            score *= (1 + inventory_proximity * 2)  # Up to 3x multiplier
        else:
            inventory_proximity = 1.0
            
        # Material availability penalty
        if not materials_available:
            score *= 0.3  # Significant penalty but still consider
            
        # Stat improvement bonus
        stat_priorities = self.SLOT_STAT_PRIORITIES.get(target_slot, {})
        stat_improvement = self._calculate_stat_improvement(item, current_item, stat_priorities)
        score *= (1 + stat_improvement * 0.5)  # Up to 1.5x for stat improvements
        
        # Level appropriateness bonus
        level_diff = abs(item_level - char_level)
        level_bonus = 1.0 - (level_diff * 0.1)  # Decrease by 10% per level difference
        score *= max(0.5, level_bonus)
        
        # Build reasoning
        reasoning_parts = []
        if materials_available:
            reasoning_parts.append("materials ready")
        else:
            reasoning_parts.append(f"missing: {', '.join(missing_materials)}")
            
        reasoning_parts.append(f"{int(inventory_proximity * 100)}% materials in inventory")
        
        if stat_improvement > 0:
            reasoning_parts.append(f"+{int(stat_improvement * 100)}% stats")
            
        reasoning_parts.append(f"level {item_level}")
        
        reasoning = ", ".join(reasoning_parts)
        
        return score, reasoning
        
    def _calculate_stat_improvement(self, new_item: Dict, current_item: Optional[Dict], 
                                   stat_priorities: Dict[str, float]) -> float:
        """Calculate the stat improvement percentage for the new item."""
        if not current_item:
            # No current item, any stats are an improvement
            return 1.0
            
        current_stats = current_item.get('effects', {})
        new_stats = new_item.get('effects', {})
        
        if not new_stats:
            return 0.0
            
        total_improvement = 0.0
        total_weight = 0.0
        
        for stat, weight in stat_priorities.items():
            current_value = current_stats.get(stat, 0)
            new_value = new_stats.get(stat, 0)
            
            if new_value > current_value:
                if current_value > 0:
                    improvement = (new_value - current_value) / current_value
                else:
                    improvement = 1.0  # 100% improvement from 0
                    
                total_improvement += improvement * weight
                total_weight += weight
                
        if total_weight > 0:
            return total_improvement / total_weight
        return 0.0