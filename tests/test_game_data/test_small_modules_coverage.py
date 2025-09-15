"""
Targeted tests for small game data modules to improve coverage.

This module focuses on achieving 100% coverage for smaller modules
with few uncovered lines, providing high-impact coverage improvements.
"""

import pytest
from unittest.mock import Mock

from src.game_data.game_item import GameItem
from src.game_data.game_map import GameMap
from src.game_data.game_monster import GameMonster
from src.game_data.game_npc import GameNPC
from src.game_data.game_resource import GameResource
from src.game_data.map_content import MapContent


class TestGameItemCoverage:
    """Test GameItem model edge cases"""

    def test_game_item_validation_error(self):
        """Test GameItem with invalid data to cover validation paths"""
        # Test missing required fields
        with pytest.raises(Exception):  # Pydantic validation error
            GameItem()
        
        # Test with minimal valid data
        item = GameItem(
            name="test_item",
            code="test_code",
            level=1,
            type="misc",
            subtype="material",
            description="Test item"
        )
        assert item.name == "test_item"

    def test_game_item_optional_fields(self):
        """Test GameItem with optional fields to cover additional paths"""
        item = GameItem(
            name="test_item",
            code="test_code", 
            level=1,
            type="misc",
            subtype="material",
            description="Test item",
            craft={"skill": "crafting", "level": 1, "items": []},
            effects=[]
        )
        assert item.craft is not None
        assert item.effects == []


class TestGameMapCoverage:
    """Test GameMap model edge cases"""

    def test_game_map_invalid_coordinates(self):
        """Test GameMap validation with invalid coordinates"""
        # Test with invalid coordinate types
        with pytest.raises(Exception):  # Pydantic validation error
            GameMap(x="invalid", y=0)
        
        with pytest.raises(Exception):  # Pydantic validation error
            GameMap(x=0, y="invalid")

    def test_game_map_content_validation(self):
        """Test GameMap with various content types"""
        # Test with no content
        game_map = GameMap(name="test_map", skin="grass", x=0, y=0, content=None)
        assert game_map.content is None
        
        # Test with valid content
        content = MapContent(type="resource", code="ash_tree")
        game_map = GameMap(name="test_map_2", skin="forest", x=1, y=1, content=content)
        assert game_map.content.type == "resource"

    def test_game_map_boundary_coordinates(self):
        """Test GameMap with boundary coordinate values"""
        # Test with extreme coordinates
        game_map = GameMap(name="edge_map", skin="desert", x=-999, y=999, content=None)
        assert game_map.x == -999
        assert game_map.y == 999
        
        # Test with zero coordinates
        game_map = GameMap(name="origin_map", skin="spawn", x=0, y=0, content=None)
        assert game_map.x == 0
        assert game_map.y == 0

    def test_from_api_map_with_content_having_to_dict(self):
        """Test GameMap.from_api_map with content that has to_dict method - covers lines 26-31"""
        # Create mock API map with content that has to_dict method
        api_map = Mock()
        api_map.name = "test_api_map"
        api_map.skin = "grassland"
        api_map.x = 10
        api_map.y = 20
        api_map.content = Mock()
        api_map.content.to_dict = Mock(return_value={"type": "monster", "code": "goblin"})
        
        # Test the from_api_map method
        game_map = GameMap.from_api_map(api_map)
        
        assert game_map.name == "test_api_map"
        assert game_map.skin == "grassland"
        assert game_map.x == 10
        assert game_map.y == 20
        assert game_map.content is not None
        assert game_map.content.type == "monster"
        assert game_map.content.code == "goblin"

    def test_from_api_map_with_content_without_to_dict(self):
        """Test GameMap.from_api_map with content that doesn't have to_dict method - covers lines 26-31"""
        # Create mock API map with content that doesn't have to_dict method
        api_map = Mock()
        api_map.name = "test_api_map_2"
        api_map.skin = "forest"
        api_map.x = 5
        api_map.y = 15
        api_map.content = {"type": "resource", "code": "iron_ore"}  # Direct dict
        
        # Test the from_api_map method
        game_map = GameMap.from_api_map(api_map)
        
        assert game_map.name == "test_api_map_2"
        assert game_map.skin == "forest"
        assert game_map.x == 5
        assert game_map.y == 15
        assert game_map.content is not None
        assert game_map.content.type == "resource"
        assert game_map.content.code == "iron_ore"

    def test_from_api_map_with_no_content(self):
        """Test GameMap.from_api_map with no content - covers lines 26-31"""
        # Create mock API map without content
        api_map = Mock()
        api_map.name = "empty_map"
        api_map.skin = "desert"
        api_map.x = 0
        api_map.y = 0
        api_map.content = None
        
        # Test the from_api_map method
        game_map = GameMap.from_api_map(api_map)
        
        assert game_map.name == "empty_map"
        assert game_map.skin == "desert"
        assert game_map.x == 0
        assert game_map.y == 0
        assert game_map.content is None


class TestGameMonsterCoverage:
    """Test GameMonster model edge cases"""

    def test_game_monster_validation_error(self):
        """Test GameMonster with invalid data"""
        with pytest.raises(Exception):  # Missing required fields
            GameMonster()

    def test_game_monster_drops_validation(self):
        """Test GameMonster drops field validation"""
        monster = GameMonster(
            name="test_monster",
            code="test_code",
            level=1,
            hp=100,
            attack_fire=10,
            attack_earth=0,
            attack_water=0,
            attack_air=0,
            res_fire=5,
            res_earth=5,
            res_water=5,
            res_air=5,
            min_gold=1,
            max_gold=10,
            drops=[]  # Empty drops list
        )
        assert monster.drops == []
        
        # Test with drops
        monster_with_drops = GameMonster(
            name="test_monster_2", 
            code="test_code_2",
            level=2,
            hp=150,
            attack_fire=15,
            attack_earth=5,
            attack_water=5,
            attack_air=5,
            res_fire=10,
            res_earth=10,
            res_water=10,
            res_air=10,
            min_gold=2,
            max_gold=20,
            drops=[{"code": "item1", "rate": 0.1, "min_quantity": 1, "max_quantity": 1}]
        )
        assert len(monster_with_drops.drops) == 1


