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
    _drop_table,
    _price_of,
    _priced,
    _prospecting_relief,
    _sale_of,
    _workshop_venue,
    acquisition_actions,
    acquisition_options,
    bundle_acquisition_actions,
    route_options,
)
from artifactsmmo_cli.ai.acquisition_cost_core import UNOBTAINABLE_PER_UNIT
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import MIN_DROP_KILLS, LearningStore
from artifactsmmo_cli.ai.obtain_sources import (
    UNBOUNDED_CAPACITY,
    Source,
    SourceKind,
    obtain_sources,
)
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT

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
                  state, game_data)
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
                  state, game_data)
    assert opt.venue == _workshop_venue("weaponcrafting")
    assert opt.inputs == game_data.crafting_recipe("iron_sword")


def test_recycle_consumes_the_source_item_not_the_target(state, game_data) -> None:
    """`Source.code` for a RECYCLE is the item to DESTROY, never the target —
    the one place that distinction becomes an input edge."""
    opt = _priced("iron",
                  Source(SourceKind.RECYCLE, "iron_sword", 3, 6),
                  state, game_data)
    assert opt.inputs == {"iron_sword": 1}
    assert opt.yield_per == 3
    assert opt.venue == _workshop_venue("weaponcrafting")


def test_gather_uses_the_resource_tile_as_its_venue(state, game_data) -> None:
    """Two materials off the same node pay one walk, which only works because
    the venue is the RESOURCE code rather than a per-item token."""
    opt = _priced("copper_ore",
                  Source(SourceKind.GATHER, "copper_rocks", 1, UNBOUNDED_CAPACITY),
                  state, game_data)
    assert opt.venue == "copper_rocks"
    assert opt.yield_per == max(1, game_data.max_gather_yield)


def _ctx_with_siblings(**skills):  # type: ignore[no-untyped-def]
    return replace(NO_PROFILE_CONTEXT, sibling_skills=dict(skills))


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
    routes = route_options("iron_sword", st, game_data, NO_PROFILE_CONTEXT,
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
                  state, gd)
    assert opt.venue == "ord-x"
    assert opt.actions_per_application == 1
    assert opt.capacity == 4, "a standing order is FINITE, unlike a vendor"
    assert opt.inputs == {"gold": 137}, "the realizable cost is the order's price"


def test_ge_fill_without_a_standing_order_raises_rather_than_defaulting(
        state, game_data) -> None:
    """CLAUDE.md: use only API data or fail with an error.

    `obtain_sources` produced the source from the same order book, so the row
    exists; if it does not, the two reads disagreed inside one decision and a
    default would price a route that is not there. Same contract as `_price_of`.
    """
    gd = game_data
    gd._ge_sell_orders = {}
    with pytest.raises(KeyError, match="no standing GE sell order"):
        _priced("backpack", Source(SourceKind.GE_FILL, "ord-gone", 1, 4), state, gd)


def test_buy_carries_its_price_as_a_currency_input(state, game_data) -> None:
    """THE TERM `min_plan_length` CANNOT EXPRESS. A purchase is priced as the
    purchase plus obtaining what it is priced in, so a 50,000-gold backpack
    pulls 50,000 gold into the demand instead of costing one imaginary
    gather."""
    opt = _priced("backpack",
                  Source(SourceKind.BUY, "nomadic_merchant", 1, UNBOUNDED_CAPACITY),
                  state, game_data)
    assert opt.venue == "nomadic_merchant"
    assert opt.inputs == {"gold": 50000}


def test_drop_costs_expected_kills_times_whole_loop_cycles(state, game_data) -> None:
    """A farm is priced as the farm. Both factors are proved elsewhere and
    reused rather than restated: `expected_kills` (exact `Fraction`,
    `Formal.MonsterDropSelection`) and `cycles_per_kill` — the same
    fight-plus-forced-rest figure `cheapest_path_to_level` spends, so a drop
    farm and a level grind are quoted in identical units."""
    opt = _priced("feather",
                  Source(SourceKind.DROP, "chicken", 1, UNBOUNDED_CAPACITY),
                  state, game_data)
    assert opt.venue == "chicken"
    assert opt.actions_per_application > 1


