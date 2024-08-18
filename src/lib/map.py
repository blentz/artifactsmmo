from typing import Optional, Tuple

from artifacts_openapi import APIConfig
from artifacts_openapi.services.Maps_service import get_map_maps__x___y__get
from artifacts_openapi.models.MapSchema import MapSchema

from .yaml_data import YamlData


class MapState(YamlData):
    """Map model."""

    _api_config: APIConfig = None

    def __init__(
        self, filename: str = "map.yaml", api_config_override: APIConfig = None
    ):
        YamlData.__init__(self, filename=filename)
        self._api_config = api_config_override

        data = self.scan(x=0, y=0)
        if data and "data" in data:
            self.data = data["data"]
        else:
            self.data = data

    def scan(
        self, x: int, y: int, cache: bool = True
    ) -> dict[Tuple[int, int], MapSchema]:
        """collect data on the given coordinates."""
        if cache and f"{x},{y}" in self.data:
            return self.data
        maptile: MapSchema = get_map_maps__x___y__get(
            x, y, api_config_override=self._api_config
        ).data  # FIXME: not async
        self.data[f"{x},{y}"] = maptile.dict()
        return self.data

    def scan_around(
        self,
        origin: Optional[tuple] = (0, 0),
        radius: Optional[int] = 1,
    ) -> dict[Tuple[int, int], MapSchema]:
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

    def scan_map_for(
        self,
        item: str,
        origin: Optional[tuple] = (0, 0),
        radius: Optional[int] = 1,
    ) -> dict[Tuple[int, int], MapSchema]:
        """
        Scan the surrounding `radius` tiles around `origin` for `item`, return tuple
        """
        zone = self.scan_around(origin=origin, radius=radius)
        for coords, tile in zone:
            if tile.content and item in [tile.content.type, tile.content.code]:
                return {coords: tile}
        return {}
