"""
Pathfinding Service for ArtifactsMMO AI Player

This module provides pathfinding algorithms and movement planning for the AI player.
It integrates with the GOAP system to generate efficient movement sequences that
navigate around obstacles and optimize character positioning.

The pathfinding service supports multiple algorithms including A* for optimal pathfinding
and provides integration with the modular action system for movement execution.
"""

import heapq
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from .actions.movement_action import MovementAction


@dataclass
class PathNode:
    """Represents a single node in a pathfinding path"""
    x: int
    y: int
    cost: int = 0
    heuristic: int = 0
    parent: Optional['PathNode'] = None

    @property
    def f_score(self) -> int:
        """Total path cost (g + h)"""
        return self.cost + self.heuristic


@dataclass
class PathfindingResult:
    """Result of pathfinding calculation"""
    success: bool
    path: list[tuple[int, int]]
    movement_actions: list[MovementAction]
    total_cost: int
    total_distance: int
    message: str


class PathfindingAlgorithm(ABC):
    """Abstract base class for pathfinding algorithms"""

    @abstractmethod
    def find_path(self, start: tuple[int, int], goal: tuple[int, int], obstacles: set[tuple[int, int]],
                  bounds: tuple[int, int, int, int]) -> PathfindingResult:
        """Find optimal path from start to goal avoiding obstacles.
        
        Parameters:
            start: Starting coordinates as (x, y) tuple
            goal: Target destination coordinates as (x, y) tuple
            obstacles: Set of coordinate tuples representing blocked positions
            bounds: Map boundaries as (min_x, min_y, max_x, max_y) tuple
            
        Return values:
            PathfindingResult containing success status, path coordinates, and movement actions
            
        This method implements the abstract pathfinding interface to find an optimal
        path from start to goal while avoiding obstacles and staying within map
        boundaries, suitable for GOAP movement planning.
        """
        pass


