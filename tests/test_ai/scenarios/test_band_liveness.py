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

from pathlib import Path

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.plan_report import PlanReport
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.progression.meta_goal import ObtainItem, ReachCharLevel, ReachSkillLevel
from artifactsmmo_cli.ai.progression.objective import CharacterObjective
from artifactsmmo_cli.ai.progression.progression_tree import decide_tree
from artifactsmmo_cli.ai.progression.strategy import StrategyDecision
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT
from tests.test_ai.scenarios.search_bounds import assert_search_bounded
from tests.test_ai.shared_world import attached, shared_world

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"

L48_BAND_ADEQUATE = "l48_band_adequate"
"""The capstone/XP-branch counterpart to l48_capstone_approach: every gear
slot already holds the catalog-best is_attainable_now item and both utility
slots are stocked, so the deleted band-adequacy leg (`has_structural_upgrade`,
plan C Task 4) read no upgrade by construction — the only band scenario that
forced decide_tree's XP branch instead of GEAR. See
scenario.py's SCENARIOS entry docstring for how the equipment set was
derived (fixed-point iteration against near_term_gear, verified empirically
before this test was written). That held only on its hand stats, which lacked
the loadout's: on its derived totals (ruling R, 2026-10-18) the slots want more,
so it is no longer band-adequate (`test_l48_band_adequate_is_the_honest_wall`)."""

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
    return shared_world(BUNDLE)


def _decide(name: str) -> tuple[StrategyDecision, WorldState]:
    gd = _bundle()
    # game_data is passed through so derive_combat_stats scenarios (the
    # GAP-8 l13 witness) can sum their gear stats; inert for the hand-
    # declared zero-stat band scenarios (the parameter is unused there).
    state = scenario_state(SCENARIOS[name], gd)
    objective = CharacterObjective.from_game_data(gd)
    # The walk's context carries the cycle's gear objective, attached by the
    # one function the player uses (ruling W).
    return decide_tree(state, gd, objective,
                       ctx=attached(state, gd, TIMED_NO_PROFILE_CONTEXT, None)), state


def _run(name: str) -> PlanReport:
    gd = shared_world(BUNDLE)
    player = GamePlayer(character=name, history=None)
    player._offline_timing = committed_timing()
    player._learned_drops = LearnedDrops.empty()
    player.seed_offline(scenario_state(SCENARIOS[name], gd), gd)
    return player.plan_from_state()


@pytest.mark.parametrize("name", BAND_NAMES)
def test_band_registered(name: str) -> None:
    """Registry-first (TDD): the band scenarios must exist under the exact
    binding names before anything else in this file can run."""
    assert name in SCENARIOS


@pytest.mark.parametrize("name", BAND_NAMES)
def test_decide_tree_answers_with_a_piece_and_no_level_grind(name: str) -> None:
    """RE-DERIVED Task 5 (global gear objective, spec 2026-10-18 §2.4, §6.2).
    Every band scenario has a gear objective with pieces missing, so the walk
    resolves a root and a step — the next piece — and offers NO level grind:
    no fight is chosen for XP while a piece of `L*` is missing. The old
    version required the trunk among the alternatives in every arm; that is
    now exactly what must not be there. Plan C deletes this band net."""
    d, _state = _decide(name)
    assert d.chosen_root is not None
    assert d.chosen_step is not None
    assert not any(isinstance(r, ReachCharLevel) for r in (d.chosen_root, *d.fallback_roots))


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


