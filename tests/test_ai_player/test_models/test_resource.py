"""
Tests for Resource Data Models

Tests for Pydantic models representing resource data from the ArtifactsMMO API,
including ResourceDrop and Resource models with comprehensive validation and
functionality testing.
"""

import pytest
from typing import Any, List
from unittest.mock import Mock

from src.ai_player.models.resource import Resource, ResourceDrop


class TestResourceDrop:
    """Test ResourceDrop model functionality"""

    def test_resource_drop_creation(self):
        """Test basic ResourceDrop creation"""
        drop = ResourceDrop(
            code="copper_ore",
            rate=50000,
            min_quantity=1,
            max_quantity=3
        )
        
        assert drop.code == "copper_ore"
        assert drop.rate == 50000
        assert drop.min_quantity == 1
        assert drop.max_quantity == 3

    def test_resource_drop_validation_rate_range(self):
        """Test ResourceDrop validates rate within valid range"""
        # Valid rate
        drop = ResourceDrop(code="iron", rate=25000, min_quantity=1, max_quantity=2)
        assert drop.rate == 25000
        
        # Rate too low
        with pytest.raises(ValueError):
            ResourceDrop(code="iron", rate=0, min_quantity=1, max_quantity=2)
        
        # Rate too high
        with pytest.raises(ValueError):
            ResourceDrop(code="iron", rate=100001, min_quantity=1, max_quantity=2)

    def test_resource_drop_validation_quantities(self):
        """Test ResourceDrop validates quantity ranges"""
        # Valid quantities
        drop = ResourceDrop(code="gold", rate=10000, min_quantity=5, max_quantity=10)
        assert drop.min_quantity == 5
        assert drop.max_quantity == 10
        
        # Invalid min_quantity
        with pytest.raises(ValueError):
            ResourceDrop(code="gold", rate=10000, min_quantity=0, max_quantity=5)
        
        # Invalid max_quantity
        with pytest.raises(ValueError):
            ResourceDrop(code="gold", rate=10000, min_quantity=1, max_quantity=0)

    def test_resource_drop_assignment_validation(self):
        """Test ResourceDrop validates assignment"""
        drop = ResourceDrop(code="silver", rate=20000, min_quantity=2, max_quantity=4)
        
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


class TestResourceBasicCreation:
    """Test basic Resource model creation and validation"""

    def test_resource_minimal_creation(self):
        """Test Resource creation with minimal fields"""
        drops = [ResourceDrop(code="copper_ore", rate=80000, min_quantity=1, max_quantity=2)]
        
        resource = Resource(
            name="Copper",
            code="copper",
            level=1,
            skill="mining",
            drops=drops
        )
        
        assert resource.name == "Copper"
        assert resource.code == "copper"
        assert resource.level == 1
        assert resource.skill == "mining"
        assert len(resource.drops) == 1
        assert resource.drops[0].code == "copper_ore"

    def test_resource_with_multiple_drops(self):
        """Test Resource creation with multiple drops"""
        drops = [
            ResourceDrop(code="ash_wood", rate=70000, min_quantity=1, max_quantity=2),
            ResourceDrop(code="ash_plank", rate=5000, min_quantity=1, max_quantity=1)
        ]
        
        resource = Resource(
            name="Ash Tree",
            code="ash_tree",
            level=1,
            skill="woodcutting",
            drops=drops
        )
        
        assert resource.name == "Ash Tree"
        assert resource.code == "ash_tree"
        assert resource.skill == "woodcutting"
        assert len(resource.drops) == 2

    def test_resource_validation_level_range(self):
        """Test Resource validates level within valid range"""
        drops = [ResourceDrop(code="item", rate=50000, min_quantity=1, max_quantity=1)]
        
        # Valid level
        resource = Resource(name="Test", code="test", level=25, skill="mining", drops=drops)
        assert resource.level == 25
        
        # Level too low
        with pytest.raises(ValueError):
            Resource(name="Test", code="test", level=0, skill="mining", drops=drops)
        
        # Level too high
        with pytest.raises(ValueError):
            Resource(name="Test", code="test", level=46, skill="mining", drops=drops)

    def test_resource_assignment_validation(self):
        """Test Resource validates field assignments"""
        drops = [ResourceDrop(code="item", rate=50000, min_quantity=1, max_quantity=1)]
        resource = Resource(name="Test", code="test", level=5, skill="mining", drops=drops)
        
        # Valid assignment
        resource.level = 10
        assert resource.level == 10
        
        # Invalid assignment should raise error
        with pytest.raises(ValueError):
            resource.level = 50


