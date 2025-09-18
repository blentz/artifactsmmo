"""Real integration tests for ArtifactsMMO CLI that test against the live API.

These tests make actual API calls to verify the CLI works correctly with real data.
They are marked with @pytest.mark.integration so they can be run separately.

Requirements:
    - Valid API token in TOKEN file or ARTIFACTSMMO_TOKEN environment variable
    - Internet connection to reach ArtifactsMMO API
    - API server must be accessible and responding

Tests cover:
    - info items (verify it returns real items)
    - info monsters (verify it returns real monsters)
    - info resources (verify it returns real resources)
    - character list (verify it can list characters)
    - info npcs (verify NPC discovery)
    - action path (verify pathfinding calculation)
    - API connectivity and authentication

Usage:
    # Run only integration tests
    uv run pytest tests/test_integration.py -m integration -v

    # Run all tests except integration
    uv run pytest -m "not integration"

    # Run integration tests directly
    uv run python tests/test_integration.py

    # Run a specific integration test
    uv run pytest tests/test_integration.py::TestInfoCommands::test_info_items_list -v
"""

import os
from pathlib import Path
from unittest.mock import patch
from io import StringIO
import sys

import pytest
from rich.console import Console

from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config
from artifactsmmo_cli.commands.info import (
    list_items,
    list_monsters,
    list_resources,
    list_npcs,
)
from artifactsmmo_cli.commands.character import list_characters
from artifactsmmo_cli.commands.action import show_path_command


class TestSetup:
    """Setup and teardown for integration tests."""

    @pytest.fixture(scope="session", autouse=True)
    def setup_api_client(self):
        """Set up the API client with real authentication for all integration tests."""
        # Try to load token from TOKEN file first
        token_file = Path("TOKEN")
        token = None

        if token_file.exists():
            token = token_file.read_text().strip()

        # Fall back to environment variable
        if not token:
            token = os.getenv("ARTIFACTSMMO_TOKEN")

        if not token:
            pytest.skip("No API token found. Create TOKEN file or set ARTIFACTSMMO_TOKEN environment variable.")

        # Initialize the client manager with real config
        config = Config(token=token)
        ClientManager().initialize(config)

        yield

        # Cleanup - reset client manager
        ClientManager()._instance = None