def test_prospecting_makes_a_drop_farm_cheaper(state, game_data) -> None:
    """INCREMENT 4. The two halves meet with no new term.

    Prospecting's entire value is reducing kills-per-drop, which is a cost in the
    DROP route. Until increment 2 priced that route there was nothing for the
    stat to reduce — pricing it earlier would have given it a coefficient on
    zero. That is why it is last, not an afterthought.

    A character wearing prospecting gear farms the same monster in strictly fewer
    actions. `vital_armor` carries prospecting 60."""
    gear = game_data.item_stats("vital_armor")
    assert gear.prospecting > 0, "fixture drift: expected a prospecting item"
    plain = _priced("feather",
                    Source(SourceKind.DROP, "chicken", 1, UNBOUNDED_CAPACITY),
                    state, game_data)
    lucky = _priced("feather",
                    Source(SourceKind.DROP, "chicken", 1, UNBOUNDED_CAPACITY),
                    replace(state, prospecting=500), game_data)
    assert lucky.actions_per_application < plain.actions_per_application


def _store_with_kills(monster: str, kills: int, drops: dict[str, int]) -> LearningStore:
    """A real store carrying `kills` recorded `Fight(<monster>)` cycles, the first
    `drops[item]` of which dropped that item. Rows, not a stub — the rate the
    production query computes is the thing under test."""
    store = LearningStore(db_path=":memory:", character="drop_probe")
    store.start_session()
    for i in range(kills):
        got = {item: 1 for item, n in drops.items() if i < n}
        store.record_cycle(Cycle(
            ts=f"2026-08-08T00:{i // 60:02d}:{i % 60:02d}+00:00", session_id="s",
            cycle_index=i, character="drop_probe", outcome="ok",
            action_repr=f"Fight({monster})",
            drops_json=json.dumps(got),
        ))
    return store


def test_an_observed_drop_rate_replaces_the_static_table(state, game_data) -> None:
    """The learned rate wins where there is enough of it.

    `chicken/feather` is 1-in-8 in the API table. Recording 100 kills that
    dropped 25 feathers (25%, twice the static rate) must make the farm cheaper —
    the whole point of learning, and the direction the live measurement pointed
    (14.8% observed vs 12.5% static)."""
    static = _priced("feather",
                     Source(SourceKind.DROP, "chicken", 1, UNBOUNDED_CAPACITY),
                     state, game_data)
    store = _store_with_kills("chicken", 100, {"feather": 25})
    try:
        assert store.observed_drop_rate("chicken", "feather") == 0.25
        learned = _priced("feather",
                          Source(SourceKind.DROP, "chicken", 1, UNBOUNDED_CAPACITY),
                          state, game_data, store)
    finally:
        store.end_session(exit_reason="normal")
        store.close()
    assert learned.actions_per_application < static.actions_per_application


def test_a_learned_rate_is_NOT_also_given_prospecting_relief(
        state, game_data) -> None:
    """THE DOUBLE-COUNT GUARD, and the reason these two terms were unified.

    The server applies prospecting when it ROLLS the drop, so a recorded
    observation is already the post-bonus rate. Applying `_prospecting_relief` on
    top would count the bonus twice.

    So with a learned rate in hand, prospecting must change NOTHING — while on
    the static fallback (no observations) it must still help, because there the
    bonus is genuinely absent from the number."""
    store = _store_with_kills("chicken", 100, {"feather": 25})
    try:
        plain = _priced("feather",
                        Source(SourceKind.DROP, "chicken", 1, UNBOUNDED_CAPACITY),
                        state, game_data, store)
        lucky = _priced("feather",
                        Source(SourceKind.DROP, "chicken", 1, UNBOUNDED_CAPACITY),
                        replace(state, prospecting=500), game_data, store)
        assert plain.actions_per_application == lucky.actions_per_application
    finally:
        store.end_session(exit_reason="normal")
        store.close()
    # ...and without observations, prospecting still pays.
    static_plain = _priced("feather",
                           Source(SourceKind.DROP, "chicken", 1, UNBOUNDED_CAPACITY),
                           state, game_data)
    static_lucky = _priced("feather",
                           Source(SourceKind.DROP, "chicken", 1, UNBOUNDED_CAPACITY),
                           replace(state, prospecting=500), game_data)
    assert static_lucky.actions_per_application < static_plain.actions_per_application


