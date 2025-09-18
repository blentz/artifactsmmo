"""Tests for character commands."""

from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from artifactsmmo_cli.commands.character import app


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_client_manager():
    """Mock the ClientManager."""
    with patch("artifactsmmo_cli.commands.character.ClientManager") as mock:
        mock_instance = Mock()
        mock.return_value = mock_instance
        mock_instance.api = Mock()
        mock_instance.client = Mock()
        mock_instance.client.characters = Mock()
        yield mock_instance


@pytest.fixture
def mock_api_response():
    """Mock API response."""
    mock_response = Mock()
    mock_response.status_code = 200
    return mock_response


class TestListCommand:
    """Test list command functionality."""

    def test_list_success(self, runner, mock_client_manager):
        """Test successful list command."""
        mock_character = Mock()
        mock_character.name = "testchar"
        mock_character.level = 10
        mock_character.x = 5
        mock_character.y = 10

        mock_response = Mock()
        mock_response.data = [mock_character]
        mock_client_manager.api.get_my_characters.return_value = mock_response

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0

    def test_list_no_characters(self, runner, mock_client_manager):
        """Test list command with no characters."""
        mock_response = Mock()
        mock_response.data = None
        mock_client_manager.api.get_my_characters.return_value = mock_response

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "No characters found" in result.stdout

    def test_list_empty_response(self, runner, mock_client_manager):
        """Test list command with empty response."""
        mock_client_manager.api.get_my_characters.return_value = None

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "No characters found" in result.stdout

    def test_list_api_exception(self, runner, mock_client_manager):
        """Test list command with API exception."""
        mock_client_manager.api.get_my_characters.side_effect = Exception("API Error")

        with patch("artifactsmmo_cli.commands.character.handle_api_error") as mock_error:
            mock_error.return_value = Mock(error="API Error")

            result = runner.invoke(app, ["list"])

            assert result.exit_code == 1
            assert "API Error" in result.stdout


class TestCreateCommand:
    """Test create command functionality."""

    def test_create_success(self, runner, mock_client_manager):
        """Test successful create command."""
        mock_client_manager.api.create_character.return_value = True

        result = runner.invoke(app, ["create", "newchar", "--skin", "men1"])

        assert result.exit_code == 0
        assert "Character 'newchar' created successfully" in result.stdout

    def test_create_with_skin(self, runner, mock_client_manager):
        """Test create command with custom skin."""
        mock_client_manager.api.create_character.return_value = True

        result = runner.invoke(app, ["create", "newchar", "--skin", "women2"])

        assert result.exit_code == 0
        assert "Character 'newchar' created successfully" in result.stdout

    def test_create_failure(self, runner, mock_client_manager):
        """Test create command failure."""
        mock_client_manager.api.create_character.return_value = False

        result = runner.invoke(app, ["create", "newchar", "--skin", "men1"])

        assert result.exit_code == 1
        assert "Failed to create character" in result.stdout

    def test_create_validation_error(self, runner):
        """Test create command with validation error."""
        result = runner.invoke(app, ["create", ""])
        assert result.exit_code == 1

    def test_create_api_exception(self, runner, mock_client_manager):
        """Test create command with API exception."""
        mock_client_manager.api.create_character.side_effect = Exception("API Error")

        with patch("artifactsmmo_cli.commands.character.handle_api_error") as mock_error:
            mock_error.return_value = Mock(error="API Error")

            result = runner.invoke(app, ["create", "newchar", "--skin", "men1"])

            assert result.exit_code == 1
            assert "API Error" in result.stdout


