"""
Pathfinding Algorithms

This module contains the pathfinding algorithm implementations including
A* and Dijkstra algorithms for efficient path calculation in the game world.
"""

import heapq
from abc import ABC, abstractmethod

from .actions.movement_action import MovementAction
from .pathfinding_models import PathfindingResult, PathNode


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
