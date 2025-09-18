"""Tests for pathfinding commands."""

import pytest
from unittest.mock import Mock, patch
from typer.testing import CliRunner

from artifactsmmo_cli.commands.action import app


class TestGotoCommand:
    """Test goto command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    @patch("artifactsmmo_cli.commands.action.get_character_position")
    @patch("artifactsmmo_cli.commands.action.parse_destination")
    @patch("artifactsmmo_cli.commands.action.calculate_path")
    @patch("artifactsmmo_cli.commands.action.ClientManager")
    @patch("artifactsmmo_cli.commands.action.handle_api_response")
    def test_goto_coordinates_success(
        self, mock_handle_response, mock_client_manager, mock_calculate_path, mock_parse_destination, mock_get_position
    ):
        """Test successful goto with coordinates."""
        # Mock character position - initial and final
        mock_get_position.side_effect = [(0, 0), (5, 5)]  # Start at (0,0), end at (5,5)

        # Mock destination parsing
        mock_parse_destination.return_value = (5, 5)

        # Mock path calculation
        from artifactsmmo_cli.utils.pathfinding import PathStep, PathResult

        mock_path = PathResult(steps=[PathStep(1, 1), PathStep(2, 2)], total_distance=4, estimated_time=10)
        mock_calculate_path.return_value = mock_path

        # Mock API responses
        mock_api = Mock()
        mock_client_manager.return_value.api = mock_api

        mock_cli_response = Mock()
        mock_cli_response.success = True
        mock_cli_response.cooldown_remaining = None
        mock_handle_response.return_value = mock_cli_response

        result = self.runner.invoke(app, ["goto", "testchar", "5 5"])

        assert result.exit_code == 0
        assert "Navigation for testchar" in result.stdout
        # The final position check should show success
        assert "successfully reached destination" in result.stdout

    @patch("artifactsmmo_cli.commands.action.get_character_position")
    def test_goto_invalid_character(self, mock_get_position):
        """Test goto with invalid character."""
        mock_get_position.side_effect = Exception("Character not found")

        result = self.runner.invoke(app, ["goto", "invalidchar", "5 5"])

        assert result.exit_code == 1
        assert "Could not get character position" in result.stdout

    @patch("artifactsmmo_cli.commands.action.get_character_position")
    @patch("artifactsmmo_cli.commands.action.parse_destination")
    @patch("artifactsmmo_cli.commands.action.resolve_named_location")
    def test_goto_invalid_location(self, mock_resolve_location, mock_parse_destination, mock_get_position):
        """Test goto with invalid named location."""
        mock_get_position.return_value = (0, 0)
        mock_parse_destination.return_value = "invalidlocation"
        mock_resolve_location.side_effect = Exception("Location not found")

        result = self.runner.invoke(app, ["goto", "testchar", "invalidlocation"])

        assert result.exit_code == 1
        assert "Could not find location" in result.stdout

    @patch("artifactsmmo_cli.commands.action.get_character_position")
    @patch("artifactsmmo_cli.commands.action.parse_destination")
    @patch("artifactsmmo_cli.commands.action.calculate_path")
    def test_goto_already_at_destination(self, mock_calculate_path, mock_parse_destination, mock_get_position):
        """Test goto when already at destination."""
        mock_get_position.return_value = (5, 5)
        mock_parse_destination.return_value = (5, 5)

        from artifactsmmo_cli.utils.pathfinding import PathResult

        mock_path = PathResult(steps=[], total_distance=0, estimated_time=0)
        mock_calculate_path.return_value = mock_path

        result = self.runner.invoke(app, ["goto", "testchar", "5 5"])

        assert result.exit_code == 0
        assert "already at the destination" in result.stdout

    @patch("artifactsmmo_cli.commands.action.get_character_position")
    @patch("artifactsmmo_cli.commands.action.parse_destination")
    @patch("artifactsmmo_cli.commands.action.calculate_path")
    @patch("artifactsmmo_cli.commands.action.ClientManager")
    @patch("artifactsmmo_cli.commands.action.handle_api_response")
    def test_goto_with_cooldown_wait(
        self, mock_handle_response, mock_client_manager, mock_calculate_path, mock_parse_destination, mock_get_position
    ):
        """Test goto with cooldown and wait option."""
        # Mock character position - initial and final
        mock_get_position.side_effect = [(0, 0), (1, 1)]

        # Mock destination parsing
        mock_parse_destination.return_value = (1, 1)

        # Mock path calculation
        from artifactsmmo_cli.utils.pathfinding import PathStep, PathResult

        mock_path = PathResult(steps=[PathStep(1, 1)], total_distance=2, estimated_time=5)
        mock_calculate_path.return_value = mock_path

        # Mock API responses - first with cooldown, then success
        mock_api = Mock()
        mock_client_manager.return_value.api = mock_api

        mock_cli_response_cooldown = Mock()
        mock_cli_response_cooldown.success = False
        mock_cli_response_cooldown.cooldown_remaining = 1  # 1 second cooldown

        mock_cli_response_success = Mock()
        mock_cli_response_success.success = True
        mock_cli_response_success.cooldown_remaining = None

        mock_handle_response.side_effect = [mock_cli_response_cooldown, mock_cli_response_success]

        result = self.runner.invoke(app, ["goto", "testchar", "1 1"])  # wait_cooldown defaults to True

        assert result.exit_code == 0
        # Should show cooldown message and waiting behavior
        assert "cooldown" in result.stdout.lower() or "waiting" in result.stdout.lower()

    @patch("artifactsmmo_cli.commands.action.get_character_position")
    @patch("artifactsmmo_cli.commands.action.parse_destination")
    @patch("artifactsmmo_cli.commands.action.calculate_path")
    @patch("artifactsmmo_cli.commands.action.ClientManager")
    @patch("artifactsmmo_cli.commands.action.handle_api_response")
    def test_goto_with_cooldown_no_wait(
        self, mock_handle_response, mock_client_manager, mock_calculate_path, mock_parse_destination, mock_get_position
    ):
        """Test goto with cooldown and no wait option."""
        # Mock character position
        mock_get_position.return_value = (0, 0)

        # Mock destination parsing
        mock_parse_destination.return_value = (1, 1)

        # Mock path calculation
        from artifactsmmo_cli.utils.pathfinding import PathStep, PathResult

        mock_path = PathResult(steps=[PathStep(1, 1)], total_distance=2, estimated_time=5)
        mock_calculate_path.return_value = mock_path

        # Mock API responses
        mock_api = Mock()
        mock_client_manager.return_value.api = mock_api

        mock_cli_response = Mock()
        mock_cli_response.success = False
        mock_cli_response.cooldown_remaining = 30  # 30 second cooldown
        mock_handle_response.return_value = mock_cli_response

        # Mock character position - initial and final (same since move failed)
        mock_get_position.side_effect = [(0, 0), (0, 0)]

        result = self.runner.invoke(app, ["goto", "testchar", "1 1", "--no-wait-cooldown"])

        assert result.exit_code == 0
        assert "Move blocked by cooldown" in result.stdout


class TestPathCommand:
    """Test path command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    @patch("artifactsmmo_cli.commands.action.get_character_position")
    @patch("artifactsmmo_cli.commands.action.parse_destination")
    @patch("artifactsmmo_cli.commands.action.calculate_path")
    def test_path_coordinates_success(self, mock_calculate_path, mock_parse_destination, mock_get_position):
        """Test successful path command with coordinates."""
        # Mock character position
        mock_get_position.return_value = (0, 0)

        # Mock destination parsing
        mock_parse_destination.return_value = (3, 3)

        # Mock path calculation
        from artifactsmmo_cli.utils.pathfinding import PathStep, PathResult

        mock_path = PathResult(
            steps=[PathStep(1, 1), PathStep(2, 2), PathStep(3, 3)], total_distance=6, estimated_time=15
        )
        mock_calculate_path.return_value = mock_path

        result = self.runner.invoke(app, ["path", "testchar", "3 3"])

        assert result.exit_code == 0
        assert "Path for testchar" in result.stdout
        assert "Step-by-step path:" in result.stdout
        assert "1. Move to (1, 1)" in result.stdout
        assert "2. Move to (2, 2)" in result.stdout
        assert "3. Move to (3, 3)" in result.stdout
        assert "Total moves: 3" in result.stdout
        assert "Total distance: 6" in result.stdout
        assert "Estimated time: ~15 seconds" in result.stdout

    @patch("artifactsmmo_cli.commands.action.get_character_position")
    @patch("artifactsmmo_cli.commands.action.parse_destination")
    @patch("artifactsmmo_cli.commands.action.calculate_path")
    def test_path_already_at_destination(self, mock_calculate_path, mock_parse_destination, mock_get_position):
        """Test path command when already at destination."""
        mock_get_position.return_value = (5, 5)
        mock_parse_destination.return_value = (5, 5)

        from artifactsmmo_cli.utils.pathfinding import PathResult

        mock_path = PathResult(steps=[], total_distance=0, estimated_time=0)
        mock_calculate_path.return_value = mock_path

        result = self.runner.invoke(app, ["path", "testchar", "5 5"])

        assert result.exit_code == 0
        assert "already at the destination" in result.stdout

    @patch("artifactsmmo_cli.commands.action.get_character_position")
    def test_path_invalid_character(self, mock_get_position):
        """Test path command with invalid character."""
        mock_get_position.side_effect = Exception("Character not found")

        result = self.runner.invoke(app, ["path", "invalidchar", "5 5"])

        assert result.exit_code == 1
        assert "Could not get character position" in result.stdout

    @patch("artifactsmmo_cli.commands.action.get_character_position")
    @patch("artifactsmmo_cli.commands.action.parse_destination")
    @patch("artifactsmmo_cli.commands.action.resolve_named_location")
    def test_path_named_location(self, mock_resolve_location, mock_parse_destination, mock_get_position):
        """Test path command with named location."""
        mock_get_position.return_value = (0, 0)
        mock_parse_destination.return_value = "bank"
        mock_resolve_location.return_value = (4, 1)

        with patch("artifactsmmo_cli.commands.action.calculate_path") as mock_calculate_path:
            from artifactsmmo_cli.utils.pathfinding import PathStep, PathResult

            mock_path = PathResult(
                steps=[PathStep(1, 0), PathStep(2, 0), PathStep(3, 0), PathStep(4, 0), PathStep(4, 1)],
                total_distance=5,
                estimated_time=25,
            )
            mock_calculate_path.return_value = mock_path

            result = self.runner.invoke(app, ["path", "testchar", "bank"])

            assert result.exit_code == 0
            assert "Path for testchar" in result.stdout
            assert "To: (4, 1)" in result.stdout

    @patch("artifactsmmo_cli.commands.action.get_character_position")
    @patch("artifactsmmo_cli.commands.action.parse_destination")
    @patch("artifactsmmo_cli.commands.action.resolve_named_location")
    def test_path_invalid_location(self, mock_resolve_location, mock_parse_destination, mock_get_position):
        """Test path command with invalid named location."""
        mock_get_position.return_value = (0, 0)
        mock_parse_destination.return_value = "invalidlocation"
        mock_resolve_location.side_effect = Exception("Location not found")

        result = self.runner.invoke(app, ["path", "testchar", "invalidlocation"])

        assert result.exit_code == 1
        assert "Could not find location" in result.stdout
