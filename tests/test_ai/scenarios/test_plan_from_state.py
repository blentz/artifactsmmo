"""plan_from_state: the pure planning entry the CLI and scenarios share."""

import json
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.plan_report import PlanReport
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from tests.test_ai.fixtures import make_state

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"


def test_plan_from_state_runs_offline() -> None:
    """A seeded player plans a full cycle with NO client and returns a
    populated PlanReport — the seam every scenario golden runs through."""
    gd = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
    player = GamePlayer(character="scenario", history=None)
    state = make_state(level=1, hp=120, max_hp=120,
                       inventory={}, bank_items={}, gold=0)
    player.seed_offline(state, gd)
    report = player.plan_from_state()
    assert isinstance(report, PlanReport)
    assert report.selected_goal  # some goal always selected (WAIT at worst)
    assert report.goals_tried    # the arbiter tried candidates


def test_plan_from_state_reports_tree_shadow_for_weapon_upgrade() -> None:
    """Phase-3 Task 2: plan_from_state computes+reports the progression-tree
    shadow alongside the legacy decision. l10_weapon_upgrade is gear-branch
    (weapon slot lags a tier, band inadequate) — the tree's chosen_root is an
    ObtainItem, while the legacy `decision`/`selected_goal` are untouched by
    the shadow (BINDING: the tree does not drive selection)."""
    gd = load_bundle_game_data(BUNDLE)
    sc = SCENARIOS["l10_weapon_upgrade"]
    player = GamePlayer(character=sc.name, history=None)
    player.seed_offline(scenario_state(sc), gd)
    report = player.plan_from_state()
    assert report.tree_decision is not None
    assert isinstance(report.tree_decision.chosen_root, ObtainItem)
    # The legacy decision flow is unchanged by the shadow's presence — the
    # existing golden (test_goldens.CURRENT_TODAY) still pins its behavior.
    assert report.decision is not None
    # Flag-off (default): the legacy decision is what's enacted.
    assert report.enacted_engine == "legacy"


def test_plan_from_state_flag_on_enacts_tree_decision_for_weapon_upgrade() -> None:
    """Phase 4a Task 1: with `progression_tree=True`, the SAME scenario's
    enacted `report.decision` becomes the tree decision (an ObtainItem for
    weapon_slot) instead of the legacy StrategyEngine decision — the flip
    point. `report.tree_decision` is still populated (the shadow is computed
    unconditionally either way) and, since it's now the enacted decision too,
    matches `report.decision` exactly."""
    gd = load_bundle_game_data(BUNDLE)
    sc = SCENARIOS["l10_weapon_upgrade"]
    player = GamePlayer(character=sc.name, history=None, progression_tree=True)
    player.seed_offline(scenario_state(sc), gd)
    report = player.plan_from_state()
    assert report.enacted_engine == "tree"
    assert report.tree_decision is not None
    assert isinstance(report.decision.chosen_root, ObtainItem)
    assert report.decision.chosen_root.slot == "weapon_slot"
    assert repr(report.decision.chosen_root) == repr(report.tree_decision.chosen_root)
    # Sticky seam: `plan_from_state` stashes the enacted decision (used by
    # downstream consumers that need "what drove selection") separately from
    # the shadow — here it equals the tree decision, since the flag flipped.
    assert player._last_enacted_decision is not None
    assert repr(player._last_enacted_decision.chosen_root) == repr(report.decision.chosen_root)
