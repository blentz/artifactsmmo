"""decide_tree(): the Phase-2 tree assembly over Phase-1 scenarios.

Drives the module DIRECTLY (not wired into StrategyEngine — Phase 3).
Expectations are computed from the tree's own binding semantics."""

import json
from dataclasses import replace
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.player import GamePlayer  # noqa: F401  (scenario seam parity)
from artifactsmmo_cli.ai.scenario import SCENARIOS, ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.progression_tree import decide_tree

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

    def test_l8_overstocked_pins_potion_branch(self):
        """Level 8, full copper set (no shield in _COPPER_SET) + empty
        utility slot: near_term_gear finds nothing above the copper set for
        the equipped slots, but shield_slot is empty (wooden_shield gain >
        0) and utility1_slot is unprovisioned (small_health_potion). The
        potion's weighted gain (61) beats wooden_shield's (17) -> GEAR
        branch, small_health_potion wins the argmax. sunflower is banked
        nowhere for this char (bank unset -> None) so the step descends to
        the gather leaf: sunflower x3."""
        d, _ = _decide("l8_overstocked")
        assert d.chosen_root == ObtainItem(code="small_health_potion", quantity=1,
                                           slot="utility1_slot")
        assert d.chosen_step == ObtainItem(code="sunflower", quantity=3)
        assert len(d.ranking) == 3  # trunk + potion + shield

    def test_l10_copper_adequate_pins_potion_branch_not_xp(self):
        """The scenario NAME says 'adequate', but adequacy here is Phase-2's
        crude 2-arg definition (candidates == []) — shield_slot is still
        empty and the utility slot is unprovisioned (sunflower is banked, 20
        of it), so the potion candidate exists and wins. This is NOT the
        XP-branch case (that needs a fully-saturated synthetic state — see
        TestSyntheticBranches). small_health_potion is immediately
        producible from the bank, so chosen_step == chosen_root."""
        d, _ = _decide("l10_copper_adequate")
        assert d.chosen_root == ObtainItem(code="small_health_potion", quantity=1,
                                           slot="utility1_slot")
        assert d.chosen_step == d.chosen_root
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

    def test_l12_taskgated_bag_pins_potion_branch(self):
        """Full copper set + empty utility slot, no sunflower banked (only
        cowhide/feather) -> small_health_potion is still the unprovisioned
        utility target and wins over wooden_shield -> GEAR branch, gather
        leaf for sunflower (not held, not banked)."""
        d, _ = _decide("l12_taskgated_bag")
        assert d.chosen_root == ObtainItem(code="small_health_potion", quantity=1,
                                           slot="utility1_slot")
        assert d.chosen_step == ObtainItem(code="sunflower", quantity=3)
        assert len(d.ranking) == 3


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


# --- Synthetic-GameData unit tests (coverage of branches the 6 scenarios
# never reach) ----------------------------------------------------------

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
