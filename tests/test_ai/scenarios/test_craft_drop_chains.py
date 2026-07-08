"""GAP-8: craft chains with monster-drop ingredients (2026-07-08 LIVE STALL).

Live evidence (Robby, L13): tree root `fire_bow` -> step
`ReachSkillLevel(weaponcrafting, 10)` -> proven dispatch picks `water_bow`
(the level-5 grinder) -> `GatherMaterials(water_bow)` NEVER planned:
`water_bow = 2x blue_slimeball (monster drop) + 5x ash_plank`, and
craft_plan_gen's CAN-GENERATE gate bailed on ANY closure containing a
monster-drop leaf — even one whose deficit the bank already covered — so
the raw A* fallback flooded 38,124 nodes into timeout / plan_len 0 and the
arbiter fell back to `GrindCharacterXP(red_slime)` for 65 consecutive
cycles. Weaponcrafting was permanently stalled.

The fix (mirroring GAP-6's proven dropper wiring, which
GatherMaterialsGoal.relevant_actions already carries): the generator now
admits a monster-drop leaf whenever the goal's own relevant_actions emits a
winnable-dropper Fight for it (xp-positive -> plain Fight; grey ->
drop_farm variant under grey_farm_allowed — the generator reuses whatever
the proven emission produced), maps a drop-leaf "gather" step to that
Fight, and truncates the generated plan at the Fight (one-leg-per-cycle:
kill yield is stochastic, so the steps after a Fight are re-derived by the
next cycle's replan). A drop leaf with NO emitted Fight still returns None
honestly (A* fallback; the goal's is_plannable prunes).

Class coverage (BINDING): the parametrized sweep below asserts the
generator produces a plan for EVERY craftable-with-drop-leaf recipe
reachable at the l13 scenario's stats — the class net, not one instance.
"""

import dataclasses
import json
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.craft_plan_gen import generate_next_craft_action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.plan_report import PlanReport
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachSkillLevel
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.scenarios.search_bounds import assert_search_bounded

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"

L13 = "l13_drop_recipe_grind"


def _bundle() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def _player(name: str) -> GamePlayer:
    gd = load_bundle_game_data(BUNDLE)
    player = GamePlayer(character=name, history=None)
    player.seed_offline(scenario_state(SCENARIOS[name], gd), gd)
    return player


def _run(name: str) -> PlanReport:
    return _player(name).plan_from_state()


def test_l13_registered() -> None:
    """Registry-first (TDD): the scenario must exist under the exact
    binding name before anything else in this file can run."""
    assert L13 in SCENARIOS


def test_l13_water_bow_chain_plans() -> None:
    """The stall, flipped positive. The derivation up to the goal is the
    UNCHANGED live shape (verified against the pre-fix code, which
    reproduced it exactly: GatherMaterials(water_bow) flooded 53,159 nodes
    offline / 38,124 live into timeout + plan_len 0, and the cycle fell
    back to GrindCharacterXP(red_slime)):

    - chosen_root: ObtainItem(fire_bow, weapon_slot) — the weapon upgrade;
      its own mats (spruce_plank 6 + red_slimeball 2) ride in the bag, so
      the material step is satisfied.
    - chosen_step: ReachSkillLevel(weaponcrafting, 10) — fire_bow's skill
      gate (5 < 10).
    - dispatch: water_bow, the level-5 in-skill grinder with the fewest
      missing mats once holdings are credited (blue_slimeball 2 needed vs
      bag 1 + bank 2; ash_plank 5 missing) — reserved-material flags
      exclude fire_staff (red_slimeball is fire_bow's own reserved input).

    NEW: the goal now PLANS via the generator (nodes 0 — the A* flood class
    is gone for drop recipes). Derived plan, pinned exactly: the core's
    withdraw arm serves the bank-covered blue_slimeball deficit first
    (recipe order; bag 1 + withdraw 1 = 2), then the ash leg: gather 49
    ash_wood (bag already holds 1 of the 50 = 5 plank x 10 wood), batch-
    craft the planks, craft the bow. No Fight leg HERE — the bank covers
    the drop deficit, so the first leg is the Withdraw; the Fight leg of
    the same generator path is pinned by the empty-holdings sweep and the
    unit tests (tests/test_ai/test_craft_plan_gen.py)."""
    report = _run(L13)
    assert report.decision.chosen_root == ObtainItem(
        code="fire_bow", quantity=1, slot="weapon_slot")
    assert report.decision.chosen_step == ReachSkillLevel(
        skill="weaponcrafting", level=10)
    assert repr(report.selected_goal) == \
        "GatherMaterials(water_bow, {water_bow:1})", (
        repr(report.selected_goal),
        [g.get("goal") for g in report.goals_tried])
    water_bow_entries = [g for g in report.goals_tried
                         if str(g.get("goal", "")).startswith(
                             "GatherMaterials(water_bow")]
    assert water_bow_entries, report.goals_tried
    assert all(entry["nodes"] == 0 and not entry["timed_out"]
               and entry["plan_len"] == len(report.plan)
               for entry in water_bow_entries), water_bow_entries
    assert [repr(a) for a in report.plan] == [
        "Withdraw(blue_slimeball×1)",
        "Gather(ash_tree)",
        "Craft(ash_plank×5)",
        "Craft(water_bow×1)",
    ], report.plan


def test_l13_search_is_bounded() -> None:
    """The 38K/53K-node A* flood becomes a caught bound-violation class:
    every goal the arbiter tried must stay bounded and un-timed-out — the
    shared band-liveness bound."""
    assert_search_bounded(_run(L13), L13)


# --- The CLASS net: every craftable-with-drop-leaf recipe reachable at the
# --- l13 scenario's stats must generate a plan from empty holdings.

