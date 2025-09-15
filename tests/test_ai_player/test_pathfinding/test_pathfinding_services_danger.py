"""Tests for pathfinding service danger zone integration"""

from dataclasses import dataclass
from typing import List

import pytest

from src.ai_player.pathfinding.services import PathfindingService
from src.ai_player.pathfinding_algorithms import AStarPathfinding


@dataclass
class MockMonster:
    """Mock monster for testing"""

    x: int
    y: int
    level: int


@dataclass
class MockGameData:
    """Mock game data for testing"""

    monsters: List[MockMonster]


def test_pathfinding_service_init():
    """Test PathfindingService initialization with danger zone manager"""
    service = PathfindingService()
    assert service.danger_zone_manager is not None


def test_get_obstacles_with_danger_zones():
    """Test obstacle detection including danger zones"""
    service = PathfindingService()

    # Create mock game data with monsters
    game_data = MockGameData(monsters=[MockMonster(x=0, y=0, level=1), MockMonster(x=5, y=5, level=5)])

    obstacles = service.get_obstacles_from_game_data(game_data)

    # Check that danger zones are included in obstacles
    assert (0, 0) in obstacles  # Monster position
    assert (1, 0) in obstacles  # Adjacent to monster
    assert (5, 5) in obstacles  # Second monster position


def test_movement_cost_with_danger():
    """Test movement cost calculation with danger zones"""
    service = PathfindingService()

    # Create mock game data with one monster
    game_data = MockGameData(monsters=[MockMonster(x=0, y=0, level=1)])

    # Test path through safe area
    safe_path = [(5, 5), (6, 5), (7, 5)]
    safe_cost = service.calculate_movement_cost(safe_path, game_data)
    assert safe_cost == 2.0  # Base cost for 2 steps

    # Test path through dangerous area
    danger_path = [(0, 1), (0, 0), (1, 0)]
    danger_cost = service.calculate_movement_cost(danger_path, game_data)
    assert danger_cost > safe_cost  # Should be more expensive


def test_pathfinding_avoids_danger():
    """Test that pathfinding avoids dangerous areas"""
    service = PathfindingService()

    # Create mock game data with monster in the middle
    game_data = MockGameData(
        monsters=[
            MockMonster(x=5, y=5, level=5)  # Monster in the middle
        ]
    )

    # Try to find path that would normally go through monster position
    start = (0, 0)
    goal = (10, 10)

    result = service.find_path(start, goal, game_data)

    # Path should exist and avoid the monster
    assert result.success
    assert (5, 5) not in result.path  # Should not go through monster

    # Calculate path length - should be longer than direct route
    direct_distance = abs(goal[0] - start[0]) + abs(goal[1] - start[1])
    assert len(result.path) > direct_distance  # Path should be longer to avoid danger


def test_pathfinding_with_multiple_monsters():
    """Test pathfinding with multiple monsters creating danger zones"""
    service = PathfindingService()

    # Create mock game data with multiple monsters
    game_data = MockGameData(
        monsters=[MockMonster(x=3, y=3, level=2), MockMonster(x=6, y=6, level=3), MockMonster(x=4, y=7, level=4)]
    )

    start = (0, 0)
    goal = (10, 10)

    result = service.find_path(start, goal, game_data)

    # Path should exist and avoid all monsters
    assert result.success
    for monster in game_data.monsters:
        assert (monster.x, monster.y) not in result.path


def test_pathfinding_with_unavoidable_danger():
    """Test pathfinding when danger cannot be completely avoided"""
    service = PathfindingService()

    # Create mock game data with monsters blocking all paths
    # Place monsters further apart to allow movement between them
    game_data = MockGameData(
        monsters=[MockMonster(x=2, y=0, level=1), MockMonster(x=2, y=2, level=1), MockMonster(x=2, y=4, level=1)]
    )

    start = (0, 2)
    goal = (4, 2)

    result = service.find_path(start, goal, game_data)

    # Should still find a path, but it will have to go through danger
    assert result.success

    # Cost should be higher due to danger
    path_cost = service.calculate_movement_cost(result.path, game_data)
    base_cost = float(len(result.path))
    assert path_cost > base_cost
