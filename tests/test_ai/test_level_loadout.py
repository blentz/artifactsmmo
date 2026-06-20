"""Tests for the catalog-wide best-equipment-by-level proxy (WinnableAcrossBand sweep)."""

from artifactsmmo_cli.ai.equipment.level_loadout import (
    best_weapon_for_level,
    obtainable_hp_bonus_ceiling,
    obtainable_inventory_for_level,
)
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


# ---------------------------------------------------------------------------
# obtainable_inventory_for_level
# ---------------------------------------------------------------------------


def test_obtainable_inventory_empty_catalog() -> None:
    assert obtainable_inventory_for_level({}, 10) == {}


def test_obtainable_inventory_only_equippable_types_included() -> None:
    """Consumables and non-equip types are excluded; weapons and armor are kept."""
    stats = {
        "sword": _weapon("sword", 1, {"fire": 5}),
        "helm": ItemStats(code="helm", level=1, type_="helmet", resistance={"fire": 10}),
        "potion": ItemStats(code="potion", level=1, type_="consumable", hp_restore=50),
        "raw_mat": ItemStats(code="raw_mat", level=1, type_="resource"),
    }
    result = obtainable_inventory_for_level(stats, 10)
    assert result == {"sword": 1, "helm": 1}


def test_obtainable_inventory_excludes_items_above_level() -> None:
    stats = {
        "low_sword": _weapon("low_sword", 5, {"fire": 10}),
        "high_sword": _weapon("high_sword", 15, {"fire": 30}),
        "low_boots": ItemStats(code="low_boots", level=5, type_="boots", hp_bonus=20),
        "high_boots": ItemStats(code="high_boots", level=15, type_="boots", hp_bonus=50),
    }
    result = obtainable_inventory_for_level(stats, 10)
    assert result == {"low_sword": 1, "low_boots": 1}


def test_obtainable_inventory_quantity_is_always_one() -> None:
    """Each item gets quantity 1 (presence in catalog = one obtainable copy)."""
    stats = {
        "sword": _weapon("sword", 1, {"fire": 5}),
        "armor": ItemStats(code="armor", level=1, type_="body_armor", resistance={"fire": 10}),
    }
    result = obtainable_inventory_for_level(stats, 10)
    assert all(qty == 1 for qty in result.values())


def test_obtainable_inventory_at_exact_level_boundary() -> None:
    """item.level == L is included; item.level == L+1 is excluded."""
    stats = {
        "at_level": _weapon("at_level", 5, {"fire": 10}),
        "above_level": _weapon("above_level", 6, {"fire": 20}),
    }
    result = obtainable_inventory_for_level(stats, 5)
    assert result == {"at_level": 1}


# ---------------------------------------------------------------------------
# obtainable_hp_bonus_ceiling
# ---------------------------------------------------------------------------


def test_hp_bonus_ceiling_empty_catalog() -> None:
    assert obtainable_hp_bonus_ceiling({}, 10) == 0


def test_hp_bonus_ceiling_no_hp_bonus_items() -> None:
    """Items with hp_bonus=0 contribute nothing to the ceiling."""
    stats = {
        "sword": _weapon("sword", 1, {"fire": 5}),  # hp_bonus defaults to 0
        "helm": ItemStats(code="helm", level=1, type_="helmet"),  # hp_bonus=0
    }
    assert obtainable_hp_bonus_ceiling(stats, 10) == 0


def test_hp_bonus_ceiling_sums_max_per_type() -> None:
    """Best hp_bonus per type is summed across distinct types."""
    stats = {
        "helm_low": ItemStats(code="helm_low", level=1, type_="helmet", hp_bonus=10),
        "helm_high": ItemStats(code="helm_high", level=5, type_="helmet", hp_bonus=30),
        "boots": ItemStats(code="boots", level=1, type_="boots", hp_bonus=15),
    }
    # helmets: max hp_bonus = 30; boots: 15 → ceiling = 45
    assert obtainable_hp_bonus_ceiling(stats, 10) == 45


def test_hp_bonus_ceiling_excludes_above_level() -> None:
    """Items above the level cap are excluded from the ceiling."""
    stats = {
        "helm_ok": ItemStats(code="helm_ok", level=5, type_="helmet", hp_bonus=20),
        "helm_too_high": ItemStats(code="helm_too_high", level=15, type_="helmet", hp_bonus=100),
    }
    assert obtainable_hp_bonus_ceiling(stats, 10) == 20


def test_hp_bonus_ceiling_excludes_non_equippable_types() -> None:
    """Non-equip types (consumables, resources) don't contribute to ceiling."""
    stats = {
        "potion": ItemStats(code="potion", level=1, type_="consumable", hp_restore=200, hp_bonus=0),
        "helm": ItemStats(code="helm", level=1, type_="helmet", hp_bonus=25),
    }
    assert obtainable_hp_bonus_ceiling(stats, 10) == 25


def test_hp_bonus_ceiling_guarantees_hp_ge_projected_max() -> None:
    """Core soundness check: base + ceiling >= base + any-item's hp_bonus
    for every obtainable item, so state.hp >= p.max_hp for any loadout."""
    base_max_hp = 200
    stats = {
        "helm": ItemStats(code="helm", level=5, type_="helmet", hp_bonus=30),
        "boots": ItemStats(code="boots", level=5, type_="boots", hp_bonus=15),
        "sword": _weapon("sword", 5, {"fire": 10}),  # hp_bonus=0
    }
    ceiling = obtainable_hp_bonus_ceiling(stats, 5)
    # ceiling must be >= the hp_bonus of any individual obtainable item
    for s in stats.values():
        if s.level <= 5:
            assert base_max_hp + ceiling >= base_max_hp + s.hp_bonus


def test_hp_bonus_ceiling_multi_slot_rings_sum_top_two() -> None:
    """Multi-slot types sum top-N hp_bonus values (N = slot count).

    pick_loadout equips ring1_slot + ring2_slot independently, so the ceiling
    must be >= copper_ring.hp_bonus + iron_ring.hp_bonus (5 + 3 = 8), NOT just
    max(5, 3) = 5.  The old per-type-max logic returned 5; the corrected
    sum-top-N logic returns 8.
    """
    base_max_hp = 200
    stats = {
        "copper_ring": ItemStats(code="copper_ring", level=5, type_="ring", hp_bonus=5),
        "iron_ring": ItemStats(code="iron_ring", level=5, type_="ring", hp_bonus=3),
    }
    ceiling = obtainable_hp_bonus_ceiling(stats, 5)
    # Must cover BOTH rings (two ring slots), not just the best one.
    assert ceiling >= 5 + 3, (
        f"ceiling {ceiling} undercounts: two ring slots require hp_bonus sum of "
        f"both rings (5 + 3 = 8), not just max (5)"
    )
    assert base_max_hp + ceiling >= base_max_hp + 5 + 3
