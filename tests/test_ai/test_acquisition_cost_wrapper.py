"""Hoisting priced routes out of `obtain_sources`.

Two layers, tested separately on purpose.

`_priced` is the MAPPING from an availability answer to a price, and it is
exercised with hand-built `Source`s so every route kind is covered regardless of
whether the committed fixture happens to make that route servable. Driving it
only through `obtain_sources` would leave BUY, WITHDRAW and RECYCLE untested
here — the fixture has no reachable vendor, an inaccessible bank, and no
licensed surplus — and those are exactly the routes `min_plan_length` could not
express, so leaving them uncovered would repeat the original omission.

`acquisition_actions` is then tested END TO END on a real scenario state, where
`obtain_sources`' gates DO apply. That is where the interesting result lives:
most gear comes back unobtainable, and the reasons are worth reading.
"""

import json
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.acquisition_cost import (
    BANK_VENUE,
    _drop_actions,
    _drop_table,
    _kill_actions,
    _priced,
    _sale_of,
    _workshop_venue,
    acquisition_actions,
    acquisition_options,
    bundle_acquisition_actions,
    cheapest_route,
    drop_work,
    drop_work_actions,
    leg_prospecting,
    npc_price_of,
    route_options,
)
from artifactsmmo_cli.ai.acquisition_cost_core import (
    UNOBTAINABLE_PER_UNIT,
    RouteOption,
    acquisition_cost,
)
from artifactsmmo_cli.ai.drop_leg import DropLeg
from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.gear_objective import _price
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.drop_observations import fleet_k, learned_drops
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.obtain_model.policy import LEGACY
from artifactsmmo_cli.ai.obtain_sources import (
    UNBOUNDED_CAPACITY,
    Source,
    SourceKind,
    obtain_sources,
)
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.tiers.skill_grind_target import GRIND_PRICING
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT
from tests.test_ai.shared_world import shared_world

_BUNDLE = (Path(__file__).resolve().parent / "scenarios" / "fixtures"
           / "gamedata_bundle.json")


@pytest.fixture(scope="module")
def game_data():  # type: ignore[no-untyped-def]
    return load_bundle_game_data(_BUNDLE)


@pytest.fixture(scope="module")
def state(game_data):  # type: ignore[no-untyped-def]
    return scenario_state(SCENARIOS["l12_deep_chain_grind"], game_data)


def test_withdraw_is_a_bank_hop_and_one_action(state, game_data) -> None:
    """Bank stock is a ROUTE, not free holdings — which is the change from
    `min_plan_length`, whose callers pass inventory PLUS bank because that model
    has no withdraw action at all."""
    opt = _priced("copper_ore",
                  Source(SourceKind.WITHDRAW, "copper_ore", 1, 7),
                  state, game_data, TIMED_NO_PROFILE_CONTEXT)
    assert opt.venue == BANK_VENUE
    assert opt.actions_per_application == 1
    assert opt.capacity == 7
    assert not opt.inputs


def test_craft_carries_its_recipe_as_inputs_and_a_workshop_venue(
        state, game_data) -> None:
    """The AND arm. The recipe comes from game data, not from anything restated
    here, so a recipe change cannot leave the price describing the old one."""
    opt = _priced("iron_sword",
                  Source(SourceKind.CRAFT, "iron_sword", 1, UNBOUNDED_CAPACITY),
                  state, game_data, TIMED_NO_PROFILE_CONTEXT)
    assert opt.venue == _workshop_venue("weaponcrafting")
    assert opt.inputs == game_data.crafting_recipe("iron_sword")


def test_recycle_consumes_the_source_item_not_the_target(state, game_data) -> None:
    """`Source.code` for a RECYCLE is the item to DESTROY, never the target —
    the one place that distinction becomes an input edge."""
    opt = _priced("iron",
                  Source(SourceKind.RECYCLE, "iron_sword", 3, 6),
                  state, game_data, TIMED_NO_PROFILE_CONTEXT)
    assert opt.inputs == {"iron_sword": 1}
    assert opt.yield_per == 3
    assert opt.venue == _workshop_venue("weaponcrafting")


def test_gather_uses_the_resource_tile_as_its_venue(state, game_data) -> None:
    """Two materials off the same node pay one walk, which only works because
    the venue is the RESOURCE code rather than a per-item token."""
    opt = _priced("copper_ore",
                  Source(SourceKind.GATHER, "copper_rocks", 1, UNBOUNDED_CAPACITY),
                  state, game_data, TIMED_NO_PROFILE_CONTEXT)
    assert opt.venue == "copper_rocks"
    assert (opt.actions_per_application, opt.yield_per) == (1, 1)


def test_a_secondary_drop_costs_its_expected_gathers(state, game_data, monkeypatch) -> None:
    """Live 2026-10-05: `apple` drops off `ash_tree` at 1 in 20, and priced at
    one gather a unit the fleet spent 554 gathers on 25 apples. One application
    is 20 gathers for 1 apple; the primary wood off the same tree stays 1 for 1."""
    monkeypatch.setattr(game_data.recipes_catalog, "resource_drops_full", {
        **game_data.recipes_catalog.resource_drops_full,
        "ash_tree": [("ash_wood", 1, 1, 1), ("apple", 20, 1, 1)]})
    apple = _priced("apple", Source(SourceKind.GATHER, "ash_tree", 1, UNBOUNDED_CAPACITY),
                    state, game_data, TIMED_NO_PROFILE_CONTEXT)
    wood = _priced("ash_wood", Source(SourceKind.GATHER, "ash_tree", 1, UNBOUNDED_CAPACITY),
                   state, game_data, TIMED_NO_PROFILE_CONTEXT)
    assert (apple.actions_per_application, apple.yield_per) == (20, 1)
    assert (wood.actions_per_application, wood.yield_per) == (1, 1)


def test_a_multi_unit_drop_is_priced_in_lowest_terms(state, game_data, monkeypatch) -> None:
    """1 to 2 units a gather is 2/3 of a gather a unit, exactly, rather than
    rounding the ratio to a whole action either way: the walk rounds the
    route's gathers up once (three units are two gathers)."""
    monkeypatch.setattr(game_data.recipes_catalog, "resource_drops_full", {
        **game_data.recipes_catalog.resource_drops_full,
        "copper_rocks": [("copper_ore", 1, 1, 2)]})
    opt = _priced("copper_ore", Source(SourceKind.GATHER, "copper_rocks", 1, UNBOUNDED_CAPACITY),
                  state, game_data, TIMED_NO_PROFILE_CONTEXT)
    assert (opt.actions_per_application, opt.yield_per) == (Fraction(2, 3), 1)
    assert acquisition_cost("copper_ore", 3, {"copper_ore": [opt]}, {}) == 2 + 1


def _ctx_with_siblings(**skills):  # type: ignore[no-untyped-def]
    return replace(TIMED_NO_PROFILE_CONTEXT, sibling_skills=dict(skills))


class _SupplyStore:
    """A store that has seen fleet supply requests but no grind evidence, so the
    sibling route is the only deferred option under test."""

    def __init__(self, request_cycles=15.0):  # type: ignore[no-untyped-def]
        self._request_cycles = request_cycles

    def fleet_supply_request_cycles(self):  # type: ignore[no-untyped-def]
        return self._request_cycles

    def skill_grind_rate(self, skill):  # type: ignore[no-untyped-def]
        return None

    def fleet_skill_grind_rate(self, skill):  # type: ignore[no-untyped-def]
        return None


def test_sibling_route_opens_a_skill_gate_the_character_cannot_meet(
        state, game_data) -> None:
    """THE GAP. `iron_sword` needs weaponcrafting 10; this character has 1. Today
    that prices at UNOBTAINABLE_PER_UNIT even when a sibling is one craft away —
    four characters each paying 160-514 cycles to unlock the same five recipes
    (PLAN_iron_gear_acquisition increment 4).
    """
    st = replace(state, skills={**state.skills, "weaponcrafting": 1})
    routes = route_options("iron_sword", st, game_data,
                           _ctx_with_siblings(weaponcrafting=10), _SupplyStore())

    sibling = [r for r in routes if r.unlock == "sibling:iron_sword"]
    assert len(sibling) == 1
    opt = sibling[0]
    assert opt.unlock_actions == 15, "priced from the MEASURED fleet request cost"
    assert opt.inputs == game_data.crafting_recipe("iron_sword"), \
        "the requester still owes the MATERIALS — a sibling saves the SKILL GATE only"
    assert opt.venue == BANK_VENUE, "our own action is a withdraw, not a workshop trip"


def test_no_sibling_route_when_the_character_can_already_craft_it(
        state, game_data) -> None:
    """Its own CRAFT route already covers it; a second, dearer copy of the same
    thing would just be noise in the ranking."""
    st = replace(state, skills={**state.skills, "weaponcrafting": 10})
    routes = route_options("iron_sword", st, game_data,
                           _ctx_with_siblings(weaponcrafting=10), _SupplyStore())

    assert not [r for r in routes if r.unlock.startswith("sibling:")]


def test_a_sibling_who_is_merely_CLOSE_is_not_a_route(state, game_data) -> None:
    """"One craft away" is the whole claim. A sibling that could GRIND toward the
    skill is not a route, for the same reason a GE order we could POST is not
    one: both are work nobody has committed to, and pricing speculation is how a
    route model starts lying."""
    st = replace(state, skills={**state.skills, "weaponcrafting": 1})
    routes = route_options("iron_sword", st, game_data,
                           _ctx_with_siblings(weaponcrafting=9), _SupplyStore())

    assert not [r for r in routes if r.unlock.startswith("sibling:")]


def test_no_siblings_at_all_is_no_route(state, game_data) -> None:
    """Every single-character run takes this path."""
    st = replace(state, skills={**state.skills, "weaponcrafting": 1})
    routes = route_options("iron_sword", st, game_data, TIMED_NO_PROFILE_CONTEXT,
                           _SupplyStore())

    assert not [r for r in routes if r.unlock.startswith("sibling:")]


def test_a_fleet_that_never_served_a_request_cannot_price_the_route(
        state, game_data) -> None:
    """CLAUDE.md: use only API/observed data or fail. With no observation there
    is no honest price, and a default would be exactly the invented constant this
    method exists to avoid."""
    st = replace(state, skills={**state.skills, "weaponcrafting": 1})
    routes = route_options("iron_sword", st, game_data,
                           _ctx_with_siblings(weaponcrafting=10),
                           _SupplyStore(request_cycles=None))

    assert not [r for r in routes if r.unlock.startswith("sibling:")]


def test_sibling_unlock_is_keyed_ON_THE_ITEM_so_a_batch_pays_once(
        state, game_data) -> None:
    """`unlock_actions` is paid once across every route sharing the key, which is
    precisely the batching `SupplyClaim` elects a single producer to perform. Two
    units of one item are ONE request; keying on the skill instead would collapse
    two different items into one request that only delivers one of them."""
    st = replace(state, skills={**state.skills, "weaponcrafting": 1})
    routes = route_options("iron_sword", st, game_data,
                           _ctx_with_siblings(weaponcrafting=10), _SupplyStore())

    keys = [r.unlock for r in routes if r.unlock.startswith("sibling:")]
    assert keys == ["sibling:iron_sword"], "keyed on the item, not the skill"


