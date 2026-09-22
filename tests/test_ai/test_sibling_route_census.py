"""The sibling-route differential: eligible, priced, and load-bearing are three questions."""

from dataclasses import replace

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import ItemCatalog, ItemStats
from artifactsmmo_cli.ai.location_catalog import LocationCatalog
from artifactsmmo_cli.ai.recipe_catalog import RecipeCatalog
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.world_state import WorldState
from artifactsmmo_cli.audit.sibling_route_census import (
    SiblingVerdict,
    sibling_route_verdicts,
)
from tests.test_ai.fixtures import make_state


def test_saving_is_the_action_difference() -> None:
    v = SiblingVerdict(item="air_ring", skill="jewelrycrafting", required_level=15,
                       held_level=13, best_sibling_level=20, priced=True,
                       actions_with=8, actions_without=40)
    assert v.saving == 32


def test_a_priced_route_that_saves_nothing_is_not_load_bearing() -> None:
    v = SiblingVerdict(item="air_ring", skill="jewelrycrafting", required_level=15,
                       held_level=13, best_sibling_level=20, priced=True,
                       actions_with=40, actions_without=40)
    assert v.saving == 0
    assert v.load_bearing is False


def test_a_load_bearing_route_saves_actions() -> None:
    v = SiblingVerdict(item="air_ring", skill="jewelrycrafting", required_level=15,
                       held_level=13, best_sibling_level=20, priced=True,
                       actions_with=8, actions_without=40)
    assert v.load_bearing is True


def test_an_unpriced_route_is_never_load_bearing_even_if_the_costs_differ() -> None:
    # Defensive: if the two prices differ while no sibling route was returned, the
    # difference came from somewhere else and must not be credited to this route.
    v = SiblingVerdict(item="air_ring", skill="jewelrycrafting", required_level=15,
                       held_level=13, best_sibling_level=20, priced=False,
                       actions_with=8, actions_without=40)
    assert v.load_bearing is False


class _FleetStore:
    """This test module's OWN store stand-in: has seen exactly one fleet supply
    request (`fleet_supply_request_cycles` positive, so
    `_sibling_craft_option`'s pricing gate is satisfied) and, optionally, an
    observed grind rate per skill (`skill_grind_rate`, so `_gated_craft_option`
    can compete for the skills the caller names in `grind_rates`). For
    `hexstaff`'s skill (weaponcrafting) no workshop is known anywhere in
    `census_world`'s `GameData`, so `_gated_craft_option` declines before it
    would ever ask `skill_grind_rate` regardless of what this store returns —
    the sibling route is the only deferred option `hexstaff` can produce. For
    `gearclasp`'s skill (gearcrafting) a workshop IS known, so a caller that
    passes `grind_rates={"gearcrafting": ...}` gives `_gated_craft_option` a
    real, competing route."""

    def __init__(self, grind_rates: dict[str, float] | None = None) -> None:
        self._grind_rates = grind_rates or {}

    def fleet_supply_request_cycles(self) -> float | None:
        return 15.0

    def skill_grind_rate(self, skill: str) -> float | None:
        return self._grind_rates.get(skill)

    def fleet_skill_grind_rate(self, skill: str) -> float | None:
        return None


