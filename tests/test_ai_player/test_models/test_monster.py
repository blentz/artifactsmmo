"""
Tests for Monster Data Models

Tests for Pydantic models representing monster data from the ArtifactsMMO API,
including DropRate, MonsterEffect, and Monster models with comprehensive
validation and functionality testing.
"""

import pytest
from typing import Any, List
from unittest.mock import Mock

from src.ai_player.models.monster import Monster, DropRate, MonsterEffect


class TestDropRate:
    """Test DropRate model functionality"""

    def test_drop_rate_creation(self):
        """Test basic DropRate creation"""
        drop = DropRate(
            code="iron_sword",
            rate=5000,
            min_quantity=1,
            max_quantity=1
        )
        
        assert drop.code == "iron_sword"
        assert drop.rate == 5000
        assert drop.min_quantity == 1
        assert drop.max_quantity == 1

    def test_drop_rate_validation_rate_range(self):
        """Test DropRate validates rate within valid range"""
        # Valid rate
        drop = DropRate(code="item", rate=25000, min_quantity=1, max_quantity=2)
        assert drop.rate == 25000
        
        # Rate too low
        with pytest.raises(ValueError):
            DropRate(code="item", rate=0, min_quantity=1, max_quantity=2)
        
        # Rate too high
        with pytest.raises(ValueError):
            DropRate(code="item", rate=100001, min_quantity=1, max_quantity=2)

    def test_drop_rate_validation_quantities(self):
        """Test DropRate validates quantity ranges"""
        # Valid quantities
        drop = DropRate(code="gold", rate=10000, min_quantity=5, max_quantity=10)
        assert drop.min_quantity == 5
        assert drop.max_quantity == 10
        
        # Invalid min_quantity
        with pytest.raises(ValueError):
            DropRate(code="gold", rate=10000, min_quantity=0, max_quantity=5)
        
        # Invalid max_quantity
        with pytest.raises(ValueError):
            DropRate(code="gold", rate=10000, min_quantity=1, max_quantity=0)

    def test_drop_rate_assignment_validation(self):
        """Test DropRate validates assignment"""
        drop = DropRate(code="silver_ring", rate=20000, min_quantity=2, max_quantity=4)
        
        # Valid assignments
        drop.rate = 30000
        drop.min_quantity = 3
        drop.max_quantity = 6
        
        assert drop.rate == 30000
        assert drop.min_quantity == 3
        assert drop.max_quantity == 6
        
        # Invalid assignments should raise errors
        with pytest.raises(ValueError):
            drop.rate = -1
        
        with pytest.raises(ValueError):
            drop.min_quantity = 0


class TestMonsterEffect:
    """Test MonsterEffect model functionality"""

    def test_monster_effect_creation(self):
        """Test basic MonsterEffect creation"""
        effect = MonsterEffect(name="poison", value=10)
        
        assert effect.name == "poison"
        assert effect.value == 10

    def test_monster_effect_negative_value(self):
        """Test MonsterEffect can have negative values"""
        effect = MonsterEffect(name="debuff", value=-5)
        
        assert effect.name == "debuff"
        assert effect.value == -5

    def test_monster_effect_assignment_validation(self):
        """Test MonsterEffect validates assignment"""
        effect = MonsterEffect(name="burn", value=15)
        
        # Valid assignments
        effect.name = "freeze"
        effect.value = 20
        
        assert effect.name == "freeze"
        assert effect.value == 20


