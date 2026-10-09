"""ALCHEMY — the eighth skill, and the one the orphan rule once wrongly declined.

No gear target can name alchemy: `objective._gear_candidates_by_type` — the
ONLY builder of the gear sheet `classify_target` reads `blocking_skill` off —
skips `stats.type_ == "utility"` outright, and alchemy's 25 recipes are 20
`utility` potions and 5 `consumable`s. A gear target named alchemy in 0 of the
committed scenarios.

So alchemy reaches a standalone climb only through `_orphan_skill_roots`, and
since USER 2026-10-08 ("Only when demanded") only when the goal-action DAG
demands it: a root on offer whose closure bottoms out in an alchemy-gated leaf.
This module names the branch, shows it reached on a committed scenario with
real demand, and shows the climb plans a grind.
"""

import pytest

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.craft_plan_gen import decompose
from artifactsmmo_cli.ai.decisions.root import _orphan_skill_roots
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.skill_grindable import skill_is_grindable
from artifactsmmo_cli.ai.strategy_driver import objective_step_goal
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachSkillLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from artifactsmmo_cli.ai.world_state import EQUIPMENT_SLOTS, WorldState
from artifactsmmo_cli.audit.grind_cycle_census import earned_skill
from artifactsmmo_cli.audit.open_rung_completeness import census_state, routed_skills

SKILL = "alchemy"
CELL = "l15_midband"
"""The committed scenario this module witnesses on: level 15, alchemy 6 — the
skill furthest behind the character, so it heads the orphan list."""

RUNG = "small_health_potion"
GEAR_NAMEABLE = frozenset({"gearcrafting", "weaponcrafting", "jewelrycrafting"})
PLAN_BUDGET_SECONDS = 5.0
"""Measured 0.3 s for the one grind plan below."""

_OFFERED = [ObtainItem(code=code, quantity=1) for code in
           ("nettle_leaf", "small_pearls", "birch_wood", "steel_bar")]
"""The DEMAND, one item per gathering skill, each gated
(`RequirementGraph.gather_skill`) ABOVE `l15_midband`'s own level for that
skill (alchemy 6, fishing 10, woodcutting 12, mining 12): `nettle_leaf`
(alchemy@20), `small_pearls` (fishing@20), `birch_wood` (woodcutting@20), and
`steel_bar` (mining@20, via its `coal` ingredient). Without it nothing asks
for alchemy and `_orphan_skill_roots` offers it nothing."""


@pytest.fixture
def state(bundle_game_data: GameData) -> WorldState:
    return scenario_state(SCENARIOS[CELL], bundle_game_data)


# --- the finding: no gear target can name alchemy ---------------------------

def test_alchemys_whole_catalogue_is_utility_or_consumable(
        bundle_game_data: GameData) -> None:
    """The catalogue fact the rest of this module stands on, stated over the
    GAME rather than over a fixture: every alchemy recipe is a `utility` potion
    (which the gear sheet skips) or a `consumable` (which maps to no slot).

    The `utility` half is why the old reading looked right — those types DO map
    to `utility1_slot`/`utility2_slot`, both real `EQUIPMENT_SLOTS` — so the
    assertion below records that the naive reading is not merely careless, it
    is defensible right up until you read `_gear_candidates_by_type`."""
    recipes = {code: stats for code, stats
               in bundle_game_data.all_item_stats.items()
               if stats.crafting_skill == SKILL}
    assert len(recipes) == 25
    types = {stats.type_ for stats in recipes.values()}
    assert types == {"utility", "consumable"}
    utility = [c for c, s in recipes.items() if s.type_ == "utility"]
    assert len(utility) == 20
    # The trap: `utility` really does map to two real equipment slots.
    assert [s for s in ITEM_TYPE_TO_SLOTS["utility"] if s in EQUIPMENT_SLOTS] == [
        "utility1_slot", "utility2_slot"]
    # And `consumable` really does map to none.
    assert not ITEM_TYPE_TO_SLOTS.get("consumable")


def test_no_scenario_produces_a_gear_target_that_names_alchemy(
        bundle_game_data: GameData) -> None:
    """The measurement, over the whole corpus: 0 of 42. This is what makes the
    old docstring's "alchemy is therefore NOT an orphan" false rather than
    merely unproven — the claim had a witness set and it was empty.

    Every OTHER skill in `GEAR_NAMEABLE` is asserted to appear somewhere in the
    same sweep, so an empty answer for alchemy cannot be a broken sweep."""
    objective = CharacterObjective.from_game_data(bundle_game_data)
    named: set[str] = set()
    for scenario in SCENARIOS.values():
        state = census_state(scenario, bundle_game_data)
        for target in objective.gear_targets_with_blockers(state, None).values():
            if target.blocking_skill:
                named.add(target.blocking_skill)
    assert SKILL not in named
    assert named and named <= GEAR_NAMEABLE


# --- the branch that now carries alchemy, reached ---------------------------

def test_alchemy_heads_the_orphan_list_for_this_cell(
        bundle_game_data: GameData, state: WorldState) -> None:
    """THE BRANCH: `_orphan_skill_roots` emits `ReachSkillLevel(alchemy, 20)`
    — the level `_OFFERED`'s closure asks for, not `C+1` — and emits it FIRST:
    the group's one ordering integer is `skill level - character level`, and
    alchemy at 6 trails this level-15 character furthest. Only the demanded
    skills appear (USER 2026-10-08, "Only when demanded")."""
    orphans = _orphan_skill_roots(state, bundle_game_data, _OFFERED, NO_PROFILE_CONTEXT)
    assert orphans[0] == ReachSkillLevel(skill=SKILL, level=20)
    assert [goal.skill for goal in orphans] == [SKILL, "fishing", "mining", "woodcutting"]
    assert all(goal.skill != SKILL for goal in _orphan_skill_roots(
        state, bundle_game_data, [], NO_PROFILE_CONTEXT))


def test_the_alchemy_rung_is_open_and_is_a_potion(
        bundle_game_data: GameData, state: WorldState) -> None:
    """The rung the root stands on: production's own picker names an alchemy
    recipe at or below the current level, and `skill_is_grindable(alchemy, C+1)` —
    the orphan rule's second conjunct and the O1 census's verdict predicate —
    holds through it."""
    assert skill_grind_target(SKILL, state, bundle_game_data) == RUNG
    stats = bundle_game_data.item_stats(RUNG)
    assert stats is not None
    assert (stats.crafting_skill, stats.type_) == (SKILL, "utility")
    assert stats.crafting_level <= state.skills[SKILL]
    assert skill_is_grindable(SKILL, state.skills[SKILL] + 1, state, bundle_game_data)


def test_the_alchemy_root_plans_a_grind_cycle(
        bundle_game_data: GameData, state: WorldState) -> None:
    """The root reaches an ACTION, which is what "routable" has to mean:
    `ReachSkillLevel(alchemy, C+1)` -> `objective_step_goal`'s skill arm ->
    the grind's committed plan from the arbiter's producer (`decompose`, Phase
    2d), ending in the leg that earns alchemy."""
    root = ReachSkillLevel(skill=SKILL, level=state.skills[SKILL] + 1)
    goal = objective_step_goal(root, state, bundle_game_data,
                               NO_PROFILE_CONTEXT, root=root, history=None)
    assert repr(goal) == f"ReachSkill({SKILL}->{state.skills[SKILL] + 1})"
    player = GamePlayer(character=CELL, history=None)
    player.seed_offline(state, bundle_game_data)
    plan = decompose(goal, state, bundle_game_data, list(player._build_actions()),
                     NO_PROFILE_CONTEXT)
    assert plan and earned_skill(plan[-1], bundle_game_data) == SKILL, plan


def test_no_scenario_routes_alchemy_without_demand(bundle_game_data: GameData) -> None:
    """`resolve_root`'s natural walk (no demand injected) routes only the three
    gear-crafting skills the tier walk names: no committed scenario's roots
    demand alchemy, so no scenario offers it a climb (USER 2026-10-08)."""
    routed: set[str] = set()
    for scenario in SCENARIOS.values():
        cell = routed_skills(census_state(scenario, bundle_game_data),
                             bundle_game_data)
        assert SKILL not in cell, scenario.name
        routed |= cell
    assert routed == GEAR_NAMEABLE
