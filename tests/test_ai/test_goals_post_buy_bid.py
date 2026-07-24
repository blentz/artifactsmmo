"""Tests for the GE_BID discretionary means: the shared `ge_bid_candidates`
predicate, the reactive `PostBuyBidGoal`, its `_fires` guard, and the
`map_means` wiring.

GameData is built bare with its private catalog attributes assigned directly —
the established construction pattern for these pure `ai/` modules (see
`test_bid_vs_craft.py` / `test_ge_buy_source_integration.py`).
"""

from artifactsmmo_cli.ai.actions.ge_post_buy import GePostBuyOrderAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.ge_bid import ge_bid_candidates
from artifactsmmo_cli.ai.ge_order_config import BID_FILL_HORIZON_SECONDS
from artifactsmmo_cli.ai.goals.post_buy_bid import POST_BUY_BID_VALUE, PostBuyBidGoal
from artifactsmmo_cli.ai.open_order import OpenOrder, OrderSide
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.strategy_driver import map_means
from artifactsmmo_cli.ai.tiers.means import MeansKind, means_fires
from tests.test_ai.fixtures import make_state


def _gd(
    *,
    recipes=None,
    monster_drops=None,
    resource_drops=None,
    npc_stock=None,
    ge_buy_orders=None,
    ge_sell_orders=None,
    ge_loc=(7, 7),
) -> GameData:
    gd = GameData()
    gd._crafting_recipes = recipes or {}
    if monster_drops is not None:
        gd._monster_drops = monster_drops
    gd._resource_drops = resource_drops or {}
    gd._npc_stock = npc_stock or {}
    gd._npc_locations = {npc: (1, 0) for npc in (npc_stock or {})}
    gd._ge_buy_orders = ge_buy_orders or {}
    gd._ge_sell_orders = ge_sell_orders or {}
    gd._grand_exchange_location = ge_loc
    return gd


def _steel_gd(**over) -> GameData:
    """steel <- iron x2; iron is a very-rare monster drop (slow to self-craft,
    ~1000s >> the 600s bid horizon), sold by an NPC at 100, with a standing GE
    buy order at 40 to overbid."""
    defaults = dict(
        recipes={"steel": {"iron": 2}},
        monster_drops={"mob": [("iron", 50, 1, 1)]},
        npc_stock={"shop": {"steel": 100}},
        ge_buy_orders={"steel": ("b1", 40, 5)},
        ge_sell_orders={},
    )
    defaults.update(over)
    return _gd(**defaults)


def _ctx(step_profile) -> SelectionContext:
    return SelectionContext(
        bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
        initial_xp=0, task_exchange_min_coins=5, combat_monster=None,
        step_profile=step_profile)


def _state(**over):
    base = dict(gold=1000, inventory={}, x=0, y=0)
    base.update(over)
    return make_state(**base)


# --------------------------------------------------------------------------- #
# ge_bid_candidates
# --------------------------------------------------------------------------- #

def test_candidate_for_slow_to_craft_needed_item():
    gd = _steel_gd()
    cands = ge_bid_candidates(_state(), gd, _ctx({"steel": 1}), BID_FILL_HORIZON_SECONDS)
    # overbid best_buy 40 by one tick, ceiling 100-1; 41 < 99 -> 41.
    assert cands == [("steel", 1, 41)]


def test_qty_is_net_of_held():
    gd = _steel_gd()
    st = _state(inventory={"steel": 1})
    cands = ge_bid_candidates(st, gd, _ctx({"steel": 3}), BID_FILL_HORIZON_SECONDS)
    assert cands == [("steel", 2, 41)]


def test_no_candidate_when_already_held():
    gd = _steel_gd()
    st = _state(inventory={"steel": 5})
    assert ge_bid_candidates(st, gd, _ctx({"steel": 3}), BID_FILL_HORIZON_SECONDS) == []


def test_held_counts_bank_and_equipped():
    gd = _steel_gd()
    st = _state(bank_items={"steel": 1}, equipment={"weapon_slot": "steel"})
    # wanted 2, held (bank 1 + equipped 1) = 2 -> nothing needed.
    assert ge_bid_candidates(st, gd, _ctx({"steel": 2}), BID_FILL_HORIZON_SECONDS) == []


def test_suppressed_when_open_order_exists():
    gd = _steel_gd()
    st = _state(open_orders=(OpenOrder("x", "steel", 1, 41, OrderSide.BUY, 0),))
    assert ge_bid_candidates(st, gd, _ctx({"steel": 1}), BID_FILL_HORIZON_SECONDS) == []