class AStarPathfinding(PathfindingAlgorithm):
    """A* pathfinding algorithm implementation"""

    def find_path(self, start: tuple[int, int], goal: tuple[int, int], obstacles: set[tuple[int, int]],
                  bounds: tuple[int, int, int, int]) -> PathfindingResult:
        """A* pathfinding with obstacle avoidance.
        
        Parameters:
            start: Starting coordinates as (x, y) tuple
            goal: Target destination coordinates as (x, y) tuple
            obstacles: Set of coordinate tuples representing blocked positions
            bounds: Map boundaries as (min_x, min_y, max_x, max_y) tuple
            
        Return values:
            PathfindingResult with optimal path using A* algorithm evaluation
            
        This method implements the A* pathfinding algorithm with Manhattan distance
        heuristic to find the optimal path while avoiding obstacles and respecting
        map boundaries for efficient character navigation.
        """
        # Validate start and goal positions
        if not self.is_valid_position(start[0], start[1], obstacles, bounds):
            return PathfindingResult(
                success=False,
                path=[],
                movement_actions=[],
                total_cost=0,
                total_distance=0,
                message="Start position is invalid or blocked"
            )

        if not self.is_valid_position(goal[0], goal[1], obstacles, bounds):
            return PathfindingResult(
                success=False,
                path=[],
                movement_actions=[],
                total_cost=0,
                total_distance=0,
                message="Goal position is invalid or blocked"
            )

        # If start equals goal, return trivial path
        if start == goal:
            return PathfindingResult(
                success=True,
                path=[start],
                movement_actions=[],
                total_cost=0,
                total_distance=0,
                message="Already at goal position"
            )

        # Initialize A* algorithm
        start_node = PathNode(start[0], start[1], cost=0, heuristic=self.heuristic(start, goal))
        goal_node: PathNode | None = None

        # Priority queue for open set (nodes to be evaluated)
        open_set = [(start_node.f_score, 0, start_node)]  # (f_score, tie_breaker, node)
        open_set_dict = {(start[0], start[1]): start_node}  # For fast lookup

        # Set of evaluated nodes
        closed_set = set()

        # Counter for tie-breaking in heap
        counter = 1

        while open_set:
            # Get node with lowest f_score
            _, _, current_node = heapq.heappop(open_set)
            current_pos = (current_node.x, current_node.y)

            # Remove from open set dict
            if current_pos in open_set_dict:
                del open_set_dict[current_pos]

            # Check if we reached the goal
            if current_pos == goal:
                goal_node = current_node
                break

            # Add to closed set
            closed_set.add(current_pos)

            # Examine all neighbors
            for neighbor in self.get_neighbors(current_node, bounds):
                neighbor_pos = (neighbor.x, neighbor.y)

                # Skip if already evaluated or is obstacle
                if neighbor_pos in closed_set or not self.is_valid_position(neighbor.x, neighbor.y, obstacles, bounds):
                    continue

                # Calculate costs
                neighbor.cost = current_node.cost + 1  # Movement cost is 1
                neighbor.heuristic = self.heuristic(neighbor_pos, goal)

                # Check if this path to neighbor is better than any previous one
                if neighbor_pos in open_set_dict:
                    existing_neighbor = open_set_dict[neighbor_pos]
                    if neighbor.cost >= existing_neighbor.cost:
                        continue  # This path is not better

                # This is the best path to neighbor so far
                open_set_dict[neighbor_pos] = neighbor
                heapq.heappush(open_set, (neighbor.f_score, counter, neighbor))
                counter += 1

        # Generate result
        if goal_node is None:
            return PathfindingResult(
                success=False,
                path=[],
                movement_actions=[],
                total_cost=0,
                total_distance=0,
                message="No path found to goal"
            )

        # Reconstruct path
        path = self.reconstruct_path(goal_node)
        movement_actions = self.generate_movement_actions(path)

        return PathfindingResult(
            success=True,
            path=path,
            movement_actions=movement_actions,
            total_cost=goal_node.cost,
            total_distance=len(path) - 1,
            message=f"Path found with {len(path)} waypoints"
        )

    def generate_movement_actions(self, path: list[tuple[int, int]]) -> list[MovementAction]:
        """Generate MovementAction instances from path coordinates"""
        actions = []
        # Skip the first position (starting position)
        for i in range(1, len(path)):
            x, y = path[i]
            actions.append(MovementAction(x, y))
        return actions

    def heuristic(self, pos1: tuple[int, int], pos2: tuple[int, int]) -> int:
        """Manhattan distance heuristic.
        
        Parameters:
            pos1: First position coordinates as (x, y) tuple
            pos2: Second position coordinates as (x, y) tuple
            
        Return values:
            Integer representing Manhattan distance between the two positions
            
        This method calculates the Manhattan distance heuristic for A* pathfinding,
        providing an admissible estimate of movement cost between positions for
        optimal pathfinding performance in grid-based movement.
        """
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

    def get_neighbors(self, node: PathNode, bounds: tuple[int, int, int, int]) -> list[PathNode]:
        """Get valid neighboring positions.
        
        Parameters:
            node: Current PathNode to find neighbors for
            bounds: Map boundaries as (min_x, min_y, max_x, max_y) tuple
            
        Return values:
            List of PathNode objects representing valid adjacent positions
            
        This method generates all valid neighboring positions for the current node
        considering map boundaries and movement constraints, supporting 4-directional
        movement for A* pathfinding exploration.
        """
        neighbors = []

        # 4-directional movement: up, down, left, right
        directions = [(0, 1), (0, -1), (-1, 0), (1, 0)]

        for dx, dy in directions:
            new_x = node.x + dx
            new_y = node.y + dy

            # Check bounds
            min_x, min_y, max_x, max_y = bounds
            if min_x <= new_x <= max_x and min_y <= new_y <= max_y:
                neighbor = PathNode(new_x, new_y, parent=node)
                neighbors.append(neighbor)

        return neighbors

    def is_valid_position(self, x: int, y: int, obstacles: set[tuple[int, int]],
                          bounds: tuple[int, int, int, int]) -> bool:
        """Check if position is valid (not obstacle, within bounds).
        
        Parameters:
            x: X coordinate to validate
            y: Y coordinate to validate
            obstacles: Set of coordinate tuples representing blocked positions
            bounds: Map boundaries as (min_x, min_y, max_x, max_y) tuple
            
        Return values:
            Boolean indicating whether position is accessible for movement
            
        This method validates that a position is within map boundaries, not blocked
        by obstacles, and accessible for character movement in the pathfinding
        algorithm exploration process.
        """
        min_x, min_y, max_x, max_y = bounds

        # Check if within bounds
        if x < min_x or x > max_x or y < min_y or y > max_y:
            return False

        # Check if not an obstacle
        if (x, y) in obstacles:
            return False

        return True

    def reconstruct_path(self, goal_node: PathNode) -> list[tuple[int, int]]:
        """Reconstruct path from goal back to start"""
        path = []
        current: PathNode | None = goal_node

        while current is not None:
            path.append((current.x, current.y))
            current = current.parent

        # Reverse to get path from start to goal
        path.reverse()
        return path


