"""The walk serves the route that priced the item (the ticket farm, live
2026-10-31).

Robby and C3P0 farmed `event_ticket` with `Gather(shrimp_spot)`: 266 gathers
for one ticket. The ticket drops 1 in 200 from every resource and 1 in 100
from every monster, and the price (`cheapest_route`) took a chicken fight at
86.8 actions a ticket. The walk kept `ObtainModel.routes`' fixed kind order
(GATHER before DROP) and its greedy fill served any ready gather first; only a
route past a door was re-sorted toward the priced one. Now every choice among
routes that make copies is served cheapest first, by the pricer's own unit
cost (`acquisition_cost.route_order`).
"""

from fractions import Fraction

import pytest

from artifactsmmo_cli.ai import acquisition_cost
from artifactsmmo_cli.ai.acquisition_cost import route_key, route_order
from artifactsmmo_cli.ai.acquisition_cost_core import (
    BANK_VENUE,
    RouteOption,
    priced_route,
    route_ranks,
)
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.craft_plan_gen import decompose
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.obtain_model import drop_routes as drop_routes_module
from artifactsmmo_cli.ai.obtain_model.obtain_model import _walk_order
from artifactsmmo_cli.ai.obtain_model.policy import DECOMPOSE_POLICY
from artifactsmmo_cli.ai.obtain_model.route import UNBOUNDED_CAPACITY, Route
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, derived_scenario_state, load_bundle_game_data
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state
from tests.test_ai.scenarios.routing import BUNDLE

TICKET = "event_ticket"


def _ticket_world() -> GameData:
    """The committed bundle with the season's ticket drops (the bundle
    predates them): 1 in 200 from every resource, 1 in 100 from every
    monster. A private copy: the shared world is never mutated."""
    world = load_bundle_game_data(BUNDLE)
    for table in world.recipes_catalog.resource_drops_full.values():
        table.append((TICKET, 200, 1, 1))
    for drops in world.monsters.drops.values():
        drops.append((TICKET, 100, 1, 1))
    return world


def _seeded(name: str) -> tuple[WorldState, GameData, GamePlayer]:
    sc = SCENARIOS[name]
    world = _ticket_world()
    player = GamePlayer(character=sc.name, history=None)
    player.seed_offline(derived_scenario_state(sc, world), world)
    assert player.state is not None
    return player.state, world, player


