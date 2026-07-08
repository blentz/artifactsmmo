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

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.plan_report import PlanReport
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.tiers.meta_goal import ReachCharLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.progression_tree import decide_tree, has_structural_upgrade
from artifactsmmo_cli.ai.tiers.progression_tree_core import milestone_pure
from artifactsmmo_cli.ai.tiers.strategy import StrategyDecision
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.scenarios.search_bounds import assert_search_bounded

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"

L48_BAND_ADEQUATE = "l48_band_adequate"
"""The capstone/XP-branch counterpart to l48_capstone_approach: every gear
slot already holds the catalog-best is_attainable_now item and both utility
slots are stocked, so has_structural_upgrade is False by construction — the
only band scenario that forces decide_tree's XP branch instead of GEAR. See
scenario.py's SCENARIOS entry docstring for how the equipment set was
derived (fixed-point iteration against near_term_gear, verified empirically
before this test was written)."""

BAND_NAMES = [
    "l15_midband", "l20_band_entry", "l30_band_entry",
    "l40_band_entry", "l48_capstone_approach", L48_BAND_ADEQUATE,
]

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
    """Every tried goal bounded — see search_bounds.assert_search_bounded
    (extracted for reuse by the slot-coverage net; the bound and its
    rationale live there now)."""
    assert_search_bounded(_run(name), name)


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


def test_l48_band_adequate_forced_xp_branch() -> None:
    """l48_band_adequate is constructed so has_structural_upgrade is False
    (every slot already holds the catalog-best is_attainable_now item, both
    utility slots stocked past 0 — see the SCENARIOS docstring) — the XP/
    capstone path the per-band net had no coverage for (test_decide_tree_
    is_total's under-tier bands all exercise the GEAR branch). With
    band_adequate explicitly True (the caller-supplied leg decide_tree
    itself never computes), branch_pick_pure must pick XP and the chosen
    root/step must be exactly the L48->50 trunk milestone, not a gear
    candidate."""
    gd = _bundle()
    state = scenario_state(SCENARIOS[L48_BAND_ADEQUATE])
    objective = CharacterObjective.from_game_data(gd)
    decision = decide_tree(state, gd, objective, band_adequate=True)
    expected = ReachCharLevel(level=milestone_pure(state.level))
    assert decision.chosen_root == expected
    assert decision.chosen_step == expected


def test_l48_band_adequate_real_band_adequate_verdict() -> None:
    """Empirical record of the REAL `_tree_band_adequate()` wiring for
    l48_band_adequate (as opposed to the hardcoded band_adequate=True in
    test_l48_band_adequate_forced_xp_branch above) — plan_from_state's
    actual caller, not a direct decide_tree call.

    `_tree_band_adequate()` ANDs two legs: no structural upgrade (verified
    True here, matching the scenario's construction) AND a winnable monster
    exists for the current loadout. The second leg is FALSE in this bundle:
    the only catalog monsters in the L48 fight window ([47, 50] — duskworm,
    dusk_beetle, sandwarden, desert_scorpion, solar_desert_scorpion,
    baby_red_dragon) are all unwinnable against a full non-event mithril-
    tier loadout at max HP. This is the SAME difficulty wall documented in
    project_l50_unconditional_descent ("event gear = progression
    REQUIREMENT") — band_adequate reads False for a real, already-known
    reason, not a construction bug in this scenario.

    decide_tree's answer is unaffected either way (branch_pick_pure picks
    XP whenever gear_target_exists is False, regardless of band_adequate —
    see test_l48_band_adequate_forced_xp_branch), so the plan_from_state
    seam still selects and plans something: WaitGoal, the documented
    last-resort fallback (goals/wait.py) — no combat target exists to grind
    the trunk milestone with. That IS the genuine capstone-path finding
    this test records rather than hides: at L48 with a complete non-event
    loadout, this bundle's monster catalog cannot carry a character to L50
    by combat alone."""
    gd = _bundle()
    state = scenario_state(SCENARIOS[L48_BAND_ADEQUATE])
    objective = CharacterObjective.from_game_data(gd)
    assert has_structural_upgrade(state, gd, objective) is False

    player = GamePlayer(character=L48_BAND_ADEQUATE, history=None)
    player.seed_offline(state, load_bundle_game_data(BUNDLE))
    assert player._pick_winnable_monster() is None, (
        "no L47-50 window monster should be winnable against this "
        "non-event loadout in this bundle; if this now finds one, the "
        "L50-difficulty-wall finding above is stale and must be revised")
    assert player._tree_band_adequate() is False

    report = player.plan_from_state()
    # Pin the EXACT last-resort outcome (not just any non-empty plan): the
    # docstring's finding is only witnessed if Wait is what gets selected.
    assert repr(report.selected_goal) == "Wait", (
        repr(report.selected_goal), report.plan)
    assert report.plan, (repr(report.selected_goal), report.plan)
    assert report.decision.chosen_root == ReachCharLevel(level=50)
    assert report.decision.chosen_step == ReachCharLevel(level=50)