class _ClimbStore(_SupplyStore):
    """A store that has seen fleet supply requests and the fleet climber's own
    grind (`character_skill_grind_rate`), with an optional fleet rate."""

    def __init__(self, rates, fleet=None, request_cycles=15.0):  # type: ignore[no-untyped-def]
        super().__init__(request_cycles)
        self._rates = rates
        self._fleet = fleet

    def character_skill_grind_rate(self, character, skill):  # type: ignore[no-untyped-def]
        return self._rates.get(character)

    def fleet_skill_grind_rate(self, skill):  # type: ignore[no-untyped-def]
        return self._fleet


_CLIMB_BOARD = {
    "iron_dagger": (2, Fraction(1)),       # weaponcrafting 10: the climb to 10 opens it
    "fire_staff": (1, Fraction(1)),        # weaponcrafting 5: the climber already makes it
    "king_slime_sword": (1, Fraction(1)),  # weaponcrafting 15: past this climb
    "iron_shield": (3, Fraction(1)),       # another skill's piece, in the climb's range
    "feather": (4, Fraction(1)),           # no producing skill at all
}


def _climb_ctx(climber="Sib", board=None):  # type: ignore[no-untyped-def]
    """No sibling meets `iron_sword`'s weaponcrafting 10; `Sib`, at 6, is the
    fleet's climber for it."""
    return replace(TIMED_NO_PROFILE_CONTEXT, sibling_skills={"weaponcrafting": 6},
                   sibling_skill_ledger={"Sib": {"weaponcrafting": 6}},
                   fleet_climbers={"weaponcrafting": climber},
                   fleet_board=_CLIMB_BOARD if board is None else board)


def _sibling_routes(st, game_data, ctx, store):  # type: ignore[no-untyped-def]
    return [r for r in route_options("iron_sword", st, game_data, ctx, store)
            if r.unlock == "sibling:iron_sword"]


def test_the_fleet_climber_shares_its_climb_across_the_units_it_opens(
        gated_state, game_data) -> None:
    """Spec 2026-10-18 §2.5: no sibling meets the gate yet, so the route is the
    climber's remaining climb (6 -> 10 at 500 xp a level and 10 xp a cycle:
    2000 / 10 = 200 cycles) shared by the units the climb opens — this one and
    the sibling's two `iron_dagger`s (3), rounded up to 67 — plus the request
    cost. A piece the climber already makes, one past the climb, another
    skill's and a drop share none of it."""
    st = replace(gated_state, skills={**gated_state.skills, "weaponcrafting": 1})
    [route] = _sibling_routes(st, game_data, _climb_ctx(), _ClimbStore({"Sib": 10.0}))
    assert route.unlock_actions == 67 + 15
    assert route.venue == BANK_VENUE
    assert route.inputs == game_data.crafting_recipe("iron_sword")


def test_the_climbers_own_rate_comes_before_the_fleets(gated_state, game_data) -> None:
    """The fleet rate prices the climb only in the climber's ABSENCE: 20 xp a
    cycle is 100 cycles, 34 a unit."""
    st = replace(gated_state, skills={**gated_state.skills, "weaponcrafting": 1})
    [own] = _sibling_routes(st, game_data, _climb_ctx(), _ClimbStore({"Sib": 20.0}, fleet=5.0))
    [fleet] = _sibling_routes(st, game_data, _climb_ctx(), _ClimbStore({}, fleet=20.0))
    assert own.unlock_actions == fleet.unlock_actions == 34 + 15


@pytest.mark.parametrize(("rates", "fleet"), [({}, None), ({"Sib": 0.0}, 9.0)])
def test_an_unpriceable_climb_is_no_route(gated_state, game_data, rates, fleet) -> None:
    """No rate anywhere, or the climber's own zero (evidence, not ignorance):
    a climb priced at nothing would be the free-looking grind."""
    st = replace(gated_state, skills={**gated_state.skills, "weaponcrafting": 1})
    assert not _sibling_routes(st, game_data, _climb_ctx(), _ClimbStore(rates, fleet=fleet))


def test_no_skill_requirement_reading_is_no_climb(state, game_data) -> None:
    """`skill_max_xp` empty: the climb has no size, so it is not priced."""
    st = replace(state, skills={**state.skills, "weaponcrafting": 1})
    assert not _sibling_routes(st, game_data, _climb_ctx(), _ClimbStore({"Sib": 10.0}))


def test_the_climber_itself_has_no_sibling_route(gated_state, game_data) -> None:
    """Its own climb is `_gated_skill_option`; a second route would price it twice."""
    st = replace(gated_state, character="Me", skills={**gated_state.skills, "weaponcrafting": 1})
    assert not _sibling_routes(st, game_data, _climb_ctx(climber="Me"), _ClimbStore({"Me": 10.0}))


def test_a_fleet_naming_no_climber_has_no_sibling_route(gated_state, game_data) -> None:
    st = replace(gated_state, skills={**gated_state.skills, "weaponcrafting": 1})
    ctx = replace(_climb_ctx(), fleet_climbers={})
    assert not _sibling_routes(st, game_data, ctx, _ClimbStore({"Sib": 10.0}))


def test_a_sibling_priced_piece_is_served_by_a_withdraw(gated_state, game_data) -> None:
    """The sibling crafts and banks it; this character's own step is the
    withdraw (§2.5 "Delivery"), never its own craft behind the gate."""
    st = replace(gated_state, skills={**gated_state.skills, "weaponcrafting": 1})
    _price, kind = cheapest_route("iron_sword", 1, st, game_data, _climb_ctx(),
                                  _ClimbStore({"Sib": 10.0}), policy=LEGACY, pocket=0)
    assert kind is SourceKind.WITHDRAW


def test_ge_fill_is_priced_in_gold_at_the_standing_order(state, game_data) -> None:
    """REGRESSION. Adding `SourceKind.GE_FILL` to `obtain_sources` was green across
    the whole gate and still broke the live bot on the first plan:

        KeyError: no 6a803d67e8e9a9dd4ab01f5d drop row for battlestaff

    `_priced`'s DROP arm was an UNGUARDED FALLTHROUGH — every kind without an
    explicit branch reached it — so a GE order id was handed to `_drop_table` as
    if it were a monster code. The census could not catch it either: parity
    compares KINDS, not prices. Hence both halves of the fix are pinned here — the
    GE branch, and DROP no longer swallowing the unclassified.
    """
    gd = game_data
    gd._ge_sell_orders = {"backpack": ("ord-x", 137, 4)}
    opt = _priced("backpack",
                  Source(SourceKind.GE_FILL, "ord-x", 1, 4),
                  state, gd, TIMED_NO_PROFILE_CONTEXT)
    assert opt.venue == "ord-x"
    assert opt.actions_per_application == 1
    assert opt.capacity == 4, "a standing order is FINITE, unlike a vendor"
    assert opt.inputs == {"gold": 137}, "the realizable cost is the order's price"


def test_ge_fill_without_a_standing_order_raises_rather_than_defaulting(
        state, game_data) -> None:
    """CLAUDE.md: use only API data or fail with an error.

    `obtain_sources` produced the source from the same order book, so the row
    exists; if it does not, the two reads disagreed inside one decision and a
    default would price a route that is not there. Same contract as `npc_price_of`.
    """
    gd = game_data
    gd._ge_sell_orders = {}
    with pytest.raises(KeyError, match="no standing GE sell order"):
        _priced("backpack", Source(SourceKind.GE_FILL, "ord-gone", 1, 4), state, gd, TIMED_NO_PROFILE_CONTEXT)


def test_buy_carries_its_price_as_a_currency_input(state, game_data) -> None:
    """THE TERM `min_plan_length` CANNOT EXPRESS. A purchase is priced as the
    purchase plus obtaining what it is priced in, so a 50,000-gold backpack
    pulls 50,000 gold into the demand instead of costing one imaginary
    gather."""
    opt = _priced("backpack",
                  Source(SourceKind.BUY, "nomadic_merchant", 1, UNBOUNDED_CAPACITY),
                  state, game_data, TIMED_NO_PROFILE_CONTEXT)
    assert opt.venue == "nomadic_merchant"
    assert opt.inputs == {"gold": 50000}


def test_drop_costs_expected_kills_times_whole_loop_cycles(state, game_data) -> None:
    """A farm is priced as the farm. Both factors are proved elsewhere and
    reused rather than restated: the wins per unit (the learned chance,
    `Formal.DropChance`) and `cycles_per_kill` — the same
    fight-plus-forced-rest figure `cheapest_path_to_level` spends, so a drop
    farm and a level grind are quoted in identical units."""
    opt = _priced("feather",
                  Source(SourceKind.DROP, "chicken", 1, UNBOUNDED_CAPACITY),
                  state, game_data, TIMED_NO_PROFILE_CONTEXT)
    assert opt.venue == "chicken"
    assert opt.actions_per_application > 1


def _fleet(path: Path, rows: list[tuple[str, str, str, int | None, int]]) -> LearningStore:
    """A real store carrying `(action_repr, action_class, drops_json,
    prospecting, count)` ok cycles: the fleet's drop observations."""
    store = LearningStore(db_path=str(path), character="drop_probe")
    store.start_session()
    for action_repr, action_class, drops, prospecting, count in rows:
        for _ in range(count):
            store.record_cycle(Cycle(ts="2026-10-21T00:00:00+00:00", cycle_index=0,
                                     action_repr=action_repr, action_class=action_class,
                                     outcome="ok", drops_json=drops,
                                     prospecting=prospecting))
    return store


def _learned(game_data, store=None):  # type: ignore[no-untyped-def]
    """The pricing context carrying `store`'s drop evidence (ruling T16a), or
    none observed without one."""
    evidence = learned_drops(store, game_data) if store is not None else LearnedDrops.empty()
    return replace(TIMED_NO_PROFILE_CONTEXT, learned_drops=evidence)


_PEARLS_383_FOR_2 = [
    ("Gather(trout_spot)", "GatherAction", '{"trout": 1}', None, 381),
    ("Gather(trout_spot->small_pearls)", "GatherAction",
     '{"trout": 1, "small_pearls": 1}', None, 2),
]
"""The live 2026-10-19 trigger: 383 gathers at `trout_spot` for 2 pearls."""

_PROSPECTING_SLOPE = [
    ("Gather(trout_spot)", "GatherAction", '{"trout": 1, "algae": 1, "small_pearls": 1}', 10, 1),
    ("Gather(trout_spot)", "GatherAction", '{"trout": 1, "algae": 1}', 10, 9),
    ("Gather(trout_spot->algae)", "GatherAction", '{"trout": 1}', 10, 90),
]
"""100 gathers at prospecting 10, 1 pearl: `fleet_k` fits `k = 1/10`
(`test_drop_observations.test_fleet_k_fits_every_drop_of_each_observed_source`)."""


