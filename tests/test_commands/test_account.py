"""Tests for account commands."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from artifactsmmo_cli.commands.account import app
from tests.test_commands.conftest import api_error, api_response, unexpected_status


@pytest.fixture
def mock_client_manager():
    """Stub the ClientManager so commands get a fake network client."""
    with patch("artifactsmmo_cli.commands.account.ClientManager") as mock:
        mock_instance = Mock()
        mock.return_value = mock_instance
        mock_instance.client = Mock()
        yield mock_instance


def make_log(
    character="testchar",
    type="action",
    description="Moved to (5, 10)",
    content=None,
    cooldown=5,
    created_at="2024-01-01T12:00:00Z",
) -> SimpleNamespace:
    """Build a log entry shaped like the generated LogSchema."""
    return SimpleNamespace(
        character=character,
        type=type,
        description=description,
        content=content if content is not None else {"x": 5, "y": 10},
        cooldown=cooldown,
        created_at=created_at,
    )


class TestAccountCommands:
    """Test account command functionality."""

    def test_details_success(self, runner, mock_client_manager):
        """Test successful account details command."""
        account = SimpleNamespace(
            username="testuser",
            email="test@example.com",
            subscribed=True,
            status="active",
            badges=5,
            subscription=SimpleNamespace(type="premium", status="active", expires_at="2024-12-31T23:59:59Z"),
        )

        with patch("artifactsmmo_api_client.api.my_account.get_account_details_my_details_get.sync") as mock_api:
            mock_api.return_value = api_response(account)

            result = runner.invoke(app, ["details"])

            assert result.exit_code == 0
            mock_api.assert_called_once()
            assert "testuser" in result.stdout
            assert "premium" in result.stdout

    def test_details_no_subscription(self, runner, mock_client_manager):
        """Test account details without subscription."""
        # Absent badges must render as the MISSING marker, not a fabricated 0
        account = SimpleNamespace(
            username="testuser",
            email="test@example.com",
            subscribed=False,
            status="active",
            subscription=None,
        )

        with patch("artifactsmmo_api_client.api.my_account.get_account_details_my_details_get.sync") as mock_api:
            mock_api.return_value = api_response(account)

            result = runner.invoke(app, ["details"])

            assert result.exit_code == 0
            mock_api.assert_called_once()
            assert "—" in result.stdout
            assert "premium" not in result.stdout

    def test_details_error(self, runner, mock_client_manager):
        """Test account details with an API error response."""
        with patch("artifactsmmo_api_client.api.my_account.get_account_details_my_details_get.sync") as mock_api:
            mock_api.return_value = api_error(403, "Access denied")

            result = runner.invoke(app, ["details"])

            assert result.exit_code == 1
            assert "Access denied" in result.stdout

    def test_logs_all_characters(self, runner, mock_client_manager):
        """Test logs command for all characters."""
        log = make_log()

        with patch("artifactsmmo_api_client.api.my_characters.get_all_characters_logs_my_logs_get.sync") as mock_api:
            mock_api.return_value = api_response(SimpleNamespace(data=[log]))

            result = runner.invoke(app, ["logs"])

            assert result.exit_code == 0
            mock_api.assert_called_once()
            assert "testchar" in result.stdout
            assert "Moved" in result.stdout

    def test_logs_specific_character(self, runner, mock_client_manager):
        """Test logs command for specific character."""
        log = make_log(
            description="Fought a goblin",
            content={"monster": "goblin", "result": "victory"},
            cooldown=10,
            created_at="2024-01-01T12:05:00Z",
        )

        with patch("artifactsmmo_api_client.api.my_characters.get_character_logs_my_logs_name_get.sync") as mock_api:
            mock_api.return_value = api_response(SimpleNamespace(data=[log]))

            result = runner.invoke(app, ["logs", "--character", "testchar"])

            assert result.exit_code == 0
            mock_api.assert_called_once()
            assert "goblin" in result.stdout

    def test_logs_with_pagination(self, runner, mock_client_manager):
        """Test logs command with pagination."""
        with patch("artifactsmmo_api_client.api.my_characters.get_all_characters_logs_my_logs_get.sync") as mock_api:
            mock_api.return_value = api_response(SimpleNamespace(data=[]))

            result = runner.invoke(app, ["logs", "--page", "2", "--size", "25"])

            assert result.exit_code == 0
            mock_api.assert_called_once()
            assert mock_api.call_args.kwargs["page"] == 2
            assert mock_api.call_args.kwargs["size"] == 25

    def test_logs_empty(self, runner, mock_client_manager):
        """Test logs command with no logs."""
        with patch("artifactsmmo_api_client.api.my_characters.get_all_characters_logs_my_logs_get.sync") as mock_api:
            mock_api.return_value = api_response(SimpleNamespace(data=[]))

            result = runner.invoke(app, ["logs"])

            assert result.exit_code == 0
            assert "No logs found" in result.stdout

    def test_logs_character_validation_error(self, runner):
        """Test logs command with invalid character name."""
        result = runner.invoke(app, ["logs", "--character", ""])
        assert result.exit_code == 1

    def test_logs_truncation(self, runner, mock_client_manager):
        """Test logs command with long descriptions and content."""
        log = make_log(
            description="A" * 50,  # Long description that should be truncated
            content="B" * 30,  # Long content that should be truncated
        )

        with patch("artifactsmmo_api_client.api.my_characters.get_all_characters_logs_my_logs_get.sync") as mock_api:
            mock_api.return_value = api_response(SimpleNamespace(data=[log]))

            result = runner.invoke(app, ["logs"])

            assert result.exit_code == 0
            # Check that truncation occurred
            assert "…" in result.stdout

    def test_api_error_handling(self, runner, mock_client_manager):
        """Test API error handling in account commands."""
        with patch("artifactsmmo_api_client.api.my_account.get_account_details_my_details_get.sync") as mock_api:
            mock_api.side_effect = unexpected_status(500, "API Error")

            result = runner.invoke(app, ["details"])

            assert result.exit_code == 1
            assert "API Error" in result.stdout

    def test_logs_api_exception_handler(self, runner, mock_client_manager):
        """logs command outer exception handler prints the error and exits 1 (lines 125-126)."""
        with patch("artifactsmmo_api_client.api.my_characters.get_all_characters_logs_my_logs_get.sync") as mock_api:
            mock_api.side_effect = unexpected_status(500, "logs crash")

            result = runner.invoke(app, ["logs"])

            assert result.exit_code == 1
            assert "logs crash" in result.stdout

    def test_logs_error_response(self, runner, mock_client_manager):
        """Test logs command with error response."""
        with patch("artifactsmmo_api_client.api.my_characters.get_all_characters_logs_my_logs_get.sync") as mock_api:
            mock_api.return_value = api_error(404, "Could not retrieve logs")

            result = runner.invoke(app, ["logs"])

            assert result.exit_code == 0
            assert "Could not retrieve logs" in result.stdout
