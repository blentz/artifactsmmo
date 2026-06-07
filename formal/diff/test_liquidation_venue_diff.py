"""choose_venue / realized_proceeds (Python) must agree with
Formal.LiquidationVenue.chooseVenue / realizedProceeds (Lean) over a small int
grid of npc prices and an order-book field ranging over {None} ∪ a small int range.

The `None` case is the anti-surrogate guard (no fillable standing order), encoded
to the oracle as `gePresent = 0`; any present order is `gePresent = 1, geProceeds`.
The test asserts BOTH the chosen venue AND the realized gold, so a mutation that
drops the `isSome` guard (choosing GE on a phantom order) or flips the strict `>`
to `>=` (choosing GE on a mere tie) diverges from the proof.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.liquidation_venue import Venue, choose_venue, realized_proceeds
from formal.diff.oracle_client import run_oracle

_ge = st.one_of(st.none(), st.integers(min_value=-20, max_value=20))


def _oracle_args(npc_pay: int, ge: int | None) -> list[int]:
    if ge is None:
        return [npc_pay, 0, 0]
    return [npc_pay, 1, ge]


@settings(max_examples=600)
@given(npc_pay=st.integers(min_value=-20, max_value=20), ge=_ge)
def test_venue_and_realized_match_lean(npc_pay, ge):
    py_venue = choose_venue(npc_pay, ge)
    py_realized = realized_proceeds(npc_pay, ge, py_venue)
    lean = run_oracle("liquidation_venue", [_oracle_args(npc_pay, ge)])[0]
    assert lean["venue"] == (1 if py_venue is Venue.GE else 0)
    assert lean["realized"] == py_realized


def test_tie_picks_npc_not_ge():
    """A standing order paying EXACTLY the NPC price must NOT win GE (the `>` is
    strict). Pins the `>`-vs-`>=` mutation: at the tie the proof says NPC."""
    py = choose_venue(10, 10)
    lean = run_oracle("liquidation_venue", [[10, 1, 10]])[0]
    assert py is Venue.NPC
    assert lean["venue"] == 0


def test_no_order_never_picks_ge():
    """With no standing order GE is never chosen, even when the encoded order field
    happens to be 0. Pins the `isSome`-guard-drop mutation."""
    py = choose_venue(-5, None)
    lean = run_oracle("liquidation_venue", [[-5, 0, 0]])[0]
    assert py is Venue.NPC
    assert lean["venue"] == 0
    # realized proceeds at NPC venue is the npc_pay, never a phantom 0.
    assert lean["realized"] == -5