class TestDeleteCommand:
    """Test delete command functionality."""

    def test_delete_success_with_confirmation(self, runner, mock_client_manager, mock_api_response):
        """Test successful delete command with confirmation."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=True, message="Character deleted")

            with patch("typer.confirm") as mock_confirm:
                mock_confirm.return_value = True

                result = runner.invoke(app, ["delete", "testchar"])

                assert result.exit_code == 0
                assert "Character deleted" in result.stdout

    def test_delete_cancelled(self, runner, mock_client_manager):
        """Test delete command cancelled by user."""
        with patch("typer.confirm") as mock_confirm:
            mock_confirm.return_value = False

            result = runner.invoke(app, ["delete", "testchar"])

            assert result.exit_code == 0
            assert "Character deletion cancelled" in result.stdout

    def test_delete_with_yes_flag(self, runner, mock_client_manager, mock_api_response):
        """Test delete command with --yes flag."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=True, message="Character deleted")

            result = runner.invoke(app, ["delete", "testchar", "--yes"])

            assert result.exit_code == 0
            assert "Character deleted" in result.stdout

    def test_delete_error(self, runner, mock_client_manager, mock_api_response):
        """Test delete command with error."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=False, error="Character not found")

            with patch("typer.confirm") as mock_confirm:
                mock_confirm.return_value = True

                result = runner.invoke(app, ["delete", "testchar"])

                assert result.exit_code == 1
                assert "Character not found" in result.stdout

    def test_delete_validation_error(self, runner):
        """Test delete command with validation error."""
        result = runner.invoke(app, ["delete", ""])
        assert result.exit_code == 1

    def test_delete_api_exception(self, runner, mock_client_manager):
        """Test delete command with API exception."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.character.handle_api_error") as mock_error:
                mock_error.return_value = Mock(error="API Error")

                with patch("typer.confirm") as mock_confirm:
                    mock_confirm.return_value = True

                    result = runner.invoke(app, ["delete", "testchar"])

            assert result.exit_code == 1
            assert "API Error" in result.stdout


class TestCooldownCommand:
    """Test cooldown command functionality."""

    def test_cooldown_no_cooldown(self, runner, mock_client_manager, mock_api_response):
        """Test cooldown command when character has no cooldown."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_character = Mock()
            mock_character.name = "testchar"
            mock_character.cooldown = 0
            mock_character.cooldown_expiration = None
            mock_handle.return_value = Mock(success=True, data=mock_character)

            result = runner.invoke(app, ["cooldown", "testchar"])

            assert result.exit_code == 0
            assert "is not on cooldown" in result.stdout

    def test_cooldown_with_cooldown(self, runner, mock_client_manager, mock_api_response):
        """Test cooldown command when character has cooldown."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_character = Mock()
            mock_character.name = "testchar"
            mock_character.cooldown = 120  # 2 minutes
            mock_character.cooldown_expiration = "2024-01-01T12:02:00Z"
            mock_handle.return_value = Mock(success=True, data=mock_character)

            result = runner.invoke(app, ["cooldown", "testchar"])

            assert result.exit_code == 1
            assert "is on cooldown" in result.stdout
            assert "2 minutes" in result.stdout
            assert "2024-01-01 12:02:00 UTC" in result.stdout

    def test_cooldown_with_short_cooldown(self, runner, mock_client_manager, mock_api_response):
        """Test cooldown command with short cooldown (seconds only)."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_character = Mock()
            mock_character.name = "testchar"
            mock_character.cooldown = 45  # 45 seconds
            mock_character.cooldown_expiration = "2024-01-01T12:00:45Z"
            mock_handle.return_value = Mock(success=True, data=mock_character)

            result = runner.invoke(app, ["cooldown", "testchar"])

            assert result.exit_code == 1
            assert "is on cooldown" in result.stdout
            assert "45 seconds" in result.stdout

    def test_cooldown_with_long_cooldown(self, runner, mock_client_manager, mock_api_response):
        """Test cooldown command with long cooldown (hours)."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_character = Mock()
            mock_character.name = "testchar"
            mock_character.cooldown = 7265  # 2h 1m 5s
            mock_character.cooldown_expiration = "2024-01-01T14:01:05Z"
            mock_handle.return_value = Mock(success=True, data=mock_character)

            result = runner.invoke(app, ["cooldown", "testchar"])

            assert result.exit_code == 1
            assert "is on cooldown" in result.stdout
            assert "2h 1m 5s" in result.stdout

    def test_cooldown_invalid_expiration_format(self, runner, mock_client_manager, mock_api_response):
        """Test cooldown command with invalid expiration format."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_character = Mock()
            mock_character.name = "testchar"
            mock_character.cooldown = 60
            mock_character.cooldown_expiration = "invalid-date-format"
            mock_handle.return_value = Mock(success=True, data=mock_character)

            result = runner.invoke(app, ["cooldown", "testchar"])

            assert result.exit_code == 1
            assert "is on cooldown" in result.stdout
            assert "invalid-date-format" in result.stdout

    def test_cooldown_no_expiration_data(self, runner, mock_client_manager, mock_api_response):
        """Test cooldown command when expiration data is missing."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_character = Mock()
            mock_character.name = "testchar"
            mock_character.cooldown = 30
            mock_character.cooldown_expiration = None
            mock_handle.return_value = Mock(success=True, data=mock_character)

            result = runner.invoke(app, ["cooldown", "testchar"])

            assert result.exit_code == 1
            assert "is on cooldown" in result.stdout
            assert "Unknown" in result.stdout

    def test_cooldown_missing_cooldown_attr(self, runner, mock_client_manager, mock_api_response):
        """Test cooldown command when character has no cooldown attribute."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_character = Mock()
            mock_character.name = "testchar"
            # No cooldown attribute
            del mock_character.cooldown
            del mock_character.cooldown_expiration
            mock_handle.return_value = Mock(success=True, data=mock_character)

            result = runner.invoke(app, ["cooldown", "testchar"])

            assert result.exit_code == 0
            assert "is not on cooldown" in result.stdout

    def test_cooldown_character_not_found(self, runner, mock_client_manager, mock_api_response):
        """Test cooldown command with character not found."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=False, data=None, error="Character not found")

            result = runner.invoke(app, ["cooldown", "nonexistent"])

            assert result.exit_code == 1
            assert "Character not found" in result.stdout

    def test_cooldown_validation_error(self, runner):
        """Test cooldown command with validation error."""
        result = runner.invoke(app, ["cooldown", ""])
        assert result.exit_code == 1

    def test_cooldown_api_exception(self, runner, mock_client_manager):
        """Test cooldown command with API exception."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.character.handle_api_error") as mock_error:
                mock_error.return_value = Mock(error="API Error")

                result = runner.invoke(app, ["cooldown", "testchar"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout

    def test_cooldown_non_string_expiration(self, runner, mock_client_manager, mock_api_response):
        """Test cooldown command with non-string expiration value."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_character = Mock()
            mock_character.name = "testchar"
            mock_character.cooldown = 60
            mock_character.cooldown_expiration = 1234567890  # Non-string value
            mock_handle.return_value = Mock(success=True, data=mock_character)

            result = runner.invoke(app, ["cooldown", "testchar"])

            assert result.exit_code == 1
            assert "is on cooldown" in result.stdout
            assert "1234567890" in result.stdout