class TestResourceFromApiResource:
    """Test Resource.from_api_resource factory method"""

    def test_from_api_resource_single_drop(self):
        """Test creating Resource from API resource with single drop"""
        # Mock drop object
        api_drop = Mock(spec=['code', 'rate', 'min_quantity', 'max_quantity'])
        api_drop.code = "iron_ore"
        api_drop.rate = 60000
        api_drop.min_quantity = 1
        api_drop.max_quantity = 3
        
        # Mock resource object
        api_resource = Mock(spec=['name', 'code', 'level', 'skill', 'drops'])
        api_resource.name = "Iron Rocks"
        api_resource.code = "iron_rocks"
        api_resource.level = 10
        api_resource.skill = "mining"
        api_resource.drops = [api_drop]
        
        resource = Resource.from_api_resource(api_resource)
        
        assert resource.name == "Iron Rocks"
        assert resource.code == "iron_rocks"
        assert resource.level == 10
        assert resource.skill == "mining"
        assert len(resource.drops) == 1
        assert resource.drops[0].code == "iron_ore"
        assert resource.drops[0].rate == 60000
        assert resource.drops[0].min_quantity == 1
        assert resource.drops[0].max_quantity == 3

    def test_from_api_resource_multiple_drops(self):
        """Test creating Resource from API resource with multiple drops"""
        # Mock drop objects
        api_drop1 = Mock(spec=['code', 'rate', 'min_quantity', 'max_quantity'])
        api_drop1.code = "trout"
        api_drop1.rate = 80000
        api_drop1.min_quantity = 1
        api_drop1.max_quantity = 1
        
        api_drop2 = Mock(spec=['code', 'rate', 'min_quantity', 'max_quantity'])
        api_drop2.code = "shrimp"
        api_drop2.rate = 15000
        api_drop2.min_quantity = 1
        api_drop2.max_quantity = 2
        
        # Mock resource object
        api_resource = Mock(spec=['name', 'code', 'level', 'skill', 'drops'])
        api_resource.name = "Gudgeon Fishing Spot"
        api_resource.code = "gudgeon_fishing_spot"
        api_resource.level = 1
        api_resource.skill = "fishing"
        api_resource.drops = [api_drop1, api_drop2]
        
        resource = Resource.from_api_resource(api_resource)
        
        assert resource.name == "Gudgeon Fishing Spot"
        assert resource.code == "gudgeon_fishing_spot"
        assert resource.level == 1
        assert resource.skill == "fishing"
        assert len(resource.drops) == 2
        assert resource.drops[0].code == "trout"
        assert resource.drops[1].code == "shrimp"

    def test_from_api_resource_empty_drops(self):
        """Test creating Resource from API resource with empty drops"""
        # Mock resource object with empty drops
        api_resource = Mock(spec=['name', 'code', 'level', 'skill', 'drops'])
        api_resource.name = "Empty Resource"
        api_resource.code = "empty"
        api_resource.level = 5
        api_resource.skill = "mining"
        api_resource.drops = []
        
        resource = Resource.from_api_resource(api_resource)
        
        assert resource.name == "Empty Resource"
        assert resource.code == "empty"
        assert resource.level == 5
        assert resource.skill == "mining"
        assert len(resource.drops) == 0


