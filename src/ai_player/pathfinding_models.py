"""
Pathfinding Data Models

This module defines the core data structures used throughout the pathfinding
system, including nodes and results for pathfinding operations.
"""

from dataclasses import dataclass
from typing import Optional

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
