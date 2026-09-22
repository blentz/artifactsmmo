"""`root_sibling_verdicts`: classifies the ROOT WALK's own candidates, not the
catalogue. One test per rule `audit/root_sibling_census.py`'s module
docstring states.

`resolve_root` is monkeypatched to return a hand-built `RootResolution` in
every test here. Driving the real tier-graph walk end to end
(`tests/test_ai/test_decisions_root.py` already does exactly that, one test
per node) is a different module's job; this module's job is the CONSUMER
that classifies whatever `resolve_root` hands back, and the trap the task
brief warns about is rebuilding `alternatives` from the walk's inputs, not
supplying a `RootResolution` directly as a controlled return value -- that is
ordinary substitution of a collaborator this module only calls once and reads
the return value of.

A SEPARATE, DECLARED WORLD backs the one test (rule 3) that needs `route_
options`/`acquisition_actions` to actually run: a single skill-gated item,
`sibling_gear`, with no known weaponcrafting workshop and its one recipe
material fully held, mirroring `test_sibling_route_census.py`'s own
`hexstaff` fixture so the sibling route is unambiguously the item's ONLY
route. This module does not import or reuse that fixture --
`feedback_scenario_declares_its_world` -- it declares its own, minimal and
single-purpose.
"""

from dataclasses import replace

import pytest

import artifactsmmo_cli.audit.root_sibling_census as root_sibling_census
from artifactsmmo_cli.ai.decisions.root import RootResolution
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import ItemCatalog, ItemStats
from artifactsmmo_cli.ai.recipe_catalog import RecipeCatalog
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel, ReachSkillLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.world_state import WorldState
from artifactsmmo_cli.audit.root_sibling_census import root_sibling_verdicts
from artifactsmmo_cli.audit.sibling_route_census import sibling_route_verdicts
from tests.test_ai.fixtures import make_state


class _Store:
    """This test module's own store stand-in -- has seen exactly one fleet
    supply request (so `_sibling_craft_option`'s pricing gate is open) and no
    observed grind rate for any skill, so `_gated_craft_option` never has a
    competing route to offer. Also stands in for `resolve_root`'s `history`
    parameter, which every test here bypasses by monkeypatching `resolve_root`
    itself -- its shape is never read."""

    def fleet_supply_request_cycles(self) -> float | None:
        return 15.0

    def skill_grind_rate(self, skill: str) -> float | None:
        return None

    def fleet_skill_grind_rate(self, skill: str) -> float | None:
        return None


def _resolution(root: object, alternatives: tuple = ()) -> RootResolution:
    return RootResolution(root=root, alternatives=alternatives, trail=(),
                          aged=False, blocked_target=None)


def _empty_world() -> tuple[WorldState, GameData]:
    """A world with no items at all. Fine for rules 1/2/4: none of those
    tests assert on `verdict`, and `sibling_route_verdicts` skips any item
    code it cannot find a recipe/crafting_skill for -- see its own
    docstring -- rather than erroring, so an `ObtainItem` naming a code this
    catalogue has never heard of still produces a row, just one with
    `verdict=None`."""
    return make_state(), GameData()


@pytest.fixture
def root_census_world() -> tuple[WorldState, GameData]:
    """One skill-gated item, `sibling_gear` (weaponcrafting 10): no known
    weaponcrafting workshop anywhere in this `GameData`, so the character's
    own gated-craft route is absent and the sibling route is this item's
    ONLY route -- the same shape `test_sibling_route_census.py`'s `hexstaff`
    fixture uses, and for the same reason: it makes PRICED and LOAD-BEARING
    both unambiguous rather than a close call. Its one recipe material,
    `gear_wood`, is already fully held so the sibling craft's own price stays
    a small, finite number of actions."""
    game_data = GameData(
        items=ItemCatalog(stats={
            "sibling_gear": ItemStats(code="sibling_gear", level=10, type_="weapon",
                                      crafting_skill="weaponcrafting", crafting_level=10),
            "gear_wood": ItemStats(code="gear_wood", level=1, type_="resource"),
        }),
        recipes_catalog=RecipeCatalog(
            crafting_recipes={"sibling_gear": {"gear_wood": 4}},
            craft_yields={"sibling_gear": 1},
        ),
    )
    state = make_state(
        skills={"weaponcrafting": 1, "gearcrafting": 1, "jewelrycrafting": 1,
                "cooking": 1, "alchemy": 1, "mining": 1, "woodcutting": 1,
                "fishing": 1},
        inventory={"gear_wood": 4},
    )
    return state, game_data


