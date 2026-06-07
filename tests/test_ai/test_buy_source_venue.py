"""choose_buy_venue / realized_cost: immediate-fill BUY source venue decision (the
DUAL of liquidation_venue).

Covers all three reachable branches (GE on a strictly-cheaper fillable order; NPC
when the order ties or is pricier; NPC when no order exists) and the realized-gold
coupling for every venue/order combination.
"""
from artifactsmmo_cli.ai.buy_source_venue import (
    BuyVenue,
    choose_buy_venue,
    realized_cost,
)


def test_ge_chosen_when_fillable_order_costs_strictly_less():
    assert choose_buy_venue(npc_price=15, ge_price=8) is BuyVenue.GE


def test_npc_chosen_when_order_ties_npc():
    # Equal cost: GE offers no strict saving, so the always-realizable NPC wins.
    assert choose_buy_venue(npc_price=10, ge_price=10) is BuyVenue.NPC


def test_npc_chosen_when_order_costs_more():
    assert choose_buy_venue(npc_price=10, ge_price=15) is BuyVenue.NPC


def test_npc_chosen_when_no_fillable_order():
    # The anti-surrogate guard: with no standing order GE is never chosen, even
    # though `None` is "absent", not "high".
    assert choose_buy_venue(npc_price=10, ge_price=None) is BuyVenue.NPC


def test_realized_cost_ge_returns_order_price():
    assert realized_cost(npc_price=15, ge_price=8, venue=BuyVenue.GE) == 8


def test_realized_cost_npc_returns_npc_price():
    assert realized_cost(npc_price=15, ge_price=8, venue=BuyVenue.NPC) == 15


def test_realized_cost_ge_without_order_falls_back_to_npc():
    # Defensive: GE venue but no order -> realize the NPC price (never a phantom).
    assert realized_cost(npc_price=10, ge_price=None, venue=BuyVenue.GE) == 10


def test_realized_cost_at_choice_is_minimal():
    # The realized gold at the chosen venue is <= NPC price and <= any standing order.
    for npc_price in range(-3, 4):
        for ge in [None, -2, 0, 3, 5]:
            venue = choose_buy_venue(npc_price, ge)
            realized = realized_cost(npc_price, ge, venue)
            assert realized <= npc_price
            if ge is not None:
                assert realized <= ge


def test_venue_enum_values():
    assert BuyVenue.NPC.value == "npc"
    assert BuyVenue.GE.value == "ge"
