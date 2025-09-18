"""Helper utilities for the CLI."""

from typing import Any
import json
import traceback

import httpx
from artifactsmmo_api_client.errors import UnexpectedStatus

from artifactsmmo_cli.models.responses import CLIResponse


# ArtifactsMMO Error Code Messages
ERROR_MESSAGES = {
    # Standard HTTP codes
    401: "Authentication failed. Check your token.",
    403: "Forbidden - insufficient permissions",
    # General
    422: "Invalid request payload",
    429: "Too many requests - rate limit exceeded",
    404: "Resource not found",
    500: "Server error - please try again later",
    # Email token error codes
    560: "Invalid email reset token",
    561: "Email reset token has expired",
    562: "Email reset token has already been used",
    # Account Error Codes
    451: "Account is not a member - subscription required",
    452: "Invalid authentication token",
    453: "Authentication token has expired",
    454: "Authentication token is missing",
    455: "Failed to generate authentication token",
    456: "Username is already taken",
    457: "Email address is already registered",
    458: "New password cannot be the same as current password",
    459: "Current password is incorrect",
    550: "Character skin not owned by account",
    # Character Error Codes
    474: "Character does not have this task",
    475: "Character has too many items for task",
    478: "Missing required items or materials",
    483: "Character does not have enough HP",
    484: "Maximum utilities already equipped",
    485: "Item is already equipped",
    486: "Character is locked",
    487: "Character has no active task",
    488: "Task is not completed",
    489: "Character already has a task",
    490: "Character is already at this location",
    491: "Equipment slot error",
    492: "Insufficient gold",
    493: "Character does not meet skill level requirements",
    494: "Character name is already taken",
    495: "Maximum number of characters reached",
    496: "Character does not meet requirements",
    497: "Character inventory is full",
    498: "Character not found",
    499: "Character is on cooldown",
    # Item Error Codes
    471: "Insufficient quantity of item",
    472: "Invalid equipment item",
    473: "Invalid item for recycling",
    476: "Invalid consumable item",
    # Grand Exchange Error Codes
    431: "No Grand Exchange orders found",
    433: "Maximum Grand Exchange orders reached",
    434: "Too many items for Grand Exchange",
    435: "Cannot trade with your own account",
    436: "Grand Exchange transaction in progress",
    437: "Invalid item for Grand Exchange",
    438: "This is not your Grand Exchange order",
    479: "Maximum quantity exceeded for Grand Exchange",
    480: "Item not in stock at Grand Exchange",
    482: "Price mismatch at Grand Exchange",
    # Bank Error Codes
    460: "Insufficient gold in bank",
    461: "Bank transaction in progress",
    462: "Bank is full",
    # Maps Error Codes
    597: "Map location not found",
    598: "Wrong location for this action - content not found at this location",
    # NPC Error Codes
    441: "Item not for sale from NPC",
    442: "NPC does not buy this item",
}


def get_error_message(code: int) -> str:
    """Get human-readable error message for ArtifactsMMO error codes."""
    return ERROR_MESSAGES.get(code, f"Unknown error (code: {code})")


def handle_api_response(response: Any, success_message: str | None = None) -> CLIResponse[Any]:
    """Handle API response and convert to CLIResponse."""
    try:
        if response is None:
            return CLIResponse.error_response("No response received from API")

        # Check if response has data attribute (successful response)
        if hasattr(response, "data"):
            return CLIResponse.success_response(response.data, success_message)

        # If response is the data itself
        return CLIResponse.success_response(response, success_message)

    except Exception as e:
        return CLIResponse.error_response(f"Unexpected error: {str(e)}")


def handle_api_error(error: Exception) -> CLIResponse[Any]:
    """Handle API errors and convert to CLIResponse."""
    # Handle ValueError from non-standard HTTP status codes
    if isinstance(error, ValueError) and "is not a valid HTTPStatus" in str(error):
        # Extract the status code from the error message
        import re

        match = re.search(r"(\d+) is not a valid HTTPStatus", str(error))
        if match:
            status_code = int(match.group(1))
            error_message = get_error_message(status_code)

            # Special handling for cooldown errors (499) - this should not be reached anymore
            # since we now convert ValueError to UnexpectedStatus in the client manager
            if status_code == 499:
                return CLIResponse.error_response(error_message)

            return CLIResponse.error_response(error_message)
        else:
            return CLIResponse.error_response(f"Unexpected error: {str(error)}")

    if isinstance(error, UnexpectedStatus):
        # Try to parse error response
        try:
            status_code = error.status_code

            # Try to extract the actual error code from the response
            actual_error_code = _extract_error_code(error)
            if actual_error_code:
                status_code = actual_error_code

            # Get the appropriate error message
            error_message = get_error_message(status_code)

            # Handle special cases that need additional parsing
            if status_code == 499:
                # Character cooldown - try to get cooldown time
                return _parse_cooldown_error(error)
            elif status_code == 478:
                # Missing items - try to get more details
                detailed_msg = _parse_detailed_error_message(error)
                if detailed_msg:
                    return CLIResponse.error_response(f"{error_message}: {detailed_msg}")
                return CLIResponse.error_response(error_message)
            else:
                # For all other errors, try to get additional details
                detailed_msg = _parse_detailed_error_message(error)
                if detailed_msg and detailed_msg != error_message:
                    return CLIResponse.error_response(f"{error_message}: {detailed_msg}")
                return CLIResponse.error_response(error_message)

        except Exception as parse_error:
            # If parsing fails, return a safe error message
            return CLIResponse.error_response(
                f"API error {error.status_code}: Unable to parse error details ({str(parse_error)})"
            )

    elif isinstance(error, httpx.TimeoutException):
        return CLIResponse.error_response("Request timed out. Please try again.")

    elif isinstance(error, httpx.ConnectError):
        return CLIResponse.error_response("Could not connect to API. Check your internet connection.")

    elif isinstance(error, httpx.HTTPStatusError):
        # Handle httpx.HTTPStatusError which might occur with non-standard status codes
        status_code = error.response.status_code
        error_message = get_error_message(status_code)
        return CLIResponse.error_response(error_message)

    else:
        return CLIResponse.error_response(f"Unexpected error: {str(error)}")


