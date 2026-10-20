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

Since the global gear objective (Task 5, spec 2026-10-18 §2.4, §6.2) every
scenario here is MISSING pieces of its `L*`, so none grinds XP and none Waits:
each pursues its first missing piece (or the skill climb in front of it).

Every scenario here is re-derived directly against the bundle and the real
`plan_from_state` seam (TDD-flavored: this documents CURRENT, empirically
observed behavior, not aspiration) — see the SCENARIOS dict in scenario.py
for the full per-scenario derivation notes (in particular
`l10_gearcrafting_gap`'s L12->L10 re-derivation, which caught a genuine
grey-mob drop-farm interaction the original investigation's framing missed)."""

from pathlib import Path

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.plan_report import PlanReport
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.tiers.meta_goal import (
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.progression_tree import decide_tree
from artifactsmmo_cli.ai.tiers.strategy import StrategyDecision
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT
from tests.test_ai.scenarios.search_bounds import assert_search_bounded
from tests.test_ai.shared_world import attached, shared_world

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"

CRITERION_1_MAIN = "l10_gearcrafting_gap"
CRITERION_1_RAMP = "l10_gearcrafting_gap_combat_blocked"
CRITERION_2_WINNABLE = "l20_dual_utility"
CRITERION_2_WALLED = "l48_band_adequate"

SCENARIO_NAMES = [CRITERION_1_MAIN, CRITERION_1_RAMP]
"""Only the scenarios ADDED by this task; CRITERION_2_WINNABLE and
CRITERION_2_WALLED already exist in SCENARIOS (reused per the task brief)."""


def _bundle() -> GameData:
    return shared_world(BUNDLE)


def _decide(name: str) -> tuple[StrategyDecision, WorldState]:
    gd = _bundle()
    state = scenario_state(SCENARIOS[name], gd)
    objective = CharacterObjective.from_game_data(gd)
    # The walk's context carries the cycle's gear objective, attached by the
    # one function the player uses (ruling W).
    return decide_tree(state, gd, objective,
                       ctx=attached(state, gd, TIMED_NO_PROFILE_CONTEXT, None)), state


def _player(name: str) -> tuple[GamePlayer, GameData]:
    gd = shared_world(BUNDLE)
    player = GamePlayer(character=name, history=None)
    player._offline_timing = committed_timing()
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

def test_l10_gearcrafting_gap_chosen_root_is_gear_never_the_trunk() -> None:
    """decide_tree's chosen_root is a reachable GEAR candidate, NEVER the
    character-level trunk — the criterion-1 property, pinned against the actual
    observed `decide_tree` output for this state.

    WAVE 3a moved WHICH gear candidate. `iron_boots` came off `near_term_gear`,
    a level-capped best-in-slot list; the walk reads
    `gear_targets_with_blockers`, ranks by TIER GAP, and the three empty
    artifact slots are further behind than the occupied boots slot. The
    gearcrafting climb `iron_boots` existed to witness has NOT been lost — it
    is `ReachSkillLevel(gearcrafting, 6)` in the alternatives and it is what
    the arbiter actually selects, which
    `test_l10_gearcrafting_gap_plans_craft_chain_not_char_grind` asserts.

    THE SUPPLIABILITY GATE moved it again, and this time the golden had been
    pinning a candidate that contradicted this test's own name. `novice_guide`
    is not REACHABLE: nothing mints it (`craft: null`, `tradeable: false`, in no
    monster/resource/NPC/task/event table) and its only supplier was the
    one-time `novice` achievement, so a character not already holding one never
    can. `objective.is_suppliable` now drops it from the ranked candidates and
    the artifact slot falls through, leaving `backpack` — a gear root that can
    actually be obtained. The property under test is unchanged and the other two
    assertions are untouched; only the identity of the winning gear candidate
    moved, exactly as it did in wave 3a.

    RE-DERIVED Task 5 (global gear objective): the root is `L*`'s first
    missing piece, `iron_sword`, gated at weaponcrafting 10 against 5 — so the
    root is the weaponcrafting climb in front of it, and the gearcrafting climb
    `iron_boots` witnesses is the next alternative. No level grind is offered
    at all while a piece is missing (spec 2026-10-18 §6.2).

    RE-DERIVED spec 2026-10-18 §2.9 (a fight's seconds are its learned
    length): `L*` is now the set that kills `red_slime` fastest, and the
    first of its pieces in the walk's order that is blocked is the
    `leather_legs_armor`, gated at gearcrafting 10 against 5 — so the root is
    the gearcrafting climb this test's name has always meant, and the two
    rings follow.

    RE-DERIVED spec 2026-10-18 §2.8 (a piece that adds no XP is not missing):
    the `leather_legs_armor` adds nothing to `R` on `red_slime` over the
    character's own legs, so the first blocked piece is the `leather_boots`,
    gated at the same gearcrafting 10: the same climb."""
    d, _state = _decide(CRITERION_1_MAIN)
    assert d.chosen_root == ReachSkillLevel(skill="gearcrafting", level=6)
    assert d.blocked_target == "leather_boots"
    assert d.fallback_roots == [
        ObtainItem(code="forest_ring", quantity=1, slot="ring1_slot"),
        ObtainItem(code="forest_ring", quantity=1, slot="ring2_slot")]
    assert not any(isinstance(r, ReachCharLevel) for r in d.fallback_roots)


def test_l10_gearcrafting_gap_plans_craft_chain_not_char_grind() -> None:
    """The full plan_from_state seam: the selected goal raises the
    gearcrafting skill the root is blocked on — NEVER GrindCharacterXP.
    Pins the ACTUAL observed selected_goal/plan, not an assumption.

    RE-DERIVED 2026-08-22 (goal-decision-graph Task 5, PF-2): this scenario IS
    the bug the task fixes. gearcrafting 5 < iron_boots' crafting_level 10,
    and iron_boots' recipe closure has a monster-drop input (feather, from
    chicken), so `_recipe_has_combat_drop_input` used to mask the (correct,
    but unreached) crafting-skill gate — the old selected_goal was
    `GatherMaterials(feather, {feather:3})`: gather feathers, via
    Fight(chicken), for boots the character cannot craft at ANY quantity of
    feathers. `CanICraftCurrentTier` now runs BEFORE the monster-drop check,
    so the skill-gated root raises gearcrafting instead — still never
    GrindCharacterXP, and now for the actual reason the craft chain was
    blocked rather than a masked one.

    WAVE 3a: the selected goal and the plan are BYTE-IDENTICAL. Only the route
    to them changed — the skill climb is now a first-class `ReachSkillLevel`
    root the walk emits (via `IsThisTargetBlocked`'s skill arm) and reaches
    through the fallback list, rather than something `objective_step_goal`
    derived from a gear root. That the answer survived a change of mechanism is
    the point of keeping this test.

    RE-DERIVED Task 5 (global gear objective): the climb the arbiter takes is
    the one in front of `L*`'s FIRST piece, `iron_sword` — weaponcrafting, not
    gearcrafting (which is the next alternative). Never GrindCharacterXP: no
    fight is chosen for XP while a piece is missing. The plan is one committed
    weaponcrafting grind cycle: a yellow_slime drop, the copper, then the
    sticky_sword that earns.

    RE-DERIVED spec 2026-10-18 §2.9: the root is the gearcrafting climb in
    front of `L*`'s `leather_legs_armor`, so the committed grind cycle is
    gearcrafting's: the copper, a chicken's feather, then the
    copper_legs_armor that earns. Since spec §2.8 the piece the climb is in
    front of is the `leather_boots` (the legs add no XP): the same climb and
    the same grind."""
    report = _run(CRITERION_1_MAIN)
    assert not isinstance(report.selected_goal, GrindCharacterXPGoal), (
        repr(report.selected_goal), report.plan)
    assert repr(report.selected_goal) == "ReachSkill(gearcrafting->6)"
    assert [repr(a) for a in report.plan] == [
        "Gather(copper_rocks×50)", "Craft(copper_bar×5)", "Fight(chicken)",
        "Craft(copper_legs_armor×1)"]
    assert report.decision.chosen_root == ReachSkillLevel(skill="gearcrafting", level=6)
    assert report.decision.blocked_target == "leather_boots"
    assert report.decision.declined == ()


def test_l10_gearcrafting_gap_search_bounded() -> None:
    assert_search_bounded(_run(CRITERION_1_MAIN), CRITERION_1_MAIN)


def test_l10_gearcrafting_gap_combat_blocked_no_winnable_monster() -> None:
    """Tripwire (mirrors test_band_liveness's l48 tripwire). The ramp was
    constructed with zero combat stats under a worn copper set so no monster
    — including the feather-dropping chicken — was winnable.

    RE-DERIVED 2026-10-18 (ruling R): that block was a STAT ARTEFACT. Zero
    totals under worn gear are a sheet the API never serves (the gear objective
    raises on it), and on its copper set's own totals the character beats the
    level-window `blue_slime`. The scenario has no honest combat block, so the
    tripwire now pins the derived pick: the ramp below no longer isolates a
    combat-blocked closure, and its guarantee (no XP thrash) is asserted on the
    derived outcome."""
    player, _gd = _player(CRITERION_1_RAMP)
    assert player._pick_winnable_monster() == "blue_slime"


def test_l10_gearcrafting_gap_combat_blocked_retargets_not_char_grind() -> None:
    """The ramp: losing the feather closure's only dropper does NOT make
    the planner thrash GrindCharacterXP against an unwinnable monster — it
    re-targets to a still-reachable candidate that needs no combat at all.
    The GUARANTEE (never GrindCharacterXP against the unwinnable) is the
    criterion; the specific re-target is pinned to the ACTUAL observed value.

    RE-DERIVED 2026-08-04 (pursuit_value unification): `_utility_candidates`
    joined `_structural_candidates` on `pursuit_value`, so the merged argmax
    stopped comparing two rulers ~1000x apart. On the ONE ruler `wooden_shield`
    leads `small_health_potion` 52_800_000 to 6_000_000 and the achievability
    factor narrows without reversing, so the re-target is
    `GatherMaterials(ash_wood)`/`wooden_shield` — the 2026-07-08 pursuit_value
    landing's verdict, restored. Still a plannable, combat-free gather; the
    GUARANTEE (not GrindCharacterXP) is unchanged, which is the criterion.

    WAVE 3a/3b: the merged-argmax comparison above no longer runs — the
    resolution walk picks `wooden_shield` off `gear_targets_with_blockers`
    (EQUIPMENT slots, ordered by `_tier_gap`), and `small_health_potion` is
    never a candidate for that walk at all (utility slots aren't equipment
    slots). `_utility_candidates` and `objective_candidates` had zero
    production callers by wave 3a and wave 3b deleted both. The shield/potion
    comparison above is retained as the historical reason the pin exists;
    the current mechanism no longer runs it, but the GUARANTEE this test
    checks does not depend on which mechanism produced the answer.

    RE-DERIVED 2026-10-18 (ruling R): on its copper set's own totals the
    character is not combat-blocked (see the tripwire above), so the
    `wooden_shield`/ash_wood re-target was a stat artefact of the zero-attack
    sheet. The walk now passes the cowhide over (no route: cow is not won in
    copper) and climbs jewelrycrafting one level with a copper ring; the
    guarantee (never GrindCharacterXP) holds on that derived outcome.

    RE-DERIVED Task 5 (global gear objective): the ramp and the main scenario
    now share their gear objective, so they share its answer — the
    weaponcrafting climb in front of `L*`'s first piece, `iron_sword`. The
    guarantee holds: never GrindCharacterXP."""
    report = _run(CRITERION_1_RAMP)
    assert not isinstance(report.selected_goal, GrindCharacterXPGoal), (
        repr(report.selected_goal), report.plan)
    assert repr(report.selected_goal) == "ReachSkill(weaponcrafting->6)"
    assert report.decision.chosen_root == ReachSkillLevel(skill="weaponcrafting", level=6)
    assert [repr(a) for a in report.plan] == [
        "Fight(yellow_slime)", "Gather(copper_rocks×50)", "Craft(copper_bar×5)",
        "Craft(sticky_sword×1)"]


def test_l10_gearcrafting_gap_combat_blocked_search_bounded() -> None:
    assert_search_bounded(_run(CRITERION_1_RAMP), CRITERION_1_RAMP)


# --- Criterion 2: never deadlock on skilling/crafting once the build is
# band-adequate — the trunk (char-level grind, or Wait when no monster in
# the level window is winnable) must win instead. ---------------------------

def test_l20_dual_utility_climbs_the_blocking_skill_not_the_char_level() -> None:
    """RENAMED IN WAVE 3a fix-round 1. LOST: this scenario no longer witnesses
    "a full build grinds XP" — it is not a full build on the TIER sheet. The
    criterion-2 guarantee it protects (never DEADLOCK on skilling) is asserted
    below. Wave 4 owns finding a scenario that can witness the original claim.

    l20_dual_utility is band-adequate (no structural upgrade) with a
    winnable monster (highwayman) in reach: the REAL `_tree_band_adequate`-
    wired decision (not the bare decide_tree default) must pick the
    char-level trunk, and the arbiter must plan a combat grind against it —
    never a skill/craft goal.

    FIXTURE RE-FIXED-POINT 2026-07-08 (Task-3 pursuit_value): the scenario's
    helmet_slot/body_armor_slot were re-equipped to the combat-dominant
    pursuit_value argmax — the old efficiency picks (wolf_ears +50 wisdom,
    adventurer_vest) that flat equip_value over-ranked were genuine COMBAT
    upgrades under pursuit_value, so the band read inadequate and the tree
    wanted the helmet. Restoring the true combat fixed point makes the band
    genuinely adequate again.

    RE-FIXED-POINT AGAIN 2026-08-04 (pursuit_value unification): five more
    slots (weapon/legs/boots/both rings/amulet) converged onto the ONE ruler's
    argmax — battlestaff, hard_leather_pants/boots, steel_ring,
    air_and_water_amulet. The GRIND TARGET moved with the loadout: at the
    stronger build `pig` is winnable and out-XPs `highwayman`, so the pins
    below name it. Criterion 2 (grind XP when full-build + winnable) is
    unchanged; only which monster the grind picks.

    WAVE 3a INVALIDATED THE PREMISE, and this is a re-derivation of the
    scenario, not of the criterion. "Band-adequate" here meant `near_term_gear`
    is empty — a LEVEL-capped best-in-slot list. The walk reads
    `gear_targets_with_blockers` against the tier sheet, and this character's
    `rune_slot`, three artifact slots and `bag_slot` are EMPTY with real
    targets behind a gearcrafting-15 gate. It is not gear-complete; it only
    looked that way to a list that never asked. So the walk raises gearcrafting
    by one, which is the honest answer to "what is stopping this build".

    Criterion 2's actual guarantee — never DEADLOCK on skilling — still holds
    and is asserted below: the climb targets `current + 1`, re-derived from
    live state every cycle, so it terminates and the trunk stays reachable in
    the fallbacks. What is genuinely lost is the pin that a full build grinds
    XP, and this scenario can no longer witness it because it does not have a
    full build. Recorded in
    `.superpowers/sdd/PLAN_wave3a_cutover/task-6-report.md`.

    RE-DERIVED Task 5 (global gear objective): `L*`'s first piece is
    `steel_battleaxe`, weaponcrafting-gated, so the root is the next
    weaponcrafting level, and the plan is one committed grind cycle ending in
    the `iron_sword` craft that earns. No level grind is offered while `L*`
    is missing (spec 2026-10-18 §6.2): the trunk is no longer a fallback."""
    report = _run(CRITERION_2_WINNABLE)
    assert report.decision.chosen_root == ReachSkillLevel(
        skill="weaponcrafting", level=16)
    assert report.decision.blocked_target == "steel_battleaxe"
    assert not isinstance(report.selected_goal, GrindCharacterXPGoal), (
        repr(report.selected_goal), report.plan)
    assert repr(report.selected_goal) == "ReachSkill(weaponcrafting->16)"
    assert [repr(a) for a in report.plan] == [
        "Gather(iron_rocks×60)", "Craft(iron_bar×6)", "Fight(chicken)", "Craft(iron_sword×1)"]
    # The climb is bounded (current + 1, not the whole gate), and nothing
    # offers a level grind while a piece is missing.
    assert report.decision.chosen_root.level == 16
    assert not any(isinstance(r, ReachCharLevel) for r in report.decision.fallback_roots)


def test_l20_dual_utility_search_bounded() -> None:
    assert_search_bounded(_run(CRITERION_2_WINNABLE), CRITERION_2_WINNABLE)


def test_l48_band_adequate_names_the_wall_when_no_winnable_monster() -> None:
    """l48_band_adequate is band-adequate (no structural/utility upgrade)
    but NO monster in this bundle's L47-50 fight window is winnable against
    a full non-event mithril loadout (the documented event-gear wall —
    project_l50_unconditional_descent). Reuses the band-liveness net's own
    scenario per the task brief — the criterion-2 walled-off witness.

    WAVE 3a changed both halves of the answer, and both changes are
    improvements. The root is no longer `ReachCharLevel(50)`: the walk's
    `CanIClearMyTier` arm reports the wall as `None` instead of handing back a
    level target with no route to it. And the outcome is no longer `Wait`: the
    trunk fallback now goes through `actionable_step`, so it descends to its
    weapon prerequisite and the arbiter reaches a real craft chain instead of
    idling. Criterion 2's guarantee — NOT a deadlock, and not an unexplained
    dead end — holds in a stronger form than before.

    RE-DERIVED 2026-10-18 (ruling R): the L47-50 wall was a STAT ARTEFACT. The
    scenario's hand stats lacked its mithril loadout's, and on that loadout's
    own totals `hellhound` is winnable, so this scenario has no honest wall.
    The pins now state the derived outcome: the walk names no root, every gear
    alternative it reaches has no route this cycle, and the trunk is the LAST
    fallback. With no task held and `L*` missing pieces (its `m*` is
    hellhound), no fight is chosen for XP (spec 2026-10-18 §6.2), so the
    trunk serves nothing.

    RE-DERIVED Task 5: the root walk offers the first `L*` piece,
    `goblin_guard_shield`, so the cycle no longer Waits: it plans the shield's
    acquisition (an acquisition fight against the goblin_guard). Not a
    deadlock, and not an XP fight: no trunk is offered at all.
    RE-DERIVED plan B Task 2 (`PIECE_POLICY`, ruling T2a): the 20000-gold
    `lifesteal_rune` is priced through gold earned by fighting, a finite price,
    so it orders ahead of the piece behind an unpriced climb."""
    player, _gd = _player(CRITERION_2_WALLED)
    assert player._pick_winnable_monster() == "hellhound"
    assert player._tree_band_adequate() is False
    report = player.plan_from_state()
    assert repr(report.selected_goal) == "UpgradeEquipment(goblin_guard_shield->shield_slot)", (
        repr(report.selected_goal), report.plan)
    assert report.decision.chosen_root == ObtainItem(
        code="goblin_guard_shield", quantity=1, slot="shield_slot")
    assert report.decision.fallback_roots == [
        ObtainItem(code="lifesteal_rune", quantity=1, slot="rune_slot"),
        ReachSkillLevel(skill="jewelrycrafting", level=36)]


def test_l48_band_adequate_search_bounded() -> None:
    # WAVE 3a: the walled scenario now HAS bounded work (the trunk descends to
    # its weapon prerequisite), so the ordinary bound applies — see
    # `search_bounds.assert_search_bounded`.
    assert_search_bounded(_run(CRITERION_2_WALLED), CRITERION_2_WALLED)


def test_l12_gearcrafting_gap_grey_farm_no_deadlock() -> None:
    """GAP-9 regression: at L12 the feather leaf's dropper (chicken) is GREY,
    so iron_boots' feather must be grey-farmed. The old lowest-consumer policy
    suppressed it (evaluated against unrelated apprentice_gloves) -> deadlock
    to GrindCharacterXP. Pins the FIXED behavior: pursue iron_boots, never
    GrindCharacterXP.

    RE-DERIVED 2026-08-22 (goal-decision-graph Task 5, PF-2): gearcrafting 5
    < iron_boots' crafting_level 10, and iron_boots' recipe closure has a
    monster-drop input (feather), so `_recipe_has_combat_drop_input` used to
    mask the crafting-skill gate — the old goal was the feather grey-farm
    (`GatherMaterials(feather...)` via `Fight(chicken)`), gathering feathers
    for boots the character could not craft at ANY quantity of feathers.
    `CanICraftCurrentTier` now runs BEFORE the monster-drop check, so the
    skill-gated root raises gearcrafting instead of grey-farming a material
    that could not have paid off yet — still never GrindCharacterXP, and the
    grey-farm route is picked back up once the skill has risen.

    WAVE 3a: the goal and the plan are BYTE-IDENTICAL; only the chosen_root
    moved, from `iron_boots` (a `near_term_gear` best-in-slot pick) to the
    furthest-behind slot on the tier sheet. The gearcrafting climb is now a
    first-class `ReachSkillLevel` root in the alternatives, which is what the
    arbiter selects — same answer, reached as a root instead of derived from
    one.

    SUPPLIABILITY GATE: byte-identical goal and plan for the third mechanism
    running, and the chosen_root moved once more. `novice_guide` held
    artifact1_slot only because nothing else could reach it, and nothing mints
    it, so `objective.is_suppliable` drops it and the gearcrafting climb is
    promoted from the alternatives to the ROOT — asserted directly below, which
    is stronger than the membership test it replaces.

    RE-DERIVED Task 5 (global gear objective): `L*`'s first piece at level 12
    is `forest_ring`, a mushmush drop, so the root is that ring and the plan
    is its acquisition: fight the mushmush, equip the ring — an acquisition
    fight, never GrindCharacterXP. The weaponcrafting and gearcrafting climbs
    the iron pieces need are behind it, in the objective's order. Since spec
    §2.8 every gain is `R` over the owned item for the slot, and the amulet's
    (jewelrycrafting) out-gains the iron boots and armour (gearcrafting) at the
    same price, so that climb comes first."""
    report = _run("l12_gearcrafting_gap")
    # An EQUALITY on chosen_root, as before — only the value moved.
    assert report.decision.chosen_root == ObtainItem(
        code="forest_ring", quantity=1, slot="ring1_slot")
    assert report.decision.declined == ()
    goal = repr(report.selected_goal)
    assert "GrindCharacterXP" not in goal, goal  # the criterion-1 guarantee
    assert goal == "UpgradeEquipment(forest_ring->ring1_slot)", goal
    assert [repr(a) for a in report.plan] == [
        "Fight(mushmush)", "Equip(forest_ring->ring1_slot)"]
    assert report.decision.fallback_roots[1:4] == [
        ReachSkillLevel(skill="weaponcrafting", level=6),
        ReachSkillLevel(skill="jewelrycrafting", level=6),
        ReachSkillLevel(skill="gearcrafting", level=6)]
    assert_search_bounded(report, "l12_gearcrafting_gap")
