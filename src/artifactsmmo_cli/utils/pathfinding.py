"""Pathfinding and navigation utilities."""

from dataclasses import dataclass

from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.utils.helpers import handle_api_response
from artifactsmmo_cli.utils.validators import validate_character_name


@dataclass
class PathStep:
    """Represents a single step in a path."""

    x: int
    y: int

    def __str__(self) -> str:
        return f"({self.x}, {self.y})"


@dataclass
class PathResult:
    """Result of pathfinding calculation."""

    steps: list[PathStep]
    total_distance: int
    estimated_time: int  # seconds including cooldowns

    @property
    def is_empty(self) -> bool:
        """Check if path is empty."""
        return len(self.steps) == 0

    def __str__(self) -> str:
        if self.is_empty:
            return "No movement needed"
        return f"{len(self.steps)} steps, {self.total_distance} distance, ~{self.estimated_time}s"


def calculate_path(start_x: int, start_y: int, end_x: int, end_y: int) -> PathResult:
    """Calculate optimal path using Manhattan distance (no obstacles).

    Args:
        start_x: Starting X coordinate
        start_y: Starting Y coordinate
        end_x: Ending X coordinate
        end_y: Ending Y coordinate

    Returns:
        PathResult with steps and metadata
    """
    # If already at destination, return empty path
    if start_x == end_x and start_y == end_y:
        return PathResult(steps=[], total_distance=0, estimated_time=0)

    steps = []
    current_x, current_y = start_x, start_y

    # Calculate path step by step
    # Move diagonally when possible, then move in remaining direction
    while current_x != end_x or current_y != end_y:
        next_x, next_y = current_x, current_y

        # Move towards target X coordinate
        if current_x < end_x:
            next_x += 1
        elif current_x > end_x:
            next_x -= 1

        # Move towards target Y coordinate
        if current_y < end_y:
            next_y += 1
        elif current_y > end_y:
            next_y -= 1

        steps.append(PathStep(next_x, next_y))
        current_x, current_y = next_x, next_y

    # Calculate total distance (Manhattan distance)
    total_distance = abs(end_x - start_x) + abs(end_y - start_y)

    # Estimate time: assume 5 seconds per move (including cooldown)
    estimated_time = len(steps) * 5

    return PathResult(
        steps=steps,
        total_distance=total_distance,
        estimated_time=estimated_time,
    )


def get_character_position(character: str) -> tuple[int, int]:
    """Get current character position from API.

    Args:
        character: Character name

    Returns:
        Tuple of (x, y) coordinates

    Raises:
        Exception: If character not found or API error
    """
    character = validate_character_name(character)
    api = ClientManager().api
    response = api.get_character(name=character)

    cli_response = handle_api_response(response)
    if not cli_response.success or not cli_response.data:
        error_msg = cli_response.error or f"Character '{character}' not found"
        raise Exception(error_msg)

    char_data = cli_response.data
    x = getattr(char_data, "x", None)
    y = getattr(char_data, "y", None)

    if x is None or y is None:
        raise Exception(f"Could not get position for character '{character}'")

    return int(x), int(y)


def resolve_named_location(location_name: str, character_x: int, character_y: int) -> tuple[int, int]:
    """Resolve named locations like 'bank', 'task master', 'copper' to coordinates.

    Args:
        location_name: Name of location to find
        character_x: Character's current X coordinate
        character_y: Character's current Y coordinate

    Returns:
        Tuple of (x, y) coordinates for the location

    Raises:
        Exception: If location not found
    """
    location_lower = location_name.lower().strip()

    # Handle specific named locations
    if location_lower == "bank":
        return find_nearest_bank(character_x, character_y)
    elif location_lower in ["task master", "taskmaster", "task_master"]:
        return find_nearest_task_master(character_x, character_y)
    else:
        # Try to find as a resource
        return find_nearest_resource(location_name, character_x, character_y)


def find_nearest_bank(character_x: int, character_y: int) -> tuple[int, int]:
    """Find nearest bank location.

    Args:
        character_x: Character's current X coordinate
        character_y: Character's current Y coordinate

    Returns:
        Tuple of (x, y) coordinates for nearest bank

    Raises:
        Exception: If no bank found
    """
    # Try to find banks via map API
    try:
        client = ClientManager().client
        from artifactsmmo_api_client.api.maps import get_all_maps_maps_get

        # Search for bank content
        banks = []
        current_page = 1
        max_pages = 10  # Limit search

        while current_page <= max_pages:
            response = get_all_maps_maps_get.sync(client=client, page=current_page, size=100)
            cli_response = handle_api_response(response)

            if not cli_response.success or not cli_response.data:
                break

            maps = cli_response.data
            if not hasattr(maps, "data") or not maps.data:
                break

            # Look for banks in this page
            for map_item in maps.data:
                if hasattr(map_item, "content") and map_item.content:
                    content = map_item.content
                    content_type = getattr(content, "type", "").lower()

                    if "bank" in content_type:
                        x = getattr(map_item, "x", None)
                        y = getattr(map_item, "y", None)
                        if x is not None and y is not None:
                            banks.append((int(x), int(y)))

            # Check if we have more pages
            if hasattr(maps, "pages") and current_page >= maps.pages:
                break
            current_page += 1

        if banks:
            # Find nearest bank
            return _find_nearest_location(banks, character_x, character_y)

    except Exception:
        pass  # Fall back to known locations

    # Fallback to known bank locations
    known_banks = [(4, 1)]  # Known bank location from info.py
    return _find_nearest_location(known_banks, character_x, character_y)


