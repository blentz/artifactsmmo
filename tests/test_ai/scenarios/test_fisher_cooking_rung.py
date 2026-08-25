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
`decisions.root._orphan_skill_roots` restores. Cooking, fishing, mining and
woodcutting are routable now; alchemy is not, and correctly so — its potions
are `utility` equippables, so it really is a prerequisite skill.

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
    the skills no gear target can name, so all four are routed now and alchemy
    still is not — alchemy's potions ARE utility equippables, so it is a
    prerequisite skill and the rule correctly declines it. The O1 census's
    routed count moves 26 -> 194 of 336 cells with this change; residuals stay
    at 0 because the rule's second conjunct is `LevelSkill(S, C+1).
    is_applicable`, the same predicate the census verdicts a cell on."""
    routed: set[str] = set()
    for scenario in SCENARIOS.values():
        routed |= routed_skills(census_state(scenario, bundle_game_data),
                                bundle_game_data)
    assert routed == {"jewelrycrafting", "gearcrafting", "weaponcrafting",
                      "cooking", "fishing", "mining", "woodcutting"}
    assert "alchemy" not in routed


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
