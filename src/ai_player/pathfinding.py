"""
Pathfinding Module

This module provides backwards-compatible imports for the pathfinding system.
All classes have been refactored into logical groups following the one-class-per-file
principle while maintaining the same import interface.
"""

# Import all classes from their logical group files
from .pathfinding_algorithms import AStarPathfinding, DijkstraPathfinding, PathfindingAlgorithm
from .pathfinding_config import PathfindingConfig
from .pathfinding_models import PathfindingResult, PathNode
from .pathfinding_services import MovementPlanner, PathfindingService

# Re-export all classes for backwards compatibility
__all__ = [
    # Data Models
    "PathNode",
    "PathfindingResult",

    # Algorithms
    "PathfindingAlgorithm",
    "AStarPathfinding",
    "DijkstraPathfinding",

    # Services
    "PathfindingService",
    "MovementPlanner",

    # Configuration
    "PathfindingConfig"
]
