"""Tests for craft commands."""

from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from artifactsmmo_cli.commands.craft import app


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_client_manager():
    """Mock the ClientManager."""
    with patch("artifactsmmo_cli.commands.craft.ClientManager") as mock:
        mock_instance = Mock()
        mock.return_value = mock_instance
        mock_instance.client = Mock()
        mock_instance.api = Mock()
        yield mock_instance


@pytest.fixture
def mock_api_response():
    """Mock API response."""
    mock_response = Mock()
    mock_response.status_code = 200
    return mock_response


class TestCraftCommands:
    """Test craft command functionality."""

    def test_craft_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful craft command."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_crafting_my_name_action_crafting_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.craft.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, message="Crafting completed")

                result = runner.invoke(app, ["craft", "testchar", "iron_sword"])

                assert result.exit_code == 0
                assert "Crafting completed" in result.stdout
                mock_api.assert_called_once()

    def test_craft_with_quantity(self, runner, mock_client_manager, mock_api_response):
        """Test craft command with quantity."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_crafting_my_name_action_crafting_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.craft.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, message="Crafting completed")

                result = runner.invoke(app, ["craft", "testchar", "iron_sword", "--quantity", "5"])

                assert result.exit_code == 0
                assert "Crafting completed" in result.stdout

    def test_craft_validation_error(self, runner):
        """Test craft with invalid input."""
        result = runner.invoke(app, ["craft", "", "iron_sword"])
        assert result.exit_code == 1

    def test_recycle_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful recycle command."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_recycling_my_name_action_recycling_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.craft.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, message="Recycling completed")

                result = runner.invoke(app, ["recycle", "testchar", "iron_sword"])

                assert result.exit_code == 0
                assert "Recycling completed" in result.stdout
                mock_api.assert_called_once()

    def test_recycle_with_quantity(self, runner, mock_client_manager, mock_api_response):
        """Test recycle command with quantity."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_recycling_my_name_action_recycling_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.craft.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, message="Recycling completed")

                result = runner.invoke(app, ["recycle", "testchar", "iron_sword", "--quantity", "3"])

                assert result.exit_code == 0
                assert "Recycling completed" in result.stdout

    def test_recipes_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful recipes command."""
        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            # Mock craftable item
            mock_item = Mock()
            mock_item.code = "iron_sword"
            mock_item.craft = Mock()
            mock_item.craft.level = 10
            mock_item.craft.skill = "weaponcrafting"
            mock_item.craft.items = [Mock(code="iron_ore", quantity=2)]

            mock_data = Mock()
            mock_data.data = [mock_item]

            with patch("artifactsmmo_cli.commands.craft.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["recipes"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_recipes_with_filters(self, runner, mock_client_manager, mock_api_response):
        """Test recipes command with filters."""
        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.craft.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=Mock(data=[]))

                result = runner.invoke(app, ["recipes", "--skill", "weaponcrafting", "--level", "10"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_recipes_no_craftable_items(self, runner, mock_client_manager, mock_api_response):
        """Test recipes command with no craftable items."""
        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            # Mock non-craftable item
            mock_item = Mock()
            mock_item.code = "iron_ore"
            mock_item.craft = None

            mock_data = Mock()
            mock_data.data = [mock_item]

            with patch("artifactsmmo_cli.commands.craft.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["recipes"])

                assert result.exit_code == 0
                assert "No craftable items found" in result.stdout

    def test_cooldown_handling(self, runner, mock_client_manager, mock_api_response):
        """Test cooldown handling in craft commands."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_crafting_my_name_action_crafting_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.craft.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=45, error=None)

                result = runner.invoke(app, ["craft", "testchar", "iron_sword"])

                assert result.exit_code == 0
                assert "cooldown" in result.stdout.lower()

    def test_craft_error_response(self, runner, mock_client_manager, mock_api_response):
        """Test craft command with error response."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_crafting_my_name_action_crafting_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.craft.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=None, error="Crafting failed")

                result = runner.invoke(app, ["craft", "testchar", "iron_sword"])

                assert result.exit_code == 1
                assert "Crafting failed" in result.stdout

    def test_craft_api_exception_with_cooldown(self, runner, mock_client_manager):
        """Test craft command with API exception and cooldown."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_crafting_my_name_action_crafting_post.sync"
        ) as mock_api:
            mock_api.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.craft.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=30, error=None)

                result = runner.invoke(app, ["craft", "testchar", "iron_sword"])

                assert result.exit_code == 1

    def test_recycle_error_response(self, runner, mock_client_manager, mock_api_response):
        """Test recycle command with error response."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_recycling_my_name_action_recycling_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.craft.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=None, error="Recycling failed")

                result = runner.invoke(app, ["recycle", "testchar", "iron_sword"])

                assert result.exit_code == 1
                assert "Recycling failed" in result.stdout

    def test_recycle_api_exception_with_cooldown(self, runner, mock_client_manager):
        """Test recycle command with API exception and cooldown."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_recycling_my_name_action_recycling_post.sync"
        ) as mock_api:
            mock_api.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.craft.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=25, error=None)

                result = runner.invoke(app, ["recycle", "testchar", "iron_sword"])

                assert result.exit_code == 1

    def test_api_error_handling(self, runner, mock_client_manager):
        """Test API error handling in craft commands."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_crafting_my_name_action_crafting_post.sync"
        ) as mock_api:
            mock_api.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.craft.handle_api_error") as mock_handle:
                mock_handle.return_value = Mock(cooldown_remaining=None, error="API Error")

                result = runner.invoke(app, ["craft", "testchar", "iron_sword"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout

    def test_preview_success_can_craft(self, runner, mock_client_manager):
        """Test successful preview command when character can craft."""
        # Mock item API response
        mock_item = Mock()
        mock_item.code = "iron_sword"
        mock_item.craft = Mock()
        mock_item.craft.level = 5
        mock_item.craft.skill = "weaponcrafting"
        mock_item.craft.items = [Mock(code="iron_ore", quantity=2)]

        mock_items_data = Mock()
        mock_items_data.data = [mock_item]

        # Mock character API response
        mock_inventory_item = Mock()
        mock_inventory_item.code = "iron_ore"
        mock_inventory_item.quantity = 5

        mock_character = Mock()
        mock_character.inventory = [mock_inventory_item]
        mock_character.weaponcrafting_level = 10

        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_items_api:
            mock_items_api.return_value = Mock()

            # Mock the API wrapper's get_character method
            mock_client_manager.api.get_character.return_value = Mock()

            with patch("artifactsmmo_cli.commands.craft.handle_api_response") as mock_handle:
                mock_handle.side_effect = [
                    Mock(success=True, data=mock_items_data),  # Items response
                    Mock(success=True, data=mock_character),  # Character response
                ]

                result = runner.invoke(app, ["preview", "testchar", "iron_sword"])

                assert result.exit_code == 0
                assert "Ready to craft!" in result.stdout
                assert "✅" in result.stdout

    def test_preview_success_cannot_craft_materials(self, runner, mock_client_manager):
        """Test preview command when character lacks materials."""
        # Mock item API response
        mock_item = Mock()
        mock_item.code = "iron_sword"
        mock_item.craft = Mock()
        mock_item.craft.level = 5
        mock_item.craft.skill = "weaponcrafting"
        mock_item.craft.items = [Mock(code="iron_ore", quantity=10)]

        mock_items_data = Mock()
        mock_items_data.data = [mock_item]

        # Mock character API response - insufficient materials
        mock_inventory_item = Mock()
        mock_inventory_item.code = "iron_ore"
        mock_inventory_item.quantity = 2  # Need 10, only have 2

        mock_character = Mock()
        mock_character.inventory = [mock_inventory_item]
        mock_character.weaponcrafting_level = 10

        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_items_api:
            mock_items_api.return_value = Mock()

            # Mock the API wrapper's get_character method
            mock_client_manager.api.get_character.return_value = Mock()

            with patch("artifactsmmo_cli.commands.craft.handle_api_response") as mock_handle:
                mock_handle.side_effect = [
                    Mock(success=True, data=mock_items_data),  # Items response
                    Mock(success=True, data=mock_character),  # Character response
                ]

                result = runner.invoke(app, ["preview", "testchar", "iron_sword"])

                assert result.exit_code == 1
                assert "Cannot craft yet" in result.stdout
                assert "❌" in result.stdout

    def test_preview_success_cannot_craft_skill(self, runner, mock_client_manager):
        """Test preview command when character lacks skill level."""
        # Mock item API response
        mock_item = Mock()
        mock_item.code = "iron_sword"
        mock_item.craft = Mock()
        mock_item.craft.level = 20  # High level requirement
        mock_item.craft.skill = "weaponcrafting"
        mock_item.craft.items = [Mock(code="iron_ore", quantity=2)]

        mock_items_data = Mock()
        mock_items_data.data = [mock_item]

        # Mock character API response - sufficient materials but low skill
        mock_inventory_item = Mock()
        mock_inventory_item.code = "iron_ore"
        mock_inventory_item.quantity = 5

        mock_character = Mock()
        mock_character.inventory = [mock_inventory_item]
        mock_character.weaponcrafting_level = 5  # Need 20, only have 5

        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_items_api:
            mock_items_api.return_value = Mock()

            # Mock the API wrapper's get_character method
            mock_client_manager.api.get_character.return_value = Mock()

            with patch("artifactsmmo_cli.commands.craft.handle_api_response") as mock_handle:
                mock_handle.side_effect = [
                    Mock(success=True, data=mock_items_data),  # Items response
                    Mock(success=True, data=mock_character),  # Character response
                ]

                result = runner.invoke(app, ["preview", "testchar", "iron_sword"])

                assert result.exit_code == 1
                assert "Cannot craft yet" in result.stdout

    def test_preview_item_not_found(self, runner, mock_client_manager):
        """Test preview command with non-existent item."""
        mock_items_data = Mock()
        mock_items_data.data = []

        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_items_api:
            mock_items_api.return_value = Mock()

            with patch("artifactsmmo_cli.commands.craft.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_items_data)

                result = runner.invoke(app, ["preview", "testchar", "nonexistent_item"])

                assert result.exit_code == 1
                assert "not found" in result.stdout

    def test_preview_item_not_craftable(self, runner, mock_client_manager):
        """Test preview command with non-craftable item."""
        # Mock item without craft info
        mock_item = Mock()
        mock_item.code = "iron_ore"
        mock_item.craft = None

        mock_items_data = Mock()
        mock_items_data.data = [mock_item]

        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_items_api:
            mock_items_api.return_value = Mock()

            with patch("artifactsmmo_cli.commands.craft.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_items_data)

                result = runner.invoke(app, ["preview", "testchar", "iron_ore"])

                assert result.exit_code == 1
                assert "not craftable" in result.stdout

    def test_preview_character_not_found(self, runner, mock_client_manager):
        """Test preview command with non-existent character."""
        # Mock item API response
        mock_item = Mock()
        mock_item.code = "iron_sword"
        mock_item.craft = Mock()
        mock_item.craft.level = 5
        mock_item.craft.skill = "weaponcrafting"
        mock_item.craft.items = [Mock(code="iron_ore", quantity=2)]

        mock_items_data = Mock()
        mock_items_data.data = [mock_item]

        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_items_api:
            mock_items_api.return_value = Mock()

            # Mock the API wrapper's get_character method
            mock_client_manager.api.get_character.return_value = Mock()

            with patch("artifactsmmo_cli.commands.craft.handle_api_response") as mock_handle:
                mock_handle.side_effect = [
                    Mock(success=True, data=mock_items_data),  # Items response
                    Mock(success=False, data=None),  # Character response
                ]

                result = runner.invoke(app, ["preview", "nonexistent", "iron_sword"])

                assert result.exit_code == 1
                assert "Character 'nonexistent' not found" in result.stdout

    def test_preview_no_materials_required(self, runner, mock_client_manager):
        """Test preview command for item with no material requirements."""
        # Mock item with no materials required
        mock_item = Mock()
        mock_item.code = "simple_item"
        mock_item.craft = Mock()
        mock_item.craft.level = 1
        mock_item.craft.skill = "cooking"
        mock_item.craft.items = []  # No materials required

        mock_items_data = Mock()
        mock_items_data.data = [mock_item]

        # Mock character API response
        mock_character = Mock()
        mock_character.inventory = []
        mock_character.cooking_level = 5

        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_items_api:
            mock_items_api.return_value = Mock()

            # Mock the API wrapper's get_character method
            mock_client_manager.api.get_character.return_value = Mock()

            with patch("artifactsmmo_cli.commands.craft.handle_api_response") as mock_handle:
                mock_handle.side_effect = [
                    Mock(success=True, data=mock_items_data),  # Items response
                    Mock(success=True, data=mock_character),  # Character response
                ]

                result = runner.invoke(app, ["preview", "testchar", "simple_item"])

                assert result.exit_code == 0
                assert "Ready to craft!" in result.stdout

    def test_preview_validation_error(self, runner):
        """Test preview with invalid input."""
        result = runner.invoke(app, ["preview", "", "iron_sword"])
        assert result.exit_code == 1

    def test_preview_api_exception(self, runner, mock_client_manager):
        """Test preview command with API exception."""
        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_api:
            mock_api.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.craft.handle_api_error") as mock_handle:
                mock_handle.return_value = Mock(cooldown_remaining=None, error="API Error")

                result = runner.invoke(app, ["preview", "testchar", "iron_sword"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout
