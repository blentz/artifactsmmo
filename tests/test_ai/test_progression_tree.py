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
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_objective_result import GearObjective
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
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT, make_state
from tests.test_ai.shared_world import attached, shared_world

BUNDLE = (Path(__file__).parent / "scenarios" / "fixtures"
          / "gamedata_bundle.json")


def _bundle() -> GameData:
    return shared_world(BUNDLE)


def _ctx_for(state, gd: GameData):  # type: ignore[no-untyped-def]
    """The context a live cycle walks: the cycle's gear objective attached by
    the one function the player uses (ruling W)."""
    return attached(state, gd, TIMED_NO_PROFILE_CONTEXT, None)


def _decide(name: str):
    gd = _bundle()
    state = scenario_state(SCENARIOS[name], gd)
    return decide_tree(state, gd, CharacterObjective.from_game_data(gd),
                       ctx=_ctx_for(state, gd)), state


def test_weapon_upgrade_scenario_builds_the_weapon_its_objective_names_first():
    """RE-DERIVED Task 5 (global gear objective), then spec 2026-10-18 §2.9: a
    fight's seconds are its learned length, so `L*` is the set that kills
    `red_slime` fastest and its weapon is `greater_wooden_staff`. Its
    `blue_slimeball` drops from a monster the worn copper does not beat, so the
    blocked target names that drop as the root (`IsThisTargetBlocked`)."""
    d, _ = _decide("l10_weapon_upgrade")
    assert d.chosen_root == ObtainItem(code="blue_slimeball", quantity=2)
    assert d.chosen_step == ObtainItem(code="blue_slimeball", quantity=2)


def test_low_hp_scenario_still_produces_a_decision():
    """Guards preempt at the ARBITER, not here — the tree always answers."""
    d, _ = _decide("l3_low_hp")
    assert d.chosen_root is not None and d.chosen_step is not None


def test_ranking_renders_the_descent():
    d, _ = _decide("l10_weapon_upgrade")
    assert d.ranking, "descent must be rendered for display parity"
    assert all(r.score >= 0 for r in d.ranking)


# THE ORPHAN TAIL (`decisions/root._orphan_skill_roots`) is empty on every pin
# below. USER 2026-10-08 "Only when demanded": a standalone skill climb is
# offered only for a skill the goal-action DAG demands and no root on offer
# already climbs, and none of these scenarios demands one. The unconditional
# cooking floor and the undemanded gear-nameable climbs that used to extend
# each list are gone with the old admission rule.


# --- Per-scenario behavior pins ---------------------------------------------
#
# Exact branch/target recorded under the committed gamedata_bundle.json
# fixture, derived from the binding semantics (progression_tree.py's own
# rules), NOT from the Lean model — this module is value-semantics only.
# These are the tree's behavior pins for Phase 3's shadow wiring: the live
# arbiter's choice gets diffed against these, catching any accidental drift
# in near_term_gear/utility_potion_targets/equip_value composition.

