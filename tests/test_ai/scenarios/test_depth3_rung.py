"""The DEPTH-3 rung — coverage-matrix cell 6.

Nine catalogue recipes close at depth 3 (`greater_dreadful_amulet`,
`greater_dreadful_staff`, the four `greater_*_amulet`s and the three
`royal_skeleton_*` pieces) and **no scenario put one on a gear sheet**, so the
deepest closure the harness ever walked was depth 2. That is not a missing
field: the root is DERIVED from the character, so reaching a depth-3 rung means
constructing a character whose gear-target tier is high enough for one to be the
best candidate in a slot it is behind on (design 2026-08-24 §4.3).

`l47_depth3_amulet` is that character. It clears through ladder rung 25 in the
best catalogue loadout at or below its own level, so `gear_target_tier` is 30,
and at rung 30 the amulet slot's best candidate is `greater_dreadful_amulet`.
The slot is empty; every other slot is worn at or above its rung-30 candidate,
so the amulet is the one slot behind and the walk resolves to it. (Since the
global gear objective, Task 5, the walk reads the cycle's `L*` instead of the
rung: its first missing piece is still `greater_dreadful_amulet`. The two
tests that pinned the rung and the tier walk's trail were deleted, ruling Y;
`test_the_objectives_first_missing_piece_is_the_depth_three_amulet` pins
the new claim.)

The bag holds every root input EXCEPT the depth-2 intermediate. Without that
the descent stops at `cyclops_eye` — a monster drop one level down — and the
depth-3 leg is never walked, which is exactly how a cell can look right and
test nothing.
"""

import dataclasses
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.decisions.root import resolve_root
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import (
    SCENARIOS,
    scenario_state,
)
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.prerequisite_graph import prerequisites
from artifactsmmo_cli.ai.tiers.strategy import actionable_step
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT
from tests.test_ai.shared_world import attached, shared_world

CELL = "l47_depth3_amulet"

ROOT = "greater_dreadful_amulet"
TIER2 = "dreadful_amulet"
TIER3 = "hardwood_plank"
LEAF = "ash_wood"
"""The four rungs of the closure this cell exists to walk: the root, the
intermediate that makes it depth-3, that intermediate's own craftable input,
and the raw material at the bottom."""

DEPTH_3_RECIPES = frozenset({
    "greater_dreadful_amulet", "greater_dreadful_staff",
    "greater_emerald_amulet", "greater_ruby_amulet",
    "greater_sapphire_amulet", "greater_topaz_amulet",
    "royal_skeleton_armor", "royal_skeleton_helmet", "royal_skeleton_pants",
})
"""Every catalogue recipe whose closure is 3 deep, enumerated so
`test_this_is_the_only_scenario_standing_on_a_depth_three_rung` can say what it
is ranging over instead of recomputing a depth function beside production."""

PLAN_NODE_BUDGET = 1_000
"""A depth-3 chain is exactly the shape the design warned could land in the
planner's tail, so the cost is asserted rather than hoped for — as WORK, not wall
clock (a 2 s clock bound flaked under a loaded suite, 2026-10-02). Measured 0
nodes: the walk serves it."""


def _state(name: str, game_data: GameData) -> WorldState:
    return scenario_state(SCENARIOS[name], game_data)


def _root_node() -> ObtainItem:
    return ObtainItem(code=ROOT, quantity=1, slot="amulet_slot")


BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"


@pytest.fixture(scope="module")
def bundle_game_data() -> GameData:
    """Module-scoped: this file resolves the root walk once per scenario in
    `test_this_is_the_only_scenario_standing_on_a_depth_three_rung`, and
    rebuilding the catalogue for each test would cost more than the sweep."""
    return shared_world(BUNDLE)


@pytest.fixture(scope="module")
def state(bundle_game_data: GameData) -> WorldState:
    return _state(CELL, bundle_game_data)


# --- the closure really is three deep ---------------------------------------

