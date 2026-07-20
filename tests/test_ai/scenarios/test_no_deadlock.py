"""Gear-pursuit correctness Task 1 (docs/superpowers/sdd gear-pursuit-
correctness plan): pin the two no-deadlock criteria a prior investigation
confirmed already hold, as a regression net ahead of Task 3's pursuit_value
behavior change.

Criterion 1 — never deadlock on GrindCharacterXP when a reachable gear
target is blocked on a CRAFTING skill (not combat): `l10_gearcrafting_gap`
witnesses this directly (`ObtainItem(iron_boots)` chosen over the character-
level trunk), and its ramp `l10_gearcrafting_gap_combat_blocked` pins that
losing the material closure's only dropper makes the planner re-target
instead of thrashing an unwinnable fight.

Criterion 2 — never deadlock on skilling once the build is band-adequate:
`l20_dual_utility` (a winnable monster exists) pins the XP/char-level
branch; `l48_band_adequate` (no winnable monster in this bundle's L47-50
window — the documented event-gear wall) pins the `Wait` fallback, NOT a
skill/craft goal.

Every scenario here is re-derived directly against the bundle and the real
`plan_from_state` seam (TDD-flavored: this documents CURRENT, empirically
observed behavior, not aspiration) — see the SCENARIOS dict in scenario.py
for the full per-scenario derivation notes (in particular
`l10_gearcrafting_gap`'s L12->L10 re-derivation, which caught a genuine
grey-mob drop-farm interaction the original investigation's framing missed)."""

import json
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.goals.wait import WaitGoal
from artifactsmmo_cli.ai.plan_report import PlanReport
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.progression_tree import decide_tree
from artifactsmmo_cli.ai.tiers.strategy import StrategyDecision
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.scenarios.search_bounds import assert_search_bounded

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"

CRITERION_1_MAIN = "l10_gearcrafting_gap"
CRITERION_1_RAMP = "l10_gearcrafting_gap_combat_blocked"
CRITERION_2_WINNABLE = "l20_dual_utility"
CRITERION_2_WALLED = "l48_band_adequate"

SCENARIO_NAMES = [CRITERION_1_MAIN, CRITERION_1_RAMP]
"""Only the scenarios ADDED by this task; CRITERION_2_WINNABLE and
CRITERION_2_WALLED already exist in SCENARIOS (reused per the task brief)."""


def _bundle() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def _decide(name: str) -> tuple[StrategyDecision, WorldState]:
    gd = _bundle()
    state = scenario_state(SCENARIOS[name], gd)
    objective = CharacterObjective.from_game_data(gd)
    return decide_tree(state, gd, objective), state


def _player(name: str) -> tuple[GamePlayer, GameData]:
    gd = load_bundle_game_data(BUNDLE)
    player = GamePlayer(character=name, history=None)
    player.seed_offline(scenario_state(SCENARIOS[name], gd), gd)
    return player, gd


def _run(name: str) -> PlanReport:
    player, _gd = _player(name)
    return player.plan_from_state()


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_scenario_registered(name: str) -> None:
    """Registry-first (TDD): the new scenarios must exist under the exact
    binding names before anything else in this file can run."""
    assert name in SCENARIOS


# --- Criterion 1: never deadlock on GrindCharacterXP when a reachable gear
# target is blocked on a CRAFTING skill gap, not combat viability. ---------

def test_l10_gearcrafting_gap_chosen_root_targets_iron_boots() -> None:
    """decide_tree's chosen_root is the reachable gear candidate
    (`ObtainItem(iron_boots)`, gated on gearcrafting 10 not combat), NEVER
    the character-level trunk — pinning the actual observed
    `decide_tree` output for this state."""
    d, _state = _decide(CRITERION_1_MAIN)
    assert d.chosen_root == ObtainItem(code="iron_boots", quantity=1, slot="boots_slot")
    assert not isinstance(d.chosen_root, ReachCharLevel)