class TestResourceProperties:
    """Test Resource property methods"""

    def setup_method(self):
        """Set up test resources for property testing"""
        self.drops = [ResourceDrop(code="item", rate=50000, min_quantity=1, max_quantity=1)]

    def test_is_mining_resource_true(self):
        """Test is_mining_resource returns True for mining skill"""
        resource = Resource(name="Copper", code="copper", level=1, skill="mining", drops=self.drops)
        assert resource.is_mining_resource is True

    def test_is_mining_resource_case_insensitive(self):
        """Test is_mining_resource is case insensitive"""
        resource = Resource(name="Copper", code="copper", level=1, skill="MINING", drops=self.drops)
        assert resource.is_mining_resource is True

    def test_is_mining_resource_false(self):
        """Test is_mining_resource returns False for non-mining skills"""
        resource = Resource(name="Tree", code="tree", level=1, skill="woodcutting", drops=self.drops)
        assert resource.is_mining_resource is False

    def test_is_woodcutting_resource_true(self):
        """Test is_woodcutting_resource returns True for woodcutting skill"""
        resource = Resource(name="Tree", code="tree", level=1, skill="woodcutting", drops=self.drops)
        assert resource.is_woodcutting_resource is True

    def test_is_woodcutting_resource_case_insensitive(self):
        """Test is_woodcutting_resource is case insensitive"""
        resource = Resource(name="Tree", code="tree", level=1, skill="WOODCUTTING", drops=self.drops)
        assert resource.is_woodcutting_resource is True

    def test_is_woodcutting_resource_false(self):
        """Test is_woodcutting_resource returns False for non-woodcutting skills"""
        resource = Resource(name="Fish", code="fish", level=1, skill="fishing", drops=self.drops)
        assert resource.is_woodcutting_resource is False

    def test_is_fishing_resource_true(self):
        """Test is_fishing_resource returns True for fishing skill"""
        resource = Resource(name="Fish", code="fish", level=1, skill="fishing", drops=self.drops)
        assert resource.is_fishing_resource is True

    def test_is_fishing_resource_case_insensitive(self):
        """Test is_fishing_resource is case insensitive"""
        resource = Resource(name="Fish", code="fish", level=1, skill="FISHING", drops=self.drops)
        assert resource.is_fishing_resource is True

    def test_is_fishing_resource_false(self):
        """Test is_fishing_resource returns False for non-fishing skills"""
        resource = Resource(name="Ore", code="ore", level=1, skill="mining", drops=self.drops)
        assert resource.is_fishing_resource is False

    def test_has_drops_true(self):
        """Test has_drops returns True when drops exist"""
        resource = Resource(name="Resource", code="resource", level=1, skill="mining", drops=self.drops)
        assert resource.has_drops is True

    def test_has_drops_false(self):
        """Test has_drops returns False when no drops"""
        resource = Resource(name="Resource", code="resource", level=1, skill="mining", drops=[])
        assert resource.has_drops is False


