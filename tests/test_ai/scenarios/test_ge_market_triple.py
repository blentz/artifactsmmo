"""The GRAND-EXCHANGE dimension of the scenario set — coverage-matrix cells 4/5/7.

Until the order book was captured into the bundle, `obtain_sources` emitted
`GE_FILL` in 0 of 30 scenarios and a test PINNED it shut, so twelve call sites
across ten production modules were provably dead in every offline test. That is
what let a standing sell order turn a skill grind's descent off at its root on
2026-08-24 with no test able to catch it.

Three cells, ONE character, two axes:

| cell | `ge_market` | `gearcrafting` | the `_source_leafs` arm it reaches |
|---|---|---|---|
| 4 `l12_ge_book_grind`    | busy  | 9 (one short) | `CRAFT_SUBSTITUTE_KINDS`: GE_FILL does NOT leaf |
| 5 `l12_ge_book_adequate` | busy  | 10 (adequate) | the general arm: GE_FILL LEAFS |
| 7 `l12_quiet_book_grind` | quiet | 9 (one short) | none — no GE_FILL exists (CONTROL) |

**Cell 7 is why the other two mean anything.** Cells 4 and 5 assert that a
descent behaves a certain way in a market with standing orders; without a row
that is identical except for the market, neither could tell "the order book
changed the answer" from "the answer was always that".

The honest reading of the cell-4/cell-7 pair, stated here rather than left for
someone to discover: they agree on the final step. That is not a failure, it is
what "the fix is in" MEANS — the grind descends past the standing order to the
material it must gather, exactly as it does when no order exists. The pair is
non-vacuous because the same busy market reaches a DIFFERENT answer the moment
the grind flag comes off (`test_the_busy_book_changes_the_answer_without_the_grind_flag`),
which is precisely the pre-fix behaviour and precisely what cell 5 institutionalises.
"""

import json
import time
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.obtain_sources import SourceKind, obtain_sources
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.tiers.prerequisite_graph import (
    CRAFT_SUBSTITUTE_KINDS,
    prerequisites,
)
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from artifactsmmo_cli.ai.tiers.strategy import actionable_step
from artifactsmmo_cli.ai.world_state import WorldState

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"

CELL4_BUSY_GRIND = "l12_ge_book_grind"
CELL7_QUIET_GRIND = "l12_quiet_book_grind"
CELL5_BUSY_ADEQUATE = "l12_ge_book_adequate"
TRIPLE = (CELL4_BUSY_GRIND, CELL7_QUIET_GRIND, CELL5_BUSY_ADEQUATE)

SKILL = "gearcrafting"
RUNG = "feather_coat"
"""The grind rung both `gearcrafting 9` cells land on. Depth-2 and DROP-FED
(`{feather: 5, ash_plank: 2}`; feather off the chicken, ash_plank from
ash_wood) — the shape that is 70.7 % of the catalogue and 87.2 % of live
`UpgradeEquipment` cycles and carried 4 of the 30 committed scenarios."""

LEG_TARGET = "iron_legs_armor"
"""Cell 5's rung: `{iron_bar: 5, cowhide: 3}`, also depth-2 drop-fed, and the
item Robby stalled on live."""

PLAN_BUDGET_SECONDS = 2.0
"""A ceiling, not a measurement. Hydrating the order book took the 30-scenario
`plan_from_state` sweep from 3.3 s to 48.5 s and pinned three scenarios to the
15 s planner budget, so a GE cell that drifts into the tail is a real risk. The
three cells here measure 0.03-0.06 s; this bound fails long before a cell
starts testing the timeout instead of the dimension."""


@pytest.fixture(scope="module")
def quiet() -> GameData:
    return load_bundle_game_data(BUNDLE)


@pytest.fixture(scope="module")
def busy() -> GameData:
    return load_bundle_game_data(BUNDLE, with_ge_orders=True)


def _market(name: str, quiet: GameData, busy: GameData) -> GameData:
    """The GameData a scenario DECLARES, never one the test picked."""
    return busy if SCENARIOS[name].ge_market else quiet


def _state(name: str, game_data: GameData) -> WorldState:
    return scenario_state(SCENARIOS[name], game_data)


def _kinds(code: str, state: WorldState, game_data: GameData) -> set[SourceKind]:
    return {s.kind for s in obtain_sources(code, state, game_data, NO_PROFILE_CONTEXT)}


# --- the dimension is real, and the control really is a control -------------

def test_the_triple_varies_only_the_market_and_the_skill() -> None:
    """Cell 7 is character-identical to cell 4 apart from its market, and cell 5
    apart from one skill level. Anything else drifting apart makes the
    three-way comparison meaningless, so it is asserted rather than trusted."""
    four, seven, five = (SCENARIOS[n] for n in TRIPLE)
    assert (four.level, four.gold, four.inventory, four.bank, four.equipment) == \
           (seven.level, seven.gold, seven.inventory, seven.bank, seven.equipment)
    assert four.skills == seven.skills
    assert (four.ge_market, seven.ge_market) == (True, False)
    # cell 5 moves ONE field against cell 4 — the skill the rung is gated on.
    assert five.ge_market is True
    assert {k: v for k, v in five.skills.items() if k != SKILL} == \
           {k: v for k, v in four.skills.items() if k != SKILL}
    assert (four.skills[SKILL], five.skills[SKILL]) == (9, 10)


def test_the_declared_market_is_the_market_the_harness_builds(
        quiet: GameData, busy: GameData) -> None:
    """`ge_market` is not decoration: it selects the world, and the two worlds
    disagree about the rung's source set. Without this the control could be
    silently planned in the busy book and nobody would notice."""
    for name in TRIPLE:
        game_data = _market(name, quiet, busy)
        state = _state(name, game_data)
        rung = skill_grind_target(SKILL, state, game_data)
        assert rung is not None
        kinds = _kinds(rung, state, game_data)
        assert (SourceKind.GE_FILL in kinds) is SCENARIOS[name].ge_market, (
            name, rung, kinds)


def test_the_control_market_really_is_empty(quiet: GameData) -> None:
    """Mechanism 3, checked head-on: the control's emptiness must come from the
    market and not from the item being uninteresting. The SAME code carries a
    standing sell order in the busy book — asserted in the test above — so this
    `None` is the market talking."""
    state = _state(CELL7_QUIET_GRIND, quiet)
    assert quiet.ge_best_sell_order(RUNG) is None
    assert _kinds(RUNG, state, quiet) == {SourceKind.CRAFT}


# --- cell 4: the GE arm of the grind descent --------------------------------

def test_cell4_reaches_the_craft_substitute_arm(busy: GameData) -> None:
    """The branch the cell targets, named and shown: `_source_leafs`'
    `CRAFT_SUBSTITUTE_KINDS` arm, entered with a GE_FILL source under a grind.

    The observable is `prerequisites`: under `grind_descent` the standing order
    must NOT end the walk, so the rung still reports its recipe inputs. Under
    the pre-fix rule it reported none and `actionable_step` handed the rung
    straight back — the 2026-08-24 stall."""
    assert SourceKind.GE_FILL in CRAFT_SUBSTITUTE_KINDS
    state = _state(CELL4_BUSY_GRIND, busy)
    assert SourceKind.GE_FILL in _kinds(RUNG, state, busy)
    node = ObtainItem(code=RUNG, quantity=1)
    assert prerequisites(node, state, busy, NO_PROFILE_CONTEXT, True) != []
    step = actionable_step(node, state, busy, NO_PROFILE_CONTEXT,
                           grind_descent=True)
    assert step == ObtainItem(code="ash_wood", quantity=10)


def test_the_busy_book_changes_the_answer_without_the_grind_flag(
        busy: GameData, quiet: GameData) -> None:
    """What makes cells 4 and 7 non-vacuous despite agreeing.

    In the BUSY book the descent's answer depends on the grind flag — the
    standing order leafs the walk at the rung when the flag is off and does not
    when it is on. In the QUIET book the flag makes no difference at all,
    because there is no order to leaf on. So the order book IS load-bearing
    here, and the grind arm is what neutralises it: exactly the pair of facts
    that "cell 4 and cell 7 reach the same step" would otherwise hide."""
    node = ObtainItem(code=RUNG, quantity=1)

    busy_state = _state(CELL4_BUSY_GRIND, busy)
    busy_grind = actionable_step(node, busy_state, busy, NO_PROFILE_CONTEXT,
                                 grind_descent=True)
    busy_plain = actionable_step(node, busy_state, busy, NO_PROFILE_CONTEXT,
                                 grind_descent=False)
    assert busy_grind != busy_plain
    assert busy_plain == ObtainItem(code=RUNG, quantity=1)

    quiet_state = _state(CELL7_QUIET_GRIND, quiet)
    quiet_grind = actionable_step(node, quiet_state, quiet, NO_PROFILE_CONTEXT,
                                  grind_descent=True)
    quiet_plain = actionable_step(node, quiet_state, quiet, NO_PROFILE_CONTEXT,
                                  grind_descent=False)
    assert quiet_grind == quiet_plain == busy_grind


