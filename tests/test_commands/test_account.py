"""Tests for account commands."""

from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from artifactsmmo_cli.commands.account import app


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_client_manager():
    """Mock the ClientManager."""
    with patch("artifactsmmo_cli.commands.account.ClientManager") as mock:
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


class TestAccountCommands:
    """Test account command functionality."""

    def test_details_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful account details command."""
        with patch("artifactsmmo_api_client.api.my_account.get_account_details_my_details_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            mock_account = Mock()
            mock_account.username = "testuser"
            mock_account.email = "test@example.com"
            mock_account.subscribed = True
            mock_account.status = "active"
            mock_account.badges = 5

            # Mock subscription details
            mock_subscription = Mock()
            mock_subscription.type = "premium"
            mock_subscription.status = "active"
            mock_subscription.expires_at = "2024-12-31T23:59:59Z"
            mock_account.subscription = mock_subscription

            with patch("artifactsmmo_cli.commands.account.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_account)

                result = runner.invoke(app, ["details"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_details_no_subscription(self, runner, mock_client_manager, mock_api_response):
        """Test account details without subscription."""
        with patch("artifactsmmo_api_client.api.my_account.get_account_details_my_details_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            mock_account = Mock()
            mock_account.username = "testuser"
            mock_account.email = "test@example.com"
            mock_account.subscribed = False
            mock_account.status = "active"
            mock_account.badges = 2
            mock_account.subscription = None

            with patch("artifactsmmo_cli.commands.account.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_account)

                result = runner.invoke(app, ["details"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_details_error(self, runner, mock_client_manager, mock_api_response):
        """Test account details with error."""
        with patch("artifactsmmo_api_client.api.my_account.get_account_details_my_details_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.account.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, error="Access denied")

                result = runner.invoke(app, ["details"])

                assert result.exit_code == 1
                assert "Access denied" in result.stdout

    def test_logs_all_characters(self, runner, mock_client_manager, mock_api_response):
        """Test logs command for all characters."""
        with patch("artifactsmmo_api_client.api.my_characters.get_all_characters_logs_my_logs_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            mock_log = Mock()
            mock_log.character = "testchar"
            mock_log.type = "action"
            mock_log.description = "Moved to (5, 10)"
            mock_log.content = {"x": 5, "y": 10}
            mock_log.cooldown = 5
            mock_log.created_at = "2024-01-01T12:00:00Z"

            mock_data = Mock()
            mock_data.data = [mock_log]

            with patch("artifactsmmo_cli.commands.account.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["logs"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_logs_specific_character(self, runner, mock_client_manager, mock_api_response):
        """Test logs command for specific character."""
        with patch("artifactsmmo_api_client.api.my_characters.get_character_logs_my_logs_name_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            mock_log = Mock()
            mock_log.character = "testchar"
            mock_log.type = "action"
            mock_log.description = "Fought a goblin"
            mock_log.content = {"monster": "goblin", "result": "victory"}
            mock_log.cooldown = 10
            mock_log.created_at = "2024-01-01T12:05:00Z"

            mock_data = Mock()
            mock_data.data = [mock_log]

            with patch("artifactsmmo_cli.commands.account.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["logs", "--character", "testchar"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_logs_with_pagination(self, runner, mock_client_manager, mock_api_response):
        """Test logs command with pagination."""
        with patch("artifactsmmo_api_client.api.my_characters.get_all_characters_logs_my_logs_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.account.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=Mock(data=[]))

                result = runner.invoke(app, ["logs", "--page", "2", "--size", "25"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_logs_empty(self, runner, mock_client_manager, mock_api_response):
        """Test logs command with no logs."""
        with patch("artifactsmmo_api_client.api.my_characters.get_all_characters_logs_my_logs_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.account.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=Mock(data=[]))

                result = runner.invoke(app, ["logs"])

                assert result.exit_code == 0
                assert "No logs found" in result.stdout

    def test_logs_character_validation_error(self, runner):
        """Test logs command with invalid character name."""
        result = runner.invoke(app, ["logs", "--character", ""])
        assert result.exit_code == 1

    def test_logs_truncation(self, runner, mock_client_manager, mock_api_response):
        """Test logs command with long descriptions and content."""
        with patch("artifactsmmo_api_client.api.my_characters.get_all_characters_logs_my_logs_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            mock_log = Mock()
            mock_log.character = "testchar"
            mock_log.type = "action"
            mock_log.description = "A" * 50  # Long description that should be truncated
            mock_log.content = "B" * 30  # Long content that should be truncated
            mock_log.cooldown = 5
            mock_log.created_at = "2024-01-01T12:00:00Z"

            mock_data = Mock()
            mock_data.data = [mock_log]

            with patch("artifactsmmo_cli.commands.account.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["logs"])

                assert result.exit_code == 0
                # Check that truncation occurred
                assert "…" in result.stdout

    def test_api_error_handling(self, runner, mock_client_manager):
        """Test API error handling in account commands."""
        with patch("artifactsmmo_api_client.api.my_account.get_account_details_my_details_get.sync") as mock_api:
            mock_api.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.account.handle_api_error") as mock_handle:
                mock_handle.return_value = Mock(error="API Error")

                result = runner.invoke(app, ["details"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout

    def test_logs_error_response(self, runner, mock_client_manager, mock_api_response):
        """Test logs command with error response."""
        with patch("artifactsmmo_api_client.api.my_characters.get_all_characters_logs_my_logs_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.account.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, error="Could not retrieve logs")

                result = runner.invoke(app, ["logs"])

                assert result.exit_code == 0
                assert "Could not retrieve logs" in result.stdout
