"""equipped_matches_loadout: per-slot match of equipped vs an optimal loadout."""

from artifactsmmo_cli.ai.loadout_match import equipped_matches_loadout


def test_exact_match_is_true() -> None:
    equipment = {"weapon_slot": "water_bow", "helmet_slot": "copper_helmet"}
    optimal = {"weapon_slot": "water_bow"}
    assert equipped_matches_loadout(equipment, optimal) is True


def test_per_slot_mismatch_is_false() -> None:
    # optimal wants water_bow in the weapon slot; a mining tool is equipped.
    equipment = {"weapon_slot": "copper_pickaxe"}
    optimal = {"weapon_slot": "water_bow"}
    assert equipped_matches_loadout(equipment, optimal) is False


def test_optimal_subset_matches_when_equipment_has_extra_slots() -> None:
    # equipment fills more slots than optimal names; only the named slots bind.
    equipment = {"weapon_slot": "water_bow", "boots_slot": "leather_boots"}
    optimal = {"weapon_slot": "water_bow"}
    assert equipped_matches_loadout(equipment, optimal) is True


def test_missing_slot_in_equipment_is_false() -> None:
    # optimal wants a weapon the character has not equipped at all.
    equipment: dict[str, str | None] = {}
    optimal = {"weapon_slot": "water_bow"}
    assert equipped_matches_loadout(equipment, optimal) is False


def test_optimal_none_placeholder_requires_empty_slot() -> None:
    # optimal explicitly wants the slot EMPTY; a filled slot mismatches.
    equipment = {"utility1_slot": "small_health_potion"}
    optimal = {"utility1_slot": None}
    assert equipped_matches_loadout(equipment, optimal) is False


def test_optimal_none_matches_absent_slot() -> None:
    # equipment lacks the slot (get -> None) and optimal wants None -> match.
    equipment: dict[str, str | None] = {}
    optimal = {"utility1_slot": None}
    assert equipped_matches_loadout(equipment, optimal) is True


def test_empty_optimal_is_vacuously_true() -> None:
    assert equipped_matches_loadout({"weapon_slot": "water_bow"}, {}) is True
