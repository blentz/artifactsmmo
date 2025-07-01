""" MapLookupAction module """

from artifactsmmo_api_client.api.maps.get_map_maps_x_y_get import sync as get_map_api

from src.lib.action_context import ActionContext

from .base import ActionBase


class MapLookupAction(ActionBase):
    """ Map lookup action to get information about a specific map location """
    
    # GOAP parameters - can be overridden by configuration
    conditions = {
        'character_alive': True,
        'can_move': True
    }
    reactions = {
        'at_target_location': True  # Assumes we move to lookup location
    }
    weights = {'map_lookup': 1.0}  # Low priority utility action

    def __init__(self):
        super().__init__()

    def execute(self, client, context: ActionContext):
        """ Get map information for the specified coordinates """
        if not self.validate_execution_context(client, context):
            return self.get_error_response("No API client provided")
        
        # Get coordinates from context
        x = context.get('x')
        y = context.get('y')
        
        if x is None or y is None:
            return self.get_error_response("No coordinates provided")
            
        self.log_execution_start(x=x, y=y)
        
        try:
            response = get_map_api(
                x=x,
                y=y,
                client=client
            )
            
            if response and response.data:
                # Convert response to standardized dict
                result = self.get_success_response(
                    x=x,
                    y=y,
                    name=response.data.name,
                    skin=response.data.skin
                )
                
                # Add content information if available
                if response.data.content:
                    result['content'] = {
                        'type': response.data.content.type_.value if hasattr(response.data.content.type_, 'value') else str(response.data.content.type_),
                        'code': response.data.content.code
                    }
                else:
                    result['content'] = None
                    
                self.log_execution_result(result)
                return result
            else:
                error_response = self.get_error_response("No map data returned", x=x, y=y)
                self.log_execution_result(error_response)
                return error_response
                
        except Exception as e:
            error_response = self.get_error_response(f"Map lookup failed: {str(e)}", x=x, y=y)
            self.log_execution_result(error_response)
            return error_response

    def __repr__(self):
        return "MapLookupAction()"