def test_l10_gearcrafting_gap_plans_craft_chain_not_char_grind() -> None:
    """The full plan_from_state seam: the selected goal is the
    GatherMaterials craft-chain step (feather, the actionable leaf of
    iron_boots' recipe closure — resolved via Fight(chicken), a normal
    winnable dropper at this level/loadout) — NEVER GrindCharacterXP. Pins
    the ACTUAL observed selected_goal/plan, not an assumption."""
    report = _run(CRITERION_1_MAIN)
    assert not isinstance(report.selected_goal, GrindCharacterXPGoal), (
        repr(report.selected_goal), report.plan)
    assert repr(report.selected_goal) == "GatherMaterials(feather, {feather:3})"
    assert [repr(a) for a in report.plan] == ["Fight(chicken)"]
    assert report.decision.chosen_root == ObtainItem(
        code="iron_boots", quantity=1, slot="boots_slot")


def test_l10_gearcrafting_gap_search_bounded() -> None:
    assert_search_bounded(_run(CRITERION_1_MAIN), CRITERION_1_MAIN)


def test_l10_gearcrafting_gap_combat_blocked_no_winnable_monster() -> None:
    """Tripwire (mirrors test_band_liveness's l48 tripwire): the ramp is
    constructed with zero derived combat stats so no monster — including
    the feather-dropping chicken — is winnable. If this ever finds a
    winnable monster, the scenario's "combat-blocked" construction is stale
    and the ramp test below no longer isolates what it claims to."""
    player, _gd = _player(CRITERION_1_RAMP)
    assert player._pick_winnable_monster() is None, (
        "no monster should be winnable against this zero-combat-stat "
        "loadout in this bundle; if this now finds one, the ramp's "
        "combat-blocked construction is stale and must be revised")


def test_l10_gearcrafting_gap_combat_blocked_retargets_not_char_grind() -> None:
    """The ramp: losing the feather closure's only dropper does NOT make
    the planner thrash GrindCharacterXP against an unwinnable monster — it
    re-targets to a still-reachable candidate that needs no combat at all.
    The GUARANTEE (never GrindCharacterXP against the unwinnable) is the
    criterion; the specific re-target is pinned to the ACTUAL observed value.

    RE-DERIVED 2026-07-08 (Task-3 pursuit_value bug-fix landing): under
    combat-dominant `pursuit_value` the structural gather `wooden_shield`
    (shield_slot, gathered from ash_wood via ash_tree — no combat) now
    outranks the utility-potion branch, so the re-target shifted from
    `GatherMaterials(sunflower)`/`small_health_potion` to
    `GatherMaterials(ash_wood)`/`wooden_shield`. Still a plannable,
    combat-free gather — the GUARANTEE (not GrindCharacterXP) is unchanged."""
    report = _run(CRITERION_1_RAMP)
    # GUARANTEE: re-target to a reachable non-combat goal, never XP-thrash.
    assert not isinstance(report.selected_goal, GrindCharacterXPGoal), (
        repr(report.selected_goal), report.plan)
    assert repr(report.selected_goal) == "GatherMaterials(ash_wood, {ash_wood:10})"
    assert [repr(a) for a in report.plan] == ["Gather(ash_tree)"]
    assert report.decision.chosen_root == ObtainItem(
        code="wooden_shield", quantity=1, slot="shield_slot")


def test_l10_gearcrafting_gap_combat_blocked_search_bounded() -> None:
    assert_search_bounded(_run(CRITERION_1_RAMP), CRITERION_1_RAMP)


# --- Criterion 2: never deadlock on skilling/crafting once the build is
# band-adequate — the trunk (char-level grind, or Wait when no monster in
# the level window is winnable) must win instead. ---------------------------