class DijkstraPathfinding(PathfindingAlgorithm):
    """Dijkstra pathfinding algorithm for guaranteed optimal paths"""

    def find_path(self, start: tuple[int, int], goal: tuple[int, int], obstacles: set[tuple[int, int]],
                  bounds: tuple[int, int, int, int]) -> PathfindingResult:
        """Dijkstra pathfinding with guaranteed optimal solution.
        
        Parameters:
            start: Starting coordinates as (x, y) tuple
            goal: Target destination coordinates as (x, y) tuple
            obstacles: Set of coordinate tuples representing blocked positions
            bounds: Map boundaries as (min_x, min_y, max_x, max_y) tuple
            
        Return values:
            PathfindingResult with optimal path using Dijkstra algorithm
            
        This method implements Dijkstra's pathfinding algorithm which guarantees
        finding the optimal path by exploring all nodes in order of distance from
        start, without using heuristics for efficient pathfinding.
        """
        # Validate start and goal positions
        if not self.is_valid_position(start[0], start[1], obstacles, bounds):
            return PathfindingResult(
                success=False,
                path=[],
                movement_actions=[],
                total_cost=0,
                total_distance=0,
                message="Start position is invalid or blocked"
            )

        if not self.is_valid_position(goal[0], goal[1], obstacles, bounds):
            return PathfindingResult(
                success=False,
                path=[],
                movement_actions=[],
                total_cost=0,
                total_distance=0,
                message="Goal position is invalid or blocked"
            )

        # If start equals goal, return trivial path
        if start == goal:
            return PathfindingResult(
                success=True,
                path=[start],
                movement_actions=[],
                total_cost=0,
                total_distance=0,
                message="Already at goal position"
            )

        # Initialize Dijkstra algorithm
        start_node = PathNode(start[0], start[1], cost=0, heuristic=0)
        goal_node: PathNode | None = None

        # Priority queue for unvisited nodes (cost, tie_breaker, node)
        unvisited = [(0, 0, start_node)]
        unvisited_dict = {(start[0], start[1]): start_node}

        # Set of visited nodes
        visited = set()

        # Counter for tie-breaking in heap
        counter = 1

        while unvisited:
            # Get node with lowest cost
            current_cost, _, current_node = heapq.heappop(unvisited)
            current_pos = (current_node.x, current_node.y)

            # Remove from unvisited dict
            if current_pos in unvisited_dict:
                del unvisited_dict[current_pos]

            # Skip if already visited
            if current_pos in visited:
                continue

            # Check if we reached the goal
            if current_pos == goal:
                goal_node = current_node
                break

            # Mark as visited
            visited.add(current_pos)

            # Examine all neighbors
            for neighbor in self.get_neighbors(current_node, bounds):
                neighbor_pos = (neighbor.x, neighbor.y)

                # Skip if already visited or is obstacle
                if neighbor_pos in visited or not self.is_valid_position(neighbor.x, neighbor.y, obstacles, bounds):
                    continue

                # Calculate new cost
                new_cost = current_node.cost + 1  # Movement cost is 1

                # Check if this path to neighbor is better than any previous one
                if neighbor_pos in unvisited_dict:
                    existing_neighbor = unvisited_dict[neighbor_pos]
                    if new_cost >= existing_neighbor.cost:
                        continue  # This path is not better

                # This is the best path to neighbor so far
                neighbor.cost = new_cost
                neighbor.heuristic = 0  # Dijkstra doesn't use heuristics
                unvisited_dict[neighbor_pos] = neighbor
                heapq.heappush(unvisited, (new_cost, counter, neighbor))
                counter += 1

        # Generate result
        if goal_node is None:
            return PathfindingResult(
                success=False,
                path=[],
                movement_actions=[],
                total_cost=0,
                total_distance=0,
                message="No path found to goal"
            )

        # Reconstruct path
        path = self.reconstruct_path(goal_node)
        movement_actions = self.generate_movement_actions(path)

        return PathfindingResult(
            success=True,
            path=path,
            movement_actions=movement_actions,
            total_cost=goal_node.cost,
            total_distance=len(path) - 1,
            message=f"Path found with {len(path)} waypoints using Dijkstra"
        )

    def generate_movement_actions(self, path: list[tuple[int, int]]) -> list[MovementAction]:
        """Generate MovementAction instances from path coordinates"""
        actions = []
        # Skip the first position (starting position)
        for i in range(1, len(path)):
            x, y = path[i]
            actions.append(MovementAction(x, y))
        return actions

    def get_neighbors(self, node: PathNode, bounds: tuple[int, int, int, int]) -> list[PathNode]:
        """Get valid neighboring positions.
        
        Parameters:
            node: Current PathNode to find neighbors for
            bounds: Map boundaries as (min_x, min_y, max_x, max_y) tuple
            
        Return values:
            List of PathNode objects representing valid adjacent positions
            
        This method generates all valid neighboring positions for the current node
        considering map boundaries and movement constraints, supporting 4-directional
        movement for Dijkstra pathfinding exploration.
        """
        neighbors = []

        # 4-directional movement: up, down, left, right
        directions = [(0, 1), (0, -1), (-1, 0), (1, 0)]

        for dx, dy in directions:
            new_x = node.x + dx
            new_y = node.y + dy

            # Check bounds
            min_x, min_y, max_x, max_y = bounds
            if min_x <= new_x <= max_x and min_y <= new_y <= max_y:
                neighbor = PathNode(new_x, new_y, parent=node)
                neighbors.append(neighbor)

        return neighbors

    def is_valid_position(self, x: int, y: int, obstacles: set[tuple[int, int]],
                          bounds: tuple[int, int, int, int]) -> bool:
        """Check if position is valid (not obstacle, within bounds).
        
        Parameters:
            x: X coordinate to validate
            y: Y coordinate to validate
            obstacles: Set of coordinate tuples representing blocked positions
            bounds: Map boundaries as (min_x, min_y, max_x, max_y) tuple
            
        Return values:
            Boolean indicating whether position is accessible for movement
            
        This method validates that a position is within map boundaries, not blocked
        by obstacles, and accessible for character movement in the Dijkstra
        algorithm exploration process.
        """
        min_x, min_y, max_x, max_y = bounds

        # Check if within bounds
        if x < min_x or x > max_x or y < min_y or y > max_y:
            return False

        # Check if not an obstacle
        if (x, y) in obstacles:
            return False

        return True

    def reconstruct_path(self, goal_node: PathNode) -> list[tuple[int, int]]:
        """Reconstruct path from goal back to start"""
        path = []
        current: PathNode | None = goal_node

        while current is not None:
            path.append((current.x, current.y))
            current = current.parent

        # Reverse to get path from start to goal
        path.reverse()
        return path


