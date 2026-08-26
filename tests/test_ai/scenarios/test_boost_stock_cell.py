"""CRAFT_POTIONS' BOOST-STOCK arm — coverage-matrix cell 13.

`potion_supply.craft_potions_fires` has three arms — unlock-boost (`:184-189`),
boost-stock (`:210-220`), heal-deficit (`:222-225`) — and
`CraftPotionsGoal._active_craft` has the matching three. Measured over the 42
committed cells before this one was added: the guard fires in **5**, and every
one takes the HEAL arm. The boost-stock arm was suite-invisible. Live it is
invisible too — `cycles.action_repr` records the executed action, not the goal
arm that chose it, so a `Craft(water_boost_potion)` row cannot be attributed to
the unlock arm or to this one.

**This cell is a DEFECT WITNESS, not a green confirmation.** Reaching the arm
deliberately shows it proposing a craft that destroys its own precondition:

* The arm fires only when the heal stock is SATISFIED. On this cell that stock
  is 40 `small_health_potion` in `utility1_slot`.
* `craft_ladder._TARGET_SLOT` is the hard-coded string `"utility1_slot"`, so
  the boost the arm sizes is equipped into **that same slot**, displacing the
  heal stack the arm's precondition depends on — while `utility2_slot`, which
  `EquipAction.is_applicable`'s own comment calls out as legal for "two
  DIFFERENT consumables across the utility slots", stays empty.
* After the plan the heal stock is 0, the guard fires again immediately, and
  the goal has switched to the HEAL arm. That is a two-cycle alternation
  between arms 2 and 3, not convergence.
* `EquipAction.apply` returns exactly **one** unit of the displaced code to
  inventory regardless of the utility stack's quantity, so the projection also
  loses 39 of the 40 heals.

The tests below pin the arm's reachability AND that behaviour, so the day the
slot choice is fixed they fail and say which of the two changed.
"""

import dataclasses

import pytest

from artifactsmmo_cli.ai.boost_selection import best_boost_potion
from artifactsmmo_cli.ai.craft_ladder import _TARGET_SLOT
from artifactsmmo_cli.ai.equipped_potion import equipped_potion_qty
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.craft_potions import CraftPotionsGoal
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.potion_baseline import potion_baseline_pure
from artifactsmmo_cli.ai.potion_supply import (
    craft_potions_fires,
    primary_combat_target,
    target_potion_pure,
)
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.thresholds import (
    POTION_HIGH_LEVEL,
    POTION_HIGH_QTY,
    POTION_LOW_LEVEL,
    POTION_LOW_QTY,
)
from artifactsmmo_cli.ai.tiers.guards import GuardKind, active_guards
from artifactsmmo_cli.ai.unlock_boost import unlock_boost_target
from artifactsmmo_cli.ai.world_state import WorldState

CELL = "l20_boost_stock"
HEAL = "small_health_potion"
BOOST = "earth_boost_potion"
"""The boost `best_boost_potion` returns for this loadout against `highwayman`
— named so a catalogue or margin change that moves it fails here rather than
silently retargeting the cell at a different potion."""
MONSTER = "highwayman"


@pytest.fixture
def state(bundle_game_data: GameData) -> WorldState:
    return scenario_state(SCENARIOS[CELL], bundle_game_data)


def _goal(state: WorldState, game_data: GameData) -> CraftPotionsGoal:
    """The goal built the way `strategy_driver.map_guard` builds it: seeded from
    the state, with `combat_monster` = the guard's own `primary_combat_target`."""
    return CraftPotionsGoal(game_data=game_data, state=state,
                            combat_monster=primary_combat_target(state, game_data))


def _planned(state: WorldState, game_data: GameData):
    player = GamePlayer(character=CELL, history=None)
    player.seed_offline(state, game_data)
    return player, player.plan_from_state()


def _arm_is_boost_stock(state: WorldState, game_data: GameData) -> bool:
    """The arm the GOAL took, read off the goal's own answer rather than
    restated: not the unlock arm (which the goal reports by
    `unlock_boost_target`), and a target that is not the heal target."""
    plan = _goal(state, game_data)._active_craft(state, game_data)
    return (plan is not None
            and unlock_boost_target(state, game_data) is None
            and plan[0] != target_potion_pure(state, game_data))


# --- the precondition the arm needs -----------------------------------------

