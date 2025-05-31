from artifactsmmo_api_client.api.maps.get_map_x_y import sync as get_map_x_y
from artifactsmmo_api_client.models.map_schema import MapSchema

from lib.yaml_data import YamlData
from game.globals import DATA_PREFIX


class MapState(YamlData):
    """Map model."""

    _client = None
    data = None

    def __init__(self, client, name="map"):
        YamlData.__init__(self, filename=f"{DATA_PREFIX}/{name}.yaml")

        self._client = client

        data = self.scan(x=0, y=0)
        if data and "data" in data:
            self.data = data["data"]
        else:
            self.data = data

    def scan(self, x, y, cache=True):
        """collect data on the given coordinates."""
        if cache and f"{x},{y}" in self.data:
            return self.data
        maptile = get_map_x_y(x, y, client=self._client).data  # FIXME: not async
        self.data[f"{x},{y}"] = maptile.to_dict()
        return self.data

    def scan_around(self, origin=(0, 0), radius=1):
        """
        Scan the surrounding `radius` tiles around `origin`, return tuple of map tiles
        TODO: Add caching
        """
        zone = []
        y_range = range(origin[1] - radius, origin[1] + radius + 1)
        x_range = range(origin[0] - radius, origin[0] + radius + 1)
        for y in y_range:
            for x in x_range:
                self.scan(x, y)
        return self.data

    def scan_map_for(self, item, origin=(0, 0), radius=1):
        """
        Scan the surrounding `radius` tiles around `origin` for `item`, return tuple
        """
        zone = self.scan_around(origin=origin, radius=radius)
        for coords, tile in zone:
            if tile.content and item in [tile.content.type, tile.content.code]:
                return {coords: tile}
        return {}