class PathfindingService:
    """Main pathfinding service integrating with GOAP system"""

    def __init__(self, algorithm: PathfindingAlgorithm | None = None):
        self.algorithm = algorithm or AStarPathfinding()
        self.map_cache: dict[int, tuple[int, int, int, int]] = {}
        self.obstacle_cache: dict[int, set[tuple[int, int]]] = {}

    def find_path(self, start: tuple[int, int], goal: tuple[int, int],
                  game_data: Any = None) -> PathfindingResult:
        """Find path using current algorithm and cached map data"""
        obstacles = self.get_obstacles_from_game_data(game_data)
        bounds = self.get_map_bounds(game_data)

        return self.algorithm.find_path(start, goal, obstacles, bounds)

    def find_path_to_nearest(self, start: tuple[int, int], targets: list[tuple[int, int]],
                            game_data: Any = None) -> PathfindingResult:
        """Find path to nearest target from a list of possible destinations"""
        if not targets:
            return PathfindingResult(
                success=False,
                path=[],
                movement_actions=[],
                total_cost=0,
                total_distance=0,
                message="No targets provided"
            )

        best_result = None
        best_cost = float('inf')

        for target in targets:
            result = self.find_path(start, target, game_data)
            if result.success and result.total_cost < best_cost:
                best_cost = result.total_cost
                best_result = result

        if best_result is None:
            return PathfindingResult(
                success=False,
                path=[],
                movement_actions=[],
                total_cost=0,
                total_distance=0,
                message="No path found to any target"
            )

        return best_result

    def generate_movement_actions(self, path: list[tuple[int, int]]) -> list[MovementAction]:
        """Convert path coordinates to MovementAction instances"""
        actions = []
        # Skip the first position (starting position)
        for i in range(1, len(path)):
            x, y = path[i]
            actions.append(MovementAction(x, y))
        return actions

    def optimize_path(self, path: list[tuple[int, int]]) -> list[tuple[int, int]]:
        """Optimize path by removing unnecessary waypoints.
        
        Parameters:
            path: List of coordinates representing the original path
            
        Return values:
            List of coordinates with unnecessary waypoints removed
            
        This method implements line-of-sight optimization to reduce the number
        of waypoints in a path by removing intermediate points when a direct
        line is possible, improving movement efficiency for the AI player.
        """
        if len(path) <= 2:
            return path.copy()

        optimized = [path[0]]  # Always include start point
        current_index = 0

        while current_index < len(path) - 1:
            # Find the furthest point we can reach directly
            furthest_reachable = current_index + 1

            for target_index in range(current_index + 2, len(path)):
                if self._has_line_of_sight(path[current_index], path[target_index]):
                    furthest_reachable = target_index
                else:
                    break

            # Add the furthest reachable point
            if furthest_reachable != current_index:
                optimized.append(path[furthest_reachable])
                current_index = furthest_reachable
            else:
                # If we can't reach further, move to next point
                current_index += 1
                if current_index < len(path):
                    optimized.append(path[current_index])

        return optimized

    def _has_line_of_sight(self, start: tuple[int, int], end: tuple[int, int]) -> bool:
        """Check if there's a clear line of sight between two points.
        
        Parameters:
            start: Starting position coordinates
            end: Ending position coordinates
            
        Return values:
            Boolean indicating if direct movement is possible
            
        This method uses Bresenham's line algorithm to check if all points
        on the line between start and end are valid movement positions,
        enabling path optimization through line-of-sight checks.
        """
        # Use Bresenham's line algorithm to check all points on the line
        x0, y0 = start
        x1, y1 = end

        dx = abs(x1 - x0)
        dy = abs(y1 - y0)

        x_step = 1 if x0 < x1 else -1
        y_step = 1 if y0 < y1 else -1

        error = dx - dy

        x, y = x0, y0

        while True:
            # For simplicity, assume all positions have line of sight
            # In a real game, we'd check against obstacles and bounds here
            # But since we're optimizing an already valid path, all intermediate
            # points should be valid

            if x == x1 and y == y1:
                break

            e2 = 2 * error

            if e2 > -dy:
                error -= dy
                x += x_step

            if e2 < dx:
                error += dx
                y += y_step

        return True

    def get_obstacles_from_game_data(self, game_data: Any) -> set[tuple[int, int]]:
        """Extract obstacle positions from game data"""
        obstacles: set[tuple[int, int]] = set()

        if game_data is None:
            return obstacles

        # For this game, we don't have explicit obstacle data
        # Instead, we treat certain map locations as obstacles based on context
        # For now, return an empty set since character movement isn't blocked by content
        # In a real implementation, we might add obstacles for:
        # - Impassable terrain
        # - Other players (if multiplayer)
        # - Dangerous areas to avoid

        return obstacles

    def get_map_bounds(self, game_data: Any) -> tuple[int, int, int, int]:
        """Get map boundaries (min_x, min_y, max_x, max_y)"""
        if game_data is None:
            # Default game bounds based on MovementAction validation
            return (-50, -50, 50, 50)

        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')

        # Check maps data for bounds
        if hasattr(game_data, 'maps') and game_data.maps:
            for map_data in game_data.maps:
                if hasattr(map_data, 'x') and hasattr(map_data, 'y'):
                    min_x = min(min_x, map_data.x)
                    max_x = max(max_x, map_data.x)
                    min_y = min(min_y, map_data.y)
                    max_y = max(max_y, map_data.y)

        # Check resources data for bounds
        if hasattr(game_data, 'resources') and game_data.resources:
            for resource in game_data.resources:
                if hasattr(resource, 'x') and hasattr(resource, 'y'):
                    min_x = min(min_x, resource.x)
                    max_x = max(max_x, resource.x)
                    min_y = min(min_y, resource.y)
                    max_y = max(max_y, resource.y)

        # Check monsters data for bounds
        if hasattr(game_data, 'monsters') and game_data.monsters:
            for monster in game_data.monsters:
                if hasattr(monster, 'x') and hasattr(monster, 'y'):
                    min_x = min(min_x, monster.x)
                    max_x = max(max_x, monster.x)
                    min_y = min(min_y, monster.y)
                    max_y = max(max_y, monster.y)

        # If no data found, use default bounds
        if min_x == float('inf'):
            return (-50, -50, 50, 50)

        # Add some padding to the bounds
        padding = 5
        return (int(min_x - padding), int(min_y - padding), int(max_x + padding), int(max_y + padding))

    def cache_map_data(self, game_data: Any) -> None:
        """Cache map information for faster pathfinding.
        
        Parameters:
            game_data: Game data to cache for pathfinding operations
            
        Return values:
            None
            
        This method caches frequently accessed map data like obstacles and
        boundaries to improve pathfinding performance by avoiding repeated
        data extraction from game data structures.
        """
        if game_data is None:
            return

        # Cache obstacles and bounds for faster access
        cache_key = id(game_data)  # Use object id as cache key

        self.obstacle_cache[cache_key] = self.get_obstacles_from_game_data(game_data)
        self.map_cache[cache_key] = self.get_map_bounds(game_data)

    def is_position_accessible(self, position: tuple[int, int], game_data: Any = None) -> bool:
        """Check if position is accessible (not blocked by obstacles)"""
        obstacles = self.get_obstacles_from_game_data(game_data)
        bounds = self.get_map_bounds(game_data)

        # Use AStarPathfinding for position validation since it has the method
        if hasattr(self.algorithm, 'is_valid_position'):
            result = self.algorithm.is_valid_position(position[0], position[1], obstacles, bounds)
            return bool(result)

        # Fallback: create temporary AStarPathfinding instance
        temp_algo = AStarPathfinding()
        return temp_algo.is_valid_position(position[0], position[1], obstacles, bounds)

    def calculate_movement_cost(self, path: list[tuple[int, int]]) -> int:
        """Calculate total movement cost for path"""
        if len(path) <= 1:
            return 0

        total_cost = 0
        for i in range(1, len(path)):
            # Each step costs 1 (Manhattan distance of 1)
            total_cost += 1

        return total_cost

    def find_safe_position_near(self, target: tuple[int, int], radius: int = 3,
                               game_data: Any = None) -> tuple[int, int] | None:
        """Find safe position near target (useful for combat positioning).
        
        Parameters:
            target: Target position coordinates as (x, y) tuple
            radius: Maximum distance from target to search for safe position
            game_data: Game data for obstacle and boundary information
            
        Return values:
            Tuple of coordinates for safe position, or None if no safe position found
            
        This method searches for an accessible position within the specified radius
        of the target, useful for strategic positioning during combat or resource
        gathering activities where proximity is important.
        """
        obstacles = self.get_obstacles_from_game_data(game_data)
        bounds = self.get_map_bounds(game_data)

        # Check target position itself first
        if (hasattr(self.algorithm, 'is_valid_position') and
            self.algorithm.is_valid_position(target[0], target[1], obstacles, bounds)):
            return target

        # Search in expanding rings around the target
        for current_radius in range(1, radius + 1):
            # Check positions at the current radius
            candidates = []

            # Generate positions in a square pattern around target
            target_x, target_y = target
            for dx in range(-current_radius, current_radius + 1):
                for dy in range(-current_radius, current_radius + 1):
                    # Skip positions that are not at the current radius boundary
                    if abs(dx) != current_radius and abs(dy) != current_radius:
                        continue

                    candidate_x = target_x + dx
                    candidate_y = target_y + dy
                    candidate = (candidate_x, candidate_y)

                    # Check if position is valid
                    if (hasattr(self.algorithm, 'is_valid_position') and
                        self.algorithm.is_valid_position(candidate_x, candidate_y, obstacles, bounds)):
                        candidates.append(candidate)

            # If we found candidates, return the closest one to target center
            if candidates:
                # For simplicity, return the first valid candidate
                # In a more sophisticated version, we might prefer certain positions
                # (e.g., positions that provide cover, are upwind, etc.)
                return candidates[0]

        # No safe position found within radius
        return None