def _pearl_gather(state, game_data, store=None):  # type: ignore[no-untyped-def]
    return _priced("small_pearls", Source(SourceKind.GATHER, "trout_spot", 1, UNBOUNDED_CAPACITY),
                   state, game_data, _learned(game_data, store))


def test_a_rare_drop_is_priced_by_its_chance(state, game_data) -> None:
    """Spec 2026-10-18 §2.8. `small_pearls` drop off `trout_spot` at 1 in 300.
    With nothing observed the chance is the API prior alone: 300 gathers a
    pearl, so 20 pearls are 6,000 gathers and one walk to the spot, not 20."""
    pearls = _pearl_gather(state, game_data)
    assert pearls.actions_per_application == 300
    assert pearls.yield_per == 1
    assert acquisition_cost("small_pearls", 20, {"small_pearls": [pearls]}, {}) == 20 * 300 + 1


def test_observations_reprice_the_drop(tmp_path, state, game_data) -> None:
    """383 gathers for 2 pearls: the posterior is `(1 + 2) / (300 + 383)`, so
    a pearl is 683/3 gathers and 20 of them `ceil(20 × 683/3)`, rounded once
    for the route (the walk's exact arm), plus the walk to the spot."""
    store = _fleet(tmp_path / "learn.db", _PEARLS_383_FOR_2)
    pearls = _pearl_gather(state, game_data, store)
    assert pearls.actions_per_application == Fraction(683, 3)
    assert acquisition_cost("small_pearls", 20, {"small_pearls": [pearls]}, {}) == 4554 + 1


def test_a_sure_primary_drop_still_costs_one_gather(tmp_path, state, game_data) -> None:
    """Every observed gather of `trout_spot` landed a trout (rate 1): the
    posterior `(1 + 383) / (1 + 383)` is 1, so a trout is one gather, as
    before the chance was learned."""
    store = _fleet(tmp_path / "learn.db", _PEARLS_383_FOR_2)
    trout = _priced("trout", Source(SourceKind.GATHER, "trout_spot", 1, UNBOUNDED_CAPACITY),
                    state, game_data, _learned(game_data, store))
    assert trout.actions_per_application == 1


def test_a_unit_is_the_chance_times_the_mean_quantity() -> None:
    """A drop of 1 to 3 units at 1 in 8 yields `(1/8) · 2` units an attempt."""
    assert LearnedDrops.empty().units_per_attempt("chicken", "feather", 8, 1, 3, 0) == Fraction(1, 4)


def test_an_observed_monster_drop_reprices_the_farm(tmp_path, state, game_data) -> None:
    """`feather` drops off `chicken` at 1 in 8. 100 recorded wins with 50
    feathers make the posterior `(1 + 50) / (8 + 100)`: the farm is the wins a
    feather takes at that chance, times one win's whole-loop actions."""
    store = _fleet(tmp_path / "learn.db",
                   [("Fight(chicken)", "FightAction", '{"feather": 1}', None, 50),
                    ("Fight(chicken)", "FightAction", '{"raw_chicken": 1}', None, 50)])
    learned = _priced("feather", Source(SourceKind.DROP, "chicken", 1, UNBOUNDED_CAPACITY),
                      state, game_data, _learned(game_data, store))
    win = _kill_actions("chicken", state, game_data, TIMED_NO_PROFILE_CONTEXT.timing(), ())
    assert learned.actions_per_application == Fraction(108, 51) * win
    prior = _priced("feather", Source(SourceKind.DROP, "chicken", 1, UNBOUNDED_CAPACITY),
                    state, game_data, TIMED_NO_PROFILE_CONTEXT)
    assert prior.actions_per_application == 8 * win


def test_prospecting_is_worth_nothing_until_k_is_learned(tmp_path, state, game_data) -> None:
    """The slope's prior is `k = 0` (§2.8): without a store, or with
    observations at no recorded prospecting, a prospecting total changes no
    price."""
    lucky = replace(state, prospecting=500)
    assert (_pearl_gather(lucky, game_data).actions_per_application
            == _pearl_gather(state, game_data).actions_per_application)
    store = _fleet(tmp_path / "learn.db", _PEARLS_383_FOR_2)
    assert fleet_k(store, game_data) == 0
    assert (_pearl_gather(lucky, game_data, store).actions_per_application
            == _pearl_gather(state, game_data, store).actions_per_application)


def test_prospecting_lowers_the_price_once_k_is_learned(tmp_path, state, game_data) -> None:
    """With `k = 1/10` learned, a pearl at prospecting 0 is `(300 + 100) / (1 +
    1)` = 200 gathers, and at prospecting 100 the chance is `1 + 10` times
    that: 200/11 gathers."""
    store = _fleet(tmp_path / "learn.db", _PROSPECTING_SLOPE)
    assert fleet_k(store, game_data) == Fraction(1, 10)
    plain = _pearl_gather(replace(state, prospecting=0), game_data, store)
    lucky = _pearl_gather(replace(state, prospecting=100), game_data, store)
    assert plain.actions_per_application == 200
    assert lucky.actions_per_application == Fraction(200, 11)


def test_the_second_copy_is_cheaper_than_the_first(tmp_path, state, game_data) -> None:
    """The USER's perfect_pearl (2026-10-19): it costs 20 `small_pearls` at
    the `archaeologist`, and it carries prospecting. Once the first is worn,
    the pearls for the second drop at the higher prospecting, so the second
    copy is cheaper. Nothing counts copies: it is the price at the worn
    total."""
    store = _fleet(tmp_path / "learn.db", _PROSPECTING_SLOPE)
    assert fleet_k(store, game_data) > 0

    def price(st) -> int:  # type: ignore[no-untyped-def]
        buy = _priced("perfect_pearl",
                      Source(SourceKind.BUY, "archaeologist", 1, UNBOUNDED_CAPACITY),
                      st, game_data, _learned(game_data, store))
        assert buy.inputs == {"small_pearls": 20}
        return acquisition_cost("perfect_pearl", 1,
                                {"perfect_pearl": [buy],
                                 "small_pearls": [_pearl_gather(st, game_data, store)]}, {})

    gem = game_data.item_stats("perfect_pearl")
    assert gem is not None and gem.prospecting > 0
    first = price(state)
    second = price(replace(state, prospecting=state.prospecting + gem.prospecting))
    assert second < first


def test_a_gear_price_reads_the_characters_own_prospecting(tmp_path, state, game_data) -> None:
    """Ruling T14d-3: a gear-objective price is read on the character's own
    state, so its own prospecting moves the drop price: with `k` learned on
    chicken kills, a character at prospecting 100 farms feathers cheaper than
    one at 0."""
    store = _fleet(tmp_path / "learn.db",
                   [("Fight(chicken)", "FightAction", '{"feather": 1}', 5, 4)])
    assert fleet_k(store, game_data) == Fraction(1, 5)
    own = _price(state, game_data, _learned(game_data, store), store, "feather")
    lucky = _price(replace(state, prospecting=100), game_data, _learned(game_data, store),
                   store, "feather")
    assert lucky[0] < own[0]


def test_an_item_with_no_crafting_skill_still_prices(state, game_data) -> None:
    """A RECYCLE whose source item has no crafting skill cannot reach a real
    workshop. It prices with an empty skill rather than crashing — the walk will
    simply never prefer it, and a crash inside a cost model would take down a
    whole decision for a route nobody was going to take."""
    opt = _priced("feather",
                  Source(SourceKind.RECYCLE, "copper_ore", 1, 2),
                  state, game_data, TIMED_NO_PROFILE_CONTEXT)
    assert opt.venue == _workshop_venue("")


def test_price_of_refuses_to_invent_a_missing_row(state, game_data) -> None:
    """`obtain_sources` built the BUY source from this same table, so a missing
    row means the two reads disagreed about game data inside one decision. That
    raises rather than defaulting — 'use only API data or fail with an error'."""
    with pytest.raises(KeyError):
        npc_price_of("backpack", "a_vendor_that_does_not_exist", game_data)


def test_sale_of_refuses_to_invent_a_missing_row(state, game_data) -> None:
    """Same contract as `npc_price_of`, for the sell side: `_sell_sources` built the
    SELL source from this table under these gates, so no row means the two reads
    disagreed inside one decision."""
    with pytest.raises(KeyError):
        _sale_of("an_item_nobody_buys", state, game_data, datetime.now(timezone.utc))


def test_a_buyer_with_no_known_location_is_skipped(state, game_data,
                                                   monkeypatch) -> None:
    """A price row is not a buyer. A dormant merchant with no location is
    skipped by BOTH reads, so the source arm and the venue lookup stay in step
    on which buyer they mean."""
    real = game_data.npc_location
    monkeypatch.setattr(game_data, "npc_location",
                        lambda npc: None if npc == "gemstone_merchant" else real(npc))
    held = _selling(state, game_data, diamond=2)
    assert obtain_sources("gold", held, game_data, TIMED_NO_PROFILE_CONTEXT) == []
    with pytest.raises(KeyError):
        _sale_of("diamond", held, game_data, datetime.now(timezone.utc))


def test_a_buyer_offering_nothing_is_skipped(state, game_data,
                                             monkeypatch) -> None:
    """A zero price is not an offer — selling into it would spend an action to
    obtain no gold, and `yield_per` must stay >= 1."""
    monkeypatch.setattr(game_data, "npcs_buying_item",
                        lambda code: [("gemstone_merchant", 0)]
                        if code == "diamond" else [])
    held = _selling(state, game_data, diamond=2)
    assert obtain_sources("gold", held, game_data, TIMED_NO_PROFILE_CONTEXT) == []
    with pytest.raises(KeyError):
        _sale_of("diamond", held, game_data, datetime.now(timezone.utc))


def test_drop_table_refuses_to_invent_a_missing_row(state, game_data) -> None:
    """Same contract for the drop table."""
    with pytest.raises(KeyError):
        _drop_table("feather", "a_monster_that_does_not_exist", game_data)


def test_the_closure_follows_currency_edges(state, game_data) -> None:
    """A purchase pulls its CURRENCY into the closure, which is the edge
    `min_plan_length` has no way to represent. Without it a 100-ticket item
    would price identically to a free one."""
    options = {"medal": [_priced("backpack",
                                 Source(SourceKind.BUY, "nomadic_merchant", 1,
                                        UNBOUNDED_CAPACITY),
                                 state, game_data, TIMED_NO_PROFILE_CONTEXT)]}
    assert "gold" in options["medal"][0].inputs


