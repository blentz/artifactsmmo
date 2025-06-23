""" MoveAction module """

from artifactsmmo_api_client.api.my_characters.action_move_my_name import sync as move_character_api
from artifactsmmo_api_client.models.destination_schema import DestinationSchema

class MoveAction:
    """ Move character action """
    conditions = {}
    reactions = {}
    weights = {}

    g = None  # goal; involved in plan costs

    def __init__(self, char_name, x, y):
        self.char_name = char_name
        self.x = x
        self.y = y

    def execute(self, client):
        """ Move the character to new coordinates """
        destination = DestinationSchema(
            x=self.x,
            y=self.y
        )
        response = move_character_api(
            name=self.char_name,
            client=client,
            body=destination
        )
        return response

    def __repr__(self):
        return f"MoveAction({self.char_name}, {self.x}, {self.y})"
