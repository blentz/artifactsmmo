"""
Tests for Item Models

Tests the Item, ItemEffect, ItemCondition, and CraftRequirement Pydantic models
ensuring proper validation, field mapping, API integration, and property calculations.
"""

from unittest.mock import Mock
import pytest
from pydantic import ValidationError

from src.ai_player.models.item import Item, ItemEffect, ItemCondition, CraftRequirement


class TestItemEffect:
    """Test ItemEffect model"""

    def test_item_effect_creation(self):
        """Test creating valid item effect"""
        effect = ItemEffect(name="attack_earth", value=10)
        
        assert effect.name == "attack_earth"
        assert effect.value == 10

    def test_item_effect_validation(self):
        """Test item effect validation"""
        # Valid effect
        effect = ItemEffect(name="dmg", value=25)
        assert effect.name == "dmg"
        assert effect.value == 25

    def test_item_effect_assignment_validation(self):
        """Test assignment validation after creation"""
        effect = ItemEffect(name="haste", value=5)
        
        # Valid assignment
        effect.value = 8
        assert effect.value == 8
        
        # Should accept any integer (including negative)
        effect.value = -3
        assert effect.value == -3


class TestItemCondition:
    """Test ItemCondition model"""

    def test_item_condition_creation_basic(self):
        """Test creating basic item condition"""
        condition = ItemCondition(type="skill")
        
        assert condition.type == "skill"
        assert condition.skill is None
        assert condition.level is None

    def test_item_condition_creation_with_skill(self):
        """Test creating item condition with skill and level"""
        condition = ItemCondition(type="skill", skill="mining", level=10)
        
        assert condition.type == "skill"
        assert condition.skill == "mining"
        assert condition.level == 10

    def test_item_condition_optional_fields(self):
        """Test optional fields can be None"""
        condition = ItemCondition(type="level", skill=None, level=None)
        
        assert condition.type == "level"
        assert condition.skill is None
        assert condition.level is None

    def test_item_condition_assignment_validation(self):
        """Test assignment validation after creation"""
        condition = ItemCondition(type="skill", skill="mining", level=5)
        
        # Valid assignments
        condition.skill = "woodcutting"
        condition.level = 15
        assert condition.skill == "woodcutting"
        assert condition.level == 15


class TestCraftRequirement:
    """Test CraftRequirement model"""

    def test_craft_requirement_creation_empty(self):
        """Test creating empty craft requirement"""
        craft = CraftRequirement()
        
        assert craft.skill is None
        assert craft.level is None
        assert craft.items is None
        assert craft.quantity is None

    def test_craft_requirement_creation_full(self):
        """Test creating full craft requirement"""
        items = [{"code": "iron_ore", "quantity": 2}, {"code": "coal", "quantity": 1}]
        craft = CraftRequirement(
            skill="weaponcrafting",
            level=10,
            items=items,
            quantity=1
        )
        
        assert craft.skill == "weaponcrafting"
        assert craft.level == 10
        assert craft.items == items
        assert craft.quantity == 1

    def test_craft_requirement_partial_data(self):
        """Test creating craft requirement with partial data"""
        craft = CraftRequirement(skill="cooking", level=5)
        
        assert craft.skill == "cooking"
        assert craft.level == 5
        assert craft.items is None
        assert craft.quantity is None

    def test_craft_requirement_assignment_validation(self):
        """Test assignment validation after creation"""
        craft = CraftRequirement()
        
        # Valid assignments
        craft.skill = "gearcrafting"
        craft.level = 20
        craft.quantity = 3
        
        assert craft.skill == "gearcrafting"
        assert craft.level == 20
        assert craft.quantity == 3


