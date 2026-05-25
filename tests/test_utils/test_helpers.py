"""Tests for helper utilities."""

import json
from unittest.mock import Mock, patch

import httpx
import pytest
from artifactsmmo_api_client.errors import UnexpectedStatus
from artifactsmmo_api_client.models.error_response_schema import ErrorResponseSchema
from artifactsmmo_api_client.models.error_schema import ErrorSchema

from artifactsmmo_cli.utils.helpers import (
    extract_character_data,
    extract_cooldown_info,
    format_coordinates,
    handle_api_error,
    handle_api_response,
    parse_coordinates,
    safe_get,
)


class TestHandleApiResponse:
    """Test handle_api_response function."""

    def test_handle_none_response(self):
        """Test handling None response."""
        result = handle_api_response(None)

        assert not result.success
        assert result.error == "No response received from API"

    def test_handle_response_with_data_attribute(self):
        """Test handling response with data attribute."""
        mock_response = Mock()
        mock_response.data = {"name": "test", "level": 5}

        result = handle_api_response(mock_response, "Success!")

        assert result.success
        assert result.data == {"name": "test", "level": 5}
        assert result.message == "Success!"

    def test_handle_response_as_data(self):
        """Test handling response that is the data itself."""
        data = {"name": "test", "level": 5}

        result = handle_api_response(data, "Success!")

        assert result.success
        assert result.data == data
        assert result.message == "Success!"

    def test_handle_error_response_schema(self):
        """ErrorResponseSchema should produce a CLIResponse error with HTTP code + message."""
        err = ErrorResponseSchema(error=ErrorSchema(code=404, message="Character not found."))
        result = handle_api_response(err)
        assert result.success is False
        assert "404" in result.error
        assert "Character not found" in result.error

    def test_handle_error_response_schema_includes_http_prefix(self):
        """ErrorResponseSchema error message should start with 'HTTP <code>'."""
        err = ErrorResponseSchema(error=ErrorSchema(code=498, message="Character not found."))
        result = handle_api_response(err)
        assert result.success is False
        assert result.error == "HTTP 498: Character not found."


class TestHandleApiError:
    """Test handle_api_error function."""

    def test_handle_unexpected_status_401(self):
        """Test handling 401 Unauthorized error."""
        error = UnexpectedStatus(status_code=401, content=b"")

        result = handle_api_error(error)

        assert not result.success
        assert result.error == "Authentication failed. Check your token."

    def test_handle_unexpected_status_404(self):
        """Test handling 404 Not Found error."""
        error = UnexpectedStatus(status_code=404, content=b"")

        result = handle_api_error(error)

        assert not result.success
        assert result.error == "Resource not found"

    def test_handle_unexpected_status_429(self):
        """Test handling 429 Rate Limit error."""
        error = UnexpectedStatus(status_code=429, content=b"")

        result = handle_api_error(error)

        assert not result.success
        assert result.error == "Too many requests - rate limit exceeded"

    def test_handle_unexpected_status_498(self):
        """Test handling 498 Character not found error."""
        error = UnexpectedStatus(status_code=498, content=b"")

        result = handle_api_error(error)

        assert not result.success
        assert result.error == "Character not found"

    def test_handle_unexpected_status_499_with_cooldown(self):
        """Test handling 499 Cooldown error with cooldown data."""
        cooldown_data = {"error": {"cooldown": {"remaining_seconds": 30}}}
        content = json.dumps(cooldown_data).encode()
        error = UnexpectedStatus(status_code=499, content=content)

        result = handle_api_error(error)

        assert not result.success
        assert result.cooldown_remaining == 30

    def test_handle_unexpected_status_with_detail(self):
        """Test handling error with detail message."""
        error_data = {"detail": "Custom error message"}
        content = json.dumps(error_data).encode()
        error = UnexpectedStatus(status_code=400, content=content)

        result = handle_api_error(error)

        assert not result.success
        assert result.error == "Unknown error (code: 400): Custom error message"

    def test_handle_unexpected_status_without_detail(self):
        """Test handling error without detail message."""
        error = UnexpectedStatus(status_code=500, content=b"invalid json")

        result = handle_api_error(error)

        assert not result.success
        assert result.error == "Server error - please try again later"

    def test_handle_unexpected_status_exception_in_parsing(self):
        """Test handling error when exception occurs during parsing."""
        # Create an error that will cause an exception during JSON parsing
        error = UnexpectedStatus(status_code=400, content=b"valid json")

        # Mock json.loads to raise a JSON decode error
        with patch("json.loads") as mock_json:
            mock_json.side_effect = json.JSONDecodeError("JSON parsing error", "", 0)

            result = handle_api_error(error)

            assert not result.success
            assert result.error == "Unknown error (code: 400)"

    def test_handle_timeout_exception(self):
        """Test handling timeout exception."""
        error = httpx.TimeoutException("Request timed out")

        result = handle_api_error(error)

        assert not result.success
        assert result.error == "Request timed out. Please try again."

    def test_handle_connect_error(self):
        """Test handling connection error."""
        error = httpx.ConnectError("Connection failed")

        result = handle_api_error(error)

        assert not result.success
        assert result.error == "Could not connect to API. Check your internet connection."

    def test_handle_generic_exception(self):
        """Test handling generic exception."""
        error = ValueError("Some error")

        result = handle_api_error(error)

        assert not result.success
        assert result.error == "Unexpected error: Some error"


