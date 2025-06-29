""" MoveToResourceAction module """

from typing import Dict, Optional
from artifactsmmo_api_client.api.my_characters.action_move_my_name import sync as move_character_api
from artifactsmmo_api_client.models.destination_schema import DestinationSchema
from .base import ActionBase


class MoveToResourceAction(ActionBase):
    """ Action to move character to a resource location """

    # GOAP parameters
    conditions = {"character_alive": True, "can_move": True, "resource_location_known": True}
    reactions = {"at_resource_location": True, "at_target_location": True}
    weights = {"at_resource_location": 10}

    def __init__(self, char_name: str, target_x: int, target_y: int):
        """
        Initialize the move to resource action.

        Args:
            char_name: Character name
            target_x: Target X coordinate for resource location
            target_y: Target Y coordinate for resource location
        """
        super().__init__()
        self.char_name = char_name
        self.target_x = target_x
        self.target_y = target_y

    def execute(self, client, **kwargs) -> Optional[Dict]:
        """ Move character to the resource location """
        if not self.validate_execution_context(client):
            return self.get_error_response("No API client provided")
            
        if not self.char_name:
            return self.get_error_response("No character name provided")
            
        self.log_execution_start(
            char_name=self.char_name,
            target_x=self.target_x,
            target_y=self.target_y
        )
        
        try:
            # Move to the resource location
            destination = DestinationSchema(
                x=self.target_x,
                y=self.target_y
            )
            response = move_character_api(
                name=self.char_name,
                client=client,
                body=destination
            )
            
            if response and hasattr(response, 'data'):
                # Extract character coordinates from the response
                character_data = response.data.character if hasattr(response.data, 'character') else None
                actual_x = getattr(character_data, 'x', self.target_x) if character_data else self.target_x
                actual_y = getattr(character_data, 'y', self.target_y) if character_data else self.target_y
                
                success_response = self.get_success_response(
                    character_x=actual_x,
                    character_y=actual_y,
                    target_x=self.target_x,
                    target_y=self.target_y,
                    at_resource_location=True,
                    response=response
                )
                self.log_execution_result(success_response)
                return success_response
            else:
                error_response = self.get_error_response("Move action failed - no response data")
                self.log_execution_result(error_response)
                return error_response
                
        except Exception as e:
            # Handle "Character already at destination" as success
            error_msg = str(e)
            if "490" in error_msg and "already at destination" in error_msg.lower():
                # Character is already at the target location - this is success
                success_response = self.get_success_response(
                    character_x=self.target_x,
                    character_y=self.target_y,
                    target_x=self.target_x,
                    target_y=self.target_y,
                    at_resource_location=True,
                    already_at_destination=True
                )
                self.log_execution_result(success_response)
                return success_response
            else:
                error_response = self.get_error_response(f"Move to resource failed: {str(e)}")
                self.log_execution_result(error_response)
                return error_response

    def __repr__(self):
        return f"MoveToResourceAction({self.char_name}, {self.target_x}, {self.target_y})"