@pytest.fixture
def census_world() -> tuple[WorldState, GameData]:
    """A DECLARED, SELF-CONTAINED world, built for this test module alone —
    NOT the shared `gamedata_bundle.json` scenario fixture
    `test_acquisition_cost_wrapper.py` uses. Reusing one shared `GameData`
    across scenarios has already produced three vacuous measurements and a
    shipped false retraction in this codebase
    (`feedback_scenario_declares_its_world`), so this census gets its own,
    minimal, single-purpose world instead.

    Two skill-gated items, chosen to give the census two DIFFERENT live
    outcomes rather than one:

    `hexstaff` (weaponcrafting 10) has NO route this character can serve on
    its own: no vendor sells it, no resource drops it, no monster drops it,
    and no workshop for weaponcrafting is known (so even the character's OWN
    craft route, and the gated-craft deferred route, are both absent). Its
    one recipe material, `hex_wood`, is already fully held — chosen so the
    sibling craft's price is a small, finite number (one craft action, one
    bank hop, one paid-once unlock) while the no-sibling price is the
    `UNOBTAINABLE_PER_UNIT` ceiling (`hexstaff` has no route AT ALL without
    the sibling option), which is what makes ITS load-bearing difference
    unambiguous rather than a close call.

    `gearclasp` (gearcrafting 8) is the outpriced case the `hexstaff`-only
    fixture could never exercise: a workshop for gearcrafting IS known, so a
    caller that hands `_FleetStore` a gearcrafting grind rate gives
    `_gated_craft_option` a real, cheap competing route (one level away, sized
    to grind in a single cycle) alongside the sibling route (a 15-cycle fleet
    request). The sibling route is genuinely PRICED (`route_options` returns
    it), but the cost walk picks the cheaper gated-craft route every time, so
    it is never LOAD-BEARING — and because `_gated_craft_option` does not read
    `ctx.sibling_skills` at all, a `gearclasp` verdict has a `kind=CRAFT`
    route even when `sibling_skills` is empty. That is what makes it pin the
    matcher: a regression from `unlock.startswith("sibling:")` to
    `kind == SourceKind.CRAFT.value` would call `gearclasp` PRICED under an
    empty-siblings ctx too, where the correct answer is False. Its recipe
    material, `gear_bolt`, is likewise fully held, for the same reason
    `hex_wood` is.
    """
    game_data = GameData(
        items=ItemCatalog(stats={
            "hexstaff": ItemStats(code="hexstaff", level=10, type_="weapon",
                                  crafting_skill="weaponcrafting", crafting_level=10),
            "hex_wood": ItemStats(code="hex_wood", level=1, type_="resource"),
            "gearclasp": ItemStats(code="gearclasp", level=8, type_="ring",
                                   crafting_skill="gearcrafting", crafting_level=8),
            "gear_bolt": ItemStats(code="gear_bolt", level=1, type_="resource"),
        }),
        recipes_catalog=RecipeCatalog(
            crafting_recipes={"hexstaff": {"hex_wood": 4},
                              "gearclasp": {"gear_bolt": 2}},
            craft_yields={"hexstaff": 1, "gearclasp": 1},
        ),
        world=LocationCatalog(workshop_locations={"gearcrafting": (2, 2)}),
    )
    state = make_state(
        skills={"weaponcrafting": 1, "gearcrafting": 7, "jewelrycrafting": 1,
                "cooking": 1, "alchemy": 1, "mining": 1, "woodcutting": 1,
                "fishing": 1},
        inventory={"hex_wood": 4, "gear_bolt": 2},
        skill_xp={"gearcrafting": 0},
        skill_max_xp={"gearcrafting": 10},
    )
    return state, game_data


def test_the_eligible_gated_item_is_priced_and_load_bearing(
        census_world: tuple[WorldState, GameData]) -> None:
    """THE POINT. `hexstaff` is ELIGIBLE (held 1 < required 10 <= sibling 10);
    its only route in this fixture is the sibling craft, so it must be PRICED;
    and without that route the item has no route at all, so it must be
    LOAD-BEARING. All three questions land on the same item, for once, and the
    census must say so on all three.

    Also exercises the skip branch: `hex_wood` names no `crafting_skill`, so it
    must be silently absent from the result rather than producing a hollow
    verdict."""
    state, game_data = census_world
    ctx = replace(NO_PROFILE_CONTEXT, sibling_skills={"weaponcrafting": 10})
    store = _FleetStore()

    verdicts = sibling_route_verdicts(
        state, game_data, ctx, store, ["hexstaff", "hex_wood"])

    assert [v.item for v in verdicts] == ["hexstaff"], \
        "hex_wood names no crafting skill and must be skipped, not stubbed"
    v = verdicts[0]
    assert v.skill == "weaponcrafting"
    assert v.held_level < v.required_level <= v.best_sibling_level, "ELIGIBLE"
    assert v.priced is True, "PRICED"
    assert v.load_bearing is True, "LOAD-BEARING"
    assert v.saving > 0


