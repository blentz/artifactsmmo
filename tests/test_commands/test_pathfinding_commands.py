"""Tests for pathfinding commands."""

from types import SimpleNamespace
from unittest.mock import patch

from artifactsmmo_api_client.models.destination_schema import DestinationSchema

from artifactsmmo_cli.commands.action import app
from tests.test_commands.conftest import api_response, cooldown_status, unexpected_status


def character_at(x: int, y: int) -> SimpleNamespace:
    """Build a character API payload at the given position."""
    return api_response(SimpleNamespace(name="testchar", x=x, y=y))


def maps_page(tiles: list[SimpleNamespace]) -> SimpleNamespace:
    """Build a maps page API payload."""
    return api_response(SimpleNamespace(data=tiles, pages=1))


class TestGotoCommand:
    """Test goto command."""

    def test_goto_coordinates_success(self, runner, stub_api):
        """A single move is issued and reported as reaching the destination."""
        stub_api.get_character.return_value = character_at(0, 0)
        stub_api.action_move.return_value = api_response(SimpleNamespace(cooldown=None))

        result = runner.invoke(app, ["goto", "testchar", "5 5"])

        assert result.exit_code == 0
        assert "Navigation for testchar" in result.stdout
        assert "reached destination" in result.stdout
        # one move only — the server routes the full path
        stub_api.action_move.assert_called_once()
        assert stub_api.action_move.call_args.kwargs["body"] == DestinationSchema(x=5, y=5)

    def test_goto_invalid_character(self, runner, stub_api):
        """Test goto with invalid character."""
        stub_api.get_character.side_effect = unexpected_status(498, "Character not found")

        result = runner.invoke(app, ["goto", "invalidchar", "5 5"])

        assert result.exit_code == 1
        assert "Could not get character position" in result.stdout

    def test_goto_invalid_location(self, runner, stub_api):
        """Test goto with a named location the map lookup cannot resolve."""
        stub_api.get_character.return_value = character_at(0, 0)

        with patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync") as mock_maps:
            mock_maps.side_effect = unexpected_status(404, "Maps not found")

            result = runner.invoke(app, ["goto", "testchar", "invalidlocation"])

        assert result.exit_code == 1
        assert "Could not find location" in result.stdout

    def test_goto_already_at_destination(self, runner, stub_api):
        """Test goto when already at destination."""
        stub_api.get_character.return_value = character_at(5, 5)

        result = runner.invoke(app, ["goto", "testchar", "5 5"])

        assert result.exit_code == 0
        assert "already at the destination" in result.stdout
        stub_api.action_move.assert_not_called()

    @patch("time.sleep")
    def test_goto_with_cooldown_wait(self, mock_sleep, runner, stub_api):
        """On cooldown with wait enabled, the move is retried after waiting."""
        stub_api.get_character.return_value = character_at(0, 0)
        stub_api.action_move.side_effect = [
            cooldown_status(1),
            api_response(SimpleNamespace(cooldown=None)),
        ]

        result = runner.invoke(app, ["goto", "testchar", "1 1"])  # wait_cooldown defaults to True

        assert result.exit_code == 0
        assert "cooldown" in result.stdout.lower() or "waiting" in result.stdout.lower()
        assert stub_api.action_move.call_count == 2
        assert "reached destination" in result.stdout

    def test_goto_with_cooldown_no_wait(self, runner, stub_api):
        """Test goto with cooldown and no wait option."""
        stub_api.get_character.return_value = character_at(0, 0)
        stub_api.action_move.side_effect = cooldown_status(30)

        result = runner.invoke(app, ["goto", "testchar", "1 1", "--no-wait-cooldown"])

        assert result.exit_code == 0
        assert "Move blocked by cooldown" in result.stdout
        stub_api.action_move.assert_called_once()


class TestPathCommand:
    """Test path command."""

    def test_path_coordinates_success(self, runner, stub_api):
        """Test successful path command with coordinates."""
        stub_api.get_character.return_value = character_at(0, 0)

        result = runner.invoke(app, ["path", "testchar", "3 3"])

        assert result.exit_code == 0
        assert "Path for testchar" in result.stdout
        assert "Step-by-step path:" in result.stdout
        assert "1. Move to (1, 1)" in result.stdout
        assert "2. Move to (2, 2)" in result.stdout
        assert "3. Move to (3, 3)" in result.stdout
        assert "Total moves: 3" in result.stdout
        assert "Total distance: 6" in result.stdout
        assert "Estimated time: ~15 seconds" in result.stdout

    def test_path_already_at_destination(self, runner, stub_api):
        """Test path command when already at destination."""
        stub_api.get_character.return_value = character_at(5, 5)

        result = runner.invoke(app, ["path", "testchar", "5 5"])

        assert result.exit_code == 0
        assert "already at the destination" in result.stdout

    def test_path_invalid_character(self, runner, stub_api):
        """Test path command with invalid character."""
        stub_api.get_character.side_effect = unexpected_status(498, "Character not found")

        result = runner.invoke(app, ["path", "invalidchar", "5 5"])

        assert result.exit_code == 1
        assert "Could not get character position" in result.stdout

    def test_path_named_location(self, runner, stub_api):
        """Test path command with named location."""
        stub_api.get_character.return_value = character_at(0, 0)
        bank_tile = SimpleNamespace(x=4, y=1, content=SimpleNamespace(type="bank"))

        with patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync") as mock_maps:
            mock_maps.return_value = maps_page([bank_tile])

            result = runner.invoke(app, ["path", "testchar", "bank"])

        assert result.exit_code == 0
        assert "Path for testchar" in result.stdout
        assert "To: (4, 1)" in result.stdout
        assert "Total moves: 4" in result.stdout

    def test_path_invalid_location(self, runner, stub_api):
        """Test path command with a named location the map lookup cannot resolve."""
        stub_api.get_character.return_value = character_at(0, 0)

        with patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync") as mock_maps:
            mock_maps.side_effect = unexpected_status(404, "Maps not found")

            result = runner.invoke(app, ["path", "testchar", "invalidlocation"])

        assert result.exit_code == 1
        assert "Could not find location" in result.stdout
