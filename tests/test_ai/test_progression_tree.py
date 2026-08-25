"""decide_tree(): the wave-3a RESOLUTION walk over the Phase-1 scenarios.

Drives the module DIRECTLY (not wired into StrategyEngine).

WAVE 3a MOVED EVERY SCENARIO PIN IN THIS FILE, and fix-round 1 moved four of
them again. Two separate causes, and the first report conflated them:

1. The walk reads `objective.gear_targets_with_blockers`, which gears for
   `tier_progress.gear_target_tier` — the rung being CLEARED, capped by
   character level. The retired ranking read `near_term_gear`, capped by LEVEL
   only and blind to winnability. So a character that has not cleared its
   level's band now gears LOWER than it used to. That is real and it bites
   live, not only here.

2. Under the ORIGINAL stats-OFF fixtures nothing cleared any rung at all
   (`predict_win` said a level-12 character in a full copper set loses to a
   60-hp chicken), so `gear_target_tier` pinned to 1 and the four GOLDEN
   scenarios collapsed onto one identical answer. Fix-round 1 turned
   `derive_combat_stats` ON for `l1_fresh`, `l10_weapon_upgrade`,
   `l10_copper_adequate` and `l12_taskgated_bag` — see `scenario.py`'s module
   docstring. Their tiers are now 1/5/5/5 and their pins are re-derived
   against a world the API could actually produce.

Scenarios that still run stats-OFF (the L48 pair, the gearcrafting ramps) keep
tier 1 for cause 2 and say so where it matters. Live data behaves like neither
extreme — `plan Robby` at L30 targets L30-tier gear — which is recorded in
`.superpowers/sdd/PLAN_wave3a_cutover/task-6-report.md`."""

