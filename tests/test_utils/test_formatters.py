"""Tests for formatting utilities."""

import json
from unittest.mock import Mock

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from artifactsmmo_cli.utils.formatters import (
    _get_attr_or_key,
    format_bank_table,
    format_character_status,
    format_character_table,
    format_combat_result,
    format_cooldown_message,
    format_error_message,
    format_gathering_result,
    format_item_table,
    format_json_output,
    format_map_info,
    format_success_message,
    format_table,
    format_time_duration,
    format_warning_message,
)


class TestGetAttrOrKey:
    """Test _get_attr_or_key function."""

    def test_get_attribute(self):
        """Test getting attribute from object."""
        obj = Mock()
        obj.name = "test_value"

        result = _get_attr_or_key(obj, "name")

        assert result == "test_value"

    def test_get_dict_key(self):
        """Test getting key from dictionary."""
        obj = {"name": "test_value"}

        result = _get_attr_or_key(obj, "name")

        assert result == "test_value"

    def test_get_missing_attribute_with_default(self):
        """Test getting missing attribute with default."""
        obj = Mock(spec=[])  # Empty spec means no attributes

        result = _get_attr_or_key(obj, "missing", "default")

        assert result == "default"

    def test_get_missing_dict_key_with_default(self):
        """Test getting missing dict key with default."""
        obj = {"name": "test_value"}

        result = _get_attr_or_key(obj, "missing", "default")

        assert result == "default"

    def test_get_from_non_dict_non_object(self):
        """Test getting from non-dict, non-object."""
        obj = "string"

        result = _get_attr_or_key(obj, "missing", "default")

        assert result == "default"

    def test_get_with_empty_default(self):
        """Test getting with empty string default."""
        obj = {}

        result = _get_attr_or_key(obj, "missing")

        assert result == ""


class TestFormatCharacterTable:
    """Test format_character_table function."""

    def test_format_empty_characters(self):
        """Test formatting empty character list."""
        result = format_character_table([])

        assert isinstance(result, Table)
        assert result.title == "Characters"

    def test_format_characters_with_attributes(self):
        """Test formatting characters with attributes."""
        char1 = Mock()
        char1.name = "warrior"
        char1.level = 10
        char1.class_ = "fighter"  # Note: class is a reserved word
        char1.hp = 80
        char1.max_hp = 100
        char1.mp = 20
        char1.max_mp = 30
        char1.gold = 500
        char1.x = 5
        char1.y = 10

        # Mock the class attribute properly
        setattr(char1, "class", "fighter")

        result = format_character_table([char1])

        assert isinstance(result, Table)
        assert result.title == "Characters"

    def test_format_characters_with_dict(self):
        """Test formatting characters as dictionaries."""
        char1 = {
            "name": "mage",
            "level": 15,
            "class": "wizard",
            "hp": 60,
            "max_hp": 80,
            "mp": 100,
            "max_mp": 120,
            "gold": 750,
            "x": -3,
            "y": 7,
        }

        result = format_character_table([char1])

        assert isinstance(result, Table)
        assert result.title == "Characters"

    def test_format_characters_with_missing_attributes(self):
        """Test formatting characters with missing attributes."""
        char1 = {"name": "incomplete"}

        result = format_character_table([char1])

        assert isinstance(result, Table)


class TestFormatItemTable:
    """Test format_item_table function."""

    def test_format_empty_items(self):
        """Test formatting empty item list."""
        result = format_item_table([])

        assert isinstance(result, Table)
        assert result.title == "Items"

    def test_format_items(self):
        """Test formatting item list."""
        items = [
            {"code": "iron_sword", "name": "Iron Sword", "type": "weapon", "level": 5, "quantity": 1},
            {"code": "health_potion", "name": "Health Potion", "type": "consumable", "level": 1, "quantity": 10},
        ]

        result = format_item_table(items)

        assert isinstance(result, Table)
        assert result.title == "Items"

    def test_format_items_with_missing_fields(self):
        """Test formatting items with missing fields."""
        items = [{"code": "incomplete_item"}]

        result = format_item_table(items)

        assert isinstance(result, Table)