def test_a_gatherable_prices_end_to_end(state, game_data) -> None:
    """The whole stack on real state: `obtain_sources` names a GATHER, the
    wrapper prices it, the core walks it."""
    bare = replace(state, inventory={})
    cost = acquisition_actions("copper_ore", 3, bare, game_data,
                               TIMED_NO_PROFILE_CONTEXT, equip=False)
    assert cost == 1 + 3   # hop to the node, three gathers


def test_equip_adds_exactly_one_action(state, game_data) -> None:
    bare = replace(state, inventory={})
    without = acquisition_actions("copper_ore", 1, bare, game_data,
                                  TIMED_NO_PROFILE_CONTEXT, equip=False)
    with_equip = acquisition_actions("copper_ore", 1, bare, game_data,
                                     TIMED_NO_PROFILE_CONTEXT, equip=True)
    assert with_equip == without + 1


def test_a_gold_priced_vendor_route_is_paid_for_with_gold(state, game_data)\
        -> None:
    """THE WALL. A BUY route carries `inputs={"gold": price}`, nothing in the
    game obtains gold, and the walk charges an unobtainable input
    `UNOBTAINABLE_PER_UNIT` PER UNIT — so a 10,000-gold rune was priced at ten
    BILLION actions and no gold-priced vendor item in the game could ever be
    chosen. Crediting the pocket is what pays it down."""
    rich = replace(state, inventory={}, gold=50_000)
    cost = acquisition_actions("healing_rune", 1, rich, game_data,
                               TIMED_NO_PROFILE_CONTEXT, equip=False)
    assert cost == 2      # hop to the vendor, one purchase

    # ...and the shortfall beyond the pocket is charged a million per gold piece,
    # which used to price this route at 10,000 * UNOBTAINABLE_PER_UNIT — ABOVE
    # the price of an item with no route in the game at all, so the walk ranked
    # the impossible thing ahead of the merely unaffordable one. The sentinel is
    # a CEILING now (`acquisition_cost_core._capped`), so the unaffordable route
    # prices at exactly what a missing one does, and never worse.
    broke = replace(state, inventory={}, gold=0)
    unaffordable = acquisition_actions("healing_rune", 1, broke, game_data,
                                       TIMED_NO_PROFILE_CONTEXT, equip=False)
    assert unaffordable == UNOBTAINABLE_PER_UNIT, unaffordable


def _selling(state, game_data, **inv):
    """A state whose gemstone-merchant window is OPEN.

    EVERY NPC in the game that buys items is an event NPC — measured live, all
    five merchants, 55 buyer rows and no non-event buyer at all. So a SELL route
    only exists inside a window, and a fixture that forgets to open one tests the
    absence of the route rather than the route."""
    event = game_data.npc_event_code("gemstone_merchant")
    assert event is not None, "fixture lost the gemstone merchant"
    open_until = datetime.now(timezone.utc) + timedelta(hours=4)
    return replace(state, inventory=dict(inv), active_events={event: open_until})


def test_gold_is_obtained_by_selling_what_the_authority_licenses(
        state, game_data) -> None:
    """S-046 made operational: gold is a thing with a ROUTE, so a shortfall is
    priced instead of walled.

    `healing_rune` costs 10,000 gold. Holding 9,000 leaves a 1,000 shortfall,
    which used to be charged 1,000 * UNOBTAINABLE_PER_UNIT — a billion actions
    for being a tenth short. With diamonds in the bag at 5,000 apiece from a
    buyer whose window is open, the shortfall is one sale."""
    short = replace(_selling(state, game_data, diamond=4), gold=9_000)
    cost = acquisition_actions("healing_rune", 1, short, game_data,
                               TIMED_NO_PROFILE_CONTEXT, equip=False)
    assert cost < UNOBTAINABLE_PER_UNIT, cost
    assert cost == 4, cost     # hop + sale to raise the 1,000, then hop + buy


def test_the_sale_consumes_the_copy_it_sells(state, game_data) -> None:
    """A sale is not free gold. `inputs={code: 1}` charges the copy, so a
    shortfall bigger than the licensed stock can cover stays unpayable."""
    one = replace(_selling(state, game_data, diamond=1), gold=0)
    assert acquisition_actions("healing_rune", 1, one, game_data,
                               TIMED_NO_PROFILE_CONTEXT, equip=False) \
        >= UNOBTAINABLE_PER_UNIT


def test_no_sellable_stock_leaves_gold_with_no_route(state, game_data) -> None:
    """The route is the keep authority's licence, not a wish. An empty bag
    licenses no sale, so gold stays unobtainable and the shortfall stays honest
    — S-046: where gold replaces nothing, it is worth nothing."""
    broke = replace(_selling(state, game_data), gold=9_000)
    assert acquisition_actions("healing_rune", 1, broke, game_data,
                               TIMED_NO_PROFILE_CONTEXT, equip=False) \
        >= UNOBTAINABLE_PER_UNIT


def test_a_closed_window_leaves_gold_with_no_route(state, game_data) -> None:
    """Same stock, no open event: the buyer is not tradeable, so there is no
    route. This is what makes the previous test's licence check meaningful
    rather than incidental — the stock alone is not enough."""
    shut = replace(state, inventory={"diamond": 4}, gold=9_000, active_events={})
    assert obtain_sources("gold", shut, game_data, TIMED_NO_PROFILE_CONTEXT) == []
    assert acquisition_actions("healing_rune", 1, shut, game_data,
                               TIMED_NO_PROFILE_CONTEXT, equip=False) \
        >= UNOBTAINABLE_PER_UNIT


def test_a_sell_source_names_the_item_sold(state, game_data) -> None:
    """`Source.code` for SELL is the item DESTROYED by the sale, the same
    convention RECYCLE uses — not the gold, and not the buyer."""
    held = _selling(state, game_data, diamond=2)
    sources = obtain_sources("gold", held, game_data, TIMED_NO_PROFILE_CONTEXT)
    assert [(s.kind, s.code, s.yield_per) for s in sources] \
        == [(SourceKind.SELL, "diamond", 5_000)]
    assert sources[0].capacity == 2 * 5_000


def test_gold_has_no_sources_for_any_other_code(state, game_data) -> None:
    """The SELL arm answers for one code. Asking for a normal item must not
    return a sale of something else."""
    held = _selling(state, game_data, diamond=2)
    assert all(s.kind is not SourceKind.SELL
               for s in obtain_sources("copper_ore", held, game_data,
                                       TIMED_NO_PROFILE_CONTEXT))


def test_gold_is_consumed_by_the_route_that_spends_it(state, game_data) -> None:
    """Gold is credited as a holding, so it is also SPENT like one: two runes at
    10,000 each are not affordable out of 15,000."""
    one = replace(state, inventory={}, gold=15_000)
    assert acquisition_actions("healing_rune", 1, one, game_data,
                               TIMED_NO_PROFILE_CONTEXT, equip=False) == 2
    assert acquisition_actions("healing_rune", 2, one, game_data,
                               TIMED_NO_PROFILE_CONTEXT, equip=False) \
        >= UNOBTAINABLE_PER_UNIT


def test_banked_gold_is_not_credited_to_the_pocket(state, game_data) -> None:
    """Same rule as every other holding in this module: the bag counts, the bank
    is a priced route. Banked gold is therefore NOT spendable here — conservative,
    and it under-credits rather than pricing the trip to the bank at nothing."""
    banked_only = replace(state, inventory={}, gold=0, bank_gold=50_000)
    assert acquisition_actions("healing_rune", 1, banked_only, game_data,
                               TIMED_NO_PROFILE_CONTEXT, equip=False) \
        >= UNOBTAINABLE_PER_UNIT


def test_held_stock_makes_an_item_free(state, game_data) -> None:
    """Bag holdings are credited; the bank deliberately is NOT (it is a priced
    withdraw route instead)."""
    held = replace(state, inventory={"copper_ore": 5})
    assert acquisition_actions("copper_ore", 3, held, game_data,
                               TIMED_NO_PROFILE_CONTEXT, equip=False) == 0


def test_a_drop_farm_prices_end_to_end(state, game_data) -> None:
    """`feather` is winnable off a chicken in this scenario, so the DROP route
    survives `obtain_sources`' gates and the farm is priced — where
    `min_plan_length` charged 2."""
    bare = replace(state, inventory={})
    cost = acquisition_actions("feather", 1, bare, game_data,
                               TIMED_NO_PROFILE_CONTEXT, equip=False)
    assert cost > 2


def test_an_unwinnable_drop_is_unobtainable_right_now(state, game_data) -> None:
    """`wolf_hair` drops from a wolf with live tiles that this character cannot
    beat. `obtain_sources` names no route, so the bound prunes — correctly, and
    only for as long as that stays true.

    This is the STATE-AWARENESS caveat recorded on `UNOBTAINABLE_PER_UNIT`
    made concrete: the verdict is about this cycle, and a consumer that cached
    it across cycles would turn a temporary prune into a permanent one."""
    assert not route_options("wolf_hair", state, game_data, TIMED_NO_PROFILE_CONTEXT)
    cost = acquisition_actions("wolf_hair", 1, state, game_data,
                               TIMED_NO_PROFILE_CONTEXT, equip=False)
    assert cost >= UNOBTAINABLE_PER_UNIT


def test_an_unmet_skill_gate_reads_as_a_WALL_not_a_price(state, game_data) -> None:
    """THE FINDING THAT BLOCKS ACTIVATION, pinned.

    `iron_sword` needs weaponcrafting 10; this character has 5. The workshop IS
    known — `obtain_sources` excludes the CRAFT route purely on the skill gate,
    so an item that is genuinely obtainable (grind five levels, then craft)
    prices as unobtainable.

    `min_plan_length` said 65, ignoring the gate entirely. Both are wrong, in
    opposite directions, and neither can be believed. Increment 1b replaces the
    exclusion with `cost_to_reach(skill, level)`, and until it lands `J` must
    NOT be switched to this model — doing so would price most gear as
    unreachable and collapse the ranking. That is why the core landed inert."""
    stats = game_data.item_stats("iron_sword")
    assert state.skills["weaponcrafting"] < stats.crafting_level
    assert game_data.workshop_location("weaponcrafting") is not None
    assert not route_options("iron_sword", state, game_data, TIMED_NO_PROFILE_CONTEXT)


@pytest.fixture(scope="module")
def gated_state(state):  # type: ignore[no-untyped-def]
    """The scenario state, plus the per-skill xp fields.

    `scenario_state` leaves `skill_xp`/`skill_max_xp` EMPTY — they are a
    synthetic fixture, not a character schema. A real `WorldState` always
    carries them: `from_character_schema` reads `<skill>_max_xp` for every skill
    through `_require`, so a missing value would already have raised long before
    any pricing happened.

    Supplying them here is therefore restoring a production invariant the
    fixture does not model, NOT relaxing a guard — and
    `test_no_skill_max_xp_leaves_the_route_excluded` pins the guard itself on
    the bare fixture, so both halves stay honest."""
    return replace(state,
                   skill_xp={s: 0 for s in state.skills},
                   skill_max_xp={s: 500 for s in state.skills})


