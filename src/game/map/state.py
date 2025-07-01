import time

from artifactsmmo_api_client.api.maps.get_map_maps_x_y_get import sync as get_map_x_y

from src.game.globals import DATA_PREFIX
from src.lib.yaml_data import YamlData


class MapState(YamlData):
    """Map model."""

    _client = None
    data = None

    def __init__(self, client, name="map", initial_scan=True, cache_duration=180):
        YamlData.__init__(self, filename=f"{DATA_PREFIX}/{name}.yaml")

        self._client = client
        self._learning_callback = None
        self.cache_duration = cache_duration  # Cache duration in seconds (default: 3 minutes)

        # Initialize data as empty dict if not loaded from file
        if not self.data:
            self.data = {}
        
        # Perform initial scan at origin to populate data if requested
        if initial_scan and client:
            try:
                self.scan(x=0, y=0)
            except Exception:
                # If initial scan fails (e.g., in tests), continue without it
                pass

    def set_learning_callback(self, callback):
        """Set a learning callback to be called when content is discovered."""
        self._learning_callback = callback

    def is_cache_fresh(self, x, y):
        """Check if cached data for coordinates is fresh enough."""
        coord_key = f"{x},{y}"
        if coord_key not in self.data:
            return False
        
        tile_data = self.data[coord_key]
        if not isinstance(tile_data, dict) or 'last_scanned' not in tile_data:
            return False
        
        # Convert last_scanned to float in case it was loaded as string from YAML
        try:
            last_scanned = float(tile_data['last_scanned'])
        except (ValueError, TypeError):
            return False
        
        time_since_scan = time.time() - last_scanned
        return time_since_scan < self.cache_duration

    def scan(self, x, y, cache=True, save_immediately=True):
        """collect data on the given coordinates."""
        coord_key = f"{x},{y}"
        
        # Check if we have fresh cached data
        if cache and self.is_cache_fresh(x, y):
            # Cache hit - return cached data without API call
            return self.data
        
        # Cache miss or expired - need to fetch from API
        current_time = time.time()
        if coord_key in self.data and 'last_scanned' in self.data[coord_key]:
            try:
                last_scanned = float(self.data[coord_key]['last_scanned'])
                age = current_time - last_scanned
                if age >= self.cache_duration:
                    self._log.debug(f"🔄 Cache expired for ({x},{y}) - age {age:.1f}s >= {self.cache_duration}s, refreshing from API")
                else:
                    self._log.debug(f"🆕 First scan for ({x},{y})")
            except (ValueError, TypeError):
                self._log.debug(f"🆕 First scan for ({x},{y})")
        else:
            self._log.debug(f"🆕 First scan for ({x},{y})")
        
        # Get map data from API
        map_response = get_map_x_y(x, y, client=self._client)  # FIXME: not async
        
        # Handle 404 responses (coordinates outside map boundaries)
        if map_response is None:
            self._log.debug(f"🚫 Map boundary detected at ({x},{y}) - coordinate outside map")
            # Don't cache invalid coordinates, just return None
            return None
            
        maptile = map_response.data
        tile_dict = maptile.to_dict()
        
        # Add timestamp to the tile data for cache freshness tracking
        tile_dict['last_scanned'] = current_time
        self.data[coord_key] = tile_dict
        
        # Trigger learning callback if content is found
        if self._learning_callback and maptile.content:
            try:
                self._learning_callback(x, y, map_response)
            except Exception:
                # Don't let learning errors break map scanning
                pass
        
        if save_immediately:
            self.save()  # Persist the scanned data immediately
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
                # Don't save immediately during batch scanning
                self.scan(x, y, save_immediately=False)
        # Save once after all locations are scanned
        self.save()
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