def test_a_ticket_is_farmed_by_the_fight_that_priced_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Robby's shape: a ticket needed, every resource a ready 1-in-200 gather
    and every monster a ready 1-in-100 fight that forces no rest (Robby's
    chicken at L41: 86.8 actions a ticket). The price takes a fight, and the
    plan is that fight, not a gather."""
    monkeypatch.setattr(drop_routes_module, "drop_fight_winnable", lambda rested, gd, monster: True)
    monkeypatch.setattr(acquisition_cost, "expected_damage_per_fight", lambda *a: 0)
    state, world, player = _seeded("l40_band_entry")
    assert world.monsters_dropping(TICKET) and TICKET in world.gatherable_drop_items()
    ctx = player._selection_context()
    ranked = route_order(TICKET, state, world, ctx, policy=DECOMPOSE_POLICY, pocket=state.gold,
                         store=None)
    kind, monster = next(iter(ranked))
    assert kind is SourceKind.DROP
    gathers = [unit for (k, _via), unit in ranked.items() if k is SourceKind.GATHER]
    assert gathers and ranked[(kind, monster)] < min(gathers)
    plan = decompose(GatherMaterialsGoal(TICKET, {TICKET: 1}), state, world,
                     player._build_actions(), ctx)
    assert plan is not None
    assert not [a for a in plan if isinstance(a, GatherAction)]
    fights = [a for a in plan if isinstance(a, FightAction)]
    # The fight served is priced at the argmin (equal prices keep the walk's
    # priority order).
    assert fights and ranked[(SourceKind.DROP, fights[0].monster_code)] == ranked[(kind, monster)]


def _route(kind: SourceKind, via: str) -> Route:
    return Route("x", kind, via, 1, UNBOUNDED_CAPACITY, ())


def test_each_priced_option_is_keyed_as_the_walk_names_its_route() -> None:
    """`route_key`: a withdraw or a craft acts on the item itself, a sibling's
    craft (CRAFT at the bank) is this character's withdraw, a recycle or a
    sale on the copy it destroys, every other kind on its venue."""
    def option(kind: SourceKind, venue: str, **inputs: int) -> RouteOption:
        return RouteOption(kind=kind.value, venue=venue, actions_per_application=1,
                           yield_per=1, capacity=1, inputs=inputs)

    assert route_key("x", option(SourceKind.WITHDRAW, BANK_VENUE)) == (SourceKind.WITHDRAW, "x")
    assert route_key("x", option(SourceKind.CRAFT, "forge", ore=2)) == (SourceKind.CRAFT, "x")
    assert route_key("x", option(SourceKind.CRAFT, BANK_VENUE)) == (SourceKind.WITHDRAW, "x")
    assert route_key("x", option(SourceKind.RECYCLE, "forge", ring=1)) == (SourceKind.RECYCLE,
                                                                          "ring")
    assert route_key("gold", option(SourceKind.SELL, "trader", junk=1)) == (SourceKind.SELL,
                                                                           "junk")
    assert route_key("x", option(SourceKind.DROP, "chicken")) == (SourceKind.DROP, "chicken")
    assert route_key("x", option(SourceKind.GATHER, "shrimp_spot")) == (SourceKind.GATHER,
                                                                       "shrimp_spot")


def test_stock_leads_a_sale_trails_and_the_price_orders_the_rest() -> None:
    """`_walk_order`: stock (a withdraw, a recycle) before every route that
    makes copies whatever the price, a sale after them, the middle by the
    priced unit cost, and a route the pricer does not list after every
    priced one."""
    priced = {(SourceKind.DROP, "chicken"): 87, (SourceKind.GATHER, "shrimp_spot"): 200,
              (SourceKind.WITHDRAW, "x"): 1000}
    routes = [_route(SourceKind.SELL, "junk"), _route(SourceKind.GATHER, "ash_tree"),
              _route(SourceKind.GATHER, "shrimp_spot"), _route(SourceKind.DROP, "chicken"),
              _route(SourceKind.RECYCLE, "ring"), _route(SourceKind.WITHDRAW, "x")]
    ordered = sorted(routes, key=lambda route: _walk_order(route, priced))
    assert [(route.kind, route.via) for route in ordered] == [
        (SourceKind.RECYCLE, "ring"), (SourceKind.WITHDRAW, "x"), (SourceKind.DROP, "chicken"),
        (SourceKind.GATHER, "shrimp_spot"), (SourceKind.GATHER, "ash_tree"),
        (SourceKind.SELL, "junk")]


def test_the_ranking_is_the_fill_the_price_makes() -> None:
    """`route_ranks` lists an item's routes cheapest first at the unit cost
    the price fills them at, so its head is `priced_route`'s argmin."""
    options = {TICKET: [
        RouteOption(kind="gather", venue="shrimp_spot", actions_per_application=Fraction(200),
                    yield_per=1, capacity=UNBOUNDED_CAPACITY),
        RouteOption(kind="drop", venue="chicken", actions_per_application=Fraction(87),
                    yield_per=1, capacity=UNBOUNDED_CAPACITY)]}
    ranked = route_ranks(TICKET, options, {})
    assert [(option.venue, unit) for option, unit in ranked] == [("chicken", 87),
                                                                 ("shrimp_spot", 200)]
    assert priced_route(TICKET, 1, options, {})[1] == ranked[0][0]


def test_two_options_one_walk_route_rank_at_the_cheaper(monkeypatch: pytest.MonkeyPatch) -> None:
    """A banked copy and a sibling's craft (CRAFT at the bank) are both this
    character's withdraw: the walk route ranks at the cheaper of the two."""
    options = {"x": [
        RouteOption(kind="withdraw", venue=BANK_VENUE, actions_per_application=1, yield_per=1,
                    capacity=1),
        RouteOption(kind="craft", venue=BANK_VENUE, actions_per_application=7, yield_per=1,
                    capacity=UNBOUNDED_CAPACITY)]}
    monkeypatch.setattr(acquisition_cost, "acquisition_options", lambda *a, **k: options)
    ranked = route_order("x", make_state(), GameData(), NO_PROFILE_CONTEXT, policy=DECOMPOSE_POLICY,
                         pocket=0, store=None)
    assert ranked == {(SourceKind.WITHDRAW, "x"): 1}