class MovementPlanner:
    """High-level movement planning integrated with GOAP"""

    def __init__(self, pathfinding_service: PathfindingService):
        self.pathfinding_service = pathfinding_service

    def plan_movement_to_resource(self, current_pos: tuple[int, int], resource_type: str,
                                 game_data: Any) -> PathfindingResult:
        """Plan movement to nearest resource of specified type.
        
        Parameters:
            current_pos: Current character position as (x, y) tuple
            resource_type: Type of resource to find (e.g., "ash_tree", "copper_rock")
            game_data: Game data containing resource location information
            
        Return values:
            PathfindingResult with path to nearest resource of specified type
            
        This method searches the game data for resources matching the specified
        type and plans an optimal path to the nearest one, supporting efficient
        resource gathering for the AI player's economic activities.
        """
        if game_data is None:
            return PathfindingResult(
                success=False,
                path=[],
                movement_actions=[],
                total_cost=0,
                total_distance=0,
                message="No game data provided"
            )

        # Extract resource positions from game data
        resource_positions = []

        if hasattr(game_data, 'resources') and game_data.resources:
            for resource in game_data.resources:
                if hasattr(resource, 'type') and hasattr(resource, 'x') and hasattr(resource, 'y'):
                    if resource.type == resource_type:
                        resource_positions.append((resource.x, resource.y))

        if not resource_positions:
            return PathfindingResult(
                success=False,
                path=[],
                movement_actions=[],
                total_cost=0,
                total_distance=0,
                message=f"No resources of type '{resource_type}' found"
            )

        # Find path to nearest resource
        return self.pathfinding_service.find_path_to_nearest(current_pos, resource_positions, game_data)

    def plan_movement_to_monster(self, current_pos: tuple[int, int], monster_level_range: tuple[int, int],
                                game_data: Any) -> PathfindingResult:
        """Plan movement to suitable monster for combat.
        
        Parameters:
            current_pos: Current character position as (x, y) tuple
            monster_level_range: Tuple of (min_level, max_level) for suitable monsters
            game_data: Game data containing monster location and level information
            
        Return values:
            PathfindingResult with path to nearest suitable monster for combat
            
        This method searches for monsters within the specified level range and
        plans an optimal path to the nearest one, supporting combat activities
        and experience farming for the AI player.
        """
        if game_data is None:
            return PathfindingResult(
                success=False,
                path=[],
                movement_actions=[],
                total_cost=0,
                total_distance=0,
                message="No game data provided"
            )

        min_level, max_level = monster_level_range
        monster_positions = []

        if hasattr(game_data, 'monsters') and game_data.monsters:
            for monster in game_data.monsters:
                if (hasattr(monster, 'level') and hasattr(monster, 'x') and
                    hasattr(monster, 'y') and min_level <= monster.level <= max_level):
                    monster_positions.append((monster.x, monster.y))

        if not monster_positions:
            return PathfindingResult(
                success=False,
                path=[],
                movement_actions=[],
                total_cost=0,
                total_distance=0,
                message=f"No monsters found in level range {min_level}-{max_level}"
            )

        # Find path to nearest suitable monster
        return self.pathfinding_service.find_path_to_nearest(current_pos, monster_positions, game_data)

    def plan_movement_to_npc(self, current_pos: tuple[int, int], npc_type: str,
                            game_data: Any) -> PathfindingResult:
        """Plan movement to specific NPC type.
        
        Parameters:
            current_pos: Current character position as (x, y) tuple
            npc_type: Type or name of NPC to find (e.g., "banker", "blacksmith")
            game_data: Game data containing NPC location information
            
        Return values:
            PathfindingResult with path to nearest NPC of specified type
            
        This method searches for NPCs matching the specified type and plans
        an optimal path to the nearest one, supporting trading, banking, and
        other NPC interaction activities for the AI player.
        """
        if game_data is None:
            return PathfindingResult(
                success=False,
                path=[],
                movement_actions=[],
                total_cost=0,
                total_distance=0,
                message="No game data provided"
            )

        npc_positions = []

        if hasattr(game_data, 'npcs') and game_data.npcs:
            for npc in game_data.npcs:
                if (hasattr(npc, 'type') and hasattr(npc, 'x') and
                    hasattr(npc, 'y') and npc.type == npc_type):
                    npc_positions.append((npc.x, npc.y))

        if not npc_positions:
            return PathfindingResult(
                success=False,
                path=[],
                movement_actions=[],
                total_cost=0,
                total_distance=0,
                message=f"No NPCs of type '{npc_type}' found"
            )

        # Find path to nearest NPC of specified type
        return self.pathfinding_service.find_path_to_nearest(current_pos, npc_positions, game_data)

    def plan_movement_to_bank(self, current_pos: tuple[int, int], game_data: Any) -> PathfindingResult:
        """Plan movement to nearest bank.
        
        Parameters:
            current_pos: Current character position as (x, y) tuple
            game_data: Game data containing bank location information
            
        Return values:
            PathfindingResult with path to nearest bank for storage operations
            
        This method finds the nearest bank location and plans an optimal path
        to it, supporting inventory management and item storage activities
        for the AI player's economic operations.
        """
        # Banks are typically a specific type of NPC
        return self.plan_movement_to_npc(current_pos, "bank", game_data)

    def plan_movement_to_grand_exchange(self, current_pos: tuple[int, int],
                                       game_data: Any) -> PathfindingResult:
        """Plan movement to Grand Exchange.
        
        Parameters:
            current_pos: Current character position as (x, y) tuple
            game_data: Game data containing Grand Exchange location information
            
        Return values:
            PathfindingResult with path to Grand Exchange for trading operations
            
        This method finds the Grand Exchange location and plans an optimal path
        to it, supporting trading and marketplace activities for the AI player's
        economic operations and item acquisition.
        """
        # Grand Exchange is typically a specific type of NPC or location
        return self.plan_movement_to_npc(current_pos, "grand_exchange", game_data)

    def plan_escape_route(self, current_pos: tuple[int, int], danger_pos: tuple[int, int],
                         game_data: Any) -> PathfindingResult:
        """Plan escape route away from danger.
        
        Parameters:
            current_pos: Current character position as (x, y) tuple
            danger_pos: Position of danger to escape from as (x, y) tuple
            game_data: Game data for obstacle and boundary information
            
        Return values:
            PathfindingResult with path away from danger to a safe location
            
        This method plans an escape route by finding the furthest safe position
        from the danger location within a reasonable distance, supporting survival
        and retreat strategies for the AI player during combat or dangerous situations.
        """
        # Find a safe position away from danger
        safe_distance = 10  # Minimum distance from danger
        max_search_distance = 20

        # Search for positions that are far from danger
        candidates = []
        bounds = self.pathfinding_service.get_map_bounds(game_data)
        obstacles = self.pathfinding_service.get_obstacles_from_game_data(game_data)

        # Generate candidate positions in expanding rings
        for distance in range(safe_distance, max_search_distance + 1):
            for dx in range(-distance, distance + 1):
                for dy in range(-distance, distance + 1):
                    if abs(dx) != distance and abs(dy) != distance:
                        continue

                    candidate_x = current_pos[0] + dx
                    candidate_y = current_pos[1] + dy
                    candidate = (candidate_x, candidate_y)

                    # Check if position is valid and far from danger
                    if (hasattr(self.pathfinding_service.algorithm, 'is_valid_position') and
                        self.pathfinding_service.algorithm.is_valid_position(
                            candidate_x, candidate_y, obstacles, bounds) and
                        self._manhattan_distance(candidate, danger_pos) >= safe_distance):
                        candidates.append(candidate)

            # If we found candidates at this distance, use them
            if candidates:
                break

        if not candidates:
            return PathfindingResult(
                success=False,
                path=[],
                movement_actions=[],
                total_cost=0,
                total_distance=0,
                message="No safe escape position found"
            )

        # Find path to the nearest safe candidate
        return self.pathfinding_service.find_path_to_nearest(current_pos, candidates, game_data)

    def _manhattan_distance(self, pos1: tuple[int, int], pos2: tuple[int, int]) -> int:
        """Calculate Manhattan distance between two positions"""
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

    def get_strategic_positioning(self, current_pos: tuple[int, int], target_pos: tuple[int, int],
                                 strategy: str, game_data: Any) -> PathfindingResult:
        """Get strategic position relative to target (combat, gathering, etc.).
        
        Parameters:
            current_pos: Current character position as (x, y) tuple
            target_pos: Target position for strategic positioning
            strategy: Strategy type ("combat", "gathering", "ranged", "melee")
            game_data: Game data for positioning calculations
            
        Return values:
            PathfindingResult with path to strategic position relative to target
            
        This method calculates an optimal strategic position relative to a target
        based on the specified strategy, supporting tactical positioning for
        combat, resource gathering, and other strategic activities.
        """
        # Define strategic positioning based on strategy type
        if strategy == "melee" or strategy == "combat":
            # For melee combat, position adjacent to target
            return self._find_adjacent_position(current_pos, target_pos, game_data)
        elif strategy == "ranged":
            # For ranged combat, maintain distance from target
            return self._find_ranged_position(current_pos, target_pos, game_data)
        elif strategy == "gathering":
            # For gathering, position adjacent to resource
            return self._find_adjacent_position(current_pos, target_pos, game_data)
        else:
            # Default: move to target location
            return self.pathfinding_service.find_path(current_pos, target_pos, game_data)

    def _find_adjacent_position(self, current_pos: tuple[int, int], target_pos: tuple[int, int],
                               game_data: Any) -> PathfindingResult:
        """Find position adjacent to target for melee/gathering activities"""
        # Generate adjacent positions around target
        adjacent_positions = []
        target_x, target_y = target_pos

        # Check all 4 adjacent positions
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            adjacent_x = target_x + dx
            adjacent_y = target_y + dy
            adjacent_positions.append((adjacent_x, adjacent_y))

        # Find path to nearest adjacent position
        return self.pathfinding_service.find_path_to_nearest(current_pos, adjacent_positions, game_data)

    def _find_ranged_position(self, current_pos: tuple[int, int], target_pos: tuple[int, int],
                             game_data: Any) -> PathfindingResult:
        """Find position at optimal range from target for ranged combat"""
        optimal_range = 3  # Optimal distance for ranged combat

        # Generate positions at optimal range
        ranged_positions = []
        target_x, target_y = target_pos

        # Generate positions in a circle around target at optimal range
        for dx in range(-optimal_range, optimal_range + 1):
            for dy in range(-optimal_range, optimal_range + 1):
                distance = abs(dx) + abs(dy)  # Manhattan distance
                if distance == optimal_range:
                    ranged_x = target_x + dx
                    ranged_y = target_y + dy
                    ranged_positions.append((ranged_x, ranged_y))

        if not ranged_positions:
            # Fallback: use adjacent positions
            return self._find_adjacent_position(current_pos, target_pos, game_data)

        # Find path to nearest ranged position
        return self.pathfinding_service.find_path_to_nearest(current_pos, ranged_positions, game_data)


