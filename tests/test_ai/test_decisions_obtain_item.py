"""Transcription parity: the Decision graph must return exactly what the
if-pile returned, for every ObtainItem shape the scenario set produces.

Enumerates BOTH `step is root` and `step != root` pairs. The branches at
`strategy_driver.py:910-1005` (`IsThisAnIntermediateOnAChain` and its
descendants) are only reachable when `root.code != step.code` — a parity
test using only `root=step` would pass while exercising none of them, and
would also leave those Decisions' `resolve` bodies uncovered.

The tests below `test_graph_matches_the_legacy_if_pile` cover branches the
bundle-catalog/scenario sweep never reaches: the `analyze_currency_leaves`
funding-target route and the depth-reachable-root route are both real, live
paths (see their docstrings) that happen not to be triggered by any
(scenario, recipe) pair in `tests/test_ai/scenarios/fixtures/gamedata_bundle.
json`, and `_legacy_objective_step_goal`'s non-`ObtainItem` branches
(`step is None`, an unrecognized step type, and every `ReachCharLevel`
sub-branch) are never reached by the ObtainItem-only parity loop at all.
Each compares `_legacy_objective_step_goal` against the STILL-LIVE
`objective_step_goal` (identical body) rather than against the Decision
graph, since the graph does not model `ReachCharLevel` — only the ObtainItem
branches were transcribed in this task."""
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
def test_graph_matches_the_legacy_if_pile(scenario_name, bundle_game_data):
    """Compares against `_legacy_objective_step_goal`, the pre-transcription
    body kept verbatim for exactly this comparison and deleted in Task 5."""
    from artifactsmmo_cli.ai.strategy_driver import _legacy_objective_step_goal

    gd = bundle_game_data
    state = scenario_state(SCENARIOS[scenario_name], gd)
    for step_code, root_code in _step_root_pairs(gd):
        step = ObtainItem(code=step_code, quantity=1)
        root = ObtainItem(code=root_code, quantity=1)
        legacy = _legacy_objective_step_goal(step, state, gd, NO_PROFILE_CONTEXT,
                                             root=root, committed_root=root,
                                             history=None)
        graph = resolve_node(obtain_item_decision(step, root), state, gd,
                             NO_PROFILE_CONTEXT, None)
        assert repr(graph) == repr(legacy), (
            f"{scenario_name}/step={step_code}/root={root_code}: "
            f"graph={graph!r} legacy={legacy!r}")


def test_legacy_matches_graph_for_currency_funding():
    """Covers the `analyze_currency_leaves` funding-target branch (`return
    ReachCurrencyGoal(...)`) in both `_legacy_objective_step_goal` and
    `CanIAffordTheCurrencyLeaf` — the live satchel<-jasper_crystal routing
    (C4 Task 6, see `strategy_driver.py`'s DEMAND ROUTING comment), which no
    (scenario, recipe) pair in the bundle catalog happens to trigger."""
    from artifactsmmo_cli.ai.strategy_driver import _legacy_objective_step_goal

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
    legacy = _legacy_objective_step_goal(step, state, gd, NO_PROFILE_CONTEXT, root=step)
    graph = resolve_node(obtain_item_decision(step, step), state, gd,
                         NO_PROFILE_CONTEXT, None)
    assert isinstance(legacy, ReachCurrencyGoal)
    assert repr(graph) == repr(legacy)


def test_legacy_matches_graph_for_reachable_root_chunk():
    """Covers the `_gather_step_target_is_root` positive branch (`return
    upgrade`) in both `_legacy_objective_step_goal` and
    `DoesTheChainFitTheDepthBudget` — never hit by the bundle-catalog sweep
    above because none of its (recipe, material) pairs happens to be
    depth-reachable from empty holdings within the default `max_depth`."""
    from artifactsmmo_cli.ai.strategy_driver import _legacy_objective_step_goal

    gd = _gd()  # wooden_shield <- ash_plank x6 <- ash_wood: shallow chain
    state = make_state()
    step = ObtainItem("ash_plank", 6)
    root = ObtainItem("wooden_shield", 1)
    legacy = _legacy_objective_step_goal(step, state, gd, NO_PROFILE_CONTEXT, root=root)
    graph = resolve_node(obtain_item_decision(step, root), state, gd,
                         NO_PROFILE_CONTEXT, None)
    assert isinstance(legacy, UpgradeEquipmentGoal)
    assert repr(graph) == repr(legacy)