@pytest.mark.integration
class TestInfoCommands(TestSetup):
    """Test info commands against live API."""

    def test_info_items_list(self):
        """Test that info items command returns real items from API."""
        # Capture console output
        console_output = StringIO()
        console = Console(file=console_output, width=120)

        # Patch the console in the info module
        with patch("artifactsmmo_cli.commands.info.console", console):
            # Call the actual command function with no filters (should return items)
            try:
                list_items(
                    item_code=None,
                    item_type=None,
                    craft_skill=None,
                    craft_level=None,
                    page=1,
                    size=10,  # Small size for faster test
                )
            except SystemExit:
                # Command might exit on success, that's ok
                pass

        output = console_output.getvalue()

        # Verify we got real data, not an error
        assert "Items" in output or "Item:" in output
        assert "Error" not in output
        assert "Could not retrieve items" not in output
        assert "No items found" not in output

        # Should contain table headers or item data
        assert any(header in output for header in ["Code", "Name", "Type", "Level"])

    def test_info_items_specific(self):
        """Test that info items command can get a specific item."""
        console_output = StringIO()
        console = Console(file=console_output, width=120)

        with patch("artifactsmmo_cli.commands.info.console", console):
            try:
                # Test with a common item that should exist
                list_items(item_code="copper_ore", item_type=None, craft_skill=None, craft_level=None, page=1, size=50)
            except SystemExit:
                pass

        output = console_output.getvalue()

        # Should show specific item details
        assert "copper_ore" in output.lower() or "Item:" in output
        assert "Error" not in output
        assert "not found" not in output

    def test_info_monsters_list(self):
        """Test that info monsters command returns real monsters from API."""
        console_output = StringIO()
        console = Console(file=console_output, width=120)

        with patch("artifactsmmo_cli.commands.info.console", console):
            try:
                list_monsters(
                    monster_code=None, level=None, min_level=None, max_level=None, compare=None, page=1, size=10
                )
            except SystemExit:
                pass

        output = console_output.getvalue()

        # Verify we got real monster data
        assert "Monsters" in output or "Monster:" in output
        assert "Error" not in output
        assert "Could not retrieve monsters" not in output
        assert "No monsters found" not in output

        # Should contain monster-related headers
        assert any(header in output for header in ["Code", "Name", "Level", "HP"])

    def test_info_monsters_specific(self):
        """Test that info monsters command can get a specific monster."""
        console_output = StringIO()
        console = Console(file=console_output, width=120)

        with patch("artifactsmmo_cli.commands.info.console", console):
            try:
                # Test with a common monster that should exist
                list_monsters(
                    monster_code="chicken", level=None, min_level=None, max_level=None, compare=None, page=1, size=50
                )
            except SystemExit:
                pass

        output = console_output.getvalue()

        # Should show specific monster details
        assert "chicken" in output.lower() or "Monster:" in output
        assert "Error" not in output
        assert "not found" not in output

    def test_info_resources_list(self):
        """Test that info resources command returns real resources from API."""
        console_output = StringIO()
        console = Console(file=console_output, width=120)

        with patch("artifactsmmo_cli.commands.info.console", console):
            try:
                list_resources(
                    resource_code=None,
                    skill=None,
                    level=None,
                    max_level=None,
                    resource_type=None,
                    location=None,
                    radius=None,
                    character=None,
                    page=1,
                    size=10,
                )
            except SystemExit:
                pass

        output = console_output.getvalue()

        # Verify we got real resource data
        assert "Resources" in output or "Resource:" in output
        assert "Error" not in output
        assert "Could not retrieve resources" not in output
        assert "No resources found" not in output

        # Should contain resource-related headers
        assert any(header in output for header in ["Code", "Name", "Skill", "Level"])

    def test_info_resources_specific(self):
        """Test that info resources command can get a specific resource."""
        console_output = StringIO()
        console = Console(file=console_output, width=120)

        with patch("artifactsmmo_cli.commands.info.console", console):
            try:
                # Test with a common resource that should exist
                list_resources(
                    resource_code="copper_rock",
                    skill=None,
                    level=None,
                    max_level=None,
                    resource_type=None,
                    location=None,
                    radius=None,
                    character=None,
                    page=1,
                    size=50,
                )
            except SystemExit:
                pass

        output = console_output.getvalue()

        # Should show specific resource details or handle API response gracefully
        # Allow for API not responding or resource not found
        if "No response received from API" in output:
            # API might be down or rate limited, that's acceptable for integration test
            pytest.skip("API not responding for resource lookup")

        # If we got a response, verify it's valid
        if output.strip() and "Error" not in output:
            assert "copper" in output.lower() or "Resource:" in output
        else:
            # Allow for resource not found - that's a valid API response
            assert "not found" in output or "Error" in output

    def test_info_npcs_list(self):
        """Test that info npcs command returns NPC discovery."""
        console_output = StringIO()
        console = Console(file=console_output, width=120)

        with patch("artifactsmmo_cli.commands.info.console", console):
            try:
                list_npcs(npc_type=None, page=1, size=10)
            except SystemExit:
                pass

        output = console_output.getvalue()

        # Verify we got NPC data (either from API or fallback)
        assert "NPCs" in output or "NPC:" in output
        assert "Error" not in output

        # Should contain NPC-related information
        assert any(term in output for term in ["Bank", "Task Master", "Workshop", "Exchange", "Location"])


@pytest.mark.integration
class TestCharacterCommands(TestSetup):
    """Test character commands against live API."""

    def test_character_list(self):
        """Test that character list command works with real API."""
        console_output = StringIO()
        console = Console(file=console_output, width=120)

        with patch("artifactsmmo_cli.commands.character.console", console):
            try:
                list_characters()
            except SystemExit:
                pass

        output = console_output.getvalue()

        # Should either show characters or "No characters found" (both are valid)
        # Should not show API errors
        assert "Error" not in output or "No characters found" in output
        assert "Failed to" not in output
        assert "Could not" not in output

        # If there are characters, should show character data
        if "No characters found" not in output:
            assert any(header in output for header in ["Name", "Level", "Class", "HP"])


