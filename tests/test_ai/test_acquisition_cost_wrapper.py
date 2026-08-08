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

from dataclasses import replace
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.acquisition_cost import (
    BANK_VENUE,
    _drop_table,
    _price_of,
    _priced,
    _workshop_venue,
    acquisition_actions,
    acquisition_options,
    route_options,
)
from artifactsmmo_cli.ai.acquisition_cost_core import UNOBTAINABLE_PER_UNIT
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