class TestPerScenarioPins:
    """RE-DERIVED Task 5 (global gear objective, spec 2026-10-18 §2.4): every
    pin below is the walk from `WhichPieceIsNext` over the cycle's own gear
    objective. The root is the first missing `L*` piece (or the climb or
    material in front of it); the rows after it are the other pieces, in the
    objective's order, deduplicated; then the task and orphan roots. No trunk
    row: no scenario holds its `L*`, and the trunk is offered only once it is
    held (§6.2). The old pins read the tier sheet's furthest-behind slot."""

    TRAIL = "WhichPieceIsNext → IsThisTargetBlocked"

    def test_l1_fresh_pins_the_first_copper_piece(self):
        """Level 1, nothing worn: `L*` is the copper set and the wooden shield,
        the dagger first. Every copper piece's step is the ore it is smelted
        from. Against `yellow_slime` the shield and the two rings add nothing to
        `R` over owning none (spec §2.8), so they are not missing; the helmet
        out-gains the boots per unit of price."""
        d, _ = _decide("l1_fresh")
        assert d.chosen_root == ObtainItem(code="copper_dagger", quantity=1, slot="weapon_slot")
        assert d.chosen_step == ObtainItem(code="copper_ore", quantity=10)
        assert [r.root_repr for r in d.ranking] == [
            "ObtainItem(code='copper_dagger', quantity=1, slot='weapon_slot')",
            "ObtainItem(code='copper_helmet', quantity=1, slot='helmet_slot')",
            "ObtainItem(code='copper_boots', quantity=1, slot='boots_slot')"]
        assert d.ranking[0].category == self.TRAIL

    def test_l8_overstocked_pins_the_weapon_climb(self):
        """`L*`'s first piece is `water_bow`, weaponcrafting-gated: the root is
        the next weaponcrafting level and the bow is the published ask. The
        feather coat's gearcrafting climb and the life amulet's jewelrycrafting
        climb follow in the objective's order. The `wooden_shield` adds nothing
        to `R` on `green_slime` (spec §2.8): it is not missing."""
        d, _ = _decide("l8_overstocked")
        assert d.chosen_root == ReachSkillLevel(skill="weaponcrafting", level=2)
        assert d.chosen_step == d.chosen_root
        assert d.blocked_target == "water_bow"
        assert [r.root_repr for r in d.ranking] == [
            "ReachSkillLevel(skill='weaponcrafting', level=2)",
            "ReachSkillLevel(skill='gearcrafting', level=2)",
            "ReachSkillLevel(skill='jewelrycrafting', level=2)"]

    def test_l10_copper_adequate_pins_the_greater_wooden_staff(self):
        """"Adequate" copper is not `L*`: since spec 2026-10-18 §2.9 (a fight's
        seconds are its learned length) the level-10 objective is the set that
        kills `red_slime` fastest, and its first piece, `greater_wooden_staff`,
        steps to the recipe's two `blue_slimeball`s (blue_slime is beaten in
        copper). No XP grind is offered while the set is missing."""
        d, _ = _decide("l10_copper_adequate")
        assert d.chosen_root == ObtainItem(code="greater_wooden_staff", quantity=1,
                                           slot="weapon_slot")
        assert d.chosen_step == ObtainItem(code="blue_slimeball", quantity=2)
        assert [r.root_repr for r in d.ranking] == [
            "ObtainItem(code='greater_wooden_staff', quantity=1, slot='weapon_slot')",
            "ObtainItem(code='leather_armor', quantity=1, slot='body_armor_slot')",
            "ObtainItem(code='leather_boots', quantity=1, slot='boots_slot')",
            "ObtainItem(code='leather_legs_armor', quantity=1, slot='leg_armor_slot')",
            "ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')",
            "ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')",
            "ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')",
            "ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')",
            "ReachSkillLevel(skill='jewelrycrafting', level=2)",
        ]
        assert not any(isinstance(r, ReachCharLevel) for r in d.fallback_roots)

    def test_l10_weapon_upgrade_pins_the_weapon_then_the_climbs(self):
        """`L*`'s weapon (`greater_wooden_staff`, spec §2.9) needs a drop the
        worn copper cannot win, so its blocked drop heads the walk; the
        gearcrafting and jewelrycrafting climbs the armour and amulet need
        follow, then the two rings. Distinguishable from `l10_copper_adequate`
        by its board: at gearcrafting 1 every gearcrafting-10 armour piece is
        the one climb."""
        d, _ = _decide("l10_weapon_upgrade")
        assert d.chosen_root == ObtainItem(code="blue_slimeball", quantity=2)
        assert [r.root_repr for r in d.ranking] == [
            "ObtainItem(code='blue_slimeball', quantity=2)",
            "ReachSkillLevel(skill='gearcrafting', level=2)",
            "ReachSkillLevel(skill='jewelrycrafting', level=2)",
            "ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')",
            "ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')",
        ]

    def test_l3_low_hp_pins_weapon_branch(self):
        """Same objective as l1_fresh (raising state.level to 3 admits nothing
        new) -> the tree still answers with the same first piece. The survival
        guard that would preempt this at the arbiter has no seam in decide_tree
        itself (semantics: guards preempt at the ARBITER, not here). As there,
        only the dagger, helmet and boots add to `R` (spec §2.8)."""
        d, _ = _decide("l3_low_hp")
        assert d.chosen_root == ObtainItem(code="copper_dagger", quantity=1, slot="weapon_slot")
        assert d.chosen_step == ObtainItem(code="copper_ore", quantity=10)
        assert len(d.ranking) == 3
        assert d.ranking[-1].root_repr == (
            "ObtainItem(code='copper_boots', quantity=1, slot='boots_slot')")

    def test_l12_taskgated_bag_pins_the_weaponcrafting_climb(self):
        """The iron sword heads `L*`, and at weaponcrafting 1 it is a climb:
        the root is weaponcrafting 2 and the sword is the published ask. The
        satchel assertion is kept verbatim — the region gate is unrelated and
        must keep holding: the satchel needs `jasper_crystal`, sold only behind
        an unreachable trader."""
        d, _ = _decide("l12_taskgated_bag")
        assert d.chosen_root == ReachSkillLevel(skill="weaponcrafting", level=2)
        assert d.blocked_target == "iron_sword"
        assert [r.root_repr for r in d.ranking] == [
            "ReachSkillLevel(skill='weaponcrafting', level=2)",
            "ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot')",
            "ObtainItem(code='iron_armor', quantity=1, slot='body_armor_slot')",
            "ObtainItem(code='iron_boots', quantity=1, slot='boots_slot')",
            "ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')",
            "ObtainItem(code='mushroom', quantity=4)",
            "ReachSkillLevel(skill='jewelrycrafting', level=2)",
            "ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')",
            "ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')",
            "ReachSkillLevel(skill='mining', level=10)",
        ]
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


