"""
Tests for the httpstatus module.

This module tests the custom HTTP status codes for ArtifactsMMO API
and the extend_http_status function that extends HTTPStatus enum.
"""

from http import HTTPStatus

from src.lib.httpstatus import ArtifactsHTTPStatus, extend_http_status


class TestArtifactsHTTPStatus:
    """Test the ArtifactsHTTPStatus dictionary."""

    def test_artifacts_http_status_is_dict(self):
        """Test that ArtifactsHTTPStatus is a dictionary."""
        assert isinstance(ArtifactsHTTPStatus, dict)

    def test_artifacts_http_status_not_empty(self):
        """Test that ArtifactsHTTPStatus is not empty."""
        assert len(ArtifactsHTTPStatus) > 0

    def test_all_status_codes_are_integers(self):
        """Test that all status codes are integers."""
        for name, code in ArtifactsHTTPStatus.items():
            assert isinstance(code, int), f"Status code for {name} should be an integer, got {type(code)}"

    def test_all_status_names_are_strings(self):
        """Test that all status names are strings."""
        for name, code in ArtifactsHTTPStatus.items():
            assert isinstance(name, str), f"Status name should be a string, got {type(name)}"
            assert len(name) > 0, "Status name should not be empty"

    def test_all_status_codes_are_valid_http_codes(self):
        """Test that all status codes are in valid HTTP status code range (400-599)."""
        for name, code in ArtifactsHTTPStatus.items():
            assert 400 <= code <= 599, f"Status code {code} for {name} should be in range 400-599"

    def test_no_duplicate_status_codes(self):
        """Test that there are no duplicate status codes (except intentional aliases)."""
        codes = list(ArtifactsHTTPStatus.values())
        # Count occurrences of each code
        code_counts = {}
        for code in codes:
            code_counts[code] = code_counts.get(code, 0) + 1

        # Check for unexpected duplicates
        expected_duplicates = {
            497: 2,  # CHARACTER_INVENTORY_FULL and INVENTORY_FULL
            499: 2,  # CHARACTER_IN_COOLDOWN and CHARACTER_COOLDOWN
        }

        for code, count in code_counts.items():
            if count > 1:
                assert code in expected_duplicates, f"Unexpected duplicate status code: {code}"
                expected_count = expected_duplicates[code]
                assert count == expected_count, f"Status code {code} appears {count} times, expected {expected_count}"

    def test_account_error_codes_exist(self):
        """Test that all account error codes are defined."""
        account_codes = [
            "TOKEN_INVALID", "TOKEN_EXPIRED", "TOKEN_MISSING", "TOKEN_GENERATION_FAIL",
            "USERNAME_ALREADY_USED", "EMAIL_ALREADY_USED", "SAME_PASSWORD", "CURRENT_PASSWORD_INVALID"
        ]
        for code in account_codes:
            assert code in ArtifactsHTTPStatus, f"Account error code {code} should be defined"

    def test_character_error_codes_exist(self):
        """Test that all character error codes are defined."""
        character_codes = [
            "CHARACTER_NOT_ENOUGH_HP", "CHARACTER_MAXIMUM_UTILITES_EQUIPED", "CHARACTER_ITEM_ALREADY_EQUIPED",
            "CHARACTER_LOCKED", "CHARACTER_NOT_THIS_TASK", "CHARACTER_TOO_MANY_ITEMS_TASK", "CHARACTER_NO_TASK",
            "CHARACTER_TASK_NOT_COMPLETED", "CHARACTER_ALREADY_TASK", "CHARACTER_ALREADY_MAP",
            "CHARACTER_SLOT_EQUIPMENT_ERROR", "CHARACTER_GOLD_INSUFFICIENT", "CHARACTER_NOT_SKILL_LEVEL_REQUIRED",
            "CHARACTER_NAME_ALREADY_USED", "MAX_CHARACTERS_REACHED", "CHARACTER_NOT_LEVEL_REQUIRED",
            "CHARACTER_INVENTORY_FULL", "CHARACTER_NOT_FOUND", "CHARACTER_IN_COOLDOWN"
        ]
        for code in character_codes:
            assert code in ArtifactsHTTPStatus, f"Character error code {code} should be defined"

    def test_item_error_codes_exist(self):
        """Test that all item error codes are defined."""
        item_codes = [
            "ITEM_INSUFFICIENT_QUANTITY", "ITEM_INVALID_EQUIPMENT", "ITEM_RECYCLING_INVALID_ITEM",
            "ITEM_INVALID_CONSUMABLE", "MISSING_ITEM"
        ]
        for code in item_codes:
            assert code in ArtifactsHTTPStatus, f"Item error code {code} should be defined"

    def test_grand_exchange_error_codes_exist(self):
        """Test that all grand exchange error codes are defined."""
        ge_codes = [
            "GE_MAX_QUANTITY", "GE_NOT_IN_STOCK", "GE_NOT_THE_PRICE", "GE_TRANSACTION_IN_PROGRESS",
            "GE_NO_ORDERS", "GE_MAX_ORDERS", "GE_TOO_MANY_ITEMS", "GE_SAME_ACCOUNT",
            "GE_INVALID_ITEM", "GE_NOT_YOUR_ORDER"
        ]
        for code in ge_codes:
            assert code in ArtifactsHTTPStatus, f"Grand exchange error code {code} should be defined"

    def test_bank_error_codes_exist(self):
        """Test that all bank error codes are defined."""
        bank_codes = ["BANK_INSUFFICIENT_GOLD", "BANK_TRANSACTION_IN_PROGRESS", "BANK_FULL"]
        for code in bank_codes:
            assert code in ArtifactsHTTPStatus, f"Bank error code {code} should be defined"

    def test_map_error_codes_exist(self):
        """Test that all map error codes are defined."""
        map_codes = ["MAP_NOT_FOUND", "MAP_CONTENT_NOT_FOUND"]
        for code in map_codes:
            assert code in ArtifactsHTTPStatus, f"Map error code {code} should be defined"

    def test_alias_codes_exist(self):
        """Test that alias codes are defined correctly."""
        # Test that the aliases exist and have the correct values
        assert "INVENTORY_FULL" in ArtifactsHTTPStatus
        assert "CHARACTER_COOLDOWN" in ArtifactsHTTPStatus
        assert ArtifactsHTTPStatus["INVENTORY_FULL"] == ArtifactsHTTPStatus["CHARACTER_INVENTORY_FULL"]
        assert ArtifactsHTTPStatus["CHARACTER_COOLDOWN"] == ArtifactsHTTPStatus["CHARACTER_IN_COOLDOWN"]

    def test_specific_status_code_values(self):
        """Test specific status code values to ensure they haven't changed accidentally."""
        expected_values = {
            "TOKEN_INVALID": 452,
            "CHARACTER_IN_COOLDOWN": 499,
            "CHARACTER_INVENTORY_FULL": 497,
            "ITEM_INSUFFICIENT_QUANTITY": 471,
            "GE_TRANSACTION_IN_PROGRESS": 436,
            "BANK_INSUFFICIENT_GOLD": 460,
            "MAP_NOT_FOUND": 597,
        }

        for name, expected_code in expected_values.items():
            actual_code = ArtifactsHTTPStatus[name]
            assert actual_code == expected_code, f"{name} should be {expected_code}, got {actual_code}"


