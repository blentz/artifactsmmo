"""
Select Recipe Action

This action selects the optimal recipe for crafting based on current equipment analysis
and character status, setting the selected_item for subsequent crafting actions.
"""

from typing import TYPE_CHECKING, Dict, Optional

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api

from .base import ActionBase

if TYPE_CHECKING:
    from src.lib.action_context import ActionContext

class SelectRecipeAction(ActionBase):
    """
    Action to select optimal recipe for equipment crafting.
    
    This action evaluates available recipes based on character level,
    current equipment status, and crafting capabilities to select
    the best item to craft next.
    """

    # GOAP parameters - consolidated state format
    conditions = {
        "equipment_status": {
            "upgrade_status": "analyzing",
            "target_slot": "!null"
        }
    }
    reactions = {
        "equipment_status": {
            "upgrade_status": "ready",
            "selected_item": "${selected_item}"
        }
    }
    weight = 2

    def __init__(self):
        """Initialize the recipe selection action."""
        super().__init__()

    def execute(self, client, context: 'ActionContext') -> Optional[Dict]:
        """Select optimal recipe for current equipment needs."""
        # Call superclass to set self._context
        super().execute(client, context)
        
        # Get parameters from context
        character_name = context.character_name
        target_slot = context.get('target_slot', 'weapon')
        
        self.log_execution_start(
            character_name=character_name,
            target_slot=target_slot
        )
        
        try:
            # Get current character data
            character_response = get_character_api(name=character_name, client=client)
            if not character_response or not character_response.data:
                return self.get_error_response("Could not get character data")
            
            character_data = character_response.data
            character_level = getattr(character_data, 'level', 1)
            
            # Select recipe based on target slot and character level
            selected_recipe = self._select_optimal_recipe(target_slot, character_level, character_data, client, context)
            
            if not selected_recipe:
                return self.get_error_response(f"No suitable recipe found for {target_slot}")
            
            # Create result with consolidated state updates
            result = self.get_success_response(
                equipment_status={
                    "upgrade_status": "ready",
                    "selected_item": selected_recipe['item_code'],
                    "target_slot": target_slot,
                    "recipe_selected": True
                },
                selected_recipe=selected_recipe,
                character_level=character_level,
                # Add top-level keys for template resolution
                selected_item=selected_recipe['item_code'],
                target_slot=target_slot
            )
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Recipe selection failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def _select_optimal_recipe(self, target_slot: str, character_level: int, 
                              character_data, client, context: 'ActionContext') -> Optional[Dict]:
        """Select the optimal recipe for the target slot and character level."""
        try:
            # Get basic recipes based on character level and slot
            if target_slot == 'weapon':
                return self._select_weapon_recipe(character_level, character_data, client, context)
            elif target_slot in ['helmet', 'body_armor', 'leg_armor', 'boots']:
                return self._select_armor_recipe(target_slot, character_level, character_data, client, context)
            else:
                return self._select_accessory_recipe(target_slot, character_level, character_data, client, context)
                
        except Exception as e:
            self.logger.warning(f"Recipe selection failed: {e}")
            return None

    def _select_weapon_recipe(self, character_level: int, character_data, client, context: 'ActionContext') -> Optional[Dict]:
        """Select optimal weapon recipe for character level."""
        try:
            current_weapon = getattr(character_data, 'weapon_slot', '')
            
            # Define weapon progression by level
            weapon_recipes = {
                1: {"item_code": "wooden_staff", "materials": ["ash_wood"], "workshop": "weaponcrafting"},
                2: {"item_code": "copper_dagger", "materials": ["copper"], "workshop": "weaponcrafting"},
                3: {"item_code": "iron_dagger", "materials": ["iron"], "workshop": "weaponcrafting"},
                4: {"item_code": "bronze_sword", "materials": ["bronze"], "workshop": "weaponcrafting"},
                5: {"item_code": "iron_sword", "materials": ["iron", "ash_wood"], "workshop": "weaponcrafting"}
            }
            
            # Select appropriate weapon for level
            if character_level <= 2 and current_weapon in ['wooden_stick', '', None]:
                if character_level == 1:
                    return weapon_recipes[1]  # wooden_staff
                else:
                    return weapon_recipes[2]  # copper_dagger
            elif character_level >= 3:
                # Select highest appropriate weapon
                max_level = min(character_level, max(weapon_recipes.keys()))
                return weapon_recipes[max_level]
            
            # Default to basic weapon
            return weapon_recipes[1]
            
        except Exception as e:
            self.logger.warning(f"Weapon recipe selection failed: {e}")
            return {"item_code": "wooden_staff", "materials": ["ash_wood"], "workshop": "weaponcrafting"}

    def _select_armor_recipe(self, target_slot: str, character_level: int, 
                           character_data, client, context: 'ActionContext') -> Optional[Dict]:
        """Select optimal armor recipe for target slot and character level."""
        try:
            # Define armor recipes by slot and level
            armor_recipes = {
                'helmet': {
                    1: {"item_code": "leather_cap", "materials": ["leather"], "workshop": "gearcrafting"},
                    2: {"item_code": "copper_helmet", "materials": ["copper"], "workshop": "gearcrafting"}
                },
                'body_armor': {
                    1: {"item_code": "leather_vest", "materials": ["leather"], "workshop": "gearcrafting"},
                    2: {"item_code": "copper_armor", "materials": ["copper"], "workshop": "gearcrafting"}
                },
                'leg_armor': {
                    1: {"item_code": "leather_pants", "materials": ["leather"], "workshop": "gearcrafting"},
                    2: {"item_code": "copper_legs", "materials": ["copper"], "workshop": "gearcrafting"}
                },
                'boots': {
                    1: {"item_code": "leather_boots", "materials": ["leather"], "workshop": "gearcrafting"},
                    2: {"item_code": "copper_boots", "materials": ["copper"], "workshop": "gearcrafting"}
                }
            }
            
            slot_recipes = armor_recipes.get(target_slot, {})
            if not slot_recipes:
                return None
                
            # Select appropriate armor for level
            max_level = min(character_level, max(slot_recipes.keys()))
            return slot_recipes[max_level]
            
        except Exception as e:
            self.logger.warning(f"Armor recipe selection failed: {e}")
            return None

    def _select_accessory_recipe(self, target_slot: str, character_level: int,
                               character_data, client, context: 'ActionContext') -> Optional[Dict]:
        """Select optimal accessory recipe for target slot and character level."""
        try:
            # Accessories are lower priority and simpler
            accessory_recipes = {
                'ring1': {"item_code": "copper_ring", "materials": ["copper"], "workshop": "jewelrycrafting"},
                'ring2': {"item_code": "copper_ring", "materials": ["copper"], "workshop": "jewelrycrafting"},
                'amulet': {"item_code": "copper_amulet", "materials": ["copper"], "workshop": "jewelrycrafting"}
            }
            
            return accessory_recipes.get(target_slot)
            
        except Exception as e:
            self.logger.warning(f"Accessory recipe selection failed: {e}")
            return None

    def __repr__(self):
        return "SelectRecipeAction()"