class TestFormatBankTable:
    """Test format_bank_table function."""

    def test_format_empty_bank(self):
        """Test formatting empty bank."""
        result = format_bank_table([])

        assert isinstance(result, Table)
        assert result.title == "Bank Items"

    def test_format_bank_items(self):
        """Test formatting bank items."""
        items = [{"code": "iron_ore", "quantity": 50}, {"code": "copper_ore", "quantity": 25}]

        result = format_bank_table(items)

        assert isinstance(result, Table)
        assert result.title == "Bank Items"

    def test_format_bank_items_with_missing_fields(self):
        """Test formatting bank items with missing fields."""
        items = [{"code": "incomplete_item"}]

        result = format_bank_table(items)

        assert isinstance(result, Table)


class TestFormatMessages:
    """Test message formatting functions."""

    def test_format_success_message(self):
        """Test formatting success message."""
        result = format_success_message("Operation completed")

        assert isinstance(result, Text)
        assert "✓ Operation completed" in str(result)

    def test_format_error_message(self):
        """Test formatting error message."""
        result = format_error_message("Something went wrong")

        assert isinstance(result, Text)
        assert "✗ Something went wrong" in str(result)

    def test_format_warning_message(self):
        """Test formatting warning message."""
        result = format_warning_message("Be careful")

        assert isinstance(result, Text)
        assert "⚠ Be careful" in str(result)

    def test_format_cooldown_message(self):
        """Test formatting cooldown message."""
        result = format_cooldown_message(30)

        assert isinstance(result, Text)
        assert "⏱ Action on cooldown for 30 seconds" in str(result)


class TestFormatJsonOutput:
    """Test format_json_output function."""

    def test_format_dict(self):
        """Test formatting dictionary as JSON."""
        data = {"name": "test", "value": 123}

        result = format_json_output(data)

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed == data

    def test_format_list(self):
        """Test formatting list as JSON."""
        data = [1, 2, 3, "test"]

        result = format_json_output(data)

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed == data

    def test_format_with_non_serializable(self):
        """Test formatting with non-serializable objects."""
        data = {"mock": Mock()}

        result = format_json_output(data)

        assert isinstance(result, str)
        # Should not raise exception due to default=str


class TestFormatTable:
    """Test format_table function."""

    def test_format_generic_table(self):
        """Test formatting generic table."""
        headers = ["Name", "Age", "City"]
        rows = [["Alice", "25", "New York"], ["Bob", "30", "London"]]

        result = format_table(headers, rows, "People")

        assert isinstance(result, Table)
        assert result.title == "People"

    def test_format_table_without_title(self):
        """Test formatting table without title."""
        headers = ["Col1", "Col2"]
        rows = [["A", "B"]]

        result = format_table(headers, rows)

        assert isinstance(result, Table)
        assert result.title == ""

    def test_format_empty_table(self):
        """Test formatting empty table."""
        headers = ["Col1", "Col2"]
        rows = []

        result = format_table(headers, rows)

        assert isinstance(result, Table)


class TestFormatMapInfo:
    """Test format_map_info function."""

    def test_format_complete_map_info(self):
        """Test formatting complete map information."""
        map_data = {
            "x": 5,
            "y": 10,
            "name": "Forest",
            "skin": "forest_tile",
            "content": {"type": "monster", "code": "goblin"},
        }

        result = format_map_info(map_data)

        assert isinstance(result, str)
        assert "Forest" in result
        assert "forest_tile" in result
        assert "monster" in result
        assert "goblin" in result

    def test_format_minimal_map_info(self):
        """Test formatting minimal map information."""
        map_data = {}

        result = format_map_info(map_data)

        assert isinstance(result, str)
        assert "Unknown" in result

    def test_format_map_info_with_partial_content(self):
        """Test formatting map info with partial content."""
        map_data = {"x": 0, "y": 0, "name": "Town", "content": {"type": "bank"}}

        result = format_map_info(map_data)

        assert isinstance(result, str)
        assert "Town" in result
        assert "bank" in result


