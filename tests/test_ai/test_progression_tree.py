"""decide_tree(): the wave-3a RESOLUTION walk over the Phase-1 scenarios.

Drives the module DIRECTLY (not wired into StrategyEngine).

WAVE 3a MOVED EVERY SCENARIO PIN IN THIS FILE, and one fixture fact explains
all of them. The walk reads `objective.gear_targets_with_blockers`, which gears
for `tier_progress.gear_target_tier` — the rung being CLEARED, capped by
character level. Under `scenarios/fixtures/gamedata_bundle.json` NO scenario
clears rung 1: `predict_win` says a level-12 character in a full copper set
loses to a 60-hp chicken, so `next_uncleared_tier` is 1 for every scenario and
`gear_target_tier` is pinned to 1. Rung-1 gear — `wooden_shield`,
`wooden_staff` (blocked on `wooden_stick`) — is therefore the whole target
sheet, whatever the character's level.

The retired ranking never consulted winnability: `near_term_gear` capped by
LEVEL only, which is why the old pins read copper at L10 and iron at L12. The
new values are what the shipped tier model says about this fixture, not a
weakening. Live data does NOT behave this way — see
`.superpowers/sdd/PLAN_wave3a_cutover/task-6-report.md`, which records
`plan Robby` (L30, gearcrafting/jewelrycrafting roots) and `plan Lor` (L20,
`ReachSkillLevel(gearcrafting, 10)` as the chosen root) against the live
catalogue."""

import json
from dataclasses import replace
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.item_catalog import ItemCatalog
from artifactsmmo_cli.ai.player import GamePlayer  # noqa: F401  (scenario seam parity)
from artifactsmmo_cli.ai.scenario import SCENARIOS, ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.progression_tree import (
    _achievability_map,
    _structural_candidates,
    _utility_candidates,
    decide_tree,
    has_structural_upgrade,
    objective_candidates,
)
from artifactsmmo_cli.ai.tiers.progression_tree_core import (
    GearCandidate,
    focus_aging_order,
)
from artifactsmmo_cli.ai.world_state import WorldState

BUNDLE = (Path(__file__).parent / "scenarios" / "fixtures"
          / "gamedata_bundle.json")


def _bundle() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def _decide(name: str):
    gd = _bundle()
    state = scenario_state(SCENARIOS[name])
    return decide_tree(state, gd, CharacterObjective.from_game_data(gd)), state