class TestMonsterBasicCreation:
    """Test basic Monster model creation and validation"""

    def test_monster_minimal_creation(self):
        """Test Monster creation with minimal fields"""
        drops = [DropRate(code="leather", rate=50000, min_quantity=1, max_quantity=2)]
        
        monster = Monster(
            name="Chicken",
            code="chicken",
            level=1,
            hp=50,
            attack_fire=0,
            attack_earth=5,
            attack_water=0,
            attack_air=0,
            res_fire=0,
            res_earth=0,
            res_water=0,
            res_air=0,
            critical_strike=0,
            min_gold=1,
            max_gold=5,
            drops=drops
        )
        
        assert monster.name == "Chicken"
        assert monster.code == "chicken"
        assert monster.level == 1
        assert monster.hp == 50
        assert monster.effects is None

    def test_monster_with_effects(self):
        """Test Monster creation with effects"""
        drops = [DropRate(code="bones", rate=100000, min_quantity=1, max_quantity=1)]
        effects = [MonsterEffect(name="poison", value=5)]
        
        monster = Monster(
            name="Poison Spider",
            code="poison_spider",
            level=10,
            hp=150,
            attack_fire=0,
            attack_earth=20,
            attack_water=0,
            attack_air=0,
            res_fire=5,
            res_earth=10,
            res_water=0,
            res_air=0,
            critical_strike=5,
            min_gold=10,
            max_gold=25,
            drops=drops,
            effects=effects
        )
        
        assert monster.name == "Poison Spider"
        assert monster.effects is not None
        assert len(monster.effects) == 1
        assert monster.effects[0].name == "poison"

    def test_monster_validation_level_range(self):
        """Test Monster validates level within valid range"""
        drops = [DropRate(code="item", rate=50000, min_quantity=1, max_quantity=1)]
        
        # Valid level
        monster = Monster(
            name="Test", code="test", level=25, hp=100,
            attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
            res_fire=0, res_earth=0, res_water=0, res_air=0,
            critical_strike=0, min_gold=0, max_gold=0, drops=drops
        )
        assert monster.level == 25
        
        # Level too low
        with pytest.raises(ValueError):
            Monster(
                name="Test", code="test", level=0, hp=100,
                attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
                res_fire=0, res_earth=0, res_water=0, res_air=0,
                critical_strike=0, min_gold=0, max_gold=0, drops=drops
            )
        
        # Level too high
        with pytest.raises(ValueError):
            Monster(
                name="Test", code="test", level=46, hp=100,
                attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
                res_fire=0, res_earth=0, res_water=0, res_air=0,
                critical_strike=0, min_gold=0, max_gold=0, drops=drops
            )

    def test_monster_validation_hp_positive(self):
        """Test Monster validates HP is positive"""
        drops = [DropRate(code="item", rate=50000, min_quantity=1, max_quantity=1)]
        
        # Valid HP
        monster = Monster(
            name="Test", code="test", level=5, hp=100,
            attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
            res_fire=0, res_earth=0, res_water=0, res_air=0,
            critical_strike=0, min_gold=0, max_gold=0, drops=drops
        )
        assert monster.hp == 100
        
        # Invalid HP
        with pytest.raises(ValueError):
            Monster(
                name="Test", code="test", level=5, hp=0,
                attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
                res_fire=0, res_earth=0, res_water=0, res_air=0,
                critical_strike=0, min_gold=0, max_gold=0, drops=drops
            )

    def test_monster_validation_stats_non_negative(self):
        """Test Monster validates all stats are non-negative"""
        drops = [DropRate(code="item", rate=50000, min_quantity=1, max_quantity=1)]
        
        # Valid stats
        monster = Monster(
            name="Test", code="test", level=5, hp=100,
            attack_fire=10, attack_earth=15, attack_water=5, attack_air=20,
            res_fire=8, res_earth=12, res_water=3, res_air=7,
            critical_strike=5, min_gold=5, max_gold=15, drops=drops
        )
        assert monster.attack_fire == 10
        assert monster.res_fire == 8
        
        # Invalid attack stat
        with pytest.raises(ValueError):
            Monster(
                name="Test", code="test", level=5, hp=100,
                attack_fire=-1, attack_earth=0, attack_water=0, attack_air=0,
                res_fire=0, res_earth=0, res_water=0, res_air=0,
                critical_strike=0, min_gold=0, max_gold=0, drops=drops
            )