class TestFormatTimeDuration:
    """Test format_time_duration function."""

    def test_format_seconds_only(self):
        """Test formatting seconds only."""
        result = format_time_duration(30)
        assert result == "30 seconds"

    def test_format_minutes_only(self):
        """Test formatting exact minutes."""
        result = format_time_duration(120)
        assert result == "2 minutes"

    def test_format_minutes_and_seconds(self):
        """Test formatting minutes and seconds."""
        result = format_time_duration(90)
        assert result == "1m 30s"

    def test_format_hours_only(self):
        """Test formatting exact hours."""
        result = format_time_duration(7200)
        assert result == "2h"

    def test_format_hours_and_minutes(self):
        """Test formatting hours and minutes."""
        result = format_time_duration(7320)
        assert result == "2h 2m"

    def test_format_hours_minutes_seconds(self):
        """Test formatting hours, minutes, and seconds."""
        result = format_time_duration(7323)
        assert result == "2h 2m 3s"


class TestFormatCombatResult:
    """Test format_combat_result function."""

    def test_format_victory(self):
        """Test formatting victory result."""
        fight_data = {"result": "win", "damage": 25, "xp": 100, "gold": 50}

        result = format_combat_result(fight_data)

        assert isinstance(result, Text)
        assert "Victory!" in str(result)
        assert "Damage dealt: 25" in str(result)
        assert "XP gained: 100" in str(result)
        assert "Gold gained: 50" in str(result)

    def test_format_defeat(self):
        """Test formatting defeat result."""
        fight_data = {"result": "lose", "damage": 10}

        result = format_combat_result(fight_data)

        assert isinstance(result, Text)
        assert "Defeat!" in str(result)
        assert "Damage dealt: 10" in str(result)

    def test_format_defeat_with_loss_result(self):
        """Test formatting defeat result with 'loss' instead of 'lose'."""
        fight_data = {"result": "loss", "damage": 15, "xp": 25}

        result = format_combat_result(fight_data)

        assert isinstance(result, Text)
        assert "Defeat!" in str(result)
        assert "Damage dealt: 15" in str(result)
        assert "XP gained: 25" in str(result)

    def test_format_with_drops(self):
        """Test formatting with item drops."""
        fight_data = {
            "result": "win",
            "drops": [{"code": "iron_ore", "quantity": 2}, {"code": "gold_coin", "quantity": 1}],
        }

        result = format_combat_result(fight_data)

        assert isinstance(result, Text)
        assert "Victory!" in str(result)
        assert "Items dropped: 2x iron_ore, 1x gold_coin" in str(result)

    def test_format_minimal_data(self):
        """Test formatting with minimal data."""
        fight_data = {}

        result = format_combat_result(fight_data)

        assert isinstance(result, Text)
        assert "Combat completed" in str(result)


class TestFormatGatheringResult:
    """Test format_gathering_result function."""

    def test_format_gathering_with_items(self):
        """Test formatting gathering with items."""
        gather_data = {
            "xp": 50,
            "items": [{"code": "wood", "quantity": 3}, {"code": "apple", "quantity": 1}],
        }

        result = format_gathering_result(gather_data)

        assert isinstance(result, Text)
        assert "Gathering completed" in str(result)
        assert "XP gained: 50" in str(result)
        assert "Items gathered: 3x wood, 1x apple" in str(result)

    def test_format_gathering_minimal(self):
        """Test formatting gathering with minimal data."""
        gather_data = {"xp": 25}

        result = format_gathering_result(gather_data)

        assert isinstance(result, Text)
        assert "Gathering completed" in str(result)
        assert "XP gained: 25" in str(result)


