"""
Tests for CacheManager
"""

import os
import shutil
import tempfile
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from src.game_data.cache_manager import CacheManager, CacheMetadata
from src.game_data.models import GameItem, GameMap, GameMonster, GameNPC, GameResource
from tests.fixtures.api_responses import GameDataFixtures


def create_test_game_items(count: int = 3) -> list[GameItem]:
    """Helper to create test GameItem instances"""
    return [
        GameItem(
            code=f"test_item_{i}",
            name=f"Test Item {i}",
            level=i + 1,
            type="weapon",
            subtype="sword",
            description=f"A test item {i}",
            effects=[],
            craft=None,
            tradeable=True
        )
        for i in range(count)
    ]


def create_test_game_monsters(count: int = 3) -> list[GameMonster]:
    """Helper to create test GameMonster instances"""
    return [
        GameMonster(
            code=f"test_monster_{i}",
            name=f"Test Monster {i}",
            level=i + 1,
            hp=100 + i * 10,
            attack_fire=10 + i,
            attack_earth=10 + i,
            attack_water=10 + i,
            attack_air=10 + i,
            res_fire=5 + i,
            res_earth=5 + i,
            res_water=5 + i,
            res_air=5 + i,
            min_gold=i + 1,
            max_gold=(i + 1) * 10,
            drops=[]
        )
        for i in range(count)
    ]


def create_test_game_maps(count: int = 3) -> list[GameMap]:
    """Helper to create test GameMap instances"""
    return [
        GameMap(
            name=f"test_map_{i}",
            skin=f"map_skin_{i}",
            x=i * 10,
            y=i * 10,
            content={"type": f"content_type_{i}", "code": f"content_code_{i}"}
        )
        for i in range(count)
    ]


def create_test_game_resources(count: int = 3) -> list[GameResource]:
    """Helper to create test GameResource instances"""
    return [
        GameResource(
            code=f"test_resource_{i}",
            name=f"Test Resource {i}",
            skill=["mining", "woodcutting", "fishing"][i % 3],
            level=i + 1,
            drops=[]
        )
        for i in range(count)
    ]


def create_test_game_npcs(count: int = 3) -> list[GameNPC]:
    """Helper to create test GameNPC instances"""
    return [
        GameNPC(
            code=f"test_npc_{i}",
            name=f"Test NPC {i}",
            description=f"A test NPC {i}",
            type="trader"
        )
        for i in range(count)
    ]


class TestCacheMetadata:
    """Test CacheMetadata functionality"""

    def test_is_stale_fresh_cache(self):
        """Test that fresh cache is not stale"""
        recent_time = datetime.now() - timedelta(hours=1)
        metadata = CacheMetadata(
            last_updated=recent_time,
            cache_version="1.0.0",
            data_sources={}
        )

        assert not metadata.is_stale(max_age_hours=24)

    def test_is_stale_old_cache(self):
        """Test that old cache is stale"""
        old_time = datetime.now() - timedelta(hours=25)
        metadata = CacheMetadata(
            last_updated=old_time,
            cache_version="1.0.0",
            data_sources={}
        )

        assert metadata.is_stale(max_age_hours=24)

    def test_is_stale_custom_age_threshold(self):
        """Test custom age threshold"""
        time_2_hours_ago = datetime.now() - timedelta(hours=2)
        metadata = CacheMetadata(
            last_updated=time_2_hours_ago,
            cache_version="1.0.0",
            data_sources={}
        )

        assert not metadata.is_stale(max_age_hours=3)
        assert metadata.is_stale(max_age_hours=1)


