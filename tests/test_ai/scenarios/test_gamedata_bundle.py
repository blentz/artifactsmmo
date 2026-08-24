"""GameData.from_cache_bundle: the offline real-catalog loader scenarios use.

The committed bundle is a copy of the live disk cache (regen: run any CLI
command to refresh ~/.cache/artifactsmmo/gamedata-*.json, then re-copy —
same drill as formal/sim snapshot regen). The Grand-Exchange order book is NOT
part of that copy — the cache writer excludes it by design — so it is captured
separately by `scripts/snapshot_ge_orders.py` into the bundle's `ge_orders` key.

Every GE assertion below derives the item codes it asserts on FROM that key
rather than hard-coding them. That is deliberate: this file used to hold
`test_bundle_ge_orders_empty`, an assertion over a collection that was empty
because no key could fill it, and it passed for weeks while twelve production
call sites across ten modules went unexercised. An assertion that reads the book
first cannot pass by the book being empty — it fails at the `assert ... is not
None` that picks its subject.
"""

import json
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.obtain_sources import obtain_sources
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.source_kind import SourceKind

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"


def _raw() -> dict:
    return json.loads(BUNDLE.read_text())


def _load(*, with_ge_orders: bool = False) -> GameData:
    return GameData.from_cache_bundle(_raw(), with_ge_orders=with_ge_orders)


def _orders(side: str) -> list[dict]:
    return [o for o in _raw()["ge_orders"]["orders"] if o["type"] == side]


def test_bundle_builds_real_catalog() -> None:
    gd = _load()
    # Spot-checks against known live facts (stable game data):
    assert gd.crafting_recipe("satchel") == {
        "cowhide": 5, "feather": 2, "jasper_crystal": 1}
    assert gd.monster_level("chicken") == 1
    assert gd.npc_purchases("jasper_crystal") == [("tasks_trader", 8, "tasks_coin")]
    assert gd.bank_location() is not None
    assert gd.taskmaster_location() is not None


def test_bundle_carries_a_captured_order_book_on_both_sides() -> None:
    """The fixture holds a real market — both halves of it, verbatim.

    The floors are floors, not pins: a re-capture moves the exact counts, but a
    book that went back to empty (or lost one side, which is how the old pin
    hid `ge_best_sell_order`) fails here first."""
    book = _raw()["ge_orders"]
    assert book["fetched_at"]
    assert len(_orders("sell")) >= 100
    assert len(_orders("buy")) >= 5
    assert len({o["code"] for o in _orders("sell")}) >= 50


def test_default_load_models_a_quiet_market() -> None:
    """The DEFAULT world has no standing order — on codes that provably have one.

    This is the control side of the GE dimension (a populated-book scenario
    proves nothing without it). It is non-vacuous by construction: both codes
    are read out of the bundle's own order book, so `None` here means the
    default declined to hydrate a book it was holding, not that there was
    nothing to hydrate."""
    sold = _orders("sell")[0]["code"]
    bought = _orders("buy")[0]["code"]
    gd = _load()
    assert gd.ge_best_sell_order(sold) is None
    assert gd.ge_best_buy_order(bought) is None


def test_hydrated_load_serves_both_accessors() -> None:
    """BOTH directions, because only one of them was ever pinned.

    `ge_best_buy_order` was the accessor the deleted emptiness test named;
    `ge_best_sell_order` is the one the live stall (fixed at dd946539) went
    through. A fixture that could only express one side would have left that
    bug just as invisible."""
    sold = _orders("sell")[0]["code"]
    bought = _orders("buy")[0]["code"]
    gd = _load(with_ge_orders=True)
    assert gd.ge_best_sell_order(sold) is not None
    assert gd.ge_best_buy_order(bought) is not None


def test_hydration_keeps_the_cheapest_sell_and_the_dearest_buy() -> None:
    """The bundle holds orders VERBATIM, so the reduction is exercised, not baked.

    Picks a code the captured book quotes at more than one price — if the
    fixture ever degraded to a pre-reduced one-order-per-item index there would
    be no such code and this fails at the subject-selection assert."""
    gd = _load(with_ge_orders=True)
    for side, pick in (("sell", min), ("buy", max)):
        prices: dict[str, list[int]] = {}
        for order in _orders(side):
            prices.setdefault(order["code"], []).append(order["price"])
        contested = sorted(c for c, p in prices.items() if len(set(p)) > 1)
        assert contested, f"no {side} code is quoted at two prices in the capture"
        code = contested[0]
        accessor = (gd.ge_best_sell_order if side == "sell"
                    else gd.ge_best_buy_order)
        order = accessor(code)
        assert order is not None
        assert order[1] == pick(prices[code])


def test_a_craftable_rung_carries_a_standing_sell_order() -> None:
    """The fixture can still express the shape that stalled a character.

    Robby's stall was a craft rung with a standing sell order on it. If a
    re-capture ever lands a book with orders on nothing but raw materials, the
    scenario set silently loses the ability to reproduce that class of bug —
    this says so instead."""
    gd = _load(with_ge_orders=True)
    rungs = [code for code in sorted({o["code"] for o in _orders("sell")})
             if gd.crafting_recipe(code)]
    assert len(rungs) >= 10
    assert all(gd.ge_best_sell_order(code) is not None for code in rungs)


def test_hydrated_book_puts_a_ge_fill_route_on_the_rung() -> None:
    """The route, not just the accessor: `obtain_sources` emits GE_FILL.

    This is the production consumer that made the empty book expensive —
    `GE_FILL` is in `_source_leafs`' CRAFT_SUBSTITUTE_KINDS, so a standing order
    changes where a prerequisite descent stops. Asserted against the quiet
    market as its own control, so it cannot pass by the kind never being
    emitted."""
    state = scenario_state(SCENARIOS["l13_drop_recipe_grind"], _load())
    quiet = _load()
    busy = _load(with_ge_orders=True)
    rung = next(code for code in sorted({o["code"] for o in _orders("sell")})
                if busy.crafting_recipe(code))

    def kinds(gd: GameData) -> set[SourceKind]:
        return {s.kind for s in obtain_sources(rung, state, gd, NO_PROFILE_CONTEXT)}

    assert SourceKind.GE_FILL not in kinds(quiet)
    assert SourceKind.GE_FILL in kinds(busy)


def test_hydration_of_a_bookless_bundle_raises_rather_than_defaulting() -> None:
    """An absent key must NOT read as an empty book.

    A silent empty is precisely the failure this work exists to undo: the
    harness would go on modelling a quiet market while believing it had asked
    for the captured one."""
    raw = _raw()
    del raw["ge_orders"]
    with pytest.raises(KeyError):
        GameData.from_cache_bundle(raw, with_ge_orders=True)
