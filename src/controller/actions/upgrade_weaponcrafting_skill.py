"""
Upgrade Weaponcrafting Skill Action

This action handles leveling up the weaponcrafting skill by crafting simple items
that provide skill experience while being accessible to low-level characters.
"""

import logging
from typing import Dict, Optional

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api
from artifactsmmo_api_client.api.my_characters.action_crafting_my_name_action_crafting_post import sync as craft_api

from src.lib.action_context import ActionContext

from .base import ActionBase, ActionResult


class UpgradeWeaponcraftingSkillAction(ActionBase):
    """
    Action to upgrade weaponcrafting skill through strategic item crafting.
    
    Focuses on crafting simple weapons that provide skill XP while being
    accessible to characters with low skill levels and basic materials.
    """

    # GOAP parameters
    conditions = {
            'character_status': {
                'alive': True,
                'safe': True,
            },
            'workshop_status': {
                'at_workshop': True
            },
            'inventory_status': {
                'has_materials': True
            }
        }
    reactions = {
        'skill_status': {
            'weaponcrafting_level_sufficient': True,
            'xp_gained': True
        },
        'character_status': {
            'stats_improved': True
        }
    }
    weight = 30

    def __init__(self):
        """
        Initialize the weaponcrafting skill upgrade action.
        """
        super().__init__()
        self.logger = logging.getLogger(__name__)

    def execute(self, client, context: ActionContext) -> ActionResult:
        """Execute weaponcrafting skill upgrade through item crafting."""
        # Get parameters from context
        character_name = context.character_name
        target_level = context.get('target_level', 1)
        current_level = context.get('current_level', 0)
            
        self._context = context
        
        try:
            # Get current character data to check skill level and materials
            character_response = get_character_api(name=character_name, client=client)
            if not character_response or not character_response.data:
                return self.create_error_result("Could not get character data")
            
            character_data = character_response.data
            current_skill_level = getattr(character_data, 'weaponcrafting_level', 0)
            
            # Check if we've already reached the target level
            if current_skill_level >= target_level:
                result = self.create_success_result(
                    skill_level_achieved=True,
                    current_weaponcrafting_level=current_skill_level,
                    target_level=target_level,
                    message=f"Already at weaponcrafting level {current_skill_level}"
                )
                return result
            
            # Determine what to craft based on current skill level and available materials
            craft_item = self._select_craft_item(character_data)
            if not craft_item:
                return self.create_error_result("No suitable items to craft for skill upgrade")
            
            # Attempt to craft the item
            self.logger.info(f"🔨 Crafting {craft_item} to gain weaponcrafting experience")
            craft_response = craft_api(name=character_name, code=craft_item, client=client)
            
            if not craft_response:
                return self.create_error_result(f"Failed to craft {craft_item}")
            
            # Check if crafting was successful
            craft_data = craft_response.data if hasattr(craft_response, 'data') else {}
            
            # Get updated character data to check skill progress
            updated_character_response = get_character_api(name=character_name, client=client)
            if updated_character_response and updated_character_response.data:
                new_skill_level = getattr(updated_character_response.data, 'weaponcrafting_level', current_skill_level)
                skill_gained = new_skill_level - current_skill_level
                
                result = self.create_success_result(
                    item_crafted=craft_item,
                    skill_xp_gained=skill_gained > 0,
                    previous_skill_level=current_skill_level,
                    current_weaponcrafting_level=new_skill_level,
                    target_level=target_level,
                    target_achieved=new_skill_level >= target_level,
                    craft_response=craft_data
                )
            else:
                # Fallback result if we can't get updated character data
                result = self.create_success_result(
                    item_crafted=craft_item,
                    skill_xp_gained=True,  # Assume success
                    current_weaponcrafting_level=current_skill_level,
                    target_level=target_level,
                    craft_response=craft_data
                )
            
            return result
            
        except Exception as e:
            error_response = self.create_error_result(f"Weaponcrafting skill upgrade failed: {str(e)}")
            return error_response

    def _select_craft_item(self, character_data) -> Optional[str]:
        """
        Select an appropriate item to craft based on skill level and available materials.
        
        Returns:
            Item code to craft, or None if no suitable items available
        """
        try:
            # Get character inventory
            inventory = getattr(character_data, 'inventory', [])
            inventory_lookup = {}
            
            for item in inventory:
                if hasattr(item, 'code') and hasattr(item, 'quantity'):
                    code = item.code
                    quantity = item.quantity
                    if code and quantity > 0:
                        inventory_lookup[code] = quantity
            
            current_skill = getattr(character_data, 'weaponcrafting_level', 0)
            
            # Define craftable items for skill progression (level 0 items)
            # These should be the simplest weapons that give weaponcrafting XP
            level_0_items = [
                {
                    'code': 'wooden_stick',
                    'materials': [{'code': 'ash_wood', 'quantity': 2}]
                }
            ]
            
            # For now, focus on items that can be crafted at skill level 0
            if current_skill == 0:
                for item_option in level_0_items:
                    item_code = item_option['code']
                    materials_needed = item_option['materials']
                    
                    # Check if we have all required materials
                    can_craft = True
                    for material in materials_needed:
                        material_code = material['code']
                        required_quantity = material['quantity']
                        available_quantity = inventory_lookup.get(material_code, 0)
                        
                        if available_quantity < required_quantity:
                            can_craft = False
                            break
                    
                    if can_craft:
                        self.logger.info(f"Selected {item_code} for crafting (skill level {current_skill})")
                        return item_code
            
            # If no level 0 items are craftable, we might need to gather materials first
            self.logger.warning("No craftable items found for current skill level and materials")
            return None
            
        except Exception as e:
            self.logger.warning(f"Error selecting craft item: {e}")
            return None

    def __repr__(self):
        return "UpgradeWeaponcraftingSkillAction()"