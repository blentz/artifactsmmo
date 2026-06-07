"""choose_venue / realized_proceeds: immediate-fill liquidation venue decision.

Covers all three reachable branches (GE on a strictly-higher fillable order; NPC
when the order ties or is lower; NPC when no order exists) and the realized-gold
coupling for every venue/order combination.
"""
from artifactsmmo_cli.ai.liquidation_venue import Venue, choose_venue, realized_proceeds


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
