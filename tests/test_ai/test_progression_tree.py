"""decide_tree(): the Phase-2 tree assembly over Phase-1 scenarios.

Drives the module DIRECTLY (not wired into StrategyEngine — Phase 3).
Expectations are computed from the tree's own binding semantics."""

import json
from dataclasses import replace
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.item_catalog import ItemCatalog
from artifactsmmo_cli.ai.player import GamePlayer  # noqa: F401  (scenario seam parity)
from artifactsmmo_cli.ai.scenario import SCENARIOS, ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.progression_tree import decide_tree, has_structural_upgrade
from artifactsmmo_cli.ai.tiers.progression_tree_core import FOCUS_FLAT, FOCUS_SPAN

BUNDLE = (Path(__file__).parent / "scenarios" / "fixtures"
          / "gamedata_bundle.json")


def _bundle() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def _decide(name: str):
    gd = _bundle()
    state = scenario_state(SCENARIOS[name])
    return decide_tree(state, gd, CharacterObjective.from_game_data(gd)), state


def test_weapon_upgrade_scenario_picks_gear_branch():
    d, _ = _decide("l10_weapon_upgrade")
    assert isinstance(d.chosen_root, ObtainItem)
    assert d.chosen_root.slot == "weapon_slot"


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
    d, _state = _decide("l1_fresh")
    trunk_rows = [r for r in d.ranking if r.category == "char_level"]
    assert trunk_rows and "10" in trunk_rows[0].root_repr


def test_ranking_renders_the_descent():
    d, _ = _decide("l10_weapon_upgrade")
    assert d.ranking, "descent must be rendered for display parity"
    assert all(r.score >= 0 for r in d.ranking)


def test_fallbacks_offer_the_other_branch():
    d, _ = _decide("l10_weapon_upgrade")
    assert any(isinstance(s, ReachCharLevel) for s in d.fallback_steps), (
        "gear decision must carry the xp trunk as an arbiter fallback")


# --- Per-scenario behavior pins ---------------------------------------------
#
# Exact branch/target recorded under the committed gamedata_bundle.json
# fixture, derived from the binding semantics (progression_tree.py's own
# rules), NOT from the Lean model — this module is value-semantics only.
# These are the tree's behavior pins for Phase 3's shadow wiring: the live
# arbiter's choice gets diffed against these, catching any accidental drift
# in near_term_gear/utility_potion_targets/equip_value composition.

