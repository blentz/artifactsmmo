"""
Map Analysis Module

This module provides intelligent map analysis for finding content locations,
calculating travel efficiency, and optimizing movement decisions using real
cached map data without hardcoded coordinates or locations.
"""


from src.game_data.models import GameMap


class MapAnalysisModule:
    """Analysis module for map navigation and content location optimization.

    This class provides strategic map analysis using only real cached game data
    to find optimal locations, calculate travel routes, and assess movement
    efficiency without any hardcoded coordinates or location assumptions.
    """

    def find_nearest_content(
        self,
        current_pos: tuple[int, int],
        content_type: str,
        maps: list[GameMap],
        level_filter: int | None = None
    ) -> list[tuple[GameMap, float]]:
        """Find nearest locations with specified content type.

        Parameters:
            current_pos: Current (x, y) position
            content_type: Type of content to find ("monster", "resource", etc.)
            maps: List of all GameMap objects from cache
            level_filter: Optional level filter for content appropriateness

        Return values:
            List of (map, distance) tuples sorted by proximity

        This method finds all locations with the specified content type using
        real map data, calculates actual distances, and returns them sorted
        by proximity without any hardcoded location assumptions.
        """
        if not maps:
            raise ValueError("Cannot find content: maps list is empty")

        content_locations = []

        for game_map in maps:
            # Check if this map has the requested content type
            if (game_map.content and
                game_map.content.type == content_type):

                # Calculate Manhattan distance using real coordinates
                distance = abs(game_map.x - current_pos[0]) + abs(game_map.y - current_pos[1])
                content_locations.append((game_map, distance))

        # Sort by distance (nearest first)
        return sorted(content_locations, key=lambda x: x[1])

    def find_content_by_code(
        self,
        content_type: str,
        content_code: str,
        maps: list[GameMap]
    ) -> list[GameMap]:
        """Find all locations containing specific content by code.

        Parameters:
            content_type: Type of content ("monster", "resource", etc.)
            content_code: Specific code of the content to find
            maps: List of all GameMap objects from cache

        Return values:
            List of GameMap objects containing the specified content

        This method finds all locations where specific content appears,
        using real map data to cross-reference content codes with locations.
        """
        if not maps:
            raise ValueError("Cannot find content by code: maps list is empty")

        matching_locations = []

        for game_map in maps:
            if (game_map.content and
                game_map.content.type == content_type and
                game_map.content.code == content_code):
                matching_locations.append(game_map)

        return matching_locations

    def calculate_travel_efficiency(
        self,
        start_pos: tuple[int, int],
        targets: list[tuple[int, int]]
    ) -> dict[tuple[int, int], float]:
        """Calculate travel time and efficiency for multiple targets.

        Parameters:
            start_pos: Starting (x, y) position
            targets: List of target (x, y) positions

        Return values:
            Dictionary mapping target positions to efficiency scores

        This method calculates travel efficiency to multiple targets,
        considering distance and potential for efficient routing.
        Higher scores indicate more efficient targets.
        """
        if not targets:
            return {}

        efficiency_scores = {}

        for target_pos in targets:
            # Calculate Manhattan distance
            distance = abs(target_pos[0] - start_pos[0]) + abs(target_pos[1] - start_pos[1])

            # Convert distance to efficiency score (closer = higher efficiency)
            # Use reciprocal with minimum distance of 1 to avoid division by zero
            efficiency = 1.0 / max(1, distance)

            efficiency_scores[target_pos] = efficiency

        return efficiency_scores

    def find_safe_locations(
        self,
        current_pos: tuple[int, int],
        maps: list[GameMap],
        max_distance: int = 10
    ) -> list[tuple[GameMap, float]]:
        """Find safe locations (no monsters) within specified distance.

        Parameters:
            current_pos: Current (x, y) position
            maps: List of all GameMap objects from cache
            max_distance: Maximum distance to search

        Return values:
            List of (map, distance) tuples for safe locations

        This method identifies locations without monsters where the character
        can safely rest or perform non-combat activities, using real map data
        to determine content safety.
        """
        if not maps:
            raise ValueError("Cannot find safe locations: maps list is empty")

        safe_locations = []

        for game_map in maps:
            # Calculate distance first to avoid unnecessary processing
            distance = abs(game_map.x - current_pos[0]) + abs(game_map.y - current_pos[1])

            if distance <= max_distance:
                # Check if location is safe (no monster content)
                is_safe = (not game_map.content or
                          game_map.content.type != "monster")

                if is_safe:
                    safe_locations.append((game_map, distance))

        # Sort by distance (nearest first)
        return sorted(safe_locations, key=lambda x: x[1])

    def calculate_optimal_route(
        self,
        start_pos: tuple[int, int],
        waypoints: list[tuple[int, int]]
    ) -> list[tuple[int, int]]:
        """Calculate optimal route through multiple waypoints.

        Parameters:
            start_pos: Starting (x, y) position
            waypoints: List of waypoint (x, y) positions to visit

        Return values:
            List of positions in optimal visit order

        This method uses a simple greedy nearest-neighbor approach to find
        an efficient route through multiple waypoints. For more complex
        routing, this could be enhanced with more sophisticated algorithms.
        """
        if not waypoints:
            return []

        if len(waypoints) == 1:
            return waypoints

        # Simple greedy nearest-neighbor algorithm
        route = []
        remaining_waypoints = waypoints.copy()
        current_position = start_pos

        while remaining_waypoints:
            # Find nearest remaining waypoint
            nearest_waypoint = None
            nearest_distance = float('inf')

            for waypoint in remaining_waypoints:
                distance = abs(waypoint[0] - current_position[0]) + abs(waypoint[1] - current_position[1])
                if distance < nearest_distance:
                    nearest_distance = distance
                    nearest_waypoint = waypoint

            if nearest_waypoint:
                route.append(nearest_waypoint)
                remaining_waypoints.remove(nearest_waypoint)
                current_position = nearest_waypoint

        return route

    def analyze_area_density(
        self,
        center_pos: tuple[int, int],
        content_type: str,
        maps: list[GameMap],
        radius: int = 5
    ) -> dict:
        """Analyze content density in an area around a position.

        Parameters:
            center_pos: Center (x, y) position for analysis
            content_type: Type of content to analyze density for
            maps: List of all GameMap objects from cache
            radius: Radius around center position to analyze

        Return values:
            Dictionary with density analysis results

        This method analyzes the density of specific content types in an area,
        helping to identify hotspots or optimal farming locations.
        """
        if not maps:
            raise ValueError("Cannot analyze area density: maps list is empty")

        content_in_area = []
        total_locations_in_area = 0

        # Analyze all locations within the specified radius
        for game_map in maps:
            distance = abs(game_map.x - center_pos[0]) + abs(game_map.y - center_pos[1])

            if distance <= radius:
                total_locations_in_area += 1

                if (game_map.content and
                    game_map.content.type == content_type):
                    content_in_area.append(game_map)

        # Calculate density metrics
        content_count = len(content_in_area)
        density_ratio = content_count / max(1, total_locations_in_area)

        return {
            'center_position': center_pos,
            'radius': radius,
            'content_type': content_type,
            'content_count': content_count,
            'total_locations': total_locations_in_area,
            'density_ratio': density_ratio,
            'content_locations': [(m.x, m.y) for m in content_in_area]
        }

    def find_content_clusters(
        self,
        content_type: str,
        maps: list[GameMap],
        cluster_radius: int = 3
    ) -> list[dict]:
        """Find clusters of similar content for efficient farming.

        Parameters:
            content_type: Type of content to find clusters for
            maps: List of all GameMap objects from cache
            cluster_radius: Radius to consider locations as part of same cluster

        Return values:
            List of cluster dictionaries with center and member locations

        This method identifies areas with high concentrations of specific
        content types, enabling efficient route planning for resource gathering
        or monster farming.
        """
        if not maps:
            raise ValueError("Cannot find content clusters: maps list is empty")

        # Find all locations with the specified content type
        content_locations = [
            game_map for game_map in maps
            if (game_map.content and game_map.content.type == content_type)
        ]

        if not content_locations:
            return []

        clusters = []
        processed_locations = set()

        for location in content_locations:
            if (location.x, location.y) in processed_locations:
                continue

            # Start a new cluster with this location
            cluster_members = [location]
            processed_locations.add((location.x, location.y))

            # Find nearby locations that belong to this cluster
            for other_location in content_locations:
                if (other_location.x, other_location.y) in processed_locations:
                    continue

                # Check if within cluster radius of any cluster member
                in_cluster = False
                for member in cluster_members:
                    distance = abs(other_location.x - member.x) + abs(other_location.y - member.y)
                    if distance <= cluster_radius:
                        in_cluster = True
                        break

                if in_cluster:
                    cluster_members.append(other_location)
                    processed_locations.add((other_location.x, other_location.y))

            # Calculate cluster center
            center_x = sum(loc.x for loc in cluster_members) // len(cluster_members)
            center_y = sum(loc.y for loc in cluster_members) // len(cluster_members)

            cluster_info = {
                'center': (center_x, center_y),
                'member_count': len(cluster_members),
                'locations': [(loc.x, loc.y) for loc in cluster_members],
                'content_codes': list(set(loc.content.code for loc in cluster_members if loc.content))
            }

            clusters.append(cluster_info)

        # Sort clusters by member count (largest first)
        return sorted(clusters, key=lambda x: x['member_count'], reverse=True)
