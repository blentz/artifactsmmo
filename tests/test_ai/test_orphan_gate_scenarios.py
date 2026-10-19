"""The orphan skill gate, driven over the REAL walk (`resolve_root`), not over
`_orphan_skill_roots` called directly with an injected `offered`.

USER 2026-10-08, "Only when demanded": a skill climbs only when the goal-action
DAG demands it (gear, the consumable floor's tier food, a task). Cooking rises
when a better tier food is due, not before.

All suites run against the committed bundle
(`tests/test_ai/scenarios/fixtures/gamedata_bundle.json`, loaded exactly as
the deleted open-rung census loaded it — see `conftest.bundle_game_data`). None
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
from fractions import Fraction

from artifactsmmo_cli.ai.decisions.root import resolve_root
from artifactsmmo_cli.ai.gear_objective_context import attach_gear_objective
from artifactsmmo_cli.ai.gear_objective_result import GearObjective, GearPiece
from artifactsmmo_cli.ai.scenario import SCENARIOS, derived_scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import ReachSkillLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from tests.test_ai.scenarios.routing import scenario_resolution, skills_offered


def _skills_offered(res) -> set[str]:  # type: ignore[no-untyped-def]
    return {g.skill for g in (res.root, *res.alternatives) if isinstance(g, ReachSkillLevel)}


def _cycle(state, gd, ctx):  # type: ignore[no-untyped-def]
    """`ctx` with the cycle's gear objective attached, as the player attaches
    it (ruling W): the walk's roots, and so its demand, are the live cycle's."""
    return attach_gear_objective(state, gd, ctx, None)


class TestNoUndemandedCooking:
    """NOT marked `integration`: the sweep loads the committed bundle and makes
    no API call, and the pre-commit hook runs `-m "not integration"`."""

    def test_cooking_is_never_offered_without_a_tier_food_due(self, bundle_game_data):
        gd = bundle_game_data
        cooking = []
        for name in SCENARIOS:
            if "cooking" in skills_offered(scenario_resolution(name, gd)):
                cooking.append(name)
        assert cooking == []


def _mining_gated_state(bundle_game_data, mining: int):
    """A character whose `boots_slot` target is `iron_boots` — unblocked on
    the crafting-skill gate but whose material closure (`iron_bar` ->
    `iron_ore`) bottoms out at mining@10 — built from `l24_fisher_cooking_rung`
    by `dataclasses.replace`.

    HAND-BUILT with `gearcrafting >= 10`, so `iron_boots` (crafting_level 10)
    is not skill-blocked and surfaces as an `ObtainItem` seed, and an empty
    `boots_slot`. Only those fields change; the objective naming the boots
    is `_BOOTS`."""
    base = SCENARIOS["l24_fisher_cooking_rung"]
    sc = dataclasses.replace(
        base,
        skills={**base.skills, "gearcrafting": 10, "mining": mining},
        equipment={**base.equipment, "boots_slot": None})
    return derived_scenario_state(sc, bundle_game_data)


_BOOTS = dataclasses.replace(NO_PROFILE_CONTEXT, gear_objective=GearObjective(
    "pig", {"boots_slot": "iron_boots"}, Fraction(1),
    (GearPiece("boots_slot", "iron_boots", 0, Fraction(1), Fraction(1)),)))
"""A gear objective missing exactly `iron_boots`: these tests mean that one
piece, so the objective is built explicitly (ruling W)."""


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
        res = resolve_root(state, gd, objective, _BOOTS, None)
        assert ReachSkillLevel(skill="mining", level=10) in (res.root, *res.alternatives)
        assert "cooking" not in _skills_offered(res)

    def test_once_satisfied_the_demanded_skill_disappears(self, bundle_game_data):
        """The mirror: raise mining to 10 and the mining root disappears. Kills
        an unconditional admission, which would still offer `mining 11`."""
        gd = bundle_game_data
        objective = CharacterObjective.from_game_data(gd)
        state = _mining_gated_state(gd, mining=10)
        res = resolve_root(state, gd, objective, _BOOTS, None)
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
        state = derived_scenario_state(SCENARIOS[CHAIN_CELL], gd)
        assert state.skills["fishing"] < CHAIN_RUNG
        res = resolve_root(state, gd, objective, _cycle(state, gd, NO_PROFILE_CONTEXT), None)
        assert "fishing" not in _skills_offered(res)

    def test_a_short_tier_food_gets_a_fishing_root(self, bundle_game_data):
        """Kills a gate that drops `ctx.supply_shortfall` from the demand
        roots, and the demanded-level lookup collapsing to `current + 1`."""
        gd = bundle_game_data
        objective = CharacterObjective.from_game_data(gd)
        state = derived_scenario_state(SCENARIOS[CHAIN_CELL], gd)
        res = resolve_root(state, gd, objective, _cycle(state, gd, SHORT_SHRIMP), None)
        assert ReachSkillLevel(skill="fishing", level=CHAIN_RUNG) in (res.root, *res.alternatives)

    def test_raising_fishing_to_the_gate_removes_the_root(self, bundle_game_data):
        gd = bundle_game_data
        objective = CharacterObjective.from_game_data(gd)
        base = SCENARIOS[CHAIN_CELL]
        state = derived_scenario_state(
            dataclasses.replace(base, skills={**base.skills, "fishing": CHAIN_RUNG}), gd)
        res = resolve_root(state, gd, objective, _cycle(state, gd, SHORT_SHRIMP), None)
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
        state = derived_scenario_state(SCENARIOS[CHAIN_CELL], gd)
        due = dataclasses.replace(NO_PROFILE_CONTEXT, supply_shortfall=(("cooked_porkchop", 10),))
        res = resolve_root(state, gd, objective, _cycle(state, gd, due), None)
        offered = (res.root, *res.alternatives)
        assert ReachSkillLevel(skill="cooking", level=20) in offered
        assert ReachSkillLevel(skill="fishing", level=CHAIN_RUNG) in offered


class TestOnlyTheProducerClimbsForFood:
    """Spec 2026-10-13 §4: only the food's owner makes it. A sibling with a
    share of the fleet's food shortfall is NOT offered the fishing climb its
    `cooked_shrimp` closure would demand while a live fisher holds the role;
    the fisher, and a character in a fleet with no fisher, still are."""

    def _fishing_offered(self, gd, role, fleet_roles) -> bool:  # type: ignore[no-untyped-def]
        objective = CharacterObjective.from_game_data(gd)
        state = derived_scenario_state(SCENARIOS[CHAIN_CELL], gd)
        ctx = dataclasses.replace(SHORT_SHRIMP, role=role, fleet_roles=fleet_roles)
        res = resolve_root(state, gd, objective, _cycle(state, gd, ctx), None)
        return ReachSkillLevel(skill="fishing", level=CHAIN_RUNG) in (res.root, *res.alternatives)

    def test_a_sibling_of_a_live_fisher_is_not_offered_the_climb(self, bundle_game_data):
        assert not self._fishing_offered(
            bundle_game_data, "miner", frozenset({"fisher", "miner"}))

    def test_the_fisher_is_offered_the_climb(self, bundle_game_data):
        assert self._fishing_offered(
            bundle_game_data, "fisher", frozenset({"fisher", "miner"}))

    def test_a_fleet_without_a_fisher_still_climbs(self, bundle_game_data):
        assert self._fishing_offered(bundle_game_data, "miner", frozenset({"miner"}))

    def test_a_potion_shortfall_is_read_for_every_role(self, bundle_game_data):
        """Potions are untouched (spec non-goal): a miner beside a live
        alchemist is still offered the alchemy climb `minor_health_potion`
        (alchemy 20) demands. Kills a filter that drops every non-producer
        row instead of only the FOOD rows."""
        gd = bundle_game_data
        objective = CharacterObjective.from_game_data(gd)
        state = derived_scenario_state(SCENARIOS[CHAIN_CELL], gd)
        ctx = dataclasses.replace(
            NO_PROFILE_CONTEXT, supply_shortfall=(("minor_health_potion", 10),),
            role="miner", fleet_roles=frozenset({"alchemist", "miner"}))
        res = resolve_root(state, gd, objective, _cycle(state, gd, ctx), None)
        assert ReachSkillLevel(skill="alchemy", level=20) in (res.root, *res.alternatives)