class TestPerScenarioPins:
    def test_l1_fresh_pins_weapon_gear_branch(self):
        """Level 1, nothing owned: near_term_gear admits every attainable
        item with stats.level <= 1 whose equip_value beats the empty slot
        (gain > 0) — copper_dagger/helmet/boots/shield/rings all qualify,
        plus small_health_potion via utility_potion_targets (unprovisioned,
        weight 1 for hp_restore). candidates != [] -> gear_target_exists
        -> GEAR (branch_pick_pure). copper_dagger's weighted gain (83) beats
        every other candidate's, so it wins gear_target_pick's argmax.
        The dagger isn't directly craftable-now (no bar/ore held), so
        actionable_step descends to the gather leaf: copper_ore x10."""
        d, _ = _decide("l1_fresh")
        assert d.chosen_root == ObtainItem(code="copper_dagger", quantity=1, slot="weapon_slot")
        assert d.chosen_step == ObtainItem(code="copper_ore", quantity=10)
        assert len(d.ranking) == 8  # trunk + 7 gear candidates
        assert d.ranking[0].category == "char_level"
        assert d.ranking[0].root_repr == "ReachCharLevel(level=10)"

    def test_l8_overstocked_pins_gear_branch(self):
        """Level 8, full copper set (no shield in _COPPER_SET) + empty
        utility slot: near_term_gear finds nothing above the copper set for
        the equipped slots, but shield_slot is empty (wooden_shield) and
        utility1_slot is unprovisioned (small_health_potion).

        GEAR-FIRST re-derivation 2026-07-08 (Task-3 pursuit_value; user
        ruling): wooden_shield is a STRUCTURAL candidate now scored by
        combat-dominant pursuit_value (gain 8000), which beats the POTION's
        equip_value×weight gain (61) in the merged argmax -> GEAR branch,
        wooden_shield wins (was small_health_potion under flat equip_value,
        where the potion's 61 beat the shield's 17). Combat/gear pursuit
        outranks potion-stocking; the potion still survives as a fallback.
        wooden_shield isn't craftable-now, so the step descends to its gather
        leaf: ash_wood x10."""
        d, _ = _decide("l8_overstocked")
        assert d.chosen_root == ObtainItem(code="wooden_shield", quantity=1,
                                           slot="shield_slot")
        assert d.chosen_step == ObtainItem(code="ash_wood", quantity=10)
        assert len(d.ranking) == 3  # trunk + shield + potion

    def test_l10_copper_adequate_pins_gear_branch_not_xp(self):
        """The scenario NAME says 'adequate', but adequacy here is Phase-2's
        crude 2-arg definition (candidates == []) — shield_slot is still
        empty, so a structural candidate (wooden_shield) exists and wins.
        This is NOT the XP-branch case (that needs a fully-saturated synthetic
        state — see TestSyntheticBranches).

        GEAR-FIRST re-derivation 2026-07-08 (Task-3 pursuit_value; user
        ruling): the empty shield_slot's wooden_shield (structural, gain 8000)
        outranks the unprovisioned small_health_potion (utility, gain 61), so
        the gear branch chooses wooden_shield (was the potion under flat
        equip_value). wooden_shield isn't craftable-now (ash_wood not held),
        so the step descends to its gather leaf: ash_wood x10."""
        d, _ = _decide("l10_copper_adequate")
        assert d.chosen_root == ObtainItem(code="wooden_shield", quantity=1,
                                           slot="shield_slot")
        assert d.chosen_step == ObtainItem(code="ash_wood", quantity=10)
        assert len(d.ranking) == 3
        assert d.ranking[0].root_repr == "ReachCharLevel(level=20)"

    def test_l10_weapon_upgrade_pins_weapon_over_potion(self):
        """weapon_slot holds wooden_stick; copper_dagger's gain (64) beats
        both small_health_potion (61) and wooden_shield (17) -> weapon_slot
        wins gear_target_pick's argmax -> GEAR branch. copper_bar (6, from
        the banked copper_ore/iron_ore smelt chain) is the actionable step,
        not the raw ore -- the recipe is one level closer to satisfied here
        than in l1_fresh (bars bankable, no ore held directly)."""
        d, _ = _decide("l10_weapon_upgrade")
        assert d.chosen_root == ObtainItem(code="copper_dagger", quantity=1, slot="weapon_slot")
        assert d.chosen_step == ObtainItem(code="copper_bar", quantity=6)
        assert len(d.ranking) == 4  # trunk + dagger + potion + shield
        assert d.fallback_roots[0] == ReachCharLevel(level=20)
        assert ObtainItem(code="small_health_potion", quantity=1,
                          slot="utility1_slot") in d.fallback_roots
        assert ObtainItem(code="wooden_shield", quantity=1, slot="shield_slot") in d.fallback_roots

    def test_l3_low_hp_pins_weapon_branch(self):
        """Same near_term_gear pool as l1_fresh (all qualifying items are
        level <= 1, so raising state.level to 3 admits nothing new) -> the
        tree still answers with the GEAR branch. The survival guard that
        would preempt this at the arbiter has no seam in decide_tree
        itself (semantics: guards preempt at the ARBITER, not here)."""
        d, _ = _decide("l3_low_hp")
        assert d.chosen_root == ObtainItem(code="copper_dagger", quantity=1, slot="weapon_slot")
        assert d.chosen_step == ObtainItem(code="copper_ore", quantity=10)
        assert len(d.ranking) == 8

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
        recipe's higher qty-3 demand) and iron_boots's higher equip_value
        contribution (66) outranks small_health_potion (61) outright ->
        GEAR branch, boots_slot, gather leaf for the still-short feather
        (2 banked, 3 needed — the STEP goal is quantity-aware even though
        attainability isn't)."""
        d, _ = _decide("l12_taskgated_bag")
        assert d.chosen_root == ObtainItem(code="iron_boots", quantity=1,
                                           slot="boots_slot")
        assert d.chosen_step == ObtainItem(code="feather", quantity=3)
        assert len(d.ranking) == 8


# --- band_adequate parameter (Phase-3 Task-1) -------------------------------
#
# Phase-2 computed band_adequate internally as `candidates == []`. Phase 3
# replaces that stand-in with a caller-supplied verdict (Task 2 wires the
# real progression-band signal) — decide_tree defaults band_adequate=False
# so every existing caller (including all tests above) is unaffected.

class TestAdequacyParameter:
    def test_adequate_with_candidates_goes_xp_with_gear_fallbacks(self):
        """Adequate band + upgrades available: XP is chosen, gear candidates
        survive as arbiter fallbacks (Phase-2 final-review finding — they
        must NOT be silently dropped)."""
        gd = _bundle()
        state = scenario_state(SCENARIOS["l10_weapon_upgrade"])
        d = decide_tree(state, gd, CharacterObjective.from_game_data(gd),
                        band_adequate=True)
        assert isinstance(d.chosen_root, ReachCharLevel)
        assert any(isinstance(r, ObtainItem) for r in d.fallback_roots), (
            "gear candidates must survive as fallbacks under the XP branch")

    def test_not_adequate_defaults_preserve_phase2_pins(self):
        """band_adequate=False (the default) reproduces the Phase-2 behavior
        pins exactly — the parameter is additive."""
        gd = _bundle()
        state = scenario_state(SCENARIOS["l10_weapon_upgrade"])
        d = decide_tree(state, gd, CharacterObjective.from_game_data(gd))
        assert isinstance(d.chosen_root, ObtainItem)
        assert d.chosen_root.slot == "weapon_slot"

    def test_adequate_no_candidates_pure_xp(self):
        """Adequate + zero candidates: pure XP decision, empty gear
        fallbacks. Reuses the same empty-GameData synthetic fixture as
        TestSyntheticBranches.test_xp_branch_fires_when_candidates_are_truly_empty."""
        gd = GameData()
        objective = CharacterObjective.from_game_data(gd)
        state = scenario_state(ScenarioCharacter(name="synthetic_empty", level=5, max_hp=100))
        d = decide_tree(state, gd, objective, band_adequate=True)
        assert isinstance(d.chosen_root, ReachCharLevel)
        assert d.chosen_step == d.chosen_root
        assert not any(isinstance(r, ObtainItem) for r in d.fallback_roots)


# --- step_servable demotion (Phase-4b Task-1: THE FLIP) ---------------------
#
# The legacy decide()'s servable filter must survive the cutover: an
# unservable chosen (root, step) falls through the fallback pairs IN ORDER to
# the first servable pair; demoted pairs stay in the fallback lists after the
# promoted one; all-unservable keeps the original choice (the arbiter's
# doomed-memo handles it, as today).

class TestServabilityDemotion:
    """l10_weapon_upgrade pins (see TestPerScenarioPins): chosen =
    ObtainItem(copper_dagger, weapon_slot) / step ObtainItem(copper_bar, 6);
    fallback_roots = [ReachCharLevel(20), wooden_shield, small_health_potion].

    GEAR-FIRST re-derivation 2026-07-08 (Task-3 pursuit_value; user ruling):
    the SHIELD (a structural candidate, now scored by combat-dominant
    pursuit_value ×1000) outranks the POTION (a utility-potion candidate, kept
    on equip_value × potion_weight ×~2) in the merged argmax, so the two swap
    order — combat/gear pursuit outranks potion-stocking, potions still pursued
    once no structural upgrade remains. Was [TRUNK, POTION, SHIELD]."""

    DAGGER = ObtainItem(code="copper_dagger", quantity=1, slot="weapon_slot")
    TRUNK = ReachCharLevel(level=20)
    POTION = ObtainItem(code="small_health_potion", quantity=1, slot="utility1_slot")
    SHIELD = ObtainItem(code="wooden_shield", quantity=1, slot="shield_slot")

    def _decide_with(self, servable):
        gd = _bundle()
        state = scenario_state(SCENARIOS["l10_weapon_upgrade"])
        return decide_tree(state, gd, CharacterObjective.from_game_data(gd),
                           step_servable=servable)

    def test_servable_chosen_is_untouched(self):
        d = self._decide_with(lambda root, step: True)
        assert d.chosen_root == self.DAGGER
        assert d.fallback_roots == [self.TRUNK, self.SHIELD, self.POTION]

    def test_unservable_chosen_promotes_first_servable_fallback(self):
        d = self._decide_with(lambda root, step: root != self.DAGGER)
        assert d.chosen_root == self.TRUNK
        assert d.chosen_step == self.TRUNK
        # The demoted pair survives in the fallbacks, ahead of the rest —
        # original priority order minus the promotion.
        assert d.fallback_roots == [self.DAGGER, self.SHIELD, self.POTION]
        assert d.fallback_steps[0] == ObtainItem(code="copper_bar", quantity=6)

    def test_walk_skips_unservable_fallbacks_in_order(self):
        servable = lambda root, step: root not in (self.DAGGER, self.TRUNK)  # noqa: E731
        d = self._decide_with(servable)
        # GEAR-FIRST (2026-07-08): SHIELD now precedes POTION, so the first
        # servable fallback promoted is the SHIELD, not the potion.
        assert d.chosen_root == self.SHIELD
        # Demoted pairs (chosen first, then the skipped fallbacks) keep their
        # relative order after the promoted pair leaves the list.
        assert d.fallback_roots == [self.DAGGER, self.TRUNK, self.POTION]

    def test_all_unservable_keeps_original_choice(self):
        d = self._decide_with(lambda root, step: False)
        assert d.chosen_root == self.DAGGER
        assert d.fallback_roots == [self.TRUNK, self.SHIELD, self.POTION]

    def test_default_none_predicate_is_untouched(self):
        gd = _bundle()
        state = scenario_state(SCENARIOS["l10_weapon_upgrade"])
        d = decide_tree(state, gd, CharacterObjective.from_game_data(gd))
        assert d.chosen_root == self.DAGGER
        assert d.fallback_roots == [self.TRUNK, self.SHIELD, self.POTION]

    def test_predicate_sees_root_step_pairs(self):
        seen: list[tuple[object, object]] = []

        def spy(root, step):
            seen.append((root, step))
            return False

        self._decide_with(spy)
        # Walk order: chosen pair first, then fallbacks in order.
        assert seen[0] == (self.DAGGER, ObtainItem(code="copper_bar", quantity=6))
        assert [r for r, _ in seen[1:]] == [self.TRUNK, self.SHIELD, self.POTION]


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
    def test_xp_branch_fires_when_candidates_are_truly_empty(self):
        """None of the 6 committed scenarios ever produce an empty
        candidate list (there's always a spare slot or an unprovisioned
        potion in the real catalog) -- so the `else` arm of decide_tree's
        branch dispatch (chosen_root = chosen_step = trunk, no fallbacks)
        needs its own minimal fixture: an EMPTY GameData (no items, so
        near_term_gear and utility_potion_targets both return {})."""
        gd = GameData()
        objective = CharacterObjective.from_game_data(gd)
        state = scenario_state(ScenarioCharacter(name="synthetic_empty", level=5, max_hp=100))
        d = decide_tree(state, gd, objective)
        assert d.chosen_root == ReachCharLevel(level=10)
        assert d.chosen_step == d.chosen_root
        assert d.fallback_roots == []
        assert d.fallback_steps == []
        assert len(d.ranking) == 1  # trunk row only

    def test_structural_and_utility_candidates_skip_unknown_item_stats(self):
        """near_term_gear/utility_potion_targets are computed from the
        OBJECTIVE's own bound game_data (baked in at from_game_data time),
        not the `game_data` parameter decide_tree separately receives. If
        the two ever diverge (a stale objective queried against a refreshed
        catalog, or -- as here -- a deliberately mismatched pairing),
        item_stats(code) can miss and both candidate builders must skip the
        code rather than crash. Passing an empty GameData as the decide_tree
        parameter (while the objective was built from the full bundle)
        exercises both `stats is None: continue` guards at once, since
        every code the objective offers is unknown to the empty catalog."""
        gd_full = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
        objective = CharacterObjective.from_game_data(gd_full)
        state = scenario_state(SCENARIOS["l1_fresh"])
        assert objective.near_term_gear(state), "sanity: real bundle offers structural candidates"
        assert objective.utility_potion_targets(state), "sanity: real bundle offers a potion target"
        d = decide_tree(state, GameData(), objective)
        # Every candidate got skipped (unknown stats) -> no gear candidates,
        # tree falls to the trunk.
        assert d.chosen_root == ReachCharLevel(level=10)
        assert len(d.ranking) == 1

    def test_already_provisioned_utility_slot_is_skipped(self):
        """equipped_potion_qty > 0 must remove the potion from candidates
        (refill churn is the guard's job) -- scenario_state never sets a
        utility slot quantity > 0 (ScenarioCharacter has no such field), so
        this needs a directly-constructed WorldState via dataclasses.replace."""
        gd = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
        objective = CharacterObjective.from_game_data(gd)
        base_state = scenario_state(SCENARIOS["l10_weapon_upgrade"])
        code = objective.utility_potion_targets(base_state)["utility1_slot"]
        provisioned_state = replace(
            base_state,
            equipment={**base_state.equipment, "utility1_slot": code},
            utility1_slot_quantity=5,
        )
        d = decide_tree(provisioned_state, gd, objective)
        # The potion candidate is gone; only the weapon (and shield, if any
        # remain empty) compete -- small_health_potion must not appear
        # anywhere in the rendered ranking.
        assert not any(code in r.root_repr for r in d.ranking)
        assert d.chosen_root == ObtainItem(code="copper_dagger", quantity=1, slot="weapon_slot")

    def test_zero_gain_utility_candidate_is_filtered_and_falls_to_xp(self):
        """A utility target whose own equip_value computes to 0 (all-zero
        ItemStats) must never arm the gear branch -- the same `gain > 0`
        guard _structural_candidates already has, applied to the utility
        leg. Mirrors test_structural_and_utility_candidates_skip_unknown_
        item_stats's mismatched-game_data trick: the OBJECTIVE stays bound
        to the full bundle (bootstrap_potion_target legitimately picks
        small_health_potion there -- it needs hp_restore > 0 to be picked
        at all), but decide_tree's own `game_data` parameter maps that same
        code to an all-zero ItemStats, so it survives the `stats is None`
        skip yet contributes 0 weighted gain. near_term_gear's codes are
        absent from this catalog entirely (only the potion code is
        present), so structural_candidates is empty too, and decide_tree
        must fall all the way to the XP trunk."""
        gd_full = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
        objective = CharacterObjective.from_game_data(gd_full)
        state = scenario_state(SCENARIOS["l1_fresh"])
        code = objective.utility_potion_targets(state)["utility1_slot"]
        assert code == "small_health_potion"  # sanity: matches the Phase-2 pin
        zero_stats_gd = GameData(items=ItemCatalog(
            stats={code: ItemStats(code=code, level=1, type_="utility", subtype="tool")}))
        d = decide_tree(state, zero_stats_gd, objective)
        assert not any(code in r.root_repr for r in d.ranking)
        assert d.chosen_root == ReachCharLevel(level=10)
        assert d.chosen_step == d.chosen_root
        assert d.fallback_roots == []
        assert d.fallback_steps == []


# --- focus/cycle aging parameters (arbiter anti-starvation epic, Task 4) ----
#
# decide_tree's pick/order swap from the plain gear_target_pick/_ordered
# argmax to focus_aging_pick/focus_aging_order (Task 3's cores). The empty-
# focus/cycle-0 default must reproduce today's argmax exactly; a fully-decayed
# focus must hand cycles off to a reachable alternative without abandoning the
# stuck root outright.

def _two_gear_candidate_fixture() -> tuple:
    """Two structural gear candidates with a wide gain gap: `wolf_ears`
    (helmet_slot, hp_bonus=100 -> pursuit_value 100000, the argmax) and
    `iron_ring` (ring1_slot AND ring2_slot -- rings are a DUPLICATE_SLOT_TYPE,
    so one candidate item fills both -- hp_bonus=1 -> pursuit_value 1000, far
    behind). Both items are held in inventory so `is_attainable_now`'s
    stock_ok short-circuit fires without needing a recipe or a gatherable
    resource (see objective.py's `_attainable_closure`/`is_attainable_now`).
    Level 1 items, character level 5, so both clear near_term_gear's
    `stats.level <= state.level` filter and neither slot is pre-equipped, so
    every candidate's gain is strictly positive."""
    gd = GameData(items=ItemCatalog(stats={
        "wolf_ears": ItemStats(code="wolf_ears", level=1, type_="helmet", hp_bonus=100),
        "iron_ring": ItemStats(code="iron_ring", level=1, type_="ring", hp_bonus=1),
    }))
    objective = CharacterObjective.from_game_data(gd)
    state = scenario_state(ScenarioCharacter(
        name="synthetic_two_gear", level=5, max_hp=100,
        inventory={"wolf_ears": 1, "iron_ring": 1},
    ))
    return state, gd, objective


class TestFocusAging:
    def test_decide_tree_aging_hands_off_stuck_top(self):
        """A helmet fully decayed past FOCUS_FLAT + FOCUS_SPAN never fully
        starves the alternative (ring2_slot) over 40 cycles, and never fully
        abandons the decayed top either -- FOCUS_FLOOR keeps it alive."""
        state, gd, objective = _two_gear_candidate_fixture()
        stuck_key = ("helmet_slot", "wolf_ears")
        focus = {stuck_key: FOCUS_FLAT + FOCUS_SPAN}
        seen = set()
        for cyc in range(40):
            d = decide_tree(state, gd, objective, band_adequate=False,
                            focus=focus, cycle=cyc)
            seen.add(repr(d.chosen_root))
        assert any("ring2_slot" in r for r in seen), (
            "starved alternative root must run within 40 aged cycles")
        assert any("helmet_slot" in r for r in seen), (
            "FOCUS_FLOOR keeps the decayed drop root alive, not abandoned")

    def test_decide_tree_empty_focus_matches_argmax(self):
        """Defaults (no focus arg, no cycle arg) and an explicit empty
        focus/cycle=7 both agree with the plain argmax: the aging swap must
        not perturb any caller that doesn't wire the ledger in."""
        state, gd, objective = _two_gear_candidate_fixture()
        d0 = decide_tree(state, gd, objective, band_adequate=False)
        d1 = decide_tree(state, gd, objective, band_adequate=False, focus={}, cycle=7)
        assert repr(d0.chosen_root) == repr(d1.chosen_root)
        assert d0.chosen_root == ObtainItem(code="wolf_ears", quantity=1, slot="helmet_slot")
