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

from artifactsmmo_cli.ai import accumulation_sell, acquisition_cost
from artifactsmmo_cli.ai.acquisition_cost import (
    acquisition_actions,
    door_price,
    route_options,
)
from artifactsmmo_cli.ai.acquisition_cost_core import UNOBTAINABLE_PER_UNIT, RouteOption
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals import currency_demand
from artifactsmmo_cli.ai.goals import gathering as gathering_module
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.sell_inventory import SellInventoryGoal
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.liquidation_venue import Venue, liquidation_venue
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
from artifactsmmo_cli.ai.shed_actions import shed_actions
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


PINNED = {
    "cloth": RouteOption(kind="buy", venue="tailor", actions_per_application=1, yield_per=1,
                         capacity=UNBOUNDED_CAPACITY, inputs={"wool": 3}),
    "fire_crystal": RouteOption(kind="buy", venue="sorceress", actions_per_application=1,
                                yield_per=1, capacity=UNBOUNDED_CAPACITY,
                                inputs={"fire_dust": 10}),
    "healing_rune": RouteOption(kind="buy", venue="rune_vendor", actions_per_application=1,
                                yield_per=1, capacity=UNBOUNDED_CAPACITY,
                                inputs={GOLD_CODE: 10000}),
}
"""The piece-policy options base 556104dc priced for three reached vendors at
level 48 with no gold (a mainland one, the underground sorceress, a gold
vendor), pinned as literals (Task 8a M-2)."""


@pytest.mark.parametrize("item", sorted(PINNED))
def test_a_reachable_vendor_prices_as_it_did_at_base(item: str) -> None:
    state, world = _seeded("l48_band_adequate", gold=0)
    assert route_options(item, state, world, TIMED_NO_PROFILE_CONTEXT,
                         policy=PIECE_POLICY) == [PINNED[item]]


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


def _held_diamonds(world: GameData, state: WorldState, *events: str) -> WorldState:
    """`state` holding two diamonds (the level-12 cell's keep licenses them for
    sale) with `events` live for four hours."""
    until = datetime.now(UTC) + timedelta(hours=4)
    return replace(state, inventory={"diamond": 2}, active_events=dict.fromkeys(events, until))


