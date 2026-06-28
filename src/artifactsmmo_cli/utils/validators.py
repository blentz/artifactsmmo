"""Input validation utilities for the CLI."""

import re

import typer
from artifactsmmo_api_client.models.item_slot import ItemSlot

from artifactsmmo_cli.api_wrapper import APIWrapper


def validate_coordinates(x: int, y: int) -> tuple[int, int]:
    """Validate map coordinates."""
    # Basic validation - coordinates should be reasonable
    if x < -100 or x > 100:
        raise typer.BadParameter(f"X coordinate {x} is out of reasonable range (-100 to 100)")
    if y < -100 or y > 100:
        raise typer.BadParameter(f"Y coordinate {y} is out of reasonable range (-100 to 100)")
    return x, y


def validate_character_name(name: str) -> str:
    """Validate character name format."""
    if not name:
        raise typer.BadParameter("Character name cannot be empty")

    if len(name) < 3:
        raise typer.BadParameter("Character name must be at least 3 characters long")

    if len(name) > 20:
        raise typer.BadParameter("Character name must be 20 characters or less")

    # Check for valid characters (alphanumeric and some special chars)
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        raise typer.BadParameter("Character name can only contain letters, numbers, underscores, and hyphens")

    return name


def validate_item_code(code: str) -> str:
    """Validate item code format."""
    if not code:
        raise typer.BadParameter("Item code cannot be empty")

    # Item codes are typically lowercase with underscores
    if not re.match(r"^[a-z0-9_]+$", code):
        raise typer.BadParameter("Item code should contain only lowercase letters, numbers, and underscores")

    return code


def validate_quantity(quantity: int) -> int:
    """Validate item quantity."""
    if quantity <= 0:
        raise typer.BadParameter("Quantity must be greater than 0")

    if quantity > 1000000:
        raise typer.BadParameter("Quantity is too large (max 1,000,000)")

    return quantity


def validate_gold_amount(amount: int) -> int:
    """Validate gold amount."""
    if amount <= 0:
        raise typer.BadParameter("Gold amount must be greater than 0")

    if amount > 1000000000:
        raise typer.BadParameter("Gold amount is too large (max 1,000,000,000)")

    return amount


def validate_skin_code(skin: str, api: APIWrapper) -> str:
    """Validate character skin code against the live skins catalog.

    Skins became dynamic data in API v8.0.0 (the static CharacterSkin enum was removed),
    so the valid set must come from the /skins endpoint rather than a hardcoded list.
    """
    valid_skins: list[str] = []
    page = 1
    while True:
        response = api.get_all_skins(page=page)
        if response is None or not response.data:
            break
        valid_skins.extend(s.code for s in response.data)
        if page >= response.pages:
            break
        page += 1

    if skin not in valid_skins:
        raise typer.BadParameter(f"Invalid skin '{skin}'. Valid skins: {', '.join(valid_skins)}")

    return skin


def validate_item_slot(slot: str) -> str:
    """Validate item slot."""
    valid_slots = [s.value for s in ItemSlot]

    if slot not in valid_slots:
        raise typer.BadParameter(f"Invalid slot '{slot}'. Valid slots: {', '.join(valid_slots)}")

    return slot