class TestMonsterFromApiMonster:
    """Test Monster.from_api_monster factory method"""

    def test_from_api_monster_minimal(self):
        """Test creating Monster from API monster with minimal data"""
        # Mock drop object
        api_drop = Mock(spec=['code', 'rate', 'min_quantity', 'max_quantity'])
        api_drop.code = "feather"
        api_drop.rate = 75000
        api_drop.min_quantity = 1
        api_drop.max_quantity = 3
        
        # Mock monster object
        api_monster = Mock(spec=[
            'name', 'code', 'level', 'hp',
            'attack_fire', 'attack_earth', 'attack_water', 'attack_air',
            'res_fire', 'res_earth', 'res_water', 'res_air',
            'critical_strike', 'min_gold', 'max_gold', 'drops'
        ])
        api_monster.name = "Flying Chicken"
        api_monster.code = "flying_chicken"
        api_monster.level = 3
        api_monster.hp = 75
        api_monster.attack_fire = 0
        api_monster.attack_earth = 8
        api_monster.attack_water = 0
        api_monster.attack_air = 12
        api_monster.res_fire = 2
        api_monster.res_earth = 5
        api_monster.res_water = 1
        api_monster.res_air = 8
        api_monster.critical_strike = 3
        api_monster.min_gold = 2
        api_monster.max_gold = 8
        api_monster.drops = [api_drop]
        
        monster = Monster.from_api_monster(api_monster)
        
        assert monster.name == "Flying Chicken"
        assert monster.code == "flying_chicken"
        assert monster.level == 3
        assert monster.hp == 75
        assert monster.attack_fire == 0
        assert monster.attack_air == 12
        assert monster.res_fire == 2
        assert monster.critical_strike == 3
        assert monster.min_gold == 2
        assert monster.max_gold == 8
        assert len(monster.drops) == 1
        assert monster.drops[0].code == "feather"
        assert monster.effects is None

    def test_from_api_monster_with_effects(self):
        """Test creating Monster from API monster with effects"""
        # Mock drop object
        api_drop = Mock(spec=['code', 'rate', 'min_quantity', 'max_quantity'])
        api_drop.code = "venom_sac"
        api_drop.rate = 25000
        api_drop.min_quantity = 1
        api_drop.max_quantity = 1
        
        # Mock effect objects
        api_effect1 = Mock(spec=['name', 'value'])
        api_effect1.name = "poison"
        api_effect1.value = 10
        
        api_effect2 = Mock(spec=['name', 'value'])
        api_effect2.name = "slow"
        api_effect2.value = 5
        
        # Mock monster object
        api_monster = Mock(spec=[
            'name', 'code', 'level', 'hp',
            'attack_fire', 'attack_earth', 'attack_water', 'attack_air',
            'res_fire', 'res_earth', 'res_water', 'res_air',
            'critical_strike', 'min_gold', 'max_gold', 'drops', 'effects'
        ])
        api_monster.name = "Venomous Snake"
        api_monster.code = "venomous_snake"
        api_monster.level = 15
        api_monster.hp = 200
        api_monster.attack_fire = 5
        api_monster.attack_earth = 25
        api_monster.attack_water = 0
        api_monster.attack_air = 0
        api_monster.res_fire = 10
        api_monster.res_earth = 15
        api_monster.res_water = 5
        api_monster.res_air = 0
        api_monster.critical_strike = 8
        api_monster.min_gold = 15
        api_monster.max_gold = 35
        api_monster.drops = [api_drop]
        api_monster.effects = [api_effect1, api_effect2]
        
        monster = Monster.from_api_monster(api_monster)
        
        assert monster.name == "Venomous Snake"
        assert monster.effects is not None
        assert len(monster.effects) == 2
        assert monster.effects[0].name == "poison"
        assert monster.effects[0].value == 10
        assert monster.effects[1].name == "slow"
        assert monster.effects[1].value == 5

    def test_from_api_monster_no_effects_attribute(self):
        """Test creating Monster from API monster without effects attribute"""
        # Mock drop object
        api_drop = Mock(spec=['code', 'rate', 'min_quantity', 'max_quantity'])
        api_drop.code = "bone"
        api_drop.rate = 90000
        api_drop.min_quantity = 1
        api_drop.max_quantity = 2
        
        # Mock monster object without effects
        api_monster = Mock(spec=[
            'name', 'code', 'level', 'hp',
            'attack_fire', 'attack_earth', 'attack_water', 'attack_air',
            'res_fire', 'res_earth', 'res_water', 'res_air',
            'critical_strike', 'min_gold', 'max_gold', 'drops'
        ])
        api_monster.name = "Skeleton"
        api_monster.code = "skeleton"
        api_monster.level = 8
        api_monster.hp = 120
        api_monster.attack_fire = 0
        api_monster.attack_earth = 15
        api_monster.attack_water = 0
        api_monster.attack_air = 0
        api_monster.res_fire = 0
        api_monster.res_earth = 10
        api_monster.res_water = 0
        api_monster.res_air = 0
        api_monster.critical_strike = 2
        api_monster.min_gold = 8
        api_monster.max_gold = 18
        api_monster.drops = [api_drop]
        
        monster = Monster.from_api_monster(api_monster)
        
        assert monster.name == "Skeleton"
        assert monster.effects is None

    def test_from_api_monster_empty_effects(self):
        """Test creating Monster from API monster with empty effects"""
        # Mock drop object
        api_drop = Mock(spec=['code', 'rate', 'min_quantity', 'max_quantity'])
        api_drop.code = "claw"
        api_drop.rate = 60000
        api_drop.min_quantity = 2
        api_drop.max_quantity = 4
        
        # Mock monster object with empty effects
        api_monster = Mock(spec=[
            'name', 'code', 'level', 'hp',
            'attack_fire', 'attack_earth', 'attack_water', 'attack_air',
            'res_fire', 'res_earth', 'res_water', 'res_air',
            'critical_strike', 'min_gold', 'max_gold', 'drops', 'effects'
        ])
        api_monster.name = "Bear"
        api_monster.code = "bear"
        api_monster.level = 12
        api_monster.hp = 180
        api_monster.attack_fire = 0
        api_monster.attack_earth = 30
        api_monster.attack_water = 0
        api_monster.attack_air = 0
        api_monster.res_fire = 5
        api_monster.res_earth = 20
        api_monster.res_water = 5
        api_monster.res_air = 0
        api_monster.critical_strike = 10
        api_monster.min_gold = 12
        api_monster.max_gold = 28
        api_monster.drops = [api_drop]
        api_monster.effects = []
        
        monster = Monster.from_api_monster(api_monster)
        
        assert monster.name == "Bear"
        assert monster.effects is None

    def test_from_api_monster_multiple_drops(self):
        """Test creating Monster from API monster with multiple drops"""
        # Mock drop objects
        api_drop1 = Mock(spec=['code', 'rate', 'min_quantity', 'max_quantity'])
        api_drop1.code = "scale"
        api_drop1.rate = 70000
        api_drop1.min_quantity = 1
        api_drop1.max_quantity = 3
        
        api_drop2 = Mock(spec=['code', 'rate', 'min_quantity', 'max_quantity'])
        api_drop2.code = "fire_crystal"
        api_drop2.rate = 5000
        api_drop2.min_quantity = 1
        api_drop2.max_quantity = 1
        
        # Mock monster object
        api_monster = Mock(spec=[
            'name', 'code', 'level', 'hp',
            'attack_fire', 'attack_earth', 'attack_water', 'attack_air',
            'res_fire', 'res_earth', 'res_water', 'res_air',
            'critical_strike', 'min_gold', 'max_gold', 'drops'
        ])
        api_monster.name = "Fire Dragon"
        api_monster.code = "fire_dragon"
        api_monster.level = 35
        api_monster.hp = 500
        api_monster.attack_fire = 80
        api_monster.attack_earth = 10
        api_monster.attack_water = 0
        api_monster.attack_air = 20
        api_monster.res_fire = 50
        api_monster.res_earth = 20
        api_monster.res_water = 0
        api_monster.res_air = 15
        api_monster.critical_strike = 25
        api_monster.min_gold = 50
        api_monster.max_gold = 100
        api_monster.drops = [api_drop1, api_drop2]
        
        monster = Monster.from_api_monster(api_monster)
        
        assert monster.name == "Fire Dragon"
        assert len(monster.drops) == 2
        assert monster.drops[0].code == "scale"
        assert monster.drops[1].code == "fire_crystal"


