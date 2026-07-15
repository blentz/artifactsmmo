"""Tests for craft_plan_full — the deterministic full craft-plan driver."""

import pytest

from artifactsmmo_cli.ai.craft_plan_driver_core import _apply_state, craft_plan_full
from artifactsmmo_cli.ai.next_craft_core import NextAction
from artifactsmmo_cli.ai.obtain_sources import UNBOUNDED_CAPACITY, Source, SourceKind

COPPER: dict[str, dict[str, int]] = {
    "copper_ring": {"copper_bar": 1},
    "copper_bar": {"copper_ore": 10},
}

NO: dict[str, int] = {}


def test_full_chain_from_empty() -> None:
    """0 owned / 0 bank → gather 10 ore, craft 1 bar, craft 1 ring (consuming)."""
    plan = craft_plan_full(COPPER, NO, NO, "copper_ring", 1)
    assert plan == [
        NextAction("copper_ore", "gather", 10),
        NextAction("copper_bar", "craft", 1),
        NextAction("copper_ring", "craft", 1),
    ]


def test_banked_bar_withdraws_then_crafts() -> None:
    """1 copper_bar banked → withdraw it, then craft the ring (no gather/smelt)."""
    plan = craft_plan_full(COPPER, NO, {"copper_bar": 1}, "copper_ring", 1)
    assert plan == [
        NextAction("copper_bar", "withdraw", 1),
        NextAction("copper_ring", "craft", 1),
    ]


def test_already_satisfied_returns_empty() -> None:
    plan = craft_plan_full(COPPER, {"copper_ring": 1}, NO, "copper_ring", 1)
    assert plan == []


def test_partial_inventory_only_gathers_shortfall() -> None:
    """Own 5 ore, need 10 → gather only the 5-ore shortfall, then craft up."""
    plan = craft_plan_full(COPPER, {"copper_ore": 5}, NO, "copper_ring", 1)
    assert plan == [
        NextAction("copper_ore", "gather", 5),
        NextAction("copper_bar", "craft", 1),
        NextAction("copper_ring", "craft", 1),
    ]


def test_shared_intermediate_gathers_twice_consuming_model() -> None:
    """SOUNDNESS on shared intermediates: x feeds both a and b.

    Crafting a CONSUMES the gathered x, so x must be gathered AGAIN for b. A
    non-consuming model would gather x once and under-supply b — the bug this
    consuming driver avoids.
    """
    recipes: dict[str, dict[str, int]] = {
        "gadget": {"a": 1, "b": 1},
        "a": {"x": 1},
        "b": {"x": 1},
    }
    plan = craft_plan_full(recipes, NO, NO, "gadget", 1)
    assert plan == [
        NextAction("x", "gather", 1),
        NextAction("a", "craft", 1),
        NextAction("x", "gather", 1),   # gathered AGAIN — first x was consumed by craft a
        NextAction("b", "craft", 1),
        NextAction("gadget", "craft", 1),
    ]


def test_multi_unit_scales() -> None:
    """qty 3 rings → 3 bars → 30 ore."""
    plan = craft_plan_full(COPPER, NO, NO, "copper_ring", 3)
    assert plan == [
        NextAction("copper_ore", "gather", 30),
        NextAction("copper_bar", "craft", 3),
        NextAction("copper_ring", "craft", 3),
    ]


# --- widened obtain-model sources (Task 2: the descent reads the model
# instead of hard-coding "no recipe -> gather" as the only non-craft route) ---


def test_three_kind_map_is_byte_identical_to_today() -> None:
    """The regression guard: with only GATHER/CRAFT/WITHDRAW sources, the widened
    descent must produce EXACTLY the plan the old recipe-driven descent produced."""
    sources = {
        "copper_bar": [Source(SourceKind.CRAFT, "copper_bar", 1, UNBOUNDED_CAPACITY)],
        "copper_ore": [Source(SourceKind.GATHER, "copper_ore", 1, UNBOUNDED_CAPACITY)],
    }
    recipes = {"copper_bar": {"copper_ore": 10}}
    plan = craft_plan_full(recipes, NO, NO, "copper_bar", 6, sources)
    assert [(s.item, s.kind, s.qty) for s in plan] == [
        ("copper_ore", "gather", 60),
        ("copper_bar", "craft", 6),
    ]


