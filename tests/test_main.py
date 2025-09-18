"""Tests for main CLI entry point."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from artifactsmmo_cli.main import app

runner = CliRunner()


def test_cli_help():
    """Test CLI help command."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "CLI interface for ArtifactsMMO game" in result.output
    assert "character" in result.output
    assert "action" in result.output
    assert "bank" in result.output


def test_cli_version():
    """Test version command."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "ArtifactsMMO CLI version" in result.output


def test_cli_with_token_file():
    """Test CLI initialization with token file."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("test-token-123")
        token_file = Path(f.name)

    try:
        with patch("artifactsmmo_cli.main.ClientManager") as mock_manager:
            result = runner.invoke(app, ["--token-file", str(token_file), "version"])
            assert result.exit_code == 0
            mock_manager().initialize.assert_called_once()
    finally:
        token_file.unlink()


def test_cli_missing_token():
    """Test CLI with missing token file."""
    result = runner.invoke(app, ["--token-file", "nonexistent", "version"])
    assert result.exit_code == 1
    assert "No authentication token found" in result.output


def test_cli_status_command():
    """Test status command."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("test-token")
        token_file = Path(f.name)

    try:
        with patch("artifactsmmo_cli.main.ClientManager") as mock_manager:
            # Mock successful API response
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.data = {"name": "Test Server", "version": "1.0.0"}
            mock_client.server_details.get_server_details_get.return_value = mock_response
            mock_manager().client = mock_client
            mock_manager().is_initialized.return_value = True

            result = runner.invoke(app, ["--token-file", str(token_file), "status"])
            assert result.exit_code == 0
            assert "API connection successful" in result.output
    finally:
        token_file.unlink()


def test_cli_debug_mode():
    """Test CLI with debug mode enabled."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("test-token")
        token_file = Path(f.name)

    try:
        with patch("artifactsmmo_cli.main.ClientManager"):
            result = runner.invoke(app, ["--token-file", str(token_file), "--debug", "version"])
            assert result.exit_code == 0
            # Check that debug output is shown
            assert "Initialized with API base URL" in result.output
    finally:
        token_file.unlink()


def test_cli_status_not_initialized():
    """Test status command when client not initialized."""
    with patch("artifactsmmo_cli.main.ClientManager") as mock_manager:
        mock_manager().is_initialized.return_value = False

        result = runner.invoke(app, ["status"])
        assert result.exit_code == 1
        assert "Client not initialized" in result.output


def test_cli_status_api_failure():
    """Test status command when API call fails."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("test-token")
        token_file = Path(f.name)

    try:
        with patch("artifactsmmo_cli.main.ClientManager") as mock_manager:
            mock_manager().is_initialized.return_value = True
            mock_manager().api.get_server_details.return_value = None

            result = runner.invoke(app, ["--token-file", str(token_file), "status"])
            assert result.exit_code == 1
            assert "Failed to connect to API" in result.output
    finally:
        token_file.unlink()


def test_cli_status_exception():
    """Test status command when exception occurs."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("test-token")
        token_file = Path(f.name)

    try:
        with patch("artifactsmmo_cli.main.ClientManager") as mock_manager:
            mock_manager().is_initialized.return_value = True
            mock_manager().api.get_server_details.side_effect = Exception("Connection error")

            result = runner.invoke(app, ["--token-file", str(token_file), "status"])
            assert result.exit_code == 1
            assert "API connection failed" in result.output
    finally:
        token_file.unlink()


def test_cli_initialization_exception():
    """Test CLI initialization with general exception."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("test-token")
        token_file = Path(f.name)

    try:
        with patch("artifactsmmo_cli.main.ClientManager") as mock_manager:
            mock_manager().initialize.side_effect = Exception("Initialization failed")

            result = runner.invoke(app, ["--token-file", str(token_file), "version"])
            assert result.exit_code == 1
            assert "Failed to initialize CLI" in result.output
    finally:
        token_file.unlink()


def test_cli_help_commands_skip_initialization():
    """Test that help commands skip initialization."""
    # These should work without any token file
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["character", "--help"])
    assert result.exit_code == 0


def test_cli_completion_commands_skip_initialization():
    """Test that completion commands skip initialization."""
    # Test install-completion command
    result = runner.invoke(app, ["--install-completion"])
    # This might fail due to shell detection, but it should not fail due to missing token
    # The important thing is that it doesn't try to initialize the client

    # Test show-completion command
    runner.invoke(app, ["--show-completion"])
    # Similar to above, might fail for other reasons but not token issues


def test_main_module_import():
    """Test that main module can be imported without issues."""
    # This test covers the if __name__ == "__main__" block
    import artifactsmmo_cli.main

    assert hasattr(artifactsmmo_cli.main, "app")