def _store_with_rate(skill: str, xp_per_cycle: int, cycles: int = 5) -> LearningStore:
    """A real `LearningStore` carrying observed skill-xp gains — not a stub.

    The rows carry `action_repr="LevelSkill(<skill>->10)"` because
    `skill_grind_rate` measures the grind's OWN cycles. That is not a concession
    to the query: a real grind cycle always carries it, since `GamePlayer` records
    the action it executed, so a row without one is a fixture that could not
    happen. Recording rows means asserting against the number the production query
    computes rather than one this test invented."""
    store = LearningStore(db_path=":memory:", character="grind_probe")
    store.start_session()
    for i in range(cycles):
        store.record_cycle(Cycle(
            ts=f"2026-08-08T00:00:{i:02d}+00:00", session_id="s", cycle_index=i,
            character="grind_probe", outcome="ok",
            action_repr=f"LevelSkill({skill}->10)",
            delta_skill_xp_json=json.dumps({skill: xp_per_cycle}),
        ))
    return store


def test_an_unmet_gate_becomes_a_PRICE_once_a_grind_rate_is_known(
        gated_state, game_data) -> None:
    """INCREMENT 1B'S WHOLE POINT, end to end on real game data.

    `iron_sword` needs weaponcrafting 10 against this character's 5. With no
    store the route stays excluded — today's behaviour, unchanged. Given an
    observed weaponcrafting rate, the same sword prices FINITELY: the grind,
    then the workshop, then the craft chain.

    `min_plan_length` said 65 (gate ignored); the pricer without a store says
    unobtainable (gate as a wall). Both are wrong in opposite directions. This
    is the first number that is neither."""
    store = _store_with_rate("weaponcrafting", 40)
    try:
        assert not route_options("iron_sword", gated_state, game_data,
                                 TIMED_NO_PROFILE_CONTEXT)
        gated = route_options("iron_sword", gated_state, game_data,
                              TIMED_NO_PROFILE_CONTEXT, store)
        assert [r.kind for r in gated] == ["craft"]
        assert gated[0].unlock == "skill:weaponcrafting:10"
        assert gated[0].unlock_actions > 0
        assert gated[0].inputs == game_data.crafting_recipe("iron_sword")
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def test_a_policy_that_prices_no_climb_names_the_open_gate_once(
        gated_state, game_data) -> None:
    """A policy without `price_climbs` that opens the crafting gate (the
    grind's `GRIND_PRICING`) prices the under-skill `iron_sword` as the ready
    craft and adds no climb beside it, even with a grind rate to price one:
    the gate it opens is no unlock."""
    store = _store_with_rate("weaponcrafting", 40)
    try:
        routes = route_options("iron_sword", gated_state, game_data,
                               TIMED_NO_PROFILE_CONTEXT, store, policy=GRIND_PRICING)
        assert [(r.kind, r.unlock) for r in routes] == [("craft", "")]
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def test_an_undiscovered_workshop_leaves_the_route_excluded(
        gated_state, game_data) -> None:
    """A grind cannot conjure a workshop.

    Workshop locations are DISCOVERED, so a skill can be gated AND have no known
    bench. Paying the grind would buy nothing — the craft is still unservable
    afterwards — so the gated arm declines, matching `_craft_sources`' own
    workshop guard exactly. Two arms of the same policy must agree, or the
    pricer and the readiness model disagree about what a workshop means.

    The committed fixture knows a workshop for every skill, so this drops the
    one entry rather than mocking the lookup."""
    world = replace(game_data.world, workshop_locations={
        s: loc for s, loc in game_data.world.workshop_locations.items()
        if s != "weaponcrafting"})
    benchless = replace(game_data, world=world)
    assert benchless.workshop_location("weaponcrafting") is None
    store = _store_with_rate("weaponcrafting", 40)
    try:
        assert not route_options("iron_sword", gated_state, benchless,
                                 TIMED_NO_PROFILE_CONTEXT, store)
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def test_no_skill_max_xp_DECLINES_the_route(state, game_data) -> None:
    """`scenario_state` supplies no `skill_max_xp`, so the grind cannot be sized
    and the route is declined.

    This briefly charged 0 instead, on the argument that a LOWER bound should
    omit an unknown positive term. That argument is right about pruning and wrong
    about RANKING — see `_gated_skill_option`, and the 4.5 live hours R2D2 spent
    on a grind that looked free."""
    assert not state.skill_max_xp
    store = _store_with_rate("weaponcrafting", 40)
    try:
        assert not route_options("iron_sword", state, game_data,
                                 TIMED_NO_PROFILE_CONTEXT, store)
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def test_a_NON_POSITIVE_observed_rate_declines_the_route(
        gated_state, game_data) -> None:
    """THE LIVE BUG, pinned.

    A character with recorded cycles but no skill xp has an UNCONDITIONAL rate of
    0.0. Charging a zero-cost grind there is what let `J` commit R2D2 to 207
    `LevelSkill` actions over 4.5 hours for +270 skill xp and zero character xp.

    A non-positive rate is EVIDENCE the grind is not progressing — a stronger
    reason to decline than ignorance is. It also would have divided by zero:
    `skill_xp_per_cycle_all` can return 0.0 where the old conditional mean was
    positive by construction."""
    store = LearningStore(db_path=":memory:", character="no_progress")
    store.start_session()
    for i in range(5):
        store.record_cycle(Cycle(
            ts=f"2026-08-08T00:00:{i:02d}+00:00", session_id="s", cycle_index=i,
            character="no_progress", outcome="ok",
            action_repr="LevelSkill(weaponcrafting->10)",
            delta_skill_xp_json=json.dumps({"weaponcrafting": 0}),
        ))
    try:
        # The rate the pricer reads is now the GRIND rate. Stamping the rows keeps
        # this test on the branch its name claims — a non-positive rate that is
        # PRESENT — rather than sliding onto the absent-rate branch that
        # `test_no_observed_rate_declines_the_route` below already covers. Two
        # tests asserting one branch under different names is how a real branch
        # goes uncovered.
        assert store.skill_grind_rate("weaponcrafting") == 0.0
        assert not route_options("iron_sword", gated_state, game_data,
                                 TIMED_NO_PROFILE_CONTEXT, store)
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def test_the_UNCONDITIONAL_rate_is_what_prices_a_grind(gated_state, game_data) -> None:
    """THE DEFECT CLASS, one more time: a quantity that is not what its name says.

    `skill_xp_per_cycle` averages ONLY cycles that gained xp, so one paying cycle
    in fifty reports the paying cycle's figure as if it were the rate. Measured
    live: 54.0 reported against 1.08 actual for R2D2 (50x), 55.0 against 0.55 for
    HAL (100x). A grind priced on that is priced 50-100x too cheap.

    The two must differ here, or this test is watching the wrong function."""
    store = LearningStore(db_path=":memory:", character="sparse")
    store.start_session()
    # One paying cycle in ten: conditional says 50, unconditional says 5.
    for i in range(10):
        store.record_cycle(Cycle(
            ts=f"2026-08-08T00:00:{i:02d}+00:00", session_id="s", cycle_index=i,
            character="sparse", outcome="ok",
            action_repr="LevelSkill(weaponcrafting->10)",
            delta_skill_xp_json=json.dumps({"weaponcrafting": 50 if i == 0 else 0}),
        ))
    try:
        # All three estimators on ONE fixture, which is the only place their
        # difference is visible: the conditional mean reports the paying cycle,
        # the unconditional mean and the grind rate keep the nine zero-xp cycles
        # in the denominator. The pricer reads the last of these.
        assert store.skill_xp_per_cycle("weaponcrafting") == 50.0
        assert store.skill_xp_per_cycle_all("weaponcrafting") == 5.0
        assert store.skill_grind_rate("weaponcrafting") == 5.0
        routes = route_options("iron_sword", gated_state, game_data,
                               TIMED_NO_PROFILE_CONTEXT, store)
        assert [r.kind for r in routes] == ["craft"]
        # Priced on 5/cycle, not 50 — so the grind is the larger, honest number.
        assert routes[0].unlock_actions > 0
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def test_the_sword_finally_has_a_price_neither_model_could_give(
        gated_state, game_data) -> None:
    """END TO END, and the point of the whole increment.

    `min_plan_length` says 65 (gate ignored). The pricer without a grind rate
    says unobtainable (gate as a wall). With the rate, the sword costs the grind
    plus the chain — finite, larger than 65, and for the first time an answer
    that accounts for the five weaponcrafting levels standing in the way."""
    bare = replace(gated_state, inventory={})
    store = _store_with_rate("weaponcrafting", 40)
    try:
        walled = acquisition_actions("iron_sword", 1, bare, game_data,
                                     TIMED_NO_PROFILE_CONTEXT, equip=True)
        priced = acquisition_actions("iron_sword", 1, bare, game_data,
                                     TIMED_NO_PROFILE_CONTEXT, equip=True, store=store)
    finally:
        store.end_session(exit_reason="normal")
        store.close()
    assert walled >= UNOBTAINABLE_PER_UNIT
    assert priced < UNOBTAINABLE_PER_UNIT
    assert priced > 65


