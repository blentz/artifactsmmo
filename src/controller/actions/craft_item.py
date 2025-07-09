""" CraftItemAction module """

import time
from typing import Dict, Optional

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api
from artifactsmmo_api_client.api.items.get_item_items_code_get import sync as get_item_api
from artifactsmmo_api_client.api.maps.get_map_maps_x_y_get import sync as get_map_api
from artifactsmmo_api_client.api.my_characters.action_crafting_my_name_action_crafting_post import sync as crafting_api
from artifactsmmo_api_client.models.crafting_schema import CraftingSchema

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from src.game.globals import MaterialStatus

from .base import ActionBase, ActionResult
from .coordinate_mixin import CoordinateStandardizationMixin


class CraftItemAction(ActionBase, CoordinateStandardizationMixin):
    """ Action to craft items at workshop locations """

    # GOAP parameters
    conditions = {
        'location_context': {
            'at_workshop': True
        },
        'materials': {
            'status': MaterialStatus.SUFFICIENT
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

    def execute(self, client, context: ActionContext) -> ActionResult:
        """ Craft the specified item """
            
        # Get parameters from context
        character_name = context.get(StateParameters.CHARACTER_NAME)
        item_code = context.get('item_code')
        quantity = context.get('quantity', 1)
        
        self._context = context
        
        try:
            # Get current character position from context
            character_x = context.get(StateParameters.CHARACTER_X)
            character_y = context.get(StateParameters.CHARACTER_Y)
            
            # If position not available, get from API
            if character_x is None or character_y is None:
                character_response = get_character_api(name=character_name, client=client)
                
                if not character_response or not character_response.data:
                    return self.create_error_result('No character data available')
                    
                character_x = character_response.data.x
                character_y = character_response.data.y
            
            # Get map information for workshop details
            # Note: Workshop presence and compatibility are now validated by ActionValidator
            map_response = get_map_api(x=character_x, y=character_y, client=client)
            if not map_response or not map_response.data:
                # Set coordinates directly on ActionContext for unified access
                if hasattr(self, '_context') and self._context:
                    self._context.target_x = character_x
                    self._context.target_y = character_y
                
                return self.create_error_result(
                    'Could not get map information',
                    target_x=character_x,
                    target_y=character_y
                )
                
            map_data = map_response.data
            workshop_code = getattr(map_data.content, 'code', 'unknown') if hasattr(map_data, 'content') else 'unknown'
            
            # Get item details for response enrichment
            item_details = get_item_api(code=item_code, client=client)
            if not item_details or not item_details.data:
                # Set coordinates directly on ActionContext for unified access
                if hasattr(self, '_context') and self._context:
                    self._context.target_x = character_x
                    self._context.target_y = character_y
                
                return self.create_error_result(
                    f'Could not get details for item {item_code}',
                    target_x=character_x,
                    target_y=character_y
                )
            
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
                            # Set coordinates directly on ActionContext for unified access
                            if hasattr(self, '_context') and self._context:
                                self._context.target_x = character_x
                                self._context.target_y = character_y
                                self._context.workshop_code = workshop_code
                                self._context.item_code = item_code
                            
                            return self.create_error_result(
                                f'Workshop not found on map - API returned HTTP 598. Found {workshop_code} workshop',
                                workshop_code=workshop_code,
                                api_error=error_msg,
                                item_code=item_code,
                                attempts=attempt + 1
                            )
                        else:
                            # Set coordinates directly on ActionContext for unified access
                            if hasattr(self, '_context') and self._context:
                                self._context.target_x = character_x
                                self._context.target_y = character_y
                            
                            return self.create_error_result(
                                f'Crafting API call failed after {attempt + 1} attempts: {error_msg}',
                                api_error=error_msg,
                                attempts=attempt + 1
                            )
                    
                    # Calculate exponential backoff delay
                    delay = base_delay * (2 ** attempt)
                    self.logger.info(f"Crafting attempt {attempt + 1} failed with {error_msg}, retrying in {delay} seconds...")
                    time.sleep(delay)
            
            if crafting_response and crafting_response.data:
                # Extract useful information from the response
                skill_data = crafting_response.data
                
                # Set coordinates directly on ActionContext for unified access
                if hasattr(self, '_context') and self._context:
                    self._context.target_x = character_x
                    self._context.target_y = character_y
                    self._context.item_code = item_code
                    self._context.workshop_code = workshop_code
                
                success_data = {
                    'item_code': item_code,
                    'item_name': item_details.data.name,
                    'quantity_crafted': quantity,
                    'workshop_code': workshop_code,
                    'cooldown': getattr(skill_data.cooldown, 'total_seconds', 0) if hasattr(skill_data, 'cooldown') else 0,
                    'xp_gained': getattr(skill_data, 'xp', 0),
                    'skill': getattr(skill_data, 'skill', 'unknown'),
                    'target_x': character_x,
                    'target_y': character_y
                }
                
                # Add character data if available
                if hasattr(skill_data, 'character'):
                    char_data = skill_data.character
                    success_data['character_level'] = getattr(char_data, 'level', 0)
                    success_data['character_hp'] = getattr(char_data, 'hp', 0)
                    success_data['character_max_hp'] = getattr(char_data, 'max_hp', 0)
                
                # Add items produced if available
                if hasattr(skill_data, 'details') and hasattr(skill_data.details, 'items'):
                    success_data['items_produced'] = []
                    for item in skill_data.details.items:
                        success_data['items_produced'].append({
                            'code': getattr(item, 'code', ''),
                            'quantity': getattr(item, 'quantity', 0)
                        })
                
                # Add materials consumed if available
                if hasattr(skill_data, 'details') and hasattr(skill_data.details, 'consumed'):
                    success_data['materials_consumed'] = []
                    for item in skill_data.details.consumed:
                        success_data['materials_consumed'].append({
                            'code': getattr(item, 'code', ''),
                            'quantity': getattr(item, 'quantity', 0)
                        })
                
                return self.create_success_result(
                    f'Successfully crafted {quantity} {item_details.data.name}',
                    **success_data
                )
            else:
                # Set coordinates directly on ActionContext for unified access
                if hasattr(self, '_context') and self._context:
                    self._context.target_x = character_x
                    self._context.target_y = character_y
                
                return self.create_error_result(
                    'Crafting action failed - no response data'
                )
                
        except Exception as e:
            # Set default coordinates on ActionContext if we don't have character position
            if hasattr(self, '_context') and self._context:
                self._context.target_x = 0
                self._context.target_y = 0
            
            return self.create_error_result(
                f'Crafting action failed: {str(e)}'
            )
    
    def _verify_workshop_compatibility(self, client, character_x: int, character_y: int, item_data) -> Dict[str, any]:
        """Verify that the character is at the correct workshop type for crafting the item."""
        try:
            # Get map information for workshop details
            map_response = get_map_api(x=character_x, y=character_y, client=client)
            if not map_response or not map_response.data:
                return {
                    'valid': False,
                    'error': 'Could not get map information'
                }
            
            map_data = map_response.data
            
            # Check if current location is a workshop
            if not hasattr(map_data, 'content') or not map_data.content:
                return {
                    'valid': False,
                    'error': 'Current location is not a workshop'
                }
            
            if not hasattr(map_data.content, 'type_') or map_data.content.type_ != 'workshop':
                return {
                    'valid': False,
                    'error': 'Current location is not a workshop'
                }
            
            current_workshop = getattr(map_data.content, 'code', 'unknown')
            
            # Determine required workshop type from item data
            required_workshop = None
            if hasattr(item_data, 'craft') and item_data.craft:
                required_workshop = getattr(item_data.craft, 'skill', None)
            
            if not required_workshop:
                return {
                    'valid': False,
                    'error': f'Item {item_data.code} is not craftable or has no skill requirement',
                    'current_workshop': current_workshop
                }
            
            # Check if current workshop matches required workshop
            if current_workshop != required_workshop:
                return {
                    'valid': False,
                    'error': f'Wrong workshop type. Need {required_workshop}, currently at {current_workshop}',
                    'required_workshop': required_workshop,
                    'current_workshop': current_workshop
                }
            
            return {
                'valid': True,
                'workshop_code': current_workshop
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f'Workshop verification failed: {str(e)}'
            }

    def __repr__(self):
        return "CraftItemAction()"
