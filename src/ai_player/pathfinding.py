"""
Pathfinding Module

This module provides backwards-compatible imports for the pathfinding system.
All classes have been refactored into logical groups following the one-class-per-file
principle while maintaining the same import interface.
"""

# Import all classes from their logical group files
from .pathfinding_models import PathNode, PathfindingResult
from .pathfinding_algorithms import PathfindingAlgorithm, AStarPathfinding, DijkstraPathfinding
from .pathfinding_services import PathfindingService, MovementPlanner
from .pathfinding_config import PathfindingConfig

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
