"""The unaffordable CURRENCY LEAF — coverage-matrix cell 11.

`CanIAffordTheCurrencyLeaf` is the first node of the `ObtainItem` step graph and
its POSITIVE arm — route to `ReachCurrencyGoal` and FUND the currency instead of
gathering for a craft that cannot be paid for — fired in 0 of 36 scenarios.

**A design correction the cell could not be built without.** The arm needs
`analyze_currency_leaves(...).funding_target`, which is set only for a leaf
priced in `tasks_coin` at a PERMANENT, LOCATED vendor. All four `tasks_coin`
sinks in the bundle (`jasper_crystal`, `magical_cure`, `astralyte_crystal`,
`prime_fabric`) are sold by ONE npc, `tasks_trader`, whose map tile carries an
`achievement_unlocked` access condition on `tasks_farmer` — and the captured
account has that achievement INCOMPLETE. Access conditions are evaluated at map
build, so `npc_location('tasks_trader')` is None, the permanent-vendor list is
empty, and the arm is unreachable from EVERY scenario against the default
world. That is a fixture property, not a bot property, so the cell declares the
achievement (`ScenarioCharacter.unlocked_achievements`, new surface) rather than
being reported as impossible.

**What this file deliberately does NOT do.** It does not run the planner.
`ReachCurrencyGoal` has to accept a task, kill its monsters and complete it, and
measured on this cell that search runs 15,052 nodes and hits the 15 s budget —
the first scenario in the set to reach the planner's tail at all (the committed
set's previous maximum was 41 nodes). Asserting a 15 s timeout would test the
timeout, not the dimension, so the cell is asserted at the DECISION seam:
`objective_step_goal`, which is what production calls.
"""

import dataclasses
import json
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.currency_demand import analyze_currency_leaves
from artifactsmmo_cli.ai.scenario import (
    SCENARIOS,
    load_bundle_game_data,
    scenario_state,
)
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.strategy_driver import objective_step_goal
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.tiers.strategy import actionable_step
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"

CELL = "l25_currency_leaf_unfunded"
ACHIEVEMENT = "tasks_farmer"
VENDOR = "tasks_trader"
VENDOR_TILE = (5, 11)
LEAF = "jasper_crystal"
LEAF_PRICE = 8
ROOT_CODE = "king_slime_sword"


@pytest.fixture(scope="module")
def locked() -> GameData:
    """The world every other scenario is planned in: `tasks_farmer` incomplete,
    so the tasks_coin vendor's tile is not in any location index."""
    return load_bundle_game_data(BUNDLE)


@pytest.fixture(scope="module")
def unlocked() -> GameData:
    """The world THIS cell declares — and the declaration is read off the
    scenario, never chosen by the test."""
    return load_bundle_game_data(
        BUNDLE,
        completed_achievements=frozenset(SCENARIOS[CELL].unlocked_achievements))


def _state(game_data: GameData) -> WorldState:
    return scenario_state(SCENARIOS[CELL], game_data)


def _root() -> ObtainItem:
    return ObtainItem(code=ROOT_CODE, quantity=1, slot="weapon_slot")


# --- the world the cell declares, and why it has to declare one -------------

def test_the_scenario_declares_the_achievement_that_opens_the_vendor(
        locked: GameData, unlocked: GameData) -> None:
    """The whole reason this cell needs new fixture surface, as an assertion.

    Same bundle, same tile data — the ONLY difference is whether the account
    has completed `tasks_farmer`, and it decides whether the game's only
    permanent tasks_coin vendor exists at all."""
    assert SCENARIOS[CELL].unlocked_achievements == (ACHIEVEMENT,)
    assert locked.npc_location(VENDOR) is None
    assert unlocked.npc_location(VENDOR) == VENDOR_TILE
    assert unlocked.achievement_completed(ACHIEVEMENT)
    assert not locked.achievement_completed(ACHIEVEMENT)


def test_the_leaf_is_priced_only_in_tasks_coin_at_that_one_vendor(
        unlocked: GameData) -> None:
    """`funding_target` fires ONLY for a tasks_coin leaf, and the catalogue
    offers exactly one seller — so the vendor's reachability IS the dimension,
    not a detail of it."""
    assert unlocked.npc_purchases(LEAF) == [(VENDOR, LEAF_PRICE,
                                             TASKS_COIN_CODE)]
    sinks = {code for code, npc, _price
             in unlocked.currency_sinks(TASKS_COIN_CODE)}
    assert LEAF in sinks
    assert {npc for _code, npc, _price
            in unlocked.currency_sinks(TASKS_COIN_CODE)} == {VENDOR}


