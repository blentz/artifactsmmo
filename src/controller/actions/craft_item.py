""" CraftItemAction module """

import time
from typing import Dict, Optional
from artifactsmmo_api_client.api.my_characters.action_crafting_my_name import sync as crafting_api
from artifactsmmo_api_client.api.items.get_item import sync as get_item_api
from artifactsmmo_api_client.api.maps.get_map_x_y import sync as get_map_api
from artifactsmmo_api_client.api.characters.get_character_name import sync as get_character_api
from artifactsmmo_api_client.models.crafting_schema import CraftingSchema
from .base import ActionBase


class CraftItemAction(ActionBase):
    """ Action to craft items at workshop locations """

    def __init__(self, character_name: str, item_code: str, quantity: int = 1):
        """
        Initialize the craft item action.

        Args:
            character_name: Name of the character performing the action
            item_code: Code of the item to craft
            quantity: Number of items to craft (default: 1)
        """
        super().__init__()
        self.character_name = character_name
        self.item_code = item_code
        self.quantity = quantity

    def execute(self, client, **kwargs) -> Optional[Dict]:
        """ Craft the specified item """
        if not self.validate_execution_context(client):
            return self.get_error_response("No API client provided")
            
        self.log_execution_start(character_name=self.character_name, item_code=self.item_code, quantity=self.quantity)
        
        try:
            # Get current character position from cache or API
            character_x, character_y = None, None
            
            # Try to get from client cache first
            if hasattr(client, '_character_cache') and client._character_cache:
                if hasattr(client._character_cache, 'data') and client._character_cache.data:
                    character_x = client._character_cache.data.x
                    character_y = client._character_cache.data.y
            
            # If cache not available, get from API
            if character_x is None or character_y is None:
                character_response = get_character_api(name=self.character_name, client=client)
                
                if not character_response or not character_response.data:
                    error_response = self.get_error_response('No character data available')
                    self.log_execution_result(error_response)
                    return error_response
                    
                character_x = character_response.data.x
                character_y = character_response.data.y
            
            # Get map information to verify workshop
            map_response = get_map_api(x=character_x, y=character_y, client=client)
            if not map_response or not map_response.data:
                return {
                    'success': False,
                    'error': 'Could not get map information',
                    'location': (character_x, character_y)
                }
                
            map_data = map_response.data
            
            # Check if there's a workshop at this location
            has_content = hasattr(map_data, 'content') and map_data.content
            is_workshop = (has_content and 
                          hasattr(map_data.content, 'type_') and 
                          map_data.content.type_ == 'workshop')
            
            if not is_workshop:
                return {
                    'success': False,
                    'error': 'No workshop available at current location',
                    'location': (character_x, character_y),
                    'map_content_type': getattr(map_data.content, 'type_', 'none') if has_content else 'none'
                }
            
            workshop_code = getattr(map_data.content, 'code', 'unknown')
            
            # Get item details for validation
            item_details = get_item_api(code=self.item_code, client=client)
            if not item_details or not item_details.data:
                return {
                    'success': False,
                    'error': f'Could not get details for item {self.item_code}',
                    'location': (character_x, character_y)
                }
            
            # Check workshop compatibility with item crafting requirements
            item_data = item_details.data
            required_skill = None
            if hasattr(item_data, 'craft') and item_data.craft:
                required_skill = getattr(item_data.craft, 'skill', None)
                if required_skill:
                    # Skills and workshops have the same names, so direct comparison
                    if workshop_code != required_skill:
                        return {
                            'success': False,
                            'error': f'Workshop type mismatch: item requires {required_skill} skill but at {workshop_code} workshop',
                            'location': (character_x, character_y),
                            'workshop_code': workshop_code,
                            'required_skill': required_skill,
                            'expected_workshop': required_skill,
                            'item_code': self.item_code
                        }
            
            # Prepare crafting schema
            crafting_schema = CraftingSchema(
                code=self.item_code,
                quantity=self.quantity
            )
            
            # Perform the crafting action with retry logic
            max_retries = 3
            base_delay = 1.0  # Start with 1 second delay
            
            for attempt in range(max_retries):
                try:
                    crafting_response = crafting_api(
                        name=self.character_name, 
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
                            return {
                                'success': False,
                                'error': f'Workshop not found on map - API returned HTTP 598. Expected {required_skill or "unknown"} workshop, found {workshop_code}',
                                'location': (character_x, character_y),
                                'workshop_code': workshop_code,
                                'api_error': error_msg,
                                'item_code': self.item_code,
                                'attempts': attempt + 1
                            }
                        else:
                            return {
                                'success': False,
                                'error': f'Crafting API call failed after {attempt + 1} attempts: {error_msg}',
                                'location': (character_x, character_y),
                                'api_error': error_msg,
                                'attempts': attempt + 1
                            }
                    
                    # Calculate exponential backoff delay
                    delay = base_delay * (2 ** attempt)
                    print(f"Crafting attempt {attempt + 1} failed with {error_msg}, retrying in {delay} seconds...")
                    time.sleep(delay)
            
            if crafting_response and crafting_response.data:
                # Extract useful information from the response
                skill_data = crafting_response.data
                result = {
                    'success': True,
                    'item_code': self.item_code,
                    'item_name': item_details.data.name,
                    'quantity_crafted': self.quantity,
                    'workshop_code': workshop_code,
                    'location': (character_x, character_y),
                    'cooldown': getattr(skill_data.cooldown, 'total_seconds', 0) if hasattr(skill_data, 'cooldown') else 0,
                    'xp_gained': getattr(skill_data, 'xp', 0),
                    'skill': getattr(skill_data, 'skill', 'unknown')
                }
                
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
                return {
                    'success': False,
                    'error': 'Crafting action failed - no response data',
                    'location': (character_x, character_y)
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Crafting action failed: {str(e)}',
                'location': getattr(self, '_last_location', (0, 0))
            }

    def __repr__(self):
        return f"CraftItemAction({self.character_name}, {self.item_code}, qty={self.quantity})"