class TestStepDeclineInTheWalk:
    """l10_weapon_upgrade pins (see TestPerScenarioPins): chosen =
    ObtainItem(blue_slimeball, 2), the blocked drop of `L*`'s
    `greater_wooden_staff` (spec 2026-10-18 §2.9); alternatives = [
    ReachSkillLevel(gearcrafting, 2), ReachSkillLevel(jewelrycrafting, 2),
    ObtainItem(forest_ring, ring1_slot), ObtainItem(forest_ring, ring2_slot)].

    PHASE 3-2, kept by Task 5: the walk asks each piece's step
    (`step_decline`) in the objective's order and lets only a served one head
    it; a declined piece is named and stays on offer in its own place in that
    order (the alternatives are the objective's pieces, never re-sorted).
    No trunk while a piece is served: a piece is missing, so no level grind is
    offered (spec 2026-10-18 §6.2) — unless every piece is declined (ruling
    AI, INTERIM)."""

    HEAD = ObtainItem(code="blue_slimeball", quantity=2)
    SKILL_GEAR = ReachSkillLevel(skill="gearcrafting", level=2)
    SKILL_JEWEL = ReachSkillLevel(skill="jewelrycrafting", level=2)
    RING1 = ObtainItem(code="forest_ring", quantity=1, slot="ring1_slot")
    RING2 = ObtainItem(code="forest_ring", quantity=1, slot="ring2_slot")

    def _decide_with(self, decline):
        gd = _bundle()
        state = scenario_state(SCENARIOS["l10_weapon_upgrade"], gd)
        return decide_tree(state, gd, CharacterObjective.from_game_data(gd),
                           step_decline=decline, ctx=_ctx_for(state, gd))

    def test_default_no_decline_is_untouched(self):
        d = self._decide_with(lambda root: None)
        assert d.chosen_root == self.HEAD
        assert d.fallback_roots == [self.SKILL_GEAR, self.SKILL_JEWEL, self.RING1, self.RING2]
        assert d.declined == ()

    def test_a_declined_head_lets_the_next_piece_head(self):
        """One declined piece hands the head to the next PIECE, never to a
        level grind, and is offered in its own place with its reason."""
        d = self._decide_with(lambda root: "blocked" if root == self.HEAD else None)
        assert d.chosen_root == self.SKILL_GEAR
        assert d.fallback_roots == [self.HEAD, self.SKILL_JEWEL, self.RING1, self.RING2]
        assert d.declined == ((repr(self.HEAD), "blocked"),)

    def test_declined_pieces_keep_the_objectives_order(self):
        declined = {self.HEAD, self.SKILL_GEAR}
        d = self._decide_with(lambda root: "blocked" if root in declined else None)
        assert d.chosen_root == self.SKILL_JEWEL
        assert d.fallback_roots == [self.HEAD, self.SKILL_GEAR, self.RING1, self.RING2]

    def test_every_piece_declined_offers_the_trunk(self):
        """Ruling AI (INTERIM): with no servable gear step the root is one
        more character level; every piece stays declined by name, on offer."""
        gear = {self.HEAD, self.SKILL_GEAR, self.SKILL_JEWEL, self.RING1, self.RING2}
        d = self._decide_with(lambda root: "blocked" if root in gear else None)
        assert d.chosen_root == ReachCharLevel(level=11)
        assert {root for root, _reason in d.declined} == {repr(g) for g in gear}
        assert d.fallback_roots[:5] == [self.HEAD, self.SKILL_GEAR, self.SKILL_JEWEL,
                                        self.RING1, self.RING2]
        assert not any(isinstance(r, ReachCharLevel) for r in d.fallback_roots)

    def test_the_walk_asks_in_order_until_a_piece_is_served(self):
        """The first served piece ends the question: the rings behind the
        served jewelrycrafting climb are never asked."""
        seen: list[object] = []

        def spy(root):
            seen.append(root)
            return "blocked" if root in (self.HEAD, self.SKILL_GEAR) else None

        d = self._decide_with(spy)
        assert d.chosen_root == self.SKILL_JEWEL
        assert list(dict.fromkeys(seen)) == [self.HEAD, self.SKILL_GEAR, self.SKILL_JEWEL]


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
        """REWRITTEN Task 5 (ruling Y) on a HELD shape: the character wears its
        whole `L*` (the one equippable in this minimal catalogue), so the
        objective misses nothing and the root is one more character level —
        `ReachCharLevel(level + 1)`, no milestone. Its step is itself, and the
        trunk is the only thing offered, so there are no alternatives."""
        gd = GameData(items=ItemCatalog(stats={
            "wooden_stick": ItemStats(code="wooden_stick", level=1,
                                      type_="weapon", attack={"air": 2})}))
        objective = CharacterObjective.from_game_data(gd)
        state = scenario_state(ScenarioCharacter(
            name="synthetic_geared", level=5, max_hp=100,
            equipment={"weapon_slot": "wooden_stick"}))
        held = GearObjective("chicken", {"weapon_slot": "wooden_stick"}, Fraction(1), ())
        d = decide_tree(state, gd, objective,
                        ctx=replace(TIMED_NO_PROFILE_CONTEXT, gear_objective=held))
        assert d.chosen_root == ReachCharLevel(level=6)
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