def test_weapon_upgrade_scenario_picks_gear_branch():
    """`shield_slot`, not `weapon_slot`: at gear-target tier 1 the weapon-slot
    target is `wooden_staff`, blocked on the material `wooden_stick`, while the
    EMPTY shield slot is a full rung behind (`_tier_gap` scores an empty slot
    from rung 0) and resolves attainable. Still the gear branch, which is what
    this test is named for."""
    d, _ = _decide("l10_weapon_upgrade")
    assert isinstance(d.chosen_root, ObtainItem)
    assert d.chosen_root.slot == "shield_slot"


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
    """Asserted on `fallback_roots`, not `fallback_steps`. The trunk is still
    last in the fallback list — the 2026-07-27 trunk-last ruling survives the
    flip verbatim — but its STEP is no longer the trunk itself: this character
    is not `combat_capable`, so `prerequisites(ReachCharLevel)` emits a weapon
    and `actionable_step` descends to `ObtainItem(mithril_ore, 10)`. Matching
    on the step therefore says nothing about whether the trunk is reachable,
    which is the property this test is for."""
    d, _ = _decide("l10_weapon_upgrade")
    assert any(isinstance(r, ReachCharLevel) for r in d.fallback_roots), (
        "gear decision must carry the xp trunk as an arbiter fallback")
    assert d.fallback_roots[-1] == ReachCharLevel(level=20)


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
        The trunk is last."""
        d, _ = _decide("l1_fresh")
        assert d.chosen_root == ObtainItem(code="wooden_stick", quantity=1)
        assert d.chosen_step == d.chosen_root
        assert len(d.ranking) == 7  # chosen + 5 sibling slots + trunk
        assert d.ranking[0].root_repr == "ObtainItem(code='wooden_stick', quantity=1)"
        assert d.ranking[0].category == (
            "IsMyGearBehindMyTier → WhichSlotIsFurthestBehind → IsThisTargetBlocked")
        assert d.ranking[-1].root_repr == "ReachCharLevel(level=10)"

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
            "ReachCharLevel(level=10)"]

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
        leads with the resolved root and the trunk goes last. The trunk itself
        is unchanged at `ReachCharLevel(20)`."""
        d, _ = _decide("l10_copper_adequate")
        assert d.chosen_root == ObtainItem(code="wooden_shield", quantity=1,
                                           slot="shield_slot")
        assert len(d.ranking) == 3
        assert d.ranking[0].root_repr == (
            "ObtainItem(code='wooden_shield', quantity=1, slot='shield_slot')")
        assert d.ranking[-1].root_repr == "ReachCharLevel(level=20)"

    def test_l10_weapon_upgrade_pins_the_empty_shield_slot(self):
        """WAVE 3a. `copper_dagger` is not on the target sheet: the gear-target
        tier is 1 (see the module docstring), so the weapon slot's target is
        `wooden_staff` and the character already wears a `wooden_stick` there.
        The EMPTY shield slot is the furthest behind — `_tier_gap` scores an
        empty slot from rung 0, so a rung-1 target in an empty slot outranks a
        rung-1 target over an occupied one, which is the empty-slot dominance
        the kernel proves.

        Trunk LAST (2026-07-27) survives the flip: `resolve_root` appends the
        trunk after every sibling."""
        d, _ = _decide("l10_weapon_upgrade")
        assert d.chosen_root == ObtainItem(code="wooden_shield", quantity=1,
                                           slot="shield_slot")
        assert d.chosen_step == ObtainItem(code="ash_wood", quantity=10)
        assert len(d.ranking) == 3
        assert d.fallback_roots[-1] == ReachCharLevel(level=20)
        assert ObtainItem(code="wooden_stick", quantity=1) in d.fallback_roots

    def test_l3_low_hp_pins_weapon_branch(self):
        """Same target sheet as l1_fresh (the gear-target tier is 1 for both,
        and raising state.level to 3 admits nothing new) -> the tree still
        answers with the GEAR branch and the same root. The survival guard that
        would preempt this at the arbiter has no seam in decide_tree itself
        (semantics: guards preempt at the ARBITER, not here)."""
        d, _ = _decide("l3_low_hp")
        assert d.chosen_root == ObtainItem(code="wooden_stick", quantity=1)
        assert d.chosen_step == d.chosen_root
        assert len(d.ranking) == 7

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

        WAVE 3a: iron gear is off the sheet entirely. This scenario has NO
        attack (`derive_combat_stats` off), so `tier_cleared(1)` is False and
        `gear_target_tier` caps at rung 1 — the character is not asked to gear
        for a rung whose band it cannot clear, which is the whole point of
        `gear_target_tier` (its docstring's Robby-at-30 case). That is a
        stronger answer than the old level-capped one, not a weaker one: at
        zero attack, iron_sword's materials come from monsters this character
        loses to.

        The satchel assertion is kept verbatim — the region gate is unrelated
        to the flip and must keep holding."""
        d, _ = _decide("l12_taskgated_bag")
        assert d.chosen_root == ObtainItem(code="wooden_shield", quantity=1,
                                           slot="shield_slot")
        assert d.chosen_step == ObtainItem(code="ash_wood", quantity=10)
        assert len(d.ranking) == 3
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
    ObtainItem(wooden_shield, shield_slot) / step ObtainItem(ash_wood, 10);
    fallback_roots = [ObtainItem(wooden_stick), ReachCharLevel(20)].

    TRUNK-LAST correction 2026-07-27 (live trace): the trunk used to sit at
    index 0, so ONE unservable gear step promoted the XP trunk over servable
    gear candidates sitting behind it — Robby ran 9 of 15 cycles on
    ReachCharLevel with 7 live structural candidates and the branch verdict
    saying GEAR. That ruling is unchanged by wave 3a: `resolve_root` appends
    the trunk AFTER every sibling, so this class keeps testing the same
    property against the walk's own fallback order.

    WAVE 3a re-derivation: the three candidate roots are now SHIELD (the
    furthest-behind slot), STICK (the weapon slot's blocking material) and the
    TRUNK — one fewer than before, because the POTION was a
    `_utility_candidates` entry and utility potions are not gear targets. Every
    test below keeps its exact assertion shape; only the constants moved."""

    SHIELD = ObtainItem(code="wooden_shield", quantity=1, slot="shield_slot")
    SHIELD_STEP = ObtainItem(code="ash_wood", quantity=10)
    STICK = ObtainItem(code="wooden_stick", quantity=1)
    TRUNK = ReachCharLevel(level=20)

    def _decide_with(self, servable):
        gd = _bundle()
        state = scenario_state(SCENARIOS["l10_weapon_upgrade"])
        return decide_tree(state, gd, CharacterObjective.from_game_data(gd),
                           step_servable=servable)

    def test_servable_chosen_is_untouched(self):
        d = self._decide_with(lambda root, step: True)
        assert d.chosen_root == self.SHIELD
        assert d.fallback_roots == [self.STICK, self.TRUNK]

    def test_unservable_chosen_promotes_the_next_gear_candidate_not_the_trunk(self):
        """THE 2026-07-27 REGRESSION. One unservable gear step must not
        abandon the gear branch: the promotion takes the next servable GEAR
        candidate, and the trunk stays behind it."""
        d = self._decide_with(lambda root, step: root != self.SHIELD)
        assert d.chosen_root == self.STICK
        assert d.chosen_root != self.TRUNK
        # The demoted pair survives in the fallbacks, ahead of the rest —
        # original priority order minus the promotion.
        assert d.fallback_roots == [self.SHIELD, self.TRUNK]
        assert d.fallback_steps[0] == self.SHIELD_STEP

    def test_walk_skips_unservable_fallbacks_in_order(self):
        servable = lambda root, step: root not in (self.SHIELD, self.STICK)  # noqa: E731
        d = self._decide_with(servable)
        # SHIELD unservable, STICK (the next gear candidate) unservable too, so
        # the walk skips it and reaches the trunk.
        assert d.chosen_root == self.TRUNK
        # Demoted pairs (chosen first, then the skipped fallbacks) keep their
        # relative order after the promoted pair leaves the list. THIS is the
        # in-order claim: a walk that took the last servable pair, or that
        # reordered the demoted remainder, would fail here and not above.
        assert d.fallback_roots == [self.SHIELD, self.STICK]

    def test_every_gear_pair_unservable_still_reaches_the_trunk(self):
        """The trunk stays in the list, just last: a FULLY blocked gear branch
        must still yield to XP rather than deadlock on an unservable pick.
        Yielding the branch is the last resort, not the first.

        The promoted STEP is `ObtainItem(mithril_ore, 10)`, not the trunk
        itself: this character is not `combat_capable`, so the trunk's
        prerequisite is a weapon and `actionable_step` descends into it. The
        step is asserted explicitly rather than as `== chosen_root`, because
        the promotion carries the (root, step) PAIR and a walk that promoted
        the root while keeping some other root's step would pass the loose
        form."""
        gear = (self.SHIELD, self.STICK)
        d = self._decide_with(lambda root, step: root not in gear)
        assert d.chosen_root == self.TRUNK
        assert d.chosen_step == ObtainItem(code="mithril_ore", quantity=10)

    def test_promotion_records_the_root_the_tree_actually_picked(self):
        """The trace could not tell "the tree chose this" from "promotion landed
        here": the servability verdict is computed on the FINAL root, so a
        promoted root always logs as servable. Live 2026-07-27, 9 of 15 cycles
        logged `ReachCharLevel, servable: true` and read as the tree choosing XP
        when every one was a displaced gear pick."""
        d = self._decide_with(lambda root, step: root != self.SHIELD)
        assert d.chosen_root == self.STICK
        assert d.promoted_from == self.SHIELD

    def test_no_promotion_records_nothing(self):
        d = self._decide_with(lambda root, step: True)
        assert d.chosen_root == self.SHIELD
        assert d.promoted_from is None

    def test_all_unservable_records_no_promotion(self):
        """Nothing was displaced — the original choice is kept — so the field
        must stay None rather than pointing at the root that IS chosen."""
        d = self._decide_with(lambda root, step: False)
        assert d.chosen_root == self.SHIELD
        assert d.promoted_from is None

    def test_all_unservable_keeps_original_choice(self):
        d = self._decide_with(lambda root, step: False)
        assert d.chosen_root == self.SHIELD
        assert d.fallback_roots == [self.STICK, self.TRUNK]

    def test_default_none_predicate_is_untouched(self):
        gd = _bundle()
        state = scenario_state(SCENARIOS["l10_weapon_upgrade"])
        d = decide_tree(state, gd, CharacterObjective.from_game_data(gd))
        assert d.chosen_root == self.SHIELD
        assert d.fallback_roots == [self.STICK, self.TRUNK]

    def test_predicate_sees_root_step_pairs(self):
        seen: list[tuple[object, object]] = []

        def spy(root, step):
            seen.append((root, step))
            return False

        self._decide_with(spy)
        # Walk order: chosen pair first, then fallbacks in order.
        assert seen[0] == (self.SHIELD, self.SHIELD_STEP)
        assert [r for r, _ in seen[1:]] == [self.STICK, self.TRUNK]


# --- Synthetic-GameData unit tests (coverage of branches the 6 scenarios
# never reach) ----------------------------------------------------------

class TestHasStructuralUpgrade:
    """has_structural_upgrade: the tier-aware adequacy leg (2026-07-07 live
    shadow finding — filled COPPER slots at L14 must NOT read as adequate)."""

    def test_true_when_positive_gain_upgrade_reachable(self):
        gd = _bundle()
        state = scenario_state(SCENARIOS["l10_weapon_upgrade"])
        assert has_structural_upgrade(state, gd,
                                      CharacterObjective.from_game_data(gd))

    def test_true_for_filled_but_underleveled_set(self):
        """Full copper set, higher-tier targets exist: NOT adequate —
        the exact live-review correction (slots filled ≠ at-band-tier)."""
        gd = _bundle()
        state = scenario_state(SCENARIOS["l10_copper_adequate"])
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
        """`_structural_candidates` / `_utility_candidates` are computed from
        the OBJECTIVE's own bound game_data (baked in at `from_game_data` time),
        not the `game_data` parameter they separately receive. If the two ever
        diverge, `item_stats(code)` can miss and both builders must skip the
        code rather than crash. An empty `GameData` makes every code the
        objective offers unknown, exercising both `stats is None: continue`
        guards at once.

        WAVE 3a re-pointed this at `objective_candidates` — the one function
        that concatenates the two builders — because `decide_tree` no longer
        calls them. The guards are still live: `commands/objective.py` runs the
        same list outside the bot."""
        gd_full = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
        objective = CharacterObjective.from_game_data(gd_full)
        state = scenario_state(SCENARIOS["l1_fresh"])
        assert objective.near_term_gear(state), "sanity: real bundle offers structural candidates"
        assert objective.utility_potion_targets(state), "sanity: real bundle offers a potion target"
        assert objective_candidates(state, gd_full, objective), \
            "sanity: the SAME call is non-empty against the matching catalogue"
        assert objective_candidates(state, GameData(), objective) == []

    def test_already_provisioned_utility_slot_is_skipped(self):
        """equipped_potion_qty > 0 must remove the potion from candidates
        (refill churn is the guard's job) -- scenario_state never sets a
        utility slot quantity > 0 (ScenarioCharacter has no such field), so
        this needs a directly-constructed WorldState via dataclasses.replace.

        WAVE 3a re-pointed this at `objective_candidates` for the same reason
        as the test above."""
        gd = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
        objective = CharacterObjective.from_game_data(gd)
        base_state = scenario_state(SCENARIOS["l10_weapon_upgrade"])
        code = objective.utility_potion_targets(base_state)["utility1_slot"]
        assert any(c.code == code for c in
                   objective_candidates(base_state, gd, objective)), \
            "sanity: the unprovisioned slot DOES offer the potion"
        provisioned_state = replace(
            base_state,
            equipment={**base_state.equipment, "utility1_slot": code},
            utility1_slot_quantity=5,
        )
        assert not any(c.code == code for c in
                       objective_candidates(provisioned_state, gd, objective))

    def test_zero_gain_utility_candidate_is_filtered(self):
        """A utility target whose own equip_value computes to 0 (all-zero
        ItemStats) must never become a candidate -- the same `gain > 0`
        guard `_structural_candidates` already has, applied to the utility
        leg. Mirrors the mismatched-game_data trick above: the OBJECTIVE stays
        bound to the full bundle (`bootstrap_potion_target` legitimately picks
        small_health_potion there -- it needs hp_restore > 0 to be picked at
        all), but the `game_data` parameter maps that same code to an all-zero
        ItemStats, so it survives the `stats is None` skip yet contributes 0
        weighted gain."""
        gd_full = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
        objective = CharacterObjective.from_game_data(gd_full)
        state = scenario_state(SCENARIOS["l1_fresh"])
        code = objective.utility_potion_targets(state)["utility1_slot"]
        assert code == "small_health_potion"  # sanity: matches the Phase-2 pin
        zero_stats_gd = GameData(items=ItemCatalog(
            stats={code: ItemStats(code=code, level=1, type_="utility", subtype="tool")}))
        assert objective_candidates(state, zero_stats_gd, objective) == []


# --- Achievability acceptance witness (Task 6) -------------------------------
#
# THE acceptance test for the whole achievability-factor epic: the factor must
# actually reorder live candidates, and the reordering must be REVERSIBLE by
# holdings, or it is just a blanket penalty on long chains dressed up as an
# effort measure. `lich_race_trophy` (achievability_core.py's own docstring
# example -- "Live at L21 ... 1000 event_tickets away") is not itself in the
# committed `gamedata_bundle.json` fixture (only `lich_crown`/`lich_tomb_key`
# are), so this builds the same TWO-HOP currency shape
# (`requirement_graph_memo.py`'s own docstring: trophy <- 10 medal <- 100
# event_ticket each = 1000) on top of the real bundle: one synthetic BUY-only
# artifact plus one synthetic intermediate currency, priced by two permanent
# NPC vendors, bottoming out in `event_ticket` -- a real bundle item, gatherable
# here (so it is attainable-now on its own, not only once held). This uses the
# SAME post-load `npc_stock`/`npc_buy_currency`/`npc_tiles` mutation TECHNIQUE
# tests/test_ai/test_requirement_graph_memo.py's `_gd_with_chain` uses (that
# fixture is a synthetic `GameData()` modelling the chain in isolation; this one
# is the real bundle, modelling the ranking-path consumer of it) -- a single-hop
# price would exercise `_currency_cost`'s base case only, never its recursive
# transitive-expansion arm, which is exactly what Task 1 added.

def _bundle_with_currency_gated_artifact() -> GameData:
    """`_bundle()` plus one synthetic artifact, `lich_race_trophy`: no recipe
    (BUY leaf only), sold by a permanent vendor for 10 `lich_race_medal`, itself
    sold by a second permanent vendor for 100 `event_ticket` each -- a genuine
    two-hop chain (`_currency_cost`'s recursive arm, not just its base case),
    totalling 1000 tickets exactly as `requirement_graph_memo.py`'s own
    docstring describes. a 1.6x gain gap over the ring slot's real argmax -- comfortably under
    achievability_core.A_MIN's documented 2x boundary (a maximally distant
    candidate can only lose to a maximally close one below that gap), which is
    the exact property this test exercises. `event_ticket` is made gatherable
    (a resource drop) so it is attainable-now by itself; the poor/rich split
    below turns entirely on how much of it is HELD, not on whether it can be
    acquired in principle.

    RE-DERIVED 2026-08-04 (pursuit_value unification). The near candidate used
    to be `life_ring` (hp_bonus) and the trophy carried hp_bonus 40. On the ONE
    ruler the ring slot's argmax is `iron_ring` (4% global damage,
    pursuit 105_600_000) rather than `life_ring` (hp_bonus 25, 5_000_020), so
    the near witness moved with it; the trophy's hp_bonus was re-derived to 845
    (200 * 845 * 1000 = 169_000_000) to keep the SAME ~1.6x gain gap the test
    needs -- comfortably under achievability_core.A_MIN's 2x boundary, which is
    the property being exercised. Neither the mechanism nor the gap changed,
    only the two items' absolute numbers."""
    gd = _bundle()
    gd.items.stats["lich_race_trophy"] = ItemStats(
        code="lich_race_trophy", level=15, type_="artifact", hp_bonus=845)
    gd.world.npc_stock["trophy_vendor"] = {"lich_race_trophy": 10}
    gd.world.npc_buy_currency["trophy_vendor"] = {"lich_race_trophy": "lich_race_medal"}
    gd.world.npc_tiles["trophy_vendor"] = (5, 5)
    gd.world.npc_stock["medal_vendor"] = {"lich_race_medal": 100}
    gd.world.npc_buy_currency["medal_vendor"] = {"lich_race_medal": "event_ticket"}
    gd.world.npc_tiles["medal_vendor"] = (6, 6)
    gd.recipes_catalog.resource_drops_full["event_shrine"] = [("event_ticket", 1, 1, 1)]
    return gd


_ACHIEVABILITY_WITNESS_BANK = {
    "iron_bar": 8, "iron_ore": 80, "cloth": 2, "mushroom": 5,
    "wool": 6, "life_ring": 1, "iron_ring": 1,
}
"""Covers the near candidate's ENTIRE real requirement multiset so its
`_effort_for(...)` is exactly 0 -- the achievability FLOOR every other
candidate in the decision is scored against (`achievability_pure`'s
`min_effort`). Holds BOTH rings: `life_ring` was the near candidate before the
pursuit_value unification and `iron_ring` is it now (see
`_bundle_with_currency_gated_artifact`), and keeping both makes the floor
independent of which one the ruler picks for the slot."""


def _state_with(gd: GameData, inventory: dict[str, int]) -> WorldState:
    """A near_term_gear fixed point for every slot EXCEPT rings/artifacts
    (iterated empirically the same way every fixed-point entry in
    scenario.SCENARIOS is -- see e.g. l30_rune_fill/l48_band_adequate), so
    `life_ring` (ring1_slot/ring2_slot) and `lich_race_trophy`
    (artifact1/2/3_slot) are the ONLY structural gear candidates. `gold=2000`
    and `skills` clear life_ring's own currency/skill-gate tokens (see
    `_ACHIEVABILITY_WITNESS_BANK`). `inventory` is the SOLE difference between
    the poor and rich witnesses -- holding `event_ticket` is the only thing
    that changes."""
    sc = ScenarioCharacter(
        name="achievability_witness", level=25, max_hp=500, gold=2000,
        skills={"jewelrycrafting": 15, "mining": 10},
        equipment={
            "helmet_slot": "iron_helm", "weapon_slot": "copper_dagger",
            "shield_slot": "iron_shield", "boots_slot": "copper_boots",
            "body_armor_slot": "copper_armor",
            "utility1_slot": "small_health_potion",
        },
        utility_quantities={"utility1_slot": 5},
        bank=dict(_ACHIEVABILITY_WITNESS_BANK),
        inventory=inventory, inventory_max=2000,
    )
    return scenario_state(sc)


def _ordered_candidates(state: WorldState, gd: GameData) -> list[GearCandidate]:
    """The tree's OWN achievability-weighted display order: exactly
    `decide_tree`'s own `_structural_candidates + _utility_candidates` ->
    `_achievability_map` -> `focus_aging_order` pipeline
    (progression_tree.py:397-418), read directly -- NOT `decision.ranking`,
    which is display-only (progression_tree.py:149-155: "no separate
    weighting exists in this display path -- the trunk row does the same")."""
    objective = CharacterObjective.from_game_data(gd)
    candidates = (_structural_candidates(state, gd, objective)
                  + _utility_candidates(state, gd, objective))
    achievability = _achievability_map(candidates, state, gd)
    return focus_aging_order(candidates, {}, {}, {}, achievability)


def test_achievability_map_of_no_candidates_is_inert() -> None:
    """`_achievability_map`'s empty guard, directly.

    It exists because `min(efforts.values())` raises on an empty sequence, and
    `{}` is the inert map every `.get(..., Fraction(1))` lookup reads as "no
    penalty". Wave 3a made this a direct unit: `decide_tree` used to reach the
    empty case whenever a state had no gear candidates, and it no longer calls
    this function at all."""
    assert _achievability_map([], scenario_state(SCENARIOS["l1_fresh"]),
                              _bundle()) == {}


class TestAchievabilityReversalWitness:
    def test_achievability_reorders_the_live_bundle_and_is_reversible(self) -> None:
        """THE acceptance test. With ordinary holdings the craftable iron_ring
        outranks the currency-gated lich_race_trophy; give the character 1000
        event_tickets and the trophy returns to the top. If the second half
        failed, the factor would be a blanket penalty on long chains rather
        than an effort measure that responds to what is actually held."""
        gd = _bundle_with_currency_gated_artifact()
        poor = _state_with(gd, inventory={})
        rich = _state_with(gd, inventory={"event_ticket": 1000})

        poor_order = [c.code for c in _ordered_candidates(poor, gd)]
        rich_order = [c.code for c in _ordered_candidates(rich, gd)]

        assert poor_order.index("iron_ring") < poor_order.index("lich_race_trophy")
        assert rich_order.index("lich_race_trophy") < rich_order.index("iron_ring")

    def test_reversal_is_falsifiable_by_the_inert_achievability_default(self) -> None:
        """OVERRIDE (supersedes the brief's `git stash` step, per a standing
        project rule against stashing mid-task): `focus_aging_order`'s
        achievability parameter defaults to the empty `_NO_ACHIEVABILITY` map,
        bit-identical to pre-factor behaviour (progression_tree_core.py's own
        docstring). If the poor-holdings order above held regardless of
        achievability, it would equal this inert-default order too -- it does
        not, so the factor (not the candidates' raw gains alone) drives the
        poor-case ranking. A permanent test, not a one-off manual diff."""
        gd = _bundle_with_currency_gated_artifact()
        poor = _state_with(gd, inventory={})
        objective = CharacterObjective.from_game_data(gd)
        candidates = (_structural_candidates(poor, gd, objective)
                      + _utility_candidates(poor, gd, objective))

        real_achievability = _achievability_map(candidates, poor, gd)
        weighted_order = [c.code for c in
                          focus_aging_order(candidates, {}, {}, {}, real_achievability)]
        inert_order = [c.code for c in focus_aging_order(candidates, {}, {})]

        assert weighted_order.index("iron_ring") < weighted_order.index("lich_race_trophy")
        assert inert_order.index("lich_race_trophy") < inert_order.index("iron_ring")
        assert weighted_order != inert_order
