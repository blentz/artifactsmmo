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


def test_plan_from_state_decision_is_the_tree_decision() -> None:
    """Phase 4b (THE FLIP): `report.decision` IS the progression-tree
    decision — there is no separate shadow (`tree_decision`/`enacted_engine`
    died with the flag). l10_weapon_upgrade is gear-branch (weapon slot lags
    a tier, band inadequate), so the chosen_root is the weapon-slot
    ObtainItem the tree pins (see test_progression_tree's per-scenario
    pins)."""
    gd = load_bundle_game_data(BUNDLE)
    sc = SCENARIOS["l10_weapon_upgrade"]
    player = GamePlayer(character=sc.name, history=None)
    player.seed_offline(scenario_state(sc), gd)
    report = player.plan_from_state()
    assert isinstance(report.decision.chosen_root, ObtainItem)
    assert report.decision.chosen_root.slot == "weapon_slot"
    # The single decision is what the player stashed for trace/observer use.
    assert player._last_decision is not None
    assert repr(player._last_decision.chosen_root) == repr(report.decision.chosen_root)
    # The Phase-3/4a shadow surfaces are gone from the report.
    assert not hasattr(report, "tree_decision")
    assert not hasattr(report, "enacted_engine")
