"""The orphan skill gate, driven over the REAL walk (`resolve_root`), not over
`_orphan_skill_roots` called directly with an injected `offered`.

USER 2026-10-08, "Only when demanded": a skill climbs only when the goal-action
DAG demands it (gear, the consumable floor's tier food, a task). Cooking rises
when a better tier food is due, not before.

All suites run against the committed bundle
(`tests/test_ai/scenarios/fixtures/gamedata_bundle.json`, loaded exactly as
`scripts/gen_open_rung.py` loads it — see `conftest.bundle_game_data`). None
makes an API call.

(A) `TestNoUndemandedCooking`: cooking used to be the unconditional floor,
admitted in 44 of 44 scenarios. With no tier food short it is now offered in
none — the live 2026-10-08 `ReachSkillLevel(cooking, 32)` that pulled fishing
in through its grind target is the case this pins.

(B) `TestGatheringDemandPositiveBranch`: a gathering skill demanded by an
`ObtainItem` gear sibling is kept at the DEMANDED level, and disappears once
satisfied.

(C) `TestTierFoodDemandsFishing`: THE CANONICAL CHAIN — the fleet's tier-food
shortfall `cooked_shrimp` -> `shrimp` -> fishing@10 — end to end. Across all
522 bundle items the only item consuming a fish above fishing@1 is
`cooked_shrimp`, a `consumable` no gear root can name, so the consumable floor
(`ctx.supply_shortfall`) is fishing's demand route.
"""

import dataclasses

from artifactsmmo_cli.ai.decisions.root import resolve_root
from artifactsmmo_cli.ai.scenario import SCENARIOS
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import ReachSkillLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.audit.open_rung_completeness import census_state


def _skills_offered(res) -> set[str]:  # type: ignore[no-untyped-def]
    return {g.skill for g in (res.root, *res.alternatives) if isinstance(g, ReachSkillLevel)}


class TestNoUndemandedCooking:
    """NOT marked `integration`: the sweep loads the committed bundle and makes
    no API call, and the pre-commit hook runs `-m "not integration"`."""

    def test_cooking_is_never_offered_without_a_tier_food_due(self, bundle_game_data):
        gd = bundle_game_data
        objective = CharacterObjective.from_game_data(gd)
        cooking = []
        for name, scenario in SCENARIOS.items():
            res = resolve_root(census_state(scenario, gd), gd, objective, NO_PROFILE_CONTEXT, None)
            if "cooking" in _skills_offered(res):
                cooking.append(name)
        assert cooking == []


def _mining_gated_state(bundle_game_data, mining: int):
    """A character whose `boots_slot` target is `iron_boots` — unblocked on
    the crafting-skill gate but whose material closure (`iron_bar` ->
    `iron_ore`) bottoms out at mining@10 — built from `l24_fisher_cooking_rung`
    by `dataclasses.replace`.

    HAND-BUILT because no committed scenario combines: (1) combat stats that
    clear `gear_target_tier` past rung 1 to the iron rung (this scenario's
    `_IRON_SET` does); (2) `gearcrafting >= 10`, so `iron_boots`
    (crafting_level 10) is not skill-blocked and surfaces as an `ObtainItem`
    seed; and (3) an empty `boots_slot`, so `iron_boots` is actually assigned
    as the slot's target. Only those fields change."""
    base = SCENARIOS["l24_fisher_cooking_rung"]
    sc = dataclasses.replace(
        base,
        skills={**base.skills, "gearcrafting": 10, "mining": mining},
        equipment={**base.equipment, "boots_slot": None})
    return census_state(sc, bundle_game_data)