class TestExtendHttpStatus:
    """Test the extend_http_status function."""

    def test_extend_http_status_function_exists(self):
        """Test that extend_http_status function exists and is callable."""
        assert callable(extend_http_status)

    def test_extend_http_status_adds_artifacts_codes(self):
        """Test that extend_http_status adds ArtifactsMMO codes to HTTPStatus."""
        # Call extend_http_status
        extend_http_status()

        # Check that all ArtifactsHTTPStatus codes are now in HTTPStatus
        for name, value in ArtifactsHTTPStatus.items():
            assert hasattr(HTTPStatus, name), f"HTTPStatus should have {name} after extending"
            status_member = getattr(HTTPStatus, name)
            actual_value = status_member.value
            assert actual_value == value, f"HTTPStatus.{name} should have value {value}, got {actual_value}"

    def test_extend_http_status_preserves_original_codes(self):
        """Test that extend_http_status preserves original HTTPStatus codes."""
        # Get some well-known original HTTP status codes
        original_codes = {
            "OK": 200,
            "NOT_FOUND": 404,
            "INTERNAL_SERVER_ERROR": 500,
            "BAD_REQUEST": 400,
        }

        # Call extend_http_status
        extend_http_status()

        # Check that all original members are still there with correct values
        for name, value in original_codes.items():
            assert hasattr(HTTPStatus, name), f"HTTPStatus should still have original member {name}"
            status_member = getattr(HTTPStatus, name)
            actual_value = status_member.value
            assert actual_value == value, f"HTTPStatus.{name} should still have value {value}, got {actual_value}"

    def test_extend_http_status_can_be_called_multiple_times(self):
        """Test that extend_http_status can be called multiple times without error."""
        # Call extend_http_status multiple times
        extend_http_status()
        extend_http_status()
        extend_http_status()

        # Should not raise any errors and all codes should still be accessible
        for name, value in ArtifactsHTTPStatus.items():
            assert hasattr(HTTPStatus, name), f"HTTPStatus should have {name} after multiple extensions"
            status_member = getattr(HTTPStatus, name)
            actual_value = status_member.value
            assert actual_value == value, f"HTTPStatus.{name} should have value {value}, got {actual_value}"


class TestIntegration:
    """Integration tests for httpstatus module."""

    def test_module_imports_correctly(self):
        """Test that the module imports correctly."""
        from src.lib.httpstatus import ArtifactsHTTPStatus, extend_http_status
        assert ArtifactsHTTPStatus is not None
        assert extend_http_status is not None

    def test_status_codes_can_be_used_in_comparisons(self):
        """Test that status codes can be used in comparisons."""
        # Test direct comparison
        assert ArtifactsHTTPStatus["TOKEN_INVALID"] == 452
        assert ArtifactsHTTPStatus["CHARACTER_IN_COOLDOWN"] != 400

        # Test range checks
        assert 400 <= ArtifactsHTTPStatus["TOKEN_INVALID"] < 500
        assert ArtifactsHTTPStatus["MAP_NOT_FOUND"] >= 500

    def test_status_codes_can_be_used_as_dict_keys(self):
        """Test that status codes can be used as dictionary keys."""
        status_messages = {
            ArtifactsHTTPStatus["TOKEN_INVALID"]: "Invalid token",
            ArtifactsHTTPStatus["CHARACTER_IN_COOLDOWN"]: "Character on cooldown",
        }

        assert status_messages[452] == "Invalid token"
        assert status_messages[499] == "Character on cooldown"

    def test_alias_consistency(self):
        """Test that aliases work consistently."""
        # Test that both the full name and alias work
        assert ArtifactsHTTPStatus["CHARACTER_INVENTORY_FULL"] == 497
        assert ArtifactsHTTPStatus["INVENTORY_FULL"] == 497
        assert ArtifactsHTTPStatus["CHARACTER_IN_COOLDOWN"] == 499
        assert ArtifactsHTTPStatus["CHARACTER_COOLDOWN"] == 499
