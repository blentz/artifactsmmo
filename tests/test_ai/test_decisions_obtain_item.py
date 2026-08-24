"""Transcription parity: the Decision graph must return exactly what
`objective_step_goal`'s `ObtainItem` arm returns, for every ObtainItem shape
the scenario set produces. `objective_step_goal`'s `ObtainItem` arm IS
`resolve_node(obtain_item_decision(step, root), ...)` (Task 5) -- there is no
longer a second, independent if-pile implementation to transcribe against
(`_legacy_objective_step_goal` was that implementation, kept only for the
Task 4/5 transition and deleted once this parity held). The sweep below
still earns its keep two ways: it pins that the production entry point
forwards its arguments to the graph correctly (a wiring regression a future
edit to `objective_step_goal` could silently break), and it is the only
thing that reaches many of the Decision classes' `resolve` bodies across a
realistic (recipe, material) space for coverage.

Enumerates BOTH `step is root` and `step != root` pairs. The branches at
`decisions/obtain_item.py`'s `IsThisAnIntermediateOnAChain` and its
descendants are only reachable when `root.code != step.code` — a parity
test using only `root=step` would pass while exercising none of them, and
would also leave those Decisions' `resolve` bodies uncovered.

The tests below `test_objective_step_goal_forwards_to_the_graph` cover
branches the bundle-catalog/scenario sweep never reaches: the
`analyze_currency_leaves` funding-target route and the depth-reachable-root
route are both real, live paths (see their docstrings) that happen not to be
triggered by any (scenario, recipe) pair in
`tests/test_ai/scenarios/fixtures/gamedata_bundle.json`. The final group pins
`objective_step_goal`'s non-`ObtainItem` branches (`step is None`, an
unrecognized step type, and every `ReachCharLevel` sub-branch) directly --
those live entirely in `strategy_driver.py` and are never reached by the
ObtainItem-only Decision graph at all."""
import json

import pytest

from artifactsmmo_cli.ai.decision import resolve_node
from artifactsmmo_cli.ai.decisions.obtain_item import obtain_item_decision
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.goals.provision_marginal_fight import ProvisionMarginalFightGoal
from artifactsmmo_cli.ai.goals.reach_currency import ReachCurrencyGoal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.strategy_driver import objective_step_goal
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_strategy_driver import (
    _ctx,
    _gd,
    _gd_with_utility_heal,
    _record_fight_wins_with_consumables,
)


def _step_root_pairs(gd):
    """(step_code, root_code) pairs: every recipe paired with itself
    (`step is root`) and with each of its own recipe materials
    (`step != root`, and `root` is a real chain root over `step`)."""
    pairs = []
    for root_code in sorted(gd.crafting_recipes)[:25]:
        pairs.append((root_code, root_code))
        for material_code in sorted(gd.crafting_recipes[root_code]):
            pairs.append((material_code, root_code))
    return pairs


@pytest.mark.parametrize("scenario_name", sorted(SCENARIOS))
def test_objective_step_goal_forwards_to_the_graph(scenario_name, bundle_game_data):
    """`objective_step_goal`'s `ObtainItem` arm must return exactly what
    calling the graph directly returns, for every (scenario, step, root)
    triple the bundle catalog produces -- pinning the production wiring
    (`return resolve_node(obtain_item_decision(step, root), state, game_data,
    ctx, history)`) rather than a second hand-written implementation."""
    gd = bundle_game_data
    state = scenario_state(SCENARIOS[scenario_name], gd)
    for step_code, root_code in _step_root_pairs(gd):
        step = ObtainItem(code=step_code, quantity=1)
        root = ObtainItem(code=root_code, quantity=1)
        production = objective_step_goal(step, state, gd, NO_PROFILE_CONTEXT,
                                         root=root,
                                         history=None)
        graph = resolve_node(obtain_item_decision(step, root), state, gd,
                             NO_PROFILE_CONTEXT, None)
        assert repr(production) == repr(graph), (
            f"{scenario_name}/step={step_code}/root={root_code}: "
            f"objective_step_goal={production!r} graph={graph!r}")


def test_a_skill_gated_root_raises_the_skill_by_one(bundle_game_data):
    """Robby's live case. gold_sword is weaponcrafting 30 and he has 10. The
    branch used to return GatherMaterials for the step — gather the materials
    for a craft that cannot run — so nothing ever demanded the skill and
    weaponcrafting sat at 10 fleet-wide from 2026-08-16.

    The increment is +1, not the target: the graph re-derives every cycle, so
    planning the whole 10->30 climb is both unnecessary and enormous."""
    gd = bundle_game_data
    root = ObtainItem(code="gold_sword", quantity=1, slot="weapon_slot")
    step = ObtainItem(code="gold_bar", quantity=8)
    state = make_state(level=30, skills={"weaponcrafting": 10})

    goal = resolve_node(obtain_item_decision(step, root), state, gd,
                        NO_PROFILE_CONTEXT, None)

    assert repr(goal) == "ReachSkill(weaponcrafting->11)"