class TestFormatCharacterStatus:
    """Test format_character_status function."""

    def test_format_character_status_complete(self):
        """Test formatting character status with complete data."""
        mock_character = Mock()
        mock_character.name = "testchar"
        mock_character.level = 15
        mock_character.xp = 1500
        mock_character.max_xp = 2000
        mock_character.gold = 500
        mock_character.hp = 80
        mock_character.max_hp = 100
        mock_character.mp = 40
        mock_character.max_mp = 50
        mock_character.x = 10
        mock_character.y = 20
        mock_character.cooldown = 30
        mock_character.cooldown_expiration = "2024-01-01T12:00:00Z"

        # Add skill levels
        mock_character.mining_level = 5
        mock_character.mining_xp = 250
        mock_character.mining_max_xp = 500
        mock_character.woodcutting_level = 3
        mock_character.woodcutting_xp = 150
        mock_character.woodcutting_max_xp = 300
        mock_character.fishing_level = 2
        mock_character.fishing_xp = 75
        mock_character.fishing_max_xp = 150
        mock_character.weaponcrafting_level = 1
        mock_character.weaponcrafting_xp = 25
        mock_character.weaponcrafting_max_xp = 100
        mock_character.gearcrafting_level = 1
        mock_character.gearcrafting_xp = 30
        mock_character.gearcrafting_max_xp = 100
        mock_character.jewelrycrafting_level = 0
        mock_character.jewelrycrafting_xp = 0
        mock_character.jewelrycrafting_max_xp = 100
        mock_character.cooking_level = 2
        mock_character.cooking_xp = 80
        mock_character.cooking_max_xp = 150
        mock_character.alchemy_level = 0
        mock_character.alchemy_xp = 0
        mock_character.alchemy_max_xp = 100

        # Add combat stats
        mock_character.haste = 5
        mock_character.critical_strike = 10
        mock_character.wisdom = 15
        mock_character.prospecting = 8
        mock_character.attack_fire = 20
        mock_character.attack_earth = 15
        mock_character.attack_water = 10
        mock_character.attack_air = 5
        mock_character.dmg = 5
        mock_character.dmg_fire = 10
        mock_character.dmg_earth = 8
        mock_character.dmg_water = 6
        mock_character.dmg_air = 4
        mock_character.res_fire = 12
        mock_character.res_earth = 10
        mock_character.res_water = 8
        mock_character.res_air = 6

        # Add task info
        mock_task = Mock()
        mock_task.code = "kill_wolves"
        mock_task.type = "monsters"
        mock_task.progress = 5
        mock_task.total = 10
        mock_character.task = mock_task

        # Add equipment
        mock_weapon = Mock()
        mock_weapon.code = "iron_sword"
        mock_character.weapon_slot = mock_weapon
        mock_character.shield_slot = None

        result = format_character_status(mock_character)

        assert isinstance(result, Panel)
        assert result.title == "[bold cyan]testchar's Status[/bold cyan]"

    def test_format_character_status_minimal(self):
        """Test formatting character status with minimal data."""
        mock_character = Mock()
        mock_character.name = "newchar"
        mock_character.level = 1
        mock_character.task = None

        # Mock missing attributes to return defaults
        for attr in [
            "xp",
            "max_xp",
            "gold",
            "hp",
            "max_hp",
            "mp",
            "max_mp",
            "x",
            "y",
            "cooldown",
            "cooldown_expiration",
        ]:
            if not hasattr(mock_character, attr):
                setattr(mock_character, attr, 0 if attr != "cooldown_expiration" else "N/A")

        result = format_character_status(mock_character)

        assert isinstance(result, Panel)
        assert result.title == "[bold cyan]newchar's Status[/bold cyan]"

    def test_format_character_status_no_task(self):
        """Test formatting character status with no active task."""
        mock_character = Mock()
        mock_character.name = "taskless"
        mock_character.level = 5
        mock_character.task = None

        result = format_character_status(mock_character)

        assert isinstance(result, Panel)
        assert result.title == "[bold cyan]taskless's Status[/bold cyan]"
