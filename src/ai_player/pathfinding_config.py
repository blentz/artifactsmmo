"""
Pathfinding Configuration

This module contains configuration classes for customizing pathfinding
behavior and algorithm selection in the AI player system.
"""


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