"""Tests for the catalog-wide best-weapon-by-level proxy (WinnableAcrossBand sweep)."""

from artifactsmmo_cli.ai.equipment.level_loadout import best_weapon_for_level
from artifactsmmo_cli.ai.item_catalog import ItemStats


def _weapon(code: str, level: int, attack: dict[str, int]) -> ItemStats:
    return ItemStats(code=code, level=level, type_="weapon", attack=attack)


def test_empty_catalog_returns_none() -> None:
    assert best_weapon_for_level({}, 10) is None


def test_no_weapon_at_or_below_level_returns_none() -> None:
    stats = {"big_sword": _weapon("big_sword", 20, {"fire": 50})}
    assert best_weapon_for_level(stats, 10) is None


def test_non_weapon_types_excluded() -> None:
    stats = {
        "helm": ItemStats(code="helm", level=1, type_="helmet", resistance={"fire": 30}),
        "potion": ItemStats(code="potion", level=1, type_="consumable", hp_restore=50),
    }
    assert best_weapon_for_level(stats, 10) is None


def test_picks_max_total_attack_among_eligible() -> None:
    stats = {
        "weak": _weapon("weak", 1, {"fire": 5}),
        "strong": _weapon("strong", 5, {"fire": 10, "earth": 8}),
        "too_high": _weapon("too_high", 30, {"fire": 100}),
    }
    best = best_weapon_for_level(stats, 10)
    assert best is not None
    assert best.code == "strong"


def test_total_attack_sums_across_elements() -> None:
    stats = {
        "mono": _weapon("mono", 1, {"fire": 15}),
        "spread": _weapon("spread", 1, {"fire": 6, "earth": 6, "water": 6}),
    }
    best = best_weapon_for_level(stats, 5)
    assert best is not None
    assert best.code == "spread"  # 18 > 15


def test_tie_broken_by_higher_item_level_then_code() -> None:
    # Equal total attack (10): higher item level wins.
    stats = {
        "low": _weapon("low", 2, {"fire": 10}),
        "high": _weapon("high", 8, {"fire": 10}),
    }
    best = best_weapon_for_level(stats, 10)
    assert best is not None
    assert best.code == "high"


def test_tie_on_attack_and_level_broken_by_code() -> None:
    # Equal attack AND level: deterministic last-code-lexicographically.
    stats = {
        "aaa": _weapon("aaa", 3, {"fire": 7}),
        "zzz": _weapon("zzz", 3, {"fire": 7}),
    }
    best = best_weapon_for_level(stats, 5)
    assert best is not None
    assert best.code == "zzz"
