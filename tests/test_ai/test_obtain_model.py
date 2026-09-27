"""Phase 1 step 1: the obtain model, built beside `obtain_sources`.

The pin is `test_legacy_policy_reproduces_obtain_sources_everywhere`: under
`LEGACY`, `ready(item)` equals `obtain_sources(item)` for every item of real
game data in every scenario world, with the bank open and locked. The other
tests cover what that sweep cannot: behaviour the scenario worlds never exhibit
(two buyers for one surplus item) and the non-legacy policies later steps turn on.
"""

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.obtain_model.gate import Gate, GateKind
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import LEGACY, Policy
from artifactsmmo_cli.ai.obtain_model.route import Route
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.world_state import GOLD_CODE, WorldState
from artifactsmmo_cli.audit.obtain_model_census import census_items, legacy_differences

BUNDLE = Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json"
NOW = datetime(2026, 9, 27, tzinfo=UTC)
OPEN = Policy(all_gather_routes=True, gather_skill_gate=True, event_vendors=True)


def _ctx(bank_accessible: bool = True) -> SelectionContext:
    return SelectionContext(bank_accessible=bank_accessible, bank_required_level=0,
                            bank_unlock_monster=None, initial_xp=0,
                            task_exchange_min_coins=0, combat_monster=None)


def _worlds() -> Iterator[tuple[str, WorldState, GameData]]:
    cache: dict[tuple[bool, frozenset[str]], GameData] = {}
    for name, sc in SCENARIOS.items():
        key = (sc.ge_market, frozenset(sc.unlocked_achievements))
        if key not in cache:
            cache[key] = load_bundle_game_data(BUNDLE, with_ge_orders=sc.ge_market,
                                               completed_achievements=key[1])
        yield name, scenario_state(sc, cache[key]), cache[key]


@pytest.fixture(scope="module")
def world() -> tuple[WorldState, GameData]:
    gd = load_bundle_game_data(BUNDLE, with_ge_orders=True)
    return scenario_state(SCENARIOS["l20_band_entry"], gd), gd


def test_legacy_policy_reproduces_obtain_sources_everywhere() -> None:
    compared = 0
    for name, state, gd in _worlds():
        items = census_items(gd)
        for bank in (True, False):
            differences = legacy_differences(state, gd, _ctx(bank), NOW, items)
            assert differences == [], f"{name} bank={bank}: {differences[:3]}"
            compared += len(items)
    assert compared > 40_000  # every item of every world, both bank states


def test_routes_are_memoised_per_item(world: tuple[WorldState, GameData]) -> None:
    state, gd = world
    model = ObtainModel(state, gd, _ctx(), NOW)
    assert model.routes("copper_bar") is model.routes("copper_bar")


def test_every_resource_that_drops_an_item_is_a_route_with_its_skill_gate(
        world: tuple[WorldState, GameData]) -> None:
    """D-A / D-B: legacy offered only the most frequent dropper and never checked
    the gathering skill. The model offers every dropper and records the gate."""
    state, gd = world
    item = next(i for i in sorted(gd.gatherable_drop_items())
                if len({res for res, table in gd.resource_drops_full.items()
                        for code, *_ in table if code == i}) > 1)
    routes = [r for r in ObtainModel(state, gd, _ctx(), NOW).routes(item)
              if r.kind is SourceKind.GATHER]
    assert len(routes) > 1
    assert sum(r.primary for r in routes) == 1 and routes[0].primary
    assert all(any(g.kind is GateKind.GATHER_SKILL for g in r.gates) for r in routes
               if gd.resource_skill_level(r.via) is not None)


def test_a_primary_only_resource_is_still_offered(world: tuple[WorldState, GameData]) -> None:
    """An item only the primary-drop map knows (absent from every full drop
    table) falls back to that map, as `resource_for_drop` does."""
    state, gd = world
    resource, item = "fallback_rocks", "fallback_ore"
    with (patch.object(GameData, "resource_drops_full", new={}),
          patch.object(GameData, "resource_drops", new={resource: item}),
          patch.object(GameData, "resource_for_drop", return_value=(resource, 1)),
          patch.object(GameData, "resource_skill_level", return_value=None)):
        [route] = ObtainModel(state, gd, _ctx(), NOW).routes(item)
    assert (route.kind, route.via, route.primary) == (SourceKind.GATHER, resource, True)
    assert [g.kind for g in route.gates] == [GateKind.SPAWN_LIVE]


