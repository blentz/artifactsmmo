"""Bid-vs-craft, RE-DENOMINATED IN ACTIONS (wave 6, increment 5.4).

This module used to test a private seconds model: `estimate_craft_seconds` summed
hand-set per-action constants over a recipe closure, `closure_leaf_kinds`
classified that closure's leaves, and `should_bid` compared the total against a
wall-clock horizon. All three are gone — the estimator was a SECOND cost model
drifting independently of the one every other route uses, and its comparison put
seconds against a horizon built by multiplying cycles by an average cycle length.

Their tests are deleted with them rather than adapted: their subject no longer
exists. What replaces them is thinner on purpose. `should_bid` is now a
comparison between two action counts, and the walk that produces one of them is
`decisions/route.route_price`, which has its own tests. Re-testing the closure
walk here would be a second opinion about a producer this module no longer owns.
"""

import json
from pathlib import Path

from artifactsmmo_cli.ai.acquisition_cost_core import UNOBTAINABLE_PER_UNIT
from artifactsmmo_cli.ai.bid_vs_craft import should_bid
from artifactsmmo_cli.ai.decisions.route import route_price
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem

_BUNDLE = (Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json")
CELL = "l32_held_task_closable"


def _gd() -> GameData:
    return GameData.from_cache_bundle(json.loads(_BUNDLE.read_text()))


def _state(game_data: GameData):
    return scenario_state(SCENARIOS[CELL], game_data)


def test_should_bid_compares_two_action_counts() -> None:
    """THE UNIT IS THE POINT. Both sides are planner actions, so the gate is a
    plain comparison with nothing converted.

    Asserted against `route_price` itself rather than a literal: a hard-coded
    expectation would pass while the two sides silently diverged, which is
    exactly what the seconds estimator did."""
    gd = _gd()
    state = _state(gd)
    priced = route_price(ObtainItem("iron_sword", 1), state, gd,
                         NO_PROFILE_CONTEXT, None)
    assert should_bid("iron_sword", 1, priced - 1, state, gd,
                      NO_PROFILE_CONTEXT) is True
    assert should_bid("iron_sword", 1, priced, state, gd,
                      NO_PROFILE_CONTEXT) is False


def test_the_boundary_is_strictly_greater_than() -> None:
    """A horizon EQUAL to the acquisition cost does not bid. Kept from the
    seconds-era suite because the strictness is a real decision: at equality,
    self-acquiring is already as good and does not depend on a stranger filling
    an order."""
    gd = _gd()
    state = _state(gd)
    priced = route_price(ObtainItem("iron_ore", 3), state, gd,
                         NO_PROFILE_CONTEXT, None)
    assert should_bid("iron_ore", 3, priced, state, gd,
                      NO_PROFILE_CONTEXT) is False
    assert should_bid("iron_ore", 3, priced - 1, state, gd,
                      NO_PROFILE_CONTEXT) is True


def test_an_unroutable_item_bids() -> None:
    """`UNOBTAINABLE_PER_UNIT` is far above any horizon, so an item we cannot
    route to at all bids — and that is right: a standing order is exactly what
    an unroutable item is for.

    This is the arm the seconds estimator could not express. Its closure walk
    returned a finite number for an item with no obtainable leaf, so an
    unroutable item read as CHEAP and the gate declined to bid on the one case
    a bid serves best."""
    gd = _gd()
    state = _state(gd)
    assert route_price(ObtainItem("no_such_item_xyzzy", 1), state, gd,
                       NO_PROFILE_CONTEXT, None) == UNOBTAINABLE_PER_UNIT
    assert should_bid("no_such_item_xyzzy", 1, 20, state, gd,
                      NO_PROFILE_CONTEXT) is True


def test_quantity_moves_the_decision() -> None:
    """NOT VACUOUS on quantity: a bigger ask costs more actions, so a horizon
    that declines one unit can accept many."""
    gd = _gd()
    state = _state(gd)
    one = route_price(ObtainItem("iron_ore", 1), state, gd, NO_PROFILE_CONTEXT, None)
    many = route_price(ObtainItem("iron_ore", 40), state, gd, NO_PROFILE_CONTEXT, None)
    assert many > one, (one, many)
    assert should_bid("iron_ore", 1, one, state, gd, NO_PROFILE_CONTEXT) is False
    assert should_bid("iron_ore", 40, one, state, gd, NO_PROFILE_CONTEXT) is True