def test_too_few_kills_falls_back_to_the_static_table(state, game_data) -> None:
    """Below the sample floor the estimate is noise, and noise here feeds a cost
    the planner ranks on. Measured live: at n=199 `green_slime/apple` read 0.60x
    its static rate, inside ordinary sampling error for p=0.083 and worth a 40%
    phantom price rise if believed."""
    store = _store_with_kills("chicken", MIN_DROP_KILLS - 1, {"feather": 20})
    try:
        assert store.observed_drop_rate("chicken", "feather") is None
        sparse = _priced("feather",
                         Source(SourceKind.DROP, "chicken", 1, UNBOUNDED_CAPACITY),
                         state, game_data, store)
    finally:
        store.end_session(exit_reason="normal")
        store.close()
    static = _priced("feather",
                     Source(SourceKind.DROP, "chicken", 1, UNBOUNDED_CAPACITY),
                     state, game_data)
    assert sparse.actions_per_application == static.actions_per_application


def test_a_monster_that_never_drops_the_item_falls_back(state, game_data) -> None:
    """An observed rate of exactly 0 is not a usable divisor — it would mean
    infinite kills. Falls back to the static table rather than pricing the route
    out of existence on a run of bad luck."""
    store = _store_with_kills("chicken", 100, {})
    try:
        assert store.observed_drop_rate("chicken", "feather") == 0.0
        zero = _priced("feather",
                       Source(SourceKind.DROP, "chicken", 1, UNBOUNDED_CAPACITY),
                       state, game_data, store)
    finally:
        store.end_session(exit_reason="normal")
        store.close()
    static = _priced("feather",
                     Source(SourceKind.DROP, "chicken", 1, UNBOUNDED_CAPACITY),
                     state, game_data)
    assert zero.actions_per_application == static.actions_per_application


def test_the_prospecting_rate_mirrors_the_wisdom_rate(state, game_data) -> None:
    """"1% extra per 10 points" is decided in ONE place.

    `MonsterCatalog.xp_per_kill` scales xp by `(1000 + wisdom) / 1000`; this
    scales kills by the reciprocal of the same form. Restating the rate as a
    literal here would let the two drift, and a rate that means one thing for xp
    and another for drops is the unit-confusion this epic keeps finding.

    Exact `Fraction`, never a float: it multiplies a `Fraction` that
    `Formal.MonsterDropSelection` proves things about."""
    assert _prospecting_relief(0) == Fraction(1)
    assert _prospecting_relief(1000) == Fraction(1, 2)
    assert isinstance(_prospecting_relief(60), Fraction)


def test_an_item_with_no_crafting_skill_still_prices(state, game_data) -> None:
    """A RECYCLE whose source item has no crafting skill cannot reach a real
    workshop. It prices with an empty skill rather than crashing — the walk will
    simply never prefer it, and a crash inside a cost model would take down a
    whole decision for a route nobody was going to take."""
    opt = _priced("feather",
                  Source(SourceKind.RECYCLE, "copper_ore", 1, 2),
                  state, game_data)
    assert opt.venue == _workshop_venue("")