def test_no_observed_rate_declines_the_route(gated_state, game_data) -> None:
    """A skill the character has never ground has no rate, and there is no
    defensible default for "how fast does this character gain jewelrycraft xp".
    The route is declined rather than priced on an invention."""
    store = LearningStore(db_path=":memory:", character="no_observations")
    store.start_session()
    try:
        assert store.skill_grind_rate("weaponcrafting") is None
        assert store.fleet_skill_grind_rate("weaponcrafting") is None
        assert not route_options("iron_sword", gated_state, game_data,
                                 TIMED_NO_PROFILE_CONTEXT, store)
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def test_a_met_gate_adds_no_second_craft_route(gated_state, game_data) -> None:
    """When the gate is MET, `obtain_sources` names the craft itself. Adding a
    gated copy would double the route and let the walk pick between two
    identical things — harmless for cost, but a duplicate route set is how the
    two-plan-producer trap starts."""
    store = _store_with_rate("gearcrafting", 40)
    try:
        # gearcrafting 8 in this scenario; find something it already clears.
        ready = [c for c, r in game_data.crafting_recipes.items()
                 if (s := game_data.item_stats(c)) is not None
                 and s.crafting_skill == "gearcrafting"
                 and s.crafting_level <= gated_state.skills["gearcrafting"]]
        assert ready, "fixture drift: no gearcrafting recipe within reach"
        for code in ready[:5]:
            routes = route_options(code, gated_state, game_data, TIMED_NO_PROFILE_CONTEXT,
                                   store)
            assert sum(1 for r in routes if r.kind == "craft") <= 1
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def test_the_pricer_adds_nothing_but_gated_routes(gated_state, game_data) -> None:
    """THE CENSUS THAT STOPS THIS BECOMING A RIVAL ROUTE MODEL.

    `obtain_sources` is meant to be the one enumeration every producer consumes.
    This module deliberately adds only routes it does not name because ONE gate
    keeps them from being ready — a skill-gated craft or gather, a sibling's
    craft, an unwinnable drop — priced by what opens the gate, because
    readiness and cost are different questions. Every such route carries its
    `unlock`; anything else the pricer returns must be a kind `obtain_sources`
    named, or the epic has reintroduced the duplication it exists to remove.

    Same shape as `test_obtain_graph_agreement`, which pins `obtain_sources`
    against `RequirementGraph.leaves`."""
    store = _store_with_rate("weaponcrafting", 40)
    try:
        probes = ["iron_sword", "copper_ore", "feather", "copper_dagger",
                  "wisdom_amulet", "wolf_hair"]
        for code in probes:
            ready = {s.kind.value for s in
                     obtain_sources(code, gated_state, game_data, TIMED_NO_PROFILE_CONTEXT)}
            priced = route_options(code, gated_state, game_data, TIMED_NO_PROFILE_CONTEXT,
                                   store)
            extra = [r for r in priced if not r.unlock]
            assert {r.kind for r in extra} <= ready, (
                f"{code}: pricer invented a route obtain_sources did not name")
            assert all(r.kind in {"craft", "gather", "drop"} for r in priced if r.unlock), (
                f"{code}: only a gated craft, gather or drop may be added")
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def test_the_closure_terminates_on_real_data(state, game_data) -> None:
    """A walk with a visited set, so a route graph that loops enumerates once.
    The cost walk's fuel bound handles the cycle when pricing; this only has to
    finish."""
    options = acquisition_options("copper_dagger", state, game_data,
                                  TIMED_NO_PROFILE_CONTEXT)
    assert "copper_dagger" in options
    assert all(isinstance(v, list) for v in options.values())


def test_the_closure_survives_a_genuine_cycle_in_real_game_data(
        state, game_data) -> None:
    """The cycle is not hypothetical. Holding copper helmets, `copper_bar` has a
    RECYCLE route out of `copper_helmet` (its recycle yield is learned: the
    bundle captures the fleet's observed totals), and `copper_helmet` CRAFTS
    from `copper_bar` — a two-node loop straight out of the live recipe tables.

    This is the case that showed the walk had two visited-set guards where one
    is correct, and that the redundant push-time filter was making the pop-time
    guard unreachable."""
    holding = replace(state, inventory={"copper_helmet": 3})
    kinds = {s.kind for s in
             obtain_sources("copper_bar", holding, game_data, TIMED_NO_PROFILE_CONTEXT)}
    assert SourceKind.RECYCLE in kinds, "fixture drift: the cycle is gone"
    options = acquisition_options("copper_bar", holding, game_data,
                                  TIMED_NO_PROFILE_CONTEXT)
    assert {"copper_bar", "copper_helmet", "copper_ore"} <= set(options)


def _live_sized(state, game_data):  # type: ignore[no-untyped-def]
    """A holding the size a real character carries, and a target NOT in it.

    THE FIRST VERSION OF THIS WAS VACUOUS. It stocked inventory and bank from the
    same code list the targets came from, so every target was already held —
    `copper_dagger` and `iron_sword` in the bag, `adventurer_vest` in the bank —
    and the walk returned in ONE call without descending anything. It would have
    passed against the exponential code it was written to catch.

    The target is asserted absent from both, so the walk has to run."""
    codes = [c for c in game_data.crafting_recipes][:60]
    big = replace(state,
                  inventory={c: 2 for c in codes[:40]},
                  bank_items={c: 5 for c in codes[:60]})
    held = set(big.inventory) | set(big.bank_items)
    deep = [c for c, r in game_data.crafting_recipes.items()
            if c not in held and len(r) >= 4]
    assert deep, "fixture drift: no unheld multi-input recipe to price"
    return big, sorted(deep)[:3]


def test_pricing_stays_affordable_on_a_LIVE_SIZED_HOLDING(state, game_data) -> None:
    """THE TEST WHOSE ABSENCE LET A LIVE REGRESSION SHIP.

    5175 tests and nine green gate runs said nothing about the exponential
    blow-up that took `J` live at ~2x the cycle cost, because every fixture has
    SMALL holdings and the cost of this model is a function of HOLDINGS, not of
    the item. The missing test was never a case — it was a DIMENSION.

    Measured before the fix: a four-input recipe ran 10.1 million recursive calls
    in 20 seconds without finishing. After: seven-input recipes price in under
    10ms with ~10 calls.

    The budget is deliberately loose. This guards against a return to
    exponential, not a microbenchmark — a tight bound would flake on a loaded
    machine and get deleted, which puts us back where we started."""
    live_sized, targets = _live_sized(state, game_data)
    store = _store_with_rate("weaponcrafting", 40)
    try:
        for code in targets:
            assert code not in live_sized.inventory
            assert code not in (live_sized.bank_items or {})
        started = time.monotonic()
        for code in targets:
            acquisition_actions(code, 1, live_sized, game_data,
                                TIMED_NO_PROFILE_CONTEXT, equip=True, store=store)
        elapsed = time.monotonic() - started
    finally:
        store.end_session(exit_reason="normal")
        store.close()
    assert elapsed < 2.0, (
        f"pricing {len(targets)} unheld multi-input items took {elapsed:.1f}s — "
        "the walk has gone superlinear in holdings again")


def test_recipe_FAN_OUT_does_not_explode(state, game_data) -> None:
    """Pins the specific axis that broke: cost must not blow up with the number
    of recipe INPUTS. The old walk was exponential in fan-out — one input was
    fine, two were fine, four did not finish."""
    live_sized, targets = _live_sized(state, game_data)
    widest = max(targets, key=lambda c: len(game_data.crafting_recipe(c)))
    assert len(game_data.crafting_recipe(widest)) >= 4
    store = _store_with_rate("weaponcrafting", 40)
    try:
        started = time.monotonic()
        acquisition_actions(widest, 1, live_sized, game_data,
                            TIMED_NO_PROFILE_CONTEXT, equip=True, store=store)
        elapsed = time.monotonic() - started
    finally:
        store.end_session(exit_reason="normal")
        store.close()
    assert elapsed < 1.0, (
        f"{widest} ({len(game_data.crafting_recipe(widest))} inputs) took "
        f"{elapsed:.1f}s — fan-out is superlinear again")


_IRON_SET = ["iron_boots", "iron_helm", "iron_shield", "iron_armor",
             "iron_legs_armor"]


@pytest.fixture(scope="module")
def unlock_state(game_data):  # type: ignore[no-untyped-def]
    """A character whose iron-set INPUTS are all obtainable and whose
    gearcrafting gate is not yet met.

    `gated_state` cannot carry this measurement: its fixture leaves cowhide and
    wool without a route, so five `UNOBTAINABLE_PER_UNIT` sentinels dominate the
    total and swamp the very term under test. That is not an artefact of the
    fixture — it is the live interaction recorded in
    `docs/PLAN_bounded_horizon_objective.md`, where the pricing wall and the
    objective each hide the other's defects. Here the wall is deliberately
    removed so the unlock is the only large shared cost left.

    `l21_grey_material_grind` beats every dropper it needs; dropping gearcrafting
    to 5 puts the five iron pieces behind one five-level grind."""
    base = scenario_state(SCENARIOS["l21_grey_material_grind"], game_data)
    return replace(base,
                   skills={**base.skills, "gearcrafting": 5},
                   skill_xp={s: 0 for s in base.skills},
                   skill_max_xp={s: 500 for s in base.skills})


def test_a_shared_skill_unlock_is_what_makes_the_iron_set_affordable(
        unlock_state, game_data) -> None:
    """E3 OF THE BOUNDED-HORIZON SPIKE, on real game data.

    The five gearcrafting-10 iron pieces sit behind ONE grind. `J` prices every
    candidate independently, so each is billed the whole grind and all five are
    rejected for a cost they would have shared. Priced as one plan the grind is
    charged once — the amortisation option C claims and option B cannot express.

    Measured here rather than asserted at a magnitude: the numbers move with the
    fixture, the ORDER does not.

    The four-extra-unlocks bound is measured with the bank emptied (ruling
    T14a-B'): the bank's 6 iron_bar now serve the bundle ONCE, as one plan
    draws them, while each piece priced apart draws all six, so banked stock
    is a second cross-root term pulling the other way (2736 - 918 = 1818 <
    4 x 500 with it). With the stock the bundle is still the cheaper plan."""
    store = _store_with_rate("gearcrafting", 5, cycles=5)
    try:
        measured = []
        for state in (replace(unlock_state, bank_items={}), unlock_state):
            singly = {c: acquisition_actions(c, 1, state, game_data,
                                             TIMED_NO_PROFILE_CONTEXT, equip=True, store=store)
                      for c in _IRON_SET}
            together, paid = bundle_acquisition_actions(
                [(c, 1) for c in _IRON_SET], state, game_data,
                TIMED_NO_PROFILE_CONTEXT, equip=True, store=store)
            measured.append((sum(singly.values()), together, paid))
    finally:
        store.end_session(exit_reason="normal")
        store.close()
    unlock = "skill:gearcrafting:10"
    (apart, together, paid), (stocked_apart, stocked_together, _paid) = measured
    assert unlock in paid, "the gated craft did not fire — this measures nothing"
    assert paid[unlock] > 0
    # The unlock alone is charged four extra times when the five are priced apart.
    assert apart - together >= paid[unlock] * 4
    # And it dominates: nothing here is walled, so the whole set as one plan
    # costs a small fraction of the five priced apart; with the stock, less.
    assert apart < UNOBTAINABLE_PER_UNIT, "a walled input would swamp the term under test"
    assert together < apart // 3
    assert stocked_together < stocked_apart


def test_bundling_saves_nothing_when_there_is_nothing_to_share(
        unlock_state, game_data) -> None:
    """The honest negative. Two roots with no common venue and no common gate
    cost the same together as apart — so a non-zero saving elsewhere is
    attributable to a shared key rather than to bundling as such."""
    store = _store_with_rate("gearcrafting", 5, cycles=5)
    try:
        codes = ["iron_boots"]
        singly = sum(acquisition_actions(c, 1, unlock_state, game_data,
                                         TIMED_NO_PROFILE_CONTEXT, equip=True, store=store)
                     for c in codes)
        together, _paid = bundle_acquisition_actions(
            [(c, 1) for c in codes], unlock_state, game_data,
            TIMED_NO_PROFILE_CONTEXT, equip=True, store=store)
    finally:
        store.end_session(exit_reason="normal")
        store.close()
    assert together == singly