class TestMonsterProperties:
    """Test Monster property methods"""

    def setup_method(self):
        """Set up test monster for property testing"""
        self.drops = [DropRate(code="item", rate=50000, min_quantity=1, max_quantity=1)]

    def test_total_attack(self):
        """Test total_attack calculation"""
        monster = Monster(
            name="Test", code="test", level=10, hp=100,
            attack_fire=15, attack_earth=20, attack_water=10, attack_air=25,
            res_fire=0, res_earth=0, res_water=0, res_air=0,
            critical_strike=0, min_gold=0, max_gold=0, drops=self.drops
        )
        
        assert monster.total_attack == 70  # 15 + 20 + 10 + 25

    def test_total_attack_zero(self):
        """Test total_attack when all attacks are zero"""
        monster = Monster(
            name="Test", code="test", level=10, hp=100,
            attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
            res_fire=0, res_earth=0, res_water=0, res_air=0,
            critical_strike=0, min_gold=0, max_gold=0, drops=self.drops
        )
        
        assert monster.total_attack == 0

    def test_total_resistance(self):
        """Test total_resistance calculation"""
        monster = Monster(
            name="Test", code="test", level=10, hp=100,
            attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
            res_fire=12, res_earth=8, res_water=15, res_air=5,
            critical_strike=0, min_gold=0, max_gold=0, drops=self.drops
        )
        
        assert monster.total_resistance == 40  # 12 + 8 + 15 + 5

    def test_total_resistance_zero(self):
        """Test total_resistance when all resistances are zero"""
        monster = Monster(
            name="Test", code="test", level=10, hp=100,
            attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
            res_fire=0, res_earth=0, res_water=0, res_air=0,
            critical_strike=0, min_gold=0, max_gold=0, drops=self.drops
        )
        
        assert monster.total_resistance == 0

    def test_average_gold_drop_equal_min_max(self):
        """Test average_gold_drop when min and max are equal"""
        monster = Monster(
            name="Test", code="test", level=10, hp=100,
            attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
            res_fire=0, res_earth=0, res_water=0, res_air=0,
            critical_strike=0, min_gold=10, max_gold=10, drops=self.drops
        )
        
        assert monster.average_gold_drop == 10.0

    def test_average_gold_drop_different_min_max(self):
        """Test average_gold_drop calculation"""
        monster = Monster(
            name="Test", code="test", level=10, hp=100,
            attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
            res_fire=0, res_earth=0, res_water=0, res_air=0,
            critical_strike=0, min_gold=5, max_gold=15, drops=self.drops
        )
        
        assert monster.average_gold_drop == 10.0

    def test_average_gold_drop_zero(self):
        """Test average_gold_drop when no gold is dropped"""
        monster = Monster(
            name="Test", code="test", level=10, hp=100,
            attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
            res_fire=0, res_earth=0, res_water=0, res_air=0,
            critical_strike=0, min_gold=0, max_gold=0, drops=self.drops
        )
        
        assert monster.average_gold_drop == 0.0

    def test_has_drops_true(self):
        """Test has_drops returns True when drops exist"""
        monster = Monster(
            name="Test", code="test", level=10, hp=100,
            attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
            res_fire=0, res_earth=0, res_water=0, res_air=0,
            critical_strike=0, min_gold=0, max_gold=0, drops=self.drops
        )
        
        assert monster.has_drops is True

    def test_has_drops_false(self):
        """Test has_drops returns False when no drops"""
        monster = Monster(
            name="Test", code="test", level=10, hp=100,
            attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
            res_fire=0, res_earth=0, res_water=0, res_air=0,
            critical_strike=0, min_gold=0, max_gold=0, drops=[]
        )
        
        assert monster.has_drops is False


