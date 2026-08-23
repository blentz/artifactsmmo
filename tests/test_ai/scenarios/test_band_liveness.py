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
    # GAP-8 (2026-07-08): the live-Robby drop-recipe stall witness joins the
    # net permanently — its GatherMaterials(water_bow) goal used to flood A*
    # to timeout (38K live / 53K offline nodes), which is exactly the
    # deadlock-precursor class test_band_search_is_bounded exists to catch.
    "l13_drop_recipe_grind",
]

def _bundle() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def _decide(name: str) -> tuple[StrategyDecision, WorldState]:
    gd = _bundle()
    # game_data is passed through so derive_combat_stats scenarios (the
    # GAP-8 l13 witness) can sum their gear stats; inert for the hand-
    # declared zero-stat band scenarios (the parameter is unused there).
    state = scenario_state(SCENARIOS[name], gd)
    objective = CharacterObjective.from_game_data(gd)
    return decide_tree(state, gd, objective), state


def _run(name: str) -> PlanReport:
    gd = load_bundle_game_data(BUNDLE)
    player = GamePlayer(character=name, history=None)
    player.seed_offline(scenario_state(SCENARIOS[name], gd), gd)
    return player.plan_from_state()


@pytest.mark.parametrize("name", BAND_NAMES)
def test_band_registered(name: str) -> None:
    """Registry-first (TDD): the band scenarios must exist under the exact
    binding names before anything else in this file can run."""
    assert name in SCENARIOS


@pytest.mark.parametrize("name", BAND_NAMES)
def test_decide_tree_answers_or_names_the_wall(name: str) -> None:
    """WAVE 3a re-derived this from "decide_tree always answers" to "decide_tree
    answers, or says None and offers the trunk".

    Totality was a property of the old assembly: the trunk was ALWAYS the
    chosen root or a fallback, so a character with nothing to do was handed a
    level target it could not reach and the pane read as progress. The
    resolution walk has an explicit wall arm — `CanIClearMyTier` returns None
    when the gear sheet wants nothing AND no monster in the band is winnable —
    and reporting that honestly is the behaviour, not a gap in it
    (`root.py`: "reported as `None` rather than dressed up as a root the
    character cannot make progress on").

    `l48_band_adequate` is the one band scenario that hits it, and it hits it
    for the documented L50 difficulty-wall reason (see
    `test_l48_band_adequate_is_the_honest_wall`). Every other band still
    resolves a root, so this stays a real assertion rather than a disjunction
    that can never fail: the trunk alternative is required in BOTH arms, so a
    walk that returned None with nothing behind it fails here."""
    d, _state = _decide(name)
    if name == L48_BAND_ADEQUATE:
        assert d.chosen_root is None and d.chosen_step is None
    else:
        assert d.chosen_root is not None
        assert d.chosen_step is not None
    assert any(isinstance(r, ReachCharLevel) for r in d.fallback_roots)


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
    # WAVE 3a: l48_band_adequate is no longer a no-work scenario — the trunk
    # now descends through `actionable_step` and reaches a craft chain. See
    # `search_bounds.assert_search_bounded`, which lost its `expect_no_work`
    # flag for that reason.
    assert_search_bounded(_run(name), name)


@pytest.mark.parametrize("name", BAND_NAMES)
def test_band_trunk_row_matches_milestone_pure(name: str) -> None:
    """decide_tree's trunk row must be exactly
    ReachCharLevel(level=milestone_pure(scenario.level)) — the tree's own trunk
    semantics, checked against the pure core directly.

    WAVE 3a moved WHERE the row sits and what its `category` reads. It is no
    longer `ranking[0]`: `_resolution_rows` leads with the CHOSEN root, and
    `resolve_root` appends the trunk after every sibling, so the trunk is LAST.
    Its category is `alternative · char_level` — the column now says how a row
    got there, and the trunk is an alternative in every one of these
    scenarios. Both facts are asserted, so a walk that promoted the trunk to
    the head or relabelled the column fails here."""
    d, state = _decide(name)
    expected_trunk = ReachCharLevel(level=milestone_pure(state.level))
    trunk_row = d.ranking[-1]
    assert trunk_row.category == "alternative · char_level"
    assert trunk_row.root_repr == repr(expected_trunk)


def test_l48_band_adequate_is_the_honest_wall() -> None:
    """l48_band_adequate is constructed so has_structural_upgrade is False
    (every slot already holds the catalog-best is_attainable_now item, both
    utility slots stocked past 0 — see the SCENARIOS docstring).

    WAVE 3a re-derived this test. It used to pass `band_adequate=True` and
    assert `branch_pick_pure` picked the L48->50 trunk. There is no
    `band_adequate` and no `branch_pick_pure` in the walk, and the answer is
    strictly better: the gear sheet wants nothing, no L47-50 monster is
    winnable (the documented event-gear wall — see
    `test_l48_band_adequate_real_band_adequate_verdict`), and rung 50 is NOT
    cleared, so `CanIClearMyTier` names the wall as `None` instead of handing
    back a level-50 target the character has no route to.

    The trunk is still OFFERED, last, so the arbiter can fall through to it —
    which is what stops this being a deadlock and what the old assertion was
    really buying."""
    gd = _bundle()
    state = scenario_state(SCENARIOS[L48_BAND_ADEQUATE])
    objective = CharacterObjective.from_game_data(gd)
    decision = decide_tree(state, gd, objective)
    assert decision.chosen_root is None
    assert decision.chosen_step is None
    assert decision.fallback_roots == [
        ReachCharLevel(level=milestone_pure(state.level))]


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

    WAVE 3a changed what the seam then DOES with that verdict, and the change
    is an improvement worth recording. The walk now names the wall (`chosen_root
    is None` — see `test_l48_band_adequate_is_the_honest_wall`), and instead of
    falling all the way to `WaitGoal` the arbiter reaches a real means:
    `GatherMaterials(mithril_bar)`, a 3-action craft chain. The finding this
    test exists to record is UNCHANGED — at L48 with a complete non-event
    loadout this bundle's monster catalogue cannot carry a character to L50 by
    combat alone — but the bot no longer idles on it, which is why the pinned
    outcome moved from `Wait` to a plan."""
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
    # Pin the EXACT outcome, not just any non-empty plan.
    assert repr(report.selected_goal) == "GatherMaterials(mithril_bar, {mithril_bar:11})", (
        repr(report.selected_goal), report.plan)
    assert report.plan, (repr(report.selected_goal), report.plan)
    assert report.decision.chosen_root is None
    assert report.decision.chosen_step is None