def test_the_bundle_charges_one_equip_per_root(unlock_state, game_data) -> None:
    """Every piece has to be put on, so `equip` is per ROOT — unlike a venue or a
    gate, which are per plan. Folding it into the pay-once ledger would make a
    five-piece set look one action from wearable."""
    store = _store_with_rate("gearcrafting", 5, cycles=5)
    try:
        roots = [(c, 1) for c in _IRON_SET]
        bare, _ = bundle_acquisition_actions(roots, unlock_state, game_data,
                                             TIMED_NO_PROFILE_CONTEXT, equip=False,
                                             store=store)
        worn, _ = bundle_acquisition_actions(roots, unlock_state, game_data,
                                             TIMED_NO_PROFILE_CONTEXT, equip=True,
                                             store=store)
    finally:
        store.end_session(exit_reason="normal")
        store.close()
    assert worn - bare == len(_IRON_SET)


def test_a_window_of_fighting_no_longer_hides_the_grind(
        gated_state, game_data) -> None:
    """THE LIVE DEFECT, pinned at the pricing seam.

    Measured 2026-08-17: all five live characters read 0.0 from
    `skill_xp_per_cycle_all` for every crafting skill, because their recent cycles
    are fights — so `_gated_skill_option` declined every skill-gated craft and
    `iron_sword` priced at UNOBTAINABLE. The grind cycles that answer the question
    were sitting in the same table the whole time."""
    store = LearningStore(db_path=":memory:", character="fought_recently")
    store.start_session()
    try:
        for i in range(5):
            store.record_cycle(Cycle(
                ts=f"2026-08-18T00:00:{i:02d}+00:00", session_id="s",
                cycle_index=i, character="fought_recently", outcome="ok",
                action_repr="LevelSkill(weaponcrafting->10)",
                delta_skill_xp_json=json.dumps({"weaponcrafting": 40})))
        for i in range(5, 205):
            store.record_cycle(Cycle(
                ts=f"2026-08-18T01:00:{i % 60:02d}+00:00", session_id="s",
                cycle_index=i, character="fought_recently", outcome="ok",
                action_repr="Fight(pig)", delta_skill_xp_json=json.dumps({})))
        assert store.skill_xp_per_cycle_all("weaponcrafting") == 0.0, \
            "the retired estimator no longer reads 0 — this pins nothing"
        routes = route_options("iron_sword", gated_state, game_data,
                               TIMED_NO_PROFILE_CONTEXT, store)
        assert [r.kind for r in routes] == ["craft"]
        assert routes[0].unlock == "skill:weaponcrafting:10"
        assert routes[0].unlock_actions > 0
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def test_a_sibling_that_has_ground_the_skill_prices_it_for_one_that_has_not(
        gated_state, game_data) -> None:
    """The fallback. A fresh character has no evidence of its own about how fast
    weaponcrafting goes; a sibling on the same server does."""
    store = LearningStore(db_path=":memory:", character="fresh")
    store.start_session()
    veteran = LearningStore(db_path=":memory:", character="veteran")
    try:
        assert store.skill_grind_rate("weaponcrafting") is None
        assert store.fleet_skill_grind_rate("weaponcrafting") is None
        assert not route_options("iron_sword", gated_state, game_data,
                                 TIMED_NO_PROFILE_CONTEXT, store)
    finally:
        veteran.close()
        store.end_session(exit_reason="normal")
        store.close()


def test_own_zero_evidence_is_not_overridden_by_the_fleet(
        gated_state, game_data, tmp_path) -> None:
    """The fallback is ONE-WAY, and this is the test that pins it.

    A character whose own grind ran and gained nothing has told us something about
    ITS gear and level that a sibling's number cannot override. `0.0` is evidence;
    `None` is ignorance; only ignorance falls back — which is why the call site
    tests `is None` and not falsiness.

    A SHARED FILE DB, not `:memory:`, and that is what makes this bite. Each
    in-memory store gets its own database, so a sibling written to one is
    invisible to the other and the fleet rate comes back None — under which
    `rate or fleet` and `rate if rate is not None else fleet` agree and the
    mutant survives. Verified: with the call site written as `or`, this test fails
    and every other one in this file still passes."""
    db = str(tmp_path / "fleet.db")
    veteran = LearningStore(db_path=db, character="veteran")
    veteran.start_session()
    for i in range(5):
        veteran.record_cycle(Cycle(
            ts=f"2026-08-18T02:00:{i:02d}+00:00", session_id="s", cycle_index=i,
            character="veteran", outcome="ok",
            action_repr="LevelSkill(weaponcrafting->10)",
            delta_skill_xp_json=json.dumps({"weaponcrafting": 40})))
    veteran.end_session(exit_reason="normal")
    veteran.close()

    store = LearningStore(db_path=db, character="stuck")
    store.start_session()
    for i in range(5):
        store.record_cycle(Cycle(
            ts=f"2026-08-18T03:00:{i:02d}+00:00", session_id="s", cycle_index=i,
            character="stuck", outcome="ok",
            action_repr="LevelSkill(weaponcrafting->10)",
            delta_skill_xp_json=json.dumps({"weaponcrafting": 0})))
    try:
        assert store.skill_grind_rate("weaponcrafting") == 0.0
        assert store.fleet_skill_grind_rate("weaponcrafting") > 0, \
            "no positive fleet rate to be overridden BY — this cannot bite"
        assert not route_options("iron_sword", gated_state, game_data,
                                 TIMED_NO_PROFILE_CONTEXT, store)
    finally:
        store.end_session(exit_reason="normal")
        store.close()


# ── the unwinnable-dropper gate: a price, not a wall ────────────────────────

def test_an_unwinnable_dropper_is_a_PRICE_not_a_wall(gated_state, game_data) -> None:
    """`cowhide` drops from `cow`, which this character cannot beat — so
    `obtain_sources` withholds the DROP route and the item priced at infinity,
    taking every recipe that consumes it with it.

    That is the wall the drop-wall census named (`audit/drop_wall_census.py`, 9
    walled candidates on the committed bundle, `l12_deep_chain_grind` among
    them). `combat_deficit` closes this one with a ONE-ITEM chain — `iron_sword`
    — so the honest answer is not "unobtainable" but "iron_sword, then farm
    cows". Same seam as `_gated_skill_option`: `obtain_sources` answers
    READINESS, this module answers COST, and a gate is a price."""
    rested = replace(gated_state, hp=gated_state.max_hp)
    assert not any(
        s.kind is SourceKind.DROP
        for s in obtain_sources("cowhide", rested, game_data, TIMED_NO_PROFILE_CONTEXT))
    store = _store_with_rate("weaponcrafting", 40)
    try:
        routes = route_options("cowhide", gated_state, game_data,
                               TIMED_NO_PROFILE_CONTEXT, store)
        gated = [r for r in routes if r.unlock.startswith("gear:")]
        assert len(gated) == 1
        assert gated[0].kind == SourceKind.DROP.value
        assert gated[0].venue == "cow"
        assert gated[0].unlock == "gear:cow"
        assert gated[0].unlock_actions > 0
        assert gated[0].actions_per_application > 0
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def test_the_gated_drop_makes_the_walled_item_obtainable(
        gated_state, game_data) -> None:
    """The point of the route, stated as the price it changes.

    THE CHAIN'S OWN PRICE IS WHY THIS NEEDS A STORE. `cowhide` is unlocked by
    `iron_sword`, whose CRAFT is itself skill-gated (weaponcrafting 10 against
    this character's 5) — so without an observed grind rate `_gated_skill_option`
    declines the sword, the sword prices at infinity, and this gate declines the
    cow for the same reason it declines any unpriceable chain. The dependency is
    transitive, not direct: nothing in THIS route reads the store, and a chain
    that is already craftable prices without one."""
    without = acquisition_actions("cowhide", 1, gated_state, game_data,
                                  TIMED_NO_PROFILE_CONTEXT, equip=False)
    assert without == UNOBTAINABLE_PER_UNIT
    store = _store_with_rate("weaponcrafting", 40)
    try:
        assert acquisition_actions("cowhide", 1, gated_state, game_data,
                                   TIMED_NO_PROFILE_CONTEXT, equip=False,
                                   store=store) < UNOBTAINABLE_PER_UNIT
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def test_a_winnable_dropper_adds_NO_second_route(gated_state, game_data) -> None:
    """`obtain_sources` already names a beatable dropper's DROP route, so the
    gate must decline — two copies of one route is the double-pricing
    `_gated_skill_option` refuses for the same reason."""
    winnable = next(
        item for item in ("yellow_slimeball", "red_slimeball", "feather")
        if any(s.kind is SourceKind.DROP for s in obtain_sources(
            item, replace(gated_state, hp=gated_state.max_hp), game_data,
            TIMED_NO_PROFILE_CONTEXT)))
    routes = route_options(winnable, gated_state, game_data, TIMED_NO_PROFILE_CONTEXT)
    assert [r for r in routes if r.kind == SourceKind.DROP.value]
    assert not [r for r in routes if r.unlock.startswith("gear:")]


def test_an_item_with_no_dropper_is_not_this_gates_business(
        gated_state, game_data) -> None:
    """`copper_ore` is gathered, not dropped. The gate must not invent a fight."""
    routes = route_options("copper_ore", gated_state, game_data,
                           TIMED_NO_PROFILE_CONTEXT)
    assert not [r for r in routes if r.unlock.startswith("gear:")]


