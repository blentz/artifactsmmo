"""plan_from_state: the pure planning entry the CLI and scenarios share."""

import json
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.plan_report import PlanReport
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.tiers.prerequisite_graph import prerequisites
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


def test_plan_from_state_wires_the_real_selection_context() -> None:
    """THE ACTIVATION (one-obtain-model epic, Task 5; originally the
    recycle-as-acquisition epic's Task 6): the player must compute the
    per-cycle `SelectionContext` at the `_selection_context` seam and stash it
    on `self._last_ctx`, or `prerequisites`/`actionable_step`/`next_grind_goal`
    (which all consume it to ask `ai/obtain_sources` for a ready non-craft
    route) stay INERT in production (feedback_verify_runtime_activation). Bag
    holds 7 fishing_net (recipe: 6 ash_plank each) — licensed surplus
    recyclable for ash_plank, so under the wired ctx
    `prerequisites(ObtainItem("ash_plank"), ...)` must be a LEAF."""
    gd = GameData()
    gd._item_stats = {
        "fishing_net": ItemStats(code="fishing_net", level=1, type_="amulet",
                                 crafting_skill="gearcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {"fishing_net": {"ash_plank": 6}}
    gd._workshop_locations = {"gearcrafting": (2, 1)}
    gd._bank_location = (0, 0)
    gd._taskmaster_location = (0, 0)
    player = GamePlayer(character="scenario", history=None)
    state = make_state(level=5, inventory={"fishing_net": 7}, bank_items={})
    player.seed_offline(state, gd)

    assert player._last_ctx == NO_PROFILE_CONTEXT  # nothing computed before the first cycle

    player.plan_from_state()

    assert player._last_ctx != NO_PROFILE_CONTEXT  # a real per-cycle ctx was computed
    assert prerequisites(ObtainItem("ash_plank", 6), player.state, gd,
                         player._last_ctx) == []