class TestHandleApiErrorBranches:
    """Cover the error-parsing branches of handle_api_error and its helpers."""

    def test_valueerror_httpstatus_with_cooldown_code(self):
        """ValueError carrying the 499 cooldown code maps to its message."""
        error = ValueError("499 is not a valid HTTPStatus")
        result = handle_api_error(error)
        assert not result.success
        assert result.error == "Character is on cooldown"

    def test_valueerror_httpstatus_with_known_noncooldown_code(self):
        """ValueError carrying a known non-499 code maps to its message."""
        error = ValueError("492 is not a valid HTTPStatus")
        result = handle_api_error(error)
        assert not result.success
        assert result.error == "Insufficient gold"

    def test_valueerror_httpstatus_without_match(self):
        """ValueError mentioning HTTPStatus but with no numeric code falls back."""
        error = ValueError("xyz is not a valid HTTPStatus")
        result = handle_api_error(error)
        assert not result.success
        assert result.error == "Unexpected error: xyz is not a valid HTTPStatus"

    def test_extracted_error_code_overrides_status(self):
        """A code in the JSON body overrides the HTTP status for message lookup."""
        # HTTP 400 (unknown), body code 492 -> "Insufficient gold".
        content = json.dumps({"error": {"code": 492}}).encode()
        error = UnexpectedStatus(status_code=400, content=content)
        result = handle_api_error(error)
        assert not result.success
        assert result.error == "Insufficient gold"

    def test_478_with_detailed_message(self):
        """478 missing-items appends the parsed detail message."""
        content = json.dumps({"error": {"message": "need 3 iron"}}).encode()
        error = UnexpectedStatus(status_code=478, content=content)
        result = handle_api_error(error)
        assert not result.success
        assert result.error == "Missing required items or materials: need 3 iron"

    def test_478_without_detailed_message(self):
        """478 with no parseable detail returns the bare mapped message."""
        error = UnexpectedStatus(status_code=478, content=b"not json")
        result = handle_api_error(error)
        assert not result.success
        assert result.error == "Missing required items or materials"

    def test_httpx_http_status_error(self):
        """httpx.HTTPStatusError maps via the response status code."""
        request = httpx.Request("GET", "https://example.test")
        response = httpx.Response(404, request=request)
        error = httpx.HTTPStatusError("boom", request=request, response=response)
        result = handle_api_error(error)
        assert not result.success
        assert result.error == "Resource not found"

    def test_extract_error_code_root_level(self):
        """_extract_error_code reads a root-level integer code."""
        from artifactsmmo_cli.utils.helpers import _extract_error_code

        error = UnexpectedStatus(status_code=400, content=json.dumps({"code": 492}).encode())
        assert _extract_error_code(error) == 492

    def test_extract_error_code_nested(self):
        """_extract_error_code reads a nested error.code."""
        from artifactsmmo_cli.utils.helpers import _extract_error_code

        error = UnexpectedStatus(status_code=400, content=json.dumps({"error": {"code": 471}}).encode())
        assert _extract_error_code(error) == 471

    def test_extract_error_code_absent(self):
        """_extract_error_code returns None when no code present."""
        from artifactsmmo_cli.utils.helpers import _extract_error_code

        error = UnexpectedStatus(status_code=400, content=json.dumps({"foo": "bar"}).encode())
        assert _extract_error_code(error) is None

    def test_parse_detailed_message_from_details_field(self):
        """_parse_detailed_error_message falls back to error.details."""
        from artifactsmmo_cli.utils.helpers import _parse_detailed_error_message

        content = json.dumps({"error": {"details": ["a", "b"]}}).encode()
        error = UnexpectedStatus(status_code=400, content=content)
        assert _parse_detailed_error_message(error) == "['a', 'b']"

    def test_parse_detailed_message_top_level_message(self):
        """_parse_detailed_error_message falls back to top-level message."""
        from artifactsmmo_cli.utils.helpers import _parse_detailed_error_message

        content = json.dumps({"message": "top level"}).encode()
        error = UnexpectedStatus(status_code=400, content=content)
        assert _parse_detailed_error_message(error) == "top level"

    def test_parse_detailed_message_invalid_json(self):
        """_parse_detailed_error_message returns None on invalid JSON."""
        from artifactsmmo_cli.utils.helpers import _parse_detailed_error_message

        error = UnexpectedStatus(status_code=400, content=b"not json")
        assert _parse_detailed_error_message(error) is None

    def test_cooldown_error_parsed_from_message_regex(self):
        """_parse_cooldown_error extracts seconds from a free-text message."""
        from artifactsmmo_cli.utils.helpers import _parse_cooldown_error

        content = json.dumps({"error": {"message": "Wait 2.27 seconds remaining"}}).encode()
        error = UnexpectedStatus(status_code=499, content=content)
        result = _parse_cooldown_error(error)
        assert not result.success
        assert result.cooldown_remaining == 2.27

    def test_cooldown_error_no_time_found(self):
        """_parse_cooldown_error falls back when neither object nor regex matches."""
        from artifactsmmo_cli.utils.helpers import _parse_cooldown_error

        content = json.dumps({"error": {"message": "on cooldown, no number"}}).encode()
        error = UnexpectedStatus(status_code=499, content=content)
        result = _parse_cooldown_error(error)
        assert not result.success
        assert result.error == "Character is on cooldown"

    def test_parse_api_error_response_detail_field(self):
        """_parse_api_error_response prefers the detail field."""
        from artifactsmmo_cli.utils.helpers import _parse_api_error_response

        content = json.dumps({"detail": "the detail"}).encode()
        error = UnexpectedStatus(status_code=400, content=content)
        result = _parse_api_error_response(error, "fallback")
        assert not result.success
        assert result.error == "the detail"

    def test_parse_api_error_response_message_field(self):
        """_parse_api_error_response falls back to the message field."""
        from artifactsmmo_cli.utils.helpers import _parse_api_error_response

        content = json.dumps({"message": "the message"}).encode()
        error = UnexpectedStatus(status_code=400, content=content)
        result = _parse_api_error_response(error, "fallback")
        assert not result.success
        assert result.error == "the message"

    def test_parse_api_error_response_uses_fallback_when_empty(self):
        """_parse_api_error_response uses the fallback when no message is present."""
        from artifactsmmo_cli.utils.helpers import _parse_api_error_response

        content = json.dumps({"unrelated": "x"}).encode()
        error = UnexpectedStatus(status_code=400, content=content)
        result = _parse_api_error_response(error, "fallback msg")
        assert not result.success
        assert result.error == "fallback msg"

    def test_parse_api_error_response_invalid_json_uses_fallback(self):
        """_parse_api_error_response returns the fallback on invalid JSON."""
        from artifactsmmo_cli.utils.helpers import _parse_api_error_response

        error = UnexpectedStatus(status_code=400, content=b"not json")
        result = _parse_api_error_response(error, "fb")
        assert not result.success
        assert result.error == "fb"

    def test_extract_action_result_non_dict_returns_none(self):
        """extract_action_result returns None for non-dict input."""
        from artifactsmmo_cli.utils.helpers import extract_action_result

        assert extract_action_result("not a dict", "fight") is None  # type: ignore[arg-type]