def test_an_outpriced_sibling_route_is_priced_but_not_load_bearing(
        census_world: tuple[WorldState, GameData]) -> None:
    """THE MOST LIKELY LIVE OUTCOME, and the one the four value-object tests
    at the top of this file cannot exercise on their own: they hand-construct
    a `SiblingVerdict` directly, so they say nothing about whether the REAL
    compute path (`route_options` + `acquisition_actions`) can actually land
    on `priced=True, load_bearing=False`.

    `gearclasp` is ELIGIBLE (held 7 < required 8 <= sibling 8) and its sibling
    route IS in `route_options` (`priced=True`), but the character's own
    gated-craft grind — one level away, sized to a single cycle — is far
    cheaper than the sibling's 15-cycle fleet request, so the cost walk picks
    the grind every time REGARDLESS of whether the sibling route exists.
    `actions_with` and `actions_without` therefore land on the SAME number:
    saving is exactly 0, not merely small, and `load_bearing` must be False.

    Distinguishing "outpriced" from "absent" (the `hexstaff` case above) is
    the entire point of keeping `priced` and `load_bearing` separate — an
    audit that only counted `load_bearing` verdicts would report `gearclasp`
    identically to an item with no sibling capability at all, and nobody
    reading "0 load-bearing" would know whether the fleet has no sibling
    capacity or has capacity nothing ever needs."""
    state, game_data = census_world
    ctx = replace(NO_PROFILE_CONTEXT,
                  sibling_skills={"weaponcrafting": 10, "gearcrafting": 8})
    store = _FleetStore(grind_rates={"gearcrafting": 100.0})

    verdicts = sibling_route_verdicts(state, game_data, ctx, store, ["gearclasp"])

    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.held_level < v.required_level <= v.best_sibling_level, "ELIGIBLE"
    assert v.priced is True, "PRICED: route_options returns the sibling option"
    assert v.saving == 0
    assert v.load_bearing is False, "OUTPRICED: the character's own grind wins"


def test_load_bearing_is_provable_by_emptying_sibling_skills(
        census_world: tuple[WorldState, GameData]) -> None:
    """THE LOAD-BEARING PROOF the task brief requires before the fixtures
    above are trusted: with `ctx.sibling_skills` emptied, `_sibling_craft_option`
    declines before it ever looks at anything else
    (`ctx.sibling_skills.get(skill, 0) < stats.crafting_level` is its second
    gate), so `route_options` can return no `sibling:` option and `priced`
    must flip to False for both items — taking `load_bearing` with it.
    Observed while developing this test (recorded in the task report): with
    the real `census_world` fixture and this empty-siblings ctx, both items
    also fail the ELIGIBLE check (`best_sibling_level` is now 0), so this is
    the same "no sibling in the fleet" case every single-character run takes.

    `gearclasp` is the case that actually distinguishes `unlock.startswith(
    "sibling:")` from `kind == SourceKind.CRAFT.value`: its gated-craft route
    does NOT read `ctx.sibling_skills`, so it is STILL in `route_options` here
    (`kind=CRAFT`, `unlock="skill:gearcrafting:8"`) even though no sibling
    route is. The correct matcher must say `priced=False` anyway; a
    `kind`-matching regression would see that surviving `kind=CRAFT` route and
    say `priced=True`, which `hexstaff` alone (no `kind=CRAFT` route survives
    it at all) could never catch."""
    state, game_data = census_world
    ctx = replace(NO_PROFILE_CONTEXT, sibling_skills={})
    store = _FleetStore(grind_rates={"gearcrafting": 100.0})

    verdicts = sibling_route_verdicts(
        state, game_data, ctx, store, ["hexstaff", "gearclasp"])

    assert [v.item for v in verdicts] == ["hexstaff", "gearclasp"]
    hexstaff_v, gearclasp_v = verdicts

    assert hexstaff_v.best_sibling_level < hexstaff_v.required_level, \
        "no longer ELIGIBLE either"
    assert hexstaff_v.priced is False
    assert hexstaff_v.load_bearing is False

    assert gearclasp_v.best_sibling_level < gearclasp_v.required_level, \
        "no longer ELIGIBLE either"
    assert gearclasp_v.priced is False, (
        "no sibling clears gearcrafting here, so route_options must return no "
        "sibling: route -- a kind=CRAFT match would wrongly see the surviving "
        "gated-craft (skill:gearcrafting:8) route and call this PRICED")
    assert gearclasp_v.load_bearing is False