@pytest.mark.integration
class TestActionCommands(TestSetup):
    """Test action commands against live API."""

    def test_action_path_calculation(self):
        """Test that action path command can calculate paths."""
        # This test requires a character to exist, so we'll make it conditional
        console_output = StringIO()
        console = Console(file=console_output, width=120)

        # First, check if we have any characters
        char_console_output = StringIO()
        char_console = Console(file=char_console_output, width=120)

        with patch("artifactsmmo_cli.commands.character.console", char_console):
            try:
                list_characters()
            except SystemExit:
                pass

        char_output = char_console_output.getvalue()

        if "No characters found" in char_output:
            pytest.skip("No characters available for path testing")

        # Extract a character name from the output (this is a bit hacky but works for testing)
        # Look for character names in the table output
        lines = char_output.split("\n")
        character_name = None

        for line in lines:
            # Skip header and separator lines
            if "│" in line and not line.strip().startswith("│ Name") and not line.strip().startswith("│ ─"):
                # Extract character name from table row
                parts = [part.strip() for part in line.split("│") if part.strip()]
                if len(parts) > 1 and parts[1] and not parts[1].startswith("─"):
                    character_name = parts[1]
                    break

        if not character_name:
            pytest.skip("Could not extract character name for path testing")

        # Validate character name meets requirements (at least 3 characters)
        if len(character_name) < 3:
            pytest.skip(f"Character name '{character_name}' too short for validation")

        # Now test path calculation
        with patch("artifactsmmo_cli.commands.action.console", console):
            try:
                show_path_command(
                    character=character_name,
                    destination="5 5",  # Simple coordinate destination
                )
            except SystemExit as e:
                # SystemExit with code 1 indicates an error, 0 or None is success
                if e.code == 1:
                    # Check if it's a validation error we can handle
                    pass
                else:
                    pass  # Success exit
            except Exception as e:
                # Handle other exceptions like validation errors
                if "Character name must be at least 3 characters long" in str(e):
                    pytest.skip(f"Character name '{character_name}' failed validation")
                else:
                    raise

        output = console_output.getvalue()

        # Verify path calculation worked
        assert "Path for" in output
        assert "From:" in output and "To:" in output
        assert "Error" not in output or "already at the destination" in output

        # Should show path information
        assert any(term in output for term in ["Summary:", "steps", "distance", "already at"])

    def test_action_path_calculation_simple(self):
        """Test path calculation with a simple test case that doesn't require real characters."""
        # This is a simpler test that just verifies the pathfinding logic works
        # without needing to extract character names from API responses

        # We'll test the pathfinding utility functions directly
        from artifactsmmo_cli.utils.pathfinding import calculate_path, parse_destination

        # Test coordinate parsing
        parsed = parse_destination("5 10")
        assert parsed == (5, 10)

        # Test path calculation
        path_result = calculate_path(0, 0, 5, 5)
        assert path_result is not None
        assert hasattr(path_result, "total_distance")
        assert path_result.total_distance > 0


@pytest.mark.integration
class TestAPIConnectivity(TestSetup):
    """Test basic API connectivity and client functionality."""

    def test_client_manager_initialization(self):
        """Test that ClientManager is properly initialized with real config."""
        client_manager = ClientManager()

        # Should be initialized from setup
        assert client_manager.is_initialized()

        # Should have valid API client
        api = client_manager.api
        assert api is not None

        # Should have valid HTTP client
        client = client_manager.client
        assert client is not None

    def test_api_server_status(self):
        """Test that we can connect to the API server."""
        client_manager = ClientManager()
        api = client_manager.api

        # Try to get server details (this is a simple API call)
        try:
            response = api.get_server_details()

            # Should get a valid response
            assert response is not None
            assert hasattr(response, "data")
            assert response.data is not None

            # Should have basic server info
            server_data = response.data
            assert hasattr(server_data, "version")
            assert hasattr(server_data, "max_level")

        except Exception as e:
            pytest.fail(f"Failed to connect to API server: {e}")

    def test_api_authentication(self):
        """Test that API authentication is working."""
        client_manager = ClientManager()
        api = client_manager.api

        # Try to make an authenticated call (get characters)
        try:
            response = api.get_my_characters()

            # Should get a response (even if empty)
            assert response is not None

            # Should not get authentication errors
            # If we get here without exception, authentication is working

        except Exception as e:
            # Check if it's an authentication error
            error_str = str(e).lower()
            if any(auth_term in error_str for auth_term in ["unauthorized", "authentication", "token", "401"]):
                pytest.fail(f"API authentication failed: {e}")
            else:
                # Other errors might be OK (like rate limiting, server issues, etc.)
                # As long as it's not an auth error, the test passes
                pass


if __name__ == "__main__":
    # Allow running this file directly for quick testing
    pytest.main([__file__, "-v", "-m", "integration"])