class TestCacheManager:
    """Test CacheManager functionality"""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_api_client(self):
        """Create mock API client"""
        client = Mock()
        client.get_all_items = AsyncMock(return_value=self._create_mock_items())
        client.get_all_monsters = AsyncMock(return_value=self._create_mock_monsters())
        client.get_all_maps = AsyncMock(return_value=self._create_mock_maps())
        client.get_all_resources = AsyncMock(return_value=self._create_mock_resources())
        client.get_all_npcs = AsyncMock(return_value=create_test_game_npcs(2))
        client.get_character = AsyncMock(return_value=self._create_mock_character())
        return client

    def _create_mock_items(self):
        """Create mock items with model_dump and to_dict methods"""
        items_data = GameDataFixtures.get_items_data()
        mock_items = []
        for item_data in items_data:
            mock_item = Mock()
            mock_item.model_dump = Mock(return_value=item_data)
            mock_item.to_dict = Mock(return_value=item_data)
            for key, value in item_data.items():
                setattr(mock_item, key, value)
            mock_items.append(mock_item)
        return mock_items

    def _create_mock_monsters(self):
        """Create mock monsters with model_dump and to_dict methods"""
        monsters_data = GameDataFixtures.get_monsters_data()
        mock_monsters = []
        for monster_data in monsters_data:
            mock_monster = Mock()
            mock_monster.model_dump = Mock(return_value=monster_data)
            mock_monster.to_dict = Mock(return_value=monster_data)
            for key, value in monster_data.items():
                setattr(mock_monster, key, value)
            mock_monsters.append(mock_monster)
        return mock_monsters

    def _create_mock_maps(self):
        """Create mock maps with model_dump and to_dict methods"""
        maps_data = GameDataFixtures.get_maps_data()
        mock_maps = []
        for map_data in maps_data:
            mock_map = Mock()
            mock_map.model_dump = Mock(return_value=map_data)
            mock_map.to_dict = Mock(return_value=map_data)
            for key, value in map_data.items():
                setattr(mock_map, key, value)
            mock_maps.append(mock_map)
        return mock_maps

    def _create_mock_resources(self):
        """Create mock resources with model_dump and to_dict methods"""
        resources_data = GameDataFixtures.get_resources_data()
        mock_resources = []
        for resource_data in resources_data:
            mock_resource = Mock()
            mock_resource.model_dump = Mock(return_value=resource_data)
            mock_resource.to_dict = Mock(return_value=resource_data)
            for key, value in resource_data.items():
                setattr(mock_resource, key, value)
            mock_resources.append(mock_resource)
        return mock_resources

    def _create_mock_npcs(self):
        """Create mock NPCs with model_dump and to_dict methods"""
        # Simple NPC data since GameDataFixtures doesn't have NPCs
        mock_npcs = []
        npc_info = [
            {"code": "merchant", "name": "Town Merchant", "description": "A friendly merchant"},
            {"code": "blacksmith", "name": "Town Blacksmith", "description": "A skilled blacksmith"}
        ]

        for info in npc_info:
            mock_npc = Mock()
            # Set up attributes for GameNPC.from_api_npc transformation
            mock_npc.code = info["code"]
            mock_npc.name = info["name"]
            mock_npc.description = info["description"]
            mock_npc.type_ = Mock()
            mock_npc.type_.value = "trader"
            mock_npcs.append(mock_npc)
        return mock_npcs

    def _create_mock_character(self):
        """Create mock character with model_dump and to_dict methods"""
        character_data = {
            "name": "test_character",
            "level": 10,
            "hp": 100,
            "x": 0,
            "y": 0
        }
        mock_character = Mock()
        mock_character.model_dump = Mock(return_value=character_data)
        mock_character.to_dict = Mock(return_value=character_data)
        for key, value in character_data.items():
            setattr(mock_character, key, value)
        return mock_character

    def test_cache_manager_initialization(self, mock_api_client, temp_cache_dir):
        """Test CacheManager initialization"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        assert cache_manager._api_client == mock_api_client
        assert cache_manager.cache_dir == temp_cache_dir
        assert cache_manager.metadata_file == f"{temp_cache_dir}/metadata.yaml"

    def test_get_cache_metadata_new_cache(self, mock_api_client, temp_cache_dir):
        """Test getting metadata for new cache"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)
        metadata = cache_manager.get_cache_metadata()

        assert isinstance(metadata, CacheMetadata)
        assert metadata.cache_version == "1.0.0"
        assert isinstance(metadata.data_sources, dict)
        assert len(metadata.data_sources) == 0

    def test_save_and_load_cache_data(self, mock_api_client, temp_cache_dir):
        """Test saving and loading cache data with internal Pydantic models"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Create test data using internal Pydantic models
        test_items = create_test_game_items(2)

        # Save data
        cache_manager.save_cache_data("items", test_items)

        # Verify cache file exists
        cache_file = f"{temp_cache_dir}/items.yaml"
        assert os.path.exists(cache_file)

        # Load and verify data - should get the Pydantic models
        loaded_data = cache_manager.load_cache_data("items")
        assert loaded_data == test_items
        assert all(isinstance(item, GameItem) for item in loaded_data)

    def test_save_cache_data_with_pydantic_objects(self, mock_api_client, temp_cache_dir):
        """Test saving cache data with Pydantic-like objects"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Create mock objects with model_dump method
        mock_objects = []
        for i in range(3):
            mock_obj = Mock()
            mock_obj.model_dump = Mock(return_value={"id": i, "name": f"Item {i}"})
            mock_obj.to_dict = Mock(return_value={"id": i, "name": f"Item {i}"})
            mock_objects.append(mock_obj)

        # Save data
        cache_manager.save_cache_data("mock_items", mock_objects)

        # Load and verify data
        loaded_data = cache_manager.load_cache_data("mock_items")
        expected_data = [{"id": i, "name": f"Item {i}"} for i in range(3)]
        assert loaded_data == expected_data

    def test_load_cache_data_nonexistent_file(self, mock_api_client, temp_cache_dir):
        """Test loading data from nonexistent cache file"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        loaded_data = cache_manager.load_cache_data("nonexistent")
        assert loaded_data is None

    @pytest.mark.asyncio
    async def test_get_all_items_with_fresh_cache(self, mock_api_client, temp_cache_dir):
        """Test getting items with valid cache"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Pre-populate cache with internal Pydantic models
        cached_items = create_test_game_items(1)
        cache_manager.save_cache_data("items", cached_items)
        cache_manager._update_metadata("items")

        # Get items - should return cached data
        items = await cache_manager.get_all_items()

        # Should return cached data, not call API
        # Note: cache returns Pydantic models, not dicts
        assert len(items) == 1
        assert isinstance(items[0], GameItem)
        assert items[0].code == 'test_item_0'
        assert items[0].name == 'Test Item 0'
        mock_api_client.get_all_items.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_all_items_force_refresh(self, mock_api_client, temp_cache_dir):
        """Test getting items with forced refresh"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Pre-populate cache with internal models
        cached_items = create_test_game_items(1)
        cache_manager.save_cache_data("items", cached_items)
        cache_manager._update_metadata("items")

        # Mock API client to return internal models (since API wrapper now transforms)
        fresh_items = create_test_game_items(2)
        mock_api_client.get_all_items.return_value = fresh_items

        # Get items with force refresh
        items = await cache_manager.get_all_items(force_refresh=True)

        # Should call API and return fresh data
        mock_api_client.get_all_items.assert_called_once()
        assert items == fresh_items

        # Verify data was updated in cache
        cached_data = cache_manager.load_cache_data("items")
        assert cached_data == fresh_items
        assert all(isinstance(item, GameItem) for item in cached_data)

    @pytest.mark.asyncio
    async def test_get_all_items_no_cache(self, mock_api_client, temp_cache_dir):
        """Test getting items when no cache exists"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Get items - should fetch from API
        await cache_manager.get_all_items()

        # Should call API
        mock_api_client.get_all_items.assert_called_once()
        # Should save to cache
        cached_data = cache_manager.load_cache_data("items")
        assert cached_data is not None
        assert len(cached_data) == len(GameDataFixtures.get_items_data())

    def test_is_cache_valid_fresh_cache(self, mock_api_client, temp_cache_dir):
        """Test cache validity for fresh cache"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Create cache and metadata
        cache_manager.save_cache_data("items", [])
        cache_manager._update_metadata("items")

        assert cache_manager.is_cache_valid("items")

    def test_is_cache_valid_no_metadata(self, mock_api_client, temp_cache_dir):
        """Test cache validity when no metadata exists"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        assert not cache_manager.is_cache_valid("items")

    def test_clear_cache_specific_type(self, mock_api_client, temp_cache_dir):
        """Test clearing specific cache type"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Create cache files
        cache_manager.save_cache_data("items", [])
        cache_manager.save_cache_data("monsters", [])

        # Clear only items cache
        cache_manager.clear_cache("items")

        # Items cache should be gone, monsters should remain
        assert not os.path.exists(f"{temp_cache_dir}/items.yaml")
        assert os.path.exists(f"{temp_cache_dir}/monsters.yaml")

    def test_clear_cache_all(self, mock_api_client, temp_cache_dir):
        """Test clearing all cache"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Create cache files and metadata
        cache_manager.save_cache_data("items", [])
        cache_manager.save_cache_data("monsters", [])
        cache_manager._update_metadata("items")

        # Clear all cache
        cache_manager.clear_cache()

        # All cache files should be gone
        assert not os.path.exists(f"{temp_cache_dir}/items.yaml")
        assert not os.path.exists(f"{temp_cache_dir}/monsters.yaml")
        assert not os.path.exists(f"{temp_cache_dir}/metadata.yaml")

    @pytest.mark.asyncio
    async def test_refresh_all_cache(self, mock_api_client, temp_cache_dir):
        """Test refreshing all cache data"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Should succeed
        result = await cache_manager.refresh_all_cache()
        assert result is True

        # Verify all API methods were called
        mock_api_client.get_all_items.assert_called_once()
        mock_api_client.get_all_monsters.assert_called_once()
        mock_api_client.get_all_maps.assert_called_once()
        mock_api_client.get_all_resources.assert_called_once()
        mock_api_client.get_all_npcs.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_all_cache_failure(self, mock_api_client, temp_cache_dir):
        """Test refresh_all_cache when API fails"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Make one API call fail
        mock_api_client.get_all_items.side_effect = Exception("API Error")

        result = await cache_manager.refresh_all_cache()
        assert result is False

    def test_validate_cached_data_valid(self, mock_api_client, temp_cache_dir):
        """Test validation of valid cached data"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Test valid items data
        valid_items = [
            {"code": "copper_ore", "name": "Copper Ore"},
            {"code": "iron_sword", "name": "Iron Sword"}
        ]
        assert cache_manager.validate_cached_data("items", valid_items)

        # Test valid monsters data
        valid_monsters = [
            {"code": "chicken", "name": "Chicken"},
            {"code": "goblin", "name": "Goblin"}
        ]
        assert cache_manager.validate_cached_data("monsters", valid_monsters)

    def test_validate_cached_data_invalid(self, mock_api_client, temp_cache_dir):
        """Test validation of invalid cached data"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Missing required fields
        invalid_items = [{"code": "missing_name"}]
        assert not cache_manager.validate_cached_data("items", invalid_items)

        # None data
        assert not cache_manager.validate_cached_data("items", None)

        # Not a list
        assert not cache_manager.validate_cached_data("items", {"not": "list"})

    def test_validate_character_state_data_valid(self, mock_api_client, temp_cache_dir):
        """Test validation of valid character state data"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        valid_state = {
            "character_level": 10,
            "hp_current": 80,
            "current_x": 15,
            "current_y": 20,
            "cooldown_ready": True
        }
        assert cache_manager.validate_character_state_data(valid_state)

    def test_validate_character_state_data_invalid(self, mock_api_client, temp_cache_dir):
        """Test validation of invalid character state data"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Missing required fields
        invalid_state = {"character_level": 5}
        assert not cache_manager.validate_character_state_data(invalid_state)

        # Invalid types
        invalid_types = {
            "character_level": "not_number",
            "hp_current": 80,
            "current_x": 15,
            "current_y": 20
        }
        assert not cache_manager.validate_character_state_data(invalid_types)

        # Not a dict
        assert not cache_manager.validate_character_state_data("not_dict")

    @pytest.mark.asyncio
    async def test_cache_character_data(self, mock_api_client, temp_cache_dir):
        """Test caching character data"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        character_name = "test_character"
        await cache_manager.cache_character_data(character_name)

        # Verify API was called
        mock_api_client.get_character.assert_called_once_with(character_name)

        # Verify cache file was created
        cache_file = f"{temp_cache_dir}/characters/{character_name}/data.yaml"
        assert os.path.exists(cache_file)

    def test_save_and_load_character_state(self, mock_api_client, temp_cache_dir):
        """Test saving and loading character state"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        character_name = "test_character"
        character_state = {
            "character_level": 10,
            "hp_current": 80,
            "current_x": 15,
            "current_y": 20,
            "cooldown_ready": True
        }

        # Save state
        cache_manager.save_character_state(character_name, character_state)

        # Load and verify
        loaded_state = cache_manager.load_character_state(character_name)
        assert loaded_state == character_state

    def test_load_character_state_nonexistent(self, mock_api_client, temp_cache_dir):
        """Test loading nonexistent character state"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        loaded_state = cache_manager.load_character_state("nonexistent")
        assert loaded_state is None

    def test_clear_character_cache(self, mock_api_client, temp_cache_dir):
        """Test clearing character cache"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        character_name = "test_character"
        character_state = {
            "character_level": 10,
            "hp_current": 80,
            "current_x": 15,
            "current_y": 20,
            "cooldown_ready": True
        }

        # Create character cache
        cache_manager.save_character_state(character_name, character_state)
        assert cache_manager.load_character_state(character_name) is not None

        # Clear it
        cache_manager.clear_character_cache(character_name)
        assert cache_manager.load_character_state(character_name) is None

    def test_get_cache_statistics(self, mock_api_client, temp_cache_dir):
        """Test getting cache statistics"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Create some cache files with internal models
        test_items = create_test_game_items(1)
        test_monsters = create_test_game_monsters(1)
        cache_manager.save_cache_data("items", test_items)
        cache_manager.save_cache_data("monsters", test_monsters)

        stats = cache_manager.get_cache_statistics()

        assert isinstance(stats, dict)
        assert "total_size" in stats
        assert "data_types" in stats
        assert isinstance(stats["data_types"], dict)

        # Check individual data type stats
        assert "items" in stats["data_types"]
        assert "monsters" in stats["data_types"]
        assert stats["data_types"]["items"]["exists"] is True
        assert stats["data_types"]["monsters"]["exists"] is True

    @pytest.mark.asyncio
    async def test_get_all_monsters_no_cache(self, mock_api_client, temp_cache_dir):
        """Test getting monsters when no cache exists"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        await cache_manager.get_all_monsters()

        mock_api_client.get_all_monsters.assert_called_once()
        cached_data = cache_manager.load_cache_data("monsters")
        assert cached_data is not None
        assert len(cached_data) == len(GameDataFixtures.get_monsters_data())

    @pytest.mark.asyncio
    async def test_get_all_monsters_with_cache(self, mock_api_client, temp_cache_dir):
        """Test getting monsters with valid cache"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        cached_monsters = create_test_game_monsters(1)
        cache_manager.save_cache_data("monsters", cached_monsters)
        cache_manager._update_metadata("monsters")

        monsters = await cache_manager.get_all_monsters()

        # Should return cached data - check key fields
        assert len(monsters) == 1
        assert isinstance(monsters[0], GameMonster)
        assert monsters[0].code == 'test_monster_0'
        assert monsters[0].name == 'Test Monster 0'
        mock_api_client.get_all_monsters.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_all_maps_no_cache(self, mock_api_client, temp_cache_dir):
        """Test getting maps when no cache exists"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        await cache_manager.get_all_maps()

        mock_api_client.get_all_maps.assert_called_once()
        cached_data = cache_manager.load_cache_data("maps")
        assert cached_data is not None
        assert len(cached_data) == len(GameDataFixtures.get_maps_data())

    @pytest.mark.asyncio
    async def test_get_all_maps_with_cache(self, mock_api_client, temp_cache_dir):
        """Test getting maps with valid cache"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        cached_maps = create_test_game_maps(1)
        cache_manager.save_cache_data("maps", cached_maps)
        cache_manager._update_metadata("maps")

        maps = await cache_manager.get_all_maps()

        # Should return cached data - check key fields
        assert len(maps) == 1
        assert isinstance(maps[0], GameMap)
        assert maps[0].name == 'test_map_0'
        assert maps[0].x == 0
        mock_api_client.get_all_maps.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_all_resources_no_cache(self, mock_api_client, temp_cache_dir):
        """Test getting resources when no cache exists"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        await cache_manager.get_all_resources()

        mock_api_client.get_all_resources.assert_called_once()
        cached_data = cache_manager.load_cache_data("resources")
        assert cached_data is not None
        assert len(cached_data) == len(GameDataFixtures.get_resources_data())

    @pytest.mark.asyncio
    async def test_get_all_resources_with_cache(self, mock_api_client, temp_cache_dir):
        """Test getting resources with valid cache"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        cached_resources = create_test_game_resources(1)
        cache_manager.save_cache_data("resources", cached_resources)
        cache_manager._update_metadata("resources")

        resources = await cache_manager.get_all_resources()

        # Should return cached data - check key fields
        assert len(resources) == 1
        assert isinstance(resources[0], GameResource)
        assert resources[0].code == 'test_resource_0'
        assert resources[0].name == 'Test Resource 0'
        mock_api_client.get_all_resources.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_all_npcs_no_cache(self, mock_api_client, temp_cache_dir):
        """Test getting NPCs when no cache exists"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        await cache_manager.get_all_npcs()

        mock_api_client.get_all_npcs.assert_called_once()
        cached_data = cache_manager.load_cache_data("npcs")
        assert cached_data is not None
        assert len(cached_data) == 2  # We create 2 NPCs in _create_mock_npcs

    @pytest.mark.asyncio
    async def test_get_all_npcs_with_cache(self, mock_api_client, temp_cache_dir):
        """Test getting NPCs with valid cache"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        cached_npcs = create_test_game_npcs(1)
        cache_manager.save_cache_data("npcs", cached_npcs)
        cache_manager._update_metadata("npcs")

        npcs = await cache_manager.get_all_npcs()

        # Should return cached data - check key fields
        assert len(npcs) == 1
        assert isinstance(npcs[0], GameNPC)
        assert npcs[0].code == 'test_npc_0'
        assert npcs[0].name == 'Test NPC 0'
        mock_api_client.get_all_npcs.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_game_data_invalid_type(self, mock_api_client, temp_cache_dir):
        """Test cache_game_data with invalid type"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        with pytest.raises(ValueError, match="Unknown game data type"):
            await cache_manager.cache_game_data("invalid_type")

    @pytest.mark.asyncio
    async def test_cache_game_data_items(self, mock_api_client, temp_cache_dir):
        """Test cache_game_data for items"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        await cache_manager.cache_game_data("items")

        mock_api_client.get_all_items.assert_called_once()
        cached_data = cache_manager.load_cache_data("items")
        assert cached_data is not None

    @pytest.mark.asyncio
    async def test_cache_game_data_monsters(self, mock_api_client, temp_cache_dir):
        """Test cache_game_data for monsters"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        await cache_manager.cache_game_data("monsters")

        mock_api_client.get_all_monsters.assert_called_once()
        cached_data = cache_manager.load_cache_data("monsters")
        assert cached_data is not None

    @pytest.mark.asyncio
    async def test_cache_game_data_maps(self, mock_api_client, temp_cache_dir):
        """Test cache_game_data for maps"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        await cache_manager.cache_game_data("maps")

        mock_api_client.get_all_maps.assert_called_once()
        cached_data = cache_manager.load_cache_data("maps")
        assert cached_data is not None

    @pytest.mark.asyncio
    async def test_cache_game_data_resources(self, mock_api_client, temp_cache_dir):
        """Test cache_game_data for resources"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        await cache_manager.cache_game_data("resources")

        mock_api_client.get_all_resources.assert_called_once()
        cached_data = cache_manager.load_cache_data("resources")
        assert cached_data is not None

    @pytest.mark.asyncio
    async def test_cache_game_data_npcs(self, mock_api_client, temp_cache_dir):
        """Test cache_game_data for npcs"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        await cache_manager.cache_game_data("npcs")

        mock_api_client.get_all_npcs.assert_called_once()
        cached_data = cache_manager.load_cache_data("npcs")
        assert cached_data is not None

    def test_get_cached_game_data_exists(self, mock_api_client, temp_cache_dir):
        """Test get_cached_game_data when data exists"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        test_data = create_test_game_items(1)
        cache_manager.save_cache_data("items", test_data)

        result = cache_manager.get_cached_game_data("items")
        # Result should be Pydantic models, not serialized dictionaries
        assert result == test_data
        assert isinstance(result[0], GameItem)

    def test_get_cached_game_data_not_exists(self, mock_api_client, temp_cache_dir):
        """Test get_cached_game_data when data doesn't exist"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        result = cache_manager.get_cached_game_data("nonexistent")
        assert result is None

    def test_is_cache_fresh_true(self, mock_api_client, temp_cache_dir):
        """Test is_cache_fresh returns True for fresh cache"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        cache_manager.save_cache_data("items", [])
        cache_manager._update_metadata("items")

        assert cache_manager.is_cache_fresh("items")

    def test_is_cache_fresh_false(self, mock_api_client, temp_cache_dir):
        """Test is_cache_fresh returns False for missing cache"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        assert not cache_manager.is_cache_fresh("nonexistent")

    @pytest.mark.asyncio
    async def test_refresh_cache_with_types(self, mock_api_client, temp_cache_dir):
        """Test refresh_cache with specific data types"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        await cache_manager.refresh_cache(data_types=["items", "monsters"], force=True)

        mock_api_client.get_all_items.assert_called_once()
        mock_api_client.get_all_monsters.assert_called_once()
        mock_api_client.get_all_maps.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_cache_skip_fresh(self, mock_api_client, temp_cache_dir):
        """Test refresh_cache skips fresh cache when force=False"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Make cache fresh
        cache_manager.save_cache_data("items", [])
        cache_manager._update_metadata("items")

        await cache_manager.refresh_cache(data_types=["items"], force=False)

        # Should not refresh fresh cache
        mock_api_client.get_all_items.assert_not_called()

    def test_validate_cached_data_empty_list(self, mock_api_client, temp_cache_dir):
        """Test validation of empty list is valid"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        assert cache_manager.validate_cached_data("items", [])

    def test_validate_cached_data_unknown_type(self, mock_api_client, temp_cache_dir):
        """Test validation of unknown data type"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        assert not cache_manager.validate_cached_data("unknown_type", [{"code": "test"}])

    def test_validate_cached_data_not_dict_items(self, mock_api_client, temp_cache_dir):
        """Test validation fails for non-dict items in list"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        invalid_data = ["not_a_dict", {"code": "valid"}]
        assert not cache_manager.validate_cached_data("items", invalid_data)

    def test_validate_character_state_negative_values(self, mock_api_client, temp_cache_dir):
        """Test validation fails for negative values"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        invalid_state = {
            "character_level": -1,
            "hp_current": 80,
            "current_x": 15,
            "current_y": 20
        }
        assert not cache_manager.validate_character_state_data(invalid_state)

    def test_validate_character_state_invalid_cooldown_ready(self, mock_api_client, temp_cache_dir):
        """Test validation fails for invalid cooldown_ready type"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        invalid_state = {
            "character_level": 10,
            "hp_current": 80,
            "current_x": 15,
            "current_y": 20,
            "cooldown_ready": "not_boolean"
        }
        assert not cache_manager.validate_character_state_data(invalid_state)

    def test_save_cache_data_with_dict_method(self, mock_api_client, temp_cache_dir):
        """Test that objects with dict() method but no model_dump() are rejected"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Create custom class with dict method but no model_dump
        class DictObject:
            def __init__(self, id_val, name):
                self.id = id_val
                self.name = name

            def dict(self):
                return {"id": self.id, "name": self.name}

        objects_with_dict = [
            DictObject(1, "Item 1"),
            DictObject(2, "Item 2"),
            DictObject(3, "Item 3")
        ]

        # Should raise ValueError due to boundary enforcement
        with pytest.raises(ValueError, match="Cache data must be internal Pydantic models"):
            cache_manager.save_cache_data("dict_items", objects_with_dict)

    def test_save_cache_data_with_plain_objects(self, mock_api_client, temp_cache_dir):
        """Test that plain dictionaries are rejected by boundary enforcement"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Plain dictionaries (no special methods)
        plain_objects = [
            {"id": 1, "name": "Plain Item 1"},
            {"id": 2, "name": "Plain Item 2"}
        ]

        # Should raise ValueError due to boundary enforcement
        with pytest.raises(ValueError, match="Cache data must be internal Pydantic models"):
            cache_manager.save_cache_data("plain_items", plain_objects)

    def test_load_cache_data_malformed_yaml(self, mock_api_client, temp_cache_dir):
        """Test loading cache data handles YAML errors gracefully"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Create a malformed YAML file
        cache_file = f"{temp_cache_dir}/malformed.yaml"
        os.makedirs(temp_cache_dir, exist_ok=True)
        with open(cache_file, 'w') as f:
            f.write("data: [\n  invalid yaml structure")

        # Should return None for malformed YAML
        loaded_data = cache_manager.load_cache_data("malformed")
        assert loaded_data is None

    def test_is_cache_valid_stale_cache(self, mock_api_client, temp_cache_dir):
        """Test cache validity for stale cache"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Create cache with old metadata
        cache_manager.save_cache_data("items", [])

        # Manually set old timestamp in metadata
        from datetime import datetime, timedelta
        old_metadata = CacheMetadata(
            last_updated=datetime.now() - timedelta(hours=25),
            cache_version="1.0.0",
            data_sources={"items": f"{temp_cache_dir}/items.yaml"}
        )

        # Mock get_cache_metadata to return old metadata
        cache_manager.get_cache_metadata = Mock(return_value=old_metadata)

        assert not cache_manager.is_cache_valid("items")

    def test_clear_cache_nonexistent_files(self, mock_api_client, temp_cache_dir):
        """Test clearing cache when files don't exist"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Should not raise error when clearing nonexistent cache
        cache_manager.clear_cache("nonexistent")
        cache_manager.clear_cache()  # Clear all when no files exist

    def test_get_cache_metadata_with_existing_metadata(self, mock_api_client, temp_cache_dir):
        """Test getting metadata when metadata file exists"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Create initial metadata
        cache_manager._update_metadata("items")

        # Get metadata - should load from file
        metadata = cache_manager.get_cache_metadata()

        assert isinstance(metadata, CacheMetadata)
        assert "items" in metadata.data_sources

    def test_get_cache_metadata_corrupted_file(self, mock_api_client, temp_cache_dir):
        """Test getting metadata when metadata file is corrupted"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Create corrupted metadata file
        os.makedirs(temp_cache_dir, exist_ok=True)
        with open(cache_manager.metadata_file, 'w') as f:
            f.write("corrupted yaml: [\n  invalid")

        # Should return default metadata
        metadata = cache_manager.get_cache_metadata()
        assert isinstance(metadata, CacheMetadata)
        assert metadata.cache_version == "1.0.0"
        assert len(metadata.data_sources) == 0

    def test_clear_character_cache_nonexistent(self, mock_api_client, temp_cache_dir):
        """Test clearing character cache when it doesn't exist"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Should not raise error
        cache_manager.clear_character_cache("nonexistent_character")

    def test_private_helper_methods(self, mock_api_client, temp_cache_dir):
        """Test private helper methods"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Test _get_cache_timestamp
        test_file = f"{temp_cache_dir}/test_timestamp.yaml"
        cache_manager.save_cache_data("test_timestamp", [])

        timestamp = cache_manager._get_cache_timestamp(test_file)
        assert timestamp is not None
        assert isinstance(timestamp, datetime)

        # Test _get_cache_timestamp for nonexistent file
        nonexistent_timestamp = cache_manager._get_cache_timestamp("nonexistent.yaml")
        assert nonexistent_timestamp is None

        # Test _get_cache_size
        size = cache_manager._get_cache_size(test_file)
        assert size > 0

        # Test _get_cache_size for nonexistent file
        nonexistent_size = cache_manager._get_cache_size("nonexistent.yaml")
        assert nonexistent_size == 0

    def test_delete_cache_file_and_directory(self, mock_api_client, temp_cache_dir):
        """Test _delete_cache_file and _delete_cache_directory methods"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Create test file and directory
        test_file = f"{temp_cache_dir}/test_delete.yaml"
        test_dir = f"{temp_cache_dir}/test_directory"

        cache_manager.save_cache_data("test_delete", [])
        os.makedirs(test_dir, exist_ok=True)

        # Test deleting file
        assert os.path.exists(test_file)
        cache_manager._delete_cache_file(test_file)
        assert not os.path.exists(test_file)

        # Test deleting directory
        assert os.path.exists(test_dir)
        cache_manager._delete_cache_directory(test_dir)
        assert not os.path.exists(test_dir)

        # Test deleting nonexistent file/directory (should not raise error)
        cache_manager._delete_cache_file("nonexistent.yaml")
        cache_manager._delete_cache_directory("nonexistent_dir")

    def test_is_cache_valid_exception_handling(self, mock_api_client, temp_cache_dir):
        """Test is_cache_valid exception handling"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Mock get_cache_metadata to raise exception
        cache_manager.get_cache_metadata = Mock(side_effect=Exception("Metadata error"))

        # Should return False when exception occurs
        result = cache_manager.is_cache_valid("items")
        assert result is False

    def test_load_character_state_exception_handling(self, mock_api_client, temp_cache_dir):
        """Test load_character_state exception handling"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Create a character state file that will cause YAML loading to fail
        character_name = "exception_character"
        cache_dir = f"{temp_cache_dir}/characters/{character_name}"
        os.makedirs(cache_dir, exist_ok=True)

        # Write invalid YAML that will cause an exception during loading
        cache_file = f"{cache_dir}/state.yaml"
        with open(cache_file, 'w') as f:
            f.write("invalid: yaml: structure: [\n  unclosed")

        # Should return None when exception occurs
        result = cache_manager.load_character_state(character_name)
        assert result is None

    def test_get_cache_metadata_yaml_without_data_key(self, mock_api_client, temp_cache_dir):
        """Test get_cache_metadata when YAML exists but doesn't have 'data' key"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Create metadata file without 'data' key
        os.makedirs(temp_cache_dir, exist_ok=True)
        with open(cache_manager.metadata_file, 'w') as f:
            f.write("some_other_key: some_value\n")

        # Should return default metadata
        metadata = cache_manager.get_cache_metadata()
        assert isinstance(metadata, CacheMetadata)
        assert metadata.cache_version == "1.0.0"
        assert len(metadata.data_sources) == 0

    def test_load_cache_data_yaml_without_data_key(self, mock_api_client, temp_cache_dir):
        """Test load_cache_data when YAML exists but doesn't have 'data' key"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Create cache file without 'data' key
        cache_file = f"{temp_cache_dir}/no_data_key.yaml"
        os.makedirs(temp_cache_dir, exist_ok=True)
        with open(cache_file, 'w') as f:
            f.write("some_other_key: some_value\n")

        # Should return None
        result = cache_manager.load_cache_data("no_data_key")
        assert result is None

    def test_load_character_state_yaml_without_data_key(self, mock_api_client, temp_cache_dir):
        """Test load_character_state when YAML exists but doesn't have 'data' key"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        character_name = "no_data_character"
        cache_dir = f"{temp_cache_dir}/characters/{character_name}"
        os.makedirs(cache_dir, exist_ok=True)

        # Create state file without 'data' key
        cache_file = f"{cache_dir}/state.yaml"
        with open(cache_file, 'w') as f:
            f.write("some_other_key: some_value\n")

        # Should return None
        result = cache_manager.load_character_state(character_name)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_npcs_missing_method(self, mock_api_client, temp_cache_dir):
        """Test get_all_npcs when API client doesn't have get_all_npcs method"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Remove the get_all_npcs method to simulate missing method
        delattr(mock_api_client, 'get_all_npcs')

        # Should raise AttributeError
        with pytest.raises(AttributeError):
            await cache_manager.get_all_npcs()

    @pytest.mark.asyncio
    async def test_refresh_cache_default_data_types(self, mock_api_client, temp_cache_dir):
        """Test refresh_cache with default data types (None parameter)"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Call refresh_cache with None data_types
        await cache_manager.refresh_cache(data_types=None, force=True)

        # Should call all five data type methods
        mock_api_client.get_all_items.assert_called_once()
        mock_api_client.get_all_monsters.assert_called_once()
        mock_api_client.get_all_maps.assert_called_once()
        mock_api_client.get_all_resources.assert_called_once()
        mock_api_client.get_all_npcs.assert_called_once()

    def test_load_yaml_data_exception_handling(self, mock_api_client, temp_cache_dir):
        """Test _load_yaml_data exception handling"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Create a malformed YAML file
        bad_file = f"{temp_cache_dir}/bad_yaml.yaml"
        os.makedirs(temp_cache_dir, exist_ok=True)
        with open(bad_file, 'w') as f:
            f.write("invalid: yaml: structure: [\n  unclosed")

        # Should return None when exception occurs
        result = cache_manager._load_yaml_data(bad_file)
        assert result is None

    def test_load_yaml_data_no_data_key(self, mock_api_client, temp_cache_dir):
        """Test _load_yaml_data when YAML has no 'data' key"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Create YAML file without 'data' key
        no_data_file = f"{temp_cache_dir}/no_data.yaml"
        os.makedirs(temp_cache_dir, exist_ok=True)
        with open(no_data_file, 'w') as f:
            f.write("other_key: other_value\n")

        # Should return None
        result = cache_manager._load_yaml_data(no_data_file)
        assert result is None

    def test_load_yaml_data_empty_data(self, mock_api_client, temp_cache_dir):
        """Test _load_yaml_data when YAML data is None/empty"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Create empty YAML file
        empty_file = f"{temp_cache_dir}/empty.yaml"
        os.makedirs(temp_cache_dir, exist_ok=True)
        with open(empty_file, 'w') as f:
            f.write("")  # Empty file

        # Should return None
        result = cache_manager._load_yaml_data(empty_file)
        assert result is None

    def test_load_yaml_data_successful(self, mock_api_client, temp_cache_dir):
        """Test _load_yaml_data successful loading"""
        cache_manager = CacheManager(mock_api_client, temp_cache_dir)

        # Create valid YAML file with data using internal models
        test_data = create_test_game_items(1)
        cache_manager.save_cache_data("test_yaml", test_data)

        # Load using _load_yaml_data directly
        yaml_file = f"{temp_cache_dir}/test_yaml.yaml"
        result = cache_manager._load_yaml_data(yaml_file)
        expected_data = [item.model_dump(mode='json') for item in test_data]
        assert result == expected_data
