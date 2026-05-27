"""Differential test: the real Python `owned_count_pure` must agree with the
proved Lean `ownedCount`.

`owned_count_pure(inventory, bank, equipped_codes, code)` =
    inventory.get(code, 0)
  + (bank.get(code, 0) if bank is not None)
  + (1 if code in equipped_codes)

The Lean oracle is scalarized to the queried code's three store contributions
`[invCount, bankCount, equipped(0/1)]`. We generate those and build matching
Python stores. The three stores are disjoint by construction on the server:
`inventory` holds only UNEQUIPPED (spare) copies because equipping decrements
inventory and moves the item into a separate equipment slot, so the `+1` for an
equipped item is never a double-count. We exercise the full cross product
(including spare copies of an equipped item, which are correctly summed) and the
no-bank (None) path, and pin the load-bearing `ownedCount_counts_equipped`
property (an equipped item with zero spares/bank counts as 1).
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.tiers.owned_count import owned_count_pure
from formal.diff.oracle_client import run_oracle

CODE = "x"


@settings(max_examples=250)
@given(
    inv_count=st.integers(min_value=0, max_value=1000),
    bank_count=st.integers(min_value=0, max_value=1000),
    equipped=st.booleans(),
    bank_present=st.booleans(),
)
def test_python_matches_lean(inv_count, bank_count, equipped, bank_present):
    inventory = {CODE: inv_count} if inv_count else {}
    bank = ({CODE: bank_count} if bank_count else {}) if bank_present else None
    equipped_codes = [CODE] if equipped else []
    py = owned_count_pure(inventory, bank, equipped_codes, CODE)
    # The Lean oracle's bank contribution is unconditional (an absent bank is the
    # zero count). When the Python bank is None its contribution is 0 too, so the
    # comparison is exact only when we feed the oracle the effective bank count.
    effective_bank = bank_count if bank_present else 0
    lean = run_oracle("owned_count",
                      [[inv_count, effective_bank, 1 if equipped else 0]])[0]
    assert py == lean["owned"]


@settings(max_examples=250)
@given(
    # `inv_count` is the count of SPARE (unequipped) copies. When the item is
    # equipped these spares are still counted additively — the equipped copy lives
    # in a separate server slot, so spares + 1 is the true physical total, NOT a
    # double-count.
    inv_count=st.integers(min_value=0, max_value=1000),
    bank_count=st.integers(min_value=0, max_value=1000),
    equipped=st.booleans(),
)
def test_spares_and_equipped_sum_against_lean(inv_count, bank_count, equipped):
    inventory = {CODE: inv_count} if inv_count else {}
    equipped_codes = [CODE] if equipped else []
    bank = {CODE: bank_count} if bank_count else {}
    py = owned_count_pure(inventory, bank, equipped_codes, CODE)
    lean = run_oracle("owned_count",
                      [[inv_count, bank_count, 1 if equipped else 0]])[0]
    assert py == lean["owned"]
    # The count is exactly the sum of the three disjoint stores.
    assert py == inv_count + bank_count + (1 if equipped else 0)


def test_equipped_with_zero_spares_counts_as_one_against_lean():
    """ownedCount_counts_equipped: an item owned ONLY by wearing it (zero spares,
    zero bank) still counts as 1 — so ObtainItem.is_satisfied is True and the goal
    does not loop forever re-acquiring an already-equipped item."""
    py = owned_count_pure({}, {"sword": 0}, ["sword"], "sword")
    lean = run_oracle("owned_count", [[0, 0, 1]])[0]
    assert py == 1 == lean["owned"]


def test_equipped_plus_spare_sums_against_lean():
    """An equipped item with a spare copy in inventory counts as 2 — two swords
    are physically owned. This is correct additive counting (separate server
    slot), not a double-count of one item."""
    py = owned_count_pure({"sword": 1}, None, ["sword"], "sword")
    lean = run_oracle("owned_count", [[1, 0, 1]])[0]
    assert py == 2 == lean["owned"]  # equipped sword + one spare = two owned
