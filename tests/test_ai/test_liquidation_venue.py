"""choose_venue / realized_proceeds: immediate-fill liquidation venue decision.

Covers all three reachable branches (GE on a strictly-higher fillable order; NPC
when the order ties or is lower; NPC when no order exists) and the realized-gold
coupling for every venue/order combination.
"""
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.liquidation_venue import (
    Venue,
    choose_venue,
    liquidation_venue,
    realized_proceeds,
)
from tests.test_ai.fixtures import make_state


def test_ge_chosen_when_fillable_order_pays_strictly_more():
    assert choose_venue(npc_pay=10, ge_proceeds=15) is Venue.GE


def test_npc_chosen_when_order_ties_npc():
    # Equal proceeds: GE offers no strict gain, so the always-realizable NPC wins.
    assert choose_venue(npc_pay=10, ge_proceeds=10) is Venue.NPC


def test_npc_chosen_when_order_pays_less():
    assert choose_venue(npc_pay=10, ge_proceeds=5) is Venue.NPC


def test_npc_chosen_when_no_fillable_order():
    # The anti-surrogate guard: with no standing order GE is never chosen, even
    # though `None` is "absent", not "low".
    assert choose_venue(npc_pay=10, ge_proceeds=None) is Venue.NPC


def test_realized_proceeds_ge_returns_order_price():
    assert realized_proceeds(npc_pay=10, ge_proceeds=15, venue=Venue.GE) == 15


def test_realized_proceeds_npc_returns_npc_pay():
    assert realized_proceeds(npc_pay=10, ge_proceeds=15, venue=Venue.NPC) == 10


def test_realized_proceeds_ge_without_order_falls_back_to_npc():
    # Defensive: GE venue but no order -> realize the NPC price (never a phantom).
    assert realized_proceeds(npc_pay=10, ge_proceeds=None, venue=Venue.GE) == 10


def test_realized_proceeds_at_choice_is_maximal():
    # The realized gold at the chosen venue is >= NPC pay and >= any standing order.
    for npc_pay in range(-3, 4):
        for ge in [None, -2, 0, 3, 5]:
            venue = choose_venue(npc_pay, ge)
            realized = realized_proceeds(npc_pay, ge, venue)
            assert realized >= npc_pay
            if ge is not None:
                assert realized >= ge


def test_venue_enum_values():
    assert Venue.NPC.value == "npc"
    assert Venue.GE.value == "ge"


# ---- liquidation_venue adapter (impure glue over GameData) ----


def _gd(*, sell_prices=None, ge_orders=None) -> GameData:
    gd = GameData()
    if sell_prices:
        gd._npc_sell_prices = sell_prices
    if ge_orders:
        gd._ge_buy_orders = ge_orders
    return gd


def test_adapter_chooses_ge_when_fillable_order_pays_above_npc():
    # NPC buys at 5; a standing GE buy order (qty 10 >= 3 needed) pays 9 → GE.
    gd = _gd(
        sell_prices={"merchant": {"iron_ore": 5}},
        ge_orders={"iron_ore": ("ord-1", 9, 10)},
    )
    state = make_state(inventory={"iron_ore": 3})
    assert liquidation_venue("iron_ore", 3, state, gd) is Venue.GE


def test_adapter_chooses_npc_when_no_fillable_order():
    gd = _gd(sell_prices={"merchant": {"iron_ore": 5}})
    state = make_state(inventory={"iron_ore": 3})
    assert liquidation_venue("iron_ore", 3, state, gd) is Venue.NPC


def test_adapter_chooses_npc_when_ge_order_quantity_too_small():
    # The GE order pays more per unit, but can only absorb 2 of the 3 units, so it
    # is NOT a single-fill realizable venue for the requested qty → None → NPC.
    gd = _gd(
        sell_prices={"merchant": {"iron_ore": 5}},
        ge_orders={"iron_ore": ("ord-1", 9, 2)},
    )
    state = make_state(inventory={"iron_ore": 3})
    assert liquidation_venue("iron_ore", 3, state, gd) is Venue.NPC


def test_adapter_chooses_npc_when_ge_order_pays_less():
    gd = _gd(
        sell_prices={"merchant": {"iron_ore": 8}},
        ge_orders={"iron_ore": ("ord-1", 5, 10)},
    )
    state = make_state(inventory={"iron_ore": 3})
    assert liquidation_venue("iron_ore", 3, state, gd) is Venue.NPC


def test_adapter_uses_max_npc_buyer_price():
    # Two NPC buyers: the higher (12) must beat the GE order (10) → NPC.
    gd = _gd(
        sell_prices={"a": {"iron_ore": 7}, "b": {"iron_ore": 12}},
        ge_orders={"iron_ore": ("ord-1", 10, 10)},
    )
    state = make_state(inventory={"iron_ore": 1})
    assert liquidation_venue("iron_ore", 1, state, gd) is Venue.NPC


def test_adapter_chooses_ge_when_no_npc_buyer_but_order_exists():
    # No NPC buys → npc_pay 0; a positive standing order wins.
    gd = _gd(ge_orders={"junk": ("ord-9", 3, 5)})
    state = make_state(inventory={"junk": 2})
    assert liquidation_venue("junk", 2, state, gd) is Venue.GE


def test_adapter_chooses_npc_when_neither_buyer_nor_order():
    gd = _gd()
    state = make_state(inventory={"junk": 2})
    # npc_pay 0, ge None → choose_venue returns NPC (the safe default).
    assert liquidation_venue("junk", 2, state, gd) is Venue.NPC
