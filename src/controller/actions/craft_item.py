""" CraftItemAction module """

from typing import Dict, Optional
from artifactsmmo_api_client.api.my_characters.action_crafting_my_name import sync as crafting_api
from artifactsmmo_api_client.api.items.get_item import sync as get_item_api
from artifactsmmo_api_client.api.maps.get_map_x_y import sync as get_map_api
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
            # First check if we're at a workshop location
            character_response = getattr(client, '_character_cache', None)
            if not character_response:
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
                    'location': (character_x, character_y)
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
            
            # Prepare crafting schema
            crafting_schema = CraftingSchema(
                code=self.item_code,
                quantity=self.quantity
            )
            
            # Perform the crafting action
            crafting_response = crafting_api(
                name=self.character_name, 
                client=client, 
                body=crafting_schema
            )
            
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