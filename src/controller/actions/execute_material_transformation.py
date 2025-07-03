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
from .base import ActionBase


class ExecuteMaterialTransformationAction(ActionBase):
    """
    Bridge action to execute a single material transformation.
    
    This action assumes the character is already at the correct workshop
    and executes the crafting/transformation of raw materials.
    """
    
    def __init__(self):
        """Initialize execute material transformation action."""
        super().__init__()
        
    def execute(self, client, context: ActionContext) -> Dict[str, Any]:
        """
        Execute material transformation.
        
        Args:
            client: API client
            context: Action context containing:
                - character_name: Name of character
                - raw_material: Raw material to transform
                - refined_material: Target refined material
                - quantity: Quantity to transform
                - action_config: Optional configuration
                
        Returns:
            Dict with transformation results
        """
        try:
            character_name = context.character_name
            raw_material = context.get('raw_material')
            refined_material = context.get('refined_material')
            quantity = context.get('quantity', 1)
            
            if not all([raw_material, refined_material]):
                return self.get_error_response("Missing transformation parameters")
            
            self.logger.info(f"🔥 Transforming {quantity}x {raw_material} → {refined_material}")
            
            # Check for cooldown before crafting
            self._wait_for_cooldown(client, character_name, context)
            
            # Execute crafting
            crafting_schema = CraftingSchema(code=refined_material, quantity=quantity)
            craft_response = crafting_api(name=character_name, client=client, body=crafting_schema)
            
            if not craft_response or not hasattr(craft_response, 'data') or not craft_response.data:
                return self.get_error_response(f"Crafting failed for {refined_material}")
            
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
            
            self.logger.info(f"✅ Successfully transformed {raw_material} → {refined_material}")
            
            # Store results in context
            transformation_result = {
                'raw_material': raw_material,
                'refined_material': refined_material,
                'quantity_requested': quantity,
                'items_produced': items_produced,
                'xp_gained': xp_gained,
                'success': True
            }
            
            context.set_result('last_transformation', transformation_result)
            
            return self.get_success_response(
                transformation=transformation_result,
                items_produced=items_produced,
                xp_gained=xp_gained
            )
            
        except Exception as e:
            return self.get_error_response(f"Failed to execute transformation: {e}")
    
    def _wait_for_cooldown(self, client, character_name: str, context: ActionContext):
        """Wait for cooldown if active."""
        try:
            from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api
            
            char_response = get_character_api(name=character_name, client=client)
            if char_response and char_response.data and char_response.data.cooldown > 0:
                cooldown_seconds = char_response.data.cooldown
                
                # Get cooldown buffer from config
                action_config = context.get('action_config', {})
                cooldown_buffer = action_config.get('cooldown_buffer_seconds', 1)
                
                total_wait = cooldown_seconds + cooldown_buffer
                
                self.logger.info(f"⏳ Waiting {cooldown_seconds}s for cooldown...")
                time.sleep(total_wait)
                self.logger.info("✅ Cooldown complete")
                
        except Exception as e:
            self.logger.warning(f"Could not check cooldown: {e}")
    
    def __repr__(self):
        return "ExecuteMaterialTransformationAction()"