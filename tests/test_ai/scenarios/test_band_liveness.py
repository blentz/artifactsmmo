"""Per-band planner-deadlock insulation (Phase 1 follow-up, deferred at
progression-tree design time — docs/superpowers/specs/
2026-07-06-progression-tree-design.md): one scenario per trunk band (L10,
L20, L30, L40, L50), each a plausible character ENTERING that band slightly
under-tier, asserting the planner CANNOT deadlock there.

These scenarios double as an anti-deadlock net for the whole trunk AND as
empirical evidence toward L50 reachability (see project_l50_unconditional
_descent): each band's decide_tree call must produce a totalizing decision
(chosen_root/chosen_step non-None), the full plan_from_state seam must
select a goal and emit a non-empty plan, and the search behind that plan
must stay bounded (the feather_coat 237K-node flood is the deadlock
precursor this net exists to catch — see project_feather_coat_cpu_peg)."""

import json
from pathlib import Path
from typing import cast

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.plan_report import PlanReport
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.tiers.meta_goal import ReachCharLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.progression_tree import decide_tree
from artifactsmmo_cli.ai.tiers.progression_tree_core import milestone_pure
from artifactsmmo_cli.ai.tiers.strategy import StrategyDecision
from artifactsmmo_cli.ai.world_state import WorldState

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"

BAND_NAMES = [
    "l15_midband", "l20_band_entry", "l30_band_entry",
    "l40_band_entry", "l48_capstone_approach",
]

MAX_SEARCH_NODES = 200_000
"""The feather_coat lesson (project_feather_coat_cpu_peg): an unsatisfiable
GatherMaterials goal exploded to 237K nodes/cycle before a plan-cache /
memo fix landed. A band scenario that lands anywhere near that magnitude,
even while still emitting SOME plan, is a deadlock precursor — treat it as
a failure, not a warning."""


def _bundle() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def _decide(name: str) -> tuple[StrategyDecision, WorldState]:
    gd = _bundle()
    state = scenario_state(SCENARIOS[name])
    objective = CharacterObjective.from_game_data(gd)
    return decide_tree(state, gd, objective), state


def _run(name: str) -> PlanReport:
    player = GamePlayer(character=name, history=None)
    player.seed_offline(scenario_state(SCENARIOS[name]), load_bundle_game_data(BUNDLE))
    return player.plan_from_state()


@pytest.mark.parametrize("name", BAND_NAMES)
def test_band_registered(name: str) -> None:
    """Registry-first (TDD): the band scenarios must exist under the exact
    binding names before anything else in this file can run."""
    assert name in SCENARIOS


@pytest.mark.parametrize("name", BAND_NAMES)
def test_decide_tree_is_total(name: str) -> None:
    """decide_tree always answers: chosen_root and chosen_step are never
    None. Every band scenario here is under-tier by construction (a
    reachable structural upgrade exists in every slot set below), so this
    also exercises the GEAR branch and its internal ordered[0] == pick
    assertion (progression_tree.py:194) on real catalog data."""
    d, _state = _decide(name)
    assert d.chosen_root is not None
    assert d.chosen_step is not None


@pytest.mark.parametrize("name", BAND_NAMES)
def test_band_liveness_full_stack(name: str) -> None:
    """The Phase-1 seam (GamePlayer.seed_offline + plan_from_state): a goal
    must be selected and the plan must be non-empty. A guard goal (deposit/
    discard) still counts as long as it plans — an empty plan here is a
    genuine liveness bug, not something to relax."""
    report = _run(name)
    assert report.selected_goal is not None, (name, report.decision.chosen_root)
    assert report.plan, (
        name, repr(report.selected_goal),
        [g.get("goal") for g in report.goals_tried])


@pytest.mark.parametrize("name", BAND_NAMES)
def test_band_search_is_bounded(name: str) -> None:
    """The selected goal's own goals_tried entry must stay well under the
    node cap and must not have been node-capped or timed out — a bounded
    search that still finds nothing is a different (legitimate) failure
    mode than an unbounded one that happens to find something."""
    report = _run(name)
    selected_repr = repr(report.selected_goal)
    matches = [g for g in report.goals_tried if g.get("goal") == selected_repr]
    assert matches, (name, selected_repr, [g.get("goal") for g in report.goals_tried])
    entry = matches[-1]
    nodes = cast(int, entry["nodes"])
    node_capped = cast(bool, entry.get("node_capped", False))
    timed_out = cast(bool, entry["timed_out"])
    assert nodes < MAX_SEARCH_NODES, (name, entry)
    assert not node_capped, (name, entry)
    assert not timed_out, (name, entry)


@pytest.mark.parametrize("name", BAND_NAMES)
def test_band_trunk_row_matches_milestone_pure(name: str) -> None:
    """decide_tree's trunk row (ranking[0], category char_level) must be
    exactly ReachCharLevel(level=milestone_pure(scenario.level)) — the
    tree's own trunk semantics, checked against the pure core directly."""
    d, state = _decide(name)
    expected_trunk = ReachCharLevel(level=milestone_pure(state.level))
    trunk_row = d.ranking[0]
    assert trunk_row.category == "char_level"
    assert trunk_row.root_repr == repr(expected_trunk)