def _extract_error_code(error: UnexpectedStatus) -> int | None:
    """Extract the actual error code from the API response."""
    try:
        import json

        error_data = json.loads(error.content.decode())

        # Check for error code in the error object
        if isinstance(error_data.get("error"), dict):
            code = error_data["error"].get("code")
            if code:
                return int(code)

        # Sometimes the code might be at the root level
        if "code" in error_data:
            return int(error_data["code"])

    except Exception:
        pass

    return None


def _parse_detailed_error_message(error: UnexpectedStatus) -> str | None:
    """Parse additional error details from API response."""
    try:
        import json

        error_data = json.loads(error.content.decode())

        # Try to get additional message details
        if isinstance(error_data.get("error"), dict):
            error_obj = error_data["error"]
            # Get the message if available
            if "message" in error_obj:
                return error_obj["message"]
            # Get details if available
            if "details" in error_obj:
                return str(error_obj["details"])

        # Check for detail field
        if "detail" in error_data:
            return error_data["detail"]

        # Check for message field
        if "message" in error_data:
            return error_data["message"]

    except Exception:
        pass

    return None


def _parse_cooldown_error(error: UnexpectedStatus) -> CLIResponse[Any]:
    """Parse cooldown error from API response."""
    try:
        import json
        import re

        error_data = json.loads(error.content.decode())

        # Try multiple possible paths for cooldown data
        cooldown_data = error_data.get("error", {}).get("cooldown") or error_data.get("cooldown") or {}

        remaining_seconds = cooldown_data.get("remaining_seconds", 0)
        if remaining_seconds > 0:
            return CLIResponse.cooldown_response(remaining_seconds)

        # If no cooldown object, try to extract from the message
        message = error_data.get("error", {}).get("message", "")
        if message:
            # Look for patterns like "2.27 seconds remaining"
            match = re.search(r"(\d+\.?\d*)\s+seconds?\s+remaining", message)
            if match:
                remaining_seconds = float(match.group(1))
                return CLIResponse.cooldown_response(remaining_seconds)

        # Fallback if no specific cooldown time found
        return CLIResponse.error_response("Character is on cooldown")
    except Exception:
        return CLIResponse.error_response("Character is on cooldown")


def _parse_api_error_response(error: UnexpectedStatus, fallback_message: str) -> CLIResponse[Any]:
    """Parse detailed error information from API response."""
    try:
        import json

        error_data = json.loads(error.content.decode())

        # Try multiple possible paths for error messages
        message = None

        # Check for detail field first
        if "detail" in error_data and error_data["detail"]:
            message = error_data["detail"]
        # Check for message field
        elif "message" in error_data and error_data["message"]:
            message = error_data["message"]
        # Check for nested error message
        elif "error" in error_data and isinstance(error_data["error"], dict):
            if "message" in error_data["error"]:
                message = error_data["error"]["message"]
        # Check for error as string
        elif "error" in error_data and error_data["error"]:
            message = str(error_data["error"])

        # Use fallback if no message found
        if not message:
            message = fallback_message

        # If we have additional error details, include them
        if isinstance(error_data.get("error"), dict):
            error_details = error_data["error"]
            if "code" in error_details:
                # Use our error message mapping
                code = error_details["code"]
                message = get_error_message(code)

        return CLIResponse.error_response(message)
    except Exception:
        return CLIResponse.error_response(fallback_message)


def extract_character_data(character_response: dict[str, Any]) -> dict[str, Any]:
    """Extract character data from API response."""
    if "character" in character_response:
        return character_response["character"]
    return character_response


def extract_cooldown_info(response: dict[str, Any]) -> int | None:
    """Extract cooldown information from response."""
    cooldown = response.get("cooldown", {})
    if cooldown:
        return cooldown.get("remaining_seconds", 0)
    return None


def extract_action_result(response: dict[str, Any], action_type: str) -> dict[str, Any] | None:
    """Extract action result data from API response."""
    if not isinstance(response, dict):
        return None

    # Try different possible paths for action results
    result_data = (
        response.get(action_type)
        or response.get("data", {}).get(action_type)
        or response.get("result")
        or response.get("details")
    )

    if isinstance(result_data, dict):
        return result_data

    return None


def format_coordinates(x: int, y: int) -> str:
    """Format coordinates as a string."""
    return f"({x}, {y})"


def parse_coordinates(coord_str: str) -> tuple[int, int]:
    """Parse coordinates from string format like '(5, 10)' or '5,10'."""
    # Remove parentheses and spaces, then split by comma
    clean_str = coord_str.strip("() ").replace(" ", "")
    try:
        x_str, y_str = clean_str.split(",")
        return int(x_str), int(y_str)
    except ValueError:
        raise ValueError(f"Invalid coordinate format: {coord_str}. Use format: 'x,y' or '(x,y)'")


def safe_get(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Safely get nested dictionary values."""
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current
