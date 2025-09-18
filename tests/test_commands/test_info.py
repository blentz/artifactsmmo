"""Tests for info commands."""

from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from artifactsmmo_cli.commands.info import (
    _calculate_difficulty_rating,
    _calculate_success_probability,
    _classify_npc,
    _find_resource_locations,
    _format_combat_analysis,
    _get_character_data,
    _get_fallback_npc,
    _get_monster_drops,
    _get_resource_data,
    _get_resource_info_for_content,
    _matches_resource_criteria,
    app,
)


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_client_manager():
    """Mock the ClientManager."""
    with patch("artifactsmmo_cli.commands.info.ClientManager") as mock:
        mock_instance = Mock()
        mock.return_value = mock_instance
        mock_instance.client = Mock()
        yield mock_instance


@pytest.fixture
def mock_api_response():
    """Mock API response."""
    mock_response = Mock()
    mock_response.status_code = 200
    return mock_response


class TestInfoCommands:
    """Test info command functionality."""

    def test_items_specific_item(self, runner, mock_client_manager, mock_api_response):
        """Test items command for specific item."""
        with patch("artifactsmmo_api_client.api.items.get_item_items_code_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            mock_item = Mock()
            mock_item.code = "iron_ore"
            mock_item.name = "Iron Ore"
            mock_item.type_ = "resource"
            mock_item.subtype = "ore"
            mock_item.level = 1
            mock_item.description = "Basic iron ore"
            mock_item.craft = None

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_item)

                result = runner.invoke(app, ["items", "--item-code", "iron_ore"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_items_list(self, runner, mock_client_manager, mock_api_response):
        """Test items command for listing items."""
        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            mock_item = Mock()
            mock_item.code = "iron_ore"
            mock_item.name = "Iron Ore"
            mock_item.type_ = "resource"
            mock_item.level = 1
            mock_item.description = "Basic iron ore"

            mock_data = Mock()
            mock_data.data = [mock_item]

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["items"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_monsters_specific_monster(self, runner, mock_client_manager, mock_api_response):
        """Test monsters command for specific monster."""
        with patch("artifactsmmo_api_client.api.monsters.get_monster_monsters_code_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            mock_monster = Mock()
            mock_monster.code = "goblin"
            mock_monster.name = "Goblin"
            mock_monster.level = 5
            mock_monster.hp = 100
            mock_monster.attack_fire = 10
            mock_monster.attack_earth = 0
            mock_monster.attack_water = 0
            mock_monster.attack_air = 0
            mock_monster.res_fire = 5
            mock_monster.res_earth = 0
            mock_monster.res_water = 0
            mock_monster.res_air = 0
            mock_monster.drops = []

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_monster)

                result = runner.invoke(app, ["monsters", "--monster-code", "goblin"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_monsters_list(self, runner, mock_client_manager, mock_api_response):
        """Test monsters command for listing monsters."""
        with patch("artifactsmmo_api_client.api.monsters.get_all_monsters_monsters_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            mock_monster = Mock()
            mock_monster.code = "goblin"
            mock_monster.name = "Goblin"
            mock_monster.level = 5
            mock_monster.hp = 100
            mock_monster.attack_fire = 10
            mock_monster.attack_earth = 0
            mock_monster.attack_water = 0
            mock_monster.attack_air = 0
            mock_monster.drops = []

            mock_data = Mock()
            mock_data.data = [mock_monster]

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["monsters"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_monsters_level_exact_match(self, runner, mock_client_manager, mock_api_response):
        """Test monsters command with exact level filtering (backward compatibility)."""
        with patch("artifactsmmo_api_client.api.monsters.get_all_monsters_monsters_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            mock_monster = Mock()
            mock_monster.code = "goblin"
            mock_monster.name = "Goblin"
            mock_monster.level = 5
            mock_monster.hp = 100
            mock_monster.attack_fire = 10
            mock_monster.attack_earth = 0
            mock_monster.attack_water = 0
            mock_monster.attack_air = 0

            mock_data = Mock()
            mock_data.data = [mock_monster]

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["monsters", "--level", "5"])

                assert result.exit_code == 0
                # Should call API with both min_level and max_level set to 5 for exact match
                mock_api.assert_called_once()
                call_args = mock_api.call_args
                assert call_args.kwargs["min_level"] == 5
                assert call_args.kwargs["max_level"] == 5
                assert call_args.kwargs["page"] == 1
                assert call_args.kwargs["size"] == 50

    def test_monsters_min_level_only(self, runner, mock_client_manager, mock_api_response):
        """Test monsters command with minimum level filtering only."""
        with patch("artifactsmmo_api_client.api.monsters.get_all_monsters_monsters_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            mock_data = Mock()
            mock_data.data = []

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["monsters", "--min-level", "10"])

                assert result.exit_code == 0
                mock_api.assert_called_once()
                call_args = mock_api.call_args
                assert call_args.kwargs["min_level"] == 10
                assert call_args.kwargs["max_level"] is None
                assert call_args.kwargs["page"] == 1
                assert call_args.kwargs["size"] == 50

    def test_monsters_max_level_only(self, runner, mock_client_manager, mock_api_response):
        """Test monsters command with maximum level filtering only."""
        with patch("artifactsmmo_api_client.api.monsters.get_all_monsters_monsters_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            mock_data = Mock()
            mock_data.data = []

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["monsters", "--max-level", "5"])

                assert result.exit_code == 0
                mock_api.assert_called_once()
                call_args = mock_api.call_args
                assert call_args.kwargs["min_level"] is None
                assert call_args.kwargs["max_level"] == 5
                assert call_args.kwargs["page"] == 1
                assert call_args.kwargs["size"] == 50

    def test_monsters_level_range(self, runner, mock_client_manager, mock_api_response):
        """Test monsters command with level range filtering."""
        with patch("artifactsmmo_api_client.api.monsters.get_all_monsters_monsters_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            mock_data = Mock()
            mock_data.data = []

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["monsters", "--min-level", "1", "--max-level", "5"])

                assert result.exit_code == 0
                mock_api.assert_called_once()
                call_args = mock_api.call_args
                assert call_args.kwargs["min_level"] == 1
                assert call_args.kwargs["max_level"] == 5
                assert call_args.kwargs["page"] == 1
                assert call_args.kwargs["size"] == 50

    def test_monsters_level_conflict_with_min_level(self, runner, mock_client_manager):
        """Test monsters command with conflicting level and min-level parameters."""
        result = runner.invoke(app, ["monsters", "--level", "5", "--min-level", "3"])

        assert result.exit_code == 1
        assert "Cannot combine --level with --min-level or --max-level" in result.output

    def test_monsters_level_conflict_with_max_level(self, runner, mock_client_manager):
        """Test monsters command with conflicting level and max-level parameters."""
        result = runner.invoke(app, ["monsters", "--level", "5", "--max-level", "10"])

        assert result.exit_code == 1
        assert "Cannot combine --level with --min-level or --max-level" in result.output

    def test_monsters_level_conflict_with_both(self, runner, mock_client_manager):
        """Test monsters command with conflicting level and both min/max-level parameters."""
        result = runner.invoke(app, ["monsters", "--level", "5", "--min-level", "3", "--max-level", "10"])

        assert result.exit_code == 1
        assert "Cannot combine --level with --min-level or --max-level" in result.output

    def test_monsters_invalid_level_range(self, runner, mock_client_manager):
        """Test monsters command with invalid level range (min > max)."""
        result = runner.invoke(app, ["monsters", "--min-level", "10", "--max-level", "5"])

        assert result.exit_code == 1
        assert "Minimum level cannot be greater than maximum level" in result.output

    def test_resources_specific_resource(self, runner, mock_client_manager, mock_api_response):
        """Test resources command for specific resource."""
        with patch("artifactsmmo_api_client.api.resources.get_resource_resources_code_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            mock_resource = Mock()
            mock_resource.code = "iron_rocks"
            mock_resource.name = "Iron Rocks"
            mock_resource.skill = "mining"
            mock_resource.level = 1
            mock_resource.drops = [Mock(code="iron_ore", rate=100)]

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_resource)

                result = runner.invoke(app, ["resources", "--resource-code", "iron_rocks"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_resources_list(self, runner, mock_client_manager, mock_api_response):
        """Test resources command for listing resources."""
        with patch("artifactsmmo_api_client.api.resources.get_all_resources_resources_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            mock_resource = Mock()
            mock_resource.code = "iron_rocks"
            mock_resource.name = "Iron Rocks"
            mock_resource.skill = "mining"
            mock_resource.level = 1
            mock_resource.drops = [Mock(code="iron_ore", rate=100)]

            mock_data = Mock()
            mock_data.data = [mock_resource]

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["resources"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_achievements_specific(self, runner, mock_client_manager, mock_api_response):
        """Test achievements command for specific achievement."""
        with patch("artifactsmmo_api_client.api.badges.get_badge_badges_code_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            mock_badge = Mock()
            mock_badge.code = "first_kill"
            mock_badge.name = "First Kill"
            mock_badge.description = "Kill your first monster"

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_badge)

                result = runner.invoke(app, ["achievements", "--achievement-code", "first_kill"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_achievements_list(self, runner, mock_client_manager, mock_api_response):
        """Test achievements command for listing achievements."""
        with patch("artifactsmmo_api_client.api.badges.get_all_badges_badges_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            mock_badge = Mock()
            mock_badge.code = "first_kill"
            mock_badge.name = "First Kill"
            mock_badge.description = "Kill your first monster"

            mock_data = Mock()
            mock_data.data = [mock_badge]

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["achievements"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_leaderboard_characters(self, runner, mock_client_manager, mock_api_response):
        """Test leaderboard command for characters."""
        with patch(
            "artifactsmmo_api_client.api.leaderboard.get_characters_leaderboard_leaderboard_characters_get.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            mock_entry = Mock()
            mock_entry.name = "TestChar"
            mock_entry.level = 50
            mock_entry.xp = 125000
            mock_entry.gold = 10000

            mock_data = Mock()
            mock_data.data = [mock_entry]

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["leaderboard", "characters"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_leaderboard_accounts(self, runner, mock_client_manager, mock_api_response):
        """Test leaderboard command for accounts."""
        with patch(
            "artifactsmmo_api_client.api.leaderboard.get_accounts_leaderboard_leaderboard_accounts_get.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            mock_entry = Mock()
            mock_entry.username = "TestUser"
            mock_entry.characters_count = 3
            mock_entry.achievements_points = 500

            mock_data = Mock()
            mock_data.data = [mock_entry]

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["leaderboard", "accounts"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_leaderboard_invalid_type(self, runner):
        """Test leaderboard command with invalid type."""
        result = runner.invoke(app, ["leaderboard", "invalid"])
        assert result.exit_code == 1
        assert "Invalid leaderboard type" in result.stdout

    def test_events_active(self, runner, mock_client_manager, mock_api_response):
        """Test events command for active events."""
        with patch("artifactsmmo_api_client.api.events.get_all_active_events_events_active_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            mock_event = Mock()
            mock_event.name = "Double XP"
            mock_event.map = {"name": "Forest"}
            mock_event.duration = 3600
            mock_event.rate = 2.0
            mock_event.expiration = "2024-01-01T12:00:00Z"

            mock_data = Mock()
            mock_data.data = [mock_event]

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["events"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_events_all(self, runner, mock_client_manager, mock_api_response):
        """Test events command for all events."""
        with patch("artifactsmmo_api_client.api.events.get_all_events_events_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            mock_event = Mock()
            mock_event.name = "Double XP"
            mock_event.map = {"name": "Forest"}
            mock_event.duration = 3600
            mock_event.rate = 2.0
            mock_event.expiration = "2024-01-01T12:00:00Z"

            mock_data = Mock()
            mock_data.data = [mock_event]

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["events", "--no-active-only"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_empty_results(self, runner, mock_client_manager, mock_api_response):
        """Test commands with empty results."""
        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=Mock(data=[]))

                result = runner.invoke(app, ["items"])

                assert result.exit_code == 0
                assert "No items found" in result.stdout

    def test_api_error_handling(self, runner, mock_client_manager):
        """Test API error handling in info commands."""
        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_api:
            mock_api.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.info.handle_api_error") as mock_handle:
                mock_handle.return_value = Mock(error="API Error")

                result = runner.invoke(app, ["items"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout

    def test_map_specific_coordinates(self, runner, mock_client_manager, mock_api_response):
        """Test map command for specific coordinates."""
        with patch("artifactsmmo_api_client.api.maps.get_map_maps_x_y_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            mock_map = Mock()
            mock_map.x = 5
            mock_map.y = 10
            mock_map.name = "Forest"
            mock_map.skin = "forest1"
            mock_map.content = Mock()
            mock_map.content.type = "monster"
            mock_map.content.code = "wolf"

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_map)

                result = runner.invoke(app, ["map", "--x", "5", "--y", "10"])

                assert result.exit_code == 0
                mock_api.assert_called_once_with(client=mock_client_manager.client, x=5, y=10)

    def test_map_list_all(self, runner, mock_client_manager, mock_api_response):
        """Test map command for listing all maps."""
        with patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            mock_map = Mock()
            mock_map.x = 5
            mock_map.y = 10
            mock_map.name = "Forest"
            mock_map.skin = "forest1"
            mock_map.content = Mock()
            mock_map.content.type = "monster"
            mock_map.content.code = "wolf"

            mock_data = Mock()
            mock_data.data = [mock_map]

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["map"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_map_search_by_content(self, runner, mock_client_manager, mock_api_response):
        """Test map command for searching by content code."""
        with patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            mock_map = Mock()
            mock_map.x = 5
            mock_map.y = 10
            mock_map.name = "Forest"
            mock_map.skin = "forest1"
            mock_map.content = Mock()
            mock_map.content.type = "monster"
            mock_map.content.code = "wolf"

            mock_data = Mock()
            mock_data.data = [mock_map]

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["map", "--content-code", "wolf"])

                assert result.exit_code == 0
                mock_api.assert_called_once_with(
                    client=mock_client_manager.client, content_code="wolf", page=1, size=50
                )

    def test_map_not_found(self, runner, mock_client_manager, mock_api_response):
        """Test map command when location not found."""
        with patch("artifactsmmo_api_client.api.maps.get_map_maps_x_y_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, data=None, error="Map not found")

                result = runner.invoke(app, ["map", "--x", "999", "--y", "999"])

                assert result.exit_code == 0
                assert "Map not found" in result.stdout

    def test_map_empty_results(self, runner, mock_client_manager, mock_api_response):
        """Test map command with empty results."""
        with patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=Mock(data=[]))

                result = runner.invoke(app, ["map"])

                assert result.exit_code == 0
                assert "No map locations found" in result.stdout


class TestNPCCommands:
    """Test NPC command functionality."""

    def test_npcs_with_api_data(self, runner, mock_client_manager, mock_api_response):
        """Test npcs command with API data containing NPCs."""
        with patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            # Create mock map items with NPC content
            mock_map1 = Mock()
            mock_map1.x = 1
            mock_map1.y = 2
            mock_map1.name = "Town"
            mock_map1.content = Mock()
            mock_map1.content.type = "tasks_master"
            mock_map1.content.code = "task_master"

            mock_map2 = Mock()
            mock_map2.x = 4
            mock_map2.y = 1
            mock_map2.name = "Town"
            mock_map2.content = Mock()
            mock_map2.content.type = "bank"
            mock_map2.content.code = "bank"

            mock_data = Mock()
            mock_data.data = [mock_map1, mock_map2]
            mock_data.pages = 1

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["npcs"])

                assert result.exit_code == 0
                assert "Task Master" in result.stdout
                assert "Bank" in result.stdout
                assert "(1, 2)" in result.stdout
                assert "(4, 1)" in result.stdout

    def test_npcs_fallback_data(self, runner, mock_client_manager, mock_api_response):
        """Test npcs command falls back to known locations when no API data."""
        with patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            # Mock empty API response
            mock_data = Mock()
            mock_data.data = []
            mock_data.pages = 1

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["npcs"])

                assert result.exit_code == 0
                assert "Warning: No NPC content data found" in result.stdout
                assert "Known NPCs (Fallback Data)" in result.stdout
                assert "Task Master" in result.stdout
                assert "Bank" in result.stdout

    def test_npcs_with_type_filter(self, runner, mock_client_manager, mock_api_response):
        """Test npcs command with type filter."""
        with patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            # Mock empty API response to trigger fallback
            mock_data = Mock()
            mock_data.data = []
            mock_data.pages = 1

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["npcs", "--npc-type", "workshop"])

                assert result.exit_code == 0
                assert "Type: workshop" in result.stdout
                assert "Weaponcrafting Workshop" in result.stdout
                assert "Gearcrafting Workshop" in result.stdout
                assert "Cooking Workshop" in result.stdout
                # Should not contain non-workshop NPCs
                assert "Task Master" not in result.stdout
                assert "Bank" not in result.stdout

    def test_npcs_pagination(self, runner, mock_client_manager, mock_api_response):
        """Test npcs command pagination."""
        with patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            # Mock empty API response to trigger fallback
            mock_data = Mock()
            mock_data.data = []
            mock_data.pages = 1

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["npcs", "--page", "1", "--size", "3"])

                assert result.exit_code == 0
                assert "Page 1 of" in result.stdout

    def test_npc_specific_found(self, runner, mock_client_manager, mock_api_response):
        """Test npc command for specific NPC found in API data."""
        with patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            # Create mock map item with Task Master
            mock_map = Mock()
            mock_map.x = 1
            mock_map.y = 2
            mock_map.name = "Town Square"
            mock_map.content = Mock()
            mock_map.content.type = "tasks_master"
            mock_map.content.code = "task_master"

            mock_data = Mock()
            mock_data.data = [mock_map]
            mock_data.pages = 1

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["npc", "task"])

                assert result.exit_code == 0
                assert "NPC: Task Master" in result.stdout
                assert "Location" in result.stdout
                assert "(1, 2)" in result.stdout
                assert "Town Square" in result.stdout
                assert "tasks_master" in result.stdout

    def test_npc_specific_fallback(self, runner, mock_client_manager, mock_api_response):
        """Test npc command falls back to known locations."""
        with patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            # Mock empty API response
            mock_data = Mock()
            mock_data.data = []
            mock_data.pages = 1

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["npc", "bank"])

                assert result.exit_code == 0
                assert "NPC: Bank" in result.stdout
                assert "(4, 1)" in result.stdout
                assert "API content data not available" in result.stdout

    def test_npc_not_found(self, runner, mock_client_manager, mock_api_response):
        """Test npc command when NPC not found."""
        with patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            # Mock empty API response
            mock_data = Mock()
            mock_data.data = []
            mock_data.pages = 1

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["npc", "nonexistent"])

                assert result.exit_code == 0
                assert "NPC 'nonexistent' not found" in result.stdout

    def test_npc_api_error(self, runner, mock_client_manager):
        """Test NPC commands handle API errors gracefully."""
        with patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync") as mock_api:
            mock_api.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.info.handle_api_error") as mock_handle:
                mock_handle.return_value = Mock(error="API Error")

                result = runner.invoke(app, ["npcs"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout


class TestNPCHelperFunctions:
    """Test NPC helper functions."""

    def test_classify_npc_task_master(self):
        """Test classifying task master NPC."""
        result = _classify_npc("tasks_master", "task_master")

        assert result is not None
        assert result["name"] == "Task Master"
        assert result["type"] == "task_master"
        assert "Task Assignment" in result["services"]

    def test_classify_npc_bank(self):
        """Test classifying bank NPC."""
        result = _classify_npc("bank", "bank")

        assert result is not None
        assert result["name"] == "Bank"
        assert result["type"] == "bank"
        assert "Item Storage" in result["services"]

    def test_classify_npc_grand_exchange(self):
        """Test classifying grand exchange NPC."""
        result = _classify_npc("grand_exchange", "exchange")

        assert result is not None
        assert result["name"] == "Grand Exchange"
        assert result["type"] == "grand_exchange"
        assert "Item Trading" in result["services"]

    def test_classify_npc_weapon_workshop(self):
        """Test classifying weapon workshop NPC."""
        result = _classify_npc("workshop", "weaponcrafting")

        assert result is not None
        assert result["name"] == "Weaponcrafting Workshop"
        assert result["type"] == "workshop"
        assert "Weapon Crafting" in result["services"]

    def test_classify_npc_gear_workshop(self):
        """Test classifying gear workshop NPC."""
        result = _classify_npc("workshop", "gearcrafting")

        assert result is not None
        assert result["name"] == "Gearcrafting Workshop"
        assert result["type"] == "workshop"
        assert "Gear Crafting" in result["services"]

    def test_classify_npc_cooking_workshop(self):
        """Test classifying cooking workshop NPC."""
        result = _classify_npc("workshop", "cooking")

        assert result is not None
        assert result["name"] == "Cooking Workshop"
        assert result["type"] == "workshop"
        assert "Food Preparation" in result["services"]

    def test_classify_npc_generic_workshop(self):
        """Test classifying generic workshop NPC."""
        result = _classify_npc("workshop", "mining")

        assert result is not None
        assert result["name"] == "Mining Workshop"
        assert result["type"] == "workshop"
        assert "Crafting" in result["services"]

    def test_classify_npc_not_npc(self):
        """Test classifying non-NPC content."""
        result = _classify_npc("monster", "wolf")

        assert result is None

    def test_classify_npc_empty_content(self):
        """Test classifying empty content."""
        result = _classify_npc("", "")

        assert result is None

    def test_get_fallback_npc_found(self):
        """Test getting fallback NPC that exists."""
        result = _get_fallback_npc("task")

        assert result is not None
        assert result["name"] == "Task Master"
        assert result["x"] == 1
        assert result["y"] == 2

    def test_get_fallback_npc_case_insensitive(self):
        """Test getting fallback NPC with case insensitive search."""
        result = _get_fallback_npc("BANK")

        assert result is not None
        assert result["name"] == "Bank"

    def test_get_fallback_npc_partial_match(self):
        """Test getting fallback NPC with partial name match."""
        result = _get_fallback_npc("weapon")

        assert result is not None
        assert result["name"] == "Weaponcrafting Workshop"

    def test_get_fallback_npc_not_found(self):
        """Test getting fallback NPC that doesn't exist."""
        result = _get_fallback_npc("nonexistent")

        assert result is None


class TestResourceDiscoveryCommands:
    """Test resource discovery functionality."""

    def test_nearest_command_with_character(self, runner, mock_client_manager):
        """Test nearest command with character position."""
        with (
            patch("artifactsmmo_cli.commands.info.get_character_position") as mock_get_pos,
            patch("artifactsmmo_cli.commands.info._find_resource_locations") as mock_find_resources,
        ):
            mock_get_pos.return_value = (5, 5)
            mock_find_resources.return_value = [
                {
                    "name": "Copper Rock",
                    "type": "resource",
                    "x": 3,
                    "y": 4,
                    "distance": 3,
                    "level": 1,
                    "skill": "mining",
                    "content_code": "copper_rock",
                },
                {
                    "name": "Copper Rock",
                    "type": "resource",
                    "x": 7,
                    "y": 6,
                    "distance": 3,
                    "level": 1,
                    "skill": "mining",
                    "content_code": "copper_rock",
                },
            ]

            result = runner.invoke(app, ["nearest", "copper", "--character", "testchar"])

            assert result.exit_code == 0
            assert "Nearest Copper Resources" in result.stdout
            assert "(3, 4)" in result.stdout
            assert "(7, 6)" in result.stdout
            mock_get_pos.assert_called_once_with("testchar")

    def test_nearest_command_without_character(self, runner, mock_client_manager):
        """Test nearest command without character position."""
        with patch("artifactsmmo_cli.commands.info._find_resource_locations") as mock_find_resources:
            mock_find_resources.return_value = [
                {
                    "name": "Iron Rock",
                    "type": "resource",
                    "x": 10,
                    "y": 12,
                    "distance": 0,
                    "level": 5,
                    "skill": "mining",
                    "content_code": "iron_rock",
                }
            ]

            result = runner.invoke(app, ["nearest", "iron"])

            assert result.exit_code == 0
            assert "Iron Resource Locations" in result.stdout
            assert "(10, 12)" in result.stdout

    def test_nearest_command_with_type_filter(self, runner, mock_client_manager):
        """Test nearest command with resource type filter."""
        with patch("artifactsmmo_cli.commands.info._find_resource_locations") as mock_find_resources:
            mock_find_resources.return_value = [
                {
                    "name": "Ash Tree",
                    "type": "resource",
                    "x": 2,
                    "y": 3,
                    "distance": 0,
                    "level": 1,
                    "skill": "woodcutting",
                    "content_code": "ash_tree",
                }
            ]

            result = runner.invoke(app, ["nearest", "tree", "--type", "woodcutting"])

            assert result.exit_code == 0
            assert "Tree Resource Locations" in result.stdout

    def test_nearest_command_with_max_distance(self, runner, mock_client_manager):
        """Test nearest command with max distance filter."""
        with (
            patch("artifactsmmo_cli.commands.info.get_character_position") as mock_get_pos,
            patch("artifactsmmo_cli.commands.info._find_resource_locations") as mock_find_resources,
        ):
            mock_get_pos.return_value = (0, 0)
            mock_find_resources.return_value = [
                {
                    "name": "Copper Rock",
                    "type": "resource",
                    "x": 2,
                    "y": 2,
                    "distance": 4,
                    "level": 1,
                    "skill": "mining",
                    "content_code": "copper_rock",
                }
            ]

            result = runner.invoke(app, ["nearest", "copper", "--character", "testchar", "--max-distance", "5"])

            assert result.exit_code == 0
            assert "Nearest Copper Resources" in result.stdout

    def test_nearest_command_no_resources_found(self, runner, mock_client_manager):
        """Test nearest command when no resources found."""
        with patch("artifactsmmo_cli.commands.info._find_resource_locations") as mock_find_resources:
            mock_find_resources.return_value = []

            result = runner.invoke(app, ["nearest", "nonexistent"])

            assert result.exit_code == 1
            assert "No resources found matching 'nonexistent'" in result.stdout

    def test_nearest_command_character_not_found(self, runner, mock_client_manager):
        """Test nearest command with invalid character."""
        with patch("artifactsmmo_cli.commands.info.get_character_position") as mock_get_pos:
            mock_get_pos.side_effect = Exception("Character not found")

            result = runner.invoke(app, ["nearest", "copper", "--character", "invalidchar"])

            assert result.exit_code == 1
            assert "Could not get character position" in result.stdout

    def test_resources_command_with_location_filter(self, runner, mock_client_manager, mock_api_response):
        """Test resources command with location and radius filter."""
        with (
            patch("artifactsmmo_api_client.api.resources.get_all_resources_resources_get.sync") as mock_api,
            patch("artifactsmmo_cli.commands.info._find_resource_locations") as mock_find_resources,
        ):
            mock_api.return_value = mock_api_response

            # Mock resource data
            mock_resource = Mock()
            mock_resource.code = "copper_rock"
            mock_resource.name = "Copper Rock"
            mock_resource.skill = "mining"
            mock_resource.level = 1
            mock_resource.drops = []

            mock_resources = Mock()
            mock_resources.data = [mock_resource]
            mock_resources.pages = 1

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value.success = True
                mock_handle.return_value.data = mock_resources

                mock_find_resources.return_value = [
                    {
                        "name": "Copper Rock",
                        "type": "resource",
                        "x": 3,
                        "y": 4,
                        "distance": 2,
                        "level": 1,
                        "skill": "mining",
                        "content_code": "copper_rock",
                    }
                ]

                result = runner.invoke(app, ["resources", "--location", "5 5", "--radius", "3"])

                assert result.exit_code == 0
                assert "Resources (Near 5, 5 within 3)" in result.stdout

    def test_resources_command_with_character(self, runner, mock_client_manager, mock_api_response):
        """Test resources command with character for distance calculation."""
        with (
            patch("artifactsmmo_api_client.api.resources.get_all_resources_resources_get.sync") as mock_api,
            patch("artifactsmmo_cli.commands.info.get_character_position") as mock_get_pos,
            patch("artifactsmmo_cli.commands.info._find_resource_locations") as mock_find_resources,
        ):
            mock_api.return_value = mock_api_response
            mock_get_pos.return_value = (0, 0)

            # Mock resource data
            mock_resource = Mock()
            mock_resource.code = "iron_ore"
            mock_resource.name = "Iron Ore"
            mock_resource.skill = "mining"
            mock_resource.level = 5
            mock_resource.drops = []

            mock_resources = Mock()
            mock_resources.data = [mock_resource]
            mock_resources.pages = 1

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value.success = True
                mock_handle.return_value.data = mock_resources

                mock_find_resources.return_value = [
                    {
                        "name": "Iron Ore",
                        "type": "resource",
                        "x": 5,
                        "y": 5,
                        "distance": 10,
                        "level": 5,
                        "skill": "mining",
                        "content_code": "iron_ore",
                    }
                ]

                result = runner.invoke(app, ["resources", "--character", "testchar"])

                assert result.exit_code == 0
                assert "Resources (Near testchar)" in result.stdout
                assert "Distance" in result.stdout

    def test_resources_command_invalid_location(self, runner, mock_client_manager):
        """Test resources command with invalid location format."""
        result = runner.invoke(app, ["resources", "--location", "invalid"])

        assert result.exit_code == 1
        assert "Invalid location format" in result.stdout

    def test_resources_command_radius_without_location(self, runner, mock_client_manager):
        """Test resources command with radius but no location."""
        result = runner.invoke(app, ["resources", "--radius", "5"])

        assert result.exit_code == 1
        assert "--radius requires --location" in result.stdout

    def test_resources_command_with_type_filter(self, runner, mock_client_manager, mock_api_response):
        """Test resources command with type filter."""
        with patch("artifactsmmo_api_client.api.resources.get_all_resources_resources_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            # Mock resource data
            mock_resource = Mock()
            mock_resource.code = "ash_tree"
            mock_resource.name = "Ash Tree"
            mock_resource.skill = "woodcutting"
            mock_resource.level = 1
            mock_resource.drops = []

            mock_resources = Mock()
            mock_resources.data = [mock_resource]
            mock_resources.pages = 1

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value.success = True
                mock_handle.return_value.data = mock_resources

                result = runner.invoke(app, ["resources", "--type", "woodcutting"])

                assert result.exit_code == 0
                assert "Resources (Type: woodcutting)" in result.stdout

    def test_resources_command_with_max_level(self, runner, mock_client_manager, mock_api_response):
        """Test resources command with max level filter."""
        with patch("artifactsmmo_api_client.api.resources.get_all_resources_resources_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            # Mock resource data
            mock_resource = Mock()
            mock_resource.code = "copper_rock"
            mock_resource.name = "Copper Rock"
            mock_resource.skill = "mining"
            mock_resource.level = 1
            mock_resource.drops = []

            mock_resources = Mock()
            mock_resources.data = [mock_resource]
            mock_resources.pages = 1

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value.success = True
                mock_handle.return_value.data = mock_resources

                result = runner.invoke(app, ["resources", "--max-level", "5"])

                assert result.exit_code == 0


class TestResourceDiscoveryHelpers:
    """Test helper functions for resource discovery."""

    def test_get_resource_data(self, mock_client_manager):
        """Test _get_resource_data function."""
        mock_response = Mock()
        mock_response.status_code = 200

        mock_resource = Mock()
        mock_resource.code = "copper_rock"
        mock_resource.name = "Copper Rock"
        mock_resource.skill = "mining"
        mock_resource.level = 1

        mock_resources = Mock()
        mock_resources.data = [mock_resource]
        mock_resources.pages = 1

        with (
            patch("artifactsmmo_api_client.api.resources.get_all_resources_resources_get.sync") as mock_api,
            patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle,
        ):
            mock_api.return_value = mock_response
            mock_handle.return_value.success = True
            mock_handle.return_value.data = mock_resources

            result = _get_resource_data("copper")

            assert len(result) == 1
            assert result[0]["code"] == "copper_rock"
            assert result[0]["name"] == "Copper Rock"
            assert result[0]["skill"] == "mining"
            assert result[0]["level"] == 1

    def test_matches_resource_criteria(self):
        """Test _matches_resource_criteria function."""
        resource_data = [{"code": "copper_rock", "name": "Copper Rock", "skill": "mining", "level": 1}]

        # Test exact code match
        assert _matches_resource_criteria("copper_rock", "resource", "copper", None, resource_data)

        # Test name match in content code
        assert _matches_resource_criteria("copper_ore", "resource", "copper", None, resource_data)

        # Test type-based matching
        assert _matches_resource_criteria("iron_ore", "resource", "ore", "mining", resource_data)

        # Test no match
        assert not _matches_resource_criteria("fish", "resource", "copper", None, resource_data)

    def test_get_resource_info_for_content(self):
        """Test _get_resource_info_for_content function."""
        resource_data = [{"code": "copper_rock", "name": "Copper Rock", "skill": "mining", "level": 1}]

        # Test exact match
        result = _get_resource_info_for_content("copper_rock", resource_data)
        assert result["name"] == "Copper Rock"
        assert result["skill"] == "mining"
        assert result["level"] == 1

        # Test no match (default)
        result = _get_resource_info_for_content("unknown_resource", resource_data)
        assert result["name"] == "Unknown Resource"
        assert result["skill"] == "Unknown"
        assert result["level"] == 0

    def test_find_resource_locations(self, mock_client_manager):
        """Test _find_resource_locations function."""
        mock_response = Mock()
        mock_response.status_code = 200

        # Mock map data
        mock_content = Mock()
        mock_content.code = "copper_rock"
        mock_content.type = "resource"

        mock_map_item = Mock()
        mock_map_item.x = 5
        mock_map_item.y = 5
        mock_map_item.content = mock_content

        mock_maps = Mock()
        mock_maps.data = [mock_map_item]
        mock_maps.pages = 1

        # Mock resource data
        resource_data = [{"code": "copper_rock", "name": "Copper Rock", "skill": "mining", "level": 1}]

        with (
            patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync") as mock_map_api,
            patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle,
            patch("artifactsmmo_cli.commands.info._get_resource_data") as mock_get_data,
        ):
            mock_map_api.return_value = mock_response
            mock_handle.return_value.success = True
            mock_handle.return_value.data = mock_maps
            mock_get_data.return_value = resource_data

            result = _find_resource_locations("copper", character_x=0, character_y=0)

            assert len(result) == 1
            assert result[0]["name"] == "Copper Rock"
            assert result[0]["x"] == 5
            assert result[0]["y"] == 5
            assert result[0]["distance"] == 10  # Manhattan distance from (0,0) to (5,5)

    def test_find_resource_locations_with_max_distance(self, mock_client_manager):
        """Test _find_resource_locations with max distance filter."""
        mock_response = Mock()
        mock_response.status_code = 200

        # Mock map data - resource too far away
        mock_content = Mock()
        mock_content.code = "copper_rock"
        mock_content.type = "resource"

        mock_map_item = Mock()
        mock_map_item.x = 10
        mock_map_item.y = 10
        mock_map_item.content = mock_content

        mock_maps = Mock()
        mock_maps.data = [mock_map_item]
        mock_maps.pages = 1

        resource_data = [{"code": "copper_rock", "name": "Copper Rock", "skill": "mining", "level": 1}]

        with (
            patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync") as mock_map_api,
            patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle,
            patch("artifactsmmo_cli.commands.info._get_resource_data") as mock_get_data,
        ):
            mock_map_api.return_value = mock_response
            mock_handle.return_value.success = True
            mock_handle.return_value.data = mock_maps
            mock_get_data.return_value = resource_data

            # Resource at (10,10) is distance 20 from (0,0), should be filtered out with max_distance=10
            result = _find_resource_locations("copper", character_x=0, character_y=0, max_distance=10)

            assert len(result) == 0


class TestCombatAssessment:
    """Test combat assessment functionality."""

    def test_calculate_difficulty_rating_easy(self):
        """Test difficulty calculation for easy monsters."""
        result = _calculate_difficulty_rating(char_level=10, monster_level=8)

        assert result["rating"] == "Easy"
        assert result["color"] == "green"
        assert result["emoji"] == "🟢"

    def test_calculate_difficulty_rating_medium(self):
        """Test difficulty calculation for medium monsters."""
        result = _calculate_difficulty_rating(char_level=10, monster_level=10)

        assert result["rating"] == "Medium"
        assert result["color"] == "yellow"
        assert result["emoji"] == "🟡"

    def test_calculate_difficulty_rating_hard(self):
        """Test difficulty calculation for hard monsters."""
        result = _calculate_difficulty_rating(char_level=10, monster_level=12)

        assert result["rating"] == "Hard"
        assert result["color"] == "red"
        assert result["emoji"] == "🟠"

    def test_calculate_difficulty_rating_deadly(self):
        """Test difficulty calculation for deadly monsters."""
        result = _calculate_difficulty_rating(char_level=10, monster_level=15)

        assert result["rating"] == "Deadly"
        assert result["color"] == "bright_red"
        assert result["emoji"] == "🔴"

    def test_calculate_success_probability_easy(self):
        """Test success probability for easy combat."""
        character = {
            "level": 10,
            "max_hp": 200,
            "attack_fire": 50,
            "attack_earth": 0,
            "attack_water": 0,
            "attack_air": 0,
        }
        monster = {"level": 8, "hp": 100, "attack_fire": 20, "attack_earth": 0, "attack_water": 0, "attack_air": 0}

        result = _calculate_success_probability(character, monster)

        assert 85 <= result <= 95

    def test_calculate_success_probability_hard(self):
        """Test success probability for hard combat."""
        character = {
            "level": 10,
            "max_hp": 100,
            "attack_fire": 20,
            "attack_earth": 0,
            "attack_water": 0,
            "attack_air": 0,
        }
        monster = {"level": 13, "hp": 200, "attack_fire": 50, "attack_earth": 0, "attack_water": 0, "attack_air": 0}

        result = _calculate_success_probability(character, monster)

        assert 25 <= result <= 65

    def test_calculate_success_probability_hp_advantage(self):
        """Test success probability with HP advantage."""
        character = {
            "level": 10,
            "max_hp": 300,
            "attack_fire": 30,
            "attack_earth": 0,
            "attack_water": 0,
            "attack_air": 0,
        }
        monster = {"level": 10, "hp": 100, "attack_fire": 30, "attack_earth": 0, "attack_water": 0, "attack_air": 0}

        result = _calculate_success_probability(character, monster)

        # Should get bonus for HP advantage
        assert result >= 80

    def test_format_combat_analysis(self):
        """Test combat analysis formatting."""
        character = {
            "name": "TestChar",
            "level": 10,
            "max_hp": 200,
            "attack_fire": 30,
            "attack_earth": 0,
            "attack_water": 0,
            "attack_air": 0,
        }
        monster = {"level": 12, "hp": 150, "attack_fire": 25, "attack_earth": 0, "attack_water": 0, "attack_air": 0}

        result = _format_combat_analysis(character, monster)

        # Check that all expected rows are present
        row_dict = {row[0]: row[1] for row in result}

        assert row_dict["Character Level"] == "10"
        assert row_dict["Monster Level"] == "12"
        assert row_dict["Level Difference"] == "+2"
        assert "Hard" in row_dict["Difficulty"]
        assert "%" in row_dict["Success Probability"]
        assert row_dict["Character HP"] == "200"
        assert row_dict["Monster HP"] == "150"

    def test_get_monster_drops_with_drops(self):
        """Test monster drops extraction with drops."""
        mock_drop = Mock()
        mock_drop.code = "iron_ore"
        mock_drop.rate = 50
        mock_drop.min_quantity = 1
        mock_drop.max_quantity = 3

        mock_monster = Mock()
        mock_monster.drops = [mock_drop]

        result = _get_monster_drops(mock_monster)

        assert len(result) == 1
        assert "iron_ore x1-3 (50%)" in result

    def test_get_monster_drops_no_drops(self):
        """Test monster drops extraction with no drops."""
        mock_monster = Mock()
        mock_monster.drops = []

        result = _get_monster_drops(mock_monster)

        assert len(result) == 0

    def test_get_monster_drops_single_quantity(self):
        """Test monster drops with single quantity."""
        mock_drop = Mock()
        mock_drop.code = "gold"
        mock_drop.rate = 100
        mock_drop.min_quantity = 5
        mock_drop.max_quantity = 5

        mock_monster = Mock()
        mock_monster.drops = [mock_drop]

        result = _get_monster_drops(mock_monster)

        assert len(result) == 1
        assert "gold x5 (100%)" in result

    def test_get_character_data_success(self, mock_client_manager):
        """Test successful character data retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200

        mock_character = Mock()
        mock_character.name = "TestChar"
        mock_character.level = 15
        mock_character.hp = 100
        mock_character.max_hp = 150
        mock_character.attack_fire = 25
        mock_character.attack_earth = 0
        mock_character.attack_water = 0
        mock_character.attack_air = 0
        mock_character.res_fire = 10
        mock_character.res_earth = 0
        mock_character.res_water = 0
        mock_character.res_air = 0
        mock_character.dmg = 5
        mock_character.dmg_fire = 0
        mock_character.dmg_earth = 0
        mock_character.dmg_water = 0
        mock_character.dmg_air = 0

        with (
            patch("artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync") as mock_api,
            patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle,
        ):
            mock_api.return_value = mock_response
            mock_handle.return_value = Mock(success=True, data=mock_character)

            result = _get_character_data("TestChar")

            assert result is not None
            assert result["name"] == "TestChar"
            assert result["level"] == 15
            assert result["max_hp"] == 150
            assert result["attack_fire"] == 25

    def test_get_character_data_not_found(self, mock_client_manager):
        """Test character data retrieval when character not found."""
        mock_response = Mock()
        mock_response.status_code = 404

        with (
            patch("artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync") as mock_api,
            patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle,
        ):
            mock_api.return_value = mock_response
            mock_handle.return_value = Mock(success=False, data=None)

            result = _get_character_data("NonExistent")

            assert result is None

    def test_monsters_command_with_compare(self, runner, mock_client_manager, mock_api_response):
        """Test monsters command with character comparison."""
        with (
            patch("artifactsmmo_api_client.api.monsters.get_all_monsters_monsters_get.sync") as mock_monsters_api,
            patch("artifactsmmo_cli.commands.info._get_character_data") as mock_get_char,
        ):
            mock_monsters_api.return_value = mock_api_response

            # Mock character data
            mock_get_char.return_value = {
                "name": "TestChar",
                "level": 10,
                "max_hp": 200,
                "attack_fire": 30,
                "attack_earth": 0,
                "attack_water": 0,
                "attack_air": 0,
            }

            # Mock monster data
            mock_monster = Mock()
            mock_monster.code = "goblin"
            mock_monster.name = "Goblin"
            mock_monster.level = 8
            mock_monster.hp = 100
            mock_monster.attack_fire = 20
            mock_monster.attack_earth = 0
            mock_monster.attack_water = 0
            mock_monster.attack_air = 0
            mock_monster.drops = []

            mock_data = Mock()
            mock_data.data = [mock_monster]

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["monsters", "--compare", "TestChar"])

                assert result.exit_code == 0
                assert "Combat Assessment for TestChar" in result.output
                assert "Easy" in result.output
                assert "95%" in result.output
                assert "🟢" in result.output  # Easy difficulty emoji

    def test_monsters_command_compare_character_not_found(self, runner, mock_client_manager):
        """Test monsters command with invalid character for comparison."""
        with patch("artifactsmmo_cli.commands.info._get_character_data") as mock_get_char:
            mock_get_char.return_value = None

            result = runner.invoke(app, ["monsters", "--compare", "NonExistent"])

            assert result.exit_code == 1
            assert "Character 'NonExistent' not found" in result.output

    def test_monster_command_basic(self, runner, mock_client_manager, mock_api_response):
        """Test monster command for specific monster lookup."""
        with patch("artifactsmmo_api_client.api.monsters.get_monster_monsters_code_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            mock_monster = Mock()
            mock_monster.code = "dragon"
            mock_monster.name = "Dragon"
            mock_monster.level = 20
            mock_monster.hp = 500
            mock_monster.attack_fire = 80
            mock_monster.attack_earth = 0
            mock_monster.attack_water = 0
            mock_monster.attack_air = 0
            mock_monster.res_fire = 50
            mock_monster.res_earth = 0
            mock_monster.res_water = 0
            mock_monster.res_air = 0
            mock_monster.drops = []

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_monster)

                result = runner.invoke(app, ["monster", "dragon"])

                assert result.exit_code == 0
                assert "Monster: Dragon" in result.output
                assert "Level" in result.output
                assert "20" in result.output
                assert "Total Attack" in result.output

    def test_monster_command_with_compare(self, runner, mock_client_manager, mock_api_response):
        """Test monster command with character comparison."""
        with (
            patch("artifactsmmo_api_client.api.monsters.get_monster_monsters_code_get.sync") as mock_api,
            patch("artifactsmmo_cli.commands.info._get_character_data") as mock_get_char,
        ):
            mock_api.return_value = mock_api_response

            # Mock character data
            mock_get_char.return_value = {
                "name": "TestChar",
                "level": 15,
                "max_hp": 250,
                "attack_fire": 40,
                "attack_earth": 0,
                "attack_water": 0,
                "attack_air": 0,
            }

            # Mock monster data
            mock_monster = Mock()
            mock_monster.code = "orc"
            mock_monster.name = "Orc"
            mock_monster.level = 18
            mock_monster.hp = 200
            mock_monster.attack_fire = 35
            mock_monster.attack_earth = 0
            mock_monster.attack_water = 0
            mock_monster.attack_air = 0
            mock_monster.res_fire = 10
            mock_monster.res_earth = 0
            mock_monster.res_water = 0
            mock_monster.res_air = 0
            mock_monster.drops = []

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_monster)

                result = runner.invoke(app, ["monster", "orc", "--compare", "TestChar"])

                assert result.exit_code == 0
                assert "Monster: Orc" in result.output
                assert "Combat Analysis: TestChar vs Orc" in result.output
                assert "Difficulty" in result.output
                assert "Success Probability" in result.output

    def test_monster_command_not_found(self, runner, mock_client_manager, mock_api_response):
        """Test monster command when monster not found."""
        with (
            patch("artifactsmmo_api_client.api.monsters.get_monster_monsters_code_get.sync") as mock_get_api,
            patch("artifactsmmo_api_client.api.monsters.get_all_monsters_monsters_get.sync") as mock_list_api,
        ):
            # Mock failed direct lookup
            mock_get_api.side_effect = Exception("Not found")

            # Mock empty search results
            mock_list_api.return_value = mock_api_response
            mock_data = Mock()
            mock_data.data = []
            mock_data.pages = 1

            with patch("artifactsmmo_cli.commands.info.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["monster", "nonexistent"])

                assert result.exit_code == 1
                assert "Monster 'nonexistent' not found" in result.output