def test_the_heal_stock_is_exactly_satisfied(
        bundle_game_data: GameData, state: WorldState) -> None:
    """The arm's gate is `deficit <= 0`, and the cell sits ON the boundary: 40
    equipped against a level-20 ramp of 40. One potion fewer and arm 2 owns the
    cycle (`test_one_potion_fewer_moves_the_guard_back_to_the_heal_arm`)."""
    assert target_potion_pure(state, bundle_game_data) == HEAL
    assert equipped_potion_qty(state, HEAL) == 40
    ramp = potion_baseline_pure(state.level, POTION_LOW_LEVEL, POTION_LOW_QTY,
                                POTION_HIGH_LEVEL, POTION_HIGH_QTY)
    assert ramp == 40
    goal = _goal(state, bundle_game_data)
    deficit = (goal._baseline(state.level, state, bundle_game_data, None)
               - goal._equipped(state, bundle_game_data))
    assert deficit <= 0


def test_the_stall_breaker_is_silent_so_only_the_stock_arm_can_fire(
        bundle_game_data: GameData, state: WorldState) -> None:
    """`unlock_boost_target` is a TOTAL-STALL condition (no in-band monster is
    bare-winnable). It must be None here or the cell would be exercising arm 1,
    which `l30_rune_fill` already covers."""
    assert unlock_boost_target(state, bundle_game_data) is None
    assert primary_combat_target(state, bundle_game_data) == MONSTER
    assert best_boost_potion(state, bundle_game_data, MONSTER) == BOOST
    assert equipped_potion_qty(state, BOOST) == 0


def test_guard_and_goal_size_the_boost_from_the_SAME_baseline(
        bundle_game_data: GameData, state: WorldState) -> None:
    """The divergence this arm could have had and does NOT. `_active_craft`'s
    arm 3 and `craft_potions_fires`' boost arm both call
    `potion_baseline_pure(level, ...)` — the raw level ramp — on the same
    `equipped_potion_qty`. (The HEAL arms both use the combat-projected
    `potion_stock_target_pure` instead; the two families are internally
    consistent, which is what matters.) Pinned by identity: the goal's sized
    batch must close exactly the ramp deficit the guard measured."""
    ramp = potion_baseline_pure(state.level, POTION_LOW_LEVEL, POTION_LOW_QTY,
                                POTION_HIGH_LEVEL, POTION_HIGH_QTY)
    guard_deficit = ramp - equipped_potion_qty(state, BOOST)
    plan = _goal(state, bundle_game_data)._active_craft(state, bundle_game_data)
    assert plan is not None
    code, runs, equip_qty = plan
    assert code == BOOST
    assert guard_deficit == 40
    # 3 held units of each ingredient -> 3 runs at yield 2 -> 6 equipped, all of
    # it inside the 40-unit ramp deficit the guard fired on.
    assert (runs, equip_qty) == (3, 6)
    assert equip_qty <= guard_deficit


# --- the arm fires, through the real seams ----------------------------------

def test_the_guard_fires_and_the_goal_agrees_on_the_boost_arm(
        bundle_game_data: GameData, state: WorldState) -> None:
    """Guard and goal are PAIRED on this arm — the guard opens the rung and the
    goal has boost work, in the same cycle. This is the assertion an earlier
    scoping document said could not hold."""
    assert craft_potions_fires(state, bundle_game_data, None) is True
    assert _arm_is_boost_stock(state, bundle_game_data) is True


def test_the_arbiter_selects_it_and_plans_the_boost_craft(
        bundle_game_data: GameData, state: WorldState) -> None:
    """Through `plan_from_state`, not through `_active_craft` directly — the two
    pre-existing arm-3 tests call the private method and are blind to whether
    the arbiter can ever get there."""
    player, report = _planned(state, bundle_game_data)
    assert GuardKind.CRAFT_POTIONS in active_guards(
        state, bundle_game_data, None, player._last_ctx)
    assert repr(report.selected_goal) == "CraftPotionsGoal"
    assert [repr(a) for a in report.plan] == [
        f"Craft({BOOST}×3)",
        f"Equip({BOOST}x6->utility1_slot)",
    ]


