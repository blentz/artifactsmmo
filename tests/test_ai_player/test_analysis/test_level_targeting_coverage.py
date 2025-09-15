"""
Comprehensive tests for LevelAppropriateTargeting to achieve 100% code coverage.

This module focuses on testing all code paths, edge cases, and error conditions
in the LevelAppropriateTargeting implementation to ensure complete test coverage.
"""

import pytest
from unittest.mock import Mock

from src.ai_player.analysis.level_targeting import LevelAppropriateTargeting
from src.game_data.models import GameMap, GameMonster


def create_mock_monster(
    code: str = "test_monster",
    level: int = 5,
    hp: int = 100,
    attack_fire: int = 10,
    attack_earth: int = 10,
    attack_water: int = 10,
    attack_air: int = 10,
    min_gold: int = 5,
    max_gold: int = 15,
    **kwargs
):
    """Create a mock monster with specified attributes."""
    monster = Mock(spec=GameMonster)
    monster.code = code
    monster.level = level
    monster.hp = hp
    monster.attack_fire = attack_fire
    monster.attack_earth = attack_earth
    monster.attack_water = attack_water
    monster.attack_air = attack_air
    monster.min_gold = min_gold
    monster.max_gold = max_gold
    
    # Add any additional attributes
    for key, value in kwargs.items():
        setattr(monster, key, value)
    
    return monster


def create_mock_map_content(content_type: str = "monster", code: str = "test_monster"):
    """Create a mock map content object."""
    content = Mock()
    content.type = content_type
    content.code = code
    return content


def create_mock_map(
    x: int = 10,
    y: int = 10,
    content_type: str = "monster",
    content_code: str = "test_monster",
    **kwargs
):
    """Create a mock map with specified coordinates and content."""
    game_map = Mock(spec=GameMap)
    game_map.x = x
    game_map.y = y
    game_map.content = create_mock_map_content(content_type, content_code)
    
    # Add any additional attributes
    for key, value in kwargs.items():
        setattr(game_map, key, value)
    
    return game_map