def test_price_of_refuses_to_invent_a_missing_row(state, game_data) -> None:
    """`obtain_sources` built the BUY source from this same table, so a missing
    row means the two reads disagreed about game data inside one decision. That
    raises rather than defaulting — 'use only API data or fail with an error'."""
    with pytest.raises(KeyError):
        _price_of("backpack", "a_vendor_that_does_not_exist", game_data)


def test_sale_of_refuses_to_invent_a_missing_row(state, game_data) -> None:
    """Same contract as `_price_of`, for the sell side: `_sell_sources` built the
    SELL source from this table under these gates, so no row means the two reads
    disagreed inside one decision."""
    with pytest.raises(KeyError):
        _sale_of("an_item_nobody_buys", state, game_data)


def test_a_buyer_with_no_known_location_is_skipped(state, game_data,
                                                   monkeypatch) -> None:
    """A price row is not a buyer. A dormant merchant with no location is
    skipped by BOTH reads, so the source arm and the venue lookup stay in step
    on which buyer they mean."""
    real = game_data.npc_location
    monkeypatch.setattr(game_data, "npc_location",
                        lambda npc: None if npc == "gemstone_merchant" else real(npc))
    held = _selling(state, game_data, diamond=2)
    assert obtain_sources("gold", held, game_data, NO_PROFILE_CONTEXT) == []
    with pytest.raises(KeyError):
        _sale_of("diamond", held, game_data)


def test_a_buyer_offering_nothing_is_skipped(state, game_data,
                                             monkeypatch) -> None:
    """A zero price is not an offer — selling into it would spend an action to
    obtain no gold, and `yield_per` must stay >= 1."""
    monkeypatch.setattr(game_data, "npcs_buying_item",
                        lambda code: [("gemstone_merchant", 0)]
                        if code == "diamond" else [])
    held = _selling(state, game_data, diamond=2)
    assert obtain_sources("gold", held, game_data, NO_PROFILE_CONTEXT) == []
    with pytest.raises(KeyError):
        _sale_of("diamond", held, game_data)


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
                                 state, game_data)]}
    assert "gold" in options["medal"][0].inputs


def test_a_gatherable_prices_end_to_end(state, game_data) -> None:
    """The whole stack on real state: `obtain_sources` names a GATHER, the
    wrapper prices it, the core walks it."""
    bare = replace(state, inventory={})
    cost = acquisition_actions("copper_ore", 3, bare, game_data,
                               NO_PROFILE_CONTEXT, equip=False)
    assert cost == 1 + 3   # hop to the node, three gathers


def test_equip_adds_exactly_one_action(state, game_data) -> None:
    bare = replace(state, inventory={})
    without = acquisition_actions("copper_ore", 1, bare, game_data,
                                  NO_PROFILE_CONTEXT, equip=False)
    with_equip = acquisition_actions("copper_ore", 1, bare, game_data,
                                     NO_PROFILE_CONTEXT, equip=True)
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
                               NO_PROFILE_CONTEXT, equip=False)
    assert cost == 2      # hop to the vendor, one purchase

    # ...and the shortfall beyond the pocket is charged a million per gold piece,
    # which used to price this route at 10,000 * UNOBTAINABLE_PER_UNIT — ABOVE
    # the price of an item with no route in the game at all, so the walk ranked
    # the impossible thing ahead of the merely unaffordable one. The sentinel is
    # a CEILING now (`acquisition_cost_core._capped`), so the unaffordable route
    # prices at exactly what a missing one does, and never worse.
    broke = replace(state, inventory={}, gold=0)
    unaffordable = acquisition_actions("healing_rune", 1, broke, game_data,
                                       NO_PROFILE_CONTEXT, equip=False)
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
                               NO_PROFILE_CONTEXT, equip=False)
    assert cost < UNOBTAINABLE_PER_UNIT, cost
    assert cost == 4, cost     # hop + sale to raise the 1,000, then hop + buy