def _closure_items(recipes: dict[str, dict[str, int]],
                   target: str) -> set[str]:
    """Item codes in `target`'s recipe closure (same DFS the generator's
    CAN-GENERATE gate walks)."""
    seen: set[str] = set()
    stack = [target]
    while stack:
        item = stack.pop()
        if item in seen:
            continue
        seen.add(item)
        stack.extend(recipes.get(item, {}))
    return seen


def _drop_leaf_recipes() -> list[str]:
    """Every recipe in the bundle whose closure contains >= 1 monster-drop
    leaf and is otherwise fully reachable at the l13 scenario's stats:

    - every craftable in the closure has its skill gate met and a workshop;
    - every gatherable leaf is the primary drop of a resource whose skill
      gate is open (the generator maps gather steps by primary drop);
    - every monster-drop leaf has a winnable, XP-POSITIVE dropper at the
      scenario's level/loadout (grey-dropper policy variants are unit-test
      territory — grey_farm_allowed can honestly suppress the Fight, which
      is not a generator failure).

    Enumerated from the bundle so a catalog update re-derives the class
    automatically instead of pinning a hand-picked list."""
    gd = _bundle()
    state = scenario_state(SCENARIOS[L13], gd)
    recipes: dict[str, dict[str, int]] = dict(gd.crafting_recipes)
    gatherable = set(gd.gatherable_drop_items())
    primary_open = {
        drop for res, drop in gd.resource_drops.items()
        if (req := gd.resource_skill_level(res)) is None
        or state.skills.get(req[0], 1) >= req[1]
    }
    out: list[str] = []
    for code in sorted(recipes):
        closure = _closure_items(recipes, code)
        drop_leaves = [
            i for i in closure
            if i not in recipes and i not in gatherable
            and gd.monsters_dropping(i)
        ]
        if not drop_leaves:
            continue
        reachable = True
        for item in closure:
            if item in recipes:
                stats = gd.item_stats(item)
                if (stats is None or stats.crafting_skill is None
                        or state.skills.get(stats.crafting_skill, 1)
                        < stats.crafting_level
                        or gd.workshop_location(stats.crafting_skill) is None):
                    reachable = False
                    break
            elif item in gatherable:
                if item not in primary_open:
                    reachable = False
                    break
            else:
                if not any(
                    is_winnable(state, gd, monster)
                    and gd.xp_per_kill(monster, state.level) > 0
                    for monster, _rate, _mn, _mx in gd.monsters_dropping(item)
                ):
                    reachable = False
                    break
        if reachable:
            out.append(code)
    return out


DROP_LEAF_RECIPES = _drop_leaf_recipes()

# Pinned against the current bundle (2026-07-08): copper_armor, fire_staff,
# iron_helm, iron_shield, sticky_dagger, water_bow. Compared by set equality,
# not just membership, so the class can neither silently GROW (an untested
# new recipe rides the parametrized sweep unnoticed but this anchor still
# needs a deliberate update) nor silently SHRINK to a near-empty net that a
# bare "water_bow in DROP_LEAF_RECIPES" check would wave through —
# enumeration rot in either direction fails loudly here first.
_EXPECTED_DROP_LEAF_RECIPES = frozenset({
    "copper_armor", "fire_staff", "iron_helm", "iron_shield",
    "sticky_dagger", "water_bow",
})


def test_drop_leaf_class_is_nonempty() -> None:
    """The sweep must actually cover the class — an empty enumeration would
    green-wash every parametrized case away. water_bow (the live stall's
    recipe) must be in it, and the class must match the pinned set exactly
    (enumerate-and-compare) so a shrinking enumeration can't silently drop
    coverage without failing anything."""
    assert "water_bow" in DROP_LEAF_RECIPES, DROP_LEAF_RECIPES
    assert set(DROP_LEAF_RECIPES) == _EXPECTED_DROP_LEAF_RECIPES, (
        "drop-leaf class enumeration changed — update the pinned set if this "
        "is an intentional bundle/catalog change",
        sorted(set(DROP_LEAF_RECIPES) ^ _EXPECTED_DROP_LEAF_RECIPES),
        sorted(DROP_LEAF_RECIPES),
    )


@pytest.fixture(scope="module")
def bare_sweep_env() -> tuple[WorldState, GameData, list[Action]]:
    """One shared (bare state, game data, factory actions) triple for the
    sweep: the l13 scenario stripped to EMPTY holdings (inventory + bank),
    seeded through the same offline seam the full-stack tests use, with the
    REAL action factory's output (not a hand-picked action list) — the
    sweep must exercise the exact surface the live planner hands the
    generator."""
    gd = load_bundle_game_data(BUNDLE)
    state = scenario_state(SCENARIOS[L13], gd)
    bare: WorldState = dataclasses.replace(state, inventory={}, bank_items={})
    player = GamePlayer(character=L13, history=None)
    player.seed_offline(bare, gd)
    return bare, gd, list(player._build_actions())


@pytest.mark.parametrize("code", DROP_LEAF_RECIPES)
def test_drop_leaf_recipe_generates_plan(
    code: str, bare_sweep_env: tuple[WorldState, GameData, list[Action]],
) -> None:
    """CLASS NET (BINDING user directive): from EMPTY holdings — so every
    monster-drop leaf genuinely needs its Fight leg, no bank cover — the
    generator must produce a non-empty plan for every reachable
    craftable-with-drop-leaf recipe. Before GAP-8 every one of these
    returned None and rode the A* flood."""
    bare, gd, actions = bare_sweep_env
    goal = GatherMaterialsGoal(code, {code: 1})
    plan = generate_next_craft_action(goal, bare, gd, actions)
    assert plan, (code, plan)
