"""
Upgrade Weaponcrafting Skill Action

This action handles leveling up the weaponcrafting skill by crafting simple items
that provide skill experience while being accessible to low-level characters.
"""

from typing import Dict, List, Optional
import logging
from artifactsmmo_api_client.api.characters.get_character_name import sync as get_character_api
from artifactsmmo_api_client.api.my_characters.action_crafting_my_name import sync as craft_api
from .base import ActionBase


class UpgradeWeaponcraftingSkillAction(ActionBase):
    """
    Action to upgrade weaponcrafting skill through strategic item crafting.
    
    Focuses on crafting simple weapons that provide skill XP while being
    accessible to characters with low skill levels and basic materials.
    """

    # GOAP parameters
    conditions = {
        "character_alive": True,
        "at_workshop": True,
        "has_materials": True
    }
    reactions = {
        "weaponcrafting_level_sufficient": True,
        "skill_xp_gained": True,
        "character_stats_improved": True
    }
    weights = {"weaponcrafting_level_sufficient": 30}

    def __init__(self, character_name: str, target_level: int = 1, current_level: int = 0):
        """
        Initialize the weaponcrafting skill upgrade action.

        Args:
            character_name: Name of the character
            target_level: Target weaponcrafting level to reach
            current_level: Current weaponcrafting level
        """
        super().__init__()
        self.character_name = character_name
        self.target_level = target_level
        self.current_level = current_level
        self.logger = logging.getLogger(__name__)

    def execute(self, client, **kwargs) -> Optional[Dict]:
        """Execute weaponcrafting skill upgrade through item crafting."""
        if not self.validate_execution_context(client):
            return self.get_error_response("No API client provided")
            
        self.log_execution_start(
            character_name=self.character_name,
            target_level=self.target_level,
            current_level=self.current_level
        )
        
        try:
            # Get current character data to check skill level and materials
            character_response = get_character_api(name=self.character_name, client=client)
            if not character_response or not character_response.data:
                return self.get_error_response("Could not get character data")
            
            character_data = character_response.data
            current_skill_level = getattr(character_data, 'weaponcrafting_level', 0)
            
            # Check if we've already reached the target level
            if current_skill_level >= self.target_level:
                result = self.get_success_response(
                    skill_level_achieved=True,
                    current_weaponcrafting_level=current_skill_level,
                    target_level=self.target_level,
                    message=f"Already at weaponcrafting level {current_skill_level}"
                )
                self.log_execution_result(result)
                return result
            
            # Determine what to craft based on current skill level and available materials
            craft_item = self._select_craft_item(character_data)
            if not craft_item:
                return self.get_error_response("No suitable items to craft for skill upgrade")
            
            # Attempt to craft the item
            self.logger.info(f"🔨 Crafting {craft_item} to gain weaponcrafting experience")
            craft_response = craft_api(name=self.character_name, code=craft_item, client=client)
            
            if not craft_response:
                return self.get_error_response(f"Failed to craft {craft_item}")
            
            # Check if crafting was successful
            craft_data = craft_response.data if hasattr(craft_response, 'data') else {}
            
            # Get updated character data to check skill progress
            updated_character_response = get_character_api(name=self.character_name, client=client)
            if updated_character_response and updated_character_response.data:
                new_skill_level = getattr(updated_character_response.data, 'weaponcrafting_level', current_skill_level)
                skill_gained = new_skill_level - current_skill_level
                
                result = self.get_success_response(
                    item_crafted=craft_item,
                    skill_xp_gained=skill_gained > 0,
                    previous_skill_level=current_skill_level,
                    current_weaponcrafting_level=new_skill_level,
                    target_level=self.target_level,
                    target_achieved=new_skill_level >= self.target_level,
                    craft_response=craft_data
                )
            else:
                # Fallback result if we can't get updated character data
                result = self.get_success_response(
                    item_crafted=craft_item,
                    skill_xp_gained=True,  # Assume success
                    current_weaponcrafting_level=current_skill_level,
                    target_level=self.target_level,
                    craft_response=craft_data
                )
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Weaponcrafting skill upgrade failed: {str(e)}")
            self.log_execution_result(error_response)
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
        return f"UpgradeWeaponcraftingSkillAction({self.character_name}, target={self.target_level})"