def test_objective_step_goal_funds_the_currency_leaf():
    """Covers the `analyze_currency_leaves` funding-target branch (`return
    ReachCurrencyGoal(...)`) in both `objective_step_goal` and
    `CanIAffordTheCurrencyLeaf` — the live satchel<-jasper_crystal routing
    (C4 Task 6, see `strategy_driver.py`'s DEMAND ROUTING comment), which no
    (scenario, recipe) pair in the bundle catalog happens to trigger."""
    gd = GameData()
    gd._crafting_recipes = {"satchel": {"jasper_crystal": 1}}
    gd._item_stats = {
        "satchel": ItemStats(code="satchel", level=1, type_="bag",
                             crafting_skill="gearcrafting", crafting_level=1),
    }
    gd._npc_stock = {"tasks_trader": {"jasper_crystal": 8}}
    gd._npc_buy_currency = {"tasks_trader": {"jasper_crystal": "tasks_coin"}}
    gd._task_coin_rewards = {"chicken": 1}
    gd._npc_locations = {"tasks_trader": (4, 1)}
    state = make_state(skills={"gearcrafting": 5}, inventory={}, bank_items={}, x=0, y=0)
    step = ObtainItem("satchel", 1)
    production = objective_step_goal(step, state, gd, NO_PROFILE_CONTEXT, root=step)
    graph = resolve_node(obtain_item_decision(step, step), state, gd,
                         NO_PROFILE_CONTEXT, None)
    assert isinstance(production, ReachCurrencyGoal)
    assert repr(graph) == repr(production)


def test_objective_step_goal_returns_the_reachable_root_chunk():
    """Covers the `_gather_step_target_is_root` positive branch (`return
    upgrade`) in both `objective_step_goal` and `DoesTheChainFitTheDepthBudget`
    — never hit by the bundle-catalog sweep above because none of its (recipe,
    material) pairs happens to be depth-reachable from empty holdings within
    the default `max_depth`."""
    gd = _gd()  # wooden_shield <- ash_plank x6 <- ash_wood: shallow chain
    state = make_state()
    step = ObtainItem("ash_plank", 6)
    root = ObtainItem("wooden_shield", 1)
    production = objective_step_goal(step, state, gd, NO_PROFILE_CONTEXT, root=root)
    graph = resolve_node(obtain_item_decision(step, root), state, gd,
                         NO_PROFILE_CONTEXT, None)
    assert isinstance(production, UpgradeEquipmentGoal)
    assert repr(graph) == repr(production)


def test_objective_step_goal_returns_none_for_step_none():
    """`step is None` -> `None`, unreached by the ObtainItem-only Decision
    graph (it has no node for a missing step at all)."""
    assert objective_step_goal(None, make_state(), _gd(), _ctx()) is None


def test_objective_step_goal_returns_none_for_unrecognized_step():
    """Covers the final `return None` fallback for a step that is neither
    `ObtainItem` nor `ReachCharLevel`."""
    class _UnknownStep:
        pass

    assert objective_step_goal(_UnknownStep(), make_state(), _gd(), _ctx()) is None  # type: ignore[arg-type]


def test_objective_step_goal_returns_none_for_reach_char_level_no_monster():
    """`ctx.combat_monster is None` -> early `return None`."""
    step = ReachCharLevel(10)
    ctx = _ctx(combat_monster=None)
    assert objective_step_goal(step, make_state(), _gd(), ctx) is None


def test_objective_step_goal_stands_down_for_reach_char_level_items_task():
    """Items-task stand-down: `objective_step_is_fight_pure` False -> None
    for the long-haul ReachCharLevel(50) step."""
    state = make_state(level=3, task_code="copper_bar", task_type="items",
                       task_total=20, task_progress=0)
    step = ReachCharLevel(50)
    ctx = _ctx(combat_monster="chicken")
    assert objective_step_goal(step, state, GameData(), ctx) is None


def test_objective_step_goal_grinds_for_reach_char_level():
    """No provision goal available -> falls through to GrindCharacterXPGoal."""
    step = ReachCharLevel(10)
    state = make_state(xp=50)
    ctx = _ctx(combat_monster="chicken")
    goal = objective_step_goal(step, state, _gd(), ctx)
    assert isinstance(goal, GrindCharacterXPGoal)


def test_objective_step_goal_provisions_for_reach_char_level(tmp_path):
    """`_marginal_provision_goal` returns a goal -> `return provision`."""
    state = make_state(level=3, inventory={"small_health_potion": 100})
    gd = _gd_with_utility_heal("small_health_potion", hp_restore=60)
    history = LearningStore(db_path=str(tmp_path / "l.db"), character="r")
    _record_fight_wins_with_consumables(
        history, "green_slime", 8, json.dumps({"small_health_potion": 2}))
    ctx = _ctx(combat_monster="green_slime")
    step = ReachCharLevel(level=5)
    goal = objective_step_goal(step, state, gd, ctx, history=history)
    assert isinstance(goal, ProvisionMarginalFightGoal)
    history.close()
