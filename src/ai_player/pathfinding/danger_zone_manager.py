"""
Danger Zone Manager

This module manages monster danger zones and their influence on pathfinding,
providing danger level calculations and obstacle detection for safer navigation.
"""

from dataclasses import dataclass
from typing import Any, Dict, Set, Tuple


@dataclass
class MonsterInfo:
    """Information about a monster and its danger zone"""

    x: int
    y: int
    level: int
    danger_radius: int
    aggro_range: int


class DangerZoneManager:
    """Manages monster danger zones and their influence on pathfinding"""

    def __init__(self) -> None:
        self.monsters: Dict[Tuple[int, int], MonsterInfo] = {}
        self.danger_cache: Dict[Tuple[int, int], float] = {}
        self.base_danger_radius = 3  # Base radius for level 1 monsters
        self.level_radius_factor = 0.5  # How much radius increases per level
        self.max_danger_radius = 10  # Maximum danger zone radius

    def update_monster_positions(self, game_data: Any) -> None:
        """Update monster positions and danger zones from game data.

        Parameters:
            game_data: Game data containing monster information

        This method updates the internal monster tracking with the latest positions
        and recalculates danger zones based on monster levels and positions.
        """
        self.monsters.clear()
        self.danger_cache.clear()

        if not hasattr(game_data, "monsters") or not game_data.monsters:
            return

        for monster in game_data.monsters:
            if not all(hasattr(monster, attr) for attr in ["x", "y", "level"]):
                continue

            # Calculate danger radius based on monster level
            danger_radius = min(
                self.base_danger_radius + int(monster.level * self.level_radius_factor), self.max_danger_radius
            )

            # Calculate aggro range (slightly smaller than danger radius)
            aggro_range = max(1, danger_radius - 1)

            monster_info = MonsterInfo(
                x=monster.x, y=monster.y, level=monster.level, danger_radius=danger_radius, aggro_range=aggro_range
            )
            self.monsters[(monster.x, monster.y)] = monster_info

    def get_danger_level(self, x: int, y: int) -> float:
        """Calculate danger level at a specific position.

        Parameters:
            x: X coordinate to check
            y: Y coordinate to check

        Return values:
            Float between 0.0 and 1.0 representing danger level

        This method calculates the danger level at a position based on proximity
        to monsters and their levels, with 0.0 being completely safe and 1.0 being
        maximum danger.
        """
        pos = (x, y)
        if pos in self.danger_cache:
            return self.danger_cache[pos]

        max_danger = 0.0
        for monster in self.monsters.values():
            distance = abs(x - monster.x) + abs(y - monster.y)  # Manhattan distance

            if distance > monster.danger_radius:
                continue

            # Calculate danger based on distance and monster level
            # Closer = more dangerous, higher level = more dangerous
            distance_factor = 1 - (distance / monster.danger_radius)
            level_factor = min(monster.level / 10, 1.0)  # Cap level influence at 10
            danger = distance_factor * (0.5 + 0.5 * level_factor)

            max_danger = max(max_danger, danger)

        self.danger_cache[pos] = max_danger
        return max_danger

    def get_danger_zones(self, high_danger_only: bool = False) -> Set[Tuple[int, int]]:
        """Get set of positions considered dangerous.

        Parameters:
            high_danger_only: If True, only return positions with very high danger

        Return values:
            Set of (x, y) tuples representing dangerous positions

        This method returns positions that should be treated as obstacles due to
        high monster danger levels, supporting safer pathfinding by avoiding
        dangerous areas. When high_danger_only is True, only positions with
        extreme danger (like monster positions) are returned, allowing movement
        through less dangerous areas when necessary.
        """
        danger_zones = set()

        for monster in self.monsters.values():
            # Always add monster positions as danger zones
            danger_zones.add((monster.x, monster.y))

            if not high_danger_only:
                # Add positions within aggro range as danger zones
                for dx in range(-monster.aggro_range, monster.aggro_range + 1):
                    for dy in range(-monster.aggro_range, monster.aggro_range + 1):
                        if abs(dx) + abs(dy) <= monster.aggro_range:  # Manhattan distance check
                            danger_zones.add((monster.x + dx, monster.y + dy))

        return danger_zones

    def get_movement_cost_multiplier(self, x: int, y: int) -> float:
        """Calculate movement cost multiplier based on danger level.

        Parameters:
            x: X coordinate to check
            y: Y coordinate to check

        Return values:
            Float >= 1.0 representing movement cost multiplier

        This method calculates how much more expensive movement through a position
        should be based on its danger level, making pathfinding prefer safer
        routes when available.
        """
        danger_level = self.get_danger_level(x, y)
        if danger_level == 0:
            return 1.0

        # Exponential cost increase based on danger level
        # At maximum danger (1.0), cost is multiplied by 5
        return 1.0 + 4.0 * danger_level

    def is_safe_position(self, x: int, y: int, safety_threshold: float = 0.3) -> bool:
        """Check if a position is considered safe.

        Parameters:
            x: X coordinate to check
            y: Y coordinate to check
            safety_threshold: Maximum danger level considered safe (0.0 to 1.0)

        Return values:
            Boolean indicating whether position is safe

        This method determines if a position is safe for the character based on
        its danger level and the specified safety threshold, supporting strategic
        positioning and path planning.
        """
        return self.get_danger_level(x, y) <= safety_threshold
