"""Tests for validation utilities."""

import pytest
import typer

from artifactsmmo_cli.utils.validators import (
    validate_character_name,
    validate_coordinates,
    validate_gold_amount,
    validate_item_code,
    validate_item_slot,
    validate_quantity,
    validate_skin_code,
)


class TestValidateCoordinates:
    """Test validate_coordinates function."""

    def test_valid_coordinates(self):
        """Test valid coordinates."""
        result = validate_coordinates(5, 10)
        assert result == (5, 10)

    def test_zero_coordinates(self):
        """Test zero coordinates."""
        result = validate_coordinates(0, 0)
        assert result == (0, 0)

    def test_negative_coordinates(self):
        """Test negative coordinates."""
        result = validate_coordinates(-50, -25)
        assert result == (-50, -25)

    def test_boundary_coordinates(self):
        """Test boundary coordinates."""
        result = validate_coordinates(100, -100)
        assert result == (100, -100)

    def test_x_coordinate_too_large(self):
        """Test X coordinate out of range (too large)."""
        with pytest.raises(typer.BadParameter, match="X coordinate 101 is out of reasonable range"):
            validate_coordinates(101, 0)

    def test_x_coordinate_too_small(self):
        """Test X coordinate out of range (too small)."""
        with pytest.raises(typer.BadParameter, match="X coordinate -101 is out of reasonable range"):
            validate_coordinates(-101, 0)

    def test_y_coordinate_too_large(self):
        """Test Y coordinate out of range (too large)."""
        with pytest.raises(typer.BadParameter, match="Y coordinate 101 is out of reasonable range"):
            validate_coordinates(0, 101)

    def test_y_coordinate_too_small(self):
        """Test Y coordinate out of range (too small)."""
        with pytest.raises(typer.BadParameter, match="Y coordinate -101 is out of reasonable range"):
            validate_coordinates(0, -101)


class TestValidateCharacterName:
    """Test validate_character_name function."""

    def test_valid_character_name(self):
        """Test valid character name."""
        result = validate_character_name("warrior123")
        assert result == "warrior123"

    def test_valid_name_with_underscore(self):
        """Test valid character name with underscore."""
        result = validate_character_name("my_character")
        assert result == "my_character"

    def test_valid_name_with_hyphen(self):
        """Test valid character name with hyphen."""
        result = validate_character_name("test-char")
        assert result == "test-char"

    def test_minimum_length_name(self):
        """Test minimum length character name."""
        result = validate_character_name("abc")
        assert result == "abc"

    def test_maximum_length_name(self):
        """Test maximum length character name."""
        name = "a" * 20
        result = validate_character_name(name)
        assert result == name

    def test_empty_character_name(self):
        """Test empty character name."""
        with pytest.raises(typer.BadParameter, match="Character name cannot be empty"):
            validate_character_name("")

    def test_character_name_too_short(self):
        """Test character name too short."""
        with pytest.raises(typer.BadParameter, match="Character name must be at least 3 characters long"):
            validate_character_name("ab")

    def test_character_name_too_long(self):
        """Test character name too long."""
        name = "a" * 21
        with pytest.raises(typer.BadParameter, match="Character name must be 20 characters or less"):
            validate_character_name(name)

    def test_character_name_invalid_characters(self):
        """Test character name with invalid characters."""
        with pytest.raises(typer.BadParameter, match="Character name can only contain"):
            validate_character_name("test@char")

    def test_character_name_with_spaces(self):
        """Test character name with spaces."""
        with pytest.raises(typer.BadParameter, match="Character name can only contain"):
            validate_character_name("test char")


class TestValidateItemCode:
    """Test validate_item_code function."""

    def test_valid_item_code(self):
        """Test valid item code."""
        result = validate_item_code("iron_sword")
        assert result == "iron_sword"

    def test_valid_item_code_with_numbers(self):
        """Test valid item code with numbers."""
        result = validate_item_code("potion_level_2")
        assert result == "potion_level_2"

    def test_empty_item_code(self):
        """Test empty item code."""
        with pytest.raises(typer.BadParameter, match="Item code cannot be empty"):
            validate_item_code("")

    def test_item_code_with_uppercase(self):
        """Test item code with uppercase letters."""
        with pytest.raises(typer.BadParameter, match="Item code should contain only lowercase"):
            validate_item_code("Iron_Sword")

    def test_item_code_with_hyphen(self):
        """Test item code with hyphen."""
        with pytest.raises(typer.BadParameter, match="Item code should contain only lowercase"):
            validate_item_code("iron-sword")

    def test_item_code_with_special_chars(self):
        """Test item code with special characters."""
        with pytest.raises(typer.BadParameter, match="Item code should contain only lowercase"):
            validate_item_code("iron@sword")