def test_l48_band_adequate_is_the_honest_wall() -> None:
    """l48_band_adequate is constructed so every slot already holds the
    catalog-best is_attainable_now item, both utility slots stocked past 0 —
    see the SCENARIOS docstring.

    WAVE 3a re-derived this test. It used to pass `band_adequate=True` and
    assert `branch_pick_pure` picked the L48->50 trunk. There is no
    `band_adequate` and no `branch_pick_pure` in the walk, and the answer is
    strictly better: the gear sheet wants nothing, no L47-50 monster is
    winnable (the documented event-gear wall — see
    `test_l48_band_adequate_plans_the_first_missing_piece`), and rung 50 is NOT
    cleared, so `CanIClearMyTier` names the wall as `None` instead of handing
    back a level-50 target the character has no route to.

    The trunk is still OFFERED, ahead of everything else, so the arbiter can
    fall through to it — which is what stops this being a deadlock and what
    the old assertion was really buying. Behind the trunk sit the restored
    standalone skill roots (`decisions/root._orphan_skill_roots`): the walk
    still NAMES the wall, and offering a skill nothing can gear for is what a
    walled character has left after the trunk. Both are asserted, because the
    ORDER is the safety property — an orphan root ahead of the trunk displaced
    this scenario's `GatherMaterials(mithril_bar)`, the gear that breaks the
    L38-48 wall.

    RE-DERIVED 2026-10-18 (ruling R): the wall was a STAT ARTEFACT. The
    scenario's hand stats lacked its loadout's; on the loadout's own totals
    the drop routes of monsters it now beats open gear its slots want. There
    is no honest wall in this scenario to rebuild, so the derived resolution
    is pinned.

    RE-DERIVED Task 5 (global gear objective): the root is the first missing
    `L*` piece for `m*` = hellhound, `goblin_guard_shield` (a drop of the
    underground goblin_guard), with the other pieces behind it — the
    jewelrycrafting climb the `mithril_ring` needs and the `lifesteal_rune` —
    and no trunk: no level grind while a piece is missing (§6.2). Plan C
    deletes this band witness.
    RE-DERIVED plan B Task 2 (`PIECE_POLICY`, ruling T2a): the 20000-gold
    `lifesteal_rune` is priced through gold earned by fighting, a finite price,
    so it orders ahead of the piece behind an unpriced climb."""
    gd = _bundle()
    state = scenario_state(SCENARIOS[L48_BAND_ADEQUATE], gd)
    objective = CharacterObjective.from_game_data(gd)
    decision = decide_tree(state, gd, objective,
                           ctx=attached(state, gd, TIMED_NO_PROFILE_CONTEXT, None))
    shield = ObtainItem(code="goblin_guard_shield", quantity=1, slot="shield_slot")
    assert decision.chosen_root == shield
    assert decision.chosen_step == shield
    assert decision.fallback_roots == [
        ObtainItem(code="lifesteal_rune", quantity=1, slot="rune_slot"),
        ReachSkillLevel(skill="jewelrycrafting", level=36)]


def test_l48_band_adequate_plans_the_first_missing_piece() -> None:
    """The full seam (plan_from_state) on l48_band_adequate: the grind target
    is `farm_target`'s, and with a piece of `L*` missing there is none — no
    fight is chosen for XP (spec 2026-10-18 §2.4, §6.2) — so the cycle plans
    that piece's acquisition: down to the goblin_guard's underground tile,
    fight it for the shield, equip it. The fight is an ACQUISITION step
    (§2.4.3), not one chosen for XP.

    RE-DERIVED plan C Task 4: this used to record the player's band-adequacy
    verdict (`_tree_band_adequate`: a structural upgrade exists, and the
    windowed pick found `hellhound`); both were deleted with the three-tier
    cascade. The outcome it pinned is unchanged, and `hellhound` is still the
    objective's `m*`."""
    gd = _bundle()
    state = scenario_state(SCENARIOS[L48_BAND_ADEQUATE], gd)
    player = GamePlayer(character=L48_BAND_ADEQUATE, history=None)
    player._offline_timing = committed_timing()
    player._learned_drops = LearnedDrops.empty()
    player.seed_offline(state, shared_world(BUNDLE))

    report = player.plan_from_state()
    assert player._last_ctx is not None and player._last_ctx.gear_objective is not None
    assert player._last_ctx.gear_objective.monster == "hellhound"
    assert not player._last_ctx.gear_objective.held
    assert player._last_ctx.combat_monster is None
    # Pin the EXACT outcome, not just any non-empty plan.
    shield = ObtainItem(code="goblin_guard_shield", quantity=1, slot="shield_slot")
    assert repr(report.selected_goal) == "UpgradeEquipment(goblin_guard_shield->shield_slot)"
    assert [repr(a) for a in report.plan] == [
        "Transition((5,-3,overworld)->(5,-3,underground))", "Fight(goblin_guard)",
        "Equip(goblin_guard_shield->shield_slot)"]
    assert report.decision.chosen_root == shield
    assert report.decision.chosen_step == shield