class TestGameNPCCoverage:
    """Test GameNPC model edge cases"""

    def test_game_npc_validation_error(self):
        """Test GameNPC with invalid data"""
        with pytest.raises(Exception):  # Missing required fields
            GameNPC()

    def test_game_npc_inventory_validation(self):
        """Test GameNPC with required fields"""
        npc = GameNPC(
            name="test_npc",
            code="test_code",
            description="A test NPC",
            type="trader"
        )
        assert npc.name == "test_npc"
        assert npc.type == "trader"


class TestGameResourceCoverage:
    """Test GameResource model edge cases"""

    def test_game_resource_validation_error(self):
        """Test GameResource with invalid data"""
        with pytest.raises(Exception):  # Missing required fields
            GameResource()

    def test_game_resource_drops_validation(self):
        """Test GameResource drops field validation"""
        resource = GameResource(
            name="test_resource",
            code="test_code", 
            skill="mining",
            level=1,
            drops=[]  # Empty drops
        )
        assert resource.drops == []


class TestMapContentCoverage:
    """Test MapContent model edge cases"""

    def test_map_content_validation_error(self):
        """Test MapContent with invalid data"""
        with pytest.raises(Exception):  # Missing required fields
            MapContent()

    def test_map_content_types(self):
        """Test MapContent with different types"""
        # Test resource type
        resource_content = MapContent(type="resource", code="ash_tree")
        assert resource_content.type == "resource"
        assert resource_content.code == "ash_tree"
        
        # Test monster type
        monster_content = MapContent(type="monster", code="green_slime")
        assert monster_content.type == "monster"
        assert monster_content.code == "green_slime"


class TestGameDataValidationScenarios:
    """Test complex validation scenarios across game data models"""

    def test_coordinated_map_and_content_validation(self):
        """Test coordinated validation between GameMap and MapContent"""
        # Create map with monster content
        monster_content = MapContent(type="monster", code="chicken")
        game_map = GameMap(name="chicken_farm", skin="farm", x=5, y=3, content=monster_content)
        
        assert game_map.x == 5
        assert game_map.y == 3
        assert game_map.content.type == "monster"
        assert game_map.content.code == "chicken"

    def test_item_with_complex_craft_recipe(self):
        """Test GameItem with complex crafting recipe"""
        complex_craft = {
            "skill": "weaponcrafting",
            "level": 10,
            "items": [
                {"code": "iron_ore", "quantity": 5},
                {"code": "coal", "quantity": 2}
            ],
            "quantity": 1
        }
        
        item = GameItem(
            name="iron_sword",
            code="iron_sword",
            level=10,
            type="weapon",
            subtype="sword",
            description="A sharp iron sword",
            craft=complex_craft
        )
        
        assert item.craft["skill"] == "weaponcrafting"
        assert len(item.craft["items"]) == 2

    def test_monster_with_balanced_stats(self):
        """Test GameMonster with balanced attack and resistance stats"""
        balanced_monster = GameMonster(
            name="balanced_golem",
            code="balanced_golem",
            level=25,
            hp=500,
            attack_fire=25,
            attack_earth=25,
            attack_water=25,
            attack_air=25,
            res_fire=20,
            res_earth=20,
            res_water=20,
            res_air=20,
            min_gold=50,
            max_gold=100,
            drops=[
                {"code": "stone", "rate": 0.8, "min_quantity": 1, "max_quantity": 3},
                {"code": "rare_gem", "rate": 0.1, "min_quantity": 1, "max_quantity": 1}
            ]
        )
        
        # Verify balanced stats
        total_attack = (balanced_monster.attack_fire + balanced_monster.attack_earth + 
                       balanced_monster.attack_water + balanced_monster.attack_air)
        total_resistance = (balanced_monster.res_fire + balanced_monster.res_earth +
                           balanced_monster.res_water + balanced_monster.res_air)
        
        assert total_attack == 100
        assert total_resistance == 80
        assert len(balanced_monster.drops) == 2

    def test_npc_with_trading_inventory(self):
        """Test GameNPC with realistic trading description"""
        trading_npc = GameNPC(
            name="weapons_merchant",
            code="weapons_merchant", 
            description="A merchant who sells weapons and armor",
            type="trader"
        )
        
        assert trading_npc.name == "weapons_merchant"
        assert trading_npc.type == "trader"
        assert "weapons" in trading_npc.description

    def test_resource_with_multiple_drops(self):
        """Test GameResource with multiple possible drops"""
        resource = GameResource(
            name="ash_tree",
            code="ash_tree",
            skill="woodcutting", 
            level=1,
            drops=[
                {"code": "ash_wood", "rate": 1.0, "min_quantity": 1, "max_quantity": 3},
                {"code": "ash_plank", "rate": 0.1, "min_quantity": 1, "max_quantity": 1}
            ]
        )
        
        assert resource.skill == "woodcutting"
        assert len(resource.drops) == 2
        assert resource.drops[0]["rate"] == 1.0  # Guaranteed drop
        assert resource.drops[1]["rate"] == 0.1  # Rare drop