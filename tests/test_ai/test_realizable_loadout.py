"""Coverage tests for equipment/realizable_loadout.py.

Diff tests live under formal/diff/ but need the Lean oracle to run.
These tests cover the pure-Python branches so the 100% coverage
gate (CLAUDE.md) holds locally."""

from artifactsmmo_cli.ai.equipment.realizable_loadout import (
    is_realizable,
    ownership,
)


def test_ownership_inventory_only():
    """Item only in inventory: count is inventory[code]."""
    assert ownership("copper_dagger", {"copper_dagger": 3}, {}) == 3


def test_ownership_equipped_only():
    """Item only equipped: count is +1 per slot holding it."""
    assert ownership(
        "copper_dagger", {},
        {"weapon_slot": "copper_dagger", "shield_slot": None},
    ) == 1


def test_ownership_inventory_plus_equipped():
    """Item in both inventory and equipped: sum."""
    assert ownership(
        "copper_dagger", {"copper_dagger": 2},
        {"weapon_slot": "copper_dagger"},
    ) == 3


def test_ownership_zero_when_absent():
    assert ownership("missing", {}, {}) == 0


def test_is_realizable_true_when_inventory_covers_loadout():
    """Two copies of copper_ring needed (ring1+ring2), two in inventory."""
    loadout = {"ring1_slot": "copper_ring", "ring2_slot": "copper_ring"}
    inventory = {"copper_ring": 2}
    current_equipment: dict[str, str | None] = {}
    assert is_realizable(loadout, inventory, current_equipment) is True


def test_is_realizable_false_when_inventory_short():
    """Two copies needed, one in inventory → not realizable."""
    loadout = {"ring1_slot": "copper_ring", "ring2_slot": "copper_ring"}
    inventory = {"copper_ring": 1}
    current_equipment: dict[str, str | None] = {}
    assert is_realizable(loadout, inventory, current_equipment) is False


def test_is_realizable_counts_currently_equipped():
    """Currently-equipped copies count toward demand."""
    loadout = {"ring1_slot": "copper_ring", "ring2_slot": "copper_ring"}
    inventory = {"copper_ring": 1}
    current_equipment: dict[str, str | None] = {"ring1_slot": "copper_ring"}
    assert is_realizable(loadout, inventory, current_equipment) is True


def test_is_realizable_skips_none_slots():
    """None entries in loadout don't add demand."""
    loadout: dict[str, str | None] = {"weapon_slot": None, "shield_slot": None}
    assert is_realizable(loadout, {}, {}) is True


def test_is_realizable_empty_loadout_true():
    """No demand → trivially realizable."""
    loadout: dict[str, str | None] = {}
    assert is_realizable(loadout, {}, {}) is True
