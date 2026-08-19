from artifactsmmo_cli.ai.accumulation_sell import (
    ACCUM_MULT,
    SEVERE_STEPS,
    _is_sellable,
    accumulation_excess,
    accumulation_steps,
    sell_targets,
    sellable_accumulation,
    sellable_surplus,
    sellable_tradeable_now,
    worst_accumulation_steps,
)
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from tests.test_ai.fixtures import make_state

CTX = NO_PROFILE_CONTEXT


def test_is_sellable_requires_a_reachable_buyer():
    """A buyer in the price table whose npc_location is None (dormant event
    merchant) does NOT make the item sellable; a reachable buyer does."""
    gd = GameData()
    gd._item_stats = {"x": ItemStats(code="x", level=1, type_="resource", tradeable=True)}
    gd._npc_sell_prices = {"dormant": {"x": 5}}
    gd._crafting_recipes = {}
    gd._npc_locations = {}                       # buyer exists but unreachable
    assert _is_sellable("x", gd) is False
    gd._npc_locations = {"dormant": (1, 1)}      # now reachable
    assert _is_sellable("x", gd) is True
    # also excluded from the accumulation set when unreachable
    gd._npc_locations = {}
    state = make_state(level=1, inventory={"x": 40})
    assert sellable_accumulation(state, gd, CTX) == {}


def _gd_with_buyer() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "wooden_shield": ItemStats(code="wooden_shield", level=1, type_="shield",
                                   crafting_skill="gearcrafting", crafting_level=1,
                                   tradeable=True),
        "gold_coin": ItemStats(code="gold_coin", level=1, type_="currency"),
    }
    gd._crafting_recipes = {}
    gd._npc_sell_prices = {"vendor": {"wooden_shield": 2}}
    gd._npc_locations = {"vendor": (1, 1)}
    return gd


def test_sellable_accumulation_targets_over_ratio_sellable_gear():
    gd = _gd_with_buyer()
    # 14 shields, keep 1 (the authority's EQUIPPED/RECIPE_DEMAND arm) -> 13 licensed,
    # and 14 >= ACCUM_MULT * 1 clears the ratio gate.
    state = make_state(level=1, inventory={"wooden_shield": 14})
    assert sellable_accumulation(state, gd, CTX) == {"wooden_shield": 13}


def test_sellable_accumulation_skips_unsellable_and_below_gate():
    gd = _gd_with_buyer()
    # gold_coin has no buyer -> skipped even if accumulated.
    state = make_state(level=1, inventory={"wooden_shield": 4, "gold_coin": 999})
    assert sellable_accumulation(state, gd, CTX) == {}  # 4 < 5*1; coin not sellable


def test_sellable_surplus_is_the_licence_the_ratio_gate_holds_back():
    """The AUTHORITY licenses the 3 spare shields; the ratio gate (4 < 5*1) is
    what declines to sell them while the bank can still take them. The two
    functions differ exactly there, and `sell_targets(relief=True)` — the
    bank-full cascade's SELL rung — takes the licence."""
    gd = _gd_with_buyer()
    state = make_state(level=1, inventory={"wooden_shield": 4})
    assert sellable_surplus(state, gd, CTX) == {"wooden_shield": 3}
    assert sellable_accumulation(state, gd, CTX) == {}
    assert sell_targets(state, gd, CTX) == {}
    assert sell_targets(state, gd, CTX, relief=True) == {"wooden_shield": 3}


def test_worst_accumulation_steps_is_max_over_items():
    gd = _gd_with_buyer()
    state = make_state(level=1, inventory={"wooden_shield": 40})  # steps 5
    assert worst_accumulation_steps(state, gd, CTX) == 5
    assert worst_accumulation_steps(make_state(level=1), gd, CTX) == 0


def test_steps_is_floor_log2_ratio():
    assert accumulation_steps(14, 1) == 3   # 2^3=8<=14<16
    assert accumulation_steps(11, 2) == 2   # 11/2=5.5 -> 2^2=4*2=8<=11<16
    assert accumulation_steps(32, 1) == 5   # exactly SEVERE
    assert accumulation_steps(1000, 1) == 9


def test_steps_zero_below_eff_cap_and_cap_zero_uses_one():
    assert accumulation_steps(0, 5) == 0
    assert accumulation_steps(3, 0) == 1    # eff_cap 1: 2^1=2<=3<4


def test_excess_sells_down_to_true_cap_past_gate():
    assert accumulation_excess(14, 1) == 13   # keep 1
    assert accumulation_excess(14, 0) == 14   # dominated -> sell all
    assert accumulation_excess(11, 2) == 9    # keep 2