class TestLevelAppropriateTargeting:
    """Comprehensive tests for LevelAppropriateTargeting class."""

    def test_find_optimal_monsters_empty_monsters_list(self):
        """Test find_optimal_monsters raises error with empty monsters list."""
        targeting = LevelAppropriateTargeting()
        
        with pytest.raises(ValueError, match="Cannot find optimal monsters: monsters list is empty"):
            targeting.find_optimal_monsters(
                character_level=5,
                current_position=(0, 0),
                monsters=[],
                maps=[create_mock_map()]
            )

    def test_find_optimal_monsters_empty_maps_list(self):
        """Test find_optimal_monsters raises error with empty maps list."""
        targeting = LevelAppropriateTargeting()
        
        with pytest.raises(ValueError, match="Cannot find optimal monsters: maps list is empty"):
            targeting.find_optimal_monsters(
                character_level=5,
                current_position=(0, 0),
                monsters=[create_mock_monster()],
                maps=[]
            )

    def test_find_optimal_monsters_no_appropriate_level_monsters(self):
        """Test find_optimal_monsters returns empty list when no monsters in level range."""
        targeting = LevelAppropriateTargeting()
        
        # Create monsters outside level range
        monsters = [
            create_mock_monster(code="too_low", level=1),     # character_level - 1 = 4, this is too low
            create_mock_monster(code="too_high", level=10)    # character_level + 1 = 6, this is too high
        ]
        maps = [create_mock_map()]
        
        result = targeting.find_optimal_monsters(
            character_level=5,
            current_position=(0, 0),
            monsters=monsters,
            maps=maps
        )
        
        assert result == []

    def test_find_optimal_monsters_level_filtering(self):
        """Test find_optimal_monsters correctly filters by level range."""
        targeting = LevelAppropriateTargeting()
        
        # Create monsters at various levels
        monsters = [
            create_mock_monster(code="too_low", level=3),      # Below range
            create_mock_monster(code="level_4", level=4),      # In range (5-1)
            create_mock_monster(code="level_5", level=5),      # In range (exact)
            create_mock_monster(code="level_6", level=6),      # In range (5+1)
            create_mock_monster(code="too_high", level=7)      # Above range
        ]
        
        # Create maps for all monsters
        maps = [
            create_mock_map(x=0, y=0, content_code="too_low"),
            create_mock_map(x=1, y=1, content_code="level_4"),
            create_mock_map(x=2, y=2, content_code="level_5"),
            create_mock_map(x=3, y=3, content_code="level_6"),
            create_mock_map(x=4, y=4, content_code="too_high")
        ]
        
        result = targeting.find_optimal_monsters(
            character_level=5,
            current_position=(0, 0),
            monsters=monsters,
            maps=maps
        )
        
        # Should only include monsters with levels 4, 5, 6
        assert len(result) == 3
        found_codes = {monster.code for monster, _, _ in result}
        assert found_codes == {"level_4", "level_5", "level_6"}

    def test_find_optimal_monsters_map_content_filtering(self):
        """Test find_optimal_monsters correctly filters maps by content type and code."""
        targeting = LevelAppropriateTargeting()
        
        monster = create_mock_monster(code="target_monster", level=5)
        monsters = [monster]
        
        # Create maps with different content types and codes
        maps = [
            create_mock_map(x=0, y=0, content_type="resource", content_code="target_monster"),  # Wrong type
            create_mock_map(x=1, y=1, content_type="monster", content_code="wrong_monster"),    # Wrong code
            create_mock_map(x=2, y=2, content_type="monster", content_code="target_monster"),   # Match!
            create_mock_map(x=3, y=3, content_type="npc", content_code="target_monster")        # Wrong type
        ]
        
        result = targeting.find_optimal_monsters(
            character_level=5,
            current_position=(0, 0),
            monsters=monsters,
            maps=maps
        )
        
        # Should only find the one matching location
        assert len(result) == 1
        _, location, _ = result[0]
        assert location.x == 2
        assert location.y == 2

    def test_find_optimal_monsters_map_content_missing_attributes(self):
        """Test find_optimal_monsters handles maps with missing content attributes."""
        targeting = LevelAppropriateTargeting()
        
        monster = create_mock_monster(code="target_monster", level=5)
        monsters = [monster]
        
        # Create maps with missing attributes
        map_no_content = Mock(spec=GameMap)
        map_no_content.x = 0
        map_no_content.y = 0
        # No content attribute
        
        map_none_content = Mock(spec=GameMap)
        map_none_content.x = 1
        map_none_content.y = 1
        map_none_content.content = None
        
        map_no_type = Mock(spec=GameMap)
        map_no_type.x = 2
        map_no_type.y = 2
        map_no_type.content = Mock()
        # content has no type attribute
        
        map_no_code = Mock(spec=GameMap)
        map_no_code.x = 3
        map_no_code.y = 3
        map_no_code.content = Mock()
        map_no_code.content.type = "monster"
        # content has no code attribute
        
        map_valid = create_mock_map(x=4, y=4, content_type="monster", content_code="target_monster")
        
        maps = [map_no_content, map_none_content, map_no_type, map_no_code, map_valid]
        
        result = targeting.find_optimal_monsters(
            character_level=5,
            current_position=(0, 0),
            monsters=monsters,
            maps=maps
        )
        
        # Should only find the valid map
        assert len(result) == 1
        _, location, _ = result[0]
        assert location.x == 4
        assert location.y == 4

    def test_find_optimal_monsters_efficiency_sorting(self):
        """Test find_optimal_monsters sorts results by efficiency score."""
        targeting = LevelAppropriateTargeting()
        
        # Create monsters with different attributes that affect efficiency
        monsters = [
            create_mock_monster(code="close_weak", level=5, hp=50, min_gold=1, max_gold=3),
            create_mock_monster(code="far_strong", level=5, hp=200, min_gold=20, max_gold=30)
        ]
        
        # Close weak monster at (1,1), far strong monster at (10,10)
        maps = [
            create_mock_map(x=1, y=1, content_code="close_weak"),
            create_mock_map(x=10, y=10, content_code="far_strong")
        ]
        
        result = targeting.find_optimal_monsters(
            character_level=5,
            current_position=(0, 0),
            monsters=monsters,
            maps=maps
        )
        
        # Results should be sorted by efficiency (higher first)
        assert len(result) == 2
        first_monster, _, first_efficiency = result[0]
        second_monster, _, second_efficiency = result[1]
        
        # First should have higher efficiency than second
        assert first_efficiency >= second_efficiency

    def test_calculate_monster_efficiency_basic(self):
        """Test _calculate_monster_efficiency with basic values."""
        targeting = LevelAppropriateTargeting()
        
        monster = create_mock_monster(
            level=5,
            hp=100,
            attack_fire=10,
            attack_earth=10,
            attack_water=10,
            attack_air=10,
            min_gold=5,
            max_gold=15
        )
        
        location = create_mock_map(x=5, y=5)
        current_position = (0, 0)
        
        efficiency = targeting._calculate_monster_efficiency(monster, location, current_position)
        
        # Should return a positive efficiency score
        assert efficiency > 0

    def test_calculate_monster_efficiency_zero_distance(self):
        """Test _calculate_monster_efficiency when at same location as monster."""
        targeting = LevelAppropriateTargeting()
        
        monster = create_mock_monster(level=5)
        location = create_mock_map(x=0, y=0)
        current_position = (0, 0)
        
        efficiency = targeting._calculate_monster_efficiency(monster, location, current_position)
        
        # Should handle zero distance correctly (max distance factor)
        assert efficiency > 0

    def test_find_safest_appropriate_monster_no_monsters(self):
        """Test find_safest_appropriate_monster returns None when no appropriate monsters available."""
        targeting = LevelAppropriateTargeting()
        
        # Test with no appropriate level monsters
        monsters = [create_mock_monster(level=10)]  # Too high level
        maps = [create_mock_map()]
        
        result = targeting.find_safest_appropriate_monster(
            character_level=5,
            character_hp=50,
            character_max_hp=100,
            current_position=(0, 0),
            monsters=monsters,
            maps=maps
        )
        
        assert result is None

    def test_find_safest_appropriate_monster_low_hp(self):
        """Test find_safest_appropriate_monster prioritizes weakest monster for low HP."""
        targeting = LevelAppropriateTargeting()
        
        # Create monsters with different combat power
        weak_monster = create_mock_monster(
            code="weak", level=5, hp=50,
            attack_fire=5, attack_earth=5, attack_water=5, attack_air=5
        )
        strong_monster = create_mock_monster(
            code="strong", level=5, hp=150,
            attack_fire=15, attack_earth=15, attack_water=15, attack_air=15
        )
        
        monsters = [strong_monster, weak_monster]  # Strong first to test sorting
        maps = [
            create_mock_map(x=1, y=1, content_code="strong"),
            create_mock_map(x=2, y=2, content_code="weak")
        ]
        
        result = targeting.find_safest_appropriate_monster(
            character_level=5,
            character_hp=20,  # 20% HP (< 0.3 threshold)
            character_max_hp=100,
            current_position=(0, 0),
            monsters=monsters,
            maps=maps
        )
        
        assert result is not None
        monster, location = result
        assert monster.code == "weak"  # Should select the weaker monster

    def test_find_safest_appropriate_monster_healthy_hp(self):
        """Test find_safest_appropriate_monster returns most efficient for healthy HP."""
        targeting = LevelAppropriateTargeting()
        
        monsters = [create_mock_monster(code="monster", level=5)]
        maps = [create_mock_map(x=1, y=1, content_code="monster")]
        
        result = targeting.find_safest_appropriate_monster(
            character_level=5,
            character_hp=80,  # 80% HP (healthy)
            character_max_hp=100,
            current_position=(0, 0),
            monsters=monsters,
            maps=maps
        )
        
        assert result is not None
        monster, location = result
        assert monster.code == "monster"

    def test_validate_monster_accessibility_valid_monsters(self):
        """Test validate_monster_accessibility with valid monster data."""
        targeting = LevelAppropriateTargeting()
        
        monster = create_mock_monster(code="valid", level=5, hp=100)
        location = create_mock_map(x=1, y=1, content_code="valid")
        monster_locations = [(monster, location, 10.0)]
        
        result = targeting.validate_monster_accessibility(monster_locations, character_level=5)
        
        assert len(result) == 1
        assert result[0] == (monster, location, 10.0)

    def test_validate_monster_accessibility_empty_list(self):
        """Test validate_monster_accessibility with empty input list."""
        targeting = LevelAppropriateTargeting()
        
        result = targeting.validate_monster_accessibility([], character_level=5)
        
        assert result == []

    def test_validate_monster_accessibility_normal_usage(self):
        """Test validate_monster_accessibility with normal well-formed data."""
        targeting = LevelAppropriateTargeting()
        
        monster1 = create_mock_monster(code="monster1", level=5, hp=100)
        monster2 = create_mock_monster(code="monster2", level=4, hp=80)  
        location1 = create_mock_map(x=1, y=1, content_code="monster1")
        location2 = create_mock_map(x=2, y=2, content_code="monster2")
        
        monster_locations = [
            (monster1, location1, 10.0),
            (monster2, location2, 15.0)
        ]
        
        result = targeting.validate_monster_accessibility(monster_locations, character_level=5)
        
        # Should include both monsters as they're within level range and valid
        assert len(result) == 2

    def test_validate_monster_accessibility_level_out_of_range(self):
        """Test validate_monster_accessibility filters out monsters outside level range."""
        targeting = LevelAppropriateTargeting()
        
        monster_too_low = create_mock_monster(code="low", level=3, hp=100)
        monster_valid = create_mock_monster(code="valid", level=5, hp=100)
        monster_too_high = create_mock_monster(code="high", level=7, hp=100)
        
        location = create_mock_map(x=1, y=1)
        
        monster_locations = [
            (monster_too_low, location, 10.0),
            (monster_valid, location, 15.0),
            (monster_too_high, location, 12.0)
        ]
        
        result = targeting.validate_monster_accessibility(monster_locations, character_level=5)
        
        # Should only include the valid level monster
        assert len(result) == 1
        assert result[0][0] == monster_valid

    def test_validate_monster_accessibility_zero_hp_monster(self):
        """Test validate_monster_accessibility filters out monsters with zero HP."""
        targeting = LevelAppropriateTargeting()
        
        zero_hp_monster = create_mock_monster(code="dead", level=5, hp=0)
        valid_monster = create_mock_monster(code="alive", level=5, hp=100)
        location = create_mock_map(x=1, y=1)
        
        monster_locations = [
            (zero_hp_monster, location, 10.0),
            (valid_monster, location, 15.0)
        ]
        
        result = targeting.validate_monster_accessibility(monster_locations, character_level=5)
        
        # Should only include the monster with positive HP
        assert len(result) == 1
        assert result[0][0] == valid_monster

    @pytest.mark.parametrize("character_level,monster_levels,expected_count", [
        (1, [1, 2], 2),           # Level 1: accepts 0-2, has 1,2
        (5, [3, 4, 5, 6, 7], 3),  # Level 5: accepts 4-6, has 4,5,6
        (10, [8, 9, 10, 11, 12], 3), # Level 10: accepts 9-11, has 9,10,11
    ])
    def test_level_filtering_edge_cases(self, character_level, monster_levels, expected_count):
        """Test level filtering with various character levels."""
        targeting = LevelAppropriateTargeting()
        
        monsters = [create_mock_monster(code=f"monster_{level}", level=level) for level in monster_levels]
        maps = [create_mock_map(x=i, y=i, content_code=f"monster_{level}") for i, level in enumerate(monster_levels)]
        
        result = targeting.find_optimal_monsters(
            character_level=character_level,
            current_position=(0, 0),
            monsters=monsters,
            maps=maps
        )
        
        assert len(result) == expected_count