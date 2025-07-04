""" MapLookupAction module """

from artifactsmmo_api_client.api.maps.get_map_maps_x_y_get import sync as get_map_api

from src.lib.action_context import ActionContext

from .base import ActionBase, ActionResult


class MapLookupAction(ActionBase):
    """ Map lookup action to get information about a specific map location """
    
    # GOAP parameters - can be overridden by configuration
    conditions = {
            'character_status': {
                'alive': True,
                'cooldown_active': False,
            },
        }
    reactions = {
            'location_context': {
                'at_target': True,
            },
        }
    weight = 1.0  # Low priority utility action

    def __init__(self):
        super().__init__()

    def execute(self, client, context: ActionContext) -> ActionResult:
        """ Get map information for the specified coordinates """
        # Get coordinates from context
        x = context.get('x')
        y = context.get('y')
        
        if x is None or y is None:
            return self.create_error_result("No coordinates provided")
            
        self._context = context
        
        try:
            response = get_map_api(
                x=x,
                y=y,
                client=client
            )
            
            if response and response.data:
                # Convert response to standardized dict
                result = self.create_success_result(
                    x=x,
                    y=y,
                    name=response.data.name,
                    skin=response.data.skin
                )
                
                # Add content information if available
                if response.data.content:
                    result.data['content'] = {
                        'type': response.data.content.type_.value if hasattr(response.data.content.type_, 'value') else str(response.data.content.type_),
                        'code': response.data.content.code
                    }
                else:
                    result.data['content'] = None
                    
                return result
            else:
                error_response = self.create_error_result("No map data returned", x=x, y=y)
                return error_response
                
        except Exception as e:
            error_response = self.create_error_result(f"Map lookup failed: {str(e)}", x=x, y=y)
            return error_response

    def __repr__(self):
        return "MapLookupAction()"