class TestExtractCharacterData:
    """Test extract_character_data function."""

    def test_extract_with_character_key(self):
        """Test extracting character data when character key exists."""
        response = {"character": {"name": "test", "level": 5}, "other_data": "ignored"}

        result = extract_character_data(response)

        assert result == {"name": "test", "level": 5}

    def test_extract_without_character_key(self):
        """Test extracting character data when no character key."""
        response = {"name": "test", "level": 5}

        result = extract_character_data(response)

        assert result == {"name": "test", "level": 5}


class TestExtractCooldownInfo:
    """Test extract_cooldown_info function."""

    def test_extract_with_cooldown(self):
        """Test extracting cooldown when present."""
        response = {"cooldown": {"remaining_seconds": 45}}

        result = extract_cooldown_info(response)

        assert result == 45

    def test_extract_without_cooldown(self):
        """Test extracting cooldown when not present."""
        response = {"other_data": "value"}

        result = extract_cooldown_info(response)

        assert result is None

    def test_extract_empty_cooldown(self):
        """Test extracting empty cooldown."""
        response = {"cooldown": {}}

        result = extract_cooldown_info(response)

        assert result is None


class TestFormatCoordinates:
    """Test format_coordinates function."""

    def test_format_positive_coordinates(self):
        """Test formatting positive coordinates."""
        result = format_coordinates(5, 10)
        assert result == "(5, 10)"

    def test_format_negative_coordinates(self):
        """Test formatting negative coordinates."""
        result = format_coordinates(-3, -7)
        assert result == "(-3, -7)"

    def test_format_zero_coordinates(self):
        """Test formatting zero coordinates."""
        result = format_coordinates(0, 0)
        assert result == "(0, 0)"


