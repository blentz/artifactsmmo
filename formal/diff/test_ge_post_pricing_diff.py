"""sell_post_price / buy_post_price (Python) must agree with
Formal.GePostPricing.sellPostPrice / buyPostPrice (Lean) over an int grid where the
best-standing-order anchor ranges over {None} ∪ a small int range.

The `None` anchor is the FAIL-CLOSED guard (no live order to anchor on -> no posted
price), encoded to the oracle as `anchorPresent = 0` and mirrored by `present = false`.
Each test asserts the FULL `Option Int`: the no-post `None` case AND the posted price
including the NPC-floor / alt-cost-ceiling clamp — so a mutation that drops the anchor
guard (posting on an empty book), or that flips the `max`/`min` clamp (posting a price
strictly worse than the realizable alternative), diverges from the proof.
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.ge_post_pricing import buy_post_price, sell_post_price
from formal.diff.oracle_client import run_oracle

_anchor = st.one_of(st.none(), st.integers(min_value=-20, max_value=20))
_bound = st.integers(min_value=-20, max_value=20)
_margin = st.integers(min_value=0, max_value=5)


def _oracle_args(anchor: int | None, bound: int, margin: int) -> list[int]:
    if anchor is None:
        return [0, 0, bound, margin]
    return [1, anchor, bound, margin]


def _assert_option(lean: dict, py: int | None) -> None:
    """Assert the Lean present-flag+value encoding matches the Python Option Int."""
    if py is None:
        assert lean["present"] is False
    else:
        assert lean["present"] is True
        assert lean["value"] == py


@settings(max_examples=600)
@given(anchor=_anchor, npc_sellback=_bound, margin=_margin)
def test_sell_post_price_matches_lean(anchor, npc_sellback, margin):
    py = sell_post_price(anchor, npc_sellback, margin)
    lean = run_oracle("sell_post_price", [_oracle_args(anchor, npc_sellback, margin)])[0]
    _assert_option(lean, py)


@settings(max_examples=600)
@given(anchor=_anchor, alt_cost=_bound, margin=_margin)
def test_buy_post_price_matches_lean(anchor, alt_cost, margin):
    py = buy_post_price(anchor, alt_cost, margin)
    lean = run_oracle("buy_post_price", [_oracle_args(anchor, alt_cost, margin)])[0]
    _assert_option(lean, py)


def test_sell_no_anchor_fails_closed():
    """No standing sell order -> no posted price. Pins the fail-closed guard: dropping
    the `best_sell is None` short-circuit would post on an empty book."""
    assert sell_post_price(None, 5, 1) is None
    lean = run_oracle("sell_post_price", [[0, 0, 5, 1]])[0]
    assert lean["present"] is False


def test_buy_no_anchor_fails_closed():
    """No standing buy order -> no posted price (dual of the sell fail-closed case)."""
    assert buy_post_price(None, 15, 1) is None
    lean = run_oracle("buy_post_price", [[0, 0, 15, 1]])[0]
    assert lean["present"] is False


def test_sell_clamps_to_floor():
    """When one-tick-below-best would dip below the NPC floor+margin, the post price
    clamps UP to the floor. Pins the `max` clamp: a `min` mutation would post below
    the NPC sell-back, i.e. strictly worse than dumping to the NPC."""
    py = sell_post_price(6, 5, 1)  # best-1 == 5, floor == 6 -> clamps to 6
    lean = run_oracle("sell_post_price", [[1, 6, 5, 1]])[0]
    assert py == 6
    assert lean["present"] is True
    assert lean["value"] == 6


def test_buy_clamps_to_ceiling():
    """When one-tick-above-best would exceed the alt-cost-minus-margin ceiling, the
    post price clamps DOWN to the ceiling. Pins the `min` clamp: a `max` mutation would
    post above the realizable alternative cost."""
    py = buy_post_price(14, 15, 1)  # best+1 == 15, ceiling == 14 -> clamps to 14
    lean = run_oracle("buy_post_price", [[1, 14, 15, 1]])[0]
    assert py == 14
    assert lean["present"] is True
    assert lean["value"] == 14
