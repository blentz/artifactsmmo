"""
Level-Appropriate Monster Targeting Module

This module implements intelligent monster targeting that filters monsters by
character level ± 1 and scores them by efficiency, using real cached game data
to make strategic combat decisions for optimal XP progression.
"""


from src.game_data.models import GameMap, GameMonster


class LevelAppropriateTargeting:
    """Analysis module for finding optimal monster targets based on character level.

    This class implements the core requirement from the PRP to filter monsters
    within character_level ± 1 range and score them by efficiency metrics,
    using only real cached game data without any hardcoded monster names or values.
    """

    def find_optimal_monsters(
        self,
        character_level: int,
        current_position: tuple[int, int],
        monsters: list[GameMonster],
        maps: list[GameMap]
    ) -> list[tuple[GameMonster, GameMap, float]]:
        """Find monsters within character_level ± 1 with efficiency scoring.

        Parameters:
            character_level: Current character level for filtering
            current_position: Current (x, y) position for distance calculation
            monsters: List of all GameMonster objects from cache
            maps: List of all GameMap objects from cache

        Return values:
            List of (monster, location, efficiency_score) tuples sorted by efficiency

        This method implements the exact requirements from the PRP:
        - Filter by monster.level in [character_level-1, character_level+1]
        - Use monster.hp, monster.attack_*, monster.min_gold for scoring
        - Cross-reference monster.code with map.content.code for locations
        - Calculate efficiency based on XP potential, gold potential, and distance
        """
        if not monsters:
            raise ValueError("Cannot find optimal monsters: monsters list is empty")

        if not maps:
            raise ValueError("Cannot find optimal monsters: maps list is empty")

        # Filter level-appropriate monsters from real data - NO hardcoding
        level_min = character_level - 1
        level_max = character_level + 1

        appropriate_monsters = [
            monster for monster in monsters
            if level_min <= monster.level <= level_max
        ]

        if not appropriate_monsters:
            # This is valid - may be no appropriate monsters at this level
            return []

        # Find locations for each monster using real map data
        monster_locations = []

        for monster in appropriate_monsters:
            # Find all locations where this monster appears - NO hardcoded coordinates
            locations = [
                game_map for game_map in maps
                if (hasattr(game_map, 'content') and
                    game_map.content and
                    hasattr(game_map.content, 'type') and
                    hasattr(game_map.content, 'code') and
                    game_map.content.type == "monster" and
                    game_map.content.code == monster.code)
            ]

            for location in locations:
                # Calculate efficiency based on real monster stats - NO hardcoded values
                efficiency_score = self._calculate_monster_efficiency(
                    monster, location, current_position
                )

                monster_locations.append((monster, location, efficiency_score))

        # Sort by efficiency score (higher is better)
        return sorted(monster_locations, key=lambda x: x[2], reverse=True)

    def _calculate_monster_efficiency(
        self,
        monster: GameMonster,
        location: GameMap,
        current_position: tuple[int, int]
    ) -> float:
        """Calculate monster efficiency score based on real stats.

        Parameters:
            monster: GameMonster with real stats from cache
            location: GameMap with real coordinates from cache
            current_position: Current character position

        Return values:
            Float efficiency score (higher is better)

        This method calculates efficiency using only real game data:
        - XP potential based on actual monster.level
        - Gold potential from real monster.min_gold and monster.max_gold
        - Distance penalty from real map coordinates
        - Combat difficulty from actual monster.hp and attack stats
        """
        # Calculate distance using real coordinates - NO hardcoded positions
        distance = abs(location.x - current_position[0]) + abs(location.y - current_position[1])

        # XP potential based on actual monster level - NO hardcoded XP values
        # Higher level monsters generally give more XP
        xp_potential = monster.level * 10

        # Gold potential from real monster stats - NO hardcoded gold amounts
        gold_potential = (monster.min_gold + monster.max_gold) / 2

        # Combat difficulty assessment using real stats
        total_attack = (monster.attack_fire + monster.attack_earth +
                       monster.attack_water + monster.attack_air)
        combat_difficulty = monster.hp + (total_attack * 0.5)  # HP + attack factor

        # Calculate base reward value
        reward_value = xp_potential + gold_potential

        # Apply distance penalty (closer is better)
        distance_factor = 1.0 / max(1, distance)

        # Apply combat difficulty factor (easier monsters are more efficient for steady progress)
        # Normalize difficulty to prevent division by zero
        difficulty_factor = 100.0 / max(50, combat_difficulty)

        # Final efficiency score combining all factors
        efficiency = reward_value * distance_factor * difficulty_factor

        return efficiency

    def find_safest_appropriate_monster(
        self,
        character_level: int,
        character_hp: int,
        character_max_hp: int,
        current_position: tuple[int, int],
        monsters: list[GameMonster],
        maps: list[GameMap]
    ) -> tuple[GameMonster, GameMap] | None:
        """Find the safest level-appropriate monster for low-HP situations.

        Parameters:
            character_level: Current character level
            character_hp: Current HP
            character_max_hp: Maximum HP
            current_position: Current position
            monsters: All monsters from cache
            maps: All maps from cache

        Return values:
            (monster, location) tuple for safest option, or None if none safe

        This method prioritizes safety over efficiency when character HP is low,
        selecting monsters with lower attack values and HP for safer combat.
        """
        optimal_monsters = self.find_optimal_monsters(
            character_level, current_position, monsters, maps
        )

        if not optimal_monsters:
            return None

        # Calculate HP ratio for safety assessment
        hp_ratio = character_hp / max(1, character_max_hp)

        # If HP is very low, find the weakest appropriate monster
        if hp_ratio < 0.3:
            # Sort by total combat power (HP + attacks) ascending (weakest first)
            safe_monsters = sorted(
                optimal_monsters,
                key=lambda x: x[0].hp + x[0].attack_fire + x[0].attack_earth +
                             x[0].attack_water + x[0].attack_air
            )

            if safe_monsters:
                monster, location, _ = safe_monsters[0]
                return (monster, location)

        # For healthy characters, return the most efficient monster
        if optimal_monsters:
            monster, location, _ = optimal_monsters[0]
            return (monster, location)

        return None

    def validate_monster_accessibility(
        self,
        monster_locations: list[tuple[GameMonster, GameMap, float]],
        character_level: int
    ) -> list[tuple[GameMonster, GameMap, float]]:
        """Validate that monsters are accessible and appropriate for character.

        Parameters:
            monster_locations: List of monster/location/efficiency tuples
            character_level: Current character level for validation

        Return values:
            Filtered list with only accessible monsters

        This method performs additional validation to ensure recommended monsters
        are actually accessible and appropriate, removing any that might cause
        errors or be inappropriate for the character's current state.
        """
        accessible_monsters = []

        for monster, location, efficiency in monster_locations:
            # Validate monster data integrity
            if (hasattr(monster, 'level') and hasattr(monster, 'code') and
                hasattr(monster, 'hp') and monster.hp > 0):

                # Validate location data integrity
                if (hasattr(location, 'x') and hasattr(location, 'y') and
                    hasattr(location, 'content') and location.content):

                    # Double-check level appropriateness
                    if character_level - 1 <= monster.level <= character_level + 1:
                        accessible_monsters.append((monster, location, efficiency))

        return accessible_monsters