class TestMonsterMethods:
    """Test Monster method functionality"""

    def test_get_drop_by_code_found(self):
        """Test get_drop_by_code returns correct drop when found"""
        drops = [
            DropRate(code="leather", rate=70000, min_quantity=1, max_quantity=2),
            DropRate(code="meat", rate=50000, min_quantity=1, max_quantity=3),
            DropRate(code="bone", rate=20000, min_quantity=1, max_quantity=1)
        ]
        
        monster = Monster(
            name="Wolf", code="wolf", level=8, hp=120,
            attack_fire=0, attack_earth=25, attack_water=0, attack_air=5,
            res_fire=0, res_earth=10, res_water=0, res_air=5,
            critical_strike=8, min_gold=8, max_gold=20, drops=drops
        )
        
        drop = monster.get_drop_by_code("meat")
        assert drop is not None
        assert drop.code == "meat"
        assert drop.rate == 50000

    def test_get_drop_by_code_not_found(self):
        """Test get_drop_by_code returns None when not found"""
        drops = [DropRate(code="feather", rate=80000, min_quantity=1, max_quantity=2)]
        
        monster = Monster(
            name="Bird", code="bird", level=2, hp=40,
            attack_fire=0, attack_earth=0, attack_water=0, attack_air=12,
            res_fire=0, res_earth=0, res_water=0, res_air=8,
            critical_strike=2, min_gold=1, max_gold=6, drops=drops
        )
        
        drop = monster.get_drop_by_code("nonexistent_item")
        assert drop is None

    def test_get_drop_by_code_empty_drops(self):
        """Test get_drop_by_code returns None when no drops exist"""
        monster = Monster(
            name="Ghost", code="ghost", level=15, hp=80,
            attack_fire=0, attack_earth=0, attack_water=0, attack_air=30,
            res_fire=20, res_earth=0, res_water=0, res_air=15,
            critical_strike=0, min_gold=0, max_gold=0, drops=[]
        )
        
        drop = monster.get_drop_by_code("any_item")
        assert drop is None

    def test_can_defeat_with_level_sufficient_default_tolerance(self):
        """Test can_defeat_with_level with sufficient level and default tolerance"""
        drops = [DropRate(code="item", rate=50000, min_quantity=1, max_quantity=1)]
        monster = Monster(
            name="Test", code="test", level=10, hp=100,
            attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
            res_fire=0, res_earth=0, res_water=0, res_air=0,
            critical_strike=0, min_gold=0, max_gold=0, drops=drops
        )
        
        assert monster.can_defeat_with_level(10) is True  # Equal level
        assert monster.can_defeat_with_level(12) is True  # Higher level
        assert monster.can_defeat_with_level(8) is True   # Within tolerance (10 - 2)

    def test_can_defeat_with_level_insufficient_default_tolerance(self):
        """Test can_defeat_with_level with insufficient level and default tolerance"""
        drops = [DropRate(code="item", rate=50000, min_quantity=1, max_quantity=1)]
        monster = Monster(
            name="Test", code="test", level=10, hp=100,
            attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
            res_fire=0, res_earth=0, res_water=0, res_air=0,
            critical_strike=0, min_gold=0, max_gold=0, drops=drops
        )
        
        assert monster.can_defeat_with_level(7) is False  # Below tolerance (10 - 2 = 8)
        assert monster.can_defeat_with_level(5) is False  # Much lower level

    def test_can_defeat_with_level_custom_tolerance(self):
        """Test can_defeat_with_level with custom tolerance"""
        drops = [DropRate(code="item", rate=50000, min_quantity=1, max_quantity=1)]
        monster = Monster(
            name="Test", code="test", level=15, hp=200,
            attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
            res_fire=0, res_earth=0, res_water=0, res_air=0,
            critical_strike=0, min_gold=0, max_gold=0, drops=drops
        )
        
        # With tolerance of 5
        assert monster.can_defeat_with_level(15, level_tolerance=5) is True  # Equal
        assert monster.can_defeat_with_level(10, level_tolerance=5) is True  # At tolerance boundary
        assert monster.can_defeat_with_level(9, level_tolerance=5) is False  # Below tolerance

    def test_can_defeat_with_level_zero_tolerance(self):
        """Test can_defeat_with_level with zero tolerance"""
        drops = [DropRate(code="item", rate=50000, min_quantity=1, max_quantity=1)]
        monster = Monster(
            name="Test", code="test", level=20, hp=300,
            attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
            res_fire=0, res_earth=0, res_water=0, res_air=0,
            critical_strike=0, min_gold=0, max_gold=0, drops=drops
        )
        
        # With tolerance of 0
        assert monster.can_defeat_with_level(20, level_tolerance=0) is True   # Equal level
        assert monster.can_defeat_with_level(25, level_tolerance=0) is True   # Higher level
        assert monster.can_defeat_with_level(19, level_tolerance=0) is False  # Below by 1

    def test_can_defeat_with_level_negative_tolerance(self):
        """Test can_defeat_with_level with negative tolerance (stricter requirement)"""
        drops = [DropRate(code="item", rate=50000, min_quantity=1, max_quantity=1)]
        monster = Monster(
            name="Test", code="test", level=10, hp=100,
            attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
            res_fire=0, res_earth=0, res_water=0, res_air=0,
            critical_strike=0, min_gold=0, max_gold=0, drops=drops
        )
        
        # With tolerance of -3 (character must be 3+ levels higher)
        assert monster.can_defeat_with_level(13, level_tolerance=-3) is True   # 13 >= (10 - (-3)) = 13
        assert monster.can_defeat_with_level(15, level_tolerance=-3) is True   # Higher than required
        assert monster.can_defeat_with_level(12, level_tolerance=-3) is False  # 12 < 13


