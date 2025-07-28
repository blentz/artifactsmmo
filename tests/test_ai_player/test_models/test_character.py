"""
Tests for Character Model

Tests the Character Pydantic model ensuring proper validation, field mapping,
API integration, and property calculations.
"""

from datetime import datetime
from unittest.mock import Mock
import pytest
from pydantic import ValidationError

from src.ai_player.models.character import Character, InventorySlot


class TestInventorySlot:
    """Test InventorySlot model"""

    def test_inventory_slot_creation(self):
        """Test creating valid inventory slot"""
        slot = InventorySlot(slot=1, code="iron_ore", quantity=5)
        
        assert slot.slot == 1
        assert slot.code == "iron_ore"
        assert slot.quantity == 5

    def test_inventory_slot_validation(self):
        """Test inventory slot validation"""
        # Valid slot
        slot = InventorySlot(slot=10, code="copper_ore", quantity=1)
        assert slot.slot == 10
        
        # Invalid slot number (must be >= 1)
        with pytest.raises(ValidationError):
            InventorySlot(slot=0, code="item", quantity=1)
            
        # Invalid quantity (must be >= 1)
        with pytest.raises(ValidationError):
            InventorySlot(slot=1, code="item", quantity=0)

    def test_inventory_slot_assignment_validation(self):
        """Test assignment validation after creation"""
        slot = InventorySlot(slot=1, code="iron_ore", quantity=5)
        
        # Valid assignment
        slot.quantity = 10
        assert slot.quantity == 10
        
        # Invalid assignment
        with pytest.raises(ValidationError):
            slot.quantity = -1