def test_recycle_consumes_the_source_items() -> None:
    """_apply_state must debit the SOURCE item, or the plan double-spends it."""
    sources = {"ash_plank": [Source(SourceKind.RECYCLE, "fishing_net", 3, 21)]}
    owned, _bank = _apply_state(
        COPPER, {"fishing_net": 7}, {}, NextAction("ash_plank", "recycle", 6, "fishing_net"), sources
    )
    assert owned["ash_plank"] == 6
    assert owned["fishing_net"] == 7 - 2  # ceil(6 / yield 3) == 2 nets consumed


def test_recycle_capped_below_deficit_produces_mixed_recovery_plan() -> None:
    """CRITICAL 1 regression: recoverable stock (2 fishing_net, yield 3 each
    -> capacity 6) is LESS than the 10 ash_plank needed. The plan must be
    MIXED -- a capped recycle step for the recoverable 6, then a gather/craft
    step for the remaining 4 -- and NEVER claim more than the source can
    physically deliver (no negative simulated inventory at any point)."""
    sources = {"ash_plank": [Source(SourceKind.RECYCLE, "fishing_net", 3, 6)]}
    owned = {"fishing_net": 2}
    plan = craft_plan_full({}, owned, {}, "ash_plank", 10, sources)
    assert plan == [
        NextAction("ash_plank", "recycle", 6, "fishing_net"),
        NextAction("ash_plank", "gather", 4),
    ]
    cur_owned: dict[str, int] = dict(owned)
    cur_bank: dict[str, int] = {}
    for na in plan:
        cur_owned, cur_bank = _apply_state({}, cur_owned, cur_bank, na, sources)
        assert cur_owned["fishing_net"] >= 0, f"fishing_net went negative applying {na!r}"
    assert cur_owned["ash_plank"] == 10


def test_recycle_consumed_rounds_up_not_down() -> None:
    """consumed = ceil(qty / yield_per), NOT a truncating floor-div: 7 units
    needed at yield 4 requires 2 source copies (1 copy only yields 4, short
    by 3), not 1 (which floor-div would under-count and double-spend)."""
    sources = {"ash_plank": [Source(SourceKind.RECYCLE, "fishing_net", 4, 40)]}
    owned, _bank = _apply_state(
        COPPER, {"fishing_net": 10}, {}, NextAction("ash_plank", "recycle", 7, "fishing_net"), sources
    )
    assert owned["ash_plank"] == 7
    assert owned["fishing_net"] == 10 - 2  # ceil(7 / 4) == 2, not 7 // 4 == 1


def test_recycle_without_matching_source_raises() -> None:
    """A recycle NextAction whose source isn't in `sources` is a caller-invariant
    violation (the plan and the map used to apply it must be the same map)."""
    with pytest.raises(ValueError, match="no matching"):
        _apply_state(COPPER, {}, {}, NextAction("ash_plank", "recycle", 6, "fishing_net"), {})


def test_buy_adds_to_inventory_only() -> None:
    """BUY just adds to inventory — gold is NOT modelled in this pure core."""
    owned, _bank = _apply_state(COPPER, NO, NO, NextAction("lifesteal_rune", "buy", 1, "npc_merchant"))
    assert owned["lifesteal_rune"] == 1


def test_drop_adds_to_inventory_only() -> None:
    """DROP just adds to inventory — the stochastic drop rate is the same
    deliberate abstraction the existing Fight xp projection uses."""
    owned, _bank = _apply_state(COPPER, NO, NO, NextAction("dragon_scale", "drop", 2, "dragon"))
    assert owned["dragon_scale"] == 2