class TestGatheringDemandPositiveBranch:
    def test_a_genuinely_demanded_skill_is_offered_at_the_demanded_level(
            self, bundle_game_data):
        """At mining=5, `iron_boots` needs `iron_bar` -> `iron_ore`, gated at
        mining@10. The root-plus-alternatives contain
        `ReachSkillLevel('mining', 10)` — the DEMANDED level, not `current + 1`
        (6). Kills a broken seeding side (`_seed` dropping `ObtainItem`, a
        `gather_demand` that stops walking the closure)."""
        gd = bundle_game_data
        objective = CharacterObjective.from_game_data(gd)
        state = _mining_gated_state(gd, mining=5)
        res = resolve_root(state, gd, objective, NO_PROFILE_CONTEXT, None)
        assert ReachSkillLevel(skill="mining", level=10) in (res.root, *res.alternatives)
        assert "cooking" not in _skills_offered(res)

    def test_once_satisfied_the_demanded_skill_disappears(self, bundle_game_data):
        """The mirror: raise mining to 10 and the mining root disappears. Kills
        an unconditional admission, which would still offer `mining 11`."""
        gd = bundle_game_data
        objective = CharacterObjective.from_game_data(gd)
        state = _mining_gated_state(gd, mining=10)
        res = resolve_root(state, gd, objective, NO_PROFILE_CONTEXT, None)
        assert "mining" not in _skills_offered(res)


CHAIN_CELL = "l11_band_floor"
"""A COMMITTED scenario: `cooking=12, fishing=5` — HAL's live shape (fishing 8
under a shrimp demand) at this cell's own levels."""

CHAIN_RUNG = 10
"""The fishing level `cooked_shrimp`'s closure asks for. NOT `current + 1`."""

SHORT_SHRIMP = dataclasses.replace(NO_PROFILE_CONTEXT, supply_shortfall=(("cooked_shrimp", 10),))
"""The fleet consumable floor short of its tier food, as
`consumable_floor.supply_shortfall` publishes it."""


class TestTierFoodDemandsFishing:
    def test_no_shortfall_no_fishing(self, bundle_game_data):
        """Nothing else in the catalogue asks for a fish, so without the
        floor's demand fishing is not offered: the live 2026-10-08 burn."""
        gd = bundle_game_data
        objective = CharacterObjective.from_game_data(gd)
        state = census_state(SCENARIOS[CHAIN_CELL], gd)
        assert state.skills["fishing"] < CHAIN_RUNG
        res = resolve_root(state, gd, objective, NO_PROFILE_CONTEXT, None)
        assert "fishing" not in _skills_offered(res)

    def test_a_short_tier_food_gets_a_fishing_root(self, bundle_game_data):
        """Kills a gate that drops `ctx.supply_shortfall` from the demand
        roots, and the demanded-level lookup collapsing to `current + 1`."""
        gd = bundle_game_data
        objective = CharacterObjective.from_game_data(gd)
        state = census_state(SCENARIOS[CHAIN_CELL], gd)
        res = resolve_root(state, gd, objective, SHORT_SHRIMP, None)
        assert ReachSkillLevel(skill="fishing", level=CHAIN_RUNG) in (res.root, *res.alternatives)

    def test_raising_fishing_to_the_gate_removes_the_root(self, bundle_game_data):
        gd = bundle_game_data
        objective = CharacterObjective.from_game_data(gd)
        base = SCENARIOS[CHAIN_CELL]
        state = census_state(
            dataclasses.replace(base, skills={**base.skills, "fishing": CHAIN_RUNG}), gd)
        res = resolve_root(state, gd, objective, SHORT_SHRIMP, None)
        assert "fishing" not in _skills_offered(res)

    def test_a_demanded_cooking_climb_asks_for_the_fish_its_rung_cooks(
            self, bundle_game_data):
        """`cooked_porkchop` (cooking 20) needs no fish — its closure is a
        monster drop — but the cooking climb toward it stands on
        `cooked_shrimp`, this character's grind target at cooking 12, and that
        needs fishing 10. The climb seeds `gather_demand` with its own grind
        target, so fishing is offered too. Kills a demand pass that drops the
        provisional climbs."""
        gd = bundle_game_data
        objective = CharacterObjective.from_game_data(gd)
        state = census_state(SCENARIOS[CHAIN_CELL], gd)
        due = dataclasses.replace(NO_PROFILE_CONTEXT, supply_shortfall=(("cooked_porkchop", 10),))
        res = resolve_root(state, gd, objective, due, None)
        offered = (res.root, *res.alternatives)
        assert ReachSkillLevel(skill="cooking", level=20) in offered
        assert ReachSkillLevel(skill="fishing", level=CHAIN_RUNG) in offered
