""" CraftItemAction module """

import time
from typing import Dict, Optional

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api
from artifactsmmo_api_client.api.items.get_item_items_code_get import sync as get_item_api
from artifactsmmo_api_client.api.maps.get_map_maps_x_y_get import sync as get_map_api
from artifactsmmo_api_client.api.my_characters.action_crafting_my_name_action_crafting_post import sync as crafting_api
from artifactsmmo_api_client.models.crafting_schema import CraftingSchema

from src.lib.action_context import ActionContext

from .base import ActionBase
from .coordinate_mixin import CoordinateStandardizationMixin


class CraftItemAction(ActionBase, CoordinateStandardizationMixin):
    """ Action to craft items at workshop locations """

    # GOAP parameters
    conditions = {
        'location_context': {
            'at_workshop': True
        },
        'materials': {
            'status': 'sufficient'
        },
        'skill_status': {
            'sufficient': True
        },
        'character_status': {
            'alive': True,
            'cooldown_active': False
        }
    }
    reactions = {
        'equipment_status': {
            'item_crafted': True
        },
        'inventory': {
            'updated': True
        }
    }
    weight = 3

    def __init__(self):
        """
        Initialize the craft item action.
        """
        super().__init__()

    def execute(self, client, context: ActionContext) -> Optional[Dict]:
        """ Craft the specified item """
            
        # Get parameters from context
        character_name = context.character_name
        item_code = context.get('item_code')
        quantity = context.get('quantity', 1)
        
        self.log_execution_start(character_name=character_name, item_code=item_code, quantity=quantity)
        
        try:
            # Get current character position from context
            character_x = context.character_x
            character_y = context.character_y
            
            # If position not available, get from API
            if character_x is None or character_y is None:
                character_response = get_character_api(name=character_name, client=client)
                
                if not character_response or not character_response.data:
                    error_response = self.get_error_response('No character data available')
                    self.log_execution_result(error_response)
                    return error_response
                    
                character_x = character_response.data.x
                character_y = character_response.data.y
            
            # Get map information for workshop details
            # Note: Workshop presence and compatibility are now validated by ActionValidator
            map_response = get_map_api(x=character_x, y=character_y, client=client)
            if not map_response or not map_response.data:
                error_data = self.create_coordinate_response(
                    character_x, character_y,
                    success=False,
                    error='Could not get map information'
                )
                return error_data
                
            map_data = map_response.data
            workshop_code = getattr(map_data.content, 'code', 'unknown') if hasattr(map_data, 'content') else 'unknown'
            
            # Get item details for response enrichment
            item_details = get_item_api(code=item_code, client=client)
            if not item_details or not item_details.data:
                error_data = self.create_coordinate_response(
                    character_x, character_y,
                    success=False,
                    error=f'Could not get details for item {item_code}'
                )
                return error_data
            
            item_data = item_details.data
            
            # Prepare crafting schema
            crafting_schema = CraftingSchema(
                code=item_code,
                quantity=quantity
            )
            
            # Perform the crafting action with retry logic
            max_retries = 3
            base_delay = 1.0  # Start with 1 second delay
            
            for attempt in range(max_retries):
                try:
                    crafting_response = crafting_api(
                        name=character_name, 
                        client=client, 
                        body=crafting_schema
                    )
                    # If successful, break out of retry loop
                    break
                    
                except Exception as e:
                    error_msg = str(e)
                    is_timeout = any(keyword in error_msg.lower() for keyword in ['timeout', '598', 'network', 'connection'])
                    
                    # If this is the last attempt or not a timeout error, don't retry
                    if attempt == max_retries - 1 or not is_timeout:
                        if "598" in error_msg:
                            error_data = self.create_coordinate_response(
                                character_x, character_y,
                                success=False,
                                error=f'Workshop not found on map - API returned HTTP 598. Found {workshop_code} workshop',
                                workshop_code=workshop_code,
                                api_error=error_msg,
                                item_code=item_code,
                                attempts=attempt + 1
                            )
                            return error_data
                        else:
                            error_data = self.create_coordinate_response(
                                character_x, character_y,
                                success=False,
                                error=f'Crafting API call failed after {attempt + 1} attempts: {error_msg}',
                                api_error=error_msg,
                                attempts=attempt + 1
                            )
                            return error_data
                    
                    # Calculate exponential backoff delay
                    delay = base_delay * (2 ** attempt)
                    self.logger.info(f"Crafting attempt {attempt + 1} failed with {error_msg}, retrying in {delay} seconds...")
                    time.sleep(delay)
            
            if crafting_response and crafting_response.data:
                # Extract useful information from the response
                skill_data = crafting_response.data
                result = self.create_coordinate_response(
                    character_x, character_y,
                    success=True,
                    item_code=item_code,
                    item_name=item_details.data.name,
                    quantity_crafted=quantity,
                    workshop_code=workshop_code,
                    cooldown=getattr(skill_data.cooldown, 'total_seconds', 0) if hasattr(skill_data, 'cooldown') else 0,
                    xp_gained=getattr(skill_data, 'xp', 0),
                    skill=getattr(skill_data, 'skill', 'unknown')
                )
                
                # Add character data if available
                if hasattr(skill_data, 'character'):
                    char_data = skill_data.character
                    result['character_level'] = getattr(char_data, 'level', 0)
                    result['character_hp'] = getattr(char_data, 'hp', 0)
                    result['character_max_hp'] = getattr(char_data, 'max_hp', 0)
                
                # Add items produced if available
                if hasattr(skill_data, 'details') and hasattr(skill_data.details, 'items'):
                    result['items_produced'] = []
                    for item in skill_data.details.items:
                        result['items_produced'].append({
                            'code': getattr(item, 'code', ''),
                            'quantity': getattr(item, 'quantity', 0)
                        })
                
                # Add materials consumed if available
                if hasattr(skill_data, 'details') and hasattr(skill_data.details, 'consumed'):
                    result['materials_consumed'] = []
                    for item in skill_data.details.consumed:
                        result['materials_consumed'].append({
                            'code': getattr(item, 'code', ''),
                            'quantity': getattr(item, 'quantity', 0)
                        })
                
                return result
            else:
                error_data = self.create_coordinate_response(
                    character_x, character_y,
                    success=False,
                    error='Crafting action failed - no response data'
                )
                return error_data
                
        except Exception as e:
            # Use default coordinates if we don't have character position
            error_data = self.create_coordinate_response(
                0, 0,  # Default coordinates for exception case
                success=False,
                error=f'Crafting action failed: {str(e)}'
            )
            return error_data

    def __repr__(self):
        return "CraftItemAction()"
