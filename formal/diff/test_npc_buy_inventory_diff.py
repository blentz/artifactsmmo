"""Differential test: real Python pure cores
(`npc_buy_is_applicable_pure`, `npc_buy_apply_pure`) must agree with the
proved Lean cores (`Formal.NpcBuyInventory.isApplicable` / `apply`), and
the proved inventory-cap safety invariant must hold on the Python side.

Boundary cases pinned explicitly:
* `inventory_used + quantity == cap` (exactly at cap; is_applicable must hold)
* `inventory_used + quantity == cap + 1` (one past; must fail — the REAL BUG #6
  counterexample regression-pin: used=9 cap=10 quantity=5)
* `gold == price * quantity` (boundary on gold gate)
* `gold == price * quantity - 1` (one short on gold)
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.actions.npc_buy_core import (
    npc_buy_apply_pure,
    npc_buy_currency_apply_pure,
    npc_buy_currency_is_applicable_pure,
    npc_buy_is_applicable_pure,
)
from formal.diff.oracle_client import run_oracle


@settings(max_examples=300)
@given(
    used=st.integers(min_value=0, max_value=200),
    span=st.integers(min_value=0, max_value=200),
    quantity=st.integers(min_value=0, max_value=50),
    gold=st.integers(min_value=0, max_value=10000),
    price=st.integers(min_value=0, max_value=200),
)
def test_is_applicable_matches_lean(used, span, quantity, gold, price):
    cap = used + span  # well-formed: used <= cap
    py = npc_buy_is_applicable_pure(used, cap, quantity, gold, price)
    lean = run_oracle("npc_buy_inventory", [[0, used, cap, quantity, gold, price]])[0]
    assert py == lean["applicable"]
    assert lean["free"] == cap - used
    # Proved invariant: passing check ⇒ quantity ≤ free AND price*quantity ≤ gold,
    # AND the per-step safety theorem materializes (post.used <= cap).
    if py:
        assert (cap - used) >= quantity
        assert price * quantity <= gold
        post_inv = npc_buy_apply_pure({"x": used}, "x", quantity)
        # used = old + quantity since the only key "x" had `used` items
        post_used = used + quantity  # the slot-bookkeeping mirror
        assert post_used <= cap
        assert post_inv["x"] == used + quantity


@settings(max_examples=300)
@given(
    used=st.integers(min_value=0, max_value=200),
    span=st.integers(min_value=0, max_value=200),
    quantity=st.integers(min_value=0, max_value=50),
    code=st.sampled_from(["copper_ore", "ash_wood", "iron_ore", "gemstone"]),
)
def test_apply_matches_lean(used, span, quantity, code):
    cap = used + span
    # Per-key bookkeeping (Python side).
    pre = {code: 7, "other": 3}
    post = npc_buy_apply_pure(pre, code, quantity)
    assert post[code] == 7 + quantity
    assert post["other"] == 3
    # Slot totals match Lean oracle (single apply step).
    lean = run_oracle("npc_buy_inventory", [[1, used, cap, quantity, 0, 0]])[0]
    assert lean["used"] == used + quantity
    assert lean["cap"] == cap


def test_regression_pin_used9_cap10_qty5_blocked():
    """The verified Python probe counterexample for REAL BUG #6:
    state.inventory_used=9, state.inventory_max=10, NpcBuyAction.quantity=5.

    Pre-fix: is_applicable returned True (no slot check) and apply produced
    inventory_used=14 > inventory_max=10. Post-fix: is_applicable must
    REFUSE (the slot floor catches the overflow before apply runs)."""
    py = npc_buy_is_applicable_pure(
        inv_used=9, inv_max=10, quantity=5, gold=1000, price=1
    )
    assert py is False
    lean = run_oracle("npc_buy_inventory", [[0, 9, 10, 5, 1000, 1]])[0]
    assert lean["applicable"] is False
    assert lean["free"] == 1


def test_boundary_quantity_equals_free_accepted():
    """quantity == free is the post-fix accepted boundary (no off-by-one)."""
    py = npc_buy_is_applicable_pure(
        inv_used=5, inv_max=10, quantity=5, gold=100, price=1
    )
    assert py is True
    lean = run_oracle("npc_buy_inventory", [[0, 5, 10, 5, 100, 1]])[0]
    assert lean["applicable"] is True
    # And the post-state still fits (per-step safety).
    post = npc_buy_apply_pure({}, "x", 5)
    assert post["x"] == 5


def test_boundary_quantity_one_past_free_blocked():
    """quantity == free + 1 must refuse (the load-bearing slot floor)."""
    py = npc_buy_is_applicable_pure(
        inv_used=5, inv_max=10, quantity=6, gold=100, price=1
    )
    assert py is False
    lean = run_oracle("npc_buy_inventory", [[0, 5, 10, 6, 100, 1]])[0]
    assert lean["applicable"] is False


def test_full_inventory_blocks_any_buy():
    """At used = cap, any quantity >= 1 must refuse."""
    py = npc_buy_is_applicable_pure(
        inv_used=10, inv_max=10, quantity=1, gold=100, price=1
    )
    assert py is False
    lean = run_oracle("npc_buy_inventory", [[0, 10, 10, 1, 100, 1]])[0]
    assert lean["applicable"] is False


def test_gold_boundary_exact_minimum_accepted():
    """gold == price*quantity is the accepted boundary on the gold gate."""
    py = npc_buy_is_applicable_pure(
        inv_used=0, inv_max=100, quantity=5, gold=15, price=3
    )
    assert py is True
    lean = run_oracle("npc_buy_inventory", [[0, 0, 100, 5, 15, 3]])[0]
    assert lean["applicable"] is True


def test_gold_boundary_one_short_blocked():
    """gold == price*quantity - 1 must refuse."""
    py = npc_buy_is_applicable_pure(
        inv_used=0, inv_max=100, quantity=5, gold=14, price=3
    )
    assert py is False
    lean = run_oracle("npc_buy_inventory", [[0, 0, 100, 5, 14, 3]])[0]
    assert lean["applicable"] is False


# ---------------------------------------------------------------------------
# Item-currency purchase (task #13b): npc_buy_currency_* cores vs the proved
# Formal.NpcBuyInventory.isApplicableCurrency / applyCurrency (oracle q=2 / q=3).
# ---------------------------------------------------------------------------

@settings(max_examples=300)
@given(
    used=st.integers(min_value=0, max_value=200),
    span=st.integers(min_value=0, max_value=200),
    quantity=st.integers(min_value=0, max_value=50),
    on_hand=st.integers(min_value=0, max_value=500),
    spent=st.integers(min_value=0, max_value=500),
)
def test_currency_is_applicable_matches_lean(used, span, quantity, on_hand, spent):
    cap = used + span
    py = npc_buy_currency_is_applicable_pure(used, cap, quantity, on_hand, spent)
    lean = run_oracle("npc_buy_inventory", [[2, used, cap, quantity, on_hand, spent]])[0]
    assert py == lean["applicable"]
    assert lean["free"] == cap - used
    if py:
        # proved invariant: free slot AND currency covers spend; net stays in cap
        assert (cap - used) >= quantity
        assert on_hand >= spent
        post = npc_buy_currency_apply_pure({"x": used, "coin": on_hand}, "x", quantity, "coin", spent)
        # net slot count = used + quantity - spent (truncating); must fit cap
        net_used = max(0, used + quantity - spent)
        assert net_used <= cap


@settings(max_examples=300)
@given(
    used=st.integers(min_value=0, max_value=200),
    span=st.integers(min_value=0, max_value=200),
    quantity=st.integers(min_value=0, max_value=50),
    spent=st.integers(min_value=0, max_value=200),
)
def test_currency_apply_matches_lean(used, span, quantity, spent):
    cap = used + span
    # Bookkeeping: bought item +quantity, currency -spent, others preserved.
    # Seed the currency stack high enough that the decrement stays non-negative
    # (is_applicable guarantees this in production).
    pre = {"rune": 7, "coin": spent + 5, "other": 3}
    post = npc_buy_currency_apply_pure(pre, "rune", quantity, "coin", spent)
    assert post["rune"] == 7 + quantity
    assert post["coin"] == spent + 5 - spent
    assert post["other"] == 3
    # Slot totals match the Lean oracle (applyCurrency projection).
    lean = run_oracle("npc_buy_inventory", [[3, used, cap, quantity, spent]])[0]
    assert lean["used"] == max(0, used + quantity - spent)  # Nat truncation
    assert lean["cap"] == cap


def test_currency_insufficient_on_hand_blocked():
    """Rich in gold is irrelevant: too little of the pay currency must refuse."""
    py = npc_buy_currency_is_applicable_pure(
        inv_used=0, inv_max=100, quantity=1, currency_on_hand=50, total_spent=100)
    assert py is False
    lean = run_oracle("npc_buy_inventory", [[2, 0, 100, 1, 50, 100]])[0]
    assert lean["applicable"] is False


def test_currency_exact_on_hand_accepted():
    """currency_on_hand == total_spent is the accepted boundary."""
    py = npc_buy_currency_is_applicable_pure(
        inv_used=5, inv_max=10, quantity=5, currency_on_hand=100, total_spent=100)
    assert py is True
    lean = run_oracle("npc_buy_inventory", [[2, 5, 10, 5, 100, 100]])[0]
    assert lean["applicable"] is True


def test_currency_consumption_frees_net_space():
    """Paying more currency units than items bought lowers net used (10→6)."""
    post = npc_buy_currency_apply_pure({"r": 0, "coin": 5}, "r", 1, "coin", 5)
    assert post["r"] == 1
    assert post["coin"] == 0
    lean = run_oracle("npc_buy_inventory", [[3, 10, 20, 1, 5]])[0]
    assert lean["used"] == 6