import json
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.item_catalog import ItemCatalog
from artifactsmmo_cli.ai.scenario import SCENARIOS, ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.tiers.meta_goal import (
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.progression_tree import (
    _structural_candidates,
    decide_tree,
    has_structural_upgrade,
)
from artifactsmmo_cli.ai.weapon_winnability import marginal_weapon_winnability
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

BUNDLE = (Path(__file__).parent / "scenarios" / "fixtures"
          / "gamedata_bundle.json")


def _bundle() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def _decide(name: str):
    gd = _bundle()
    state = scenario_state(SCENARIOS[name], gd)
    return decide_tree(state, gd, CharacterObjective.from_game_data(gd)), state


def test_weapon_upgrade_scenario_picks_the_skill_gating_its_gear():
    """RENAMED in wave 3a fix-round 1: this is no longer a "gear branch" pin,
    because the walk's answer is a SKILL CLIMB. The weapon-slot target at
    gear-target tier 5 is skill-gated on jewelrycrafting, and
    `IsThisTargetBlocked`'s skill arm routes to the skill rather than to an item
    the character cannot craft. Still gear-DRIVEN — the skill is named because
    a gear slot wants it — which is what this test is really for."""
    d, _ = _decide("l10_weapon_upgrade")
    assert d.chosen_root == ReachSkillLevel(skill="jewelrycrafting", level=2)


def test_low_hp_scenario_still_produces_a_decision():
    """Guards preempt at the ARBITER, not here — the tree always answers."""
    d, _ = _decide("l3_low_hp")
    assert d.chosen_root is not None and d.chosen_step is not None


def test_xp_branch_when_no_gear_candidates():
    """A maximally-geared synthetic state falls to the trunk."""
    d, _state = _decide("l10_copper_adequate")
    # Whichever branch fires, the DECISION is total and the trunk is the
    # milestone: for the xp case, root == step == ReachCharLevel(20).
    if isinstance(d.chosen_root, ReachCharLevel):
        assert d.chosen_root.level == 20
        assert d.chosen_step == d.chosen_root


def test_trunk_milestone_matches_core():
    """The trunk still rides the ranking, and still at `milestone_pure`. Its
    `category` moved from the bare `"char_level"` to `"alternative · char_level"`
    because post-flip the column says how a row got there: the chosen row
    carries the resolution TRAIL, every other row is an alternative labelled by
    kind (`_resolution_rows`)."""
    d, _state = _decide("l1_fresh")
    trunk_rows = [r for r in d.ranking if r.category.endswith("char_level")]
    assert trunk_rows and "10" in trunk_rows[0].root_repr
    assert trunk_rows[0].category == "alternative · char_level"


def test_ranking_renders_the_descent():
    d, _ = _decide("l10_weapon_upgrade")
    assert d.ranking, "descent must be rendered for display parity"
    assert all(r.score >= 0 for r in d.ranking)


def test_fallbacks_offer_the_other_branch():
    """Asserted on `fallback_roots`, not `fallback_steps`. The trunk sits
    behind every GEAR fallback — the 2026-07-27 trunk-after-gear ruling
    survives the flip verbatim — but its STEP is no longer the trunk itself:
    this character is not `combat_capable`, so `prerequisites(ReachCharLevel)`
    emits a weapon and `actionable_step` descends to
    `ObtainItem(mithril_ore, 10)`. Matching on the step therefore says nothing
    about whether the trunk is reachable, which is the property this test is
    for.

    The trunk is no longer the LAST entry: the restored standalone skill roots
    (`decisions/root._orphan_skill_roots`) are offered behind it. The property
    is stated as a relation now — every gear root ahead of the trunk, every
    orphan skill root behind it — which is what `[-1]` was standing in for."""
    d, _ = _decide("l10_weapon_upgrade")
    assert any(isinstance(r, ReachCharLevel) for r in d.fallback_roots), (
        "gear decision must carry the xp trunk as an arbiter fallback")
    trunk = d.fallback_roots.index(ReachCharLevel(level=20))
    assert all(isinstance(r, ObtainItem | ReachSkillLevel)
               for r in d.fallback_roots[:trunk])
    assert all(isinstance(r, ReachSkillLevel)
               for r in d.fallback_roots[trunk + 1:])
    assert d.fallback_roots[trunk + 1:], "the orphan skill roots must be offered"


_ORPHAN_ROWS_AT_FLOOR = [
    "ReachSkillLevel(skill='cooking', level=2)",
    "ReachSkillLevel(skill='fishing', level=2)",
    "ReachSkillLevel(skill='mining', level=2)",
    "ReachSkillLevel(skill='woodcutting', level=2)",
]
"""The tail every pin below grew: the restored standalone skill roots
(`decisions/root._orphan_skill_roots`) — the skills NO gear target can name,
because nothing they craft is equippable. They are appended after the trunk, so
they extend each pinned list rather than reordering it, and the levels are
`current + 1`; this constant is the all-at-the-floor case and the scenarios
whose gather skills are higher spell their own tail out.

`ef67c1d6` deleted the standalone `ReachSkillLevel` emitters on the premise
"skills are pure prerequisites now"; cooking is the counter-example the epic
measured (33,840 live XP, 99.6% of it a `RestoreHP` side effect)."""


# --- Per-scenario behavior pins ---------------------------------------------
#
# Exact branch/target recorded under the committed gamedata_bundle.json
# fixture, derived from the binding semantics (progression_tree.py's own
# rules), NOT from the Lean model — this module is value-semantics only.
# These are the tree's behavior pins for Phase 3's shadow wiring: the live
# arbiter's choice gets diffed against these, catching any accidental drift
# in near_term_gear/utility_potion_targets/equip_value composition.

class TestPerScenarioPins:
    def test_l1_fresh_pins_the_blocking_material_of_the_weapon_slot(self):
        """WAVE 3a. Six slots are behind the rung-1 sheet; `weapon_slot` is the
        furthest behind (empty, target `wooden_staff`), and `wooden_staff` is
        material-gated on `wooden_stick`, so `IsThisTargetBlocked` routes to
        the MATERIAL at its recipe quantity rather than to the staff. The old
        pin (`copper_dagger`, the argmax of a value ranking) is gone with the
        ranking.

        Row 0 is now the CHOSEN row, not the trunk: `_resolution_rows` puts the
        resolved root first and its `category` is the trail that produced it.
        The trunk is last.

        FIX-ROUND 1: with real combat stats this scenario clears rung 1, so the
        copper set the ORIGINAL pin named is back on the sheet — the five
        alternatives below are copper_helmet / copper_boots / two copper_rings /
        wooden_shield. The head is unchanged."""
        d, _ = _decide("l1_fresh")
        assert d.chosen_root == ObtainItem(code="wooden_stick", quantity=1)
        assert d.chosen_step == d.chosen_root
        assert [r.root_repr for r in d.ranking] == [
            "ObtainItem(code='wooden_stick', quantity=1)",
            "ObtainItem(code='wooden_shield', quantity=1, slot='shield_slot')",
            "ObtainItem(code='copper_helmet', quantity=1, slot='helmet_slot')",
            "ObtainItem(code='copper_boots', quantity=1, slot='boots_slot')",
            "ObtainItem(code='copper_ring', quantity=1, slot='ring1_slot')",
            "ObtainItem(code='copper_ring', quantity=1, slot='ring2_slot')",
            "ReachCharLevel(level=10)",
            *_ORPHAN_ROWS_AT_FLOOR]
        assert d.ranking[0].category == (
            "IsMyGearBehindMyTier → WhichSlotIsFurthestBehind → IsThisTargetBlocked")

    def test_l8_overstocked_pins_gear_branch(self):
        """Level 8, full copper set (no shield in _COPPER_SET) + empty
        utility slot: near_term_gear finds nothing above the copper set for
        the equipped slots, but shield_slot is empty (wooden_shield) and
        utility1_slot is unprovisioned (small_health_potion).

        RE-DERIVED 2026-08-04 (pursuit_value unification). The merged argmax
        finally compares ONE ruler: `_utility_candidates` joined
        `_structural_candidates` on `pursuit_value`, closing the last
        cross-ruler magnitude comparison in the tree (it scored potions on
        `equip_value`, ~1000x smaller than its competitor).

        The shield wins, restoring the 2026-07-08 "combat/gear pursuit outranks
        potion-stocking" ruling. On the ONE ruler the gap is 52_800_000 to
        6_000_000 — the shield's four 2% resistances are worth 8.8x the potion's
        30 HP pool once both are priced as damage swing per turn — so the
        ACHIEVABILITY factor (shield 905/1534 for 10 gathered ash_wood, potion 1
        for craftable-now) narrows it to 31.2M vs 6.0M without reversing it. The
        brief potion win under the previous commit came from the two branches
        riding rulers ~1000x apart, not from a judgement about potions.

        WAVE 3a: the shield still wins, and the count is still 3, but neither
        for the recorded reason. The shield wins because it is the
        furthest-behind slot on the rung-1 sheet — an EMPTY slot, scored from
        rung 0 by `_tier_gap`. And the third row is NOT the potion: potions
        were `_utility_candidates`, part of the deleted candidate pass, and are
        not gear targets at all. The rows are shield, the weapon slot's
        blocking material, and the trunk. This test passed under both regimes
        for different reasons, so the rows are now spelled out rather than
        counted."""
        d, _ = _decide("l8_overstocked")
        assert d.chosen_root == ObtainItem(code="wooden_shield", quantity=1,
                                           slot="shield_slot")
        assert d.chosen_step == ObtainItem(code="ash_wood", quantity=10)
        assert [r.root_repr for r in d.ranking] == [
            "ObtainItem(code='wooden_shield', quantity=1, slot='shield_slot')",
            "ObtainItem(code='wooden_stick', quantity=1)",
            "ReachCharLevel(level=10)",
            "ReachSkillLevel(skill='cooking', level=2)",
            "ReachSkillLevel(skill='fishing', level=2)",
            "ReachSkillLevel(skill='mining', level=6)",
            "ReachSkillLevel(skill='woodcutting', level=6)"]

    def test_l10_copper_adequate_pins_gear_branch_not_xp(self):
        """The scenario NAME says 'adequate', but adequacy here is Phase-2's
        crude 2-arg definition (candidates == []) — shield_slot is still
        empty, so a structural candidate (wooden_shield) exists and wins.
        This is NOT the XP-branch case (that needs a fully-saturated synthetic
        state — see TestSyntheticBranches).

        RE-DERIVED 2026-08-04 (pursuit_value unification) — same cause as
        `test_l8_overstocked_pins_gear_branch`: both branches now rank on the
        ONE ruler, where the shield leads 52_800_000 to 6_000_000 and
        achievability narrows without reversing.

        WAVE 3a: row 0 is the CHOSEN row now, not the trunk — `_resolution_rows`
        leads with the resolved root and the trunk goes last.

        FIX-ROUND 1: with real combat stats the tier is 5, not 1, and the
        furthest-behind slot is skill-gated — the walk names the jewelrycrafting
        climb. The scenario is STILL not "adequate" in the tier model's sense,
        which is the point the original docstring was making, just with a
        different witness. The rows are spelled out rather than counted: the
        old `len(...) == 3` passed under both regimes over different rows."""
        d, _ = _decide("l10_copper_adequate")
        assert d.chosen_root == ReachSkillLevel(skill="jewelrycrafting", level=2)
        assert [r.root_repr for r in d.ranking] == [
            "ReachSkillLevel(skill='jewelrycrafting', level=2)",
            "ObtainItem(code='cowhide', quantity=5)",
            "ObtainItem(code='water_bow', quantity=1, slot='weapon_slot')",
            "ObtainItem(code='wooden_shield', quantity=1, slot='shield_slot')",
            "ReachCharLevel(level=20)",
            "ReachSkillLevel(skill='cooking', level=2)",
            "ReachSkillLevel(skill='fishing', level=2)",
            "ReachSkillLevel(skill='mining', level=11)",
            "ReachSkillLevel(skill='woodcutting', level=11)"]

    def test_l10_weapon_upgrade_pins_the_skill_gating_the_weapon(self):
        """WAVE 3a + FIX-ROUND 1. `copper_dagger` is not on the target sheet:
        the walk gears for `gear_target_tier` (5 here) rather than for
        `near_term_gear`'s level cap, and the weapon-slot target at that tier is
        skill-gated on jewelrycrafting. `IsThisTargetBlocked`'s skill arm routes
        to the skill, at `current + 1`, not to the item.

        The SECOND skill climb (gearcrafting) sits behind it, which is what
        makes this scenario distinguishable from `l12_taskgated_bag` in the
        ranking even though the two share a head.

        Trunk LAST (2026-07-27) survives the flip: `resolve_root` appends the
        trunk after every sibling."""
        d, _ = _decide("l10_weapon_upgrade")
        assert d.chosen_root == ReachSkillLevel(skill="jewelrycrafting", level=2)
        assert d.chosen_step == d.chosen_root
        assert [r.root_repr for r in d.ranking] == [
            "ReachSkillLevel(skill='jewelrycrafting', level=2)",
            "ReachSkillLevel(skill='gearcrafting', level=2)",
            "ObtainItem(code='blue_slimeball', quantity=2)",
            "ObtainItem(code='wooden_shield', quantity=1, slot='shield_slot')",
            "ReachCharLevel(level=20)",
            "ReachSkillLevel(skill='cooking', level=2)",
            "ReachSkillLevel(skill='fishing', level=2)",
            "ReachSkillLevel(skill='woodcutting', level=2)",
            "ReachSkillLevel(skill='mining', level=11)"]
        # The trunk is no longer last — the orphan skill roots sit behind it —
        # but it is still ahead of every one of them, which is the ordering
        # 2026-07-27 bought and the ordering `l48_band_adequate` re-proved.
        trunk = d.fallback_roots.index(ReachCharLevel(level=20))
        assert all(isinstance(root, ReachSkillLevel)
                   for root in d.fallback_roots[trunk + 1:])

    def test_l3_low_hp_pins_weapon_branch(self):
        """Same target sheet as l1_fresh (the gear-target tier is 1 for both,
        and raising state.level to 3 admits nothing new) -> the tree still
        answers with the GEAR branch and the same root. The survival guard that
        would preempt this at the arbiter has no seam in decide_tree itself
        (semantics: guards preempt at the ARBITER, not here)."""
        d, _ = _decide("l3_low_hp")
        assert d.chosen_root == ObtainItem(code="wooden_stick", quantity=1)
        assert d.chosen_step == d.chosen_root
        # 7 gear/trunk rows + the four restored orphan skill roots.
        assert len(d.ranking) == 11
        assert [r.root_repr for r in d.ranking[-4:]] == _ORPHAN_ROWS_AT_FLOOR

    def test_l12_taskgated_bag_pins_iron_boots_branch(self):
        """RE-DERIVED (GAP-1 fix, 2026-07-07): this scenario has zero attack
        (no derive_combat_stats) so cow AND chicken are both unwinnable here
        — before the fix, is_attainable_now's recipe walk had no
        held/banked-stock arm, so the banked cowhide(5)/feather(2) counted
        for nothing and every cowhide/feather-consuming recipe
        (iron_armor, iron_legs_armor, iron_dagger, iron_boots, satchel) read
        unattainable, leaving only small_health_potion + wooden_shield as
        gear candidates (ranking len 3: char_level + those two). Now that
        held/banked stock credits attainability, all five of those recipes
        open (iron_boots's full recipe, iron_bar via gatherable iron_ore +
        feather via the banked 2 — boolean stock credit, not gated on the
        recipe's higher qty-3 demand).

        RE-DERIVED 2026-08-04 (pursuit_value unification): the WEAPON wins now.
        `iron_sword` scores 702_000_000 against `iron_boots`' 71_999_993 because
        `pursuit_value`'s combat term is the ruler's own, and the ruler prices a
        weapon as damage DEALT per turn while armor is damage swung. That is not
        an accident of scale here: this scenario has NO attack at all
        (`derive_combat_stats` off), and the weapon-slot winnability guard —
        which suppresses any weapon that unlocks nothing — measures
        `marginal_weapon_winnability(iron_sword) == 7`, i.e. seven monsters the
        character cannot beat bare-handed and could beat armed. A character who
        cannot win a fight should buy a sword before boots.

        (The retired flat `combat_raw` scored the sword's 24 attack against the
        boots' resistance + hp 1:1, which is why the boots used to lead.)

        WAVE 3a + FIX-ROUND 1: iron gear is off the sheet. The walk gears for
        `gear_target_tier`, which is 5 here — the character is not asked to gear
        for a rung whose band it cannot clear, which is the whole point of
        `gear_target_tier` (its docstring's Robby-at-30 case). The head is the
        jewelrycrafting climb, and the WEAPONCRAFTING climb the pre-flip golden
        witnessed is still on the sheet, one row down: the skill-grind route is
        not lost here, only demoted.

        The satchel assertion is kept verbatim — the region gate is unrelated
        to the flip and must keep holding. Note `jasper_crystal` IS a row: that
        is the material, reachable in principle; the satchel ITEM stays absent
        because its trader does not."""
        d, _ = _decide("l12_taskgated_bag")
        assert d.chosen_root == ReachSkillLevel(skill="jewelrycrafting", level=2)
        assert [r.root_repr for r in d.ranking] == [
            "ReachSkillLevel(skill='jewelrycrafting', level=2)",
            "ObtainItem(code='jasper_crystal', quantity=1)",
            "ReachSkillLevel(skill='weaponcrafting', level=2)",
            "ObtainItem(code='wooden_shield', quantity=1, slot='shield_slot')",
            "ReachCharLevel(level=20)",
            *_ORPHAN_ROWS_AT_FLOOR]
        assert not any("satchel" in r.root_repr for r in d.ranking), \
            "satchel needs jasper_crystal from an unreachable trader"


# --- band_adequate parameter (Phase-3 Task-1) -------------------------------
#
# DELETED IN WAVE 3a. `band_adequate` was the input to `branch_pick_pure`, the
# boolean gear/xp pivot. The resolution walk has no pivot to feed: the branch is
# whatever `IsMyGearBehindMyTier` resolves to. The three tests that lived here
# asserted the parameter's effect on `decide_tree` and had no other subject, so
# they go with it rather than being re-pointed at something they never tested.
# `branch_pick_pure` itself keeps its own unit tests in
# tests/test_ai/test_progression_tree_core.py; it is deleted in wave 3b.


# --- step_servable demotion (Phase-4b Task-1: THE FLIP) ---------------------
#
# The legacy decide()'s servable filter must survive the cutover: an
# unservable chosen (root, step) falls through the fallback pairs IN ORDER to
# the first servable pair; demoted pairs stay in the fallback lists after the
# promoted one; all-unservable keeps the original choice (the arbiter's
# doomed-memo handles it, as today).

class TestServabilityDemotion:
    """l10_weapon_upgrade pins (see TestPerScenarioPins): chosen =
    ReachSkillLevel(jewelrycrafting, 2); alternatives = [
    ReachSkillLevel(gearcrafting, 2), ObtainItem(blue_slimeball, 2),
    ObtainItem(wooden_shield, shield_slot), ReachCharLevel(20)].

    TRUNK-LAST correction 2026-07-27 (live trace): the trunk used to sit at
    index 0, so ONE unservable gear step promoted the XP trunk over servable
    gear candidates sitting behind it — Robby ran 9 of 15 cycles on
    ReachCharLevel with 7 structural candidates live and the branch verdict
    saying GEAR. That ruling is unchanged by wave 3a: `resolve_root` appends
    the trunk AFTER every sibling, so this class keeps testing the same
    property against the walk's own fallback order, and a mutation anchor
    (`root: the xp trunk is prepended…`) now guards it directly.

    FIX-ROUND 1 re-derivation: with real combat stats this scenario's board is
    FOUR alternatives behind the head instead of one, so the in-order walk
    tests below have real room to discriminate — the previous two-candidate
    board could not tell "takes the next servable pair" from "takes the last"."""

    SKILL_JEWEL = ReachSkillLevel(skill="jewelrycrafting", level=2)
    SKILL_GEAR = ReachSkillLevel(skill="gearcrafting", level=2)
    SLIME = ObtainItem(code="blue_slimeball", quantity=2)
    SHIELD = ObtainItem(code="wooden_shield", quantity=1, slot="shield_slot")
    SHIELD_STEP = ObtainItem(code="ash_wood", quantity=10)
    TRUNK = ReachCharLevel(level=20)
    ORPHANS = [ReachSkillLevel(skill="cooking", level=2),
               ReachSkillLevel(skill="fishing", level=2),
               ReachSkillLevel(skill="woodcutting", level=2),
               ReachSkillLevel(skill="mining", level=11)]
    """The restored standalone skill roots for this character
    (`decisions/root._orphan_skill_roots`), offered BEHIND the trunk. They
    extend every list below without reordering it, and they widen the
    demotion walk's reach: a fully blocked gear branch now has somewhere past
    the trunk to go. Order is `skill level - character level`, largest gap
    first — mining is at 10 here and the other three at the floor."""

    def _decide_with(self, servable):
        gd = _bundle()
        state = scenario_state(SCENARIOS["l10_weapon_upgrade"], gd)
        return decide_tree(state, gd, CharacterObjective.from_game_data(gd),
                           step_servable=servable)

    def test_servable_chosen_is_untouched(self):
        d = self._decide_with(lambda root, step: True)
        assert d.chosen_root == self.SKILL_JEWEL
        assert d.fallback_roots == [self.SKILL_GEAR, self.SLIME, self.SHIELD,
                                    self.TRUNK, *self.ORPHANS]

    def test_unservable_chosen_promotes_the_next_gear_candidate_not_the_trunk(self):
        """THE 2026-07-27 REGRESSION. One unservable gear step must not
        abandon the gear branch: the promotion takes the next servable
        candidate, and the trunk stays behind it."""
        d = self._decide_with(lambda root, step: root != self.SKILL_JEWEL)
        assert d.chosen_root == self.SKILL_GEAR
        assert d.chosen_root != self.TRUNK
        # The demoted pair survives in the fallbacks, ahead of the rest —
        # original priority order minus the promotion.
        assert d.fallback_roots == [self.SKILL_JEWEL, self.SLIME, self.SHIELD,
                                    self.TRUNK, *self.ORPHANS]
        assert d.fallback_steps[0] == self.SKILL_JEWEL

    def test_walk_skips_unservable_fallbacks_in_order(self):
        """IN ORDER, and with four alternatives it is now a real claim: two are
        unservable, so the walk must land on the THIRD — not on the last, and
        not on the trunk."""
        blocked = (self.SKILL_JEWEL, self.SKILL_GEAR)
        d = self._decide_with(lambda root, step: root not in blocked)
        assert d.chosen_root == self.SLIME
        assert d.fallback_roots == [self.SKILL_JEWEL, self.SKILL_GEAR,
                                    self.SHIELD, self.TRUNK, *self.ORPHANS]

    def test_every_gear_pair_unservable_still_reaches_the_trunk(self):
        """The trunk stays in the list, just last: a FULLY blocked gear branch
        must still yield to XP rather than deadlock on an unservable pick.
        Yielding the branch is the last resort, not the first.

        FIX-ROUND 2: the STEP is asserted against the trunk's OWN paired step,
        taken from the unpromoted decision, not against `self.TRUNK`. The loose
        form was the very thing an earlier docstring here argued against — with
        `chosen_root` also TRUNK, "a walk that promoted the root while keeping
        some other root's step would pass". Reading the pair out of the
        no-promotion decision keeps the discrimination without hard-coding a
        step value that moves with the fixture."""
        unpromoted = self._decide_with(lambda root, step: True)
        trunk_at = unpromoted.fallback_roots.index(self.TRUNK)
        trunk_step = unpromoted.fallback_steps[trunk_at]
        gear = (self.SKILL_JEWEL, self.SKILL_GEAR, self.SLIME, self.SHIELD)
        d = self._decide_with(lambda root, step: root not in gear)
        assert d.chosen_root == self.TRUNK
        assert d.chosen_step == trunk_step
        # …and the pair really is discriminating: the promoted step is NOT the
        # step any other root would have contributed.
        assert trunk_step not in unpromoted.fallback_steps[:trunk_at]
        assert trunk_step != unpromoted.chosen_step

    def test_promotion_records_the_root_the_tree_actually_picked(self):
        """The trace could not tell "the tree chose this" from "promotion landed
        here": the servability verdict is computed on the FINAL root, so a
        promoted root always logs as servable. Live 2026-07-27, 9 of 15 cycles
        logged `ReachCharLevel, servable: true` and read as the tree choosing XP
        when every one was a displaced gear pick."""
        d = self._decide_with(lambda root, step: root != self.SKILL_JEWEL)
        assert d.chosen_root == self.SKILL_GEAR
        assert d.promoted_from == self.SKILL_JEWEL

    def test_no_promotion_records_nothing(self):
        d = self._decide_with(lambda root, step: True)
        assert d.chosen_root == self.SKILL_JEWEL
        assert d.promoted_from is None

    def test_all_unservable_records_no_promotion(self):
        """Nothing was displaced — the original choice is kept — so the field
        must stay None rather than pointing at the root that IS chosen."""
        d = self._decide_with(lambda root, step: False)
        assert d.chosen_root == self.SKILL_JEWEL
        assert d.promoted_from is None

    def test_all_unservable_keeps_original_choice(self):
        d = self._decide_with(lambda root, step: False)
        assert d.chosen_root == self.SKILL_JEWEL
        assert d.fallback_roots == [self.SKILL_GEAR, self.SLIME, self.SHIELD,
                                    self.TRUNK, *self.ORPHANS]

    def test_default_none_predicate_is_untouched(self):
        gd = _bundle()
        state = scenario_state(SCENARIOS["l10_weapon_upgrade"], gd)
        d = decide_tree(state, gd, CharacterObjective.from_game_data(gd))
        assert d.chosen_root == self.SKILL_JEWEL
        assert d.fallback_roots == [self.SKILL_GEAR, self.SLIME, self.SHIELD,
                                    self.TRUNK, *self.ORPHANS]

    def test_predicate_sees_root_step_pairs(self):
        seen: list[tuple[object, object]] = []

        def spy(root, step):
            seen.append((root, step))
            return False

        self._decide_with(spy)
        # Walk order: chosen pair first, then fallbacks in order.
        assert seen[0] == (self.SKILL_JEWEL, self.SKILL_JEWEL)
        assert [r for r, _ in seen[1:]] == [self.SKILL_GEAR, self.SLIME,
                                            self.SHIELD, self.TRUNK,
                                            *self.ORPHANS]
        assert dict(seen)[self.SHIELD] == self.SHIELD_STEP


# --- Synthetic-GameData unit tests (coverage of branches the 6 scenarios
# never reach) ----------------------------------------------------------

class TestHasStructuralUpgrade:
    """has_structural_upgrade: the tier-aware adequacy leg (2026-07-07 live
    shadow finding — filled COPPER slots at L14 must NOT read as adequate)."""

    def test_true_when_positive_gain_upgrade_reachable(self):
        gd = _bundle()
        state = scenario_state(SCENARIOS["l10_weapon_upgrade"], gd)
        assert has_structural_upgrade(state, gd,
                                      CharacterObjective.from_game_data(gd))

    def test_true_for_filled_but_underleveled_set(self):
        """Full copper set, higher-tier targets exist: NOT adequate —
        the exact live-review correction (slots filled ≠ at-band-tier)."""
        gd = _bundle()
        state = scenario_state(SCENARIOS["l10_copper_adequate"], gd)
        assert has_structural_upgrade(state, gd,
                                      CharacterObjective.from_game_data(gd))


class TestSyntheticBranches:
    def test_xp_branch_fires_when_gear_wants_nothing(self):
        """None of the 6 committed scenarios ever leaves the gear sheet empty,
        so the trunk-only outcome needs its own minimal fixture: ONE equippable
        item, already worn. The catalogue cannot be EMPTY any more — the ladder
        is derived from the equippable catalogue and `tier_of_level` refuses to
        invent a rung for a game with no equipment, which is the correct
        no-defaulting-around-API-data behaviour and not something to work
        around.

        With the one item worn, `gear_targets_with_blockers` is `{}`, there is
        no monster in the band so `IsThereACombatTarget` says no, and
        `CanIClearMyTier` finds the (empty) band cleared and returns the trunk.
        `alternatives` is empty because the only ordered entry IS the trunk and
        it is the chosen root."""
        gd = GameData(items=ItemCatalog(stats={
            "wooden_stick": ItemStats(code="wooden_stick", level=1,
                                      type_="weapon", attack={"air": 2})}))
        objective = CharacterObjective.from_game_data(gd)
        state = scenario_state(ScenarioCharacter(
            name="synthetic_geared", level=5, max_hp=100,
            equipment={"weapon_slot": "wooden_stick"}))
        d = decide_tree(state, gd, objective)
        assert d.chosen_root == ReachCharLevel(level=10)
        assert d.chosen_step == d.chosen_root
        assert d.fallback_roots == []
        assert d.fallback_steps == []
        assert len(d.ranking) == 1  # trunk row only

    def test_candidate_builders_skip_unknown_item_stats(self):
        """`_structural_candidates` is computed from the OBJECTIVE's own bound
        game_data (baked in at `from_game_data` time), not the `game_data`
        parameter it separately receives. If the two ever diverge,
        `item_stats(code)` can miss and the builder must skip the code rather
        than crash. An empty `GameData` makes every code the objective offers
        unknown, exercising the `stats is None: continue` guard.

        WAVE 3a re-pointed this at `objective_candidates`, which concatenated
        this builder with `_utility_candidates`' matching guard. WAVE 3b
        deleted `_utility_candidates` and `objective_candidates` themselves
        (zero production callers — `decide_tree` stopped reading them in
        wave 3a and the last diagnostic reader, `commands/objective.py`, was
        retired in wave 3b), so this test now calls `_structural_candidates`
        directly and only pins its own guard."""
        gd_full = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
        objective = CharacterObjective.from_game_data(gd_full)
        state = scenario_state(SCENARIOS["l1_fresh"], gd_full)
        assert objective.near_term_gear(state), "sanity: real bundle offers structural candidates"
        assert _structural_candidates(state, gd_full, objective), \
            "sanity: the SAME call is non-empty against the matching catalogue"
        assert _structural_candidates(state, GameData(), objective) == []


# --- The weapon-slot winnability guard in `_structural_candidates` ------------
#
# Coverage of that guard's `continue` used to ride on the achievability
# acceptance witness, which wave 3b deleted along with `_achievability_map`. The
# guard itself is LIVE — it is the fire_bow fix, where a damage-type-blind ruler
# ground weaponcrafting toward a combat DOWNGRADE — so it gets a direct test
# rather than incidental coverage. Both directions are asserted: a weapon that
# unlocks nothing is dropped, and the SAME weapon on the SAME sheet is admitted
# once a monster exists that only it can beat.


def _weapon_guard_gd(with_fire_mob: bool) -> GameData:
    """`stone_axe` (earth 20) and `flame_rod` (fire 40), one or two monsters.

    `earth_mob` has no resistances, so the axe alone already beats it.
    `fire_mob` resists earth 100, so the axe does zero damage to it and only the
    rod unlocks it. Same shape as `tests/test_ai/test_weapon_winnability`'s
    fixture — that suite pins the metric, this one pins the tree's use of it."""
    gd = GameData()
    gd._item_stats = {
        "stone_axe": ItemStats(code="stone_axe", level=1, type_="weapon",
                               attack={"earth": 20}),
        "flame_rod": ItemStats(code="flame_rod", level=1, type_="weapon",
                               attack={"fire": 40}),
    }
    gd._monster_level = {"earth_mob": 1}
    gd._monster_hp = {"earth_mob": 30}
    gd._monster_attack = {"earth_mob": {}}
    gd._monster_resistance = {"earth_mob": {}}
    if with_fire_mob:
        gd._monster_level["fire_mob"] = 1
        gd._monster_hp["fire_mob"] = 30
        gd._monster_attack["fire_mob"] = {}
        gd._monster_resistance["fire_mob"] = {"earth": 100}
    fill_monster_stat_defaults(gd)
    return gd


def _weapon_guard_state():
    """Empty weapon slot, `stone_axe` CARRIED (so `predict_win` may use it) and
    `flame_rod` BANKED (so it is attainable-now for the sheet, but is not part
    of the owned combat pool). That split is what makes the rod a real candidate
    whose marginal winnability is the only thing left deciding it."""
    return make_state(inventory={"stone_axe": 1}, bank_items={"flame_rod": 1})


def test_a_weapon_that_unlocks_no_monster_is_dropped_from_the_candidates():
    """THE GUARD. `flame_rod` wins the weapon slot on the damage-type-blind
    ruler (attack 40 against the axe's 20) and is attainable now, so it reaches
    `_structural_candidates`. It beats nothing the carried axe already beats, so
    it must not become a gear root — the live fire_bow case."""
    gd = _weapon_guard_gd(with_fire_mob=False)
    objective = CharacterObjective.from_game_data(gd)
    state = _weapon_guard_state()
    assert objective.near_term_gear(state).get("weapon_slot") == "flame_rod", \
        "sanity: the sheet must actually offer the rod, or the guard is untested"
    assert marginal_weapon_winnability("flame_rod", state, gd) == 0
    assert [c.code for c in _structural_candidates(state, gd, objective)] == []


def test_the_same_weapon_survives_once_it_unlocks_a_monster():
    """NON-VACUITY. Identical sheet, identical state; the only change is a
    monster that resists earth, which the rod beats and the axe cannot. The
    candidate now survives, so the empty list above is the guard firing rather
    than the candidate never having been built."""
    gd = _weapon_guard_gd(with_fire_mob=True)
    objective = CharacterObjective.from_game_data(gd)
    state = _weapon_guard_state()
    assert marginal_weapon_winnability("flame_rod", state, gd) > 0
    assert [c.code for c in _structural_candidates(state, gd, objective)] == ["flame_rod"]
