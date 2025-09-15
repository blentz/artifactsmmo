"""
Additional tests for CacheManager to achieve 100% coverage.

This module focuses on testing uncovered lines and edge cases
in the CacheManager class to reach full code coverage.
"""

import os
import shutil
import tempfile
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.game_data.cache_manager import CacheManager, CacheMetadata
from src.game_data.models import GameItem, GameMap, GameMonster, GameNPC, GameResource
from src.game_data.character import Character
from src.game_data.game_data import GameData


def create_complete_character_data(name: str = "test_char") -> dict:
    """Create complete character data with all required fields"""
    return {
        "name": name,
        "account": "test_account",
        "skin": "men1",
        "level": 1,
        "xp": 0,
        "max_xp": 100,
        "gold": 0,
        "speed": 1,
        "hp": 100,
        "max_hp": 100,
        "mining_level": 1,
        "mining_xp": 0,
        "mining_max_xp": 100,
        "woodcutting_level": 1,
        "woodcutting_xp": 0,
        "woodcutting_max_xp": 100,
        "fishing_level": 1,
        "fishing_xp": 0,
        "fishing_max_xp": 100,
        "weaponcrafting_level": 1,
        "weaponcrafting_xp": 0,
        "weaponcrafting_max_xp": 100,
        "gearcrafting_level": 1,
        "gearcrafting_xp": 0,
        "gearcrafting_max_xp": 100,
        "jewelrycrafting_level": 1,
        "jewelrycrafting_xp": 0,
        "jewelrycrafting_max_xp": 100,
        "cooking_level": 1,
        "cooking_xp": 0,
        "cooking_max_xp": 100,
        "alchemy_level": 1,
        "alchemy_xp": 0,
        "alchemy_max_xp": 100,
        "haste": 0,
        "critical_strike": 0,
        "wisdom": 0,
        "prospecting": 0,
        "attack_fire": 0,
        "attack_earth": 0,
        "attack_water": 0,
        "attack_air": 0,
        "dmg": 0,
        "dmg_fire": 0,
        "dmg_earth": 0,
        "dmg_water": 0,
        "dmg_air": 0,
        "res_fire": 0,
        "res_earth": 0,
        "res_water": 0,
        "res_air": 0,
        "x": 0,
        "y": 0,
        "cooldown": 0,
        "cooldown_expiration": None,
        "weapon_slot": "",
        "shield_slot": "",
        "helmet_slot": "",
        "body_armor_slot": "",
        "leg_armor_slot": "",
        "boots_slot": "",
        "ring1_slot": "",
        "ring2_slot": "",
        "amulet_slot": "",
        "artifact1_slot": "",
        "artifact2_slot": "",
        "artifact3_slot": "",
        "utility1_slot": "",
        "utility1_slot_quantity": 0,
        "utility2_slot": "",
        "utility2_slot_quantity": 0,
        "task": "",
        "task_type": "",
        "task_progress": 0,
        "task_total": 0,
        "inventory_max_items": 30,
        "inventory": []
    }