class TestItem:
    """Test Item model"""

    def test_item_creation_minimal(self):
        """Test creating item with minimal required fields"""
        item = Item(
            name="Iron Sword",
            code="iron_sword",
            level=5,
            type="weapon",
            subtype="sword",
            description="A sturdy iron sword",
            tradeable=True
        )
        
        assert item.name == "Iron Sword"
        assert item.code == "iron_sword"
        assert item.level == 5
        assert item.type_ == "weapon"
        assert item.subtype == "sword"
        assert item.description == "A sturdy iron sword"
        assert item.tradeable is True
        assert item.conditions is None
        assert item.effects is None
        assert item.craft is None

    def test_item_validation_level_bounds(self):
        """Test item level validation"""
        item_data = self._get_valid_item_data()
        
        # Valid level
        item_data['level'] = 30
        item = Item(**item_data)
        assert item.level == 30
        
        # Invalid level (too low)
        item_data['level'] = 0
        with pytest.raises(ValidationError):
            Item(**item_data)

    def test_item_with_conditions(self):
        """Test item with conditions"""
        item_data = self._get_valid_item_data()
        item_data['conditions'] = [
            ItemCondition(type="skill", skill="mining", level=10),
            ItemCondition(type="level", level=15)
        ]
        
        item = Item(**item_data)
        assert len(item.conditions) == 2
        assert item.conditions[0].skill == "mining"
        assert item.conditions[1].level == 15

    def test_item_with_effects(self):
        """Test item with effects"""
        item_data = self._get_valid_item_data()
        item_data['effects'] = [
            ItemEffect(name="dmg", value=25),
            ItemEffect(name="attack_earth", value=10)
        ]
        
        item = Item(**item_data)
        assert len(item.effects) == 2
        assert item.effects[0].name == "dmg"
        assert item.effects[1].value == 10

    def test_item_with_craft_requirement(self):
        """Test item with craft requirement"""
        item_data = self._get_valid_item_data()
        item_data['craft'] = CraftRequirement(
            skill="weaponcrafting",
            level=20,
            items=[{"code": "iron_ore", "quantity": 3}],
            quantity=1
        )
        
        item = Item(**item_data)
        assert item.craft.skill == "weaponcrafting"
        assert item.craft.level == 20
        assert len(item.craft.items) == 1

    def test_is_weapon_property(self):
        """Test is_weapon property"""
        item_data = self._get_valid_item_data()
        
        # Weapon
        item_data['type'] = "weapon"
        item = Item(**item_data)
        assert item.is_weapon is True
        
        # Not weapon
        item_data['type'] = "tool"
        item = Item(**item_data)
        assert item.is_weapon is False

    def test_is_tool_property(self):
        """Test is_tool property"""
        item_data = self._get_valid_item_data()
        
        # Tool
        item_data['type'] = "tool"
        item = Item(**item_data)
        assert item.is_tool is True
        
        # Not tool
        item_data['type'] = "weapon"
        item = Item(**item_data)
        assert item.is_tool is False

    def test_is_equipment_property(self):
        """Test is_equipment property"""
        item_data = self._get_valid_item_data()
        
        # Equipment types
        equipment_types = ["weapon", "helmet", "body_armor", "leg_armor", "boots", "shield", "amulet", "ring"]
        for eq_type in equipment_types:
            item_data['type'] = eq_type
            item = Item(**item_data)
            assert item.is_equipment is True, f"{eq_type} should be equipment"
        
        # Not equipment
        item_data['type'] = "consumable"
        item = Item(**item_data)
        assert item.is_equipment is False

    def test_is_consumable_property(self):
        """Test is_consumable property"""
        item_data = self._get_valid_item_data()
        
        # Consumable
        item_data['type'] = "consumable"
        item = Item(**item_data)
        assert item.is_consumable is True
        
        # Not consumable
        item_data['type'] = "weapon"
        item = Item(**item_data)
        assert item.is_consumable is False

    def test_is_resource_property(self):
        """Test is_resource property"""
        item_data = self._get_valid_item_data()
        
        # Resource
        item_data['type'] = "resource"
        item = Item(**item_data)
        assert item.is_resource is True
        
        # Not resource
        item_data['type'] = "weapon"
        item = Item(**item_data)
        assert item.is_resource is False

    def test_from_api_item_basic(self):
        """Test creating Item from API item"""
        # Use spec to prevent Mock from creating unwanted attributes
        api_item = Mock(spec=['name', 'code', 'level', 'type', 'subtype', 'description', 'tradeable', 'conditions', 'effects', 'craft'])
        api_item.name = "Copper Axe"
        api_item.code = "copper_axe"
        api_item.level = 1
        api_item.type = "tool"
        api_item.subtype = "axe"
        api_item.description = "A basic copper axe for woodcutting"
        api_item.tradeable = True
        api_item.conditions = None
        api_item.effects = None
        api_item.craft = None
        
        item = Item.from_api_item(api_item)
        
        assert item.name == "Copper Axe"
        assert item.code == "copper_axe"
        assert item.level == 1
        assert item.type_ == "tool"
        assert item.subtype == "axe"
        assert item.description == "A basic copper axe for woodcutting"
        assert item.tradeable is True
        assert item.conditions is None
        assert item.effects is None
        assert item.craft is None

    def test_from_api_item_with_type_underscore(self):
        """Test creating Item from API item with type_ attribute"""
        api_item = Mock(spec=['name', 'code', 'level', 'type_', 'subtype', 'description', 'tradeable', 'conditions', 'effects', 'craft'])
        self._set_minimal_api_item_fields(api_item)
        api_item.type_ = "weapon"  # Use type_ instead of type
        # Remove type to test type_ path
        delattr(api_item, 'type')
        
        item = Item.from_api_item(api_item)
        assert item.type_ == "weapon"

    def test_from_api_item_with_conditions(self):
        """Test creating Item from API item with conditions"""
        api_item = self._create_api_item_mock()
        self._set_minimal_api_item_fields(api_item)
        
        # Mock conditions with proper specs
        condition1 = Mock(spec=['type', 'skill', 'level'])
        condition1.type = "skill"
        condition1.skill = "mining"
        condition1.level = 10
        
        condition2 = Mock(spec=['type'])
        condition2.type = "level"
        
        api_item.conditions = [condition1, condition2]
        
        item = Item.from_api_item(api_item)
        
        assert len(item.conditions) == 2
        assert item.conditions[0].type == "skill"
        assert item.conditions[0].skill == "mining"
        assert item.conditions[0].level == 10
        assert item.conditions[1].type == "level"
        assert item.conditions[1].skill is None
        assert item.conditions[1].level is None

    def test_from_api_item_with_effects(self):
        """Test creating Item from API item with effects"""
        api_item = self._create_api_item_mock()
        self._set_minimal_api_item_fields(api_item)
        
        # Mock effects with proper specs
        effect1 = Mock(spec=['name', 'value'])
        effect1.name = "dmg"
        effect1.value = 30
        
        effect2 = Mock(spec=['name', 'value'])
        effect2.name = "attack_fire"
        effect2.value = 15
        
        api_item.effects = [effect1, effect2]
        
        item = Item.from_api_item(api_item)
        
        assert len(item.effects) == 2
        assert item.effects[0].name == "dmg"
        assert item.effects[0].value == 30
        assert item.effects[1].name == "attack_fire"
        assert item.effects[1].value == 15

    def test_from_api_item_with_craft(self):
        """Test creating Item from API item with craft requirement"""
        api_item = self._create_api_item_mock()
        self._set_minimal_api_item_fields(api_item)
        
        # Mock craft requirement with proper spec
        craft = Mock(spec=['skill', 'level', 'items', 'quantity'])
        craft.skill = "weaponcrafting"
        craft.level = 25
        craft.items = [{"code": "iron_ore", "quantity": 3}, {"code": "coal", "quantity": 1}]
        craft.quantity = 1
        
        api_item.craft = craft
        
        item = Item.from_api_item(api_item)
        
        assert item.craft.skill == "weaponcrafting"
        assert item.craft.level == 25
        assert item.craft.items == [{"code": "iron_ore", "quantity": 3}, {"code": "coal", "quantity": 1}]
        assert item.craft.quantity == 1

    def test_from_api_item_no_conditions(self):
        """Test creating Item from API item with no conditions"""
        api_item = self._create_api_item_mock()
        self._set_minimal_api_item_fields(api_item)
        api_item.conditions = None
        
        item = Item.from_api_item(api_item)
        assert item.conditions is None

    def test_from_api_item_empty_conditions(self):
        """Test creating Item from API item with empty conditions"""
        api_item = self._create_api_item_mock()
        self._set_minimal_api_item_fields(api_item)
        api_item.conditions = []
        
        item = Item.from_api_item(api_item)
        # Empty list is treated as falsy, so becomes None
        assert item.conditions is None

    def test_from_api_item_no_effects(self):
        """Test creating Item from API item with no effects"""
        api_item = self._create_api_item_mock()
        self._set_minimal_api_item_fields(api_item)
        api_item.effects = None
        
        item = Item.from_api_item(api_item)
        assert item.effects is None

    def test_from_api_item_empty_effects(self):
        """Test creating Item from API item with empty effects"""
        api_item = self._create_api_item_mock()
        self._set_minimal_api_item_fields(api_item)
        api_item.effects = []
        
        item = Item.from_api_item(api_item)
        # Empty list is treated as falsy, so becomes None
        assert item.effects is None

    def test_from_api_item_no_craft(self):
        """Test creating Item from API item with no craft requirement"""
        api_item = self._create_api_item_mock()
        self._set_minimal_api_item_fields(api_item)
        api_item.craft = None
        
        item = Item.from_api_item(api_item)
        assert item.craft is None

    def test_assignment_validation(self):
        """Test that assignment validation works"""
        item_data = self._get_valid_item_data()
        item = Item(**item_data)
        
        # Valid assignment
        item.level = 25
        assert item.level == 25
        
        # Invalid assignment
        with pytest.raises(ValidationError):
            item.level = 0  # Too low

    def _get_valid_item_data(self):
        """Get minimal valid item data"""
        return {
            'name': 'Test Item',
            'code': 'test_item',
            'level': 10,
            'type': 'tool',
            'subtype': 'pickaxe',
            'description': 'A test item for validation',
            'tradeable': True
        }

    def _create_api_item_mock(self):
        """Create API item mock with proper spec"""
        return Mock(spec=['name', 'code', 'level', 'type', 'subtype', 'description', 'tradeable', 'conditions', 'effects', 'craft'])

    def _set_minimal_api_item_fields(self, api_item):
        """Set minimal required fields on API item mock"""
        api_item.name = "Test Item"
        api_item.code = "test_item"
        api_item.level = 5
        api_item.type = "tool"
        api_item.subtype = "pickaxe"
        api_item.description = "A test item"
        api_item.tradeable = True
        api_item.conditions = None
        api_item.effects = None
        api_item.craft = None