def test_legacy_matches_current_for_step_none():
    """`_legacy_objective_step_goal` is a verbatim copy of the full
    `objective_step_goal` body, including the `step is None` guard the
    ObtainItem-only parity loop above never reaches."""
    from artifactsmmo_cli.ai.strategy_driver import _legacy_objective_step_goal

    legacy = _legacy_objective_step_goal(None, make_state(), _gd(), _ctx())
    current = objective_step_goal(None, make_state(), _gd(), _ctx())
    assert legacy is None
    assert legacy == current


def test_legacy_matches_current_for_unrecognized_step():
    """Covers the final `return None` fallback for a step that is neither
    `ObtainItem` nor `ReachCharLevel`."""
    from artifactsmmo_cli.ai.strategy_driver import _legacy_objective_step_goal

    class _UnknownStep:
        pass

    legacy = _legacy_objective_step_goal(_UnknownStep(), make_state(), _gd(), _ctx())  # type: ignore[arg-type]
    current = objective_step_goal(_UnknownStep(), make_state(), _gd(), _ctx())  # type: ignore[arg-type]
    assert legacy is None
    assert legacy == current


def test_legacy_matches_current_for_reach_char_level_no_monster():
    """`ctx.combat_monster is None` -> early `return None`."""
    from artifactsmmo_cli.ai.strategy_driver import _legacy_objective_step_goal

    step = ReachCharLevel(10)
    ctx = _ctx(combat_monster=None)
    legacy = _legacy_objective_step_goal(step, make_state(), _gd(), ctx)
    current = objective_step_goal(step, make_state(), _gd(), ctx)
    assert legacy is None
    assert legacy == current


def test_legacy_matches_current_for_reach_char_level_stands_down():
    """Items-task stand-down: `objective_step_is_fight_pure` False -> None
    for the long-haul ReachCharLevel(50) step."""
    from artifactsmmo_cli.ai.strategy_driver import _legacy_objective_step_goal

    state = make_state(level=3, task_code="copper_bar", task_type="items",
                       task_total=20, task_progress=0)
    step = ReachCharLevel(50)
    ctx = _ctx(combat_monster="chicken")
    legacy = _legacy_objective_step_goal(step, state, GameData(), ctx)
    current = objective_step_goal(step, state, GameData(), ctx)
    assert legacy is None
    assert legacy == current


def test_legacy_matches_current_for_reach_char_level_grinds():
    """No provision goal available -> falls through to GrindCharacterXPGoal."""
    from artifactsmmo_cli.ai.strategy_driver import _legacy_objective_step_goal

    step = ReachCharLevel(10)
    state = make_state(xp=50)
    ctx = _ctx(combat_monster="chicken")
    legacy = _legacy_objective_step_goal(step, state, _gd(), ctx)
    current = objective_step_goal(step, state, _gd(), ctx)
    assert isinstance(legacy, GrindCharacterXPGoal)
    assert repr(legacy) == repr(current)


def test_legacy_matches_current_for_reach_char_level_provisions(tmp_path):
    """`_marginal_provision_goal` returns a goal -> `return provision`."""
    from artifactsmmo_cli.ai.strategy_driver import _legacy_objective_step_goal

    state = make_state(level=3, inventory={"small_health_potion": 100})
    gd = _gd_with_utility_heal("small_health_potion", hp_restore=60)
    history = LearningStore(db_path=str(tmp_path / "l.db"), character="r")
    _record_fight_wins_with_consumables(
        history, "green_slime", 8, json.dumps({"small_health_potion": 2}))
    ctx = _ctx(combat_monster="green_slime")
    step = ReachCharLevel(level=5)
    legacy = _legacy_objective_step_goal(step, state, gd, ctx, history=history)
    current = objective_step_goal(step, state, gd, ctx, history=history)
    assert isinstance(legacy, ProvisionMarginalFightGoal)
    assert repr(legacy) == repr(current)
    history.close()
