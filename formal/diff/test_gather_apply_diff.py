"""Differential test: real Python pure cores
(`gather_is_applicable_pure`, `gather_apply_pure`) must agree with the proved
Lean cores (`Formal.GatherApply.isApplicable` / `applyN`), and the proved
inventory-cap safety invariant must hold on the Python side.

Boundary cases pinned explicitly:
* `inventory_used == cap - k` (exactly k slots, is_applicable must hold)
* `inventory_used == cap - k + 1` (one short, must fail)
* `inventory_used == cap` (apply would overrun if invoked — `is_applicable` blocks)
* multi-step chains with `n == cap - used` (chain exactly fills the cap)
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.actions.gather_apply_core import (
    GatherInv,
    gather_apply_pure,
    gather_is_applicable_pure,
)
from formal.diff.oracle_client import run_oracle


@settings(max_examples=300)
@given(
    used=st.integers(min_value=0, max_value=200),
    span=st.integers(min_value=0, max_value=200),
    k=st.integers(min_value=1, max_value=10),
)
def test_is_applicable_matches_lean(used, span, k):
    cap = used + span  # well-formed: used <= cap
    inv = GatherInv(used=used, cap=cap, item_count={})
    py = gather_is_applicable_pure(inv, k)
    # hasDrop=0 (drop_item None) recovers the quantity-only check.
    lean = run_oracle("gather_apply", [[0, used, cap, k, 0, 0, 0, 0]])[0]
    assert py == lean["applicable"]
    assert lean["free"] == cap - used
    # Proved invariant: passing check ⇒ free ≥ k
    if py:
        assert (cap - used) >= k
        # And the per-step safety theorem materializes in Python:
        post = gather_apply_pure(inv, "x")
        assert post.used <= cap


@settings(max_examples=300)
@given(
    used=st.integers(min_value=0, max_value=200),
    span=st.integers(min_value=0, max_value=200),
    code=st.sampled_from(["copper_ore", "ash_wood", "iron_ore", "x"]),
)
def test_apply_matches_lean(used, span, code):
    cap = used + span
    inv = GatherInv(used=used, cap=cap, item_count={code: 7, "other": 3})
    post = gather_apply_pure(inv, code)
    # Per-key bookkeeping (Python-side only; Lean tracks slot totals).
    assert post.cap == cap
    assert post.used == used + 1
    assert post.item_count[code] == 8
    assert post.item_count["other"] == 3
    # Slot totals match Lean oracle (applyN with n=1).
    lean = run_oracle("gather_apply", [[1, used, cap, 1]])[0]
    assert post.used == lean["used"]
    assert post.cap == lean["cap"]


@settings(max_examples=200)
@given(
    used=st.integers(min_value=0, max_value=200),
    span=st.integers(min_value=0, max_value=200),
    n=st.integers(min_value=0, max_value=10),
)
def test_chain_matches_lean_and_stays_in_cap_when_admissible(used, span, n):
    """Multi-step chain: if start state has at least `n` free slots, applying
    `n` consecutive mints keeps `used <= cap` (the planner-chain safety
    theorem `chain_safe`)."""
    cap = used + span
    # Apply `n` consecutive mints (the planner-side mint, ignoring per-step
    # is_applicable to exercise the chain bookkeeping).
    inv = GatherInv(used=used, cap=cap, item_count={"x": 0})
    cur = inv
    for _ in range(n):
        cur = gather_apply_pure(cur, "x")
    lean = run_oracle("gather_apply", [[1, used, cap, n]])[0]
    assert cur.used == lean["used"]
    assert cur.cap == lean["cap"]
    # When the chain is admissible (n ≤ free), the proven invariant holds.
    if n <= (cap - used):
        assert cur.used <= cap


def test_boundary_exactly_three_free_is_applicable_against_lean():
    """At `used = cap - 3`, the production `MIN_FREE_SLOTS = 3` check passes."""
    inv = GatherInv(used=5, cap=8, item_count={})
    assert gather_is_applicable_pure(inv, 3) is True
    lean = run_oracle("gather_apply", [[0, 5, 8, 3, 0, 0, 0, 0]])[0]
    assert lean["applicable"] is True
    # And the post-state still fits.
    post = gather_apply_pure(inv, "ore")
    assert post.used == 6
    assert post.used <= post.cap


def test_boundary_two_free_blocks_at_min_free_slots():
    """At `used = cap - 2`, with `MIN_FREE_SLOTS = 3`, the planner-side check
    correctly REFUSES — the load-bearing precondition that keeps the planner
    from chaining apply past `inventory_max`."""
    inv = GatherInv(used=6, cap=8, item_count={})
    assert gather_is_applicable_pure(inv, 3) is False
    lean = run_oracle("gather_apply", [[0, 6, 8, 3, 0, 0, 0, 0]])[0]
    assert lean["applicable"] is False


def test_full_inventory_blocks_is_applicable_against_lean():
    """At `used = cap`, `is_applicable` must refuse for any k ≥ 1: the
    contested-case anchor (apply WOULD overrun if invoked, planner's check
    prevents it)."""
    inv = GatherInv(used=8, cap=8, item_count={})
    assert gather_is_applicable_pure(inv, 1) is False
    lean = run_oracle("gather_apply", [[0, 8, 8, 1, 0, 0, 0, 0]])[0]
    assert lean["applicable"] is False


def test_slot_new_drop_no_free_slot_blocked_against_lean():
    """A NEW drop code at 0 free slots is blocked by the slot cap even though
    quantity has ample room — the slot-exhaustion contract (Task 4)."""
    inv = GatherInv(used=20, cap=124, item_count={f"i{n}": 1 for n in range(20)},
                    slots_used=20, slots_max=20)
    assert gather_is_applicable_pure(inv, 1, "copper_ore") is False
    # hasDrop=1, newStacks=1 (new code), slotsUsed=20, slotsMax=20 -> no slot.
    lean = run_oracle("gather_apply", [[0, 20, 124, 1, 1, 1, 20, 20]])[0]
    assert lean["applicable"] is False


def test_slot_held_drop_no_free_slot_allowed_against_lean():
    """Growing a HELD drop at 0 free slots is allowed — no new slot needed
    (quantity permitting)."""
    inv = GatherInv(used=20, cap=124,
                    item_count={"copper_ore": 5, **{f"i{n}": 1 for n in range(19)}},
                    slots_used=20, slots_max=20)
    assert gather_is_applicable_pure(inv, 1, "copper_ore") is True
    # hasDrop=1, newStacks=0 (held code), slotsUsed=20, slotsMax=20.
    lean = run_oracle("gather_apply", [[0, 20, 124, 1, 1, 0, 20, 20]])[0]
    assert lean["applicable"] is True


@settings(max_examples=300)
@given(
    used=st.integers(min_value=0, max_value=200),
    span=st.integers(min_value=0, max_value=200),
    held=st.booleans(),
    slots_used=st.integers(min_value=0, max_value=40),
    slots_span=st.integers(min_value=0, max_value=40),
)
def test_slot_aware_applicable_matches_lean(used, span, held, slots_used, slots_span):
    """Fuzz the slot-aware applicability (hasDrop=1) against the Lean oracle:
    a new stack needs a free slot AND quantity headroom; a held stack needs
    only quantity headroom."""
    cap = used + span
    slots_max = slots_used + slots_span
    code = "copper_ore"
    item_count = {code: 5} if held else {"other": 1}
    inv = GatherInv(used=used, cap=cap, item_count=item_count,
                    slots_used=slots_used, slots_max=slots_max)
    py = gather_is_applicable_pure(inv, 1, code)
    new_stacks = 0 if held else 1
    lean = run_oracle(
        "gather_apply", [[0, used, cap, 1, 1, new_stacks, slots_used, slots_max]])[0]
    assert py == lean["applicable"]