def find_nearest_task_master(character_x: int, character_y: int) -> tuple[int, int]:
    """Find nearest task master location.

    Args:
        character_x: Character's current X coordinate
        character_y: Character's current Y coordinate

    Returns:
        Tuple of (x, y) coordinates for nearest task master

    Raises:
        Exception: If no task master found
    """
    # Try to find task masters via map API
    try:
        client = ClientManager().client
        from artifactsmmo_api_client.api.maps import get_all_maps_maps_get

        # Search for task master content
        task_masters = []
        current_page = 1
        max_pages = 10  # Limit search

        while current_page <= max_pages:
            response = get_all_maps_maps_get.sync(client=client, page=current_page, size=100)
            cli_response = handle_api_response(response)

            if not cli_response.success or not cli_response.data:
                break

            maps = cli_response.data
            if not hasattr(maps, "data") or not maps.data:
                break

            # Look for task masters in this page
            for map_item in maps.data:
                if hasattr(map_item, "content") and map_item.content:
                    content = map_item.content
                    content_type = getattr(content, "type", "").lower()

                    if "task" in content_type:
                        x = getattr(map_item, "x", None)
                        y = getattr(map_item, "y", None)
                        if x is not None and y is not None:
                            task_masters.append((int(x), int(y)))

            # Check if we have more pages
            if hasattr(maps, "pages") and current_page >= maps.pages:
                break
            current_page += 1

        if task_masters:
            # Find nearest task master
            return _find_nearest_location(task_masters, character_x, character_y)

    except Exception:
        pass  # Fall back to known locations

    # Fallback to known task master locations
    known_task_masters = [(1, 2), (5, 1)]  # Known task master locations from info.py
    return _find_nearest_location(known_task_masters, character_x, character_y)


def find_nearest_resource(resource_name: str, character_x: int, character_y: int) -> tuple[int, int]:
    """Find nearest resource location.

    Args:
        resource_name: Name of resource to find
        character_x: Character's current X coordinate
        character_y: Character's current Y coordinate

    Returns:
        Tuple of (x, y) coordinates for nearest resource

    Raises:
        Exception: If resource not found
    """
    try:
        client = ClientManager().client
        from artifactsmmo_api_client.api.maps import get_all_maps_maps_get

        # Search for resource content by name
        resources = []
        current_page = 1
        max_pages = 10  # Limit search

        while current_page <= max_pages:
            response = get_all_maps_maps_get.sync(client=client, page=current_page, size=100)
            cli_response = handle_api_response(response)

            if not cli_response.success or not cli_response.data:
                break

            maps = cli_response.data
            if not hasattr(maps, "data") or not maps.data:
                break

            # Look for resources in this page
            for map_item in maps.data:
                if hasattr(map_item, "content") and map_item.content:
                    content = map_item.content
                    content_code = getattr(content, "code", "").lower()
                    content_type = getattr(content, "type", "").lower()

                    # Check if this matches the resource name
                    if (
                        resource_name.lower() in content_code
                        or resource_name.lower() in content_type
                        or "resource" in content_type
                    ):
                        x = getattr(map_item, "x", None)
                        y = getattr(map_item, "y", None)
                        if x is not None and y is not None:
                            resources.append((int(x), int(y)))

            # Check if we have more pages
            if hasattr(maps, "pages") and current_page >= maps.pages:
                break
            current_page += 1

        if resources:
            # Find nearest resource
            return _find_nearest_location(resources, character_x, character_y)

    except Exception:
        pass

    # If not found, raise an error
    raise Exception(f"Resource '{resource_name}' not found on the map")


def _find_nearest_location(locations: list[tuple[int, int]], character_x: int, character_y: int) -> tuple[int, int]:
    """Find the nearest location from a list of coordinates.

    Args:
        locations: List of (x, y) coordinate tuples
        character_x: Character's current X coordinate
        character_y: Character's current Y coordinate

    Returns:
        Tuple of (x, y) coordinates for nearest location

    Raises:
        Exception: If no locations provided
    """
    if not locations:
        raise Exception("No locations available")

    if len(locations) == 1:
        return locations[0]

    # Find location with minimum Manhattan distance
    min_distance = float("inf")
    nearest_location = locations[0]

    for x, y in locations:
        distance = abs(x - character_x) + abs(y - character_y)
        if distance < min_distance:
            min_distance = distance
            nearest_location = (x, y)

    return nearest_location


def parse_destination(destination: str) -> tuple[int, int] | str:
    """Parse destination string into coordinates or return as named location.

    Args:
        destination: Destination string (either "X Y" coordinates or named location)

    Returns:
        Either tuple of (x, y) coordinates or string for named location

    Raises:
        Exception: If coordinates are invalid
    """
    # Try to parse as coordinates first
    parts = destination.strip().split()
    if len(parts) == 2:
        try:
            x = int(parts[0])
            y = int(parts[1])
            return (x, y)
        except ValueError:
            pass  # Not coordinates, treat as named location

    # Return as named location
    return destination.strip()
