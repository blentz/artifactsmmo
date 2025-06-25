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

    def __init__(self, char_name, x, y):
        super().__init__()
        self.char_name = char_name
        self.x = x
        self.y = y

    def execute(self, client, **kwargs):
        """ Move the character to new coordinates """
        if not self.validate_execution_context(client):
            return self.get_error_response("No API client provided")
            
        self.log_execution_start(char_name=self.char_name, x=self.x, y=self.y)
        
        try:
            destination = DestinationSchema(
                x=self.x,
                y=self.y
            )
            response = move_character_api(
                name=self.char_name,
                client=client,
                body=destination
            )
            self.log_execution_result(response)
            return response
        except Exception as e:
            error_response = self.get_error_response(f"Move failed: {str(e)}", x=self.x, y=self.y)
            self.log_execution_result(error_response)
            return error_response

    def __repr__(self):
        return f"MoveAction({self.char_name}, {self.x}, {self.y})"
