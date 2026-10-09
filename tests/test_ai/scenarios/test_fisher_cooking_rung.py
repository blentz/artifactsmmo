"""A COOKING rung on a FISHER — coverage-matrix cell 12.

The O1 census reports five skills that no scenario ever routes: alchemy,
cooking, fishing, mining and woodcutting. Cooking is the one the design named —
33,840 live cooking XP that no node models — and `l24_fisher_cooking_rung` is
the first scenario whose skill grind stands on a cooking rung at all.

**A design correction that became a regression fix.** When this cell was
written, §5.3's claim that it closes "the O1 census's 5 never-routed skills"
was false, and the reason was structural: `ReachSkillLevel` had exactly one
producer — `decisions.root.IsThisTargetBlocked`, off `GearTarget.blocking_skill`
— and that field is the crafting skill of an EQUIPPABLE gear target. Every one
of the catalogue's twenty cooking recipes produces a `consumable`, which
`ITEM_TYPE_TO_SLOTS` maps to no slot, so a cooking item can never be a gear
target and `blocking_skill` can never be "cooking".

That half is still true and `test_cooking_cannot_be_routed_by_any_GEAR_TARGET`
still states it over the CATALOGUE. What changed is the conclusion drawn from
it: a skill no gear target can name needed a producer of its own, which is what
`ef67c1d6` deleted ("skills are pure prerequisites now") and what
`decisions.root._orphan_skill_roots` restores.

Since USER 2026-10-08 ("Only when demanded") that producer offers a climb only
for a skill the goal-action DAG demands: cooking rises when the fleet floor's
tier food (`ctx.supply_shortfall`) needs a cooking level the character lacks,
not before.

What the cell DOES close is the D11 value: a cooking rung, walked. `fisher` is
a declared role (`role_catalog`: gather `fishing`, craft `cooking`), and the
flip that makes the cell bite is the role itself — the same cooking rung
descends to the same fishing gather either way, but only a real fisher can
perform it, and the planner says so by planning the fishing grind that opens
the trout spot when the role is taken away.
"""

import dataclasses
import math

import pytest

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.craft_plan_gen import decompose
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.restore_hp import RestoreHPGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.role_catalog import ROLES_BY_NAME, role_skills
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.skill_grindable import skill_is_grindable
from artifactsmmo_cli.ai.strategy_driver import objective_step_goal
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachSkillLevel
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from artifactsmmo_cli.ai.tiers.strategy import actionable_step
from artifactsmmo_cli.ai.world_state import WorldState
from artifactsmmo_cli.audit.grind_cycle_census import earned_skill
from artifactsmmo_cli.audit.open_rung_completeness import census_state, routed_skills

CELL = "l24_fisher_cooking_rung"
ROLE = "fisher"
SKILL = "cooking"
GATHER_SKILL = "fishing"
RUNG = "cooked_trout"
RAW = "trout"
RAW_GATHER_LEVEL = 20
"""The fishing level the trout spot demands — the gate the role exists to
clear, and the number the flip below turns into a fishing sub-grind."""

PLAN_BUDGET_SECONDS = 2.0
"""Measured 0.003 s for both halves of the flip."""

RESTORE_PLAN_NODES = 60_000
"""The wounded cook's RestoreHP search, bounded by WORK, not wall clock. It
creates 22,233 nodes (1.05 s idle) since `UseConsumableAction.apply` heals
`hp_restore` instead of to full (2026-10-01): cook-then-eat needs several rounds
and a closing Rest. A 2 s and then a 5 s budget both ran out under xdist plus
coverage; node counts are deterministic, so this bound (~2.7x the measured
search) can fail only on a real blow-up."""


def _state(game_data: GameData) -> WorldState:
    return scenario_state(SCENARIOS[CELL], game_data)


def _gather_plan(state: WorldState, game_data: GameData,
                 code: str, quantity: int) -> list[object]:
    """Plan `GatherMaterials(code)` against the LIVE action factory, the same
    harness `test_fight_loadout_swap.py` uses — scoped to this one goal so the
    assertion is about the fishing gate and not about which root the arbiter
    happens to prefer for a fisher."""
    player = GamePlayer(character=CELL, history=None)
    player.seed_offline(state, game_data)
    actions = list(player._build_actions())
    goal = GatherMaterialsGoal(target_item=code, needed={code: quantity})
    return decompose(goal, state, game_data, actions, NO_PROFILE_CONTEXT) or []


@pytest.fixture
def state(bundle_game_data: GameData) -> WorldState:
    return _state(bundle_game_data)


# --- the character really is a fisher ---------------------------------------

def test_the_scenario_is_the_declared_fisher_role(state: WorldState) -> None:
    """The role is a DECLARATION in `role_catalog`, not a shape this test
    invents: its two skills are the two this character carries high, and every
    other skill is at the floor."""
    owned = role_skills(ROLES_BY_NAME[ROLE])
    assert owned == {GATHER_SKILL, SKILL}
    assert state.skills[GATHER_SKILL] >= RAW_GATHER_LEVEL
    assert state.skills[SKILL] > 20
    assert {name for name, level in state.skills.items() if level > 5} == owned


# --- the cooking rung, and the descent into a fishing gather ----------------

def test_the_grind_stands_on_a_cooking_rung(
        bundle_game_data: GameData, state: WorldState) -> None:
    """`skill_grind_target` — production's own rung picker — names a cooking
    recipe this character can craft, and `skill_is_grindable(cooking, C+1)`
    holds through it. Cooking has no gather arm (`GatheringSkill` does not
    contain it), so the craftable rung is the ONLY thing that can open the
    skill: this is the cooking-rung dimension, undiluted."""
    rung = skill_grind_target(SKILL, state, bundle_game_data)
    assert rung == RUNG
    stats = bundle_game_data.item_stats(RUNG)
    assert stats is not None
    assert stats.crafting_skill == SKILL
    assert stats.crafting_level <= state.skills[SKILL]
    assert bundle_game_data.crafting_recipes[RUNG] == {RAW: 1}
    assert skill_is_grindable(SKILL, state.skills[SKILL] + 1, state, bundle_game_data)


def test_the_descent_lands_on_the_fishing_gather(
        bundle_game_data: GameData, state: WorldState) -> None:
    """The grind descent, from the cooking rung down to the raw fish — the
    first fishing-fed step any scenario produces. The bag and bank are empty on
    purpose: a banked trout would make the step a WITHDRAW and the fishing gate
    would never be consulted."""
    assert state.inventory == {}
    assert state.bank_items == {}
    step = actionable_step(ObtainItem(code=RUNG, quantity=1), state,
                           bundle_game_data, NO_PROFILE_CONTEXT)
    assert step == ObtainItem(code=RAW, quantity=1)
    resource, _rate = bundle_game_data.resource_for_drop(RAW)
    assert bundle_game_data.resource_skill_level(resource) == (
        GATHER_SKILL, RAW_GATHER_LEVEL)


def test_the_role_is_what_makes_the_gather_plannable(
        bundle_game_data: GameData, state: WorldState) -> None:
    """Proof it bites, and it reaches an ACTION.

    The fisher gathers the trout in one step. Take the role away — fishing back
    to the floor, everything else identical, the SAME cooking rung — and the
    trout's skill gate is shut, so the plan is the fishing grind that opens it
    (a sub-task, Phase 2d: its cycle ends in a lower fishing gather), which is
    the fishing dimension answering."""
    fisher_plan = _gather_plan(state, bundle_game_data, RAW, 1)
    assert [repr(a) for a in fisher_plan] == ["Gather(trout_spot×1)"]

    landlubber = dataclasses.replace(
        SCENARIOS[CELL],
        skills={**SCENARIOS[CELL].skills, GATHER_SKILL: 5})
    other = scenario_state(landlubber, bundle_game_data)
    assert skill_grind_target(SKILL, other, bundle_game_data) == RUNG
    other_plan = _gather_plan(other, bundle_game_data, RAW, 1)
    assert other_plan and isinstance(other_plan[-1], GatherAction)
    gate = bundle_game_data.resource_skill_level(other_plan[-1].resource_code)
    assert gate is not None and gate[0] == GATHER_SKILL and gate[1] < RAW_GATHER_LEVEL, other_plan


# --- the design correction --------------------------------------------------

def test_cooking_cannot_be_routed_by_any_GEAR_TARGET(
        bundle_game_data: GameData, state: WorldState) -> None:
    """`blocking_skill` is a gear target's own crafting skill, and NO cooking
    recipe produces an item any equipment slot accepts. That half of the
    original finding is unchanged and is exactly WHY the standalone root had to
    come back: `ef67c1d6` deleted the four standalone `ReachSkillLevel`
    emitters on the premise "skills are pure prerequisites now", which is false
    for a skill nothing equips.

    Stated over the catalogue rather than over this one character, so it is a
    claim about the game and not about a fixture."""
    cooking_items = [code for code, stats
                     in bundle_game_data.all_item_stats.items()
                     if stats.crafting_skill == SKILL]
    assert len(cooking_items) >= 20
    for code in cooking_items:
        stats = bundle_game_data.all_item_stats[code]
        assert not ITEM_TYPE_TO_SLOTS.get(stats.type_), code


def test_no_scenario_routes_cooking_or_fishing_undemanded(bundle_game_data: GameData) -> None:
    """USER 2026-10-08, "Only when demanded". Cooking used to be routed in every
    scenario as the unconditional floor, and its grind target pulled fishing in
    (`cooking -> cooked_shrimp -> shrimp -> fishing@N`): live, four characters
    spent ~100 cycles each on `Gather(trout_spot)` with nothing asking for a
    fish. `resolve_root`'s natural walk (no tier food short) now routes neither,
    nor any other gathering skill. The demanded half is pinned in
    `test_orphan_gate_scenarios.TestTierFoodDemandsFishing` and
    `test_decisions_root.test_cooking_climbs_when_a_better_tier_food_is_due`."""
    routed: set[str] = set()
    for scenario in SCENARIOS.values():
        routed |= routed_skills(census_state(scenario, bundle_game_data), bundle_game_data)
    assert routed.isdisjoint({SKILL, GATHER_SKILL, "mining", "woodcutting", "alchemy"})


def test_the_fishers_cooking_root_plans_a_cooking_grind(
        bundle_game_data: GameData, state: WorldState) -> None:
    """The root reaches an ACTION, which is what "routable" has to mean.

    `ReachSkillLevel(cooking, C+1)` -> `ReachSkillGoal` (the
    `strategy_driver.objective_step_goal` skill arm) -> the grind's committed
    plan from the arbiter's producer (`decompose`, Phase 2d), ending in a leg
    that earns: the cooking craft, or the fishing gather of a sub-grind its
    rung's input needs."""
    root = ReachSkillLevel(skill=SKILL, level=state.skills[SKILL] + 1)
    goal = objective_step_goal(root, state, bundle_game_data,
                               NO_PROFILE_CONTEXT, root=root, history=None)
    assert repr(goal) == f"ReachSkill({SKILL}->{state.skills[SKILL] + 1})"
    player = GamePlayer(character=CELL, history=None)
    player.seed_offline(state, bundle_game_data)
    plan = decompose(goal, state, bundle_game_data, list(player._build_actions()),
                     NO_PROFILE_CONTEXT)
    assert plan and earned_skill(plan[-1], bundle_game_data) in (SKILL, GATHER_SKILL), plan


# ---------------------------------------------------------------------------
# THE COOK-THEN-EAT ROUTE, pinned END TO END (wave 6, increment 5.2)
#
# `RestoreHPGoal.relevant_actions` admits the `"craft"` tag, and
# `test_goals.py::TestRestoreHPGoal::test_relevant_actions_restricts_to_recovery_craft_movement`
# already pins THAT — over a hand-built list of six actions.
#
# It does not pin the thing that matters. A filter can admit `craft` while the
# planner never emits one, which is exactly the failure mode the user reported
# ("make cooking routable — that used to work and it got broken by another
# epicycle"): the tag survives, the route does not. 99.6 % of the fleet's
# cooking XP rides on the planner actually choosing to cook.
#
# THE DESIGN'S PREMISE FOR THIS TEST WAS WRONG, and the correction is worth
# keeping. Wave 6 §5.2 says "today nothing pins that tag; deleting it would
# silently remove 99.6 % of the fleet's cooking XP and nothing would fail."
# Measured by removing `"craft"` from the tag set and running the suite:
# exactly one test failed — the hand-built-list one above. So the TAG is
# pinned; the ROUTE is what was not, and that is what these two tests add.
# ---------------------------------------------------------------------------

COOK_CELL = "l20_relief_full_bank"
"""One of three cells (with `l20_bag_critical_empty_bank` and `l8_overstocked`)
whose deeply-wounded RestoreHP plan is a Craft followed by a UseConsumable.
Chosen by sweeping every cell rather than by guessing which would cook."""


def _wounded(game_data: GameData) -> WorldState:
    """`COOK_CELL` at 10 % HP.

    The wound depth is load-bearing: `RestAction`'s cost is dynamic
    (`max(3, ceil(missing%))/10`, 0.3..10.0), so at a light wound Rest is nearly
    free and no craft can beat it. Cook-then-eat only wins when the character is
    badly hurt, which is the regime this test has to be in to mean anything."""
    base = scenario_state(SCENARIOS[COOK_CELL], game_data)
    return dataclasses.replace(base, hp=max(1, base.max_hp // 10))


def _restore_plan(state: WorldState, game_data: GameData) -> list:
    player = GamePlayer(character=COOK_CELL, history=None)
    player.seed_offline(state, game_data)
    planner = GOAPPlanner()
    plan = planner.plan(state, RestoreHPGoal(), list(player._build_actions()),
                        game_data, history=None,
                        budget_seconds=math.inf, max_nodes=RESTORE_PLAN_NODES)
    assert not planner.last_stats.node_capped, planner.last_stats
    return plan


def test_restore_hp_may_cook(bundle_game_data: GameData) -> None:
    """The PLANNER emits cook-then-eat, not just the filter admitting it.

    Asserted on the plan's SHAPE — a Craft whose product is then consumed —
    because that is the route. A plan containing a Craft for some unrelated
    reason would not restore any HP."""
    plan = _restore_plan(_wounded(bundle_game_data), bundle_game_data)
    kinds = [type(a).__name__ for a in plan]
    assert "CraftAction" in kinds, kinds
    assert kinds.index("CraftAction") < kinds.index("UseConsumableAction"), kinds
    # `UseConsumableAction` names NO item — it eats "the best available
    # consumable from inventory" at execution time, so the craft-to-eat link is
    # implicit. What makes the route work is therefore that the thing cooked is
    # FOOD; asserting an item match here is not possible and would be asserting
    # a model the action does not have.
    crafted = next(a for a in plan if type(a).__name__ == "CraftAction")
    stats = bundle_game_data.item_stats(crafted.code)
    assert stats is not None and stats.type_ == "consumable", \
        f"cook-then-eat requires the craft to be food, got {crafted.code}"


def test_the_cook_route_is_not_what_a_light_wound_takes(
        bundle_game_data: GameData) -> None:
    """NOT VACUOUS. The same cell, barely hurt, does NOT cook — Rest is cheap
    there.

    Without this the test above would pass against a planner that cooked
    unconditionally, which would be its own bug: cooking to heal 5 HP burns a
    craft and a cycle for nothing."""
    base = scenario_state(SCENARIOS[COOK_CELL], bundle_game_data)
    light = dataclasses.replace(base, hp=base.max_hp - 1)
    kinds = [type(a).__name__ for a in _restore_plan(light, bundle_game_data)]
    assert "CraftAction" not in kinds, kinds
