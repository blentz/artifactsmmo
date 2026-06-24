"""Unit tests for RecipeCostMemo.

Recipe graph under test:
  copper_ring -> copper_bar (qty=1)
  copper_bar  -> copper_ore (qty=10)
  copper_ore  -- raw (no recipe)
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recipe_closure import closure_demand
from artifactsmmo_cli.ai.recipe_cost_memo import RecipeCostMemo


def _make_gd() -> GameData:
    gd = GameData()
    gd._crafting_recipes = {
        "copper_bar": {"copper_ore": 10},
        "copper_ring": {"copper_bar": 6},
    }
    return gd


def test_full_cost_matches_closure_demand() -> None:
    """full_cost must equal a direct closure_demand call on the same GameData."""
    gd = _make_gd()
    memo = RecipeCostMemo(gd)

    expected: dict[str, int] = {}
    closure_demand("copper_ring", 1, gd, expected, frozenset())

    result = memo.full_cost("copper_ring")
    assert result == expected


def test_full_cost_memoized_identity() -> None:
    """A second full_cost call returns the identical dict object (cache hit)."""
    gd = _make_gd()
    memo = RecipeCostMemo(gd)

    first = memo.full_cost("copper_ring")
    second = memo.full_cost("copper_ring")
    assert first is second


def test_full_cost_after_clear_recomputes() -> None:
    """After clear(), the next call recomputes (different object than before)."""
    gd = _make_gd()
    memo = RecipeCostMemo(gd)

    before = memo.full_cost("copper_ring")
    memo.clear()
    after = memo.full_cost("copper_ring")

    assert before is not after
    # Value equality still holds.
    assert before == after


def test_full_cost_raw_item() -> None:
    """full_cost of a raw item (no recipe) matches closure_demand result."""
    gd = _make_gd()
    memo = RecipeCostMemo(gd)

    expected: dict[str, int] = {}
    closure_demand("copper_ore", 1, gd, expected, frozenset())

    result = memo.full_cost("copper_ore")
    assert result == expected


def test_clear_before_build_is_noop() -> None:
    """clear() on a not-yet-built memo must not raise (safe no-op)."""
    gd = _make_gd()
    memo = RecipeCostMemo(gd)
    memo.clear()  # must not raise


def test_game_data_recipe_cost_accessor() -> None:
    """GameData.recipe_cost returns a RecipeCostMemo and the same instance each call."""
    gd = _make_gd()
    m1 = gd.recipe_cost
    m2 = gd.recipe_cost
    assert isinstance(m1, RecipeCostMemo)
    assert m1 is m2


def test_game_data_recipe_cost_clear_on_reload() -> None:
    """Setting _crafting_recipes clears the memo so next call recomputes."""
    gd = _make_gd()
    first = gd.recipe_cost.full_cost("copper_ring")

    # Simulate a recipe reload via the setter.
    gd._crafting_recipes = {
        "copper_bar": {"copper_ore": 10},
        "copper_ring": {"copper_bar": 6},
    }

    second = gd.recipe_cost.full_cost("copper_ring")
    assert first is not second