def test_excess_zero_below_ratio_gate():
    assert accumulation_excess(4, 1) == 0     # 4 < 5*1
    assert accumulation_excess(9, 2) == 0     # 9 < 5*2=10
    assert accumulation_excess(10, 2) == 8    # 10 >= 10 -> keep 2


def test_constants():
    assert ACCUM_MULT == 5
    assert SEVERE_STEPS == 5


def test_sellable_accumulation_excludes_non_tradeable_even_with_buyer():
    """A non-tradeable item with a buyer is excluded by sellable_accumulation."""
    gd = GameData()
    gd._item_stats = {
        "bound_blade": ItemStats(code="bound_blade", level=1, type_="weapon",
                                 crafting_skill="weaponcrafting", crafting_level=1,
                                 tradeable=False),
    }
    gd._crafting_recipes = {}
    gd._npc_sell_prices = {"vendor": {"bound_blade": 3}}
    gd._npc_locations = {"vendor": (1, 1)}

    # Verify the item is NOT sellable because not tradeable.
    assert _is_sellable("bound_blade", gd) is False

    # Even with held=20 (well above gate 5*1), it should be excluded.
    state = make_state(level=1, inventory={"bound_blade": 20})
    assert sellable_accumulation(state, gd, CTX) == {}
    assert sellable_surplus(state, gd, CTX) == {}


def test_worst_accumulation_steps_skips_unsellable_and_zero_qty():
    """worst_accumulation_steps skips items with held <= 0 or not sellable."""
    gd = GameData()
    gd._item_stats = {
        "unsellable_item": ItemStats(code="unsellable_item", level=1, type_="misc"),
    }
    gd._crafting_recipes = {}
    # unsellable_item has no buyer, so it's not sellable
    gd._npc_sell_prices = {}
    gd._npc_locations = {}

    # State with zero qty and one unsellable item -> worst_accumulation_steps returns 0
    state = make_state(level=1, inventory={"unsellable_item": 0})
    assert worst_accumulation_steps(state, gd, CTX) == 0

    # Also test with negative qty (edge case, but ensures continue is exercised)
    state = make_state(level=1, inventory={"unsellable_item": -5})
    assert worst_accumulation_steps(state, gd, CTX) == 0


def _buys_ore(location, *, event=None) -> GameData:
    gd = GameData()
    gd._npc_sell_prices = {"merchant": {"copper_ore": 5}}
    if location is not None:
        gd._npc_locations = {"merchant": location}
    if event is not None:
        gd.world.npc_event_codes["merchant"] = event
    return gd


def test_sellable_tradeable_now_true_for_a_located_permanent_buyer():
    state = make_state(inventory={"copper_ore": 3})
    assert sellable_tradeable_now(state, _buys_ore((1, 2))) is True


def test_sellable_tradeable_now_skips_a_buyer_with_no_known_location():
    """A price row is not a buyer. A dormant merchant with no tile cannot take
    the sale, and NpcSellAction.is_applicable refuses on the same check."""
    state = make_state(inventory={"copper_ore": 3})
    assert sellable_tradeable_now(state, _buys_ore(None)) is False


def test_sellable_tradeable_now_passes_over_an_unlocated_buyer_to_a_located_one():
    """Buyers come back highest price first, so the best one may be the dormant
    one. The walk must keep going rather than answer on the first row — with only
    ONE unlocated buyer `_is_sellable` already refuses, so it takes a second,
    cheaper, located buyer to reach that decision at all."""
    gd = GameData()
    gd._npc_sell_prices = {"rich_but_absent": {"copper_ore": 500},
                           "merchant": {"copper_ore": 5}}
    gd._npc_locations = {"merchant": (1, 2)}
    state = make_state(inventory={"copper_ore": 3})
    assert next(n for n, _p in gd.npcs_buying_item("copper_ore")) == "rich_but_absent"
    assert sellable_tradeable_now(state, gd) is True


def test_sellable_tradeable_now_skips_a_shut_event_window():
    """The half `_has_sellable` was blind to, and the usual case rather than an
    edge one: EVERY NPC in the game that buys items is an event NPC."""
    state = make_state(inventory={"copper_ore": 3}, active_events={})
    gd = _buys_ore((1, 2), event="merchant_visit")
    assert sellable_tradeable_now(state, gd) is False


def test_sellable_tradeable_now_skips_zero_quantity_and_unsellable_codes():
    gd = _buys_ore((1, 2))
    assert sellable_tradeable_now(make_state(inventory={"copper_ore": 0}), gd) is False
    assert sellable_tradeable_now(make_state(inventory={"obscure": 4}), gd) is False