def test_l20_dual_utility_chosen_root_is_char_level_when_winnable() -> None:
    """l20_dual_utility is band-adequate (no structural upgrade) with a
    winnable monster (highwayman) in reach: the REAL `_tree_band_adequate`-
    wired decision (not the bare decide_tree default) must pick the
    char-level trunk, and the arbiter must plan a combat grind against it —
    never a skill/craft goal.

    FIXTURE RE-FIXED-POINT 2026-07-08 (Task-3 pursuit_value): the scenario's
    helmet_slot/body_armor_slot were re-equipped to the combat-dominant
    pursuit_value argmax (hard_leather_helmet / mushmush_jacket) — the old
    efficiency picks (wolf_ears +50 wisdom, adventurer_vest) that flat
    equip_value over-ranked were genuine COMBAT upgrades under pursuit_value,
    so the band read inadequate and the tree wanted the helmet. Restoring the
    true combat fixed point makes the band genuinely adequate again, so this
    criterion-2 pin (grind XP when full-build + winnable) holds with its
    ORIGINAL assertions (see scenario.py's l20_dual_utility re-fixed-point
    comment)."""
    report = _run(CRITERION_2_WINNABLE)
    assert report.decision.chosen_root == ReachCharLevel(level=30)
    assert isinstance(report.selected_goal, GrindCharacterXPGoal), (
        repr(report.selected_goal), report.plan)
    assert repr(report.selected_goal) == "GrindCharacterXP(highwayman)"
    assert [repr(a) for a in report.plan] == ["Fight(highwayman)"]


def test_l20_dual_utility_search_bounded() -> None:
    assert_search_bounded(_run(CRITERION_2_WINNABLE), CRITERION_2_WINNABLE)


def test_l48_band_adequate_chosen_root_is_wait_when_no_winnable_monster() -> None:
    """l48_band_adequate is band-adequate (no structural/utility upgrade)
    but NO monster in this bundle's L47-50 fight window is winnable against
    a full non-event mithril loadout (the documented event-gear wall —
    project_l50_unconditional_descent) — `_tree_band_adequate()` reads
    False (its winnable-monster leg fails), yet decide_tree's XP branch
    still wins on `gear_target_exists is False` alone, and the arbiter's
    last resort is Wait, documented, NOT a skill/craft goal. Reuses the
    band-liveness net's own scenario per the task brief ("reuse ...
    l48_band_adequate") — re-pinned here as the criterion-2 walled-off
    witness."""
    player, _gd = _player(CRITERION_2_WALLED)
    assert player._pick_winnable_monster() is None, (
        "no L47-50 window monster should be winnable against this "
        "non-event loadout in this bundle; if this now finds one, the "
        "L50-difficulty-wall finding is stale and must be revised")
    assert player._tree_band_adequate() is False
    report = player.plan_from_state()
    assert isinstance(report.selected_goal, WaitGoal), (
        repr(report.selected_goal), report.plan)
    assert repr(report.selected_goal) == "Wait"
    assert report.plan, (repr(report.selected_goal), report.plan)
    assert report.decision.chosen_root == ReachCharLevel(level=50)


def test_l48_band_adequate_search_bounded() -> None:
    # The walled scenario provably has nothing to try (event/raid-only L47-50
    # window); both poles are asserted in test_l48_raid_pair.
    assert_search_bounded(_run(CRITERION_2_WALLED), CRITERION_2_WALLED,
                          expect_no_work=True)


def test_l12_gearcrafting_gap_grey_farm_no_deadlock() -> None:
    """GAP-9 regression: at L12 the feather leaf's dropper (chicken) is GREY,
    so iron_boots' feather must be grey-farmed. The old lowest-consumer policy
    suppressed it (evaluated against unrelated apprentice_gloves) -> deadlock
    to GrindCharacterXP. Pins the FIXED behavior: pursue iron_boots via the
    feather grey-farm, never GrindCharacterXP."""
    report = _run("l12_gearcrafting_gap")
    assert repr(report.decision.chosen_root).startswith("ObtainItem(code='iron_boots'"), \
        report.decision.chosen_root
    goal = repr(report.selected_goal)
    assert "GrindCharacterXP" not in goal, goal  # the criterion-1 guarantee
    assert goal.startswith("GatherMaterials(feather"), goal
    assert report.plan and "Fight(chicken)" in repr(report.plan[0]), report.plan
    assert_search_bounded(report, "l12_gearcrafting_gap")
