"""The sibling-route differential: eligible, priced, and load-bearing are three questions."""

from dataclasses import replace

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import ItemCatalog, ItemStats
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
    `_sibling_craft_option`'s pricing gate is satisfied) and nothing else. No
    workshop is known anywhere in `census_world`'s `GameData`, so
    `_gated_craft_option` declines before it would ever ask a store method —
    the sibling route is the only deferred option this fixture's world can
    produce, which is what isolates it."""

    def fleet_supply_request_cycles(self) -> float | None:
        return 15.0


@pytest.fixture
def census_world() -> tuple[WorldState, GameData]:
    """A DECLARED, SELF-CONTAINED world, built for this test module alone —
    NOT the shared `gamedata_bundle.json` scenario fixture
    `test_acquisition_cost_wrapper.py` uses. Reusing one shared `GameData`
    across scenarios has already produced three vacuous measurements and a
    shipped false retraction in this codebase
    (`feedback_scenario_declares_its_world`), so this census gets its own,
    minimal, single-purpose world instead.

    One skill-gated weapon, `hexstaff` (weaponcrafting 10), with NO route
    this character can serve on its own: no vendor sells it, no resource
    drops it, no monster drops it, and no workshop is known (so even the
    character's OWN craft route, and the gated-craft deferred route, are both
    absent). Its one recipe material, `hex_wood`, is already fully held —
    chosen so the sibling craft's price is a small, finite number (one craft
    action, one bank hop, one paid-once unlock) while the no-sibling price is
    the `UNOBTAINABLE_PER_UNIT` ceiling (`hexstaff` has no route AT ALL
    without the sibling option), which is what makes the load-bearing
    difference unambiguous rather than a close call.
    """
    game_data = GameData(
        items=ItemCatalog(stats={
            "hexstaff": ItemStats(code="hexstaff", level=10, type_="weapon",
                                  crafting_skill="weaponcrafting", crafting_level=10),
            "hex_wood": ItemStats(code="hex_wood", level=1, type_="resource"),
        }),
        recipes_catalog=RecipeCatalog(
            crafting_recipes={"hexstaff": {"hex_wood": 4}},
            craft_yields={"hexstaff": 1},
        ),
    )
    state = make_state(
        skills={"weaponcrafting": 1, "gearcrafting": 1, "jewelrycrafting": 1,
                "cooking": 1, "alchemy": 1, "mining": 1, "woodcutting": 1,
                "fishing": 1},
        inventory={"hex_wood": 4},
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


def test_load_bearing_is_provable_by_emptying_sibling_skills(
        census_world: tuple[WorldState, GameData]) -> None:
    """THE LOAD-BEARING PROOF the task brief requires before the fixture above
    is trusted: with `ctx.sibling_skills` emptied, `_sibling_craft_option`
    declines before it ever looks at anything else
    (`ctx.sibling_skills.get(skill, 0) < stats.crafting_level` is its second
    gate), so `route_options` can return no `sibling:` option and `priced`
    must flip to False — taking `load_bearing` with it. Observed while
    developing this test (recorded in the task report): with the real
    `census_world` fixture and this empty-siblings ctx, `hexstaff` also fails
    the ELIGIBLE check (`best_sibling_level` is now 0), so this is the same
    "no sibling in the fleet" case every single-character run takes."""
    state, game_data = census_world
    ctx = replace(NO_PROFILE_CONTEXT, sibling_skills={})
    store = _FleetStore()

    verdicts = sibling_route_verdicts(state, game_data, ctx, store, ["hexstaff"])

    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.best_sibling_level < v.required_level, "no longer ELIGIBLE either"
    assert v.priced is False
    assert v.load_bearing is False