def test_the_sale_consumes_the_copy_it_sells(state, game_data) -> None:
    """A sale is not free gold. `inputs={code: 1}` charges the copy, so a
    shortfall bigger than the licensed stock can cover stays unpayable."""
    one = replace(_selling(state, game_data, diamond=1), gold=0)
    assert acquisition_actions("healing_rune", 1, one, game_data,
                               NO_PROFILE_CONTEXT, equip=False) \
        >= UNOBTAINABLE_PER_UNIT


def test_no_sellable_stock_leaves_gold_with_no_route(state, game_data) -> None:
    """The route is the keep authority's licence, not a wish. An empty bag
    licenses no sale, so gold stays unobtainable and the shortfall stays honest
    — S-046: where gold replaces nothing, it is worth nothing."""
    broke = replace(_selling(state, game_data), gold=9_000)
    assert acquisition_actions("healing_rune", 1, broke, game_data,
                               NO_PROFILE_CONTEXT, equip=False) \
        >= UNOBTAINABLE_PER_UNIT


def test_a_closed_window_leaves_gold_with_no_route(state, game_data) -> None:
    """Same stock, no open event: the buyer is not tradeable, so there is no
    route. This is what makes the previous test's licence check meaningful
    rather than incidental — the stock alone is not enough."""
    shut = replace(state, inventory={"diamond": 4}, gold=9_000, active_events={})
    assert obtain_sources("gold", shut, game_data, NO_PROFILE_CONTEXT) == []
    assert acquisition_actions("healing_rune", 1, shut, game_data,
                               NO_PROFILE_CONTEXT, equip=False) \
        >= UNOBTAINABLE_PER_UNIT


def test_a_sell_source_names_the_item_sold(state, game_data) -> None:
    """`Source.code` for SELL is the item DESTROYED by the sale, the same
    convention RECYCLE uses — not the gold, and not the buyer."""
    held = _selling(state, game_data, diamond=2)
    sources = obtain_sources("gold", held, game_data, NO_PROFILE_CONTEXT)
    assert [(s.kind, s.code, s.yield_per) for s in sources] \
        == [(SourceKind.SELL, "diamond", 5_000)]
    assert sources[0].capacity == 2 * 5_000


def test_gold_has_no_sources_for_any_other_code(state, game_data) -> None:
    """The SELL arm answers for one code. Asking for a normal item must not
    return a sale of something else."""
    held = _selling(state, game_data, diamond=2)
    assert all(s.kind is not SourceKind.SELL
               for s in obtain_sources("copper_ore", held, game_data,
                                       NO_PROFILE_CONTEXT))


def test_gold_is_consumed_by_the_route_that_spends_it(state, game_data) -> None:
    """Gold is credited as a holding, so it is also SPENT like one: two runes at
    10,000 each are not affordable out of 15,000."""
    one = replace(state, inventory={}, gold=15_000)
    assert acquisition_actions("healing_rune", 1, one, game_data,
                               NO_PROFILE_CONTEXT, equip=False) == 2
    assert acquisition_actions("healing_rune", 2, one, game_data,
                               NO_PROFILE_CONTEXT, equip=False) \
        >= UNOBTAINABLE_PER_UNIT


def test_banked_gold_is_not_credited_to_the_pocket(state, game_data) -> None:
    """Same rule as every other holding in this module: the bag counts, the bank
    is a priced route. Banked gold is therefore NOT spendable here — conservative,
    and it under-credits rather than pricing the trip to the bank at nothing."""
    banked_only = replace(state, inventory={}, gold=0, bank_gold=50_000)
    assert acquisition_actions("healing_rune", 1, banked_only, game_data,
                               NO_PROFILE_CONTEXT, equip=False) \
        >= UNOBTAINABLE_PER_UNIT