class TestValidateQuantity:
    """Test validate_quantity function."""

    def test_valid_quantity(self):
        """Test valid quantity."""
        result = validate_quantity(10)
        assert result == 10

    def test_minimum_quantity(self):
        """Test minimum valid quantity."""
        result = validate_quantity(1)
        assert result == 1

    def test_maximum_quantity(self):
        """Test maximum valid quantity."""
        result = validate_quantity(1000000)
        assert result == 1000000

    def test_zero_quantity(self):
        """Test zero quantity."""
        with pytest.raises(typer.BadParameter, match="Quantity must be greater than 0"):
            validate_quantity(0)

    def test_negative_quantity(self):
        """Test negative quantity."""
        with pytest.raises(typer.BadParameter, match="Quantity must be greater than 0"):
            validate_quantity(-5)

    def test_quantity_too_large(self):
        """Test quantity too large."""
        with pytest.raises(typer.BadParameter, match="Quantity is too large"):
            validate_quantity(1000001)


class TestValidateGoldAmount:
    """Test validate_gold_amount function."""

    def test_valid_gold_amount(self):
        """Test valid gold amount."""
        result = validate_gold_amount(1000)
        assert result == 1000

    def test_minimum_gold_amount(self):
        """Test minimum valid gold amount."""
        result = validate_gold_amount(1)
        assert result == 1

    def test_maximum_gold_amount(self):
        """Test maximum valid gold amount."""
        result = validate_gold_amount(1000000000)
        assert result == 1000000000

    def test_zero_gold_amount(self):
        """Test zero gold amount."""
        with pytest.raises(typer.BadParameter, match="Gold amount must be greater than 0"):
            validate_gold_amount(0)

    def test_negative_gold_amount(self):
        """Test negative gold amount."""
        with pytest.raises(typer.BadParameter, match="Gold amount must be greater than 0"):
            validate_gold_amount(-100)

    def test_gold_amount_too_large(self):
        """Test gold amount too large."""
        with pytest.raises(typer.BadParameter, match="Gold amount is too large"):
            validate_gold_amount(1000000001)


class TestValidateSkinCode:
    """Test validate_skin_code function."""

    def test_valid_skin_code(self):
        """Test valid skin code."""
        result = validate_skin_code("men1")
        assert result == "men1"

    def test_another_valid_skin_code(self):
        """Test another valid skin code."""
        result = validate_skin_code("women2")
        assert result == "women2"

    def test_invalid_skin_code(self):
        """Test invalid skin code."""
        with pytest.raises(typer.BadParameter, match="Invalid skin 'invalid_skin'"):
            validate_skin_code("invalid_skin")

    def test_empty_skin_code(self):
        """Test empty skin code."""
        with pytest.raises(typer.BadParameter, match="Invalid skin ''"):
            validate_skin_code("")


class TestValidateItemSlot:
    """Test validate_item_slot function."""

    def test_valid_item_slot(self):
        """Test valid item slot."""
        result = validate_item_slot("weapon")
        assert result == "weapon"

    def test_another_valid_item_slot(self):
        """Test another valid item slot."""
        result = validate_item_slot("helmet")
        assert result == "helmet"

    def test_utility_slot(self):
        """Test utility slot."""
        result = validate_item_slot("utility1")
        assert result == "utility1"

    def test_invalid_item_slot(self):
        """Test invalid item slot."""
        with pytest.raises(typer.BadParameter, match="Invalid slot 'invalid_slot'"):
            validate_item_slot("invalid_slot")

    def test_empty_item_slot(self):
        """Test empty item slot."""
        with pytest.raises(typer.BadParameter, match="Invalid slot ''"):
            validate_item_slot("")
