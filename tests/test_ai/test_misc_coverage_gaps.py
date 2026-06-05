"""Coverage-gap closers for small remaining branches."""

from fractions import Fraction

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.level_skill import LevelSkillGoal
from artifactsmmo_cli.ai.scalar_priority import yield_bonus_for_goal
from artifactsmmo_cli.ai.tiers.means import _has_sellable
from tests.test_ai.fixtures import make_state


def test_level_skill_goal_max_depth_is_100():
    """Crafts can need deep recipe chains; budget matches GatherMaterials."""
    assert LevelSkillGoal("weaponcrafting", 3).max_depth == 100


def test_yield_bonus_for_goal_history_none_returns_zero():
    """yield_bonus_for_goal short-circuits to 0 when history is absent."""
    state = make_state()
    gd = GameData()
    assert yield_bonus_for_goal("AcceptTask", state, gd, None) == Fraction(0)


def test_has_sellable_skips_zero_qty():
    """_has_sellable iterates inventory but skips items with qty <= 0."""
    state = make_state(inventory={"copper_dagger": 0})
    gd = GameData()
    gd._npc_sell_prices = {"merchant": {"copper_dagger": 5}}
    assert _has_sellable(state, gd) is False


def test_has_sellable_skips_no_buyer():
    """_has_sellable skips items with qty > 0 but no NPC buys them."""
    state = make_state(inventory={"obscure_item": 1})
    gd = GameData()
    assert _has_sellable(state, gd) is False


def test_has_sellable_skips_untradeable():
    """_has_sellable skips items whose stats.tradeable=False."""
    state = make_state(inventory={"bound_item": 1})
    gd = GameData()
    gd._npc_sell_prices = {"merchant": {"bound_item": 5}}
    gd._item_stats = {
        "bound_item": ItemStats(code="bound_item", level=1, type_="weapon",
                                tradeable=False),
    }
    assert _has_sellable(state, gd) is False


def test_has_sellable_true_when_tradeable_and_has_buyer():
    """Sanity check for the positive path (qty > 0, buyer exists, tradeable)."""
    state = make_state(inventory={"good_item": 1})
    gd = GameData()
    gd._npc_sell_prices = {"merchant": {"good_item": 5}}
    gd._item_stats = {
        "good_item": ItemStats(code="good_item", level=1, type_="weapon",
                               tradeable=True),
    }
    assert _has_sellable(state, gd) is True