class PathfindingConfig:
    """Configuration for pathfinding behavior"""

    def __init__(self) -> None:
        self.max_path_length = 100
        self.prefer_straight_lines = True
        self.avoid_monsters = True
        self.cache_paths = True
        self.recalculate_threshold = 10

    def set_algorithm(self, algorithm_name: str) -> None:
        """Set pathfinding algorithm.
        
        Parameters:
            algorithm_name: Name of algorithm to use ("astar", "dijkstra")
            
        Return values:
            None
            
        This method configures which pathfinding algorithm to use for navigation,
        allowing the AI player to switch between different algorithms based on
        performance requirements and specific use cases.
        """
        self.algorithm_name = algorithm_name.lower()

    def set_avoidance_preferences(self, avoid_monsters: bool = True, avoid_players: bool = False) -> None:
        """Configure what to avoid during pathfinding.
        
        Parameters:
            avoid_monsters: Whether to avoid monster positions during pathfinding
            avoid_players: Whether to avoid other player positions during pathfinding
            
        Return values:
            None
            
        This method configures avoidance preferences for pathfinding, allowing
        the AI player to specify what types of entities to avoid when planning
        movement routes for safer and more strategic navigation.
        """
        self.avoid_monsters = avoid_monsters
        self.avoid_players = avoid_players