def test_an_unknown_achievement_code_is_refused(locked: GameData) -> None:
    """The new argument must not be a way to model a world the API cannot
    produce: a code the capture's registry does not carry RAISES rather than
    silently unlocking nothing."""
    raw = json.loads(BUNDLE.read_text())
    with pytest.raises(ValueError, match="achievement registry"):
        GameData.from_cache_bundle(
            raw, completed_achievements=frozenset({"not_an_achievement"}))
    assert locked.npc_location(VENDOR) is None


# --- the branch, reached through production's own seam ----------------------

def test_the_step_is_the_currency_leaf_itself(unlocked: GameData) -> None:
    """The character holds the iron and the slimeballs, so the descent's
    deepest unmet node IS the crystal — the "stepwise decomposition hands the
    mapper the currency item directly" shape that stalled the satchel live on
    2026-07-06."""
    state = _state(unlocked)
    step = actionable_step(_root(), state, unlocked, NO_PROFILE_CONTEXT,
                           grind_descent=False)
    assert step == ObtainItem(code=LEAF, quantity=1)


def test_the_step_graph_routes_to_funding_not_to_gathering(
        unlocked: GameData) -> None:
    """The positive arm, through `objective_step_goal` — the function
    production calls, which forwards to `obtain_item_decision`.

    0 tasks_coin held against a price of 8, so the leaf is unaffordable and
    fundable at once, which is exactly the pair the arm exists for."""
    state = _state(unlocked)
    assert state.inventory.get(TASKS_COIN_CODE, 0) == 0
    analysis = analyze_currency_leaves({LEAF: 1}, state, unlocked)
    assert analysis.blocked is True
    assert analysis.funding_target == (TASKS_COIN_CODE, LEAF_PRICE)
    goal = objective_step_goal(ObtainItem(code=LEAF, quantity=1), state,
                               unlocked, NO_PROFILE_CONTEXT, root=_root(),
                               history=None)
    assert repr(goal) == f"ReachCurrency({TASKS_COIN_CODE}, {LEAF_PRICE})"


def test_holding_the_coins_flips_the_arm_and_the_goal(
        unlocked: GameData) -> None:
    """Proof it bites, flip 1: the SAME character with 40 tasks_coin in the bag
    is not blocked, has no funding target, and the graph goes straight back to
    pursuing the weapon."""
    state = _state(unlocked)
    funded = dataclasses.replace(
        state, inventory={**state.inventory, TASKS_COIN_CODE: 40})
    analysis = analyze_currency_leaves({LEAF: 1}, funded, unlocked)
    assert analysis.blocked is False
    assert analysis.funding_target is None
    goal = objective_step_goal(ObtainItem(code=LEAF, quantity=1), funded,
                               unlocked, NO_PROFILE_CONTEXT, root=_root(),
                               history=None)
    assert "ReachCurrency" not in repr(goal)


def test_the_locked_world_cannot_reach_the_arm_at_all(
        locked: GameData) -> None:
    """Proof it bites, flip 2 — and the design correction as a
    failing-when-false assertion.

    Same character, same bag, achievement NOT declared: the vendor does not
    exist, so there is no fundable route and the arm is silent. The day the
    default world can fund a leaf, this fails and the claim above stops being
    true quietly."""
    state = _state(locked)
    analysis = analyze_currency_leaves({LEAF: 1}, state, locked)
    assert analysis.funding_target is None
    goal = objective_step_goal(ObtainItem(code=LEAF, quantity=1), state,
                               locked, NO_PROFILE_CONTEXT, root=_root(),
                               history=None)
    assert "ReachCurrency" not in repr(goal)


def test_no_other_scenario_can_route_a_funding_target(
        locked: GameData) -> None:
    """The gap the cell closes. Every OTHER scenario is planned in the locked
    world, so none of them can reach the arm for any closure — asserted over
    all four tasks_coin sinks rather than the one this cell uses."""
    sinks = [code for code, _npc, _price
             in locked.currency_sinks(TASKS_COIN_CODE)]
    assert len(sinks) == 4
    for name, scenario in SCENARIOS.items():
        if name == CELL:
            continue
        state = scenario_state(scenario, locked)
        for code in sinks:
            assert analyze_currency_leaves(
                {code: 1}, state, locked).funding_target is None, (name, code)