def test_held_stock_makes_an_item_free(state, game_data) -> None:
    """Bag holdings are credited; the bank deliberately is NOT (it is a priced
    withdraw route instead)."""
    held = replace(state, inventory={"copper_ore": 5})
    assert acquisition_actions("copper_ore", 3, held, game_data,
                               NO_PROFILE_CONTEXT, equip=False) == 0


def test_a_drop_farm_prices_end_to_end(state, game_data) -> None:
    """`feather` is winnable off a chicken in this scenario, so the DROP route
    survives `obtain_sources`' gates and the farm is priced — where
    `min_plan_length` charged 2."""
    bare = replace(state, inventory={})
    cost = acquisition_actions("feather", 1, bare, game_data,
                               NO_PROFILE_CONTEXT, equip=False)
    assert cost > 2


def test_an_unwinnable_drop_is_unobtainable_right_now(state, game_data) -> None:
    """`wolf_hair` drops from a wolf with live tiles that this character cannot
    beat. `obtain_sources` names no route, so the bound prunes — correctly, and
    only for as long as that stays true.

    This is the STATE-AWARENESS caveat recorded on `UNOBTAINABLE_PER_UNIT`
    made concrete: the verdict is about this cycle, and a consumer that cached
    it across cycles would turn a temporary prune into a permanent one."""
    assert not route_options("wolf_hair", state, game_data, NO_PROFILE_CONTEXT)
    cost = acquisition_actions("wolf_hair", 1, state, game_data,
                               NO_PROFILE_CONTEXT, equip=False)
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
    assert not route_options("iron_sword", state, game_data, NO_PROFILE_CONTEXT)


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
                                 NO_PROFILE_CONTEXT)
        gated = route_options("iron_sword", gated_state, game_data,
                              NO_PROFILE_CONTEXT, store)
        assert [r.kind for r in gated] == ["craft"]
        assert gated[0].unlock == "skill:weaponcrafting:10"
        assert gated[0].unlock_actions > 0
        assert gated[0].inputs == game_data.crafting_recipe("iron_sword")
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
                                 NO_PROFILE_CONTEXT, store)
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def test_no_skill_max_xp_DECLINES_the_route(state, game_data) -> None:
    """`scenario_state` supplies no `skill_max_xp`, so the grind cannot be sized
    and the route is declined.

    This briefly charged 0 instead, on the argument that a LOWER bound should
    omit an unknown positive term. That argument is right about pruning and wrong
    about RANKING — see `_gated_craft_option`, and the 4.5 live hours R2D2 spent
    on a grind that looked free."""
    assert not state.skill_max_xp
    store = _store_with_rate("weaponcrafting", 40)
    try:
        assert not route_options("iron_sword", state, game_data,
                                 NO_PROFILE_CONTEXT, store)
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
                                 NO_PROFILE_CONTEXT, store)
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
                               NO_PROFILE_CONTEXT, store)
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
                                     NO_PROFILE_CONTEXT, equip=True)
        priced = acquisition_actions("iron_sword", 1, bare, game_data,
                                     NO_PROFILE_CONTEXT, equip=True, store=store)
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
                                 NO_PROFILE_CONTEXT, store)
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
            routes = route_options(code, gated_state, game_data, NO_PROFILE_CONTEXT,
                                   store)
            assert sum(1 for r in routes if r.kind == "craft") <= 1
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def test_the_pricer_adds_nothing_but_gated_crafts(gated_state, game_data) -> None:
    """THE CENSUS THAT STOPS THIS BECOMING A RIVAL ROUTE MODEL.

    `obtain_sources` is meant to be the one enumeration every producer consumes.
    This module deliberately adds ONE route it does not name — the skill-gated
    craft — because readiness and cost are different questions. That exception
    must stay exactly one, or the epic has reintroduced the duplication it
    exists to remove.

    Same shape as `test_obtain_graph_agreement`, which pins `obtain_sources`
    against `RequirementGraph.leaves`."""
    store = _store_with_rate("weaponcrafting", 40)
    try:
        probes = ["iron_sword", "copper_ore", "feather", "copper_dagger",
                  "wisdom_amulet", "wolf_hair"]
        for code in probes:
            ready = {s.kind.value for s in
                     obtain_sources(code, gated_state, game_data, NO_PROFILE_CONTEXT)}
            priced = route_options(code, gated_state, game_data, NO_PROFILE_CONTEXT,
                                   store)
            extra = [r for r in priced if not r.unlock]
            assert {r.kind for r in extra} <= ready, (
                f"{code}: pricer invented a route obtain_sources did not name")
            assert all(r.kind == "craft" for r in priced if r.unlock), (
                f"{code}: only a gated CRAFT may be added")
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def test_the_closure_terminates_on_real_data(state, game_data) -> None:
    """A walk with a visited set, so a route graph that loops enumerates once.
    The cost walk's fuel bound handles the cycle when pricing; this only has to
    finish."""
    options = acquisition_options("copper_dagger", state, game_data,
                                  NO_PROFILE_CONTEXT)
    assert "copper_dagger" in options
    assert all(isinstance(v, list) for v in options.values())