class TestMonsterEdgeCases:
    """Test edge cases and error conditions"""

    def test_monster_string_representation(self):
        """Test Monster can be represented as string"""
        drops = [DropRate(code="item", rate=50000, min_quantity=1, max_quantity=1)]
        monster = Monster(
            name="Test Monster", code="test_monster", level=5, hp=75,
            attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
            res_fire=0, res_earth=0, res_water=0, res_air=0,
            critical_strike=0, min_gold=0, max_gold=0, drops=drops
        )
        
        # Should not raise an exception
        str_repr = str(monster)
        assert "Test Monster" in str_repr
        assert "test_monster" in str_repr

    def test_drop_rate_string_representation(self):
        """Test DropRate can be represented as string"""
        drop = DropRate(code="dragon_scale", rate=1000, min_quantity=1, max_quantity=2)
        
        # Should not raise an exception
        str_repr = str(drop)
        assert "dragon_scale" in str_repr
        assert "1000" in str_repr

    def test_monster_effect_string_representation(self):
        """Test MonsterEffect can be represented as string"""
        effect = MonsterEffect(name="burning", value=15)
        
        # Should not raise an exception
        str_repr = str(effect)
        assert "burning" in str_repr
        assert "15" in str_repr

    def test_monster_equality_comparison(self):
        """Test Monster equality comparison"""
        drops = [DropRate(code="item", rate=50000, min_quantity=1, max_quantity=1)]
        
        monster1 = Monster(
            name="Same", code="same", level=5, hp=100,
            attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
            res_fire=0, res_earth=0, res_water=0, res_air=0,
            critical_strike=0, min_gold=0, max_gold=0, drops=drops
        )
        monster2 = Monster(
            name="Same", code="same", level=5, hp=100,
            attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
            res_fire=0, res_earth=0, res_water=0, res_air=0,
            critical_strike=0, min_gold=0, max_gold=0, drops=drops
        )
        monster3 = Monster(
            name="Different", code="different", level=5, hp=100,
            attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
            res_fire=0, res_earth=0, res_water=0, res_air=0,
            critical_strike=0, min_gold=0, max_gold=0, drops=drops
        )
        
        # Pydantic models should support equality comparison
        assert monster1 == monster2
        assert monster1 != monster3

    def test_monster_level_boundaries(self):
        """Test Monster level at boundaries"""
        drops = [DropRate(code="item", rate=50000, min_quantity=1, max_quantity=1)]
        
        # Minimum level
        monster_min = Monster(
            name="Min", code="min", level=1, hp=50,
            attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
            res_fire=0, res_earth=0, res_water=0, res_air=0,
            critical_strike=0, min_gold=0, max_gold=0, drops=drops
        )
        assert monster_min.level == 1
        
        # Maximum level
        monster_max = Monster(
            name="Max", code="max", level=45, hp=1000,
            attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
            res_fire=0, res_earth=0, res_water=0, res_air=0,
            critical_strike=0, min_gold=0, max_gold=0, drops=drops
        )
        assert monster_max.level == 45

    def test_average_gold_drop_floating_point(self):
        """Test average_gold_drop with odd numbers (floating point result)"""
        drops = [DropRate(code="item", rate=50000, min_quantity=1, max_quantity=1)]
        monster = Monster(
            name="Test", code="test", level=10, hp=100,
            attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
            res_fire=0, res_earth=0, res_water=0, res_air=0,
            critical_strike=0, min_gold=7, max_gold=12, drops=drops
        )
        
        assert monster.average_gold_drop == 9.5