class TestCacheManagerCoverage:
    """Test CacheManager uncovered lines for 100% coverage"""

    @pytest.fixture
    def cache_manager(self):
        """Create CacheManager with mocked API client"""
        mock_api_client = AsyncMock()
        with tempfile.TemporaryDirectory() as temp_dir:
            yield CacheManager(mock_api_client, temp_dir)

    @pytest.mark.asyncio
    async def test_load_nearby_maps_with_invalid_coords(self, cache_manager):
        """Test load_nearby_maps handling of 404 errors (lines 196-228)"""
        # Mock get_all_maps to return empty list
        cache_manager._api_client.get_all_maps.return_value = []
        
        # Mock get_map to raise ValueError for "Resource not found"
        cache_manager._api_client.get_map.side_effect = ValueError("Resource not found")
        
        # Should handle 404s gracefully and track invalid coords
        await cache_manager.load_nearby_maps(0, 0, 1)
        
        # Should have tracked the invalid coordinates
        assert hasattr(cache_manager, '_invalid_coords')
        assert len(cache_manager._invalid_coords) > 0

    @pytest.mark.asyncio
    async def test_load_nearby_maps_with_successful_maps(self, cache_manager):
        """Test load_nearby_maps with successful map loading"""
        # Mock get_all_maps to return existing maps
        existing_map = GameMap(name="existing", skin="grass", x=10, y=10, content=None)
        cache_manager._api_client.get_all_maps.return_value = [existing_map]
        
        # Mock get_map to return new maps
        new_map = GameMap(name="new", skin="forest", x=0, y=0, content=None)
        cache_manager._api_client.get_map.return_value = new_map
        
        # Mock save_cache_data and _update_metadata
        cache_manager.save_cache_data = Mock()
        cache_manager._update_metadata = Mock()
        
        await cache_manager.load_nearby_maps(0, 0, 1)
        
        # Should save enhanced maps
        cache_manager.save_cache_data.assert_called()
        cache_manager._update_metadata.assert_called_with("maps")

    @pytest.mark.asyncio
    async def test_load_nearby_maps_non_404_error(self, cache_manager):
        """Test load_nearby_maps with non-404 ValueError"""
        cache_manager._api_client.get_all_maps.return_value = []
        cache_manager._api_client.get_map.side_effect = ValueError("Rate limit exceeded")
        
        # Should re-raise non-404 errors
        with pytest.raises(ValueError, match="Rate limit exceeded"):
            await cache_manager.load_nearby_maps(0, 0, 1)

    def test_load_cache_data_characters_type(self, cache_manager):
        """Test load_cache_data with characters data type (line 337)"""
        # Create mock yaml data with complete character data
        with patch('src.game_data.cache_manager.YamlData') as mock_yaml:
            mock_yaml.return_value.data = {
                "data": [create_complete_character_data()]
            }
            
            result = cache_manager.load_cache_data("characters")
            
            assert result is not None
            assert len(result) == 1
            assert isinstance(result[0], Character)

    def test_load_cache_data_invalid_file_format(self, cache_manager):
        """Test load_cache_data with invalid file format (lines 342-343)"""
        with patch('src.game_data.cache_manager.YamlData') as mock_yaml:
            # Mock yaml data without "data" key
            mock_yaml.return_value.data = {"invalid": "format"}
            
            result = cache_manager.load_cache_data("items")
            assert result is None

    def test_get_cache_metadata_key_error(self, cache_manager):
        """Test get_cache_metadata with KeyError (line 383)"""
        with patch('src.game_data.cache_manager.YamlData') as mock_yaml:
            mock_yaml.return_value.data = {"data": {"invalid": "format"}}  # Missing required fields
            
            result = cache_manager.get_cache_metadata()
            
            # Should return default metadata
            assert result.cache_version == "1.0.0"
            assert result.data_sources == {}

    def test_get_cache_metadata_value_error(self, cache_manager):
        """Test get_cache_metadata with ValueError (line 383)"""
        with patch('src.game_data.cache_manager.YamlData') as mock_yaml:
            mock_yaml.return_value.data = {"data": {"last_updated": "invalid_date"}}
            
            result = cache_manager.get_cache_metadata()
            
            # Should return default metadata
            assert result.cache_version == "1.0.0"

    def test_get_cache_metadata_os_error(self, cache_manager):
        """Test get_cache_metadata with OSError (line 385)"""
        with patch('src.game_data.cache_manager.YamlData') as mock_yaml:
            mock_yaml.side_effect = OSError("Permission denied")
            
            result = cache_manager.get_cache_metadata()
            
            # Should return default metadata
            assert result.cache_version == "1.0.0"

    @pytest.mark.asyncio
    async def test_cache_character_data_with_model_dump(self, cache_manager):
        """Test cache_character_data with model_dump (lines 443-447)"""
        # Mock character with model_dump method
        mock_character = Mock()
        mock_character.model_dump.return_value = {"name": "test", "level": 1}
        cache_manager._api_client.get_character.return_value = mock_character
        
        with patch('src.game_data.cache_manager.YamlData') as mock_yaml:
            await cache_manager.cache_character_data("test_char")
            
            # Should call model_dump and save data
            mock_character.model_dump.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_character_data_with_dict_method(self, cache_manager):
        """Test cache_character_data with dict method"""
        # Mock character with dict method
        mock_character = Mock()
        mock_character.dict.return_value = {"name": "test", "level": 1}
        # Remove model_dump attribute
        del mock_character.model_dump
        cache_manager._api_client.get_character.return_value = mock_character
        
        with patch('src.game_data.cache_manager.YamlData') as mock_yaml:
            await cache_manager.cache_character_data("test_char")
            
            # Should call dict method
            mock_character.dict.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_character_data_fallback(self, cache_manager):
        """Test cache_character_data fallback path"""
        # Create a simple object with __dict__ but no model_dump or dict methods
        class SimpleCharacter:
            def __init__(self):
                self.name = "test"
                self.level = 1
        
        mock_character = SimpleCharacter()
        cache_manager._api_client.get_character.return_value = mock_character
        
        with patch('src.game_data.cache_manager.YamlData') as mock_yaml:
            await cache_manager.cache_character_data("test_char")
            
            # Should use __dict__ as fallback
            mock_yaml.assert_called()

    @pytest.mark.asyncio
    async def test_cache_all_characters_cache_hit(self, cache_manager):
        """Test cache_all_characters with valid cache (line 472)"""
        # Mock valid cache
        cache_manager.is_cache_valid = Mock(return_value=True)
        mock_characters = [Character(**create_complete_character_data("test"))]
        cache_manager.load_cache_data = Mock(return_value=mock_characters)
        
        result = await cache_manager.cache_all_characters(force_refresh=False)
        
        assert result == mock_characters
        # Should not call API when cache is valid
        cache_manager._api_client.get_characters.assert_not_called()

    def test_get_character_from_cache_found(self, cache_manager):
        """Test get_character_from_cache when character is found (lines 495-502)"""
        # Mock characters data
        mock_characters = [
            Mock(**{"get.return_value": "other_char"}),
            Mock(**{"get.return_value": "test_char"}),
        ]
        # Set up the get method to return the name properly
        mock_characters[0].get = Mock(side_effect=lambda key: "other_char" if key == "name" else None)
        mock_characters[1].get = Mock(side_effect=lambda key: "test_char" if key == "name" else None)
        
        cache_manager.load_cache_data = Mock(return_value=mock_characters)
        
        result = cache_manager.get_character_from_cache("test_char")
        
        assert result == mock_characters[1]

    def test_get_character_from_cache_not_found(self, cache_manager):
        """Test get_character_from_cache when character is not found"""
        mock_characters = [Mock(**{"get.return_value": "other_char"})]
        mock_characters[0].get = Mock(side_effect=lambda key: "other_char" if key == "name" else None)
        cache_manager.load_cache_data = Mock(return_value=mock_characters)
        
        result = cache_manager.get_character_from_cache("missing_char")
        
        assert result is None

    def test_get_character_from_cache_no_data(self, cache_manager):
        """Test get_character_from_cache when no characters data"""
        cache_manager.load_cache_data = Mock(return_value=None)
        
        result = cache_manager.get_character_from_cache("test_char")
        
        assert result is None

    def test_update_character_in_cache_success(self, cache_manager):
        """Test update_character_in_cache successful update (lines 517-526)"""
        # Mock characters data with get method
        mock_character = Mock()
        mock_character.get = Mock(side_effect=lambda key: "test_char" if key == "name" else None)
        mock_character.update = Mock()
        mock_characters = [mock_character]
        
        cache_manager.load_cache_data = Mock(return_value=mock_characters)
        cache_manager.save_cache_data = Mock()
        
        result = cache_manager.update_character_in_cache("test_char", {"level": 5})
        
        assert result is True
        mock_character.update.assert_called_with({"level": 5})
        cache_manager.save_cache_data.assert_called_with("characters", mock_characters)

    def test_update_character_in_cache_not_found(self, cache_manager):
        """Test update_character_in_cache when character not found"""
        mock_character = Mock()
        mock_character.get = Mock(side_effect=lambda key: "other_char" if key == "name" else None)
        mock_characters = [mock_character]
        
        cache_manager.load_cache_data = Mock(return_value=mock_characters)
        
        result = cache_manager.update_character_in_cache("missing_char", {"level": 5})
        
        assert result is False

    def test_update_character_in_cache_no_data(self, cache_manager):
        """Test update_character_in_cache when no characters data"""
        cache_manager.load_cache_data = Mock(return_value=None)
        
        result = cache_manager.update_character_in_cache("test_char", {"level": 5})
        
        assert result is False

    def test_save_character_state_validation_failure(self, cache_manager):
        """Test save_character_state with validation failure (line 621)"""
        cache_manager.validate_character_state_data = Mock(return_value=False)
        
        with pytest.raises(ValueError, match="Invalid character state data"):
            cache_manager.save_character_state("test_char", {"invalid": "data"})

    @pytest.mark.asyncio
    async def test_get_game_data_comprehensive(self, cache_manager):
        """Test get_game_data method (lines 714-720)"""
        # Mock all the get methods
        mock_maps = [GameMap(name="test", skin="grass", x=0, y=0, content=None)]
        mock_monsters = [GameMonster(
            code="test", name="Test", level=1, hp=100,
            attack_fire=10, attack_earth=10, attack_water=10, attack_air=10,
            res_fire=5, res_earth=5, res_water=5, res_air=5,
            min_gold=1, max_gold=10, drops=[]
        )]
        mock_resources = [GameResource(
            code="test", name="Test", skill="mining", level=1, drops=[]
        )]
        mock_npcs = [GameNPC(
            code="test", name="Test", description="Test NPC", type="trader"
        )]
        mock_items = [GameItem(
            code="test", name="Test", level=1, type="misc", subtype="material",
            description="Test item", effects=[], craft=None, tradeable=True
        )]
        
        cache_manager.get_all_maps = AsyncMock(return_value=mock_maps)
        cache_manager.get_all_monsters = AsyncMock(return_value=mock_monsters)
        cache_manager.get_all_resources = AsyncMock(return_value=mock_resources)
        cache_manager.get_all_npcs = AsyncMock(return_value=mock_npcs)
        cache_manager.get_all_items = AsyncMock(return_value=mock_items)
        
        result = await cache_manager.get_game_data()
        
        assert isinstance(result, GameData)
        assert result.maps == mock_maps
        assert result.monsters == mock_monsters
        assert result.resources == mock_resources
        assert result.npcs == mock_npcs
        assert result.items == mock_items