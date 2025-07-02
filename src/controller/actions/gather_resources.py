""" GatherResourcesAction module """

from typing import Dict, Optional

from artifactsmmo_api_client.api.maps.get_map_maps_x_y_get import sync as get_map_api
from artifactsmmo_api_client.api.my_characters.action_gathering_my_name_action_gathering_post import (
    sync as gathering_api,
)
from artifactsmmo_api_client.api.resources.get_resource_resources_code_get import sync as get_resource_api

from src.lib.action_context import ActionContext

from .base import ActionBase


class GatherResourcesAction(ActionBase):
    """ Action to gather resources from the current map location """

    def __init__(self):
        """
        Initialize the gather resources action.
        """
        super().__init__()

    def execute(self, client, context: ActionContext) -> Optional[Dict]:
        """ Gather resources from the current location """
            
        # Get parameters from context
        character_name = context.character_name
        target_resource = context.get('target_resource')
        
        self.log_execution_start(character_name=character_name, target_resource=target_resource)
        
        try:
            # Get character position from context
            character_x = context.character_x
            character_y = context.character_y
            
            # If position not in context, try to get from character cache
            if character_x is None or character_y is None:
                character_response = getattr(client, '_character_cache', None)
                if not character_response:
                    error_response = self.get_error_response("No character data or position available")
                    self.log_execution_result(error_response)
                    return error_response
                    
                character_x = character_response.data.x
                character_y = character_response.data.y
            
            # Get map information for resource details
            # Note: Resource presence and match are now validated by ActionValidator
            map_response = get_map_api(x=character_x, y=character_y, client=client)
            if not map_response or not map_response.data:
                error_response = self.get_error_response("Could not get map information", location=(character_x, character_y))
                self.log_execution_result(error_response)
                return error_response
                
            map_data = map_response.data
            resource_code = map_data.content.code if hasattr(map_data, 'content') and map_data.content else 'unknown'
            
            # Get resource details for validation
            resource_details = get_resource_api(code=resource_code, client=client)
            if not resource_details or not resource_details.data:
                error_response = self.get_error_response(
                    f'Could not get details for resource {resource_code}',
                    location=(character_x, character_y)
                )
                self.log_execution_result(error_response)
                return error_response
            
            # Perform the gathering action
            gathering_response = gathering_api(name=character_name, client=client)
            
            if gathering_response and gathering_response.data:
                # Extract useful information from the response
                skill_data = gathering_response.data
                result = self.get_success_response(
                    resource_code=resource_code,
                    resource_name=resource_details.data.name,
                    location=(character_x, character_y),
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
                
                # Add items obtained if available
                if hasattr(skill_data, 'details') and hasattr(skill_data.details, 'items'):
                    result['items_obtained'] = []
                    for item in skill_data.details.items:
                        result['items_obtained'].append({
                            'code': getattr(item, 'code', ''),
                            'quantity': getattr(item, 'quantity', 0)
                        })
                
                self.log_execution_result(result)
                return result
            else:
                error_response = self.get_error_response('Gathering action failed - no response data', location=(character_x, character_y))
                self.log_execution_result(error_response)
                return error_response
                
        except Exception as e:
            error_response = self.get_error_response(f'Gathering action failed: {str(e)}')
            self.log_execution_result(error_response)
            return error_response

    def __repr__(self):
        return "GatherResourcesAction()"