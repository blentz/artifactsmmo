"""
Execute Material Transformation Action

This bridge action executes a single material transformation
at the current workshop.
"""

import time
from typing import Dict, Any

from artifactsmmo_api_client.api.my_characters.action_crafting_my_name_action_crafting_post import sync as crafting_api
from artifactsmmo_api_client.models.crafting_schema import CraftingSchema

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from src.controller.knowledge.base import KnowledgeBase
from .base import ActionBase, ActionResult


class ExecuteMaterialTransformationAction(ActionBase):
    """
    Bridge action to execute a single material transformation.
    
    This action assumes the character is already at the correct workshop
    and executes the crafting/transformation of raw materials.
    """
    
    def __init__(self):
        """Initialize execute material transformation action."""
        super().__init__()
        
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Execute material transformation based on recipe.
        
        Args:
            client: API client
            context: Action context containing:
                - character_name: Name of character
                - target_recipe: Recipe code to execute
                - quantity: Quantity to craft (optional, defaults to 1)
                
        Returns:
            ActionResult with transformation results
        """
        self._context = context
        
        try:
            character_name = context.get(StateParameters.CHARACTER_NAME)
            target_recipe = context.get(StateParameters.TARGET_RECIPE)
            quantity = context.get(StateParameters.QUANTITY, 1)
            
            if not target_recipe:
                return self.create_error_result("Missing target recipe parameter")
                
            # Get recipe data from knowledge base
            knowledge_base = getattr(context, 'knowledge_base', None) or KnowledgeBase()
            
            recipe_data = knowledge_base.get_item_data(target_recipe, client=client)
            if not recipe_data:
                return self.create_error_result(f"Recipe not found: {target_recipe}")
                
            craft_info = recipe_data.get('craft')
            if not craft_info:
                return self.create_error_result(f"No craft information for recipe: {target_recipe}")
                
            # Extract the item code to craft (the output of the transformation)
            item_to_craft = target_recipe  # For most cases, recipe code == item code
            
            self.logger.info(f"🔥 Executing recipe {target_recipe} (quantity: {quantity})")
            
            # Check for cooldown before crafting
            self._wait_for_cooldown(client, character_name, context)
            
            # Execute crafting using the target recipe (item code)
            crafting_schema = CraftingSchema(code=item_to_craft, quantity=quantity)
            craft_response = crafting_api(name=character_name, client=client, body=crafting_schema)
            
            if not craft_response or not hasattr(craft_response, 'data') or not craft_response.data:
                return self.create_error_result(f"Crafting failed for recipe {target_recipe}")
            
            craft_data = craft_response.data
            
            # Extract results
            items_produced = []
            if hasattr(craft_data, 'items') and craft_data.items:
                for item in craft_data.items:
                    if hasattr(item, 'code') and hasattr(item, 'quantity'):
                        items_produced.append({
                            'code': item.code,
                            'quantity': item.quantity
                        })
            
            xp_gained = getattr(craft_data, 'xp', 0)
            
            self.logger.info(f"✅ Successfully executed recipe {target_recipe}")
            
            # Store results in context
            transformation_result = {
                'target_recipe': target_recipe,
                'item_crafted': item_to_craft,
                'quantity_requested': quantity,
                'items_produced': items_produced,
                'xp_gained': xp_gained,
                'success': True
            }
            
            context.set_result(StateParameters.LAST_TRANSFORMATION, transformation_result)
            
            return self.create_success_result(
                message=f"Successfully executed recipe {target_recipe}",
                transformation=transformation_result,
                items_produced=items_produced,
                xp_gained=xp_gained
            )
            
        except Exception as e:
            return self.create_error_result(f"Failed to execute transformation: {e}")
    
    def _wait_for_cooldown(self, client, character_name: str, context: ActionContext):
        """Wait for cooldown if active."""
        try:
            from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api
            
            char_response = get_character_api(name=character_name, client=client)
            if char_response and char_response.data and char_response.data.cooldown > 0:
                cooldown_seconds = char_response.data.cooldown
                
                # Use default cooldown buffer (no nested config)
                cooldown_buffer = 1  # Default buffer seconds
                
                total_wait = cooldown_seconds + cooldown_buffer
                
                self.logger.info(f"⏳ Waiting {cooldown_seconds}s for cooldown...")
                time.sleep(total_wait)
                self.logger.info("✅ Cooldown complete")
                
        except Exception as e:
            self.logger.warning(f"Could not check cooldown: {e}")
    
    def __repr__(self):
        return "ExecuteMaterialTransformationAction()"