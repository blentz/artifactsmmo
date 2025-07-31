"""
Tests for Location and Map Data Models

This module tests the Pydantic models for map/location data that align with
MapSchema and related models from the artifactsmmo-api-client.
"""

from unittest.mock import Mock

import pytest

from src.ai_player.models.location import MapContent, MapLocation


class TestMapContent:
    """Test MapContent model"""
    
    def test_map_content_creation(self):
        """Test creating MapContent with valid data"""
        content = MapContent(type="monster", code="chicken")
        
        assert content.type == "monster"
        assert content.code == "chicken"
    
    def test_map_content_validation(self):
        """Test MapContent field validation"""
        content = MapContent(type="resource", code="copper_ore")
        
        # Should be able to modify with valid values
        content.type = "workshop"
        content.code = "weaponcrafting"
        
        assert content.type == "workshop"
        assert content.code == "weaponcrafting"


class TestMapLocation:
    """Test MapLocation model"""
    
    def test_map_location_creation(self):
        """Test creating MapLocation with basic data"""
        location = MapLocation(
            name="Chicken Coop",
            skin="chicken_coop",
            x=0,
            y=1
        )
        
        assert location.name == "Chicken Coop"
        assert location.skin == "chicken_coop"
        assert location.x == 0
        assert location.y == 1
        assert location.content is None
    
    def test_map_location_with_content(self):
        """Test creating MapLocation with content"""
        content = MapContent(type="monster", code="chicken")
        location = MapLocation(
            name="Chicken Coop",
            skin="chicken_coop",
            x=0,
            y=1,
            content=content
        )
        
        assert location.content == content
        assert location.content.type == "monster"
        assert location.content.code == "chicken"
    
    def test_from_api_map_no_content(self):
        """Test creating MapLocation from API map without content"""
        api_map = Mock()
        api_map.name = "Forest"
        api_map.skin = "forest"
        api_map.x = 2
        api_map.y = 3
        api_map.content = None
        
        location = MapLocation.from_api_map(api_map)
        
        assert location.name == "Forest"
        assert location.skin == "forest"
        assert location.x == 2
        assert location.y == 3
        assert location.content is None
    
    def test_from_api_map_with_content(self):
        """Test creating MapLocation from API map with content"""
        api_content = Mock()
        api_content.type = "resource"
        api_content.code = "ash_wood"
        
        api_map = Mock()
        api_map.name = "Forest"
        api_map.skin = "forest"
        api_map.x = 2
        api_map.y = 3
        api_map.content = api_content
        
        location = MapLocation.from_api_map(api_map)
        
        assert location.name == "Forest"
        assert location.skin == "forest" 
        assert location.x == 2
        assert location.y == 3
        assert location.content is not None
        assert location.content.type == "resource"
        assert location.content.code == "ash_wood"
    
    def test_from_api_map_no_content_attribute(self):
        """Test creating MapLocation from API map without content attribute"""
        api_map = Mock()
        api_map.name = "Empty"
        api_map.skin = "empty"
        api_map.x = 0
        api_map.y = 0
        # No content attribute at all
        delattr(api_map, 'content')
        
        location = MapLocation.from_api_map(api_map)
        
        assert location.name == "Empty"
        assert location.content is None
    
    def test_coordinates_property(self):
        """Test coordinates property"""
        location = MapLocation(name="Test", skin="test", x=5, y=10)
        
        assert location.coordinates == (5, 10)
    
    def test_has_content_property(self):
        """Test has_content property"""
        # Location without content
        location = MapLocation(name="Empty", skin="empty", x=0, y=0)
        assert location.has_content is False
        
        # Location with content
        content = MapContent(type="monster", code="chicken")
        location_with_content = MapLocation(
            name="Coop", 
            skin="coop", 
            x=0, 
            y=1, 
            content=content
        )
        assert location_with_content.has_content is True
    
    def test_content_type_property(self):
        """Test content_type property"""
        # Location without content
        location = MapLocation(name="Empty", skin="empty", x=0, y=0)
        assert location.content_type is None
        
        # Location with content
        content = MapContent(type="monster", code="chicken")
        location_with_content = MapLocation(
            name="Coop", 
            skin="coop", 
            x=0, 
            y=1, 
            content=content
        )
        assert location_with_content.content_type == "monster"
    
    def test_content_code_property(self):
        """Test content_code property"""
        # Location without content
        location = MapLocation(name="Empty", skin="empty", x=0, y=0)
        assert location.content_code is None
        
        # Location with content
        content = MapContent(type="resource", code="copper_ore")
        location_with_content = MapLocation(
            name="Mine", 
            skin="mine", 
            x=1, 
            y=0, 
            content=content
        )
        assert location_with_content.content_code == "copper_ore"
    
    def test_is_monster_location_property(self):
        """Test is_monster_location property"""
        # Non-monster location
        location = MapLocation(name="Empty", skin="empty", x=0, y=0)
        assert location.is_monster_location is False
        
        # Monster location
        content = MapContent(type="monster", code="chicken")
        monster_location = MapLocation(
            name="Coop", 
            skin="coop", 
            x=0, 
            y=1, 
            content=content
        )
        assert monster_location.is_monster_location is True
        
        # Non-monster content
        resource_content = MapContent(type="resource", code="copper_ore")
        resource_location = MapLocation(
            name="Mine", 
            skin="mine", 
            x=1, 
            y=0, 
            content=resource_content
        )
        assert resource_location.is_monster_location is False
    
    def test_is_resource_location_property(self):
        """Test is_resource_location property"""
        # Non-resource location
        location = MapLocation(name="Empty", skin="empty", x=0, y=0)
        assert location.is_resource_location is False
        
        # Resource location
        content = MapContent(type="resource", code="copper_ore")
        resource_location = MapLocation(
            name="Mine", 
            skin="mine", 
            x=1, 
            y=0, 
            content=content
        )
        assert resource_location.is_resource_location is True
        
        # Non-resource content
        monster_content = MapContent(type="monster", code="chicken")
        monster_location = MapLocation(
            name="Coop", 
            skin="coop", 
            x=0, 
            y=1, 
            content=monster_content
        )
        assert monster_location.is_resource_location is False
    
    def test_is_workshop_location_property(self):
        """Test is_workshop_location property"""
        # Non-workshop location
        location = MapLocation(name="Empty", skin="empty", x=0, y=0)
        assert location.is_workshop_location is False
        
        # Workshop location
        content = MapContent(type="workshop", code="weaponcrafting")
        workshop_location = MapLocation(
            name="Weapon Shop", 
            skin="weapon_shop", 
            x=2, 
            y=3, 
            content=content
        )
        assert workshop_location.is_workshop_location is True
    
    def test_is_bank_location_property(self):
        """Test is_bank_location property"""
        # Non-bank location
        location = MapLocation(name="Empty", skin="empty", x=0, y=0)
        assert location.is_bank_location is False
        
        # Bank location
        content = MapContent(type="bank", code="bank")
        bank_location = MapLocation(
            name="Bank", 
            skin="bank", 
            x=4, 
            y=1, 
            content=content
        )
        assert bank_location.is_bank_location is True
    
    def test_is_grand_exchange_location_property(self):
        """Test is_grand_exchange_location property"""
        # Non-grand exchange location
        location = MapLocation(name="Empty", skin="empty", x=0, y=0)
        assert location.is_grand_exchange_location is False
        
        # Grand exchange location
        content = MapContent(type="grand_exchange", code="grand_exchange")
        ge_location = MapLocation(
            name="Grand Exchange", 
            skin="grand_exchange", 
            x=5, 
            y=1, 
            content=content
        )
        assert ge_location.is_grand_exchange_location is True
    
    def test_distance_to_method(self):
        """Test distance_to method for Manhattan distance calculation"""
        location = MapLocation(name="Origin", skin="origin", x=0, y=0)
        
        # Distance to same point
        assert location.distance_to(0, 0) == 0
        
        # Distance to adjacent points
        assert location.distance_to(1, 0) == 1
        assert location.distance_to(0, 1) == 1
        assert location.distance_to(-1, 0) == 1
        assert location.distance_to(0, -1) == 1
        
        # Distance to diagonal points
        assert location.distance_to(1, 1) == 2
        assert location.distance_to(-1, -1) == 2
        
        # Distance to farther points
        assert location.distance_to(3, 4) == 7
        assert location.distance_to(-2, 5) == 7
        
        # Test from non-origin location
        location2 = MapLocation(name="Offset", skin="offset", x=2, y=3)
        assert location2.distance_to(5, 7) == 7  # |2-5| + |3-7| = 3 + 4 = 7