def test_a_sale_is_priced_at_its_own_buyer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Task 8a I-1: a SELL route names its buyer (`Route.agent`), and its price
    is that buyer's. The best buyer past the boat is no ready route; the ready
    sale to the reached second buyer is priced at that buyer and its price,
    not re-picked to the best one, and the door route to the best buyer is
    priced at the best buyer, with the door as its unlock."""
    state, world = _seeded("l12_deep_chain_grind", gold=0)
    gem = _island_event(world, monkeypatch)
    nomad = world.npc_event_code("nomadic_merchant")
    assert nomad is not None
    monkeypatch.setattr(world.world, "active_event_codes", {gem, nomad})
    monkeypatch.setattr(world, "npcs_buying_item", lambda code: (
        [("gemstone_merchant", 5000), ("nomadic_merchant", 4000)] if code == "diamond" else []))
    held = _held_diamonds(world, state, gem, nomad)
    sells = {r.agent: r for r in _model(held, world).routes(GOLD_CODE) if r.kind is SourceKind.SELL}
    assert not _reach_gate(sells["gemstone_merchant"]).satisfied
    assert _reach_gate(sells["nomadic_merchant"]).satisfied
    (ready,) = obtain_sources(GOLD_CODE, held, world, TIMED_NO_PROFILE_CONTEXT)
    assert (ready.code, ready.agent, ready.yield_per) == ("diamond", "nomadic_merchant", 4000)
    options = route_options(GOLD_CODE, held, world, TIMED_NO_PROFILE_CONTEXT, policy=PIECE_POLICY)
    by_venue = {o.venue: o for o in options if o.kind == SourceKind.SELL.value}
    assert by_venue["nomadic_merchant"].yield_per == 4000
    assert by_venue["nomadic_merchant"].unlock == ""
    assert by_venue["gemstone_merchant"].yield_per == 5000
    assert by_venue["gemstone_merchant"].unlock == "door:goldx1100"


def _read_on(world: GameData, monkeypatch: pytest.MonkeyPatch, tile: tuple[int, int, str]) -> str:
    """The gemstone merchant's event live, read on `tile`: not its catalogue
    spawn (`ev.maps[0]`)."""
    event = world.npc_event_code("gemstone_merchant")
    assert event is not None
    assert tile[:2] != world.world.event_npc_spawns["gemstone_merchant"]
    monkeypatch.setattr(world.world, "active_event_maps", {event: [tile]})
    monkeypatch.setattr(world.world, "active_event_codes", {event})
    return event


@pytest.mark.parametrize("tile", [ISLAND_TILE, (1, 1, "overworld")], ids=["island", "mainland"])
def test_the_pricer_and_the_executor_read_one_event_tile(
        tile: tuple[int, int, str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Task 8a I-2, I-3: an event vendor read on a map other than its first.
    Every buy and sale the action pool builds for it walks to a tile of
    `vendor_tiles` and travels in that tile's region; and the pricer prices
    its buy and its sale where it stands (the boat door on the island, plain
    on the mainland), in a region the pool's action reaches or the door
    opens."""
    state, world = _seeded("l12_deep_chain_grind", gold=0)
    event = _read_on(world, monkeypatch, tile)
    held = _held_diamonds(world, state, event)
    tiles = vendor_tiles("gemstone_merchant", world)
    assert tiles == [tile[:2]]
    region = world.region_of(tile[0], tile[1], "overworld")
    pool = [a for a in build_actions(world, held, None, True, 0, LearnedDrops.empty())
            if isinstance(a, NpcBuyAction | NpcSellAction) and a.npc_code == "gemstone_merchant"]
    assert {type(a) for a in pool} == {NpcBuyAction, NpcSellAction}
    for action in pool:
        assert action.npc_location in tiles
        assert action.travel_region == region
    reach = reachable_regions_now(held, world)
    beyond = {acquisition_cost._door_unlock(door): regions
              for door, _toll, regions in door_reaches(held, world)}
    island = region not in reach
    priced = [o for item in ("piece_of_obsidian", GOLD_CODE)
              for o in route_options(item, held, world, TIMED_NO_PROFILE_CONTEXT,
                                     policy=PIECE_POLICY)
              if o.venue == "gemstone_merchant"]
    assert {o.kind for o in priced} == {SourceKind.BUY.value, SourceKind.SELL.value}
    for option in priced:
        if island:
            assert region in beyond[option.unlock.split("+")[0]]
        else:
            assert option.unlock == ""


