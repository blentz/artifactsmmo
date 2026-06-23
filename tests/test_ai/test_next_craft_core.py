"""Tests for next_craft_target_pure — deterministic next craft/gather/withdraw action."""

from artifactsmmo_cli.ai.next_craft_core import NextAction, next_craft_target_pure

COPPER_RECIPES: dict[str, dict[str, int]] = {
    "copper_ring": {"copper_bar": 6},
    "copper_bar": {"copper_ore": 10},
}

NO_BANK: dict[str, int] = {}


def test_copper_ring_chain_all_zero_returns_gather_ore() -> None:
    """Deepest dependency of copper_ring with 0 owned: gather copper_ore."""
    result = next_craft_target_pure(COPPER_RECIPES, {}, NO_BANK, "copper_ring", 3)
    assert result == NextAction("copper_ore", "gather", 180)


def test_copper_ring_chain_with_ore_owned_returns_craft_bar() -> None:
    """180 ore owned → next action is to craft 18 bars."""
    result = next_craft_target_pure(
        COPPER_RECIPES, {"copper_ore": 180}, NO_BANK, "copper_ring", 3
    )
    assert result == NextAction("copper_bar", "craft", 18)


def test_copper_ring_chain_with_bars_owned_returns_craft_ring() -> None:
    """18 bars owned → next action is to craft 3 rings."""
    result = next_craft_target_pure(
        COPPER_RECIPES, {"copper_bar": 18}, NO_BANK, "copper_ring", 3
    )
    assert result == NextAction("copper_ring", "craft", 3)


def test_satisfied_returns_none() -> None:
    """Already have qty of target → returns None."""
    result = next_craft_target_pure(
        COPPER_RECIPES, {"copper_ring": 3}, NO_BANK, "copper_ring", 3
    )
    assert result is None


def test_satisfied_with_excess_returns_none() -> None:
    """More than qty of target → returns None."""
    result = next_craft_target_pure(
        COPPER_RECIPES, {"copper_ring": 5}, NO_BANK, "copper_ring", 3
    )
    assert result is None


def test_partial_ore_owned_returns_gather_deficit() -> None:
    """100 ore owned but need 180 → gather deficit of 80."""
    result = next_craft_target_pure(
        COPPER_RECIPES, {"copper_ore": 100}, NO_BANK, "copper_ring", 3
    )
    assert result == NextAction("copper_ore", "gather", 80)


def test_raw_target_with_no_recipe_returns_gather() -> None:
    """Target with no recipe → gather the full qty."""
    result = next_craft_target_pure({}, {}, NO_BANK, "copper_ore", 5)
    assert result == NextAction("copper_ore", "gather", 5)


def test_multi_input_first_short_input_selected() -> None:
    """Two-input recipe: when both inputs are short, the FIRST short input is returned."""
    recipes: dict[str, dict[str, int]] = {"widget": {"a": 1, "b": 1}}
    # Both 'a' and 'b' are raw (no recipes); owned = {}
    result = next_craft_target_pure(recipes, {}, NO_BANK, "widget", 1)
    # 'a' is first in dict order and is short → returns gather 'a'
    assert result == NextAction("a", "gather", 1)


def test_multi_input_first_satisfied_second_short() -> None:
    """Two-input recipe: first input satisfied, second input short → returns second."""
    recipes: dict[str, dict[str, int]] = {"widget": {"a": 1, "b": 1}}
    result = next_craft_target_pure(recipes, {"a": 1}, NO_BANK, "widget", 1)
    assert result == NextAction("b", "gather", 1)


def test_multi_input_all_satisfied_returns_craft() -> None:
    """Two-input recipe: all inputs satisfied → returns craft the target."""
    recipes: dict[str, dict[str, int]] = {"widget": {"a": 1, "b": 1}}
    result = next_craft_target_pure(recipes, {"a": 1, "b": 1}, NO_BANK, "widget", 1)
    assert result == NextAction("widget", "craft", 1)


def test_raw_target_partial_owned_returns_deficit() -> None:
    """Raw target with partial ownership → gather the deficit."""
    result = next_craft_target_pure({}, {"copper_ore": 3}, NO_BANK, "copper_ore", 5)
    assert result == NextAction("copper_ore", "gather", 2)


# --- withdraw branch (banked intermediates) ---


def test_banked_intermediate_returns_withdraw() -> None:
    """A banked copper_bar (short in inventory) → withdraw it, not gather/craft.

    Need 18 bars for 3 rings; inventory has 0, bank has 5 → withdraw min(5, 18)=5.
    """
    result = next_craft_target_pure(
        COPPER_RECIPES, {}, {"copper_bar": 5}, "copper_ring", 3
    )
    assert result == NextAction("copper_bar", "withdraw", 5)


def test_withdraw_capped_by_shortfall() -> None:
    """Bank holds more than the shortfall → withdraw only the shortfall.

    Need 6 bars for 1 ring; have 4 in inventory → short 2; bank has 10 →
    withdraw min(10, 2)=2.
    """
    result = next_craft_target_pure(
        COPPER_RECIPES, {"copper_bar": 4}, {"copper_bar": 10}, "copper_ring", 1
    )
    assert result == NextAction("copper_bar", "withdraw", 2)


def test_banked_raw_returns_withdraw() -> None:
    """A banked raw input (copper_ore) short in inventory → withdraw, not gather."""
    result = next_craft_target_pure(
        COPPER_RECIPES, {}, {"copper_ore": 50}, "copper_ring", 3
    )
    # First short input down the chain is copper_bar (not banked) → descend →
    # copper_ore short, banked → withdraw min(50, 180)=50.
    assert result == NextAction("copper_ore", "withdraw", 50)


def test_unbanked_short_input_still_recurses() -> None:
    """Bank holds an UNRELATED item → no withdraw; normal gather descent."""
    result = next_craft_target_pure(
        COPPER_RECIPES, {}, {"unrelated": 99}, "copper_ring", 3
    )
    assert result == NextAction("copper_ore", "gather", 180)