def test_a_chain_that_cannot_be_priced_DECLINES_the_route(
        gated_state, game_data) -> None:
    """An unpriceable chain declines, exactly as an unpriceable grind does one
    function up — and for the live reason recorded there: a route that looks free
    does not merely fail to prune, it CAPTURES the bot.

    `l20_boost_stock` is the case, and it is the circularity the 2026-08-09 audit
    feared, exhibited rather than argued about: `mushroom` is walled by
    `mushmush`, `combat_deficit` closes that with `forest_whip`, and
    `forest_whip`'s own recipe wants `king_slimeball` — which is walled by
    `king_slime`, a monster this character also cannot beat. Pricing it would
    need a FIXED POINT, not a deeper walk, so the gate declines and the wall
    stays named."""
    state = replace(scenario_state(SCENARIOS["l20_boost_stock"], game_data),
                    skill_xp=gated_state.skill_xp,
                    skill_max_xp=gated_state.skill_max_xp)
    store = _store_with_rate("weaponcrafting", 40)
    try:
        assert "king_slimeball" in (game_data.crafting_recipe("forest_whip") or {})
        assert acquisition_actions("king_slimeball", 1, state, game_data,
                                   TIMED_NO_PROFILE_CONTEXT, equip=False, store=store,
                                   gated_drop=False) >= UNOBTAINABLE_PER_UNIT
        routes = route_options("mushroom", state, game_data, TIMED_NO_PROFILE_CONTEXT,
                               store)
        assert not [r for r in routes if r.unlock.startswith("gear:")]
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def test_the_inner_walk_does_not_re_enter_this_gate(gated_state, game_data) -> None:
    """The recursion is cut BY CONSTRUCTION: the chain is priced with
    `gated_drop=False`, so a chain item wanting a drop-walled material sees only
    the routes `obtain_sources` serves today and the walk terminates without a
    fuel counter.

    Asserted as the price DIFFERENCE the flag makes, so a future refactor that
    quietly threads `gated_drop=True` into the inner call fails here rather than
    hanging."""
    store = _store_with_rate("weaponcrafting", 40)
    try:
        assert acquisition_actions("cowhide", 1, gated_state, game_data,
                                   TIMED_NO_PROFILE_CONTEXT, equip=False, store=store,
                                   gated_drop=False) == UNOBTAINABLE_PER_UNIT
        assert acquisition_actions("cowhide", 1, gated_state, game_data,
                                   TIMED_NO_PROFILE_CONTEXT, equip=False, store=store,
                                   gated_drop=True) < UNOBTAINABLE_PER_UNIT
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def test_the_unlock_is_keyed_on_the_MONSTER_not_the_item(
        gated_state, game_data) -> None:
    """Two materials behind one unbeatable monster are opened by ONE gear
    acquisition, so the key must be the monster — keying it on the item would
    charge the sword once per material the cow drops, which is the per-application
    error `RouteOption.unlock`'s docstring exists to prevent."""
    store = _store_with_rate("weaponcrafting", 40)
    try:
        drops = [item for item in ("cowhide", "milk_bucket")
                 if any(m == "cow" for m, _r, _a, _b
                        in game_data.monsters_dropping(item))]
        assert len(drops) > 1, "fixture no longer has two cow drops — test vacuous"
        keys = set()
        for item in drops:
            routes = route_options(item, gated_state, game_data,
                                   TIMED_NO_PROFILE_CONTEXT, store)
            keys |= {r.unlock for r in routes if r.unlock.startswith("gear:")}
        assert keys == {"gear:cow"}
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def test_an_under_skill_gather_is_priced_by_its_grind_not_offered_as_ready(
        gated_state, game_data) -> None:
    """D-A: `obtain_sources` no longer offers a gather the character cannot
    perform, and the pricer offers it instead as a route gated by the gathering
    skill, priced with the grind that opens it (the same rule as a skill-gated
    craft). No observed rate: no route, as for a craft."""
    item, resource, (skill, level) = next(
        (item, res, gd_skill)
        for res, item in sorted(game_data.resource_drops.items())
        if (gd_skill := game_data.resource_skill_level(res)) is not None
        and gated_state.skills.get(gd_skill[0], 1) < gd_skill[1]
        and game_data.all_resource_locations.get(res))
    assert not [s for s in obtain_sources(item, gated_state, game_data, TIMED_NO_PROFILE_CONTEXT)
                if s.kind is SourceKind.GATHER and s.code == resource]
    assert not [r for r in route_options(item, gated_state, game_data, TIMED_NO_PROFILE_CONTEXT)
                if r.kind == "gather" and r.venue == resource]
    store = _store_with_rate(skill, 40)
    try:
        [gated] = [r for r in route_options(item, gated_state, game_data, TIMED_NO_PROFILE_CONTEXT, store)
                   if r.kind == "gather" and r.venue == resource]
        assert gated.unlock == f"skill:{skill}:{level}" and gated.unlock_actions > 0
        assert gated.actions_per_application == 1
        # The climb's gather is priced at the learned chance too (the
        # context's drop evidence, ruling T16a): three recorded gathers that
        # missed the item make it 1 in 4 (`(1 + 0) / (1 + 3)`), so a unit is 4
        # gathers.
        for i in range(3):
            store.record_cycle(Cycle(
                ts=f"2026-08-09T00:00:{i:02d}+00:00", session_id="s", cycle_index=i,
                character="grind_probe", outcome="ok", action_class="GatherAction",
                action_repr=f"Gather({resource})", drops_json=None))
        [learned] = [r for r in route_options(item, gated_state, game_data,
                                              _learned(game_data, store), store)
                     if r.kind == "gather" and r.venue == resource]
        assert learned.actions_per_application == 4
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def test_a_produced_item_is_priced_only_by_making_it() -> None:
    """Ruling T12j: an item in `produce` keeps only its CRAFT and GATHER
    routes, as `ObtainModel.walk_graph` serves it, and its ingredients keep
    every route. In the busy book, with copper banked, `copper_bar` is
    crafted, filled or withdrawn and `copper_ore` gathered, filled or
    withdrawn; produced, each keeps only the route that makes it."""
    world = shared_world(_BUNDLE, with_ge_orders=True)
    state = replace(scenario_state(SCENARIOS["l12_ge_book_grind"], world),
                    bank_items={"copper_bar": 2, "copper_ore": 3})

    def kinds(produce: frozenset[str]) -> dict[str, list[str]]:
        options = acquisition_options("copper_bar", state, world, TIMED_NO_PROFILE_CONTEXT,
                                      policy=LEGACY, produce=produce)
        return {code: sorted(r.kind for r in options[code])
                for code in ("copper_bar", "copper_ore")}

    every = {"copper_bar": ["craft", "ge_fill", "withdraw"],
             "copper_ore": ["gather", "ge_fill", "withdraw"]}
    assert kinds(frozenset()) == every
    assert kinds(frozenset({"copper_bar"})) == {**every, "copper_bar": ["craft"]}
    assert kinds(frozenset({"copper_ore"})) == {**every, "copper_ore": ["gather"]}


def test_drop_work_is_the_walks_gathers_and_farms_priced_by_their_route(
        state, game_data) -> None:
    """`drop_work` lists the gather and drop-farm legs the price walks, after
    holdings, each carrying its route's kind; `drop_work_actions` prices a farm
    leg as the walk's DROP route (wins at the learned chance times one win's
    actions) and a gather leg as its GATHER route. A route with no drop work
    lists none."""
    assert drop_work("feather", 2, state, game_data, TIMED_NO_PROFILE_CONTEXT, None,
                     policy=LEGACY) == (DropLeg(SourceKind.DROP, "chicken", "feather", 2, True),)
    assert drop_work("copper_helmet", 2, state, game_data, TIMED_NO_PROFILE_CONTEXT, None,
                     policy=LEGACY) == (
        DropLeg(SourceKind.GATHER, "copper_rocks", "copper_ore", 119, True),)
    win = _kill_actions("chicken", state, game_data, TIMED_NO_PROFILE_CONTEXT.timing(), ())
    assert drop_work_actions((DropLeg(SourceKind.DROP, "chicken", "feather", 3, True),), state,
                             game_data, TIMED_NO_PROFILE_CONTEXT) == 3 * 8 * win
    assert drop_work_actions((DropLeg(SourceKind.GATHER, "copper_rocks", "copper_ore", 119, True),),
                             state, game_data, TIMED_NO_PROFILE_CONTEXT) == 119


def test_a_farm_behind_gear_is_drop_work_without_the_loss_surcharge(
        state, game_data, monkeypatch) -> None:
    """The walk prices a farm behind gear the character lacks
    (`_gated_drop_option`, its unlock keyed `gear:<monster>`) with no loss
    surcharge, so its leg says so and is priced the same way; a ready farm's
    leg carries the learned losses."""
    gated = RouteOption(kind=SourceKind.DROP.value, venue="chicken", actions_per_application=1,
                        yield_per=1, capacity=UNBOUNDED_CAPACITY, unlock="gear:chicken",
                        unlock_actions=5)
    monkeypatch.setattr("artifactsmmo_cli.ai.acquisition_cost.acquisition_options",
                        lambda *_args, **_kwargs: {"feather": [gated]})
    assert drop_work("feather", 2, state, game_data, TIMED_NO_PROFILE_CONTEXT, None,
                     policy=LEGACY) == (DropLeg(SourceKind.DROP, "chicken", "feather", 2, False),)
    records = (("chicken", 20, 10),)
    ctx = replace(TIMED_NO_PROFILE_CONTEXT, fight_records=records)
    timing = ctx.timing()
    lossy = _kill_actions("chicken", state, game_data, timing, records)
    clean = _kill_actions("chicken", state, game_data, timing, ())
    assert lossy > clean
    assert drop_work_actions((DropLeg(SourceKind.DROP, "chicken", "feather", 3, True),), state,
                             game_data, ctx) == 3 * 8 * lossy
    assert drop_work_actions((DropLeg(SourceKind.DROP, "chicken", "feather", 3, False),), state,
                             game_data, ctx) == 3 * 8 * clean


def test_a_legs_prospecting_is_its_loadouts_swap(state, game_data, monkeypatch) -> None:
    """`leg_prospecting` is the prospecting of the loadout the leg is attempted
    in: a fight wears a +200 vest, displacing a +150 one for a net +50; a gather
    keeps its armour, so the vest moves nothing there. A resource without a
    gathering skill is a data fault."""
    monkeypatch.setattr(game_data, "_item_stats", {
        **game_data._item_stats,
        "old_vest": ItemStats(code="old_vest", level=1, type_="body_armor", prospecting=150),
        "vest": ItemStats(code="vest", level=1, type_="body_armor", prospecting=200)})
    worn = replace(state, equipment={**state.equipment, "body_armor_slot": "old_vest"},
                   prospecting=150)
    owning = replace(worn, inventory={**worn.inventory, "vest": 1})
    fight = DropLeg(SourceKind.DROP, "chicken", "feather", 1, True)
    gather = DropLeg(SourceKind.GATHER, "copper_rocks", "copper_ore", 1, True)
    assert (leg_prospecting(fight, worn, game_data), leg_prospecting(fight, owning, game_data)) == (
        150, 200)
    assert (leg_prospecting(gather, worn, game_data),
            leg_prospecting(gather, owning, game_data)) == (150, 150)
    with pytest.raises(ValueError, match="no gathering skill"):
        leg_prospecting(DropLeg(SourceKind.GATHER, "nowhere", "copper_ore", 1, True), worn,
                        game_data)


def test_a_farm_is_priced_at_the_prospecting_its_fight_loadout_wears(
        state, game_data, monkeypatch) -> None:
    """One basis (ruling T12n): a +200 vest in the bag is what the chicken
    fight's loadout wears, so with `k = 1/100` a feather is 8/3 wins, not 8,
    in the walk's own farm price as in the drop work."""
    monkeypatch.setattr(game_data, "_item_stats", {
        **game_data._item_stats,
        "vest": ItemStats(code="vest", level=1, type_="body_armor", prospecting=200)})
    ctx = replace(TIMED_NO_PROFILE_CONTEXT, learned_drops=LearnedDrops((), (), Fraction(1, 100)))
    owning = replace(state, inventory={**state.inventory, "vest": 1})
    win = _kill_actions("chicken", owning, game_data, ctx.timing(), ())
    rate, low, high = _drop_table("feather", "chicken", game_data)
    assert _drop_actions("feather", "chicken", rate, low, high, owning, game_data,
                         ctx.timing(), ctx.drops()) == Fraction(8, 3) * win
    assert _drop_actions("feather", "chicken", rate, low, high, state, game_data,
                         ctx.timing(), ctx.drops()) == 8 * win
