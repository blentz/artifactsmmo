"""Tests for craft_plan_full — the deterministic full craft-plan driver."""

from artifactsmmo_cli.ai.craft_plan_driver_core import craft_plan_full
from artifactsmmo_cli.ai.next_craft_core import NextAction

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