class TestPolicy:
    def _route(self, kind: SourceKind, *gates: Gate, primary: bool = True) -> Route:
        return Route("x", kind, "v", 1, 1, gates, primary=primary)

    def test_the_gather_skill_gate_counts_only_when_enforced(self) -> None:
        route = self._route(SourceKind.GATHER, Gate(GateKind.GATHER_SKILL, "mining", False, 10))
        assert LEGACY.ready(route) and not OPEN.ready(route)

    def test_a_non_primary_gather_route_needs_all_gather_routes(self) -> None:
        route = self._route(SourceKind.GATHER, primary=False)
        assert not LEGACY.admits(route) and OPEN.admits(route)

    def test_event_vendors_swap_permanence_for_tradeability(self) -> None:
        event_vendor_open_now = self._route(
            SourceKind.BUY, Gate(GateKind.VENDOR_PERMANENT, "npc", False),
            Gate(GateKind.VENDOR_TRADEABLE, "npc", True))
        assert not LEGACY.ready(event_vendor_open_now) and OPEN.ready(event_vendor_open_now)
        permanent_but_closed = self._route(
            SourceKind.BUY, Gate(GateKind.VENDOR_PERMANENT, "npc", True),
            Gate(GateKind.VENDOR_TRADEABLE, "npc", False))
        assert LEGACY.ready(permanent_but_closed) and not OPEN.ready(permanent_but_closed)

    def test_every_other_gate_is_always_enforced(self) -> None:
        route = self._route(SourceKind.DROP, Gate(GateKind.WINNABLE, "wolf", False))
        assert not LEGACY.ready(route) and not OPEN.ready(route)


def test_only_the_first_usable_buyer_of_a_surplus_item_is_a_ready_sell_route(
        world: tuple[WorldState, GameData]) -> None:
    """Buyers come highest price first; a closed first buyer yields to the next
    one, and a third buyer of the same item is never offered. The scenario
    worlds never hold a surplus with two buyers, so the census cannot see this."""
    state, gd = world
    buyers = [("closed_npc", 30), ("free_npc", 0), ("open_npc", 20), ("cheap_npc", 10)]
    with (patch("artifactsmmo_cli.ai.obtain_model.obtain_model.accumulation_sell.sellable_surplus",
                return_value={"relic": 3}),
          patch.object(GameData, "npcs_buying_item", return_value=buyers),
          patch.object(GameData, "npc_location", return_value=(0, 0)),
          patch("artifactsmmo_cli.ai.obtain_model.obtain_model.event_npc_tradeable",
                side_effect=lambda npc, *a, **kw: npc != "closed_npc")):
        model = ObtainModel(state, gd, _ctx(), NOW)
        routes = model.routes(GOLD_CODE)
        ready = model.ready(GOLD_CODE, LEGACY)
    assert [r.agent for r in routes] == ["closed_npc", "open_npc", "cheap_npc"]  # price 0 is no route
    assert [(r.via, r.agent, r.yield_per, r.capacity) for r in ready] == [("relic", "open_npc", 20, 60)]


def test_an_unowned_non_gold_item_has_no_sell_route(world: tuple[WorldState, GameData]) -> None:
    state, gd = world
    assert not [r for r in ObtainModel(state, gd, _ctx(), NOW).routes("copper_ore")
                if r.kind is SourceKind.SELL]


def test_a_sleeping_monster_is_not_asked_whether_it_is_winnable(
        world: tuple[WorldState, GameData]) -> None:
    state, gd = world
    item = next(i for i in sorted(gd.all_item_stats) if gd.monsters_dropping(i))
    with (patch.object(GameData, "all_monster_locations", new={}),
          patch("artifactsmmo_cli.ai.obtain_model.obtain_model.is_winnable") as winnable):
        routes = ObtainModel(state, gd, _ctx(), NOW).routes(item)
    winnable.assert_not_called()
    assert all(not g.satisfied for r in routes if r.kind is SourceKind.DROP for g in r.gates)


def test_recycle_skips_holdings_that_cannot_be_recycled(world: tuple[WorldState, GameData]) -> None:
    """A held consumer of the item that is not equippable has no RecycleAction
    in existence, so it is no route at all rather than a gated one."""
    state, gd = world
    item, consumer = next((mat, code) for code, recipe in sorted(gd.crafting_recipes.items())
                          for mat in recipe
                          if (s := gd.item_stats(code)) is not None and s.type_ == "resource")
    held = replace(state, inventory={**state.inventory, consumer: 1})
    routes = ObtainModel(held, gd, _ctx(), NOW).routes(item)
    assert not [r for r in routes if r.kind is SourceKind.RECYCLE and r.via == consumer]


def test_a_recipe_whose_item_names_no_crafting_skill_is_no_craft_route(
        world: tuple[WorldState, GameData]) -> None:
    """No crafting skill means no workshop to craft at, so no CraftAction
    exists; `obtain_sources` skips it too."""
    state, gd = world
    stats = replace(gd.item_stats("copper_bar"), crafting_skill="")
    with patch.object(GameData, "item_stats", return_value=stats):
        routes = ObtainModel(state, gd, _ctx(), NOW).routes("copper_bar")
    assert not [r for r in routes if r.kind is SourceKind.CRAFT]


def test_the_census_reports_a_difference_with_both_answers(
        world: tuple[WorldState, GameData]) -> None:
    """Vacuity guard for the pin above: a model that disagrees is reported."""
    state, gd = world
    with patch("artifactsmmo_cli.audit.obtain_model_census.obtain_sources", return_value=[]):
        [difference] = legacy_differences(state, gd, _ctx(), NOW, ["copper_bar"])
    assert difference.item == "copper_bar"
    assert difference.legacy == () and difference.model
