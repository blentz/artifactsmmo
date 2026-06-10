"""Tests for craft commands."""

from unittest.mock import Mock, patch

from artifactsmmo_api_client.types import UNSET

from artifactsmmo_cli.commands.craft import app
from tests.test_commands.conftest import api_error, api_response, cooldown_status, unexpected_status


class TestCraftCommands:
    """Test craft command functionality."""

    def test_craft_success(self, runner, stub_api):
        """Test successful craft command."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_crafting_my_name_action_crafting_post.sync"
        ) as mock_api:
            mock_api.return_value = api_response(Mock())

            result = runner.invoke(app, ["craft", "testchar", "iron_sword"])

            assert result.exit_code == 0
            assert "Crafted 1x iron_sword" in result.stdout
            mock_api.assert_called_once()

    def test_craft_with_quantity(self, runner, stub_api):
        """Test craft command with quantity."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_crafting_my_name_action_crafting_post.sync"
        ) as mock_api:
            mock_api.return_value = api_response(Mock())

            result = runner.invoke(app, ["craft", "testchar", "iron_sword", "--quantity", "5"])

            assert result.exit_code == 0
            assert "Crafted 5x iron_sword" in result.stdout
            assert mock_api.call_args.kwargs["body"].quantity == 5

    def test_craft_validation_error(self, runner):
        """Test craft with invalid input."""
        result = runner.invoke(app, ["craft", "", "iron_sword"])
        assert result.exit_code == 2

    def test_recycle_success(self, runner, stub_api):
        """Test successful recycle command."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_recycling_my_name_action_recycling_post.sync"
        ) as mock_api:
            mock_api.return_value = api_response(Mock())

            result = runner.invoke(app, ["recycle", "testchar", "iron_sword"])

            assert result.exit_code == 0
            assert "Recycled 1x iron_sword" in result.stdout
            mock_api.assert_called_once()

    def test_recycle_with_quantity(self, runner, stub_api):
        """Test recycle command with quantity."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_recycling_my_name_action_recycling_post.sync"
        ) as mock_api:
            mock_api.return_value = api_response(Mock())

            result = runner.invoke(app, ["recycle", "testchar", "iron_sword", "--quantity", "3"])

            assert result.exit_code == 0
            assert "Recycled 3x iron_sword" in result.stdout

    def test_recipes_success(self, runner, stub_api):
        """Test successful recipes command."""
        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_api:
            # Mock craftable item
            mock_item = Mock()
            mock_item.code = "iron_sword"
            mock_item.craft = Mock()
            mock_item.craft.level = 10
            mock_item.craft.skill = "weaponcrafting"
            mock_item.craft.items = [Mock(code="iron_ore", quantity=2)]

            mock_data = Mock()
            mock_data.data = [mock_item]

            mock_api.return_value = api_response(mock_data)

            result = runner.invoke(app, ["recipes"])

            assert result.exit_code == 0
            mock_api.assert_called_once()
            assert "iron_sword" in result.stdout

    def test_recipes_with_filters(self, runner, stub_api):
        """Test recipes command with filters."""
        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_api:
            mock_api.return_value = api_response(Mock(data=[]))

            result = runner.invoke(app, ["recipes", "--skill", "weaponcrafting", "--level", "10"])

            assert result.exit_code == 0
            mock_api.assert_called_once()

    def test_recipes_no_craftable_items(self, runner, stub_api):
        """Test recipes command with no craftable items."""
        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_api:
            # Mock non-craftable item
            mock_item = Mock()
            mock_item.code = "iron_ore"
            mock_item.craft = None

            mock_data = Mock()
            mock_data.data = [mock_item]

            mock_api.return_value = api_response(mock_data)

            result = runner.invoke(app, ["recipes"])

            assert result.exit_code == 0
            assert "No craftable items found" in result.stdout

    def test_recipes_missing_fields_render_marker(self, runner, stub_api):
        """Test recipes renders the MISSING marker when API recipe fields are absent."""
        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_api:
            mock_item = Mock()
            mock_item.code = None
            mock_item.craft = Mock()
            mock_item.craft.level = None
            mock_item.craft.skill = None
            mock_item.craft.items = [Mock(code=None, quantity=None)]

            mock_data = Mock()
            mock_data.data = [mock_item]

            mock_api.return_value = api_response(mock_data)

            result = runner.invoke(app, ["recipes"])

            assert result.exit_code == 0
            assert "—" in result.stdout

    def test_craft_error_response(self, runner, stub_api):
        """Test craft command with error response."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_crafting_my_name_action_crafting_post.sync"
        ) as mock_api:
            mock_api.return_value = api_error(422, "Crafting failed")

            result = runner.invoke(app, ["craft", "testchar", "iron_sword"])

            assert result.exit_code == 1
            assert "Crafting failed" in result.stdout

    def test_craft_api_exception_with_cooldown(self, runner, stub_api):
        """Test craft command with API cooldown error (499)."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_crafting_my_name_action_crafting_post.sync"
        ) as mock_api:
            mock_api.side_effect = cooldown_status(30)

            result = runner.invoke(app, ["craft", "testchar", "iron_sword"])

            assert result.exit_code == 1
            assert "30" in result.stdout
            assert "cooldown" in result.stdout.lower()

    def test_recycle_error_response(self, runner, stub_api):
        """Test recycle command with error response."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_recycling_my_name_action_recycling_post.sync"
        ) as mock_api:
            mock_api.return_value = api_error(473, "Recycling failed")

            result = runner.invoke(app, ["recycle", "testchar", "iron_sword"])

            assert result.exit_code == 1
            assert "Recycling failed" in result.stdout

    def test_recycle_api_exception_with_cooldown(self, runner, stub_api):
        """Test recycle command with API cooldown error (499)."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_recycling_my_name_action_recycling_post.sync"
        ) as mock_api:
            mock_api.side_effect = cooldown_status(25)

            result = runner.invoke(app, ["recycle", "testchar", "iron_sword"])

            assert result.exit_code == 1
            assert "25" in result.stdout

    def test_api_error_handling(self, runner, stub_api):
        """Test API error handling in craft commands."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_crafting_my_name_action_crafting_post.sync"
        ) as mock_api:
            mock_api.side_effect = unexpected_status(500, "API Error")

            result = runner.invoke(app, ["craft", "testchar", "iron_sword"])

            assert result.exit_code == 1
            assert "API Error" in result.stdout

    def test_preview_success_can_craft(self, runner, stub_api):
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
            mock_items_api.return_value = api_response(mock_items_data)
            stub_api.get_character.return_value = api_response(mock_character)

            result = runner.invoke(app, ["preview", "testchar", "iron_sword"])

            assert result.exit_code == 0
            assert "Ready to craft!" in result.stdout
            assert "✅" in result.stdout

    def test_preview_success_cannot_craft_materials(self, runner, stub_api):
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
            mock_items_api.return_value = api_response(mock_items_data)
            stub_api.get_character.return_value = api_response(mock_character)

            result = runner.invoke(app, ["preview", "testchar", "iron_sword"])

            assert result.exit_code == 1
            assert "Cannot craft yet" in result.stdout
            assert "❌" in result.stdout

    def test_preview_success_cannot_craft_skill(self, runner, stub_api):
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
            mock_items_api.return_value = api_response(mock_items_data)
            stub_api.get_character.return_value = api_response(mock_character)

            result = runner.invoke(app, ["preview", "testchar", "iron_sword"])

            assert result.exit_code == 1
            assert "Cannot craft yet" in result.stdout

    def test_preview_item_not_found(self, runner, stub_api):
        """Test preview command with non-existent item."""
        mock_items_data = Mock()
        mock_items_data.data = []

        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_items_api:
            mock_items_api.return_value = api_response(mock_items_data)

            result = runner.invoke(app, ["preview", "testchar", "nonexistent_item"])

            assert result.exit_code == 1
            assert "not found" in result.stdout

    def test_preview_item_not_craftable(self, runner, stub_api):
        """Test preview command with non-craftable item."""
        # Mock item without craft info
        mock_item = Mock()
        mock_item.code = "iron_ore"
        mock_item.craft = None

        mock_items_data = Mock()
        mock_items_data.data = [mock_item]

        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_items_api:
            mock_items_api.return_value = api_response(mock_items_data)

            result = runner.invoke(app, ["preview", "testchar", "iron_ore"])

            assert result.exit_code == 1
            assert "not craftable" in result.stdout

    def test_preview_character_not_found(self, runner, stub_api):
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
            mock_items_api.return_value = api_response(mock_items_data)
            stub_api.get_character.return_value = api_error(498, "Character not found")

            result = runner.invoke(app, ["preview", "nonexistent", "iron_sword"])

            assert result.exit_code == 1
            assert "Character 'nonexistent' not found" in result.stdout

    def test_preview_no_materials_required(self, runner, stub_api):
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
            mock_items_api.return_value = api_response(mock_items_data)
            stub_api.get_character.return_value = api_response(mock_character)

            result = runner.invoke(app, ["preview", "testchar", "simple_item"])

            assert result.exit_code == 0
            assert "Ready to craft!" in result.stdout

    def test_preview_validation_error(self, runner):
        """Test preview with invalid input."""
        result = runner.invoke(app, ["preview", "", "iron_sword"])
        assert result.exit_code == 2

    def test_preview_api_exception(self, runner, stub_api):
        """Test preview command with API exception."""
        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_api:
            mock_api.side_effect = unexpected_status(500, "API Error")

            result = runner.invoke(app, ["preview", "testchar", "iron_sword"])

            assert result.exit_code == 1
            assert "API Error" in result.stdout


class TestCraftUncoveredBranches:
    """Drive the remaining craft/recycle/preview/recipes branches."""

    def test_recycle_api_exception_no_cooldown(self, runner, stub_api):
        """Recycle except-branch with no cooldown prints the error (line 104)."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_recycling_my_name_action_recycling_post.sync"
        ) as mock_api:
            mock_api.side_effect = unexpected_status(500, "Recycle boom")

            result = runner.invoke(app, ["recycle", "testchar", "iron_sword"])

            assert result.exit_code == 1
            assert "Recycle boom" in result.stdout

    def test_preview_items_response_unsuccessful(self, runner, stub_api):
        """Preview reports not found when the items response is unsuccessful (lines 131-132)."""
        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_api:
            mock_api.return_value = api_error(500, "items lookup failed")

            result = runner.invoke(app, ["preview", "testchar", "iron_sword"])

            assert result.exit_code == 1
            assert "Item 'iron_sword' not found" in result.stdout

    def test_preview_no_matching_item_code(self, runner, stub_api):
        """Preview reports not found when results lack the requested code (lines 147-148)."""
        # API returns items, but none whose code matches the requested item.
        other_item = Mock()
        other_item.code = "copper_ore"

        items_data = Mock()
        items_data.data = [other_item]

        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_api:
            mock_api.return_value = api_response(items_data)

            result = runner.invoke(app, ["preview", "testchar", "iron_sword"])

            assert result.exit_code == 1
            assert "Item 'iron_sword' not found" in result.stdout

    def test_recipes_invalid_skill_falls_back_to_unset(self, runner, stub_api):
        """An unrecognized --skill is swallowed into UNSET, not an error (lines 275-277)."""
        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_api:
            mock_api.return_value = api_response(Mock(data=[]))

            result = runner.invoke(app, ["recipes", "--skill", "not_a_real_skill"])

            # Invalid skill does not abort; the items endpoint is still queried.
            assert result.exit_code == 0
            mock_api.assert_called_once()
            assert mock_api.call_args.kwargs["craft_skill"] is UNSET

    def test_recipes_unsuccessful_response(self, runner, stub_api):
        """Recipes prints the retrieve error when the response is unsuccessful (line 326)."""
        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_api:
            mock_api.return_value = api_error(500, "recipe lookup failed")

            result = runner.invoke(app, ["recipes"])

            assert result.exit_code == 0
            assert "recipe lookup failed" in result.stdout

    def test_recipes_api_exception(self, runner, stub_api):
        """Recipes except-branch prints the error and exits 1 (lines 328-331)."""
        with patch("artifactsmmo_api_client.api.items.get_all_items_items_get.sync") as mock_api:
            mock_api.side_effect = unexpected_status(500, "Recipes boom")

            result = runner.invoke(app, ["recipes"])

            assert result.exit_code == 1
            assert "Recipes boom" in result.stdout
