"""Tests for the DangerZoneManager class"""

from dataclasses import dataclass
from typing import List

import pytest

from src.ai_player.pathfinding.danger_zone_manager import DangerZoneManager


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


def test_danger_zone_manager_init():
    """Test DangerZoneManager initialization"""
    manager = DangerZoneManager()
    assert manager.monsters == {}
    assert manager.danger_cache == {}
    assert manager.base_danger_radius > 0
    assert manager.level_radius_factor > 0
    assert manager.max_danger_radius > manager.base_danger_radius


def test_update_monster_positions():
    """Test updating monster positions"""
    manager = DangerZoneManager()

    # Create mock game data with monsters
    game_data = MockGameData(monsters=[MockMonster(x=0, y=0, level=1), MockMonster(x=5, y=5, level=5)])

    manager.update_monster_positions(game_data)

    assert len(manager.monsters) == 2
    assert (0, 0) in manager.monsters
    assert (5, 5) in manager.monsters
    assert manager.monsters[(0, 0)].level == 1
    assert manager.monsters[(5, 5)].level == 5


def test_get_danger_level():
    """Test danger level calculation"""
    manager = DangerZoneManager()

    # Create mock game data with one monster
    game_data = MockGameData(monsters=[MockMonster(x=0, y=0, level=1)])

    manager.update_monster_positions(game_data)

    # Test danger levels at different distances
    assert manager.get_danger_level(0, 0) > 0.5  # At monster position
    assert manager.get_danger_level(1, 0) > 0  # Adjacent
    assert manager.get_danger_level(10, 10) == 0  # Far away


def test_get_danger_zones():
    """Test danger zone generation"""
    manager = DangerZoneManager()

    # Create mock game data with one monster
    game_data = MockGameData(monsters=[MockMonster(x=0, y=0, level=1)])

    manager.update_monster_positions(game_data)
    danger_zones = manager.get_danger_zones()

    # Check that danger zones include monster position and adjacent tiles
    assert (0, 0) in danger_zones
    assert (1, 0) in danger_zones
    assert (0, 1) in danger_zones
    assert (-1, 0) in danger_zones
    assert (0, -1) in danger_zones


def test_get_movement_cost_multiplier():
    """Test movement cost multiplier calculation"""
    manager = DangerZoneManager()

    # Create mock game data with one monster
    game_data = MockGameData(monsters=[MockMonster(x=0, y=0, level=1)])

    manager.update_monster_positions(game_data)

    # Test cost multipliers at different positions
    assert manager.get_movement_cost_multiplier(0, 0) > 1.0  # At monster position
    assert manager.get_movement_cost_multiplier(1, 0) > 1.0  # Adjacent
    assert manager.get_movement_cost_multiplier(10, 10) == 1.0  # Far away


def test_is_safe_position():
    """Test safety check functionality"""
    manager = DangerZoneManager()

    # Create mock game data with one monster
    game_data = MockGameData(monsters=[MockMonster(x=0, y=0, level=1)])

    manager.update_monster_positions(game_data)

    # Test safety at different positions
    assert not manager.is_safe_position(0, 0)  # At monster position
    assert not manager.is_safe_position(1, 0)  # Adjacent
    assert manager.is_safe_position(10, 10)  # Far away


def test_danger_scaling_with_level():
    """Test that danger scales with monster level"""
    manager = DangerZoneManager()

    # Create mock game data with two monsters of different levels
    game_data = MockGameData(monsters=[MockMonster(x=0, y=0, level=1), MockMonster(x=10, y=10, level=5)])

    manager.update_monster_positions(game_data)

    # Higher level monster should have larger danger radius
    low_level_danger = manager.get_danger_level(1, 0)  # Near level 1 monster
    high_level_danger = manager.get_danger_level(11, 10)  # Same distance from level 5 monster

    assert high_level_danger > low_level_danger


def test_danger_cache():
    """Test danger level caching"""
    manager = DangerZoneManager()

    # Create mock game data with one monster
    game_data = MockGameData(monsters=[MockMonster(x=0, y=0, level=1)])

    manager.update_monster_positions(game_data)

    # First call should cache the result
    danger_level = manager.get_danger_level(0, 0)
    assert (0, 0) in manager.danger_cache
    assert manager.danger_cache[(0, 0)] == danger_level

    # Second call should use cached value
    cached_danger_level = manager.get_danger_level(0, 0)
    assert cached_danger_level == danger_level