def test_no_candidate_when_fast_to_craft():
    # plank <- wood x2, deterministic gather (~17s << horizon) -> should_bid False.
    gd = _gd(recipes={"plank": {"wood": 2}}, resource_drops={"tree": "wood"},
             npc_stock={"shop": {"plank": 100}}, ge_buy_orders={"plank": ("b", 40, 5)})
    assert ge_bid_candidates(_state(), gd, _ctx({"plank": 1}), BID_FILL_HORIZON_SECONDS) == []


def test_no_candidate_without_npc_alternative():
    gd = _steel_gd(npc_stock={})  # no NPC sells steel -> no alt cost to bound the price
    assert ge_bid_candidates(_state(), gd, _ctx({"steel": 1}), BID_FILL_HORIZON_SECONDS) == []


def test_no_candidate_without_live_buy_anchor():
    gd = _steel_gd(ge_buy_orders={})  # no anchor -> buy_post_price None -> fail closed
    assert ge_bid_candidates(_state(), gd, _ctx({"steel": 1}), BID_FILL_HORIZON_SECONDS) == []


def test_no_candidate_when_venue_is_ge_fill():
    # A standing sell order at 30 <= post_price 41 -> choose_buy_venue3 == GE (fill),
    # not GE_POST: fill the cheaper standing order instead of posting.
    gd = _steel_gd(ge_sell_orders={"steel": ("s1", 30, 5)})
    assert ge_bid_candidates(_state(), gd, _ctx({"steel": 1}), BID_FILL_HORIZON_SECONDS) == []


def test_no_candidate_without_grand_exchange():
    gd = _steel_gd(ge_loc=None)
    assert ge_bid_candidates(_state(), gd, _ctx({"steel": 1}), BID_FILL_HORIZON_SECONDS) == []


def test_empty_step_profile_no_candidates():
    gd = _steel_gd()
    assert ge_bid_candidates(_state(), gd, _ctx({}), BID_FILL_HORIZON_SECONDS) == []


# --------------------------------------------------------------------------- #
# PostBuyBidGoal
# --------------------------------------------------------------------------- #

def test_goal_emits_post_buy_action():
    gd = _steel_gd()
    goal = PostBuyBidGoal(game_data=gd, ctx=_ctx({"steel": 1}))
    actions = goal.relevant_actions([], _state(), gd)
    assert len(actions) == 1
    a = actions[0]
    assert isinstance(a, GePostBuyOrderAction)
    assert (a.item_code, a.quantity, a.price, a.ge_location) == ("steel", 1, 41, (7, 7))


def test_goal_not_satisfied_when_candidate_exists():
    gd = _steel_gd()
    goal = PostBuyBidGoal(game_data=gd, ctx=_ctx({"steel": 1}))
    st = _state()
    assert goal.is_satisfied(st) is False
    assert goal.value(st, gd) == POST_BUY_BID_VALUE


def test_goal_satisfied_when_no_candidate():
    gd = _steel_gd()
    goal = PostBuyBidGoal(game_data=gd, ctx=_ctx({}))
    st = _state()
    assert goal.is_satisfied(st) is True
    assert goal.value(st, gd) == 0.0


def test_goal_posting_bid_suppresses_next_cycle():
    # Fire-and-lose: after applying the posted order the item has an open order,
    # so the goal is satisfied on the resulting state (no re-fire).
    gd = _steel_gd()
    goal = PostBuyBidGoal(game_data=gd, ctx=_ctx({"steel": 1}))
    st = _state()
    action = goal.relevant_actions([], st, gd)[0]
    posted = action.apply(st, gd)
    assert goal.is_satisfied(posted) is True


def test_goal_relevant_actions_empty_without_ge():
    gd = _steel_gd(ge_loc=None)
    goal = PostBuyBidGoal(game_data=gd, ctx=_ctx({"steel": 1}))
    assert goal.relevant_actions([], _state(), gd) == []


def test_goal_desired_state_and_repr():
    gd = _steel_gd()
    goal = PostBuyBidGoal(game_data=gd, ctx=_ctx({"steel": 1}))
    assert goal.desired_state(_state(), gd) == {"ge_bids_posted": True}
    assert repr(goal) == "PostBuyBid"


# --------------------------------------------------------------------------- #
# means _fires + map_means wiring
# --------------------------------------------------------------------------- #

def test_ge_bid_fires_when_candidate_exists():
    gd = _steel_gd()
    assert means_fires(MeansKind.GE_BID, _state(), gd, None, _ctx({"steel": 1})) is True


def test_ge_bid_does_not_fire_without_candidate():
    gd = _steel_gd()
    assert means_fires(MeansKind.GE_BID, _state(), gd, None, _ctx({})) is False


def test_map_means_builds_post_buy_bid_goal():
    gd = _steel_gd()
    goal = map_means(MeansKind.GE_BID, gd, _ctx({"steel": 1}), _state())
    assert isinstance(goal, PostBuyBidGoal)
    assert repr(goal) == "PostBuyBid"
