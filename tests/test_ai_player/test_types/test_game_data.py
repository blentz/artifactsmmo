"""
Tests for GameData type system

This module tests the GameData type that provides type-safe access to cached game data
used throughout the enhanced goal system.
"""

from unittest.mock import Mock

import pytest

from src.ai_player.types.game_data import GameData
from src.game_data.models import GameItem, GameMap, GameMonster, GameNPC, GameResource


class TestGameData:
    """Test GameData model functionality."""

    def test_empty_game_data_creation(self):
        """Test creating empty GameData instance."""
        game_data = GameData()

        assert game_data.monsters == []
        assert game_data.items == []
        assert game_data.resources == []
        assert game_data.maps == []
        assert game_data.npcs == []

    def test_game_data_with_data(self):
        """Test creating GameData with actual data."""
        # Create mock data
        mock_monster = Mock(spec=GameMonster)
        mock_item = Mock(spec=GameItem)
        mock_resource = Mock(spec=GameResource)
        mock_map = Mock(spec=GameMap)
        mock_npc = Mock(spec=GameNPC)

        game_data = GameData(
            monsters=[mock_monster],
            items=[mock_item],
            resources=[mock_resource],
            maps=[mock_map],
            npcs=[mock_npc]
        )

        assert len(game_data.monsters) == 1
        assert len(game_data.items) == 1
        assert len(game_data.resources) == 1
        assert len(game_data.maps) == 1
        assert len(game_data.npcs) == 1

    def test_is_empty_functionality(self):
        """Test is_empty() method."""
        empty_data = GameData()
        assert empty_data.is_empty()

        # Add one item
        mock_item = Mock(spec=GameItem)
        non_empty_data = GameData(items=[mock_item])
        assert not non_empty_data.is_empty()

    def test_length_calculation(self):
        """Test __len__() method."""
        empty_data = GameData()
        assert len(empty_data) == 0

        # Create data with multiple items
        mock_monster = Mock(spec=GameMonster)
        mock_item = Mock(spec=GameItem)
        mock_resource = Mock(spec=GameResource)

        game_data = GameData(
            monsters=[mock_monster, mock_monster],
            items=[mock_item],
            resources=[mock_resource, mock_resource, mock_resource]
        )

        assert len(game_data) == 6  # 2 + 1 + 3

    def test_validate_required_data_success(self):
        """Test validate_required_data() with valid data."""
        mock_monster = Mock(spec=GameMonster)
        mock_item = Mock(spec=GameItem)
        mock_resource = Mock(spec=GameResource)
        mock_map = Mock(spec=GameMap)

        game_data = GameData(
            monsters=[mock_monster],
            items=[mock_item],
            resources=[mock_resource],
            maps=[mock_map]
        )

        # Should not raise exception
        game_data.validate_required_data()

    def test_validate_required_data_missing_monsters(self):
        """Test validate_required_data() with missing monsters."""
        mock_item = Mock(spec=GameItem)
        mock_resource = Mock(spec=GameResource)
        mock_map = Mock(spec=GameMap)

        game_data = GameData(
            items=[mock_item],
            resources=[mock_resource],
            maps=[mock_map]
        )

        with pytest.raises(ValueError, match="Monster data is required but not cached"):
            game_data.validate_required_data()

    def test_validate_required_data_missing_items(self):
        """Test validate_required_data() with missing items."""
        mock_monster = Mock(spec=GameMonster)
        mock_resource = Mock(spec=GameResource)
        mock_map = Mock(spec=GameMap)

        game_data = GameData(
            monsters=[mock_monster],
            resources=[mock_resource],
            maps=[mock_map]
        )

        with pytest.raises(ValueError, match="Item data is required but not cached"):
            game_data.validate_required_data()

    def test_validate_required_data_missing_resources(self):
        """Test validate_required_data() with missing resources."""
        mock_monster = Mock(spec=GameMonster)
        mock_item = Mock(spec=GameItem)
        mock_map = Mock(spec=GameMap)

        game_data = GameData(
            monsters=[mock_monster],
            items=[mock_item],
            maps=[mock_map]
        )

        with pytest.raises(ValueError, match="Resource data is required but not cached"):
            game_data.validate_required_data()

    def test_validate_required_data_missing_maps(self):
        """Test validate_required_data() with missing maps."""
        mock_monster = Mock(spec=GameMonster)
        mock_item = Mock(spec=GameItem)
        mock_resource = Mock(spec=GameResource)

        game_data = GameData(
            monsters=[mock_monster],
            items=[mock_item],
            resources=[mock_resource]
        )

        with pytest.raises(ValueError, match="Map data is required but not cached"):
            game_data.validate_required_data()

    def test_pydantic_validation(self):
        """Test that Pydantic validation works correctly."""
        # Test that invalid data types are rejected
        with pytest.raises(Exception):  # Pydantic validation error
            GameData(monsters="invalid")

        with pytest.raises(Exception):  # Pydantic validation error
            GameData(items=123)