class TestInfoCommand:
    """Test info command functionality."""

    def test_info_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful info command."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_character = Mock()
            mock_character.name = "testchar"
            mock_character.level = 15
            mock_character.x = 10
            mock_character.y = 20
            mock_handle.return_value = Mock(success=True, data=mock_character)

            result = runner.invoke(app, ["info", "testchar"])

            assert result.exit_code == 0

    def test_info_character_not_found(self, runner, mock_client_manager, mock_api_response):
        """Test info command with character not found."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=False, data=None, error="Character not found")

            result = runner.invoke(app, ["info", "nonexistent"])

            assert result.exit_code == 1
            assert "Character not found" in result.stdout

    def test_info_validation_error(self, runner):
        """Test info command with validation error."""
        result = runner.invoke(app, ["info", ""])
        assert result.exit_code == 1

    def test_info_api_exception(self, runner, mock_client_manager):
        """Test info command with API exception."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.character.handle_api_error") as mock_error:
                mock_error.return_value = Mock(error="API Error")

                result = runner.invoke(app, ["info", "testchar"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout


class TestInventoryCommand:
    """Test inventory command functionality."""

    def test_inventory_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful inventory command."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_item = Mock()
            mock_item.slot = 1
            mock_item.code = "iron_sword"
            mock_item.quantity = 1

            mock_character = Mock()
            mock_character.name = "testchar"
            mock_character.inventory = [mock_item]
            mock_handle.return_value = Mock(success=True, data=mock_character)

            result = runner.invoke(app, ["inventory", "testchar"])

            assert result.exit_code == 0

    def test_inventory_empty(self, runner, mock_client_manager, mock_api_response):
        """Test inventory command with empty inventory."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_character = Mock()
            mock_character.name = "testchar"
            mock_character.inventory = []
            mock_handle.return_value = Mock(success=True, data=mock_character)

            result = runner.invoke(app, ["inventory", "testchar"])

            assert result.exit_code == 0
            assert "has no inventory items" in result.stdout

    def test_inventory_no_inventory_attr(self, runner, mock_client_manager, mock_api_response):
        """Test inventory command when character has no inventory attribute."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_character = Mock()
            mock_character.name = "testchar"
            # No inventory attribute
            del mock_character.inventory
            mock_handle.return_value = Mock(success=True, data=mock_character)

            result = runner.invoke(app, ["inventory", "testchar"])

            assert result.exit_code == 0
            assert "has no inventory items" in result.stdout

    def test_inventory_character_not_found(self, runner, mock_client_manager, mock_api_response):
        """Test inventory command with character not found."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=False, data=None, error="Character not found")

            result = runner.invoke(app, ["inventory", "nonexistent"])

            assert result.exit_code == 1
            assert "Character not found" in result.stdout

    def test_inventory_validation_error(self, runner):
        """Test inventory command with validation error."""
        result = runner.invoke(app, ["inventory", ""])
        assert result.exit_code == 1

    def test_inventory_api_exception(self, runner, mock_client_manager):
        """Test inventory command with API exception."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.character.handle_api_error") as mock_error:
                mock_error.return_value = Mock(error="API Error")

                result = runner.invoke(app, ["inventory", "testchar"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout


class TestStatusCommand:
    """Test status command functionality."""

    def test_status_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful status command."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
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

            mock_shield = Mock()
            mock_shield.code = "wooden_shield"
            mock_character.shield_slot = mock_shield

            mock_handle.return_value = Mock(success=True, data=mock_character)

            result = runner.invoke(app, ["status", "testchar"])

            assert result.exit_code == 0
            # Verify that the command runs successfully and shows character status
            assert "testchar's Status" in result.stdout

    def test_status_minimal_character(self, runner, mock_client_manager, mock_api_response):
        """Test status command with minimal character data."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_character = Mock()
            mock_character.name = "testchar"
            mock_character.level = 1
            mock_character.xp = 0
            mock_character.max_xp = 100
            mock_character.gold = 0
            mock_character.hp = 50
            mock_character.max_hp = 50
            mock_character.mp = 25
            mock_character.max_mp = 25
            mock_character.x = 0
            mock_character.y = 0
            mock_character.cooldown = 0
            mock_character.cooldown_expiration = None

            # Add minimal skill data (all zeros)
            for skill in [
                "mining",
                "woodcutting",
                "fishing",
                "weaponcrafting",
                "gearcrafting",
                "jewelrycrafting",
                "cooking",
                "alchemy",
            ]:
                setattr(mock_character, f"{skill}_level", 0)
                setattr(mock_character, f"{skill}_xp", 0)
                setattr(mock_character, f"{skill}_max_xp", 100)

            # Add minimal combat stats
            for stat in [
                "haste",
                "critical_strike",
                "wisdom",
                "prospecting",
                "attack_fire",
                "attack_earth",
                "attack_water",
                "attack_air",
                "dmg",
                "dmg_fire",
                "dmg_earth",
                "dmg_water",
                "dmg_air",
                "res_fire",
                "res_earth",
                "res_water",
                "res_air",
            ]:
                setattr(mock_character, stat, 0)

            # No task or equipment
            mock_character.task = None
            mock_character.weapon_slot = None
            mock_character.shield_slot = None

            mock_handle.return_value = Mock(success=True, data=mock_character)

            result = runner.invoke(app, ["status", "testchar"])

            assert result.exit_code == 0
            # Verify that the command runs successfully with minimal data
            assert "testchar's Status" in result.stdout

    def test_status_character_not_found(self, runner, mock_client_manager, mock_api_response):
        """Test status command with character not found."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=False, data=None, error="Character not found")

            result = runner.invoke(app, ["status", "nonexistent"])

            assert result.exit_code == 1
            assert "Character not found" in result.stdout

    def test_status_validation_error(self, runner):
        """Test status command with validation error."""
        result = runner.invoke(app, ["status", ""])
        assert result.exit_code == 1

    def test_status_api_exception(self, runner, mock_client_manager):
        """Test status command with API exception."""
        with patch("artifactsmmo_cli.commands.character.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.character.handle_api_error") as mock_error:
                mock_error.return_value = Mock(error="API Error")

                result = runner.invoke(app, ["status", "testchar"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout
