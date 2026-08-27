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

Cooking, fishing, mining and woodcutting became routable here. ALCHEMY did not,
and this module's original text said that was correct — "its potions are
`utility` equippables, so it really is a prerequisite skill". That was WRONG,
and `tests/test_ai/scenarios/test_alchemy_rung.py` is the correction: the gear
sheet (`objective._gear_candidates_by_type`) skips `utility` outright, so a
gear target named alchemy in 0 of the 42 scenarios and could never name it. All
eight skills are routed now.

What the cell DOES close is the D11 value: a cooking rung, walked. `fisher` is
a declared role (`role_catalog`: gather `fishing`, craft `cooking`), and the
flip that makes the cell bite is the role itself — the same cooking rung
descends to the same fishing gather either way, but only a real fisher can
perform it, and the planner says so by inserting `LevelSkill(fishing->20)`
ahead of the gather when the role is taken away.
"""

import dataclasses

import pytest

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.decisions.root import _gear_nameable_skills
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.restore_hp import RestoreHPGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.role_catalog import ROLES_BY_NAME, role_skills
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.strategy_driver import objective_step_goal
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachSkillLevel
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from artifactsmmo_cli.ai.tiers.strategy import actionable_step
from artifactsmmo_cli.ai.world_state import WorldState
from artifactsmmo_cli.audit.open_rung_completeness import census_state, routed_skills

CELL = "l24_fisher_cooking_rung"
ROLE = "fisher"
SKILL = "cooking"
GATHER_SKILL = "fishing"
RUNG = "cooked_trout"
RAW = "trout"
RAW_GATHER_LEVEL = 20
"""The fishing level the trout spot demands — the gate the role exists to
clear, and the number the flip below turns into a `LevelSkill` edge."""

PLAN_BUDGET_SECONDS = 2.0
"""Measured 0.003 s for both halves of the flip."""


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
    return GOAPPlanner().plan(state, goal, actions, game_data, history=None,
                              budget_seconds=PLAN_BUDGET_SECONDS)


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
    recipe this character can craft, and `LevelSkill(cooking, C+1)` is
    applicable through it. Cooking has no gather arm (`GatheringSkill` does not
    contain it), so the craftable rung is the ONLY thing that can open the
    skill: this is the cooking-rung dimension, undiluted."""
    rung = skill_grind_target(SKILL, state, bundle_game_data)
    assert rung == RUNG
    stats = bundle_game_data.item_stats(RUNG)
    assert stats is not None
    assert stats.crafting_skill == SKILL
    assert stats.crafting_level <= state.skills[SKILL]
    assert bundle_game_data.crafting_recipes[RUNG] == {RAW: 1}
    assert LevelSkill(skill=SKILL, target_level=state.skills[SKILL] + 1
                      ).is_applicable(state, bundle_game_data)


def test_the_descent_lands_on_the_fishing_gather(
        bundle_game_data: GameData, state: WorldState) -> None:
    """The grind descent, from the cooking rung down to the raw fish — the
    first fishing-fed step any scenario produces. The bag and bank are empty on
    purpose: a banked trout would make the step a WITHDRAW and the fishing gate
    would never be consulted."""
    assert state.inventory == {}
    assert state.bank_items == {}
    step = actionable_step(ObtainItem(code=RUNG, quantity=1), state,
                           bundle_game_data, NO_PROFILE_CONTEXT,
                           grind_descent=True)
    assert step == ObtainItem(code=RAW, quantity=1)
    resource, _rate = bundle_game_data.resource_for_drop(RAW)
    assert bundle_game_data.resource_skill_level(resource) == (
        GATHER_SKILL, RAW_GATHER_LEVEL)


