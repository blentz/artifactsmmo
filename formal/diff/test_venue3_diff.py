"""choose_venue3 / choose_buy_venue3 (Python) must agree with
Formal.LiquidationVenue.chooseVenue3 / Formal.BuySourceVenue.chooseBuyVenue3 (Lean)
over an int grid of npc prices with the fillable-order and the own-post-price fields
each ranging over {None} ∪ a small int range.

This is the THREE-WAY (FILL / POST / NPC) extension of the two-way venue diff tests.
Each `None` field is the anti-surrogate anchor guard, encoded to the oracle as its
present-flag = 0. The test asserts the chosen venue matches the 0/1/2 code (NPC=0,
GE=1, GE_POST=2), so a mutation that flips a `>=`/`>` boundary, drops a fail-closed
anchor guard (posting on a phantom order), or mis-orders the FILL-beats-POST tie
diverges from the proof.
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.buy_source_venue import BuyVenue, choose_buy_venue3
from artifactsmmo_cli.ai.liquidation_venue import Venue, choose_venue3
from formal.diff.oracle_client import run_oracle

_field = st.one_of(st.none(), st.integers(min_value=-20, max_value=20))
_npc = st.integers(min_value=-20, max_value=20)

_SELL_CODE = {Venue.NPC: 0, Venue.GE: 1, Venue.GE_POST: 2}
_BUY_CODE = {BuyVenue.NPC: 0, BuyVenue.GE: 1, BuyVenue.GE_POST: 2}


def _oracle_args(npc: int, fill: int | None, post: int | None) -> list[int]:
    fill_part = [0, 0] if fill is None else [1, fill]
    post_part = [0, 0] if post is None else [1, post]
    return [npc, *fill_part, *post_part]


@settings(max_examples=800)
@given(npc=_npc, fill=_field, post=_field)
def test_choose_venue3_matches_lean(npc, fill, post):
    py = choose_venue3(npc, fill, post)
    lean = run_oracle("choose_venue3", [_oracle_args(npc, fill, post)])[0]
    assert lean["venue"] == _SELL_CODE[py]


@settings(max_examples=800)
@given(npc=_npc, fill=_field, post=_field)
def test_choose_buy_venue3_matches_lean(npc, fill, post):
    py = choose_buy_venue3(npc, fill, post)
    lean = run_oracle("choose_buy_venue3", [_oracle_args(npc, fill, post)])[0]
    assert lean["venue"] == _BUY_CODE[py]


def test_sell_fill_beats_post_at_tie():
    """A fillable buy order paying EXACTLY our post price wins FILL (immediate beats
    deferred at equal terms). Pins the `>=`: a strict `>` would defer to GE_POST."""
    py = choose_venue3(5, 8, 8)
    lean = run_oracle("choose_venue3", [[5, 1, 8, 1, 8]])[0]
    assert py is Venue.GE
    assert lean["venue"] == 1


def test_sell_no_anchor_forbids_post():
    """With no post-price anchor and no worthwhile fill, POST is forbidden -> NPC.
    Pins the fail-closed post guard."""
    py = choose_venue3(10, None, None)
    lean = run_oracle("choose_venue3", [[10, 0, 0, 0, 0]])[0]
    assert py is Venue.NPC
    assert lean["venue"] == 0


def test_buy_fill_beats_post_at_tie():
    """A sell order costing EXACTLY our post price wins FILL (dual of the sell tie).
    Pins the `<=`: a strict `<` would defer to GE_POST."""
    py = choose_buy_venue3(15, 8, 8)
    lean = run_oracle("choose_buy_venue3", [[15, 1, 8, 1, 8]])[0]
    assert py is BuyVenue.GE
    assert lean["venue"] == 1


def test_buy_post_beats_npc():
    """With no fillable order but a post price strictly below the NPC cost, POST wins."""
    py = choose_buy_venue3(15, None, 12)
    lean = run_oracle("choose_buy_venue3", [[15, 0, 0, 1, 12]])[0]
    assert py is BuyVenue.GE_POST
    assert lean["venue"] == 2
