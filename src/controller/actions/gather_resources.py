""" GatherResourcesAction module """

from typing import Dict, Optional

from artifactsmmo_api_client.api.maps.get_map_maps_x_y_get import sync as get_map_api
from artifactsmmo_api_client.api.my_characters.action_gathering_my_name_action_gathering_post import (
    sync as gathering_api,
)
from artifactsmmo_api_client.api.resources.get_resource_resources_code_get import sync as get_resource_api

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters

from .base import ActionBase, ActionResult


class GatherResourcesAction(ActionBase):
    """ Action to gather resources from the current map location """

    def __init__(self):
        """
        Initialize the gather resources action.
        """
        super().__init__()

    def execute(self, client, context: ActionContext) -> ActionResult:
        """ Gather resources from the current location """
            
        # Get parameters from context
        character_name = context.get(StateParameters.CHARACTER_NAME)
        target_resource = context.get('target_resource')
        
        self._context = context
        
        try:
            # Get character position from context
            character_x = context.get(StateParameters.CHARACTER_X)
            character_y = context.get(StateParameters.CHARACTER_Y)
            
            # If position not in context, try to get from character cache
            if character_x is None or character_y is None:
                character_response = getattr(client, '_character_cache', None)
                if not character_response:
                    return self.create_error_result("No character data or position available")
                    
                character_x = character_response.data.x
                character_y = character_response.data.y
            
            # Get map information for resource details
            # Note: Resource presence and match are now validated by ActionValidator
            map_response = get_map_api(x=character_x, y=character_y, client=client)
            if not map_response or not map_response.data:
                return self.create_error_result("Could not get map information", location=(character_x, character_y))
                
            map_data = map_response.data
            resource_code = map_data.content.code if hasattr(map_data, 'content') and map_data.content else 'unknown'
            
            # Get resource details for validation
            resource_details = get_resource_api(code=resource_code, client=client)
            if not resource_details or not resource_details.data:
                return self.create_error_result(
                    f'Could not get details for resource {resource_code}',
                    location=(character_x, character_y)
                )
            
            # Perform the gathering action
            gathering_response = gathering_api(name=character_name, client=client)
            
            if gathering_response and gathering_response.data:
                # Extract useful information from the response
                skill_data = gathering_response.data
                
                # Build additional data dictionary
                additional_data = {
                    'resource_code': resource_code,
                    'resource_name': resource_details.data.name,
                    'location': (character_x, character_y),
                    'cooldown': getattr(skill_data.cooldown, 'total_seconds', 0) if hasattr(skill_data, 'cooldown') else 0,
                    'xp_gained': getattr(skill_data, 'xp', 0),
                    'skill': getattr(skill_data, 'skill', 'unknown')
                }
                
                # Add character data if available
                if hasattr(skill_data, 'character'):
                    char_data = skill_data.character
                    additional_data['character_level'] = getattr(char_data, 'level', 0)
                    additional_data['character_hp'] = getattr(char_data, 'hp', 0)
                    additional_data['character_max_hp'] = getattr(char_data, 'max_hp', 0)
                
                # Add items obtained if available
                if hasattr(skill_data, 'details') and hasattr(skill_data.details, 'items'):
                    additional_data['items_obtained'] = []
                    for item in skill_data.details.items:
                        additional_data['items_obtained'].append({
                            'code': getattr(item, 'code', ''),
                            'quantity': getattr(item, 'quantity', 0)
                        })
                
                return self.create_success_result(
                    "Successfully gathered resources",
                    **additional_data
                )
            else:
                return self.create_error_result('Gathering action failed - no response data', location=(character_x, character_y))
                
        except Exception as e:
            return self.create_error_result(f'Gathering action failed: {str(e)}')
    
    def _verify_location_and_resource(self, client, character_x: int, character_y: int, target_resource: Optional[str]) -> Dict[str, any]:
        """Verify that the character is at the correct location to gather the target resource."""
        try:
            # Get map information for resource details
            map_response = get_map_api(x=character_x, y=character_y, client=client)
            if not map_response or not map_response.data:
                return {
                    'valid': False,
                    'error': 'Could not get map information'
                }
            
            map_data = map_response.data
            
            # Check if current location has a resource
            if not hasattr(map_data, 'content') or not map_data.content:
                return {
                    'valid': False,
                    'error': 'Current location has no resource'
                }
            
            if not hasattr(map_data.content, 'type_') or map_data.content.type_ != 'resource':
                return {
                    'valid': False,
                    'error': 'Current location is not a resource node'
                }
            
            resource_code = getattr(map_data.content, 'code', 'unknown')
            
            # Get resource details for validation
            resource_details = get_resource_api(code=resource_code, client=client)
            if not resource_details or not resource_details.data:
                return {
                    'valid': False,
                    'error': f'Could not get details for resource {resource_code}',
                    'current_resource': resource_code
                }
            
            # If target resource is specified, verify it matches current location
            if target_resource and target_resource != resource_code:
                return {
                    'valid': False,
                    'error': f'Wrong resource type. Need {target_resource}, currently at {resource_code}',
                    'target_resource': target_resource,
                    'current_resource': resource_code
                }
            
            return {
                'valid': True,
                'resource_code': resource_code,
                'resource_details': resource_details
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f'Location verification failed: {str(e)}'
            }

    def __repr__(self):
        return "GatherResourcesAction()"