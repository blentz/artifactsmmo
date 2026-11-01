"""Task 8a (Ruling C-3): a vendor route asks the one reachability authority.

A fight's and a gather's SPAWN_KNOWN gate is `region_edges.content_reached`
over `reachable_regions_now`, with the doors past which the content lies
(`region_edges.doors_to`). A BUY or SELL route asked nothing, so the island's
`sandwhisper_trader` (past a 1100-gold boat fee) was a ready route, priced as
one action and a coin, for a character with no gold. The vendor now carries the
same gate (`obtain_model.vendor_reach.vendor_gate`): reached, or priced and
walked through its door, or no route.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from artifactsmmo_cli.ai import acquisition_cost
from artifactsmmo_cli.ai.acquisition_cost import (
    acquisition_actions,
    door_price,
    route_options,
)
from artifactsmmo_cli.ai.acquisition_cost_core import UNOBTAINABLE_PER_UNIT
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.obtain_model import vendor_reach
from artifactsmmo_cli.ai.obtain_model.gate import Gate, GateKind
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import DECOMPOSE_POLICY, LEGACY, PIECE_POLICY, Policy
from artifactsmmo_cli.ai.obtain_model.route import Route
from artifactsmmo_cli.ai.obtain_model.vendor_reach import vendor_gate, vendor_tiles
from artifactsmmo_cli.ai.obtain_sources import UNBOUNDED_CAPACITY, Source, obtain_sources
from artifactsmmo_cli.ai.region_edges import (
    content_reached,
    door_reaches,
    door_toll,
    doors_to,
    reachable_regions_now,
)
from artifactsmmo_cli.ai.scenario import SCENARIOS, derived_scenario_state
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.world_state import GOLD_CODE, WorldState
from artifactsmmo_cli.audit import craft_completeness
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT
from tests.test_ai.shared_world import shared_world

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")

ISLAND = "sandwhisper_trader"
"""The island vendor (overworld (-2,18), region `overworld:-4,17`), past the
boat's gold fee (`door:goldx1100` for a pocket that holds no gold)."""

RUNE = "greater_healing_rune"
"""Sold only by `ISLAND`, for sandwhisper coins: no other route."""

ISLAND_TILE = (-2, 18, "overworld")

BOAT_DOOR = ((GOLD_CODE, 1100),)
"""The cheaper of the two boat fees' shortfalls from an empty pocket."""


def _seeded(name: str, gold: int | None = None) -> tuple[WorldState, GameData]:
    sc = SCENARIOS[name]
    world = shared_world(BUNDLE, with_ge_orders=sc.ge_market,
                         completed_achievements=frozenset(sc.unlocked_achievements))
    state = derived_scenario_state(sc, world)
    return (state if gold is None else replace(state, gold=gold)), world


def _model(state: WorldState, world: GameData) -> ObtainModel:
    return ObtainModel(state, world, TIMED_NO_PROFILE_CONTEXT, datetime.now(UTC))


def _buy(model: ObtainModel, item: str, npc: str) -> Route:
    (route,) = [r for r in model.routes(item) if r.kind is SourceKind.BUY and r.via == npc]
    return route


def _reach_gate(route: Route) -> Gate:
    (gate,) = [g for g in route.gates if g.kind is GateKind.SPAWN_KNOWN]
    return gate