def test_the_census_vendor_verdict_reads_the_vendor_s_tiles(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The craft census's vendor verdict asks production's tile test: an event
    vendor read on the island is not reached from the main overworld, though
    `npc_region` without the read was the main overworld."""
    state, world = _seeded("l48_band_adequate", gold=0)
    reach = reachable_regions_now(state, world)
    _island_event(world, monkeypatch)
    assert world.npc_region("gemstone_merchant") not in reach
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


# --- Task 8a I-4: the selection and emission sites ask the same gate ---------

def _event_read(world: GameData, monkeypatch: pytest.MonkeyPatch, npc: str,
                tile: tuple[int, int, str]) -> str:
    """`npc`'s event live, read on `tile`."""
    event = world.npc_event_code(npc)
    assert event is not None
    monkeypatch.setattr(world.world, "active_event_maps", {event: [tile]})
    monkeypatch.setattr(world.world, "active_event_codes", {event})
    return event


def _gather_buys(item: str, qty: int, state: WorldState, world: GameData) -> list[str]:
    actions = build_actions(world, state, None, True, 0, LearnedDrops.empty())
    return [repr(a) for a in GatherMaterialsGoal(item, {item: qty}).relevant_actions(
        actions, state, world) if isinstance(a, NpcBuyAction | WithdrawItemAction)]


def _npc_buys(item: str, qty: int, state: WorldState, world: GameData) -> list[str]:
    return [buy for buy in _gather_buys(item, qty, state, world) if buy.startswith("NpcBuy")]


@pytest.mark.parametrize("gold", [0, 200_000])
def test_an_island_vendor_raises_no_currency_demand_until_reached(gold: int) -> None:
    """The currency classifier and the gather goal's buy emission ask
    `vendor_reached`: with the boat unpaid the island's rune is not a coin
    buy (no granting vendor, no NpcBuy, no coin withdraw); with the fee in
    hand it is."""
    state, world = _seeded("l48_band_adequate", gold=gold)
    state = replace(state, bank_items={**(state.bank_items or {}), "sandwhisper_coin": 300})
    (leaf,) = currency_demand._classify_leaves({RUNE: 1}, state, world)
    buys = _gather_buys(RUNE, 1, state, world)
    if gold:
        assert leaf.item_route == ("sandwhisper_coin", 100)
        assert buys == [f"NpcBuy({RUNE}×1@{ISLAND})", "Withdraw(sandwhisper_coin×100)"]
    else:
        assert leaf.item_route is None
        assert buys == []


def test_an_unreached_intermediate_vendor_is_not_emitted(monkeypatch: pytest.MonkeyPatch) -> None:
    """A vendor-only closure material (`life_ring`'s cloth, at the tailor) is
    bought only from a vendor `vendor_reached` admits."""
    state, world = _seeded("l48_band_adequate", gold=200_000)
    state = replace(state, inventory={"wool": 30})
    assert _npc_buys("life_ring", 5, state, world) == ["NpcBuy(cloth×10@tailor)"]
    monkeypatch.setattr(gathering_module, "vendor_reached", lambda npc, *_a: npc != "tailor")
    assert _npc_buys("life_ring", 5, state, world) == []


def test_a_craftable_gold_buy_is_offered_only_where_its_vendor_stands_reached(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The craft-vs-buy arm's seller (`minor_health_potion` at the nomadic
    merchant) is offered only while `vendor_reached` admits it."""
    state, world = _seeded("l48_band_adequate", gold=200_000)
    assert _npc_buys("minor_health_potion", 5, state, world) == [
        "NpcBuy(minor_health_potion×5@nomadic_merchant)"]
    monkeypatch.setattr(gathering_module, "vendor_reached",
                        lambda npc, *_a: npc != "nomadic_merchant")
    assert _npc_buys("minor_health_potion", 5, state, world) == []


@pytest.mark.parametrize("tile", [ISLAND_TILE, (1, 1, "overworld")], ids=["island", "mainland"])
def test_a_sale_venue_is_a_buyer_the_walk_reaches(
        tile: tuple[int, int, str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Every sell-venue picker asks `vendor_reached`: the sell goal's bag and
    bank arms and its window bonus, the sell rungs' predicate, the shed
    routing and the liquidation venue (whose NPC price is 0 when no buyer is
    reached, so a standing GE order wins)."""
    state, world = _seeded("l12_deep_chain_grind", gold=0)
    event = _event_read(world, monkeypatch, "gemstone_merchant", tile)
    held = _held_diamonds(world, state, event)
    monkeypatch.setattr(world, "ge_best_buy_order", lambda code: (
        ("order", 1000, 10) if code == "diamond" else None))
    reached = world.region_of(tile[0], tile[1], "overworld") in reachable_regions_now(held, world)
    goal = SellInventoryGoal(world, TIMED_NO_PROFILE_CONTEXT, relief=True)
    sells = goal._sell_actions(held, world)
    assert [a.npc_code for a in sells if isinstance(a, NpcSellAction)] == (
        ["gemstone_merchant"] if reached else [])
    assert (goal._sale_after("diamond", 2, held, world) is not None) is reached
    assert goal._active_window_for_inventory(held, world) is reached
    assert accumulation_sell.sellable_tradeable_now(held, world) is reached
    shed = shed_actions("diamond", 2, held, world, TIMED_NO_PROFILE_CONTEXT, True)
    assert any(isinstance(a, NpcSellAction) for a in shed) is reached
    assert liquidation_venue("diamond", 2, held, world) is (Venue.NPC if reached else Venue.GE)


def test_a_read_of_an_ended_event_does_not_move_its_vendor(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Task 8a M-3: a read kept for an event no longer live (as
    `_content_event_active` guards an event monster's) moves neither the
    vendor's tile nor its actions' location and region."""
    _state, world = _seeded("l48_band_adequate")
    event = world.npc_event_code("gemstone_merchant")
    assert event is not None
    spawn = world.world.event_npc_spawns["gemstone_merchant"]
    monkeypatch.setattr(world.world, "active_event_maps", {event: [ISLAND_TILE]})
    monkeypatch.setattr(world.world, "active_event_codes", set())
    assert world.event_npc_tiles("gemstone_merchant") == []
    assert vendor_tiles("gemstone_merchant", world) == [spawn]
    assert world.npc_location("gemstone_merchant") == spawn
    assert world.npc_region("gemstone_merchant") == "overworld"
