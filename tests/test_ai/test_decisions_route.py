"""`ai/decisions/route.py` — the ONE pricing funnel for the resolution graph.

Wave 4 increment 4.1b. This module ships INERT: nothing under `ai/decisions/`
calls it yet, and that is deliberate. Wave 4's `WhichSlotClosesTheFight` (4.2)
is its first caller, and wave 6 completes the dispatch for the two `MetaGoal`
variants left unpriced here.

It lands now, ahead of its caller, because wave 6's obligation O6 forbids any
module under `ai/decisions/` importing `acquisition_cost` except this one. If
4.2 shipped the import inside `decisions/root.py` instead, O6 would be red the
day it was written.
"""

import json
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.acquisition_cost import acquisition_actions
from artifactsmmo_cli.ai.decisions.route import route_price
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import (
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)

BUNDLE = (Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json")
CELL = "l32_held_task_closable"


@pytest.fixture(scope="module")
def gd() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def _state(game_data: GameData):
    return scenario_state(SCENARIOS[CELL], game_data)


def test_obtain_item_prices_through_acquisition_actions(gd: GameData) -> None:
    """The funnel FORWARDS, it does not re-implement. Asserted against the
    function it forwards to, so a divergence in either is a failure here."""
    state = _state(gd)
    goal = ObtainItem("iron_sword", 1)
    assert route_price(goal, state, gd, NO_PROFILE_CONTEXT, None) == \
        acquisition_actions("iron_sword", 1, state, gd, NO_PROFILE_CONTEXT,
                            equip=False, store=None)


def test_equip_is_derived_from_slot_and_nothing_else(gd: GameData) -> None:
    """`equip` is `slot is not None` — the C11 rule. A slotted goal prices the
    equip action, an unslotted one does not, and the caller never passes it.

    This is the assertion that would fail if someone re-introduced an `equip=`
    parameter and let it disagree with the slot."""
    state = _state(gd)
    slotted = route_price(ObtainItem("iron_sword", 1, slot="weapon_slot"),
                          state, gd, NO_PROFILE_CONTEXT, None)
    bare = route_price(ObtainItem("iron_sword", 1), state, gd,
                       NO_PROFILE_CONTEXT, None)
    assert slotted == acquisition_actions(
        "iron_sword", 1, state, gd, NO_PROFILE_CONTEXT, equip=True, store=None)
    assert bare == acquisition_actions(
        "iron_sword", 1, state, gd, NO_PROFILE_CONTEXT, equip=False, store=None)
    # NOT VACUOUS: the two arms genuinely differ, by exactly the equip action.
    # Measured 10 vs 9 here. Without this line the test above would pass even
    # if `equip` made no difference to the price, which is the shape that makes
    # an assertion decorative.
    assert slotted == bare + 1


def test_quantity_is_forwarded(gd: GameData) -> None:
    """Not pinned by the two tests above, both of which use quantity=1."""
    state = _state(gd)
    assert route_price(ObtainItem("iron_ore", 5), state, gd,
                       NO_PROFILE_CONTEXT, None) == \
        acquisition_actions("iron_ore", 5, state, gd, NO_PROFILE_CONTEXT,
                            equip=False, store=None)


@pytest.mark.parametrize("goal", [
    ReachCharLevel(level=33),
    ReachSkillLevel(skill="weaponcrafting", level=16),
])
def test_unpriced_variants_raise_rather_than_defaulting(gd: GameData, goal) -> None:
    """The two variants wave 6 completes RAISE, naming themselves.

    A silent default here would be a WALL: a level root priced 0 would outrank
    every gear root, and priced high would be unreachable — either way the
    graph would rank on a number nobody chose. The repo's rule is API data or
    fail, and an unimplemented arm is the same shape."""
    with pytest.raises(NotImplementedError, match=type(goal).__name__):
        route_price(goal, _state(gd), gd, NO_PROFILE_CONTEXT, None)