class TestParseCoordinates:
    """Test parse_coordinates function."""

    def test_parse_parentheses_format(self):
        """Test parsing coordinates with parentheses."""
        result = parse_coordinates("(5, 10)")
        assert result == (5, 10)

    def test_parse_comma_format(self):
        """Test parsing coordinates without parentheses."""
        result = parse_coordinates("5,10")
        assert result == (5, 10)

    def test_parse_with_spaces(self):
        """Test parsing coordinates with extra spaces."""
        result = parse_coordinates(" ( 5 , 10 ) ")
        assert result == (5, 10)

    def test_parse_negative_coordinates(self):
        """Test parsing negative coordinates."""
        result = parse_coordinates("(-3, -7)")
        assert result == (-3, -7)

    def test_parse_invalid_format(self):
        """Test parsing invalid coordinate format."""
        with pytest.raises(ValueError, match="Invalid coordinate format"):
            parse_coordinates("invalid")

    def test_parse_non_numeric(self):
        """Test parsing non-numeric coordinates."""
        with pytest.raises(ValueError, match="Invalid coordinate format"):
            parse_coordinates("(a, b)")


class TestSafeGet:
    """Test safe_get function."""

    def test_safe_get_existing_key(self):
        """Test getting existing key."""
        data = {"level1": {"level2": {"level3": "value"}}}

        result = safe_get(data, "level1", "level2", "level3")

        assert result == "value"

    def test_safe_get_missing_key(self):
        """Test getting missing key."""
        data = {"level1": {"level2": "value"}}

        result = safe_get(data, "level1", "missing", "level3")

        assert result is None

    def test_safe_get_with_default(self):
        """Test getting missing key with default value."""
        data = {"level1": "value"}

        result = safe_get(data, "missing", default="default_value")

        assert result == "default_value"

    def test_safe_get_non_dict_value(self):
        """Test getting from non-dict value."""
        data = {"level1": "not_a_dict"}

        result = safe_get(data, "level1", "level2")

        assert result is None

    def test_safe_get_single_key(self):
        """Test getting single key."""
        data = {"key": "value"}

        result = safe_get(data, "key")

        assert result == "value"

    def test_safe_get_empty_data(self):
        """Test getting from empty data."""
        data = {}

        result = safe_get(data, "key")

        assert result is None


