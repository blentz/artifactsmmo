"""choose_buy_venue / realized_cost (Python) must agree with
Formal.BuySourceVenue.chooseBuyVenue / realizedCost (Lean) over a small int grid of
npc prices and an order-book field ranging over {None} ∪ a small int range. This is
the DUAL of test_liquidation_venue_diff.py.

The `None` case is the anti-surrogate guard (no fillable standing sell order),
encoded to the oracle as `gePresent = 0`; any present order is `gePresent = 1,
gePrice`. The test asserts BOTH the chosen venue AND the realized cost, so a mutation
that drops the `isSome` guard (buying from a phantom order) or flips the strict `<`
to `<=` (choosing GE on a mere tie) diverges from the proof.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.buy_source_venue import BuyVenue, choose_buy_venue, realized_cost
from formal.diff.oracle_client import run_oracle

_ge = st.one_of(st.none(), st.integers(min_value=-20, max_value=20))


def _oracle_args(npc_price: int, ge: int | None) -> list[int]:
    if ge is None:
        return [npc_price, 0, 0]
    return [npc_price, 1, ge]


@settings(max_examples=600)
@given(npc_price=st.integers(min_value=-20, max_value=20), ge=_ge)
def test_venue_and_realized_match_lean(npc_price, ge):
    py_venue = choose_buy_venue(npc_price, ge)
    py_realized = realized_cost(npc_price, ge, py_venue)
    lean = run_oracle("buy_source_venue", [_oracle_args(npc_price, ge)])[0]
    assert lean["venue"] == (1 if py_venue is BuyVenue.GE else 0)
    assert lean["realized"] == py_realized


def test_tie_picks_npc_not_ge():
    """A standing order priced EXACTLY at the NPC buy price must NOT win GE (the `<`
    is strict). Pins the `<`-vs-`<=` mutation: at the tie the proof says NPC."""
    py = choose_buy_venue(10, 10)
    lean = run_oracle("buy_source_venue", [[10, 1, 10]])[0]
    assert py is BuyVenue.NPC
    assert lean["venue"] == 0


def test_no_order_never_picks_ge():
    """With no standing sell order GE is never chosen, even when the encoded order
    field happens to be 0. Pins the `isSome`-guard-drop mutation."""
    py = choose_buy_venue(5, None)
    lean = run_oracle("buy_source_venue", [[5, 0, 0]])[0]
    assert py is BuyVenue.NPC
    assert lean["venue"] == 0
    # realized cost at NPC venue is the npc_price, never a phantom 0.
    assert lean["realized"] == 5


def test_cheaper_order_picks_ge():
    """A standing sell order strictly cheaper than the NPC buy price wins GE, and the
    realized cost is the order price (the gold coupling)."""
    py = choose_buy_venue(15, 8)
    lean = run_oracle("buy_source_venue", [[15, 1, 8]])[0]
    assert py is BuyVenue.GE
    assert lean["venue"] == 1
    assert realized_cost(15, 8, py) == 8
    assert lean["realized"] == 8