def test_the_rung_is_a_depth_three_recipe(bundle_game_data: GameData) -> None:
    """The premise, read straight off the catalogue rather than asserted.

    Root -> `dreadful_amulet` -> `hardwood_plank` -> `ash_wood`, and the last
    of those has no recipe at all. Three nested crafts is what "depth 3" means,
    and stating it as a chain rather than as a number means a catalogue change
    that flattens the chain fails HERE, beside the cell that depends on it."""
    recipes = bundle_game_data.crafting_recipes
    assert ROOT in DEPTH_3_RECIPES
    assert TIER2 in recipes[ROOT]
    assert TIER3 in recipes[TIER2]
    assert LEAF in recipes[TIER3]
    assert bundle_game_data.crafting_recipe(LEAF) is None


# --- the descent walks the depth-3 leg, and flipping it changes the answer ---

def test_the_descent_reaches_two_levels_below_the_root(
        bundle_game_data: GameData, state: WorldState) -> None:
    """The branch the cell targets: `actionable_step` recursing THROUGH the
    depth-2 intermediate into its own recipe.

    Every other input is in the bag, so `dreadful_amulet` is the only open
    prerequisite — and the step is not `dreadful_amulet` but `ash_wood`, two
    crafts further down. No other scenario produces a step that far from its
    root."""
    node = _root_node()
    prereqs = prerequisites(node, state, bundle_game_data, TIMED_NO_PROFILE_CONTEXT)
    assert ObtainItem(code=TIER2, quantity=1) in prereqs
    step = actionable_step(node, state, bundle_game_data, TIMED_NO_PROFILE_CONTEXT)
    assert step == ObtainItem(code=LEAF, quantity=4)


def test_owning_the_intermediate_collapses_the_depth_and_the_answer(
        bundle_game_data: GameData, state: WorldState) -> None:
    """The flip. Put ONE `dreadful_amulet` in the bag — nothing else changes —
    and the closure the walk must cross drops from three rungs to zero: the
    step becomes the intermediate itself and the plan becomes an Equip.

    This is what makes the cell non-vacuous: the answer above is produced BY
    the depth-3 leg, not by anything else about this character."""
    held = dataclasses.replace(
        state, inventory={**state.inventory, TIER2: 1})
    step = actionable_step(_root_node(), held, bundle_game_data, TIMED_NO_PROFILE_CONTEXT)
    assert step == ObtainItem(code=TIER2, quantity=1)

    player = GamePlayer(character=CELL, history=None)

    player._offline_timing = committed_timing()

    player._learned_drops = LearnedDrops.empty()

    player._offline_timing = committed_timing()

    player._learned_drops = LearnedDrops.empty()
    player.seed_offline(held, bundle_game_data)
    report = player.plan_from_state()
    assert "EquipOwnedGear" in repr(report.selected_goal)


def test_the_cell_plans_the_bottom_of_the_chain_inside_the_budget(
        bundle_game_data: GameData, state: WorldState) -> None:
    """End to end: the selected goal is the raw material at the bottom of a
    three-deep closure, and the plan is the gather that starts it."""
    player = GamePlayer(character=CELL, history=None)
    player._offline_timing = committed_timing()
    player._learned_drops = LearnedDrops.empty()
    player.seed_offline(state, bundle_game_data)
    report = player.plan_from_state()
    assert repr(report.selected_goal) == f"GatherMaterials({LEAF}, {{{LEAF}:4}})"
    assert report.plan and "Gather(ash_tree" in repr(report.plan[0])
    assert not any(t["timed_out"] for t in report.goals_tried), report.goals_tried
    nodes = sum(int(t["nodes"]) for t in report.goals_tried)
    assert nodes <= PLAN_NODE_BUDGET, f"{CELL} searched {nodes} nodes"


def test_the_objectives_first_missing_piece_is_the_depth_three_amulet(
        bundle_game_data: GameData, state: WorldState) -> None:
    """The docstring's claim since the global gear objective, asserted: the
    cell's `L*` names the depth-3 amulet as its first missing piece, and the
    walk resolves it as the root."""
    ctx = attached(state, bundle_game_data, TIMED_NO_PROFILE_CONTEXT, None)
    assert ctx.gear_objective is not None
    assert ctx.gear_objective.missing[0].code == ROOT
    resolution = resolve_root(state, bundle_game_data,
                              CharacterObjective.from_game_data(bundle_game_data), ctx, None)
    assert resolution.root == _root_node()
