""" MoveAction module """

from artifactsmmo_api_client.api.my_characters.action_move_my_name import sync as move_character_api
from artifactsmmo_api_client.models.destination_schema import DestinationSchema
from .base import ActionBase

class MoveAction(ActionBase):
    """ Move character action """
    
    # GOAP parameters - can be overridden by configuration
    conditions = {
        'can_move': True,
        'character_alive': True
    }
    reactions = {
        'at_target_location': True
    }
    weights = {'move': 1.0}

    def __init__(self, char_name, x=None, y=None, use_target_coordinates=False):
        super().__init__()
        self.char_name = char_name
        self.x = x
        self.y = y
        self.use_target_coordinates = use_target_coordinates

    def execute(self, client, **kwargs):
        """ Move the character to new coordinates """
        if not self.validate_execution_context(client):
            return self.get_error_response("No API client provided")
        
        # Handle coordinates from action context if needed
        target_x, target_y = self._get_target_coordinates(kwargs)
        
        if target_x is None or target_y is None:
            return self.get_error_response("No valid coordinates provided for move action")
            
        self.log_execution_start(char_name=self.char_name, x=target_x, y=target_y)
        
        try:
            destination = DestinationSchema(
                x=target_x,
                y=target_y
            )
            response = move_character_api(
                name=self.char_name,
                client=client,
                body=destination
            )
            self.log_execution_result(response)
            return response
        except Exception as e:
            # Handle "already at destination" as success case
            error_str = str(e)
            if "490" in error_str and "already at destination" in error_str.lower():
                success_response = self.get_success_response(
                    message="Character already at destination",
                    x=target_x,
                    y=target_y,
                    char_name=self.char_name
                )
                self.log_execution_result(success_response)
                return success_response
            
            error_response = self.get_error_response(f"Move failed: {str(e)}", x=target_x, y=target_y)
            self.log_execution_result(error_response)
            return error_response
    
    def _get_target_coordinates(self, kwargs):
        """Get target coordinates from action parameters or context."""
        # If specific coordinates provided, use them
        if self.x is not None and self.y is not None:
            return self.x, self.y
        
        # If use_target_coordinates flag is set, get from action context
        if self.use_target_coordinates:
            # Check for coordinates in action context (from previous actions)
            if 'target_x' in kwargs and 'target_y' in kwargs:
                return kwargs['target_x'], kwargs['target_y']
            elif 'x' in kwargs and 'y' in kwargs:
                return kwargs['x'], kwargs['y']
        
        return None, None

    def __repr__(self):
        return f"MoveAction({self.char_name}, {self.x}, {self.y})"