def test_candidate_order_is_preserved_and_exactly_one_root_is_chosen(monkeypatch) -> None:
    """Rule 1 (root resolved): the candidate set is `[root, *alternatives]`,
    in that order, and exactly one row -- the one built from `root` -- carries
    `chosen=True`."""
    state, game_data = _empty_world()
    root = ObtainItem(code="x")
    alt_a = ReachCharLevel(level=3)
    alt_b = ObtainItem(code="y")
    monkeypatch.setattr(root_sibling_census, "resolve_root",
                        lambda *a, **k: _resolution(root, (alt_a, alt_b)))

    rows = root_sibling_verdicts(state, game_data, CharacterObjective.from_game_data(game_data),
                                 NO_PROFILE_CONTEXT, _Store())

    assert [r.root_repr for r in rows] == [repr(root), repr(alt_a), repr(alt_b)], \
        "candidate order must match [root, *alternatives] exactly"
    chosen = [r for r in rows if r.chosen]
    assert len(chosen) == 1
    assert chosen[0].root_repr == repr(root)


def test_a_wall_resolution_filters_the_none_root_and_chooses_nothing(monkeypatch) -> None:
    """Rule 1 (the wall case): `resolve_root` can return `root=None`
    (`CanIClearMyTier`'s own docstring). The candidate set then drops that
    leading `None` and reports only the alternatives, and -- because nothing
    was actually chosen -- no row carries `chosen=True`.

    This is also the fixture Step 5's mutation proof needs: with `root=None`,
    `[resolution.root, *resolution.alternatives]` filtered to non-None
    STARTS WITH THE FIRST ALTERNATIVE, so a `chosen = index == 0` mutant
    would misreport it as chosen. Only an identity check against
    `resolution.root` (which is `None` here, and no `MetaGoal` is ever `is
    None`) gets this right."""
    state, game_data = _empty_world()
    alt_a = ReachCharLevel(level=3)
    alt_b = ObtainItem(code="y")
    monkeypatch.setattr(root_sibling_census, "resolve_root",
                        lambda *a, **k: _resolution(None, (alt_a, alt_b)))

    rows = root_sibling_verdicts(state, game_data, CharacterObjective.from_game_data(game_data),
                                 NO_PROFILE_CONTEXT, _Store())

    assert [r.root_repr for r in rows] == [repr(alt_a), repr(alt_b)], \
        "the None root must be filtered, not stand in as a row of its own"
    assert not any(r.chosen for r in rows), \
        "the wall resolved nothing, so no candidate may be marked chosen"


def test_a_root_naming_no_item_is_reported_with_none_item_and_none_verdict(monkeypatch) -> None:
    """Rule 2: `ReachCharLevel`/`ReachSkillLevel` name no item. The row is
    still produced -- dropping it would make the denominator lie about "the
    chosen root names no item" being a real, reportable answer -- with
    `item=None` and `verdict=None` rather than a fabricated stand-in for
    either."""
    state, game_data = _empty_world()
    root = ReachSkillLevel(skill="mining", level=5)
    monkeypatch.setattr(root_sibling_census, "resolve_root",
                        lambda *a, **k: _resolution(root))

    rows = root_sibling_verdicts(state, game_data, CharacterObjective.from_game_data(game_data),
                                 NO_PROFILE_CONTEXT, _Store())

    assert len(rows) == 1
    row = rows[0]
    assert row.root_repr == repr(root)
    assert row.item is None
    assert row.verdict is None
    assert row.chosen is True


def test_a_root_naming_an_item_is_priced_by_the_existing_sibling_census(
        monkeypatch, root_census_world: tuple[WorldState, GameData]) -> None:
    """Rule 3: an `ObtainItem` root is priced by calling `sibling_route_
    verdicts` over exactly that one item -- not re-derived. Proved by
    equality against an independent direct call to that same census, so a
    future edit that reimplements ELIGIBLE/PRICED/LOAD-BEARING here instead
    of delegating would be caught even if the reimplementation happened to
    agree on this one fixture's booleans."""
    state, game_data = root_census_world
    ctx = replace(NO_PROFILE_CONTEXT, sibling_skills={"weaponcrafting": 10})
    store = _Store()
    root = ObtainItem(code="sibling_gear")
    monkeypatch.setattr(root_sibling_census, "resolve_root",
                        lambda *a, **k: _resolution(root))

    rows = root_sibling_verdicts(
        state, game_data, CharacterObjective.from_game_data(game_data), ctx, store)

    assert len(rows) == 1
    row = rows[0]
    assert row.item == "sibling_gear"
    assert row.chosen is True
    expected = sibling_route_verdicts(state, game_data, ctx, store, ["sibling_gear"])
    assert expected, "fixture must actually name a skill-gated craftable item"
    assert row.verdict == expected[0]
    assert row.verdict is not None
    assert row.verdict.priced is True, "ELIGIBLE and PRICED given this fixture's sibling_skills"
    assert row.verdict.load_bearing is True, "the sibling route is this item's ONLY route here"