class TestResourceMethods:
    """Test Resource method functionality"""

    def test_get_drop_by_code_found(self):
        """Test get_drop_by_code returns correct drop when found"""
        drops = [
            ResourceDrop(code="copper_ore", rate=70000, min_quantity=1, max_quantity=2),
            ResourceDrop(code="iron_ore", rate=20000, min_quantity=1, max_quantity=1),
            ResourceDrop(code="gold_ore", rate=5000, min_quantity=1, max_quantity=1)
        ]
        
        resource = Resource(name="Mixed Ore", code="mixed", level=5, skill="mining", drops=drops)
        
        drop = resource.get_drop_by_code("iron_ore")
        assert drop is not None
        assert drop.code == "iron_ore"
        assert drop.rate == 20000

    def test_get_drop_by_code_not_found(self):
        """Test get_drop_by_code returns None when not found"""
        drops = [
            ResourceDrop(code="copper_ore", rate=70000, min_quantity=1, max_quantity=2)
        ]
        
        resource = Resource(name="Copper", code="copper", level=1, skill="mining", drops=drops)
        
        drop = resource.get_drop_by_code("nonexistent_ore")
        assert drop is None

    def test_get_drop_by_code_empty_drops(self):
        """Test get_drop_by_code returns None when no drops exist"""
        resource = Resource(name="Empty", code="empty", level=1, skill="mining", drops=[])
        
        drop = resource.get_drop_by_code("any_item")
        assert drop is None

    def test_can_gather_with_level_sufficient(self):
        """Test can_gather_with_level returns True when skill level is sufficient"""
        drops = [ResourceDrop(code="item", rate=50000, min_quantity=1, max_quantity=1)]
        resource = Resource(name="Resource", code="resource", level=10, skill="mining", drops=drops)
        
        assert resource.can_gather_with_level(10) is True
        assert resource.can_gather_with_level(15) is True

    def test_can_gather_with_level_insufficient(self):
        """Test can_gather_with_level returns False when skill level is insufficient"""
        drops = [ResourceDrop(code="item", rate=50000, min_quantity=1, max_quantity=1)]
        resource = Resource(name="Resource", code="resource", level=10, skill="mining", drops=drops)
        
        assert resource.can_gather_with_level(5) is False
        assert resource.can_gather_with_level(9) is False

    def test_can_gather_with_level_exact_match(self):
        """Test can_gather_with_level returns True for exact level match"""
        drops = [ResourceDrop(code="item", rate=50000, min_quantity=1, max_quantity=1)]
        resource = Resource(name="Resource", code="resource", level=15, skill="mining", drops=drops)
        
        assert resource.can_gather_with_level(15) is True

    def test_get_primary_drop_single_drop(self):
        """Test get_primary_drop returns the only drop when single drop exists"""
        drops = [ResourceDrop(code="only_item", rate=80000, min_quantity=1, max_quantity=3)]
        resource = Resource(name="Single", code="single", level=1, skill="mining", drops=drops)
        
        primary = resource.get_primary_drop()
        assert primary is not None
        assert primary.code == "only_item"
        assert primary.rate == 80000

    def test_get_primary_drop_multiple_drops(self):
        """Test get_primary_drop returns highest rate drop when multiple exist"""
        drops = [
            ResourceDrop(code="common_item", rate=60000, min_quantity=1, max_quantity=2),
            ResourceDrop(code="rare_item", rate=5000, min_quantity=1, max_quantity=1),
            ResourceDrop(code="primary_item", rate=80000, min_quantity=2, max_quantity=4),
            ResourceDrop(code="uncommon_item", rate=15000, min_quantity=1, max_quantity=1)
        ]
        
        resource = Resource(name="Multi", code="multi", level=10, skill="mining", drops=drops)
        
        primary = resource.get_primary_drop()
        assert primary is not None
        assert primary.code == "primary_item"
        assert primary.rate == 80000

    def test_get_primary_drop_no_drops(self):
        """Test get_primary_drop returns None when no drops exist"""
        resource = Resource(name="Empty", code="empty", level=1, skill="mining", drops=[])
        
        primary = resource.get_primary_drop()
        assert primary is None

    def test_get_primary_drop_tie_in_rates(self):
        """Test get_primary_drop handles ties in drop rates correctly"""
        drops = [
            ResourceDrop(code="item1", rate=50000, min_quantity=1, max_quantity=1),
            ResourceDrop(code="item2", rate=50000, min_quantity=2, max_quantity=2),
            ResourceDrop(code="item3", rate=30000, min_quantity=1, max_quantity=3)
        ]
        
        resource = Resource(name="Tied", code="tied", level=5, skill="mining", drops=drops)
        
        primary = resource.get_primary_drop()
        assert primary is not None
        assert primary.rate == 50000
        # Should return one of the tied items (either item1 or item2)
        assert primary.code in ["item1", "item2"]