# --- cell 5: the other arm — a GE_FILL outside a grind DOES leaf ------------

def test_cell5_leafs_the_descent_on_the_standing_order(
        busy: GameData, quiet: GameData) -> None:
    """`_source_leafs`' general arm, reached with a GE_FILL and no grind flag.

    The flip is total: the busy book's descent reports NO prerequisites (the
    order hands the finished item over) while the quiet book's reports the
    recipe. Same character, same node, same call — only the market differs."""
    node = ObtainItem(code=LEG_TARGET, quantity=1, slot="leg_armor_slot")
    busy_state = _state(CELL5_BUSY_ADEQUATE, busy)
    quiet_state = _state(CELL5_BUSY_ADEQUATE, quiet)

    assert SourceKind.GE_FILL in _kinds(LEG_TARGET, busy_state, busy)
    assert _kinds(LEG_TARGET, quiet_state, quiet) == {SourceKind.CRAFT}

    assert prerequisites(node, busy_state, busy, NO_PROFILE_CONTEXT, False) == []
    assert prerequisites(node, quiet_state, quiet, NO_PROFILE_CONTEXT, False) == [
        ObtainItem(code="iron_bar", quantity=5),
        ObtainItem(code="cowhide", quantity=3),
    ]
    # ...and the grind flag restores the recipe even in the busy book, which is
    # cell 4's rule seen from cell 5's row.
    assert prerequisites(node, busy_state, busy, NO_PROFILE_CONTEXT, True) != []


def test_cell5_changes_the_planned_first_action(busy: GameData,
                                                quiet: GameData) -> None:
    """The dimension flip reaching all the way to an ACTION, not a predicate.

    The same character buys the leg armour off the book in the busy market and
    walks to the iron rocks in the quiet one. This is the strongest evidence in
    the file that the GE bundle key is load-bearing: before it existed, the
    left-hand side of this assertion was unreachable offline."""
    busy_report = _plan(CELL5_BUSY_ADEQUATE, busy)
    quiet_report = _plan(CELL5_BUSY_ADEQUATE, quiet)
    assert busy_report.plan and quiet_report.plan
    assert "GeBuy" in repr(busy_report.plan[0])
    assert LEG_TARGET in repr(busy_report.plan[0])
    assert "GeBuy" not in repr(quiet_report.plan[0])
    assert repr(busy_report.selected_goal) != repr(quiet_report.selected_goal)


def _plan(name: str, game_data: GameData):
    player = GamePlayer(character=name, history=None)
    player.seed_offline(_state(name, game_data), game_data)
    return player.plan_from_state()


# --- runtime: a cell in the planner's tail tests the timeout, not the dimension

def test_every_ge_cell_plans_well_inside_the_budget(quiet: GameData,
                                                    busy: GameData) -> None:
    """Measured 0.03-0.06 s each when this landed. The design measured that a
    populated book can take a scenario to the 15 s planner budget wall, so the
    cost is asserted rather than assumed."""
    for name in TRIPLE:
        game_data = _market(name, quiet, busy)
        started = time.monotonic()
        report = _plan(name, game_data)
        elapsed = time.monotonic() - started
        assert report.selected_goal is not None
        assert elapsed < PLAN_BUDGET_SECONDS, f"{name} planned in {elapsed:.2f}s"


def test_the_bundle_carries_the_book_these_cells_need() -> None:
    """The fixture-level premise. An `ge_orders` key that quietly emptied would
    turn cells 4 and 5 into two more copies of cell 7 with no test failing —
    the same shape as the empty book that hid for weeks."""
    raw = json.loads(BUNDLE.read_text())
    orders = raw["ge_orders"]["orders"]
    assert len(orders) > 0
    assert any(o["code"] == RUNG and o["type"] == "sell" for o in orders)
    assert any(o["code"] == LEG_TARGET and o["type"] == "sell" for o in orders)