def test_a_vendor_on_an_unreachable_island_is_not_a_free_route(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """With no gold the island stands past the boat: its vendor's route is
    not ready under any policy, and not one action and a coin. With no door
    to it either, it is no route at all: the rune has no price."""
    state, world = _seeded("l48_band_adequate", gold=0)
    assert not content_reached(ISLAND, [], world, reachable_regions_now(state, world))
    route = _buy(_model(state, world), RUNE, ISLAND)
    assert not _reach_gate(route).satisfied
    for policy in (LEGACY, DECOMPOSE_POLICY, PIECE_POLICY):
        assert route not in _model(state, world).ready(RUNE, policy)
        assert all(s.kind is not SourceKind.BUY
                   for s in obtain_sources(RUNE, state, world, TIMED_NO_PROFILE_CONTEXT,
                                           policy=policy))
    monkeypatch.setattr(vendor_reach, "doors_to", lambda *_args: ())
    assert _reach_gate(_buy(_model(state, world), RUNE, ISLAND)).doors == ()
    assert route_options(RUNE, state, world, TIMED_NO_PROFILE_CONTEXT, policy=PIECE_POLICY) == []
    assert acquisition_actions(RUNE, 1, state, world, TIMED_NO_PROFILE_CONTEXT, equip=False,
                               policy=PIECE_POLICY) >= UNOBTAINABLE_PER_UNIT


def test_a_vendor_behind_a_door_is_priced_through_the_door() -> None:
    """The island vendor names the boat's doors, as a fight past them would,
    and the pricer charges the cheapest as the route's unlock (`door_price`)
    with the fee's re-entry share per buy (its toll is consumed). The walk
    routes the buy through the same door, opening it first."""
    state, world = _seeded("l48_band_adequate", gold=0)
    ctx = TIMED_NO_PROFILE_CONTEXT
    gate = _reach_gate(_buy(_model(state, world), RUNE, ISLAND))
    assert gate.doors == doors_to(ISLAND, [], state, world)
    assert BOAT_DOOR in gate.doors
    (option,) = route_options(RUNE, state, world, ctx, policy=PIECE_POLICY)
    assert (option.kind, option.venue) == (SourceKind.BUY.value, ISLAND)
    assert option.unlock == "door:goldx1100"
    assert option.unlock_actions == door_price(BOAT_DOOR, state, world, ctx, None,
                                               PIECE_POLICY, True, frozenset())
    assert door_toll(BOAT_DOOR, state, world)
    reentry = acquisition_cost._reentry_actions(
        RUNE, _buy(_model(state, world), RUNE, ISLAND), BOAT_DOOR, state, world, ctx, None,
        PIECE_POLICY, True, frozenset(), state)
    assert reentry is not None and reentry > 0
    assert option.actions_per_application == 1 + reentry
    (past,) = _model(state, world).past_a_door(RUNE, PIECE_POLICY, frozenset())
    assert past[0].via == ISLAND
    graph = _model(state, world).walk_graph(
        RUNE, PIECE_POLICY, rank=lambda door: door_price(door, state, world, ctx, None,
                                                         PIECE_POLICY, True, frozenset()))
    (walked,) = [(route, source) for route, source in zip(graph.routes[RUNE], graph.sources[RUNE],
                                                          strict=True) if source.via == ISLAND]
    (opened,) = walked[0].gates
    assert isinstance(opened, Gate)
    assert (opened.kind, opened.doors) == (GateKind.SPAWN_KNOWN, (BOAT_DOOR,))


def test_a_vendor_sale_past_a_tolled_door_carries_no_reentry() -> None:
    """A sale adds nothing to the bag (gold takes no slot), so a buyer past a
    tolled door pays no bank-trip re-entry per sale."""
    state, world = _seeded("l48_band_adequate", gold=0)
    sale = Route(GOLD_CODE, SourceKind.SELL, "diamond", 5000, 5000, (), agent="gemstone_merchant")
    assert acquisition_cost._reentry_actions(
        GOLD_CODE, sale, BOAT_DOOR, state, world, TIMED_NO_PROFILE_CONTEXT, None, PIECE_POLICY,
        True, frozenset(), state) == 0


@pytest.mark.parametrize("gold", [0, 200_000])
def test_a_reachable_vendor_is_unchanged(gold: int) -> None:
    """Every vendor the walk reaches carries a satisfied reach gate, and its
    every priced buy is the plain one: no unlock, one action. (At 200000 gold
    the island is reached too.)"""
    state, world = _seeded("l48_band_adequate", gold=gold)
    reach = reachable_regions_now(state, world)
    model = _model(state, world)
    checked = 0
    for npc, stock in world.npc_stock.items():
        if not content_reached(npc, vendor_tiles(npc, world), world, reach):
            continue
        for item in stock:
            route = _buy(model, item, npc)
            assert _reach_gate(route).satisfied and _reach_gate(route).doors == ()
            for option in route_options(item, state, world, TIMED_NO_PROFILE_CONTEXT,
                                        policy=PIECE_POLICY):
                if (option.kind, option.venue) == (SourceKind.BUY.value, npc):
                    assert option == acquisition_cost._priced(
                        item, Source(SourceKind.BUY, npc, 1, UNBOUNDED_CAPACITY), state, world,
                        TIMED_NO_PROFILE_CONTEXT)
                    checked += 1
    assert checked > 0
    if gold:
        assert _reach_gate(_buy(model, RUNE, ISLAND)).satisfied


@pytest.mark.parametrize("name", ["l48_band_adequate", "l20_dual_utility"])
@pytest.mark.parametrize("gold", [0, 800, 200_000])
@pytest.mark.parametrize("policy", [LEGACY, DECOMPOSE_POLICY, PIECE_POLICY],
                         ids=["legacy", "decompose", "piece"])
def test_every_priced_vendor_route_is_walkable(name: str, gold: int, policy: Policy) -> None:
    """Over the whole vendor catalogue: every buy the pricer prices stands
    where the walk reaches now (`content_reached`), or carries the door
    (`doors_to`) past which it stands as its unlock; and the action pool holds
    the buy, travelling in a region that is reached now or past that door."""
    state, world = _seeded(name, gold=gold)
    reach = reachable_regions_now(state, world)
    beyond = {door: regions for door, _toll, regions in door_reaches(state, world)}
    pool = {(a.npc_code, a.item_code): a
            for a in build_actions(world, state, None, True, 0, LearnedDrops.empty())
            if isinstance(a, NpcBuyAction)}
    priced = 0
    for item in sorted({item for stock in world.npc_stock.values() for item in stock}):
        for option in route_options(item, state, world, TIMED_NO_PROFILE_CONTEXT, policy=policy):
            if option.kind != SourceKind.BUY.value:
                continue
            npc = option.venue
            region = pool[(npc, item)].travel_region
            if content_reached(npc, vendor_tiles(npc, world), world, reach):
                assert not option.unlock.startswith("door:")
                assert region in reach
            else:
                (door,) = [d for d in doors_to(npc, vendor_tiles(npc, world), state, world)
                           if option.unlock.split("+")[0] == acquisition_cost._door_unlock(d)]
                assert region in beyond[door]
            priced += 1
    assert priced > 0


def _island_event(world: GameData, monkeypatch: pytest.MonkeyPatch) -> str:
    """The gemstone merchant's event live on the island tile (the read the
    event-tile takeover keys on)."""
    event = world.npc_event_code("gemstone_merchant")
    assert event is not None
    monkeypatch.setattr(world.world, "active_event_maps", {event: [ISLAND_TILE]})
    monkeypatch.setattr(world.world, "active_event_codes", {event})
    return event


def test_an_event_vendor_is_gated_on_the_tile_its_event_stands_on(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """With no read the event vendor stands on its catalogue spawn, reached;
    with its event read on the island it stands there, past the boat."""
    state, world = _seeded("l48_band_adequate", gold=0)
    reach = reachable_regions_now(state, world)
    assert vendor_tiles("tailor", world) == [world.npc_location("tailor")]
    assert vendor_tiles("sorceress", world) == []
    assert vendor_gate("sorceress", world, reach, state).satisfied
    assert vendor_tiles("gemstone_merchant", world) == [world.npc_location("gemstone_merchant")]
    assert vendor_gate("gemstone_merchant", world, reach, state).satisfied
    _island_event(world, monkeypatch)
    assert vendor_tiles("gemstone_merchant", world) == [ISLAND_TILE[:2]]
    gate = vendor_gate("gemstone_merchant", world, reach, state)
    assert not gate.satisfied and BOAT_DOOR in gate.doors


def test_an_event_vendor_with_no_spawn_has_no_tile(monkeypatch: pytest.MonkeyPatch) -> None:
    """An event NPC with no located spawn and no read stands nowhere."""
    _state, world = _seeded("l48_band_adequate")
    monkeypatch.setattr(world, "npc_location", lambda _npc: None)
    assert vendor_tiles("gemstone_merchant", world) == []


def test_a_sale_names_only_a_buyer_the_walk_can_reach(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_sale_of` asks the gate `ObtainModel._sell` asks: a buyer past a door
    is walkable (its route's unlock pays the door), one no door opens is not
    a venue. (The level-12 cell, whose keep licenses its diamonds for sale.)"""
    state, world = _seeded("l12_deep_chain_grind", gold=0)
    event = _island_event(world, monkeypatch)
    held = replace(state, inventory={"diamond": 2},
                   active_events={event: datetime.now(UTC) + timedelta(hours=4)})
    now = datetime.now(UTC)
    assert acquisition_cost._sale_of("diamond", held, world, now) == ("gemstone_merchant", 5000)
    monkeypatch.setattr(vendor_reach, "doors_to", lambda *_args: ())
    with pytest.raises(KeyError):
        acquisition_cost._sale_of("diamond", held, world, now)
    sells = [r for r in _model(held, world).routes(GOLD_CODE) if r.kind is SourceKind.SELL]
    assert sells and all(not _reach_gate(r).satisfied for r in sells)


def test_the_census_vendor_verdict_reads_the_vendor_s_tiles(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The craft census's vendor verdict asks production's tile test: an event
    vendor read on the island is not reached from the main overworld, though
    its catalogue region (`npc_region`) is the overworld."""
    state, world = _seeded("l48_band_adequate", gold=0)
    reach = reachable_regions_now(state, world)
    _island_event(world, monkeypatch)
    assert world.npc_region("gemstone_merchant") in reach
    assert craft_completeness._vendor_sources("piece_of_obsidian", state, world, reach) == [False]


def test_a_permanent_vendor_whose_tile_an_event_takes_stands_nowhere(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The event-tile takeover: a live event standing on the tailor's tile
    hides the tailor until it ends, so its buys are not ready and no door
    opens them."""
    state, world = _seeded("l48_band_adequate", gold=0)
    x, y = world.npc_location("tailor") or (0, 0)
    monkeypatch.setattr(world.world, "active_event_maps", {"takeover": [(x, y, "overworld")]})
    monkeypatch.setattr(world.world, "active_event_codes", {"takeover"})
    assert vendor_tiles("tailor", world) == []
    gate = vendor_gate("tailor", world, reachable_regions_now(state, world), state)
    assert (gate.satisfied, gate.doors) == (False, ())