def test_the_role_is_what_makes_the_gather_plannable(
        bundle_game_data: GameData, state: WorldState) -> None:
    """Proof it bites, and it reaches an ACTION.

    The fisher gathers the trout in one step. Take the role away — fishing back
    to the floor, everything else identical, the SAME cooking rung and the SAME
    descent — and `GatherAction.is_applicable`'s skill gate refuses, so the
    planner has to buy the level first. The plan gains an edge the fisher's
    does not need, which is the fishing dimension answering."""
    fisher_plan = _gather_plan(state, bundle_game_data, RAW, 1)
    assert [repr(a) for a in fisher_plan] == ["Gather(trout_spot×1)"]

    landlubber = dataclasses.replace(
        SCENARIOS[CELL],
        skills={**SCENARIOS[CELL].skills, GATHER_SKILL: 5})
    other = scenario_state(landlubber, bundle_game_data)
    assert skill_grind_target(SKILL, other, bundle_game_data) == RUNG
    other_plan = _gather_plan(other, bundle_game_data, RAW, 1)
    assert [repr(a) for a in other_plan] == [
        f"LevelSkill({GATHER_SKILL}->{RAW_GATHER_LEVEL})", "Gather(trout_spot×1)"]


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
    claim about the game and not about a fixture — and it fails the day a
    cooking-crafted equippable exists, which is exactly when cooking would stop
    being an orphan and `_orphan_skill_roots` would stop admitting it."""
    cooking_items = [code for code, stats
                     in bundle_game_data.all_item_stats.items()
                     if stats.crafting_skill == SKILL]
    assert len(cooking_items) >= 20
    for code in cooking_items:
        stats = bundle_game_data.all_item_stats[code]
        assert not ITEM_TYPE_TO_SLOTS.get(stats.type_), code
    assert SKILL not in _gear_nameable_skills(bundle_game_data)


def test_every_scenario_now_routes_cooking(bundle_game_data: GameData) -> None:
    """THE REGRESSION FIX, AS A NUMBER. This test used to read
    `assert routed == {"jewelrycrafting", "gearcrafting", "weaponcrafting"}` —
    the honest record that no scenario could route cooking, fishing, mining or
    woodcutting, because the ONE producer of a `ReachSkillLevel` was a gear
    target's crafting skill.

    `decisions/root._orphan_skill_roots` restores the standalone producer for
    the skills no gear target can name, so all four are routed now. The O1
    census's routed count moved 26 -> 194 of 336 cells with that change;
    residuals stayed at 0 because the rule's second conjunct is
    `LevelSkill(S, C+1).is_applicable`, the same predicate the census verdicts a
    cell on.

    This test also used to end `assert "alchemy" not in routed`, on the claim
    that alchemy's utility potions make it gear-nameable. They do not — see
    `test_alchemy_rung.py` — and fixing `_gear_nameable_skills` moved the count
    again, 194 -> 236 and 7 skills -> 8. So the whole-set equality moved out of
    this cell: cooking and the three skills that arrived WITH it are asserted by
    name here, and the exact routed set is pinned where it belongs — in
    `test_alchemy_rung.test_every_scenario_now_routes_alchemy` and in
    `test_open_rung_completeness.test_the_routing_breakdown_scopes_the_residual`.
    A cell that restates a global set fails for other cells' reasons."""
    routed: set[str] = set()
    for scenario in SCENARIOS.values():
        routed |= routed_skills(census_state(scenario, bundle_game_data),
                                bundle_game_data)
    assert SKILL in routed
    assert routed >= {"cooking", "fishing", "mining", "woodcutting"}


def test_the_fishers_cooking_root_plans_a_cooking_grind(
        bundle_game_data: GameData, state: WorldState) -> None:
    """The root reaches an ACTION, which is what "routable" has to mean.

    `ReachSkillLevel(cooking, C+1)` -> `ReachSkillGoal` (the
    `strategy_driver.objective_step_goal` skill arm) -> a `LevelSkill` plan on
    the live action factory. Nothing here re-enters the root walk: the descent
    from the cooking rung into its fishing-gated input happens inside the
    planner, as `test_the_role_is_what_makes_the_gather_plannable` shows."""
    root = ReachSkillLevel(skill=SKILL, level=state.skills[SKILL] + 1)
    goal = objective_step_goal(root, state, bundle_game_data,
                               NO_PROFILE_CONTEXT, root=root, history=None)
    assert repr(goal) == f"ReachSkill({SKILL}->{state.skills[SKILL] + 1})"
    player = GamePlayer(character=CELL, history=None)
    player.seed_offline(state, bundle_game_data)
    plan = GOAPPlanner().plan(state, goal, list(player._build_actions()),
                              bundle_game_data, history=None,
                              budget_seconds=PLAN_BUDGET_SECONDS)
    assert plan and repr(plan[0]).startswith(f"LevelSkill({SKILL}->")


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
    return GOAPPlanner().plan(state, RestoreHPGoal(), list(player._build_actions()),
                              game_data, history=None,
                              budget_seconds=PLAN_BUDGET_SECONDS)


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
