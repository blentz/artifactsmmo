""" MapLookupAction module """

from artifactsmmo_api_client.api.maps.get_map_x_y import sync as get_map_api
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

    def __init__(self, x, y):
        super().__init__()
        self.x = x
        self.y = y

    def execute(self, client, **kwargs):
        """ Get map information for the specified coordinates """
        if not self.validate_execution_context(client):
            return self.get_error_response("No API client provided")
            
        self.log_execution_start(x=self.x, y=self.y)
        
        try:
            response = get_map_api(
                x=self.x,
                y=self.y,
                client=client
            )
            self.log_execution_result(response)
            return response
        except Exception as e:
            error_response = self.get_error_response(f"Map lookup failed: {str(e)}", x=self.x, y=self.y)
            self.log_execution_result(error_response)
            return error_response

    def __repr__(self):
        return f"MapLookupAction({self.x}, {self.y})"
