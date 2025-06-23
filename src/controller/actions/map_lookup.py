""" MapLookupAction module """

from artifactsmmo_api_client.api.maps.get_map_x_y import sync as get_map_api

class MapLookupAction:
    """ Map lookup action to get information about a specific map location """
    conditions = {}
    reactions = {}
    weights = {}

    g = None  # goal; involved in plan costs

    def __init__(self, x, y):
        self.x = x
        self.y = y

    def execute(self, client):
        """ Get map information for the specified coordinates """
        response = get_map_api(
            x=self.x,
            y=self.y,
            client=client
        )
        return response

    def __repr__(self):
        return f"MapLookupAction({self.x}, {self.y})"