class TestCharacter:
    """Test Character model"""

    def test_character_creation_minimal(self):
        """Test creating character with minimal required fields"""
        char = Character(
            name="TestChar",
            account="test_account",
            level=1,
            xp=0,
            max_xp=100,
            gold=0,
            speed=10,
            hp=50,
            max_hp=50,
            mining_level=1,
            mining_xp=0,
            mining_max_xp=100,
            woodcutting_level=1,
            woodcutting_xp=0,
            woodcutting_max_xp=100,
            fishing_level=1,
            fishing_xp=0,
            fishing_max_xp=100,
            weaponcrafting_level=1,
            weaponcrafting_xp=0,
            weaponcrafting_max_xp=100,
            gearcrafting_level=1,
            gearcrafting_xp=0,
            gearcrafting_max_xp=100,
            jewelrycrafting_level=1,
            jewelrycrafting_xp=0,
            jewelrycrafting_max_xp=100,
            cooking_level=1,
            cooking_xp=0,
            cooking_max_xp=100,
            alchemy_level=1,
            alchemy_xp=0,
            alchemy_max_xp=100,
            haste=0,
            critical_strike=0,
            wisdom=0,
            prospecting=0,
            attack_fire=0,
            attack_earth=0,
            attack_water=0,
            attack_air=0,
            dmg=10,
            dmg_fire=0,
            dmg_earth=0,
            dmg_water=0,
            dmg_air=0,
            res_fire=0,
            res_earth=0,
            res_water=0,
            res_air=0,
            x=0,
            y=0,
            cooldown=0,
            inventory_max_items=20
        )
        
        assert char.name == "TestChar"
        assert char.level == 1
        assert char.skin == "men1"  # Default value
        assert char.cooldown == 0

    def test_character_validation_level_bounds(self):
        """Test character level validation"""
        # Valid level
        char_data = self._get_valid_character_data()
        char_data['level'] = 45
        char = Character(**char_data)
        assert char.level == 45
        
        # Invalid level (too low)
        char_data['level'] = 0
        with pytest.raises(ValidationError):
            Character(**char_data)
            
        # Invalid level (too high)
        char_data['level'] = 46
        with pytest.raises(ValidationError):
            Character(**char_data)

    def test_character_validation_skill_levels(self):
        """Test skill level validation"""
        char_data = self._get_valid_character_data()
        
        # Valid skill levels
        char_data['mining_level'] = 30
        char = Character(**char_data)
        assert char.mining_level == 30
        
        # Invalid skill level (too low)
        char_data['mining_level'] = 0
        with pytest.raises(ValidationError):
            Character(**char_data)
            
        # Invalid skill level (too high) 
        char_data['mining_level'] = 46
        with pytest.raises(ValidationError):
            Character(**char_data)

    def test_character_validation_negative_values(self):
        """Test validation of fields that must be non-negative"""
        char_data = self._get_valid_character_data()
        
        # Valid values
        char_data['xp'] = 50
        char_data['gold'] = 1000
        char = Character(**char_data)
        assert char.xp == 50
        assert char.gold == 1000
        
        # Invalid negative values
        char_data['xp'] = -1
        with pytest.raises(ValidationError):
            Character(**char_data)
            
        char_data['xp'] = 0  # Reset
        char_data['gold'] = -100
        with pytest.raises(ValidationError):
            Character(**char_data)

    def test_character_with_inventory(self):
        """Test character with inventory slots"""
        char_data = self._get_valid_character_data()
        char_data['inventory'] = [
            InventorySlot(slot=1, code="iron_ore", quantity=10),
            InventorySlot(slot=2, code="copper_ore", quantity=5)
        ]
        
        char = Character(**char_data)
        assert len(char.inventory) == 2
        assert char.inventory[0].code == "iron_ore"
        assert char.inventory[1].quantity == 5

    def test_character_cooldown_expiration(self):
        """Test character with cooldown expiration"""
        char_data = self._get_valid_character_data()
        expiration_time = datetime.now()
        char_data['cooldown_expiration'] = expiration_time
        
        char = Character(**char_data)
        assert char.cooldown_expiration == expiration_time

    def test_is_cooldown_ready_property(self):
        """Test is_cooldown_ready property"""
        char_data = self._get_valid_character_data()
        
        # Cooldown ready
        char_data['cooldown'] = 0
        char = Character(**char_data)
        assert char.is_cooldown_ready is True
        
        # Cooldown not ready
        char_data['cooldown'] = 5
        char = Character(**char_data)
        assert char.is_cooldown_ready is False

    def test_inventory_space_available_property(self):
        """Test inventory_space_available property"""
        char_data = self._get_valid_character_data()
        char_data['inventory_max_items'] = 20
        
        # Empty inventory
        char_data['inventory'] = None
        char = Character(**char_data)
        assert char.inventory_space_available == 20
        
        # Partially filled inventory
        char_data['inventory'] = [
            InventorySlot(slot=1, code="iron_ore", quantity=10),
            InventorySlot(slot=2, code="copper_ore", quantity=5)
        ]
        char = Character(**char_data)
        assert char.inventory_space_available == 18

    def test_is_inventory_full_property(self):
        """Test is_inventory_full property"""
        char_data = self._get_valid_character_data()
        char_data['inventory_max_items'] = 2
        
        # Not full
        char_data['inventory'] = [
            InventorySlot(slot=1, code="iron_ore", quantity=10)
        ]
        char = Character(**char_data)
        assert char.is_inventory_full is False
        
        # Full inventory
        char_data['inventory'] = [
            InventorySlot(slot=1, code="iron_ore", quantity=10),
            InventorySlot(slot=2, code="copper_ore", quantity=5)
        ]
        char = Character(**char_data)
        assert char.is_inventory_full is True

    def test_from_api_character_basic(self):
        """Test creating Character from API character"""
        api_char = Mock()
        api_char.name = "APIChar"
        api_char.account = "api_account"
        api_char.skin = "women1"
        api_char.level = 10
        api_char.xp = 500
        api_char.max_xp = 1000
        api_char.gold = 250
        api_char.speed = 15
        api_char.hp = 80
        api_char.max_hp = 100
        
        # Set all skill levels
        api_char.mining_level = 5
        api_char.mining_xp = 200
        api_char.mining_max_xp = 500
        api_char.woodcutting_level = 3
        api_char.woodcutting_xp = 150
        api_char.woodcutting_max_xp = 300
        api_char.fishing_level = 2
        api_char.fishing_xp = 100
        api_char.fishing_max_xp = 200
        api_char.weaponcrafting_level = 1
        api_char.weaponcrafting_xp = 0
        api_char.weaponcrafting_max_xp = 100
        api_char.gearcrafting_level = 1
        api_char.gearcrafting_xp = 0
        api_char.gearcrafting_max_xp = 100
        api_char.jewelrycrafting_level = 1
        api_char.jewelrycrafting_xp = 0
        api_char.jewelrycrafting_max_xp = 100
        api_char.cooking_level = 4
        api_char.cooking_xp = 180
        api_char.cooking_max_xp = 400
        api_char.alchemy_level = 1
        api_char.alchemy_xp = 0
        api_char.alchemy_max_xp = 100
        
        # Set combat stats
        api_char.haste = 5
        api_char.critical_strike = 10
        api_char.wisdom = 8
        api_char.prospecting = 12
        api_char.attack_fire = 0
        api_char.attack_earth = 15
        api_char.attack_water = 0
        api_char.attack_air = 0
        api_char.dmg = 25
        api_char.dmg_fire = 0
        api_char.dmg_earth = 10
        api_char.dmg_water = 0
        api_char.dmg_air = 0
        api_char.res_fire = 5
        api_char.res_earth = 8
        api_char.res_water = 3
        api_char.res_air = 2
        
        # Position and cooldown
        api_char.x = 10
        api_char.y = 20
        api_char.cooldown = 3
        api_char.cooldown_expiration = None
        
        # Equipment slots
        api_char.weapon_slot = "iron_sword"
        api_char.rune_slot = ""
        api_char.shield_slot = "wooden_shield"
        api_char.helmet_slot = ""
        api_char.body_armor_slot = "leather_armor"
        api_char.leg_armor_slot = ""
        api_char.boots_slot = "leather_boots"
        api_char.ring1_slot = "copper_ring"
        api_char.ring2_slot = ""
        api_char.amulet_slot = ""
        api_char.artifact1_slot = ""
        api_char.artifact2_slot = ""
        api_char.artifact3_slot = ""
        api_char.utility1_slot = "health_potion"
        api_char.utility1_slot_quantity = 5
        api_char.utility2_slot = ""
        api_char.utility2_slot_quantity = 0
        api_char.bag_slot = ""
        
        # Task info
        api_char.task = "Kill 10 goblins"
        api_char.task_type = "monsters"
        api_char.task_progress = 3
        api_char.task_total = 10
        
        # Inventory
        api_char.inventory_max_items = 25
        api_char.inventory = None
        
        char = Character.from_api_character(api_char)
        
        assert char.name == "APIChar"
        assert char.level == 10
        assert char.skin == "women1"
        assert char.mining_level == 5
        assert char.x == 10
        assert char.y == 20
        assert char.weapon_slot == "iron_sword"
        assert char.task == "Kill 10 goblins"
        assert char.inventory_max_items == 25

    def test_from_api_character_with_skin_enum(self):
        """Test creating Character from API character with skin enum"""
        api_char = Mock()
        
        # Set minimal required fields first
        self._set_minimal_api_char_fields(api_char)
        
        # Mock skin as enum with value attribute (after minimal fields)
        skin_enum = Mock()
        skin_enum.value = "men2"
        api_char.skin = skin_enum
        
        # Ensure inventory is None to avoid the hasattr check issue
        api_char.inventory = None
        
        char = Character.from_api_character(api_char)
        assert char.skin == "men2"

    def test_from_api_character_with_inventory(self):
        """Test creating Character from API character with inventory"""
        api_char = Mock()
        self._set_minimal_api_char_fields(api_char)
        
        # Mock inventory slots
        slot1 = Mock()
        slot1.slot = 1
        slot1.code = "iron_ore"
        slot1.quantity = 15
        
        slot2 = Mock()
        slot2.slot = 3
        slot2.code = "copper_ore"
        slot2.quantity = 8
        
        api_char.inventory = [slot1, slot2]
        
        char = Character.from_api_character(api_char)
        
        assert len(char.inventory) == 2
        assert char.inventory[0].slot == 1
        assert char.inventory[0].code == "iron_ore"
        assert char.inventory[0].quantity == 15
        assert char.inventory[1].slot == 3
        assert char.inventory[1].code == "copper_ore"
        assert char.inventory[1].quantity == 8

    def test_from_api_character_no_inventory(self):
        """Test creating Character from API character with no inventory"""
        api_char = Mock()
        self._set_minimal_api_char_fields(api_char)
        api_char.inventory = None
        
        char = Character.from_api_character(api_char)
        assert char.inventory is None

    def test_from_api_character_empty_inventory(self):
        """Test creating Character from API character with empty inventory"""
        api_char = Mock()
        self._set_minimal_api_char_fields(api_char)
        api_char.inventory = []
        
        char = Character.from_api_character(api_char)
        # Empty list is treated as falsy, so becomes None
        assert char.inventory is None

    def test_equipment_slots_defaults(self):
        """Test equipment slot default values"""
        char_data = self._get_valid_character_data()
        char = Character(**char_data)
        
        assert char.weapon_slot == ""
        assert char.shield_slot == ""
        assert char.helmet_slot == ""
        assert char.utility1_slot_quantity == 0
        assert char.utility2_slot_quantity == 0

    def test_task_fields_defaults(self):
        """Test task field default values"""
        char_data = self._get_valid_character_data()
        char = Character(**char_data)
        
        assert char.task == ""
        assert char.task_type == ""
        assert char.task_progress == 0
        assert char.task_total == 0

    def test_assignment_validation(self):
        """Test that assignment validation works"""
        char_data = self._get_valid_character_data()
        char = Character(**char_data)
        
        # Valid assignment
        char.level = 25
        assert char.level == 25
        
        # Invalid assignment
        with pytest.raises(ValidationError):
            char.level = 50  # Too high

    def _get_valid_character_data(self):
        """Get minimal valid character data"""
        return {
            'name': 'TestChar',
            'account': 'test_account',
            'level': 5,
            'xp': 100,
            'max_xp': 500,
            'gold': 50,
            'speed': 12,
            'hp': 60,
            'max_hp': 80,
            'mining_level': 3,
            'mining_xp': 150,
            'mining_max_xp': 300,
            'woodcutting_level': 2,
            'woodcutting_xp': 80,
            'woodcutting_max_xp': 200,
            'fishing_level': 1,
            'fishing_xp': 0,
            'fishing_max_xp': 100,
            'weaponcrafting_level': 1,
            'weaponcrafting_xp': 0,
            'weaponcrafting_max_xp': 100,
            'gearcrafting_level': 1,
            'gearcrafting_xp': 0,
            'gearcrafting_max_xp': 100,
            'jewelrycrafting_level': 1,
            'jewelrycrafting_xp': 0,
            'jewelrycrafting_max_xp': 100,
            'cooking_level': 2,
            'cooking_xp': 90,
            'cooking_max_xp': 200,
            'alchemy_level': 1,
            'alchemy_xp': 0,
            'alchemy_max_xp': 100,
            'haste': 3,
            'critical_strike': 5,
            'wisdom': 7,
            'prospecting': 4,
            'attack_fire': 0,
            'attack_earth': 8,
            'attack_water': 0,
            'attack_air': 0,
            'dmg': 20,
            'dmg_fire': 0,
            'dmg_earth': 5,
            'dmg_water': 0,
            'dmg_air': 0,
            'res_fire': 2,
            'res_earth': 4,
            'res_water': 1,
            'res_air': 1,
            'x': 5,
            'y': 10,
            'cooldown': 0,
            'inventory_max_items': 20
        }

    def _set_minimal_api_char_fields(self, api_char):
        """Set minimal required fields on API character mock"""
        api_char.name = "APIChar"
        api_char.account = "api_account"
        api_char.skin = "men1"
        api_char.level = 1
        api_char.xp = 0
        api_char.max_xp = 100
        api_char.gold = 0
        api_char.speed = 10
        api_char.hp = 50
        api_char.max_hp = 50
        
        # Set all skill levels to minimum
        api_char.mining_level = 1
        api_char.mining_xp = 0
        api_char.mining_max_xp = 100
        api_char.woodcutting_level = 1
        api_char.woodcutting_xp = 0
        api_char.woodcutting_max_xp = 100
        api_char.fishing_level = 1
        api_char.fishing_xp = 0
        api_char.fishing_max_xp = 100
        api_char.weaponcrafting_level = 1
        api_char.weaponcrafting_xp = 0
        api_char.weaponcrafting_max_xp = 100
        api_char.gearcrafting_level = 1
        api_char.gearcrafting_xp = 0
        api_char.gearcrafting_max_xp = 100
        api_char.jewelrycrafting_level = 1
        api_char.jewelrycrafting_xp = 0
        api_char.jewelrycrafting_max_xp = 100
        api_char.cooking_level = 1
        api_char.cooking_xp = 0
        api_char.cooking_max_xp = 100
        api_char.alchemy_level = 1
        api_char.alchemy_xp = 0
        api_char.alchemy_max_xp = 100
        
        # Set combat stats to 0
        api_char.haste = 0
        api_char.critical_strike = 0
        api_char.wisdom = 0
        api_char.prospecting = 0
        api_char.attack_fire = 0
        api_char.attack_earth = 0
        api_char.attack_water = 0
        api_char.attack_air = 0
        api_char.dmg = 10
        api_char.dmg_fire = 0
        api_char.dmg_earth = 0
        api_char.dmg_water = 0
        api_char.dmg_air = 0
        api_char.res_fire = 0
        api_char.res_earth = 0
        api_char.res_water = 0
        api_char.res_air = 0
        
        # Position and cooldown
        api_char.x = 0
        api_char.y = 0
        api_char.cooldown = 0
        # Add cooldown_expiration attribute explicitly as None
        api_char.cooldown_expiration = None
        
        # Equipment slots (all empty)
        api_char.weapon_slot = ""
        api_char.rune_slot = ""
        api_char.shield_slot = ""
        api_char.helmet_slot = ""
        api_char.body_armor_slot = ""
        api_char.leg_armor_slot = ""
        api_char.boots_slot = ""
        api_char.ring1_slot = ""
        api_char.ring2_slot = ""
        api_char.amulet_slot = ""
        api_char.artifact1_slot = ""
        api_char.artifact2_slot = ""
        api_char.artifact3_slot = ""
        api_char.utility1_slot = ""
        api_char.utility1_slot_quantity = 0
        api_char.utility2_slot = ""
        api_char.utility2_slot_quantity = 0
        api_char.bag_slot = ""
        
        # Task info (empty)
        api_char.task = ""
        api_char.task_type = ""
        api_char.task_progress = 0
        api_char.task_total = 0
        
        # Inventory
        api_char.inventory_max_items = 20