class TestNewHelperFunctions:
    """Test new helper functions for error handling and action results."""

    def test_parse_cooldown_error_with_valid_data(self):
        """Test parsing cooldown error with valid data."""
        from artifactsmmo_cli.utils.helpers import _parse_cooldown_error

        error_data = {"error": {"cooldown": {"remaining_seconds": 30}}}
        content = json.dumps(error_data).encode()
        error = UnexpectedStatus(status_code=498, content=content)

        result = _parse_cooldown_error(error)

        assert not result.success
        assert result.cooldown_remaining == 30

    def test_parse_cooldown_error_alternative_structure(self):
        """Test parsing cooldown error with alternative data structure."""
        from artifactsmmo_cli.utils.helpers import _parse_cooldown_error

        error_data = {"cooldown": {"remaining_seconds": 45}}
        content = json.dumps(error_data).encode()
        error = UnexpectedStatus(status_code=498, content=content)

        result = _parse_cooldown_error(error)

        assert not result.success
        assert result.cooldown_remaining == 45

    def test_parse_cooldown_error_invalid_json(self):
        """Test parsing cooldown error with invalid JSON."""
        from artifactsmmo_cli.utils.helpers import _parse_cooldown_error

        error = UnexpectedStatus(status_code=498, content=b"invalid json")

        result = _parse_cooldown_error(error)

        assert not result.success
        assert result.error == "Character is on cooldown"

    def test_parse_api_error_response_with_nested_error(self):
        """Test parsing API error with nested error structure."""
        from artifactsmmo_cli.utils.helpers import _parse_api_error_response

        error_data = {"error": {"message": "Nested error message", "code": "ERR001"}}
        content = json.dumps(error_data).encode()
        error = UnexpectedStatus(status_code=400, content=content)

        result = _parse_api_error_response(error, "fallback")

        assert not result.success
        assert result.error == "Unknown error (code: ERR001)"

    def test_parse_api_error_response_with_string_error(self):
        """Test parsing API error with string error."""
        from artifactsmmo_cli.utils.helpers import _parse_api_error_response

        error_data = {"error": "Simple error string"}
        content = json.dumps(error_data).encode()
        error = UnexpectedStatus(status_code=400, content=content)

        result = _parse_api_error_response(error, "fallback")

        assert not result.success
        assert result.error == "Simple error string"

    def test_handle_api_error_status_452(self):
        """Test handling status code 452."""
        error_data = {"detail": "Inventory full"}
        content = json.dumps(error_data).encode()
        error = UnexpectedStatus(status_code=452, content=content)

        result = handle_api_error(error)

        assert not result.success
        assert result.error == "Invalid authentication token: Inventory full"

    def test_handle_api_error_status_499(self):
        """Test handling status code 499 (alternative cooldown)."""
        error_data = {"cooldown": {"remaining_seconds": 60}}
        content = json.dumps(error_data).encode()
        error = UnexpectedStatus(status_code=499, content=content)

        result = handle_api_error(error)

        assert not result.success
        assert result.cooldown_remaining == 60

    def test_extract_action_result_with_action_type(self):
        """Test extracting action result with specific action type."""
        from artifactsmmo_cli.utils.helpers import extract_action_result

        response = {"fight": {"result": "win", "damage": 25, "xp": 100}}

        result = extract_action_result(response, "fight")

        assert result == {"result": "win", "damage": 25, "xp": 100}

    def test_extract_action_result_with_nested_data(self):
        """Test extracting action result from nested data structure."""
        from artifactsmmo_cli.utils.helpers import extract_action_result

        response = {"data": {"gather": {"items": [{"code": "wood", "quantity": 3}]}}}

        result = extract_action_result(response, "gather")

        assert result == {"items": [{"code": "wood", "quantity": 3}]}

    def test_extract_action_result_not_found(self):
        """Test extracting action result when not found."""
        from artifactsmmo_cli.utils.helpers import extract_action_result

        response = {"other_data": "value"}

        result = extract_action_result(response, "fight")

        assert result is None