class TestResourceEdgeCases:
    """Test edge cases and error conditions"""

    def test_resource_with_mixed_skill_case(self):
        """Test resource with mixed case skill name"""
        drops = [ResourceDrop(code="item", rate=50000, min_quantity=1, max_quantity=1)]
        resource = Resource(name="Mixed", code="mixed", level=5, skill="WoodCutting", drops=drops)
        
        assert resource.is_woodcutting_resource is True
        assert resource.is_mining_resource is False
        assert resource.is_fishing_resource is False

    def test_resource_drop_string_representation(self):
        """Test ResourceDrop can be represented as string"""
        drop = ResourceDrop(code="gold_ore", rate=10000, min_quantity=1, max_quantity=2)
        
        # Should not raise an exception
        str_repr = str(drop)
        assert "gold_ore" in str_repr
        assert "10000" in str_repr

    def test_resource_string_representation(self):
        """Test Resource can be represented as string"""
        drops = [ResourceDrop(code="item", rate=50000, min_quantity=1, max_quantity=1)]
        resource = Resource(name="Test Resource", code="test", level=5, skill="mining", drops=drops)
        
        # Should not raise an exception
        str_repr = str(resource)
        assert "Test Resource" in str_repr
        assert "test" in str_repr

    def test_resource_equality_comparison(self):
        """Test Resource equality comparison"""
        drops = [ResourceDrop(code="item", rate=50000, min_quantity=1, max_quantity=1)]
        
        resource1 = Resource(name="Same", code="same", level=5, skill="mining", drops=drops)
        resource2 = Resource(name="Same", code="same", level=5, skill="mining", drops=drops)
        resource3 = Resource(name="Different", code="different", level=5, skill="mining", drops=drops)
        
        # Pydantic models should support equality comparison
        assert resource1 == resource2
        assert resource1 != resource3

    def test_resource_drop_equality_comparison(self):
        """Test ResourceDrop equality comparison"""
        drop1 = ResourceDrop(code="item", rate=50000, min_quantity=1, max_quantity=2)
        drop2 = ResourceDrop(code="item", rate=50000, min_quantity=1, max_quantity=2)
        drop3 = ResourceDrop(code="different", rate=50000, min_quantity=1, max_quantity=2)
        
        # Pydantic models should support equality comparison
        assert drop1 == drop2
        assert drop1 != drop3

    def test_resource_with_unknown_skill(self):
        """Test resource with skill that doesn't match known types"""
        drops = [ResourceDrop(code="item", rate=50000, min_quantity=1, max_quantity=1)]
        resource = Resource(name="Unknown", code="unknown", level=5, skill="unknown_skill", drops=drops)
        
        assert resource.is_mining_resource is False
        assert resource.is_woodcutting_resource is False
        assert resource.is_fishing_resource is False

    def test_resource_drop_with_equal_min_max_quantity(self):
        """Test ResourceDrop with equal min and max quantities"""
        drop = ResourceDrop(code="fixed_item", rate=75000, min_quantity=3, max_quantity=3)
        
        assert drop.min_quantity == 3
        assert drop.max_quantity == 3

    def test_resource_level_boundaries(self):
        """Test Resource level at boundaries"""
        drops = [ResourceDrop(code="item", rate=50000, min_quantity=1, max_quantity=1)]
        
        # Minimum level
        resource_min = Resource(name="Min", code="min", level=1, skill="mining", drops=drops)
        assert resource_min.level == 1
        
        # Maximum level
        resource_max = Resource(name="Max", code="max", level=45, skill="mining", drops=drops)
        assert resource_max.level == 45

    def test_resource_drop_rate_boundaries(self):
        """Test ResourceDrop rate at boundaries"""
        # Minimum rate
        drop_min = ResourceDrop(code="min_item", rate=1, min_quantity=1, max_quantity=1)
        assert drop_min.rate == 1
        
        # Maximum rate
        drop_max = ResourceDrop(code="max_item", rate=100000, min_quantity=1, max_quantity=1)
        assert drop_max.rate == 100000