"""Test error code handling for ArtifactsMMO specific response codes."""

import pytest
from unittest.mock import Mock

from artifactsmmo_cli.utils.helpers import get_error_message, handle_api_error
from artifactsmmo_cli.models.responses import CLIResponse


class TestErrorCodes:
    """Test ArtifactsMMO error code handling."""

    def test_get_error_message_known_codes(self):
        """Test that known error codes return proper messages."""
        # Test some common error codes
        assert get_error_message(478) == "Missing required items or materials"
        assert get_error_message(499) == "Character is on cooldown"
        assert get_error_message(598) == "Wrong location for this action - content not found at this location"
        assert get_error_message(492) == "Insufficient gold"
        assert get_error_message(497) == "Character inventory is full"
        assert get_error_message(490) == "Character is already at this location"

    def test_get_error_message_unknown_code(self):
        """Test that unknown error codes return generic message."""
        assert get_error_message(9999) == "Unknown error (code: 9999)"
        assert get_error_message(1234) == "Unknown error (code: 1234)"

    def test_handle_api_error_with_valueerror(self):
        """Test handling of ValueError from non-standard HTTP status codes."""
        # Test error 478 (missing materials)
        error = ValueError("478 is not a valid HTTPStatus")
        response = handle_api_error(error)
        assert isinstance(response, CLIResponse)
        assert not response.success
        assert response.error == "Missing required items or materials"

        # Test error 598 (wrong location)
        error = ValueError("598 is not a valid HTTPStatus")
        response = handle_api_error(error)
        assert response.error == "Wrong location for this action - content not found at this location"

        # Test error 499 (cooldown)
        error = ValueError("499 is not a valid HTTPStatus")
        response = handle_api_error(error)
        assert response.error == "Character is on cooldown"

    def test_handle_api_error_with_invalid_valueerror(self):
        """Test handling of ValueError that doesn't match pattern."""
        error = ValueError("Some other error")
        response = handle_api_error(error)
        assert isinstance(response, CLIResponse)
        assert not response.success
        assert "Unexpected error: Some other error" in response.error

    def test_all_documented_error_codes_have_messages(self):
        """Verify all documented error codes have messages."""
        # List of all documented error codes from ArtifactsMMO
        documented_codes = [
            # General
            422,
            429,
            404,
            500,
            # Email token
            560,
            561,
            562,
            # Account
            451,
            452,
            453,
            454,
            455,
            456,
            457,
            458,
            459,
            550,
            # Character
            474,
            475,
            478,
            483,
            484,
            485,
            486,
            487,
            488,
            489,
            490,
            491,
            492,
            493,
            494,
            495,
            496,
            497,
            498,
            499,
            # Item
            471,
            472,
            473,
            476,
            # Grand Exchange
            431,
            433,
            434,
            435,
            436,
            437,
            438,
            479,
            480,
            482,
            # Bank
            460,
            461,
            462,
            # Maps
            597,
            598,
            # NPC
            441,
            442,
        ]

        for code in documented_codes:
            message = get_error_message(code)
            # Should not return the generic unknown error message
            assert f"Unknown error (code: {code})" != message, f"Missing message for documented code {code}"
            # Should have a meaningful message
            assert len(message) > 10, f"Message too short for code {code}: {message}"