def test_the_goal_prices_this_arm_at_zero(
        bundle_game_data: GameData, state: WorldState) -> None:
    """`CraftPotionsGoal.value` has no boost-stock arm: `plan` is not None,
    `unlock_boost_target` is None, so it returns the HEAL deficit — which is
    <= 0 by this arm's own precondition. Recorded as a fact, NOT as a defect
    that changes a decision: `select_pure` orders candidates by BAND and skips
    on `is_satisfied`, never on `value`, and the only two readers of
    `Goal.priority` (`strategy_driver:866`, `player:1234`) both put it in a log
    line. The cost is that every live boost-stock cycle records
    `priority: 0.0`, which is one more reason the arm is hard to attribute."""
    goal = _goal(state, bundle_game_data)
    assert goal._active_craft(state, bundle_game_data) is not None
    assert goal.value(state, bundle_game_data, None) == 0.0
    assert goal.is_satisfied(state) is False


# --- the defect the cell exists to witness ----------------------------------

def test_the_arm_equips_the_boost_over_its_own_precondition(
        bundle_game_data: GameData, state: WorldState) -> None:
    """DEFECT WITNESS. `_TARGET_SLOT` is hard-coded, so the boost lands in the
    slot holding the heal stack whose satisfaction gated this arm. Applying the
    plan takes the heal stock 40 -> 0 with `utility2_slot` still empty, and
    `EquipAction.apply` credits back ONE unit of a 40-unit stack.

    If a fix moves the ladder to a free utility slot, this test fails and the
    docstring above says which assertion to retire."""
    assert _TARGET_SLOT == "utility1_slot"
    assert state.equipment.get("utility2_slot") is None
    _player, report = _planned(state, bundle_game_data)
    after = state
    for action in report.plan:
        after = action.apply(after, bundle_game_data)
    assert after.equipment["utility1_slot"] == BOOST
    assert equipped_potion_qty(after, BOOST) == 6
    assert equipped_potion_qty(after, HEAL) == 0
    assert after.equipment.get("utility2_slot") is None
    assert after.inventory.get(HEAL) == 1


def test_the_next_cycle_reverses_the_arm_instead_of_converging(
        bundle_game_data: GameData, state: WorldState) -> None:
    """DEFECT WITNESS, second half. The guard re-fires immediately and the goal
    is back on the HEAL arm asking for the whole 40-potion stack it just had —
    a two-cycle alternation between arms 2 and 3, which is what "the arm
    destroys its own precondition" means operationally."""
    _player, report = _planned(state, bundle_game_data)
    after = state
    for action in report.plan:
        after = action.apply(after, bundle_game_data)
    assert craft_potions_fires(after, bundle_game_data, None) is True
    assert _arm_is_boost_stock(after, bundle_game_data) is False
    assert _goal(after, bundle_game_data)._active_craft(
        after, bundle_game_data) == (HEAL, 20, 40)


# --- the cell bites, and it is the only one ---------------------------------

def test_one_potion_fewer_moves_the_guard_back_to_the_heal_arm(
        bundle_game_data: GameData, state: WorldState) -> None:
    """Proof it bites. ONE field changes — the utility1 quantity, 40 -> 39 —
    and the guard is still up but the arm is the heal one."""
    understocked = dataclasses.replace(state, utility1_slot_quantity=39)
    assert craft_potions_fires(understocked, bundle_game_data, None) is True
    assert _arm_is_boost_stock(understocked, bundle_game_data) is False
    plan = _goal(understocked, bundle_game_data)._active_craft(
        understocked, bundle_game_data)
    assert plan is not None and plan[0] == HEAL


def test_this_is_the_only_cell_that_reaches_the_boost_stock_arm(
        bundle_game_data: GameData) -> None:
    """The gap the cell closes, measured over the whole set. The other cells
    that fire the guard are named, so a change that silences one of them fails
    here instead of quietly shrinking the measurement."""
    firing, boost_arm = set(), set()
    for name, scenario in SCENARIOS.items():
        world = scenario_state(scenario, bundle_game_data)
        if craft_potions_fires(world, bundle_game_data, None):
            firing.add(name)
            if _arm_is_boost_stock(world, bundle_game_data):
                boost_arm.add(name)
    assert boost_arm == {CELL}
    assert firing == {CELL, "l10_copper_adequate", "l21_grey_material_grind",
                      "l22_grey_rung_grind", "l20_relief_full_bank",
                      "l20_bag_critical_empty_bank"}