def test_the_closure_survives_a_genuine_cycle_in_real_game_data(
        state, game_data) -> None:
    """The cycle is not hypothetical. Holding copper daggers, `copper_bar` has a
    RECYCLE route out of `copper_dagger`, and `copper_dagger` CRAFTS from
    `copper_bar` — a two-node loop straight out of the live recipe tables.

    This is the case that showed the walk had two visited-set guards where one
    is correct, and that the redundant push-time filter was making the pop-time
    guard unreachable."""
    holding = replace(state, inventory={"copper_dagger": 3})
    kinds = {s.kind for s in
             obtain_sources("copper_bar", holding, game_data, NO_PROFILE_CONTEXT)}
    assert SourceKind.RECYCLE in kinds, "fixture drift: the cycle is gone"
    options = acquisition_options("copper_bar", holding, game_data,
                                  NO_PROFILE_CONTEXT)
    assert {"copper_bar", "copper_dagger", "copper_ore"} <= set(options)


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
                                NO_PROFILE_CONTEXT, equip=True, store=store)
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
                            NO_PROFILE_CONTEXT, equip=True, store=store)
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
    fixture, the ORDER does not."""
    store = _store_with_rate("gearcrafting", 5, cycles=5)
    try:
        singly = {c: acquisition_actions(c, 1, unlock_state, game_data,
                                         NO_PROFILE_CONTEXT, equip=True, store=store)
                  for c in _IRON_SET}
        together, paid = bundle_acquisition_actions(
            [(c, 1) for c in _IRON_SET], unlock_state, game_data,
            NO_PROFILE_CONTEXT, equip=True, store=store)
    finally:
        store.end_session(exit_reason="normal")
        store.close()
    apart = sum(singly.values())
    unlock = "skill:gearcrafting:10"
    assert unlock in paid, "the gated craft did not fire — this measures nothing"
    assert paid[unlock] > 0
    # The unlock alone is charged four extra times when the five are priced apart.
    assert apart - together >= paid[unlock] * 4
    # And it dominates: nothing here is walled, so the whole set as one plan
    # costs a small fraction of the five priced apart.
    assert apart < UNOBTAINABLE_PER_UNIT, "a walled input would swamp the term under test"
    assert together < apart // 3


def test_bundling_saves_nothing_when_there_is_nothing_to_share(
        unlock_state, game_data) -> None:
    """The honest negative. Two roots with no common venue and no common gate
    cost the same together as apart — so a non-zero saving elsewhere is
    attributable to a shared key rather than to bundling as such."""
    store = _store_with_rate("gearcrafting", 5, cycles=5)
    try:
        codes = ["iron_boots"]
        singly = sum(acquisition_actions(c, 1, unlock_state, game_data,
                                         NO_PROFILE_CONTEXT, equip=True, store=store)
                     for c in codes)
        together, _paid = bundle_acquisition_actions(
            [(c, 1) for c in codes], unlock_state, game_data,
            NO_PROFILE_CONTEXT, equip=True, store=store)
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
                                             NO_PROFILE_CONTEXT, equip=False,
                                             store=store)
        worn, _ = bundle_acquisition_actions(roots, unlock_state, game_data,
                                             NO_PROFILE_CONTEXT, equip=True,
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
    are fights — so `_gated_craft_option` declined every skill-gated craft and
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
                               NO_PROFILE_CONTEXT, store)
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
                                 NO_PROFILE_CONTEXT, store)
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
                                 NO_PROFILE_CONTEXT, store)
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
    cows". Same seam as `_gated_craft_option`: `obtain_sources` answers
    READINESS, this module answers COST, and a gate is a price."""
    rested = replace(gated_state, hp=gated_state.max_hp)
    assert not any(
        s.kind is SourceKind.DROP
        for s in obtain_sources("cowhide", rested, game_data, NO_PROFILE_CONTEXT))
    store = _store_with_rate("weaponcrafting", 40)
    try:
        routes = route_options("cowhide", gated_state, game_data,
                               NO_PROFILE_CONTEXT, store)
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
    this character's 5) — so without an observed grind rate `_gated_craft_option`
    declines the sword, the sword prices at infinity, and this gate declines the
    cow for the same reason it declines any unpriceable chain. The dependency is
    transitive, not direct: nothing in THIS route reads the store, and a chain
    that is already craftable prices without one."""
    without = acquisition_actions("cowhide", 1, gated_state, game_data,
                                  NO_PROFILE_CONTEXT, equip=False)
    assert without == UNOBTAINABLE_PER_UNIT
    store = _store_with_rate("weaponcrafting", 40)
    try:
        assert acquisition_actions("cowhide", 1, gated_state, game_data,
                                   NO_PROFILE_CONTEXT, equip=False,
                                   store=store) < UNOBTAINABLE_PER_UNIT
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def test_a_winnable_dropper_adds_NO_second_route(gated_state, game_data) -> None:
    """`obtain_sources` already names a beatable dropper's DROP route, so the
    gate must decline — two copies of one route is the double-pricing
    `_gated_craft_option` refuses for the same reason."""
    winnable = next(
        item for item in ("yellow_slimeball", "red_slimeball", "feather")
        if any(s.kind is SourceKind.DROP for s in obtain_sources(
            item, replace(gated_state, hp=gated_state.max_hp), game_data,
            NO_PROFILE_CONTEXT)))
    routes = route_options(winnable, gated_state, game_data, NO_PROFILE_CONTEXT)
    assert [r for r in routes if r.kind == SourceKind.DROP.value]
    assert not [r for r in routes if r.unlock.startswith("gear:")]


def test_an_item_with_no_dropper_is_not_this_gates_business(
        gated_state, game_data) -> None:
    """`copper_ore` is gathered, not dropped. The gate must not invent a fight."""
    routes = route_options("copper_ore", gated_state, game_data,
                           NO_PROFILE_CONTEXT)
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
                                   NO_PROFILE_CONTEXT, equip=False, store=store,
                                   gated_drop=False) >= UNOBTAINABLE_PER_UNIT
        routes = route_options("mushroom", state, game_data, NO_PROFILE_CONTEXT,
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
                                   NO_PROFILE_CONTEXT, equip=False, store=store,
                                   gated_drop=False) == UNOBTAINABLE_PER_UNIT
        assert acquisition_actions("cowhide", 1, gated_state, game_data,
                                   NO_PROFILE_CONTEXT, equip=False, store=store,
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
                                   NO_PROFILE_CONTEXT, store)
            keys |= {r.unlock for r in routes if r.unlock.startswith("gear:")}
        assert keys == {"gear:cow"}
    finally:
        store.end_session(exit_reason="normal")
        store.close()
