""" GatherResourcesAction module """

from typing import Dict, Optional
from artifactsmmo_api_client.api.my_characters.action_gathering_my_name import sync as gathering_api
from artifactsmmo_api_client.api.resources.get_resource import sync as get_resource_api
from artifactsmmo_api_client.api.maps.get_map_x_y import sync as get_map_api
from .base import ActionBase


class GatherResourcesAction(ActionBase):
    """ Action to gather resources from the current map location """

    def __init__(self, character_name: str, target_resource: Optional[str] = None):
        """
        Initialize the gather resources action.

        Args:
            character_name: Name of the character performing the action
            target_resource: Specific resource to gather. If None, gathers any available resource.
        """
        super().__init__()
        self.character_name = character_name
        self.target_resource = target_resource

    def execute(self, client, **kwargs) -> Optional[Dict]:
        """ Gather resources from the current location """
        if not self.validate_execution_context(client):
            return self.get_error_response("No API client provided")
            
        self.log_execution_start(character_name=self.character_name, target_resource=self.target_resource)
        
        try:
            # Get character position from context or API
            character_x = kwargs.get('character_x')
            character_y = kwargs.get('character_y')
            
            # If position not in context, try to get from character cache
            if character_x is None or character_y is None:
                character_response = getattr(client, '_character_cache', None)
                if not character_response:
                    error_response = self.get_error_response("No character data or position available")
                    self.log_execution_result(error_response)
                    return error_response
                    
                character_x = character_response.data.x
                character_y = character_response.data.y
            
            # Get map information to see what resource is available
            map_response = get_map_api(x=character_x, y=character_y, client=client)
            if not map_response or not map_response.data:
                error_response = self.get_error_response("Could not get map information", location=(character_x, character_y))
                self.log_execution_result(error_response)
                return error_response
                
            map_data = map_response.data
            
            # Check if there's a resource at this location
            has_content = hasattr(map_data, 'content') and map_data.content
            is_resource = (has_content and 
                          hasattr(map_data.content, 'type_') and 
                          map_data.content.type_ == 'resource')
            
            if not is_resource:
                error_response = self.get_error_response('No resource available at current location', location=(character_x, character_y))
                self.log_execution_result(error_response)
                return error_response
            
            resource_code = map_data.content.code
            
            # Check if this matches our target resource (if specified)
            if self.target_resource and resource_code != self.target_resource:
                error_response = self.get_error_response(
                    f'Resource {resource_code} does not match target {self.target_resource}',
                    location=(character_x, character_y),
                    available_resource=resource_code
                )
                self.log_execution_result(error_response)
                return error_response
            
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
            gathering_response = gathering_api(name=self.character_name, client=client)
            
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
        target_str = f", target={self.target_resource}" if self.target_resource else ""
        return f"GatherResourcesAction({self.character_name}{target_str})"